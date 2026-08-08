"""
高级时序模型模块 - 真正的HMM和多元Copula
【修复】hmmlearn/sklearn >= 1.9 兼容: GaussianMixture.fit() 不再支持 sample_weight，
自动检测并降级为加权自助采样(weighted bootstrap)策略。
"""

import numpy as np
import inspect
from typing import Dict, Tuple, Optional, List
from sklearn.mixture import GaussianMixture
from scipy import stats
import logging

from src.core.config import ModelConfig, get_model_config

logger = logging.getLogger(__name__)

# 【修复】全局缓存 GMM.fit() 是否支持 sample_weight 参数，避免每轮反复探测
_GMM_FIT_SUPPORTS_SAMPLE_WEIGHT: Optional[bool] = None


def _gmm_fit_supports_sample_weight() -> bool:
    """检测 GaussianMixture.fit() 是否接受 sample_weight 参数（仅检测一次并缓存）"""
    global _GMM_FIT_SUPPORTS_SAMPLE_WEIGHT
    if _GMM_FIT_SUPPORTS_SAMPLE_WEIGHT is not None:
        return _GMM_FIT_SUPPORTS_SAMPLE_WEIGHT
    try:
        params = inspect.signature(GaussianMixture.fit).parameters
        _GMM_FIT_SUPPORTS_SAMPLE_WEIGHT = 'sample_weight' in params
    except Exception:
        _GMM_FIT_SUPPORTS_SAMPLE_WEIGHT = False
    return _GMM_FIT_SUPPORTS_SAMPLE_WEIGHT


def _weighted_bootstrap_fit(model: GaussianMixture, observations: np.ndarray,
                            weights: np.ndarray, n_resample: int = None) -> None:
    """
    当 GMM.fit() 不支持 sample_weight 时的替代品：
    根据权重对观测进行有放回自助采样，然后对重采样后的数据集执行无权重 fit。
    """
    n_obs = len(observations)
    if n_resample is None:
        n_resample = max(n_obs, 500)
    weights = np.asarray(weights, dtype=np.float64).ravel()
    weights = weights / (weights.sum() + 1e-12)
    rng = np.random.default_rng(42)
    indices = rng.choice(n_obs, size=n_resample, replace=True, p=weights)
    resampled = observations[indices]
    model.fit(resampled)


