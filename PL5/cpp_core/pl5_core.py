"""
C++模块Python回退实现
当C++模块不可用时使用纯Python实现（功能完整，性能略低）
"""

import math
import numpy as np
from typing import List


class FeatureCalculator:
    """Python实现的特征计算器（C++回退）—— 尽量使用numpy向量化"""

    @staticmethod
    def calculate_mean(data: List[int]) -> float:
        if not data:
            return 0.0
        return float(np.mean(data))

    @staticmethod
    def calculate_std(data: List[int]) -> float:
        if len(data) < 2:
            return 0.0
        return float(np.std(data, ddof=1))

    @staticmethod
    def calculate_max(data: List[int]) -> int:
        return int(max(data)) if data else 0

    @staticmethod
    def calculate_min(data: List[int]) -> int:
        return int(min(data)) if data else 0

    @staticmethod
    def calculate_entropy(data: List[int]) -> float:
        """Shannon 信息熵"""
        if not data:
            return 0.0
        arr = np.array(data)
        counts = np.bincount(arr[arr >= 0], minlength=10)
        probs = counts / counts.sum()
        probs = probs[probs > 0]
        return float(-np.sum(probs * np.log2(probs)))

    @staticmethod
    def rolling_mean(data: List[int], window: int) -> List[float]:
        """O(n) 滑动窗口均值"""
        n = len(data)
        result = []
        running_sum = 0
        for i in range(n):
            running_sum += data[i]
            if i >= window:
                running_sum -= data[i - window]
                result.append(running_sum / window)
            else:
                result.append(running_sum / (i + 1))
        return result

    @staticmethod
    def rolling_std(data: List[int], window: int) -> List[float]:
        """O(n) 滑动窗口标准差（基于Σx和Σx²）"""
        n = len(data)
        result = []
        sum_x = 0.0
        sum_x2 = 0.0
        for i in range(n):
            sum_x  += data[i]
            sum_x2 += data[i] * data[i]
            if i >= window:
                sum_x  -= data[i - window]
                sum_x2 -= data[i - window] * data[i - window]
                count = window
            else:
                count = i + 1
            if count < 2:
                result.append(0.0)
            else:
                mean = sum_x / count
                variance = max(0.0, sum_x2 / count - mean * mean)
                result.append(math.sqrt(variance))
        return result

    @staticmethod
    def rolling_frequency(data: List[int], window: int,
                          num_digits: int = 10) -> List[List[float]]:
        """O(n) 滑动计数数组频率统计"""
        n = len(data)
        freq = [0] * num_digits
        result = []
        for i in range(n):
            if 0 <= data[i] < num_digits:
                freq[data[i]] += 1
            if i >= window and 0 <= data[i - window] < num_digits:
                freq[data[i - window]] -= 1
            count = min(i + 1, window)
            result.append([f / count for f in freq])
        return result

    @staticmethod
    def lag_features(data: List[int], lag: int) -> List[int]:
        result = [0] * len(data)
        for i in range(lag, len(data)):
            result[i] = data[i - lag]
        return result

    @staticmethod
    def calculate_hurst(data: List[int]) -> float:
        """R/S 分析估计 Hurst 指数"""
        n = len(data)
        if n < 10:
            return 0.5
        arr = np.array(data, dtype=float)
        mean = arr.mean()
        cum_dev = np.cumsum(arr - mean)
        R = cum_dev.max() - cum_dev.min()
        S = arr.std(ddof=1)
        if S == 0:
            return 0.5
        hurst = math.log(R / S) / math.log(n)
        return float(min(max(hurst, 0.0), 1.0))

    @staticmethod
    def calculate_lyapunov(data: List[int]) -> float:
        """最大 Lyapunov 指数简化估计"""
        n = len(data)
        if n < 10:
            return 0.0
        total = 0.0
        count = 0
        for i in range(1, n - 1):
            d0 = abs(data[i] - data[i - 1]) + 1e-6
            d1 = abs(data[i + 1] - data[i])
            total += math.log(d1 / d0)
            count += 1
        return total / count if count > 0 else 0.0

    @staticmethod
    def fft_transform(data: List[int]) -> List[float]:
        """使用 numpy FFT（O(n log n)）"""
        arr = np.array(data, dtype=float)
        spectrum = np.abs(np.fft.fft(arr))
        return spectrum.tolist()


class HMMModel:
    """Python实现的HMM模型（C++回退）—— 使用 GaussianMixture 近似"""

    def __init__(self, n_components: int = 4):
        self.n_components = n_components
        self._gmm = None
        self._means = None
        self._fitted = False

    def fit(self, data: List[int]):
        """用 GMM 近似 HMM 训练"""
        try:
            from sklearn.mixture import GaussianMixture
            arr = np.array(data, dtype=float).reshape(-1, 1)
            self._gmm = GaussianMixture(
                n_components=self.n_components,
                covariance_type='full',
                random_state=42,
                n_init=3
            )
            self._gmm.fit(arr)
            self._means = self._gmm.means_.flatten()
            self._fitted = True
        except Exception:
            # 兜底：均匀划分区间
            lo, hi = min(data), max(data)
            step = (hi - lo + 1) / self.n_components
            self._means = [lo + step * i for i in range(self.n_components)]
            self._fitted = True

    def predict(self, data: List[int]) -> List[int]:
        """预测状态序列"""
        if not self._fitted or self._means is None:
            return [0] * len(data)
        if self._gmm is not None:
            arr = np.array(data, dtype=float).reshape(-1, 1)
            return self._gmm.predict(arr).tolist()
        # 兜底：最近均值
        states = []
        for v in data:
            best = int(np.argmin([abs(v - m) for m in self._means]))
            states.append(best)
        return states

    def predict_proba(self, data: List[int]) -> List[List[float]]:
        """预测状态概率"""
        if self._gmm is not None:
            arr = np.array(data, dtype=float).reshape(-1, 1)
            return self._gmm.predict_proba(arr).tolist()
        # 兜底：基于距离的 softmax
        result = []
        for v in data:
            dists = [1.0 / (abs(v - m) + 1e-6) for m in (self._means or [])]
            s = sum(dists) or 1.0
            result.append([d / s for d in dists])
        return result


class CopulaModel:
    """Python实现的Copula模型（C++回退）"""

    def __init__(self):
        self._data = None
        self._tau = None

    def fit(self, data):
        """计算 Kendall's tau 矩阵"""
        from scipy.stats import kendalltau
        self._data = data
        n = len(data)
        self._tau = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if len(data[i]) == len(data[j]) and len(data[i]) >= 2:
                    tau_val, _ = kendalltau(data[i], data[j])
                    self._tau[i][j] = float(tau_val) if not math.isnan(tau_val) else 0.0
                    self._tau[j][i] = self._tau[i][j]

    def calculate_kendall_tau(self, i: int, j: int) -> float:
        if self._tau and i < len(self._tau) and j < len(self._tau[i]):
            return self._tau[i][j]
        return 0.0

    def get_correlation_matrix(self) -> List[List[float]]:
        return self._tau or []


def benchmark() -> int:
    """性能测试 —— 返回耗时毫秒"""
    import time
    test_data = list(range(10000))
    start = time.time()
    for _ in range(1000):
        FeatureCalculator.rolling_mean(test_data, 20)
    return int((time.time() - start) * 1000)


import logging as _log
_log.getLogger(__name__).debug("[pl5_core] Python fallback implementation loaded (C++ module not available)")
