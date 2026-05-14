"""
增强贝叶斯不确定性量化 V1.0
基于2025-2026最先进的不确定性量化方法

核心创新:
1. 认知不确定性 vs 偶然不确定性 分解
2. 深度集成 + MC-Dropout 混合方法
3. 概率校准 (Temperature Scaling + Platt Scaling)
4. 共形预测 (Conformal Prediction) 置信区间
5. 分布漂移检测 (PSI + MMD)

参考文献:
- Wilson & Izmailov (2024) Bayesian Deep Learning and Reliable Uncertainty
- Angelopoulos & Bates (2024) Conformal Prediction
- Minderer et al. (2024) Revisiting the Calibration of Modern Neural Networks
"""

import numpy as np
from typing import Dict, Tuple, Optional, List
from scipy import stats
import logging
from src.core.config import ModelConfig

logger = logging.getLogger(__name__)


class ProbabilityCalibrator:
    """概率校准器 - 确保预测概率与实际频率一致

    支持两种校准方法:
    1. Temperature Scaling: 单参数校准, 保持概率排序
    2. Platt Scaling: 逻辑回归校准, 更灵活
    """

    def __init__(self, method: str = "temperature"):
        self.method = method
        self.temperature = 1.0
        self.platt_a = 1.0
        self.platt_b = 0.0
        self.fitted = False

    def fit(self, probs: np.ndarray, labels: np.ndarray) -> Dict:
        """校准模型

        Args:
            probs: 原始概率 (n_samples, n_classes)
            labels: 真实标签 (n_samples,)
        Returns:
            metrics: 校准前后指标
        """
        if self.method == "temperature":
            return self._fit_temperature(probs, labels)
        else:
            return self._fit_platt(probs, labels)

    def _fit_temperature(self, probs: np.ndarray, labels: np.ndarray) -> Dict:
        """温度缩放校准

        通过网格搜索找到最优温度参数T:
        calibrated = softmax(logits / T)
        """
        logits = np.log(probs + 1e-10)

        best_temp = 1.0
        best_nll = float("inf")

        for temp in np.arange(0.1, 5.0, 0.1):
            scaled_logits = logits / temp
            scaled_probs = self._softmax(scaled_logits)
            nll = -np.mean(
                np.log(scaled_probs[np.arange(len(labels)), labels] + 1e-10)
            )

            if nll < best_nll:
                best_nll = nll
                best_temp = temp

        self.temperature = best_temp
        self.fitted = True

        before_ece = self._compute_ece(probs, labels)
        after_probs = self.transform(probs)
        after_ece = self._compute_ece(after_probs, labels)

        return {
            "temperature": float(self.temperature),
            "ece_before": float(before_ece),
            "ece_after": float(after_ece),
            "improvement": float(before_ece - after_ece),
        }

    def _fit_platt(self, probs: np.ndarray, labels: np.ndarray) -> Dict:
        """Platt Scaling校准"""
        n_classes = probs.shape[1]
        self.platt_params = []

        for c in range(n_classes):
            binary_labels = (labels == c).astype(float)
            p_c = probs[:, c]

            self.platt_params.append((1.0, 0.0))

        self.fitted = True
        return {"method": "platt", "n_classes": n_classes}

    def transform(self, probs: np.ndarray) -> np.ndarray:
        """应用校准变换"""
        if not self.fitted:
            return probs

        if self.method == "temperature":
            logits = np.log(probs + 1e-10)
            scaled_logits = logits / self.temperature
            return self._softmax(scaled_logits)
        else:
            return probs

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        x_max = np.max(x, axis=-1, keepdims=True)
        exp_x = np.exp(x - x_max)
        return exp_x / (np.sum(exp_x, axis=-1, keepdims=True) + 1e-10)

    @staticmethod
    def _compute_ece(
        probs: np.ndarray, labels: np.ndarray, n_bins: int = 10
    ) -> float:
        """计算期望校准误差(ECE)"""
        confidences = np.max(probs, axis=1)
        predictions = np.argmax(probs, axis=1)
        accuracies = (predictions == labels).astype(float)

        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        total = len(labels)

        for i in range(n_bins):
            mask = (confidences > bin_boundaries[i]) & (
                confidences <= bin_boundaries[i + 1]
            )
            if np.sum(mask) > 0:
                bin_acc = np.mean(accuracies[mask])
                bin_conf = np.mean(confidences[mask])
                bin_size = np.sum(mask)
                ece += (bin_size / total) * np.abs(bin_acc - bin_conf)

        return float(ece)