class HiddenMarkovModel:
    """
    真正的隐马尔可夫模型 - 使用GMM发射概率
    支持自适应状态数选择 (BIC/AIC准则) 和模型诊断
    """

    def __init__(self, n_states: int = 4, n_mixtures: int = 2,
                 auto_select: bool = False, criterion: str = 'bic',
                 model_config: Optional[ModelConfig] = None):
        _mc = model_config or get_model_config()
        hmm_cfg = _mc.hmm_config()

        self._n_states_input = n_states if n_states != 4 else hmm_cfg.get('n_states', 4)
        self._n_mixtures_input = n_mixtures if n_mixtures != 2 else hmm_cfg.get('n_mixtures', 2)
        self._auto_select = auto_select if auto_select is not False else hmm_cfg.get('auto_select', False)
        self._criterion = (criterion.lower() if criterion != 'bic' else hmm_cfg.get('criterion', 'bic')).lower()

        self.n_states = n_states if isinstance(n_states, int) else 4
        self.n_mixtures = n_mixtures if isinstance(n_mixtures, int) else 2
        self.transition_matrix: Optional[np.ndarray] = None
        self.emission_models: List[GaussianMixture] = []
        self.initial_probs: Optional[np.ndarray] = None
        self.fitted = False

        self.log_likelihood: float = float('-inf')
        self.bic_value: float = float('inf')
        self.aic_value: float = float('inf')
        self.converged: bool = False
        self.n_iterations: int = 0
        self._selection_history: List[Dict] = []

    def _count_free_params(self) -> int:
        """计算HMM模型的自由参数数量"""
        n_feat = 1
        k_params = self.n_states * (self.n_states - 1)
        pi_params = self.n_states - 1
        emission_params = 0
        for s in range(self.n_states):
            if s < len(self.emission_models) and hasattr(self.emission_models[s], 'n_components'):
                nc = self.emission_models[s].n_components
                emission_params += nc - 1
                emission_params += nc * n_feat
                emission_params += nc * n_feat
        return k_params + pi_params + emission_params

    def _compute_bic_aic(self, observations: np.ndarray) -> Tuple[float, float]:
        """计算当前模型的BIC和AIC值"""
        n_obs = len(observations)
        n_params = self._count_free_params()
        ll = self.log_likelihood
        bic = -2 * ll + n_params * np.log(n_obs)
        aic = -2 * ll + 2 * n_params
        return bic, aic

    def select_optimal_states(self, data: np.ndarray,
                               max_states: int = 8,
                               min_states: int = 2) -> Dict:
        """
        使用BIC/AIC准则自动选择最优隐状态数

        Args:
            data: 观测数据
            max_states: 最大候选状态数
            min_states: 最小候选状态数

        Returns:
            包含选择结果的字典: {best_n_states, criteria_scores, ...}
        """
        data = np.asarray(data).reshape(-1, 1)
        max_states = min(max_states, max(min_states, len(data) // 10))
        results = []

        for n_s in range(min_states, max_states + 1):
            try:
                candidate = HiddenMarkovModel(
                    n_states=n_s,
                    n_mixtures=self.n_mixtures if isinstance(self._n_mixtures_input, int) else 'auto'
                )
                candidate.fit(data)

                if candidate.fitted and not np.isinf(candidate.log_likelihood):
                    bic_val, aic_val = candidate._compute_bic_aic(data)
                    score = bic_val if self._criterion == 'bic' else aic_val
                    results.append({
                        'n_states': n_s,
                        'log_likelihood': candidate.log_likelihood,
                        'bic': bic_val,
                        'aic': aic_val,
                        'score': score,
                        'converged': candidate.converged,
                        'n_iterations': candidate.n_iterations
                    })
            except Exception as e:
                logger.warning(f"[HMM] n_states={n_s} 训练失败: {e}")
                continue

        if not results:
            logger.warning("[HMM] 所有候选状态数均训练失败，使用默认值")
            return {'best_n_states': 4, 'criteria_scores': [], 'criterion': self._criterion}

        results.sort(key=lambda x: x['score'])
        best = results[0]
        self._selection_history = results

        logger.info(f"[HMM] 最优状态数选择完成: n_states={best['n_states']}, "
                   f"{self._criterion.upper()}={best['score']:.2f}, "
                   f"LL={best['log_likelihood']:.2f}")
        return {
            'best_n_states': best['n_states'],
            'criteria_scores': results,
            'criterion': self._criterion,
            'all_results': results
        }

    def select_optimal_mixtures(self, data: np.ndarray,
                                 max_mixtures: int = 5,
                                 min_mixtures: int = 1) -> int:
        """
        为每个隐状态选择最优GMM混合成分数

        Args:
            data: 观测数据
            max_mixtures: 最大混合成分数
            min_mixtures: 最小混合成分数

        Returns:
            最优混合成分数
        """
        data = np.asarray(data).reshape(-1, 1)
        best_n_mix = 2
        best_score = float('inf')

        for n_m in range(min_mixtures, max_mixtures + 1):
            try:
                gm = GaussianMixture(n_components=n_m,
                                    covariance_type='diag',
                                    random_state=42,
                                    n_init=1,
                                    max_iter=20)
                gm.fit(data)
                n_params = 2 * n_m + (n_m - 1)
                bic = -2 * gm.score(data) * len(data) + n_params * np.log(len(data))
                if bic < best_score:
                    best_score = bic
                    best_n_mix = n_m
            except Exception as e:
                logger.warning(f"[HMM.select_optimal_mixtures] n_mixtures={n_m} 拟合失败: {e}")
                continue

        logger.info(f"[HMM] GMM最优混合成分数: {best_n_mix}")
        return best_n_mix

    def fit(self, observations: np.ndarray) -> "HiddenMarkovModel":
        observations = np.asarray(observations).reshape(-1, 1)
        n_obs = len(observations)

        auto_mode = (self._n_states_input in ('auto', None) or self._auto_select)

        if auto_mode and n_obs >= 20:
            selection_result = self.select_optimal_states(observations)
            optimal_n = selection_result.get('best_n_states', 4)
            self.n_states = optimal_n
            logger.info(f"[HMM] 自适应模式: 选择 n_states={optimal_n}")

        auto_mix = (self._n_mixtures_input in ('auto', None))
        if auto_mix and n_obs >= 20:
            opt_mix = self.select_optimal_mixtures(observations)
            self.n_mixtures = opt_mix

        if n_obs < 10:
            logger.warning("[HMM] 数据太少，使用简化模型")
            self.transition_matrix = np.ones((self.n_states, self.n_states)) / self.n_states
            self.initial_probs = np.ones(self.n_states) / self.n_states
            self.emission_models = []
            self.fitted = True
            self.converged = True
            self.n_iterations = 0
            self.log_likelihood = float('-inf')
            self.bic_value, self.aic_value = float('inf'), float('inf')
            return self

        self.transition_matrix = np.random.rand(self.n_states, self.n_states)
        self.transition_matrix /= self.transition_matrix.sum(axis=1, keepdims=True)

        self.emission_models = []
        for _ in range(self.n_states):
            gm = GaussianMixture(
                n_components=min(self.n_mixtures, 5),
                covariance_type='diag',
                random_state=42,
                n_init=1,
                max_iter=20
            )
            self.emission_models.append(gm)

        # 在 EM 迭代前对所有发射模型进行初始拟合，确保 predict_proba 时 GMM 已 fitted。
        # 避免因第一次 _e_step 使用未拟合 GMM 产生无效 gamma，进而导致 _m_step 静默跳过某些状态的 fit。
        for s in range(self.n_states):
            try:
                self.emission_models[s].fit(observations)
            except Exception as e:
                logger.warning(f"[HMM.fit] 状态 {s} 初始发射模型拟合失败: {e}")

        self.initial_probs = np.ones(self.n_states) / self.n_states
        self._last_ll = float('-inf')
        self.converged = False
        self.n_iterations = 0

        for iteration in range(50):
            gamma = self._e_step(observations)
            self._m_step(observations, gamma)
            self.n_iterations = iteration + 1

            ll = self._compute_log_likelihood(observations, gamma)
            self.log_likelihood = ll

            if iteration > 0:
                if abs(ll - self._last_ll) < 1e-6:
                    self.converged = True
                    break
            self._last_ll = ll

        self.fitted = True
        self.bic_value, self.aic_value = self._compute_bic_aic(observations)

        logger.info(f"[HMM] 模型拟合完成: {n_obs}观测, {self.n_states}状态, "
                   f"{self.n_iterations}轮, 收敛={self.converged}, "
                   f"LL={self.log_likelihood:.2f}, BIC={self.bic_value:.2f}, AIC={self.aic_value:.2f}")
        return self

    def _e_step(self, observations: np.ndarray) -> np.ndarray:
        n_obs = len(observations)
        gamma = np.zeros((n_obs, self.n_states))

        for i in range(n_obs):
            for s in range(self.n_states):
                try:
                    emission_prob = np.exp(
                        self.emission_models[s].score_samples(observations[i:i+1])[0]
                    ) if self.emission_models else 0.1
                except Exception as e:
                    logger.warning(f"[HMM._e_step] 观测 {i} 状态 {s} 发射概率计算失败: {e}")
                    emission_prob = 0.1

                gamma[i, s] = self.initial_probs[s] * emission_prob

            gamma[i] /= gamma[i].sum() + 1e-10

        return gamma

    def _m_step(self, observations: np.ndarray, gamma: np.ndarray):
        n_obs = len(observations)

        self.initial_probs = gamma[0].copy()
        self.initial_probs /= self.initial_probs.sum() + 1e-10

        xi = np.zeros((self.n_states, self.n_states))
        for i in range(n_obs - 1):
            xi += np.outer(gamma[i], gamma[i + 1])

        self.transition_matrix = xi / (xi.sum(axis=1, keepdims=True) + 1e-10)

        for s in range(self.n_states):
            weight_sum = float(gamma[:, s].sum())
            if weight_sum > 1:
                weights = gamma[:, s] / (weight_sum + 1e-10)
                # 【修复】兼容 sklearn >= 1.9：GMM.fit() 不再接受 sample_weight 参数
                try:
                    if _gmm_fit_supports_sample_weight():
                        self.emission_models[s].fit(observations, sample_weight=weights)
                    else:
                        # 自动降级：加权自助采样 -> fit
                        _weighted_bootstrap_fit(self.emission_models[s], observations, weights)
                except Exception as e:
                    logger.warning(f"[HMM._m_step] 状态 {s} 发射模型加权拟合失败: {e}")
                    # 最终兜底：均匀数据 fit
                    try:
                        self.emission_models[s].fit(observations)
                    except Exception as e2:
                        logger.warning(f"[HMM._m_step] 状态 {s} 兜底拟合仍失败: {e2}")
            else:
                # 权重不足时降级拟合：用全量数据均匀权重，避免静默跳过 fit 导致 GMM 未更新。
                try:
                    self.emission_models[s].fit(observations)
                except Exception as e:
                    logger.warning(f"[HMM._m_step] 状态 {s} 权重不足降级拟合失败: {e}")

    def _compute_log_likelihood(self, observations: np.ndarray, gamma: np.ndarray) -> float:
        ll = 0.0
        for i in range(len(observations)):
            state_prob = gamma[i].sum() / len(observations)
            ll += np.log(state_prob + 1e-10)
        return ll

    def predict_proba(self, last_observations: np.ndarray) -> np.ndarray:
        if not self.fitted or not self.emission_models:
            return np.ones(10) / 10

        last_observations = np.asarray(last_observations).reshape(-1, 1)
        if len(last_observations) == 0:
            last_observations = np.array([[0]])

        alpha = self.initial_probs.copy()

        for obs in last_observations[-3:]:
            new_alpha = np.zeros(self.n_states)
            for s in range(self.n_states):
                try:
                    emission = np.exp(self.emission_models[s].score_samples(obs.reshape(1, -1))[0]) \
                              if self.emission_models else 0.1
                except Exception as e:
                    logger.warning(f"[HMM.predict_proba] 前向计算状态 {s} 发射概率失败: {e}")
                    emission = 0.1

                new_alpha[s] = emission * np.sum(
                    alpha.reshape(-1, 1) * self.transition_matrix[:, s]
                )

            alpha = new_alpha / (new_alpha.sum() + 1e-10)

        emission_probs = np.zeros(10)
        for s in range(self.n_states):
            for d in range(10):
                try:
                    emission = np.exp(
                        self.emission_models[s].score_samples(np.array([[d]]))[0]
                    ) if self.emission_models else 0.1
                except Exception as e:
                    logger.warning(f"[HMM.predict_proba] 数字 {d} 状态 {s} 发射概率失败: {e}")
                    emission = 0.1
                emission_probs[d] += alpha[s] * emission

        return emission_probs / (emission_probs.sum() + 1e-10)

    def get_state_sequence_proba(self, sequence: np.ndarray) -> float:
        if not self.fitted:
            return 0.0

        sequence = np.asarray(sequence).reshape(-1, 1)
        prob = self.initial_probs[0] if len(sequence) > 0 else 1.0

        for i, obs in enumerate(sequence):
            state_probs = np.zeros(self.n_states)
            for s in range(self.n_states):
                try:
                    state_probs[s] = np.exp(
                        self.emission_models[s].score_samples(obs.reshape(1, -1))[0]
                    ) if self.emission_models else 0.1
                except Exception as e:
                    logger.warning(f"[HMM.get_state_sequence_proba] 步骤 {i} 状态 {s} 发射概率失败: {e}")
                    state_probs[s] = 0.1

            if i > 0:
                prev_probs = state_probs.copy()
                state_probs = self.transition_matrix.T.dot(prev_probs)

            prob *= np.sum(state_probs) / self.n_states

        return prob

    def score(self, observations: np.ndarray) -> float:
        """计算模型对观测数据的对数似然值
        
        Args:
            observations: 观测数据
            
        Returns:
            对数似然值
        """
        observations = np.asarray(observations).reshape(-1, 1)
        if not self.fitted:
            return float('-inf')
        
        try:
            # 使用前向算法计算对数似然
            gamma = self._e_step(observations)
            return self._compute_log_likelihood(observations, gamma)
        except Exception as e:
            logger.warning(f"[HMM.score] 对数似然计算失败: {e}")
            return float('-inf')

    def diagnostics(self) -> Dict:
        """返回模型诊断指标摘要"""
        return {
            'n_states': self.n_states,
            'n_mixtures': self.n_mixtures,
            'fitted': self.fitted,
            'log_likelihood': self.log_likelihood,
            'bic': self.bic_value,
            'aic': self.aic_value,
            'converged': self.converged,
            'n_iterations': self.n_iterations,
            'auto_selected': self._n_states_input in ('auto', None),
            'criterion_used': self._criterion,
            'selection_history': self._selection_history
        }


class MultivariateCopula:
    """
    增强型多元Copula模型 - 支持多种Copula类型和自动选择

    支持的Copula类型:
    - gaussian: Gaussian Copula (对称尾部依赖)
    - t: Student-t Copula (厚尾, 对称尾部依赖)
    - clayton: Clayton Copula (强下尾依赖)
    - gumbel: Gumbel Copula (强上尾依赖)

    特性:
    - 自动Copula类型选择 (AIC/BIC准则)
    - 数值稳定性优化 (正则化, 边界处理)
    - 尾部依赖系数计算和评估
    """

    VALID_COPULA_TYPES = ['gaussian', 't', 'clayton', 'gumbel']

    def __init__(self, copula_type: str = 'gaussian',
                 regularization: float = 1e-6,
                 auto_select: bool = False,
                 model_config: Optional[ModelConfig] = None):
        _mc = model_config or get_model_config()
        copula_cfg = _mc.copula_config()

        self.copula_type = (copula_type.lower() if copula_type != 'gaussian'
                            else copula_cfg.get('type', 'gaussian')).lower()
        if self.copula_type not in self.VALID_COPULA_TYPES:
            self.copula_type = 'gaussian'
        reg_value = copula_cfg.get('regularization', 1e-6)
        try:
            self.regularization = float(regularization if regularization != 1e-6 else reg_value)
        except (TypeError, ValueError):
            self.regularization = 1e-6
        self.auto_select = auto_select if auto_select is not False else copula_cfg.get('auto_select', False)

        self.correlation_matrix: Optional[np.ndarray] = None
        self.marginals: Dict[int, Dict] = {}
        self.fitted = False
        self.n_positions = 5

        self._df: Optional[float] = None
        self._theta: Optional[float] = None
        self._copula_params: Dict = {}

        self.tail_dependence: Dict[str, float] = {}
        self.selection_info: Dict = {}

    def _compute_kendall_tau(self, data: np.ndarray) -> np.ndarray:
        """计算Kendall's tau相关矩阵"""
        n_vars = data.shape[1]
        kendall_tau = np.eye(n_vars)

        for i in range(n_vars):
            for j in range(i + 1, n_vars):
                tau, _ = stats.kendalltau(data[:, i], data[:, j])
                if not np.isnan(tau):
                    kendall_tau[i, j] = tau
                    kendall_tau[j, i] = tau

        return kendall_tau

    def _regularize_matrix(self, matrix: np.ndarray) -> np.ndarray:
        """
        正则化相关矩阵确保正定性

        添加对角线扰动并使用特征值分解修正
        """
        reg_matrix = matrix.copy()
        np.fill_diagonal(reg_matrix, 1.0 + self.regularization)

        try:
            eigenvalues, eigenvectors = np.linalg.eigh(reg_matrix)
            eigenvalues = np.maximum(eigenvalues, self.regularization)
            reg_matrix = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T

            reg_matrix = (reg_matrix + reg_matrix.T) / 2
        except Exception as e:
            logger.warning(f"[Copula] 矩阵正则化失败: {e}, 使用单位矩阵")
            n = len(matrix)
            reg_matrix = np.eye(n) * 0.1

        return np.clip(reg_matrix, -0.9999, 0.9999)

    def _fit_gaussian_copula(self, data: np.ndarray, kendall_tau: np.ndarray):
        """拟合Gaussian Copula"""
        rho = np.sin(np.pi / 2 * kendall_tau)
        self.correlation_matrix = self._regularize_matrix(rho)
        self._copula_params['rho'] = self.correlation_matrix.copy()

    def _fit_t_copula(self, data: np.ndarray, kendall_tau: np.ndarray):
        """拟合Student-t Copula (厚尾分布)"""
        from scipy.optimize import minimize_scalar

        rho = np.sin(np.pi / 2 * kendall_tau)
        self.correlation_matrix = self._regularize_matrix(rho)

        def neg_log_likelihood(df):
            if df <= 2:
                return 1e10
            try:
                u = np.zeros_like(data)
                for i in range(data.shape[1]):
                    u[:, i] = stats.rankdata(data[:, i]) / (len(data) + 1)

                z = stats.norm.ppf(np.clip(u, 1e-6, 1-1e-6))
                n, p = z.shape

                log_det = np.log(np.linalg.det(self.correlation_matrix) + 1e-10)
                inv_corr = np.linalg.inv(self.correlation_matrix + self.regularization * np.eye(p))

                mahal = np.sum(z @ inv_corr * z, axis=1)

                ll = (np.math.lgamma((df + p) / 2) - np.math.lgamma(df / 2)
                      - (p / 2) * np.log(df * np.pi) - 0.5 * log_det
                      - ((df + p) / 2) * np.log(1 + mahal / df))

                return -np.sum(ll)
            except:
                return 1e10

        result = minimize_scalar(neg_log_likelihood, bounds=(2.1, 50), method='bounded')
        self._df = max(2.1, result.x)
        self._copula_params['df'] = self._df
        self._copula_params['rho'] = self.correlation_matrix.copy()

    def _fit_clayton_copula(self, data: np.ndarray, kendall_tau: np.ndarray):
        """拟合Clayton Copula (强下尾依赖)"""
        from scipy.optimize import minimize_scalar

        mean_tau = np.mean(kendall_tau[kendall_tau != 1.0]) if np.any(kendall_tau != 1.0) else 0.0

        def neg_log_likelihood(theta):
            if theta <= 0:
                return 1e10
            try:
                u = np.zeros_like(data)
                for i in range(data.shape[1]):
                    u[:, i] = stats.rankdata(data[:, i]) / (len(data) + 1)

                u = np.clip(u, 1e-10, 1-1e-10)
                ll = 0.0

                for idx in range(len(u)):
                    u_sum = np.sum(u[idx] ** (-theta))
                    log_c = (-(theta + 1) * np.sum(np.log(u[idx]))
                             - (theta + 1) * np.log(u_sum)
                             - (len(u[idx]) - 1) * np.log(theta))
                    ll += log_c

                return -ll
            except:
                return 1e10

        init_theta = max(0.1, 2 * mean_tau / (1 - mean_tau)) if abs(mean_tau) < 1 else 1.0
        result = minimize_scalar(neg_log_likelihood,
                                bounds=(0.01, 20),
                                method='bounded')

        self._theta = max(0.01, result.x)
        self._copula_params['theta'] = self._theta

        pseudo_rho = np.zeros_like(kendall_tau)
        for i in range(len(kendall_tau)):
            for j in range(len(kendall_tau)):
                if i != j and kendall_tau[i, j] != 1.0:
                    tau_ij = kendall_tau[i, j]
                    theta_ij = max(0.01, 2 * abs(tau_ij) / (1 - abs(tau_ij)))
                    pseudo_rho[i, j] = theta_ij / (theta_ij + 2) * np.sign(tau_ij)

        self.correlation_matrix = self._regularize_matrix(pseudo_rho)

    def _fit_gumbel_copula(self, data: np.ndarray, kendall_tau: np.ndarray):
        """拟合Gumbel Copula (强上尾依赖)"""
        from scipy.optimize import minimize_scalar

        mean_tau = np.mean(kendall_tau[kendall_tau != 1.0]) if np.any(kendall_tau != 1.0) else 0.0

        def neg_log_likelihood(theta):
            if theta < 1:
                return 1e10
            try:
                u = np.zeros_like(data)
                for i in range(data.shape[1]):
                    u[:, i] = stats.rankdata(data[:, i]) / (len(data) + 1)

                u = np.clip(u, 1e-10, 1-1e-10)
                ll = 0.0

                for idx in range(len(u)):
                    log_u = np.log(u[idx])
                    sum_log_u_neg = np.sum((-log_u) ** theta)
                    c_val = sum_log_u_neg ** (1/theta)

                    log_c = (-c_val + (1/theta - 1) * np.log(sum_log_u_neg)
                             - (len(u[idx]) - 1) * np.log(theta)
                             - np.sum(log_u))
                    ll += log_c

                return -ll
            except:
                return 1e10

        init_theta = max(1.01, 1 / (1 - abs(mean_tau))) if abs(mean_tau) < 0.99 else 2.0
        result = minimize_scalar(neg_log_likelihood,
                                bounds=(1.01, 15),
                                method='bounded')

        self._theta = max(1.01, result.x)
        self._copula_params['theta'] = self._theta

        pseudo_rho = np.zeros_like(kendall_tau)
        for i in range(len(kendall_tau)):
            for j in range(len(kendall_tau)):
                if i != j and kendall_tau[i, j] != 1.0:
                    tau_ij = kendall_tau[i, j]
                    theta_ij = max(1.01, 1 / (1 - abs(tau_ij)))
                    pseudo_rho[i, j] = (theta_ij - 1) / theta_ij * np.sign(tau_ij)

        self.correlation_matrix = self._regularize_matrix(pseudo_rho)

    def fit(self, data: np.ndarray) -> "MultivariateCopula":
        """
        拟合Copula模型到数据

        Args:
            data: 形状为 (n_samples, n_positions) 的数据矩阵
        """
        data = np.asarray(data)
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)

        n_samples, self.n_positions = data.shape

        for i in range(self.n_positions):
            margin_data = data[:, i]
            std_val = float(np.std(margin_data))
            self.marginals[i] = {
                'mean': float(np.mean(margin_data)),
                'std': max(std_val, 1e-8),
                'skewness': float(stats.skew(margin_data)),
                'kurtosis': float(stats.kurtosis(margin_data)),
                'min': float(np.min(margin_data)),
                'max': float(np.max(margin_data))
            }

        kendall_tau = self._compute_kendall_tau(data)

        if self.copula_type == 'auto' or self.auto_select:
            return self.select_best_copula(data)

        fit_methods = {
            'gaussian': self._fit_gaussian_copula,
            't': self._fit_t_copula,
            'clayton': self._fit_clayton_copula,
            'gumbel': self._fit_gumbel_copula
        }

        if self.copula_type in fit_methods:
            fit_methods[self.copula_type](data, kendall_tau)

        self.fitted = True
        self._compute_tail_dependence()

        logger.info(f"[Copula] {self.copula_type} copula拟合完成, "
                   f"{self.n_positions}维, {n_samples}样本")
        return self

    def select_best_copula(self, data: np.ndarray) -> "MultivariateCopula":
        """
        自动选择最优Copula类型

        使用AIC/BIC准则评估每种Copula类型的拟合质量

        Args:
            data: 训练数据

        Returns:
            最优Copula实例
        """
        data = np.asarray(data)
        results = []

        for copula_type in self.VALID_COPULA_TYPES:
            try:
                temp_copula = MultivariateCopula(
                    copula_type=copula_type,
                    regularization=self.regularization
                )
                temp_copula.fit(data)

                if temp_copula.fitted:
                    aic, bic = self._compute_criteria(temp_copula, data)
                    results.append({
                        'type': copula_type,
                        'aic': aic,
                        'bic': bic,
                        'fitted': True,
                        'params': temp_copula._copula_params.copy()
                    })
                    logger.info(f"[Copula选择] {copula_type}: AIC={aic:.2f}, BIC={bic:.2f}")
            except Exception as e:
                logger.warning(f"[Copula选择] {copula_type} 拟合失败: {e}")
                continue

        if not results:
            logger.warning("[Copula选择] 所有Copula类型均失败，使用Gaussian作为默认")
            self._fit_gaussian_copula(data, self._compute_kendall_tau(data))
            self.fitted = True
            self.selection_info = {'selected_type': 'gaussian', 'reason': 'fallback'}
            return self

        results.sort(key=lambda x: x['bic'])
        best = results[0]

        self.copula_type = best['type']
        fit_method = {
            'gaussian': self._fit_gaussian_copula,
            't': self._fit_t_copula,
            'clayton': self._fit_clayton_copula,
            'gumbel': self._fit_gumbel_copula
        }[best['type']]
        fit_method(data, self._compute_kendall_tau(data))
        self.fitted = True

        self.selection_info = {
            'selected_type': best['type'],
            'selection_reason': f"最低BIC={best['bic']:.2f}",
            'all_candidates': results,
            'aic_ranking': sorted(results, key=lambda x: x['aic']),
            'bic_ranking': results
        }

        self._compute_tail_dependence()

        logger.info(f"[Copula选择] 最优类型: {best['type']} (BIC={best['bic']:.2f})")
        return self

    def _compute_criteria(self, copula: "MultivariateCopula",
                          data: np.ndarray) -> Tuple[float, float]:
        """计算AIC和BIC准则值"""
        try:
            u = np.zeros_like(data)
            for i in range(data.shape[1]):
                u[:, i] = stats.rankdata(data[:, i]) / (len(data) + 1)
            u = np.clip(u, 1e-10, 1-1e-10)

            log_likelihood = self._compute_log_likelihood(copula, u)
            n_samples = len(data)

            if copula.copula_type == 'gaussian':
                n_params = self.n_positions * (self.n_positions - 1) / 2
            elif copula.copula_type == 't':
                n_params = self.n_positions * (self.n_positions - 1) / 2 + 1
            elif copula.copula_type in ['clayton', 'gumbel']:
                n_params = 1
            else:
                n_params = self.n_positions

            aic = -2 * log_likelihood + 2 * n_params
            bic = -2 * log_likelihood + n_params * np.log(n_samples)

            return aic, bic
        except:
            return float('inf'), float('inf')

    def _compute_log_likelihood(self, copula: "MultivariateCopula",
                                 u: np.ndarray) -> float:
        """计算给定均匀数据下的对数似然"""
        try:
            if copula.copula_type == 'gaussian':
                z = stats.norm.ppf(u)
                n, p = z.shape
                log_det = np.log(abs(np.linalg.det(copula.correlation_matrix)) + 1e-10)
                inv_corr = np.linalg.inv(copula.correlation_matrix +
                                        self.regularization * np.eye(p))
                mahal = np.sum(z @ inv_corr * z, axis=1)
                ll = -0.5 * (n * p * np.log(2 * np.pi) + n * log_det + np.sum(mahal))
                return ll

            elif copula.copula_type == 't':
                z = stats.norm.ppf(u)
                df = copula._df if copula._df else 5
                n, p = z.shape
                log_det = np.log(abs(np.linalg.det(copula.correlation_matrix)) + 1e-10)
                inv_corr = np.linalg.inv(copula.correlation_matrix +
                                        self.regularization * np.eye(p))
                mahal = np.sum(z @ inv_corr * z, axis=1)
                ll = np.sum(
                    np.math.lgamma((df + p) / 2) - np.math.lgamma(df / 2)
                    - (p / 2) * np.log(df * np.pi) - 0.5 * log_det
                    - ((df + p) / 2) * np.log(1 + mahal / df)
                )
                return ll

            elif copula.copula_type == 'clayton':
                theta = copula._theta if copula._theta else 1.0
                ll = 0.0
                for idx in range(len(u)):
                    u_sum = np.sum(u[idx] ** (-theta))
                    log_c = (-(theta + 1) * np.sum(np.log(u[idx]))
                             - (theta + 1) * np.log(u_sum)
                             - (len(u[idx]) - 1) * np.log(theta))
                    ll += log_c
                return ll

            elif copula.copula_type == 'gumbel':
                theta = copula._theta if copula._theta else 2.0
                ll = 0.0
                for idx in range(len(u)):
                    log_u = np.log(u[idx])
                    sum_log_u_neg = np.sum((-log_u) ** theta)
                    c_val = sum_log_u_neg ** (1/theta)
                    log_c = (-c_val + (1/theta - 1) * np.log(sum_log_u_neg)
                             - (len(u[idx]) - 1) * np.log(theta)
                             - np.sum(log_u))
                    ll += log_c
                return ll

            else:
                return -1e10
        except:
            return -1e10

    def _compute_tail_dependence(self):
        """
        计算尾部依赖系数

        下尾依赖 (Lower Tail Dependence): 当所有变量同时取极小值的趋势
        上尾依赖 (Upper Tail Dependence): 当所有变量同时取极大值的趋势
        """
        if not self.fitted:
            return

        if self.copula_type == 'gaussian':
            self.tail_dependence = {
                'lower': 0.0,
                'upper': 0.0,
                'description': 'Gaussian Copula无尾部依赖'
            }
        elif self.copula_type == 't':
            df = self._df if self._df else 5
            lambda_l = lambda_u = 2 * stats.t.sf(df * np.sqrt((df + 1) /
                                                (df + self.correlation_matrix[0, 1]**2 *
                                                 (df + 1) - self.correlation_matrix[0, 1]**2)), df=df)
            self.tail_dependence = {
                'lower': round(float(lambda_l), 4),
                'upper': round(float(lambda_u), 4),
                'degrees_of_freedom': round(float(df), 2),
                'description': f't-Copula具有对称尾部依赖 (λ={lambda_l:.4f})'
            }
        elif self.copula_type == 'clayton':
            theta = self._theta if self._theta else 1.0
            lambda_l = 2 ** (-1/theta)
            self.tail_dependence = {
                'lower': round(float(lambda_l), 4),
                'upper': 0.0,
                'theta': round(float(theta), 4),
                'description': f'Clayton Copula具有强下尾依赖 (λ_L={lambda_l:.4f})'
            }
        elif self.copula_type == 'gumbel':
            theta = self._theta if self._theta else 2.0
            lambda_u = 2 - 2 ** (1/theta)
            self.tail_dependence = {
                'lower': 0.0,
                'upper': round(float(lambda_u), 4),
                'theta': round(float(theta), 4),
                'description': f'Gumbel Copula具有强上尾依赖 (λ_U={lambda_u:.4f})'
            }
        else:
            self.tail_dependence = {
                'lower': 0.0,
                'upper': 0.0,
                'description': '未知Copula类型'
            }

    def get_tail_dependence_strength(self) -> str:
        """
        评估尾部依赖强度

        Returns:
            描述性字符串
        """
        if not self.tail_dependence:
            return "未计算"

        lower = self.tail_dependence.get('lower', 0)
        upper = self.tail_dependence.get('upper', 0)
        max_dep = max(lower, upper)

        if max_dep >= 0.7:
            return "极强"
        elif max_dep >= 0.5:
            return "强"
        elif max_dep >= 0.3:
            return "中等"
        elif max_dep >= 0.1:
            return "弱"
        else:
            return "极弱/无"

    def simulate(self, n_samples: int) -> np.ndarray:
        """
        从Copula模型生成模拟样本

        Args:
            n_samples: 要生成的样本数量

        Returns:
            形状为 (n_samples, n_positions) 的模拟数据
        """
        if not self.fitted:
            raise ValueError("Copula未拟合")

        try:
            if self.copula_type == 'gaussian':
                uniform_samples = self._simulate_gaussian(n_samples)
            elif self.copula_type == 't':
                uniform_samples = self._simulate_t(n_samples)
            elif self.copula_type == 'clayton':
                uniform_samples = self._simulate_clayton(n_samples)
            elif self.copula_type == 'gumbel':
                uniform_samples = self._simulate_gumbel(n_samples)
            else:
                uniform_samples = np.random.rand(n_samples, self.n_positions)

            uniform_samples = np.clip(uniform_samples, 1e-6, 1-1e-6)

            result = np.zeros((n_samples, self.n_positions))
            for i in range(self.n_positions):
                std = self.marginals[i].get('std', 1.0)
                mean = self.marginals[i].get('mean', 0.0)
                result[:, i] = stats.norm.ppf(uniform_samples[:, i]) * std + mean

            return result

        except Exception as e:
            logger.error(f"[Copula] 模拟失败: {e}")
            return np.random.randn(n_samples, self.n_positions)

    def _simulate_gaussian(self, n_samples: int) -> np.ndarray:
        """Gaussian Copula模拟"""
        z = np.random.multivariate_normal(
            mean=np.zeros(self.n_positions),
            cov=self.correlation_matrix,
            size=n_samples
        )
        return stats.norm.cdf(z)

    def _simulate_t(self, n_samples: int) -> np.ndarray:
        """Student-t Copula模拟"""
        df = self._df if self._df else 5
        z = np.random.multivariate_normal(
            mean=np.zeros(self.n_positions),
            cov=self.correlation_matrix,
            size=n_samples
        )
        chi2 = np.random.chisquare(df, size=n_samples)
        t_samples = z * np.sqrt(df / chi2).reshape(-1, 1)
        return stats.t.cdf(t_samples, df=df)

    def _simulate_clayton(self, n_samples: int) -> np.ndarray:
        """Clayton Copula模拟"""
        theta = self._theta if self._theta else 1.0
        u = np.random.rand(n_samples, self.n_positions)
        v = np.random.gamma(shape=1/theta, scale=1, size=(n_samples, 1))
        clayton_sim = (u ** (-theta/v) - 1 + 1) ** (-1/theta)
        return np.clip(clayton_sim, 1e-6, 1-1e-6)

    def _simulate_gumbel(self, n_samples: int) -> np.ndarray:
        """Gumbel Copula模拟"""
        theta = self._theta if self._theta else 2.0
        u = np.random.rand(n_samples, self.n_positions)
        v = np.random.gamma(shape=1, scale=1/theta, size=(n_samples, 1))
        gumbel_sim = np.exp(-(-np.log(u) / v.reshape(-1, 1)) ** (1/theta))
        return np.clip(gumbel_sim, 1e-6, 1-1e-6)

    def get_joint_probability(self, values: np.ndarray) -> float:
        """计算联合概率密度"""
        if not self.fitted:
            return 1.0

        values = np.asarray(values).reshape(-1, self.n_positions)

        try:
            u = np.zeros(self.n_positions)
            for i in range(self.n_positions):
                normalized = (values[0, i] - self.marginals[i]['mean']) / \
                            (self.marginals[i]['std'] + 1e-10)
                u[i] = stats.norm.cdf(normalized)

            u = np.clip(u, 1e-6, 1-1e-6)
            density = self._compute_copula_density(u)

            if np.isnan(density) or density <= 0:
                return 0.1

            return float(np.clip(density, 1e-10, 1e10))
        except Exception:
            return 0.1

    def _compute_copula_density(self, u: np.ndarray) -> float:
        """计算Copula密度函数值"""
        try:
            if self.copula_type == 'gaussian':
                z = stats.norm.ppf(u)
                cov = self.correlation_matrix + self.regularization * np.eye(self.n_positions)
                det = np.linalg.det(cov)
                inv_cov = np.linalg.inv(cov)
                mahal = z @ inv_cov @ z
                density = (1 / np.sqrt((2 * np.pi) ** self.n_positions * abs(det) + 1e-10)) * \
                         np.exp(-0.5 * mahal)
                return density

            elif self.copula_type == 't':
                z = stats.norm.ppf(u)
                df = self._df if self._df else 5
                cov = self.correlation_matrix + self.regularization * np.eye(self.n_positions)
                det = np.linalg.det(cov)
                inv_cov = np.linalg.inv(cov)
                mahal = z @ inv_cov @ z
                p = self.n_positions
                density = (np.math.gamma((df + p) / 2) / (np.math.gamma(df / 2) *
                           (df * np.pi) ** (p/2) * np.sqrt(abs(det) + 1e-10))) * \
                         (1 + mahal / df) ** (-(df + p) / 2)
                return density

            elif self.copula_type == 'clayton':
                theta = self._theta if self._theta else 1.0
                u_prod = np.prod(u)
                u_theta_sum = np.sum(u ** (-theta))
                density = (theta + 1) * (u_prod ** -(theta + 1)) * \
                         (u_theta_sum - 1) ** (-(2*theta + 1)/theta)
                return density

            elif self.copula_type == 'gumbel':
                theta = self._theta if self._theta else 2.0
                log_u = np.log(u)
                sum_log_u_neg = np.sum((-log_u) ** theta)
                c = sum_log_u_neg ** (1/theta)
                density = (c ** (theta - self.n_positions + 1) *
                         np.prod(u ** (-1)) *
                         np.prod((-log_u) ** (theta - 1)) /
                         (sum_log_u_neg ** ((self.n_positions - 1) / theta)))
                return density

            else:
                return 0.1
        except:
            return 0.1

    def get_conditional_probability(self, target_position: int,
                                   target_value: int,
                                   conditioning_values: Dict[int, int]) -> float:
        """计算条件概率"""
        if not self.fitted:
            return 0.1

        margin_probs = np.zeros(10)
        for d in range(10):
            test_values = np.zeros(self.n_positions)
            for pos, val in conditioning_values.items():
                if 0 <= pos < self.n_positions:
                    test_values[pos] = val
            test_values[target_position] = d

            prob = self.get_joint_probability(test_values.reshape(1, -1))
            margin_probs[d] = prob

        return float(margin_probs[target_value] / (margin_probs.sum() + 1e-10))

    def diagnostics(self) -> Dict:
        """返回模型诊断信息"""
        return {
            'copula_type': self.copula_type,
            'n_dimensions': self.n_positions,
            'fitted': self.fitted,
            'parameters': self._copula_params,
            'tail_dependence': self.tail_dependence,
            'tail_strength': self.get_tail_dependence_strength(),
            'selection_info': self.selection_info,
            'correlation_matrix_shape': self.correlation_matrix.shape if self.correlation_matrix is not None else None,
            'regularization_used': self.regularization
        }


class BayesianStructuralTimeSeries:
    """
    增强型贝叶斯结构时序模型 (BSTS)

    改进特性:
    - 自适应趋势窗口选择 (基于数据长度和波动性)
    - 自动季节性组件检测 (基于自相关分析)
    - 鲁棒异常值处理 (MAD/IQR方法 + 贝叶斯降权)
    - 贝叶斯预测区间估计 (后验分布采样)
    - 模型诊断与验证
    """

    CANDIDATE_WINDOWS = [10, 15, 20, 30, 50]

    def __init__(self, trend_window: int = 20,
                 seasonality_period: Optional[int] = None,
                 outlier_threshold: float = 2.5,
                 n_posterior_samples: int = 1000,
                 confidence_level: float = 0.95,
                 model_config: Optional[ModelConfig] = None):
        _mc = model_config or get_model_config()
        bsts_cfg = _mc.bsts_config()

        self.trend_window = trend_window if trend_window != 20 else bsts_cfg.get('trend_window', 20)
        self.seasonality_period_input = seasonality_period
        self.outlier_threshold = outlier_threshold if outlier_threshold != 2.5 else bsts_cfg.get('outlier_threshold', 2.5)
        self.n_posterior_samples = n_posterior_samples if n_posterior_samples != 1000 else bsts_cfg.get('n_posterior_samples', 1000)
        self.confidence_level = confidence_level if confidence_level != 0.95 else bsts_cfg.get('confidence_level', 0.95)

        self.trend_coef: Optional[np.ndarray] = None
        self.trend_coef_cov: Optional[np.ndarray] = None
        self.seasonal_coef: Optional[np.ndarray] = None
        self.detected_seasonality_period: Optional[int] = None
        self.residual_std: float = 1.0
        self.fitted = False

        self._outlier_mask: Optional[np.ndarray] = None
        self._outlier_weights: Optional[np.ndarray] = None
        self._optimal_window: Optional[int] = None
        self._window_selection_scores: List[Dict] = []
        self._seasonality_detected: bool = False
        self._seasonality_strength: float = 0.0
        self._n_outliers: int = 0

        self._posterior_trend_samples: Optional[np.ndarray] = None
        self._posterior_residual_samples: Optional[np.ndarray] = None

        self._training_data: Optional[np.ndarray] = None
        self._last_fit_n: int = 0
        self._fit_count: int = 0
        self._partial_fit_history: List[Dict] = []
        self._max_history_length: int = 500
        self._learning_rate: float = 0.3

    def select_optimal_window(self, data: np.ndarray) -> Dict:
        """
        基于BIC准则和预测误差自动选择最优趋势窗口大小

        策略 (双重验证):
        1. BIC信息准则: 对每个候选窗口拟合线性趋势，计算 BIC = -2*LL + k*ln(n)
        2. 时间序列交叉验证: 滚动窗口前向验证，计算一步预测MSE
        3. 综合得分: 加权组合BIC和预测误差，高波动数据更重视预测精度

        Args:
            data: 一维时序数据

        Returns:
            包含最优窗口和评分详情的字典
        """
        data = np.asarray(data).ravel()
        n = len(data)

        if n < 20:
            optimal = min(10, max(5, n // 2))
            logger.info(f"[BSTS] 数据量少(n={n}), 选择窗口={optimal}")
            self._optimal_window = optimal
            return {'optimal_window': optimal, 'scores': [], 'reason': 'insufficient_data'}

        scores = []
        data_std = np.std(data)
        data_cv = data_std / (np.abs(np.mean(data)) + 1e-10)
        x_full = np.arange(n, dtype=float)

        n_folds = min(5, max(2, n // 30))
        fold_size = n // n_folds

        for window in self.CANDIDATE_WINDOWS:
            if window >= n - fold_size:
                continue

            try:
                train_end = n - fold_size
                train_data = data[:train_end]
                train_x = x_full[:train_end]
                test_data = data[train_end:]
                test_x = x_full[train_end:]

                use_w = window if window < len(train_data) else len(train_data)
                recent_train = train_data[-use_w:]
                recent_train_x = train_x[-use_w:]

                coeffs = np.polyfit(recent_train_x, recent_train, 1)
                n_params = 2
                fitted_train = np.polyval(coeffs, recent_train_x)
                residuals = recent_train - fitted_train
                residual_var = np.var(residuals)
                ss_res = np.sum(residuals ** 2)
                ll = -use_w / 2 * np.log(2 * np.pi * residual_var) - use_w / 2
                bic_score = -2 * ll + n_params * np.log(use_w)
                aic_score = -2 * ll + 2 * n_params

                predictions = np.polyval(coeffs, test_x)
                cv_mse = np.mean((test_data - predictions) ** 2)
                cv_mae = np.mean(np.abs(test_data - predictions))

                full_coeffs = np.polyfit(x_full, data, 1)
                full_fitted = np.polyval(full_coeffs, x_full)
                full_mse = np.mean((data - full_fitted) ** 2)
                improvement_ratio = full_mse / (cv_mse + 1e-10)

                volatility_weight = min(1.0, data_cv * 2)
                combined_score = (volatility_weight * cv_mse +
                                  (1 - volatility_weight) * bic_score / n)

                scores.append({
                    'window': window,
                    'bic': float(bic_score),
                    'aic': float(aic_score),
                    'cv_mse': float(cv_mse),
                    'cv_mae': float(cv_mae),
                    'combined_score': float(combined_score),
                    'improvement_ratio': float(improvement_ratio),
                    'residual_variance': float(residual_var),
                    'log_likelihood': float(ll)
                })

            except Exception as e:
                logger.warning(f"[BSTS] 窗口={window} 评估失败: {e}")
                continue

        if not scores:
            optimal = 20
            self._optimal_window = optimal
            return {'optimal_window': optimal, 'scores': [], 'reason': 'all_failed'}

        scores.sort(key=lambda s: s['combined_score'])
        best = scores[0]
        optimal = best['window']

        self._optimal_window = optimal
        self._window_selection_scores = scores

        logger.info(f"[BSTS] 最优窗口选择: {optimal} (候选数={len(scores)}, "
                   f"综合得分={best['combined_score']:.4f}, BIC={best['bic']:.2f}, "
                   f"CV-MSE={best['cv_mse']:.4f}, CV={data_cv:.4f})")

        return {
            'optimal_window': optimal,
            'best_score': best['combined_score'],
            'bic': best['bic'],
            'aic': best.get('aic', 0),
            'cv_mse': best['cv_mse'],
            'cv_mae': best.get('cv_mae', 0),
            'improvement_ratio': best['improvement_ratio'],
            'all_scores': scores,
            'data_cv': float(data_cv),
            'n_candidates_tested': len(scores),
            'n_cv_folds': n_folds,
            'reason': 'bic_cv_combined'
        }

    def _detect_seasonality_fft(self, data: np.ndarray,
                                 max_period: Optional[int] = None) -> Tuple[bool, int, float]:
        """
        使用FFT频谱分析检测数据中的季节性模式

        方法:
        - 对去趋势数据进行快速傅里叶变换(FFT)
        - 计算功率谱密度(PSD)
        - 寻找PSD中的显著峰值
        - 使用信噪比(SNR)阈值判断季节性显著性

        Args:
            data: 去趋势后的时序数据
            max_period: 最大待检测周期

        Returns:
            (是否检测到季节性, 季节性周期, 强度)
        """
        data = np.asarray(data).ravel()
        n = len(data)

        if n < 20:
            return False, self.seasonality_period_input or 10, 0.0

        if max_period is None:
            max_period = min(n // 2, 30)

        if max_period < 3:
            return False, self.seasonality_period_input or 10, 0.0

        data_centered = data - np.mean(data)
        data_centered = data_centered * np.hanning(len(data_centered))

        fft_vals = np.fft.rfft(data_centered)
        psd = np.abs(fft_vals) ** 2
        freqs = np.fft.rfftfreq(n)

        valid_period_range = (2, max_period)
        valid_mask = (freqs > 1 / valid_period_range[1]) & (freqs < 1 / valid_period_range[0])
        if not np.any(valid_mask):
            return False, self.seasonality_period_input or 10, 0.0

        valid_psd = np.where(valid_mask, psd, 0)
        noise_floor = np.median(valid_psd[valid_psd > 0]) if np.any(valid_psd > 0) else 1.0
        snr = valid_psd / (noise_floor + 1e-10)

        peak_indices = []
        for i in range(1, len(snr) - 1):
            if not valid_mask[i]:
                continue
            if snr[i] > snr[i-1] and snr[i] > snr[i+1] and snr[i] > 3.0:
                period_candidate = round(1 / freqs[i]) if freqs[i] > 0 else n
                if valid_period_range[0] <= period_candidate <= valid_period_range[1]:
                    peak_indices.append((period_candidate, snr[i], i))

        if not peak_indices:
            return False, self.seasonality_period_input or 10, 0.0

        peak_indices.sort(key=lambda x: x[1], reverse=True)
        best_period, best_snr, best_idx = peak_indices[0]

        total_signal_power = np.sum(valid_psd)
        peak_power = psd[best_idx]
        strength = float(peak_power / (total_signal_power + 1e-10)) * len(psd)

        detected = best_snr > 5.0 and strength > 0.05

        logger.info(f"[BSTS-FFT] 季节性检测结果: {'检测到' if detected else '未检测到'}, "
                   f"周期={best_period}, SNR={best_snr:.2f}, 强度={strength:.4f}")

        return detected, best_period if detected else (self.seasonality_period_input or 10), strength

    def _detect_seasonality(self, data: np.ndarray,
                            max_period: Optional[int] = None) -> Tuple[bool, int, float]:
        """
        联合ACF和FFT的季节性检测（融合两种方法的结果）

        方法组合:
        1. FFT频谱分析: 检测周期性信号的频域特征，适合强周期信号
        2. ACF自相关分析: 检测时域中的滞后相关性，适合弱周期信号
        3. 融合策略: 任一方法检测到显著季节性即采用，取较强结果

        Args:
            data: 去趋势后的数据
            max_period: 最大待检测周期

        Returns:
            (是否检测到季节性, 季节性周期, 强度)
        """
        fft_detected, fft_period, fft_strength = self._detect_seasonality_fft(data, max_period)
        acf_detected, acf_period, acf_strength = self._detect_seasonality_acf(data, max_period)

        combined_detected = fft_detected or acf_detected

        if combined_detected:
            if fft_detected and acf_detected:
                if fft_strength >= acf_strength:
                    best_period, best_strength = fft_period, fft_strength
                    method = 'fft_dominant'
                else:
                    best_period, best_strength = acf_period, acf_strength
                    method = 'acf_dominant'
            elif fft_detected:
                best_period, best_strength = fft_period, fft_strength
                method = 'fft_only'
            else:
                best_period, best_strength = acf_period, acf_strength
                method = 'acf_only'
        else:
            best_period = self.seasonality_period_input or 10
            best_strength = 0.0
            method = 'none'

        self._seasonality_detected = combined_detected
        self._seasonality_strength = best_strength
        self.detected_seasonality_period = best_period if combined_detected else None

        logger.info(f"[BSTS] 融合季节性检测: {'检测到' if combined_detected else '未检测到'}, "
                   f"周期={best_period}, 强度={best_strength:.4f}, 方法={method}")

        return combined_detected, best_period, best_strength

    def _detect_seasonality_acf(self, data: np.ndarray,
                                max_period: Optional[int] = None) -> Tuple[bool, int, float]:
        """
        使用自相关分析检测数据中的季节性模式

        方法:
        - 计算去趋势数据的自相关函数(ACF)
        - 寻找ACF的显著峰值
        - 使用Fisher's g检验评估季节性的统计显著性

        Args:
            data: 去趋势后的数据
            max_period: 最大待检测周期

        Returns:
            (是否检测到季节性, 季节性周期, 强度)
        """
        data = np.asarray(data).ravel()
        n = len(data)

        if n < 20 or max_period is None:
            max_period = min(n // 2, 30)

        if max_period < 3:
            return False, self.seasonality_period_input or 10, 0.0

        data_centered = data - np.mean(data)
        variance = np.var(data_centered)
        if variance < 1e-10:
            return False, self.seasonality_period_input or 10, 0.0

        acf = np.zeros(max_period)
        for lag in range(1, max_period + 1):
            if lag >= n:
                break
            acf[lag - 1] = np.sum(data_centered[:n - lag] * data_centered[lag:]) / ((n - lag) * variance)

        significant_peaks = []
        for period in range(2, max_period):
            if period >= len(acf):
                break
            acf_val = acf[period]
            if acf_val > 0.3:
                is_peak = True
                for neighbor in range(max(1, period - 2), min(len(acf), period + 3)):
                    if neighbor != period and neighbor < len(acf) and acf[neighbor] > acf_val:
                        is_peak = False
                        break
                if is_peak:
                    significant_peaks.append((period, acf_val))

        if not significant_peaks:
            return False, self.seasonality_period_input or 10, 0.0

        significant_peaks.sort(key=lambda x: x[1], reverse=True)
        best_period, best_acf = significant_peaks[0]

        n_permutations = 100
        count_extreme = 0
        shuffled = data_centered.copy()
        for _ in range(n_permutations):
            np.random.shuffle(shuffled)
            shuf_var = np.var(shuffled)
            if shuf_var < 1e-10:
                continue
            shuf_acf_max = 0
            for lag in range(best_period - 1, min(best_period + 2, max_period)):
                if lag >= n - 1:
                    continue
                val = abs(np.sum(shuffled[:n - lag - 1] * shuffled[lag + 1:]) /
                         ((n - lag - 1) * shuf_var))
                shuf_acf_max = max(shuf_acf_max, val)
            if shuf_acf_max >= best_acf:
                count_extreme += 1

        p_value = (count_extreme + 1) / (n_permutations + 1)
        detected = p_value < 0.05 and best_acf > 0.2
        strength = float(best_acf) if detected else 0.0

        seasonality_period = best_period if detected else (self.seasonality_period_input or 10)

        logger.info(f"[BSTS-ACF] 季节性检测结果: {'检测到' if detected else '未检测到'}, "
                   f"周期={best_period}, ACF={best_acf:.4f}, p值={p_value:.4f}, 强度={strength:.4f}")

        return detected, seasonality_period, strength

    def _identify_outliers(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        使用多策略鲁棒统计方法识别异常值并计算贝叶斯权重

        方法组合 (四重验证):
        1. MAD Modified Z-score: 基于中位数绝对偏差，对偏态/厚尾分布鲁棒
        2. IQR方法: 四分位距法，标准鲁棒异常检测
        3. 局部偏差检测: 滑动窗口比较局部均值偏离度
        4. 自适应阈值: 根据数据偏度和峰度动态调整判定门槛
        5. Huber-style降权: 对异常值使用平滑降权函数

        Args:
            data: 原始数据

        Returns:
            (异常值掩码, 权重数组)
        """
        data = np.asarray(data).ravel()
        n = len(data)
        outlier_mask = np.zeros(n, dtype=bool)
        weights = np.ones(n)

        if n < 10:
            self._outlier_mask = outlier_mask
            self._outlier_weights = weights
            return outlier_mask, weights

        median_val = np.median(data)
        mad = np.median(np.abs(data - median_val))
        q1, q3 = np.percentile(data, [25, 75])
        iqr = q3 - q1

        data_skewness = float(stats.skew(data))
        data_kurtosis = float(stats.kurtosis(data))
        is_heavy_tailed = data_kurtosis > 3 or abs(data_skewness) > 1.0

        adaptive_threshold = self.outlier_threshold
        if is_heavy_tailed:
            adaptive_threshold *= 1.3
        elif abs(data_skewness) < 0.3 and data_kurtosis < 0:
            adaptive_threshold *= 0.85

        mad_scaled = mad * 1.4826 if mad > 1e-10 else (iqr / 1.349 if iqr > 1e-10 else np.std(data))
        iqr_lower = q1 - adaptive_threshold * iqr
        iqr_upper = q3 + adaptive_threshold * iqr

        mad_z = np.abs(data - median_val) / (mad_scaled + 1e-10)

        global_outliers = (mad_z > adaptive_threshold) | (data < iqr_lower) | (data > iqr_upper)

        local_window = max(5, min(n // 10, 15))
        local_scores = np.zeros(n)
        for i in range(n):
            start = max(0, i - local_window)
            end = min(n, i + local_window + 1)
            local_data = data[start:end]
            if len(local_data) >= 3:
                local_median = np.median(local_data)
                local_mad = np.median(np.abs(local_data - local_median))
                local_scaled = local_mad * 1.4826 if local_mad > 1e-10 else np.std(local_data)
                local_scores[i] = abs(data[i] - local_median) / (local_scaled + 1e-10)

        local_threshold = adaptive_threshold * 1.2
        local_outliers = local_scores > local_threshold

        outlier_votes = global_outliers.astype(int) + local_outliers.astype(int)
        outlier_mask = outlier_votes >= 1

        for i in range(n):
            if outlier_mask[i]:
                combined_z = max(mad_z[i], local_scores[i])
                if combined_z <= adaptive_threshold * 1.5:
                    weight = np.exp(-0.5 * (combined_z ** 2) / (adaptive_threshold ** 2))
                elif combined_z <= adaptive_threshold * 2.5:
                    weight = np.exp(-0.5 * (combined_z ** 2) / ((adaptive_threshold * 1.5) ** 2))
                else:
                    weight = np.exp(-0.5 * (combined_z ** 2) / ((adaptive_threshold * 2.0) ** 2))
                weights[i] = max(weight, 0.02)

        self._outlier_mask = outlier_mask
        self._outlier_weights = weights
        self._n_outliers = int(np.sum(outlier_mask))

        logger.info(f"[BSTS] 异常值检测: {self._n_outliers}/{n} 个异常值 "
                   f"({100*self._n_outliers/n:.1f}%), MAD缩放={mad_scaled:.4f}, "
                   f"自适应阈值={adaptive_threshold:.2f}, "
                   f"偏度={data_skewness:.2f}, 峰度={data_kurtosis:.2f}")

        return outlier_mask, weights

    def _compute_bayesian_posterior(self, data: np.ndarray, x: np.ndarray,
                                     weights: Optional[np.ndarray] = None):
        """
        计算贝叶斯后验分布用于预测区间估计

        使用共轭先验(正态-逆Gamma)近似后验分布:
        - 趋势系数的后验: 多元正态分布
        - 残差方差的后验: 逆Gamma分布

        通过后验采样生成预测区间
        """
        n = len(data)
        w = weights if weights is not None else np.ones(n)

        X_design = np.vstack([x, np.ones(n)]).T
        W = np.diag(w)

        XtWX = X_design.T @ W @ X_design
        XtWy = X_design.T @ W @ data

        reg = 1e-6 * np.eye(2)
        posterior_cov = np.linalg.inv(XtWX + reg)
        posterior_mean = posterior_cov @ XtWy

        residuals = data - X_design @ posterior_mean
        weighted_ss = np.sum(w * residuals ** 2)
        effective_n = np.sum(w)

        prior_df = 2.0
        prior_scale = 1.0
        post_df = prior_df + effective_n / 2.0
        post_scale = (prior_scale * prior_df / 2.0 + weighted_ss / 2.0) / post_df

        rng = np.random.default_rng(42)
        trend_samples = np.zeros((self.n_posterior_samples, 2))
        residual_samples = np.zeros(self.n_posterior_samples)

        for i in range(self.n_posterior_samples):
            sampled_var = inv_gamma_sample(rng, post_df, post_scale)
            trend_samples[i] = rng.multivariate_normal(posterior_mean, sampled_var * posterior_cov)
            residual_samples[i] = rng.normal(0, np.sqrt(max(sampled_var, 1e-10)))

        self.trend_coef = posterior_mean
        self.trend_coef_cov = posterior_cov * post_scale * 2 / (post_df - 1)
        self.residual_std = float(np.sqrt(post_scale * 2 / (post_df - 1))) if post_df > 1 else 1.0

        self._posterior_trend_samples = trend_samples
        self._posterior_residual_samples = residual_samples

    def fit(self, observations: np.ndarray) -> "BayesianStructuralTimeSeries":
        """
        拟合BSTS模型到观测数据

        完整流程:
        1. 异常值检测与权重分配
        2. 最优窗口选择(如果使用自适应模式)
        3. 季节性检测
        4. 贝叶斯参数估计
        5. 后验采样
        """
        observations = np.asarray(observations).ravel()
        n = len(observations)

        if n < 10:
            self.trend_coef = np.array([0.0, float(np.mean(observations))])
            self.residual_std = max(float(np.std(observations)), 0.1)
            self.fitted = True
            logger.info(f"[BSTS] 数据量极少(n={n}), 使用简化模型")
            return self

        self._identify_outliers(observations)

        if self.trend_window == 0 or self.trend_window is None:
            self.select_optimal_window(observations)
            effective_window = self._optimal_window or 20
        else:
            effective_window = self.trend_window

        x = np.arange(n, dtype=float)

        if self.seasonality_period_input is None:
            use_seasonal, seasonality_period, _ = self._detect_seasonality(observations)
        else:
            use_seasonal = True
            seasonality_period = self.seasonality_period_input

        self.seasonality_period = seasonality_period

        fit_data = observations.copy()
        if effective_window < n and effective_window >= 5:
            fit_data = observations[-effective_window:]
            fit_x = x[-effective_window:].copy()
        else:
            fit_x = x.copy()

        self._compute_bayesian_posterior(fit_data, fit_x, self._outlier_weights[-len(fit_data):])

        detrended = observations - np.polyval(self.trend_coef, x)

        if use_seasonal and n >= seasonality_period:
            seasonal = np.zeros(seasonality_period)
            seasonal_weights = np.zeros(seasonality_period)
            for i in range(seasonality_period):
                indices = np.arange(i, n, seasonality_period)
                if len(indices) > 0:
                    w = self._outlier_weights[indices]
                    seasonal[i] = np.sum(w * detrended[indices]) / (np.sum(w) + 1e-10)
                    seasonal_weights[i] = np.sum(w)
            seasonal = seasonal - np.average(seasonal, weights=seasonal_weights + 1e-10)
            self.seasonal_coef = seasonal
            self.detected_seasonality_period = seasonality_period
        elif not use_seasonal:
            self.seasonal_coef = None
            self.detected_seasonality_period = None

        self.fitted = True
        self._training_data = observations.copy()
        self._last_fit_n = n
        self._fit_count += 1

        logger.info(f"[BSTS] 模型拟合完成: n={n}, 窗口={effective_window}, "
                   f"季节周期={seasonality_period if use_seasonal else '无'}, "
                   f"异常值={self._n_outliers}, 残差σ={self.residual_std:.4f}, "
                   f"fit_count={self._fit_count}")
        return self

    def _construct_model(self, x: np.ndarray) -> np.ndarray:
        """构建完整的趋势+季节性模型"""
        trend = np.polyval(self.trend_coef, x) if self.trend_coef is not None else np.zeros_like(x, dtype=float)
        seasonal = np.zeros_like(x, dtype=float)
        if self.seasonal_coef is not None:
            period = len(self.seasonal_coef)
            seasonal = self.seasonal_coef[np.mod(x.astype(int), period)]
        return trend + seasonal

    def predict(self, n_ahead: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """基础预测，返回概率分布和不确定性"""
        if not self.fitted:
            return np.ones(10) / 10, np.ones(10) / 10

        last_x = self._last_fit_n if hasattr(self, '_last_fit_n') else 0
        future_x = np.arange(last_x, last_x + n_ahead)

        predictions = np.zeros(10)
        uncertainty = np.ones(10) * self.residual_std

        if self.trend_coef is not None:
            recent_trend = self.trend_coef[0]
            for d in range(10):
                base_prob = 0.1
                trend_adjustment = recent_trend * 0.05 * (d - 4.5)
                predictions[d] = base_prob + trend_adjustment
        else:
            predictions = np.ones(10) / 10

        predictions = np.clip(predictions, 0.01, 0.5)
        predictions /= predictions.sum()

        return predictions, uncertainty

    def predict_with_intervals(self, n_ahead: int = 1) -> Dict:
        """
        带预测区间的贝叶斯预测（增强版）

        基于后验分布采样计算:
        - 均值预测 (趋势 + 季节性)
        - 标准差 (参数不确定性 + 过程噪声)
        - 置信区间 (默认95% CI)
        - 多置信水平区间 (68%, 90%, 95%)

        不确定性来源:
        1. 趋势系数后验不确定性
        2. 残差方差后验不确定性
        3. 预测步数递增的不确定性
        4. 季节性外推的不确定性

        Returns:
            包含预测均值、标准差、多置信区间和完整采样的字典
        """
        if not self.fitted or self._posterior_trend_samples is None:
            return {
                'mean': np.zeros(n_ahead),
                'std': np.ones(n_ahead),
                'lower_bound': np.zeros(n_ahead),
                'upper_bound': np.zeros(n_ahead),
                'prediction_probs': np.ones(10) / 10,
                'samples': None,
                'confidence_level': self.confidence_level
            }

        last_n = self._last_fit_n if hasattr(self, '_last_fit_n') else 100
        future_x = np.arange(last_n, last_n + n_ahead)

        alpha = 1 - self.confidence_level
        z_crit = stats.norm.ppf(1 - alpha / 2)

        all_predictions = np.zeros((self.n_posterior_samples, n_ahead))
        for i in range(self.n_posterior_samples):
            slope, intercept = self._posterior_trend_samples[i]
            trend_pred = slope * future_x + intercept

            seasonal_pred = np.zeros(n_ahead)
            if self.seasonal_coef is not None:
                period = len(self.seasonal_coef)
                seasonal_pred = self.seasonal_coef[np.mod(future_x.astype(int), period)]

            noise_std = self._posterior_residual_samples[i]
            step_uncertainty = noise_std * np.sqrt(np.arange(1, n_ahead + 1))

            season_noise = 0.0
            if self.seasonal_coef is not None and n_ahead > period:
                season_noise = noise_std * 0.3 * np.sqrt(np.arange(1, n_ahead + 1) / period)

            all_predictions[i] = trend_pred + seasonal_pred + step_uncertainty + season_noise

        mean_pred = np.mean(all_predictions, axis=0)
        std_pred = np.std(all_predictions, axis=0)

        lower_bound_95 = np.percentile(all_predictions, (alpha / 2) * 100, axis=0)
        upper_bound_95 = np.percentile(all_predictions, (1 - alpha / 2) * 100, axis=0)
        lower_bound_90 = np.percentile(all_predictions, 5, axis=0)
        upper_bound_90 = np.percentile(all_predictions, 95, axis=0)
        lower_bound_68 = np.percentile(all_predictions, 16, axis=0)
        upper_bound_68 = np.percentile(all_predictions, 84, axis=0)

        prediction_probs = np.zeros(10)
        if len(mean_pred) > 0:
            overall_trend = mean_pred[-1] - mean_pred[0] if n_ahead > 1 else mean_pred[0]
            uncertainty_scale = std_pred[-1] if len(std_pred) > 0 else 1.0
            for d in range(10):
                base_prob = 0.1
                trend_adj = overall_trend * 0.02 * (d - 4.5) / (uncertainty_scale + 0.1)
                prediction_probs[d] = base_prob + trend_adj
        prediction_probs = np.clip(prediction_probs, 0.01, 0.5)
        prediction_probs /= prediction_probs.sum()

        result = {
            'mean': mean_pred,
            'std': std_pred,
            'lower_bound': lower_bound_95,
            'upper_bound': upper_bound_95,
            'intervals': {
                '95%': (lower_bound_95, upper_bound_95),
                '90%': (lower_bound_90, upper_bound_90),
                '68%': (lower_bound_68, upper_bound_68),
            },
            'prediction_probs': prediction_probs,
            'posterior_samples': all_predictions,
            'confidence_level': self.confidence_level,
            'has_seasonality': self.seasonal_coef is not None
        }

        logger.info(f"[BSTS] 区间预测: 步数={n_ahead}, 均值={mean_pred[-1]:.4f}, "
                   f"σ={std_pred[-1]:.4f}, 95%CI=[{lower_bound_95[-1]:.4f}, {upper_bound_95[-1]:.4f}], "
                   f"季节性={'是' if self.seasonal_coef is not None else '否'}")

        return result

    def forecast_with_trend(self, observations: np.ndarray,
                           n_ahead: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """带趋势的预测接口（向后兼容）"""
        self.fit(observations)
        self._last_fit_n = len(observations)
        return self.predict(n_ahead)

    def forecast_with_intervals(self, observations: np.ndarray,
                                n_ahead: int = 1) -> Dict:
        """带预测区间的完整预测接口"""
        self.fit(observations)
        self._last_fit_n = len(observations)
        return self.predict_with_intervals(n_ahead)

    def partial_fit(self, new_data: np.ndarray,
                    retrain_threshold: float = 0.3,
                    window_reselect: bool = False) -> "BayesianStructuralTimeSeries":
        """
        增量更新模型（无需完全重新训练）

        策略 (自适应增量学习):
        1. 数据合并: 将新数据追加到历史数据，维护滑动窗口
        2. 偏移检测: 检测新数据与旧模型的预测偏差是否超过阈值
        3. 轻量更新:
           - 若偏差小: 用指数移动平均(EMA)更新趋势系数
           - 若偏差大: 触发完全重新拟合
        4. 季节性组件: 增量更新季节性系数
        5. 后验采样: 基于更新的参数重新生成后验样本

        Args:
            new_data: 新到的时序数据
            retrain_threshold: 预测偏差超过此比例时触发完全重训练
            window_reselect: 是否重新选择最优窗口

        Returns:
            更新后的BSTS实例(self)

        Raises:
            ValueError: 如果模型尚未经过初始fit
        """
        if not self.fitted or self.trend_coef is None:
            raise ValueError("partial_fit需要先调用fit()进行初始训练")

        new_data = np.asarray(new_data).ravel()
        n_new = len(new_data)

        if n_new < 1:
            logger.warning("[BSTS-partial] 新数据为空，跳过更新")
            return self

        if self._training_data is not None:
            combined = np.concatenate([self._training_data, new_data])
            max_len = self._max_history_length
            if len(combined) > max_len:
                combined = combined[-max_len:]
        else:
            combined = new_data

        n_combined = len(combined)
        old_n = self._last_fit_n if self._last_fit_n > 0 else n_new

        new_outlier_mask, new_weights = self._identify_outliers(new_data)
        new_x = np.arange(old_n, old_n + n_new, dtype=float)

        predictions_new = self._construct_model(new_x)
        residuals_new = new_data - predictions_new
        weighted_residual_std = np.sqrt(
            np.sum(new_weights * residuals_new ** 2) / (np.sum(new_weights) + 1e-10)
        )
        relative_deviation = abs(weighted_residual_std) / (self.residual_std + 1e-10)

        needs_full_retrain = (
            relative_deviation > retrain_threshold or
            n_new > old_n * 0.5 or
            self._fit_count == 0
        )

        fit_record = {
            'timestamp': self._fit_count,
            'n_new_points': n_new,
            'n_total': n_combined,
            'relative_deviation': float(relative_deviation),
            'full_retrain': needs_full_retrain,
            'prev_residual_std': float(self.residual_std),
            'new_residual_std': float(weighted_residual_std) if n_new > 0 else 0.0
        }

        if needs_full_retrain:
            logger.info(f"[BSTS-partial] 检测到显著偏移(dev={relative_deviation:.3f}), "
                       f"触发完全重训练, 新数据点={n_new}")
            return self.fit(combined)

        lr = self._learning_rate
        effective_lr = min(lr, 0.5 * n_new / max(old_n, 1))

        X_new_design = np.vstack([new_x, np.ones(n_new)]).T
        W_new = np.diag(new_weights)

        XtWX_new = X_new_design.T @ W_new @ X_new_design
        XtWy_new = X_new_design.T @ W_new @ new_data

        reg = 1e-6 * np.eye(2)
        try:
            delta_cov = np.linalg.inv(XtWX_new + reg)
            delta_mean = delta_cov @ XtWy_new
        except Exception:
            delta_mean = np.array([
                np.mean(np.diff(new_data)) if n_new > 1 else 0.0,
                np.mean(new_data)
            ])
            delta_cov = np.eye(2) * self.residual_std

        old_trend = self.trend_coef.copy() if self.trend_coef is not None else np.zeros(2)
        updated_trend = (1 - effective_lr) * old_trend + effective_lr * delta_mean

        old_cov = self.trend_coef_cov.copy() if self.trend_coef_cov is not None else np.eye(2)
        updated_cov = (1 - effective_lr) * old_cov + effective_lr * delta_cov

        self.trend_coef = updated_trend
        self.trend_coef_cov = updated_cov

        new_ss_res = np.sum(new_weights * (new_data - X_new_design @ updated_trend) ** 2)
        effective_n_new = np.sum(new_weights)
        old_ss_proxy = self.residual_std ** 2 * max(old_n, 1)
        updated_var = ((1 - effective_lr) * old_ss_proxy +
                       effective_lr * new_ss_res) / max(old_n + effective_n_new, 1)
        self.residual_std = float(np.sqrt(max(updated_var, 1e-6)))

        if self.seasonal_coef is not None and n_new >= len(self.seasonal_coef):
            period = len(self.seasonal_coef)
            detrended_new = new_data - np.polyval(updated_trend, new_x)

            for i in range(period):
                indices = np.arange(i, n_new, period)
                if len(indices) > 0:
                    w = new_weights[indices]
                    incremental_seasonal = np.sum(w * detrended_new[indices]) / (np.sum(w) + 1e-10)
                    self.seasonal_coef[i] = (
                        (1 - effective_lr * 0.7) * self.seasonal_coef[i] +
                        effective_lr * 0.7 * incremental_seasonal
                    )

        rng = np.random.default_rng(42)
        n_samples = self.n_posterior_samples
        trend_samples = np.zeros((n_samples, 2))
        residual_samples = np.zeros(n_samples)

        for i in range(n_samples):
            sampled_var = inv_gamma_sample(rng,
                                           2.0 + effective_n_new / 2.0,
                                           self.residual_std ** 2 / 2)
            trend_samples[i] = rng.multivariate_normal(
                updated_trend,
                sampled_var * updated_cov
            )
            residual_samples[i] = rng.normal(0, np.sqrt(max(sampled_var, 1e-10)))

        self._posterior_trend_samples = trend_samples
        self._posterior_residual_samples = residual_samples

        self._training_data = combined
        self._last_fit_n = n_combined
        self._fit_count += 1

        self._partial_fit_history.append(fit_record)
        if len(self._partial_fit_history) > 20:
            self._partial_fit_history = self._partial_fit_history[-20:]

        if window_reselect and self.trend_window == 0:
            self.select_optimal_window(combined)

        logger.info(f"[BSTS-partial] 增量更新完成: 新数据={n_new}, 总数据={n_combined}, "
                   f"偏移度={relative_deviation:.4f}, 学习率={effective_lr:.4f}, "
                   f"残差σ={self.residual_std:.4f}, 更新次数={self._fit_count}")

        return self

    def diagnostics(self) -> Dict:
        """返回完整的模型诊断信息（含增量学习状态）"""
        return {
            'model_type': 'BayesianStructuralTimeSeries',
            'fitted': self.fitted,
            'trend_window_used': self._optimal_window or self.trend_window,
            'window_selection_scores': self._window_selection_scores,
            'trend_coefficients': self.trend_coef.tolist() if self.trend_coef is not None else None,
            'detected_seasonality': self._seasonality_detected,
            'seasonality_period': self.detected_seasonality_period,
            'seasonality_strength': self._seasonality_strength,
            'seasonal_coefficients': self.seasonal_coef.tolist() if self.seasonal_coef is not None else None,
            'residual_std': self.residual_std,
            'n_outliers_detected': self._n_outliers,
            'outlier_threshold': self.outlier_threshold,
            'n_posterior_samples': self.n_posterior_samples,
            'confidence_level': self.confidence_level,
            'has_posterior_samples': self._posterior_trend_samples is not None,
            'incremental_learning': {
                'fit_count': self._fit_count,
                'last_fit_n': self._last_fit_n,
                'total_training_points': len(self._training_data) if self._training_data is not None else 0,
                'learning_rate': self._learning_rate,
                'max_history_length': self._max_history_length,
                'n_partial_fit_calls': len(self._partial_fit_history),
                'partial_fit_history': self._partial_fit_history[-5:] if self._partial_fit_history else []
            }
        }


def inv_gamma_sample(rng, df: float, scale: float) -> float:
    """从逆Gamma分布采样"""
    return scale / rng.chisquare(max(df, 0.1))
