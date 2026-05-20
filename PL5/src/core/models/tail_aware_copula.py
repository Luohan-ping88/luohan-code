"""
尾部敏感Copula模型 V1.0
多Copula混合 + 尾部依赖建模

改进点:
1. 多Copula混合 (Gaussian + t + Gumbel)
2. 尾部依赖建模 (极值理论)
3. EM算法权重估计
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from scipy.optimize import minimize
from scipy.special import gamma, gammainc
import logging

logger = logging.getLogger(__name__)


class BaseCopula:
    """Copula基类"""
    
    def fit(self, data: np.ndarray) -> 'BaseCopula':
        raise NotImplementedError
    
    def pdf(self, u: np.ndarray) -> np.ndarray:
        raise NotImplementedError
    
    def cdf(self, u: np.ndarray) -> np.ndarray:
        raise NotImplementedError
    
    def sample(self, n: int) -> np.ndarray:
        raise NotImplementedError
    
    def log_likelihood(self, data: np.ndarray) -> float:
        pdf_vals = self.pdf(data)
        return np.sum(np.log(pdf_vals + 1e-10))


class GaussianCopula(BaseCopula):
    """高斯Copula"""
    
    def __init__(self, correlation: Optional[np.ndarray] = None):
        self.correlation = correlation
        self.dimension = 0
    
    def fit(self, data: np.ndarray) -> 'GaussianCopula':
        """
        拟合高斯Copula
        
        Args:
            data: 标准化后的边缘分布数据 (n_samples, n_dims)
        """
        self.dimension = data.shape[1] if data.ndim > 1 else 1
        
        if data.ndim > 1:
            self.correlation = np.corrcoef(data.T)
            np.fill_diagonal(self.correlation, 1.0)
        else:
            self.correlation = np.array([[1.0]])
        
        self.correlation = np.clip(self.correlation, -0.999, 0.999)
        
        return self
    
    def pdf(self, u: np.ndarray) -> np.ndarray:
        """计算概率密度"""
        if u.ndim == 1:
            u = u.reshape(-1, 1)
        
        z = stats.norm.ppf(np.clip(u, 1e-6, 1-1e-6))
        
        det_r = np.linalg.det(self.correlation)
        
        z_centered = z - z.mean(axis=0)
        
        try:
            inv_r = np.linalg.inv(self.correlation)
            mahal = np.sum(z_centered @ inv_r * z_centered, axis=1)
            pdf_val = np.exp(-0.5 * mahal) / (np.sqrt(det_r) * (2 * np.pi) ** (self.dimension / 2))
        except np.linalg.LinAlgError:
            pdf_val = np.ones(len(u)) * 0.1
        
        return pdf_val
    
    def sample(self, n: int) -> np.ndarray:
        """采样"""
        z = np.random.randn(n, self.dimension)
        
        try:
            L = np.linalg.cholesky(self.correlation)
            z = z @ L.T
        except np.linalg.LinAlgError:
            pass
        
        u = stats.norm.cdf(z)
        return u


class TCopula(BaseCopula):
    """t-Copula (用于建模中度尾部相关)"""
    
    def __init__(self, correlation: Optional[np.ndarray] = None, df: float = 4.0):
        self.correlation = correlation
        self.df = df
        self.dimension = 0
    
    def fit(self, data: np.ndarray) -> 'TCopula':
        """拟合t-Copula"""
        self.dimension = data.shape[1] if data.ndim > 1 else 1
        
        if data.ndim > 1:
            self.correlation = np.corrcoef(data.T)
            np.fill_diagonal(self.correlation, 1.0)
        else:
            self.correlation = np.array([[1.0]])
        
        self.correlation = np.clip(self.correlation, -0.999, 0.999)
        
        return self
    
    def pdf(self, u: np.ndarray) -> np.ndarray:
        """计算概率密度"""
        if u.ndim == 1:
            u = u.reshape(-1, 1)
        
        z = stats.norm.ppf(np.clip(u, 1e-6, 1-1e-6))
        
        det_r = np.linalg.det(self.correlation)
        
        try:
            inv_r = np.linalg.inv(self.correlation)
            mahal = np.sum(z @ inv_r * z, axis=1)
            
            const = gamma((self.df + self.dimension) / 2) / (
                gamma(self.df / 2) * 
                (np.pi * self.df) ** (self.dimension / 2) * 
                np.sqrt(det_r)
            )
            
            pdf_val = const * (1 + mahal / self.df) ** (-(self.df + self.dimension) / 2)
        except np.linalg.LinAlgError:
            pdf_val = np.ones(len(u)) * 0.1
        
        return pdf_val
    
    def sample(self, n: int) -> np.ndarray:
        """采样"""
        z = np.random.randn(n, self.dimension)
        
        try:
            L = np.linalg.cholesky(self.correlation)
            z = z @ L.T
        except np.linalg.LinAlgError:
            pass
        
        s = np.random.chisquare(self.df, n) / self.df
        t = z / np.sqrt(s[:, np.newaxis])
        
        u = stats.t.cdf(t, df=self.df)
        return u


class GumbelCopula(BaseCopula):
    """Gumbel Copula (用于建模上尾相关)"""
    
    def __init__(self, theta: float = 1.5):
        self.theta = np.clip(theta, 1.0, 10.0)
        self.dimension = 0
    
    def fit(self, data: np.ndarray) -> 'GumbelCopula':
        """拟合Gumbel Copula"""
        self.dimension = data.shape[1] if data.ndim > 1 else 1
        
        if self.dimension > 1:
            kendall_tau = self._compute_kendall_tau(data)
            self.theta = 1 / (1 - kendall_tau + 1e-6)
            self.theta = np.clip(self.theta, 1.0, 10.0)
        
        return self
    
    def _compute_kendall_tau(self, data: np.ndarray) -> float:
        """计算Kendall tau"""
        n = len(data)
        
        concordant = 0
        total = 0
        
        for i in range(n):
            for j in range(i + 1, n):
                prod = 1
                for d in range(self.dimension):
                    prod *= (data[i, d] - data[j, d])
                
                if prod > 0:
                    concordant += 1
                total += 1
        
        return concordant / total if total > 0 else 0.0
    
    def pdf(self, u: np.ndarray) -> np.ndarray:
        """计算概率密度 (近似)"""
        if u.ndim == 1:
            u = u.reshape(-1, 1)
        
        n = len(u)
        pdf_val = np.ones(n)
        
        for i in range(n):
            prod = 1.0
            sum_log = 0.0
            
            for d in range(self.dimension):
                if u[i, d] < 1e-6 or u[i, d] > 1 - 1e-6:
                    continue
                
                prod *= -np.log(u[i, d])
                sum_log += (-np.log(u[i, d])) ** self.theta
            
            if prod > 1e-10 and sum_log > 1e-10:
                log_term = (prod ** self.theta) / sum_log
                pdf_val[i] = (
                    np.exp(-sum_log) * 
                    prod ** (self.theta - 1) * 
                    sum_log ** (-self.dimension)
                )
        
        return np.clip(pdf_val, 0, 10)
    
    def sample(self, n: int) -> np.ndarray:
        """采样 (使用拒绝采样)"""
        samples = []
        dim = self.dimension
        
        while len(samples) < n:
            z = np.random.exponential(1, dim)
            v = np.random.exponential(1)
            
            s = z / v ** (1 / self.theta)
            
            u = np.exp(-s)
            
            if np.random.random() < 1 / self.theta:
                samples.append(u)
        
        return np.array(samples[:n])


class TailAwareCopula:
    """
    尾部敏感Copula混合模型
    
    特点:
    1. 多Copula混合: Gaussian (线性相关) + t (中尾相关) + Gumbel (上尾相关)
    2. EM算法权重估计
    3. 尾部放大机制
    """
    
    def __init__(
        self,
        copula_types: List[str] = None,
        enable_tail_boost: bool = True,
        tail_threshold: float = 0.1
    ):
        self.copula_types = copula_types or ['gaussian', 't', 'gumbel']
        self.enable_tail_boost = enable_tail_boost
        self.tail_threshold = tail_threshold
        
        self.copulas: Dict[str, BaseCopula] = {}
        self.mixture_weights: np.ndarray = np.array([])
        self.is_fitted = False
        
        self._init_copulas()
    
    def _init_copulas(self):
        """初始化各类型Copula"""
        for copula_type in self.copula_types:
            if copula_type == 'gaussian':
                self.copulas[copula_type] = GaussianCopula()
            elif copula_type == 't':
                self.copulas[copula_type] = TCopula(df=4.0)
            elif copula_type == 'gumbel':
                self.copulas[copula_type] = GumbelCopula(theta=1.5)
    
    def fit(self, data: np.ndarray, max_iter: int = 50, tol: float = 1e-4) -> 'TailAwareCopula':
        """
        使用EM算法拟合混合Copula
        
        Args:
            data: 标准化后的边缘分布数据
            max_iter: 最大迭代次数
            tol: 收敛容忍度
        """
        logger.info(f"开始拟合尾部敏感Copula，数据形状: {data.shape}")
        
        n_samples = len(data)
        n_components = len(self.copulas)
        
        weights = np.ones(n_components) / n_components
        
        for copula in self.copulas.values():
            copula.fit(data)
        
        log_likelihood_history = []
        
        for iteration in range(max_iter):
            responsibilities = np.zeros((n_samples, n_components))
            
            for i, (name, copula) in enumerate(self.copulas.items()):
                responsibilities[:, i] = weights[i] * copula.pdf(data)
            
            row_sums = responsibilities.sum(axis=1, keepdims=True)
            responsibilities = responsibilities / (row_sums + 1e-10)
            
            new_weights = responsibilities.mean(axis=0)
            
            for i, (name, copula) in enumerate(self.copulas.items()):
                if new_weights[i] > 0.01:
                    copula.fit(data)
            
            weights = new_weights
            
            log_likelihood = 0
            for i, (name, copula) in enumerate(self.copulas.items()):
                log_likelihood += weights[i] * np.sum(np.log(copula.pdf(data) + 1e-10))
            log_likelihood_history.append(log_likelihood)
            
            if len(log_likelihood_history) >= 2:
                improvement = log_likelihood_history[-1] - log_likelihood_history[-2]
                if abs(improvement) < tol:
                    logger.info(f"Copula拟合收敛于第 {iteration + 1} 次迭代")
                    break
        
        self.mixture_weights = weights / weights.sum()
        self.is_fitted = True
        
        logger.info(f"混合Copula拟合完成，权重: {dict(zip(self.copulas.keys(), self.mixture_weights))}")
        
        return self
    
    def pdf(self, u: np.ndarray) -> np.ndarray:
        """
        计算混合Copula的概率密度
        
        Args:
            u: 边缘分布概率 (标准化后)
            
        Returns:
            概率密度
        """
        if not self.is_fitted:
            return np.ones(len(u)) if u.ndim == 1 else np.ones(len(u[:, 0]))
        
        pdf_vals = np.zeros(len(u))
        
        for i, (name, copula) in enumerate(self.copulas.items()):
            pdf_vals += self.mixture_weights[i] * copula.pdf(u)
        
        if self.enable_tail_boost:
            pdf_vals = self._apply_tail_boost(pdf_vals, u)
        
        return pdf_vals
    
    def _apply_tail_boost(self, pdf_vals: np.ndarray, u: np.ndarray) -> np.ndarray:
        """
        尾部放大机制
        
        当概率较低时，增加其权重，使尾部特征更明显
        """
        normalized = pdf_vals / (pdf_vals.max() + 1e-10)
        
        tail_mask = normalized < self.tail_threshold
        
        boost_factor = 1.0 + np.exp(-normalized * 10) * 0.5
        
        pdf_vals = pdf_vals * boost_factor
        
        pdf_vals = pdf_vals / (pdf_vals.sum() + 1e-10)
        
        return pdf_vals
    
    def predict_joint_probability(
        self,
        marginals: np.ndarray,
        digit_combinations: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        预测多维联合概率
        
        Args:
            marginals: 各位置的边缘概率
            digit_combinations: 要评估的数字组合
            
        Returns:
            各组合的联合概率
        """
        if not self.is_fitted:
            joint = np.ones(10)
            for i in range(10):
                for m in marginals.values():
                    if i < len(m):
                        joint[i] *= m[i]
            return joint / (joint.sum() + 1e-10)
        
        n_dims = len(marginals)
        
        if digit_combinations is None:
            digit_combinations = np.array([[d] for d in range(10)])
        
        joint_probs = np.zeros(len(digit_combinations))
        
        for i, digits in enumerate(digit_combinations):
            u = np.zeros(n_dims)
            
            for d, (pos, m) in enumerate(marginals.items()):
                if d < len(digits) and digits[d] < len(m):
                    u[d] = np.sum(m[:digits[d] + 1])
                else:
                    u[d] = 0.5
            
            u = np.clip(u, 1e-6, 1 - 1e-6)
            
            joint_probs[i] = self.pdf(u.reshape(1, -1))[0]
        
        joint_probs = joint_probs / (joint_probs.sum() + 1e-10)
        
        return joint_probs
    
    def sample(self, n: int) -> np.ndarray:
        """从混合Copula采样"""
        if not self.is_fitted:
            return np.random.rand(n, len(self.mixture_weights))
        
        n_components = len(self.copulas)
        
        component_choices = np.random.choice(
            n_components, size=n, p=self.mixture_weights
        )
        
        samples = np.zeros((n, list(self.copulas.values())[0].dimension))
        
        for i, (name, copula) in enumerate(self.copulas.items()):
            mask = component_choices == i
            if mask.sum() > 0:
                samples[mask] = copula.sample(mask.sum())
        
        return samples
    
    def get_tail_dependence(self) -> Dict[str, float]:
        """
        获取各Copula的尾部依赖系数
        """
        tail_dep = {}
        
        if 'gaussian' in self.copulas and 'gaussian' in self.mixture_weights:
            corr = self.copulas['gaussian'].correlation
            if corr is not None and len(corr) >= 2:
                rho = corr[0, 1]
                tail_dep['gaussian'] = 0.0
        
        if 't' in self.copulas and 't' in self.mixture_weights:
            df = self.copulas['t'].df
            rho = self.copulas['t'].correlation[0, 1] if hasattr(self.copulas['t'], 'correlation') else 0
            if df > 2:
                tail_dep['t'] = 2 * stats.t.cdf(
                    -np.sqrt((df + 1) * (1 - rho) / (1 + rho)), df + 1
                )
            else:
                tail_dep['t'] = 0.0
        
        if 'gumbel' in self.copulas:
            theta = self.copulas['gumbel'].theta
            tail_dep['gumbel'] = 2 - 2 ** (1 / theta)
        
        for cop_type in self.copulas:
            if cop_type not in tail_dep:
                tail_dep[cop_type] = 0.0
        
        return tail_dep