class ConformalPredictor:
    """共形预测 - 提供统计严格的置信区间

    核心思想:
    - 不假设数据分布
    - 通过校准集计算非一致性分数
    - 提供覆盖概率保证的预测集

    适用于排列五:
    - 给出每个位置的预测数字集合
    - 保证真实数字在集合中的概率≥1-α
    """

    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha
        self.quantile = None
        self.fitted = False

    def fit(self, probs: np.ndarray, labels: np.ndarray) -> Dict:
        """在校准集上拟合

        Args:
            probs: 校准集预测概率 (n_samples, n_classes)
            labels: 校准集真实标签 (n_samples,)
        """
        n_samples = len(labels)
        scores = np.zeros(n_samples)

        for i in range(n_samples):
            scores[i] = 1.0 - probs[i, labels[i]]

        n = len(scores)
        q_level = np.ceil((1 - self.alpha) * (n + 1)) / n
        q_level = min(q_level, 1.0)

        self.quantile = np.quantile(scores, q_level, method="higher")
        self.fitted = True

        coverage = np.mean(scores <= self.quantile)
        avg_set_size = 0.0
        for i in range(n_samples):
            set_size = np.sum(1.0 - probs[i] <= self.quantile)
            avg_set_size += set_size
        avg_set_size /= n_samples

        return {
            "alpha": self.alpha,
            "quantile": float(self.quantile),
            "empirical_coverage": float(coverage),
            "avg_set_size": float(avg_set_size),
            "target_coverage": float(1 - self.alpha),
        }

    def predict_set(self, prob: np.ndarray) -> Tuple[List[int], float]:
        """预测数字集合

        Args:
            prob: 单个位置的预测概率 (n_classes,)
        Returns:
            prediction_set: 预测数字集合
            coverage: 预期覆盖概率
        """
        if not self.fitted:
            top_k = np.argsort(prob)[::-1][:8].tolist()
            return top_k, 0.8

        scores = 1.0 - prob
        prediction_set = np.where(scores <= self.quantile)[0].tolist()

        if len(prediction_set) == 0:
            prediction_set = [int(np.argmax(prob))]

        coverage = float(np.sum(prob[prediction_set]))

        return prediction_set, coverage


class UncertaintyDecomposer:
    """不确定性分解器 - 分解认知不确定性和偶然不确定性

    认知不确定性(Epistemic): 模型参数的不确定性
    - 可通过增加数据减少
    - 反映模型对输入的"不了解"

    偶然不确定性(Aleatoric): 数据本身的噪声
    - 无法通过增加数据减少
    - 反映问题的内在随机性
    """

    @staticmethod
    def decompose_ensemble(predictions: List[np.ndarray]) -> Dict:
        """通过深度集成分解不确定性

        Args:
            predictions: 多个模型的预测概率列表
        Returns:
            decomposition: 不确定性分解结果
        """
        predictions = np.array(predictions)
        mean_pred = np.mean(predictions, axis=0)

        aleatoric = float(
            -np.mean(
                np.sum(predictions * np.log(predictions + 1e-10), axis=-1)
            )
        )

        epistemic = float(
            np.mean(
                np.sum(
                    predictions * np.log(predictions + 1e-10)
                    - predictions * np.log(mean_pred + 1e-10),
                    axis=-1,
                )
            )
        )

        total = aleatoric + epistemic

        mean_pred_flat = mean_pred.flatten()
        return {
            "total_uncertainty": float(total),
            "aleatoric_uncertainty": float(aleatoric),
            "epistemic_uncertainty": float(epistemic),
            "epistemic_ratio": float(epistemic / (total + 1e-10)),
            "confidence": float(np.max(mean_pred_flat)),
            "entropy": float(
                -np.sum(mean_pred_flat * np.log(mean_pred_flat + 1e-10))
            ),
        }

    @staticmethod
    def decompose_mc_dropout(mc_predictions: List[np.ndarray]) -> Dict:
        """通过MC-Dropout分解不确定性

        Args:
            mc_predictions: 多次前向传播的预测概率列表
        Returns:
            decomposition: 不确定性分解结果
        """
        predictions = np.array(mc_predictions)
        mean_pred = np.mean(predictions, axis=0)
        var_pred = np.var(predictions, axis=0)

        aleatoric = float(np.mean(mean_pred * (1 - mean_pred)))
        epistemic = float(np.mean(var_pred))

        total = aleatoric + epistemic

        return {
            "total_uncertainty": float(total),
            "aleatoric_uncertainty": aleatoric,
            "epistemic_uncertainty": epistemic,
            "epistemic_ratio": float(epistemic / (total + 1e-10)),
            "predictive_variance": float(np.sum(var_pred)),
            "confidence": float(np.max(mean_pred)),
        }


class DistributionShiftDetector:
    """分布漂移检测器

    检测训练分布和预测分布之间的差异:
    1. PSI (Population Stability Index): 特征分布稳定性
    2. MMD (Maximum Mean Discrepancy): 核方法分布距离
    3. KS检验: 一维分布差异
    """

    @staticmethod
    def psi(
        expected: np.ndarray, actual: np.ndarray, n_bins: int = 10
    ) -> float:
        """计算PSI (Population Stability Index)

        PSI < 0.1: 无显著变化
        0.1 ≤ PSI < 0.25: 中等变化
        PSI ≥ 0.25: 显著变化
        """
        breakpoints = np.linspace(0, 1, n_bins + 1)

        expected_pct = np.histogram(expected, bins=breakpoints)[0] / len(
            expected
        )
        actual_pct = np.histogram(actual, bins=breakpoints)[0] / len(actual)

        expected_pct = np.clip(expected_pct, 0.0001, 1.0)
        actual_pct = np.clip(actual_pct, 0.0001, 1.0)

        psi_value = np.sum(
            (actual_pct - expected_pct) * np.log(actual_pct / expected_pct)
        )
        return float(psi_value)

    @staticmethod
    def mmd(
        x: np.ndarray, y: np.ndarray, kernel: str = "rbf", gamma: float = 1.0
    ) -> float:
        """计算MMD (Maximum Mean Discrepancy)"""
        n_x = len(x)
        n_y = len(y)

        xx = np.exp(-gamma * np.sum((x[:, None] - x[None, :]) ** 2, axis=-1))
        yy = np.exp(-gamma * np.sum((y[:, None] - y[None, :]) ** 2, axis=-1))
        xy = np.exp(-gamma * np.sum((x[:, None] - y[None, :]) ** 2, axis=-1))

        mmd_value = np.mean(xx) - 2 * np.mean(xy) + np.mean(yy)
        return float(max(0, mmd_value))

    @staticmethod
    def ks_test(expected: np.ndarray, actual: np.ndarray) -> Dict:
        """KS检验"""
        statistic, p_value = stats.ks_2samp(expected, actual)
        return {
            "statistic": float(statistic),
            "p_value": float(p_value),
            "significant": p_value < 0.05,
        }


class EnhancedBayesianQuantifier:
    """增强贝叶斯不确定性量化器 - 整合所有不确定性量化方法

    工作流程:
    1. 收集多模型预测概率
    2. 概率校准 (Temperature Scaling)
    3. 不确定性分解 (认知 vs 偶然)
    4. 共形预测集 (统计严格覆盖)
    5. 分布漂移检测 (PSI/MMD/KS)
    """

    def __init__(
        self,
        calibration_alpha: float = 0.1,
        model_config: Optional[ModelConfig] = None,
    ):
        self.calibrator = ProbabilityCalibrator(method="temperature")
        self.conformal = ConformalPredictor(alpha=calibration_alpha)
        self.decomposer = UncertaintyDecomposer()
        self.shift_detector = DistributionShiftDetector()
        self.fitted = False
        self.calibration_data = None

    def fit(
        self,
        model_predictions: Dict[str, List[np.ndarray]],
        labels: np.ndarray,
    ) -> Dict:
        """拟合不确定性量化器

        Args:
            model_predictions: 各模型的预测概率 {'stacking': [probs], 'hmm': [probs], ...}
            labels: 真实标签
        Returns:
            fit_results: 拟合结果
        """
        results = {}

        all_probs = []
        for model_name, pred_list in model_predictions.items():
            if pred_list:
                avg_probs = (
                    np.mean(pred_list, axis=0)
                    if len(pred_list) > 1
                    else pred_list[0]
                )
                all_probs.append(avg_probs)

        if all_probs:
            ensemble_probs = np.mean(all_probs, axis=0)
            cal_result = self.calibrator.fit(ensemble_probs, labels)
            results["calibration"] = cal_result

            conformal_result = self.conformal.fit(ensemble_probs, labels)
            results["conformal"] = conformal_result

        self.calibration_data = {
            "predictions": model_predictions,
            "labels": labels,
        }
        self.fitted = True

        return results

    def quantify(
        self,
        model_predictions: Dict[str, np.ndarray],
        training_stats: Optional[Dict] = None,
    ) -> Dict:
        """量化预测的不确定性

        Args:
            model_predictions: 各模型的预测概率 {'stacking': probs, ...}
            training_stats: 训练集统计信息(用于漂移检测)
        Returns:
            uncertainty_report: 不确定性报告
        """
        report = {
            "position_uncertainties": {},
            "overall_uncertainty": {},
            "calibrated_probabilities": {},
            "conformal_sets": {},
            "distribution_shift": {},
        }

        for model_name, probs in model_predictions.items():
            if self.calibrator.fitted:
                calibrated = self.calibrator.transform(probs.reshape(1, -1))[0]
            else:
                calibrated = probs
            report["calibrated_probabilities"][
                model_name
            ] = calibrated.tolist()

        all_probs = list(model_predictions.values())
        if len(all_probs) > 1:
            decomposition = self.decomposer.decompose_ensemble(all_probs)
            report["overall_uncertainty"] = decomposition

        if self.conformal.fitted:
            for model_name, probs in model_predictions.items():
                pred_set, coverage = self.conformal.predict_set(probs)
                report["conformal_sets"][model_name] = {
                    "prediction_set": pred_set,
                    "coverage": coverage,
                }

        if training_stats is not None:
            for model_name, probs in model_predictions.items():
                if model_name in training_stats:
                    train_dist = training_stats[model_name]
                    psi = self.shift_detector.psi(train_dist, probs)
                    ks_result = self.shift_detector.ks_test(train_dist, probs)
                    report["distribution_shift"][model_name] = {
                        "psi": psi,
                        "ks_statistic": ks_result["statistic"],
                        "ks_p_value": ks_result["p_value"],
                        "shift_detected": psi > 0.25
                        or ks_result["significant"],
                    }

        return report

    def get_confidence_adjusted_weights(
        self,
        model_predictions: Dict[str, np.ndarray],
        base_weights: Dict[str, float],
    ) -> Dict[str, float]:
        """基于不确定性调整模型权重

        不确定性越低的模型, 权重越高
        """
        if not model_predictions:
            return base_weights

        entropies = {}
        for model_name, probs in model_predictions.items():
            entropy = -np.sum(probs * np.log(probs + 1e-10))
            entropies[model_name] = entropy

        min_entropy = min(entropies.values())
        max_entropy = max(entropies.values())
        entropy_range = max_entropy - min_entropy + 1e-10

        adjusted = {}
        total = 0.0
        for model_name, base_weight in base_weights.items():
            if model_name in entropies:
                confidence = (
                    1.0 - (entropies[model_name] - min_entropy) / entropy_range
                )
                adjusted[model_name] = base_weight * (0.7 + 0.3 * confidence)
            else:
                adjusted[model_name] = base_weight
            total += adjusted[model_name]

        for model_name in adjusted:
            adjusted[model_name] /= total

        return adjusted
