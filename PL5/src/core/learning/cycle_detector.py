"""
周期变化检测模块 V1.0

提供多维度的周期性变化检测能力：
1. 频域分析 - 使用 FFT 检测数据中的周期性频率分量
2. 变点检测 - CUSUM 和 PELT 算法（简化版）检测数据分布突变点
3. 周期长度识别 - 自动发现数据中存在的主要周期长度
4. 周期强度评估 - 评估周期的显著性和稳定性
5. 周期变化趋势 - 分析周期是否在发生变化（延长/缩短/消失）

当检测到周期性变化时，为学习模式调整提供依据。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


class CycleChangeType(Enum):
    """周期变化类型"""
    STABLE = "stable"              # 周期稳定
    EXTENDING = "extending"        # 周期延长
    SHORTENING = "shortening"      # 周期缩短
    EMERGING = "emerging"          # 新周期出现
    DISAPPEARING = "disappearing"  # 周期消失
    SHIFTING = "shifting"          # 周期相位/形态偏移


class ChangePointType(Enum):
    """变点类型"""
    MEAN = "mean"                  # 均值突变
    VARIANCE = "variance"          # 方差突变
    TREND = "trend"                # 趋势突变
    DISTRIBUTION = "distribution"  # 分布突变
    FREQUENCY = "frequency"        # 频率突变


class DetectionMethod(Enum):
    """检测方法类型"""
    FFT = "fft"                            # 快速傅里叶变换
    CUSUM = "cusum"                        # 累积和
    PELT = "pelt"                          # 剪枝精确线性时间
    AUTOCORRELATION = "autocorrelation"    # 自相关
    HYBRID = "hybrid"                      # 混合方法


@dataclass
class CycleInfo:
    """单个周期信息"""
    length: int                                      # 周期长度（样本数）
    frequency: float                                 # 对应频率
    strength: float = 0.0                            # 周期强度（0-1，显著性）
    confidence: float = 0.0                          # 置信度（0-1）
    stability: float = 0.0                           # 稳定性（0-1，跨段一致性）
    phase: float = 0.0                               # 相位（弧度）
    method: DetectionMethod = DetectionMethod.FFT    # 检测方法
    detail: str = ""                                 # 详细描述

    def to_dict(self) -> Dict[str, Any]:
        return {
            'length': self.length,
            'frequency': round(self.frequency, 6),
            'strength': round(self.strength, 4),
            'confidence': round(self.confidence, 4),
            'stability': round(self.stability, 4),
            'phase': round(self.phase, 4),
            'method': self.method.value,
            'detail': self.detail,
        }


@dataclass
class CycleResult:
    """周期检测结果"""
    cycles: List[CycleInfo] = field(default_factory=list)
    dominant_cycle: Optional[CycleInfo] = None  # 主导周期
    total_strength: float = 0.0                 # 总周期强度
    is_periodic: bool = False                   # 是否具有显著周期性
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'cycles': [c.to_dict() for c in self.cycles],
            'dominant_cycle': self.dominant_cycle.to_dict() if self.dominant_cycle else None,
            'total_strength': round(self.total_strength, 4),
            'is_periodic': self.is_periodic,
            'timestamp': self.timestamp,
        }


@dataclass
class ChangePoint:
    """单个变点信息"""
    position: int                                              # 变点位置（索引）
    confidence: float = 0.0                                    # 置信度（0-1）
    change_type: ChangePointType = ChangePointType.MEAN        # 变化类型
    magnitude: float = 0.0                                     # 变化幅度
    method: DetectionMethod = DetectionMethod.CUSUM            # 检测方法
    detail: str = ""                                           # 详细描述

    def to_dict(self) -> Dict[str, Any]:
        return {
            'position': self.position,
            'confidence': round(self.confidence, 4),
            'change_type': self.change_type.value,
            'magnitude': round(self.magnitude, 6),
            'method': self.method.value,
            'detail': self.detail,
        }


@dataclass
class CycleChangeResult:
    """周期变化趋势分析结果"""
    change_type: CycleChangeType = CycleChangeType.STABLE
    cycle_length_trend: float = 0.0   # 周期长度变化趋势（正：延长，负：缩短）
    strength_trend: float = 0.0       # 周期强度变化趋势（正：增强，负：减弱）
    early_cycles: List[CycleInfo] = field(default_factory=list)   # 前半段周期
    late_cycles: List[CycleInfo] = field(default_factory=list)    # 后半段周期
    summary: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'change_type': self.change_type.value,
            'cycle_length_trend': round(self.cycle_length_trend, 4),
            'strength_trend': round(self.strength_trend, 4),
            'early_cycles': [c.to_dict() for c in self.early_cycles],
            'late_cycles': [c.to_dict() for c in self.late_cycles],
            'summary': self.summary,
            'timestamp': self.timestamp,
        }


class FFTAnalyzer:
    """FFT 频域分析器

    使用 numpy 实现快速傅里叶变换，检测序列中的周期性频率分量。
    """

    @staticmethod
    def analyze(
        series: np.ndarray,
        detrend: bool = True,
        window: str = "hann"
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """执行 FFT 分析

        Args:
            series: 输入序列
            detrend: 是否去除线性趋势
            window: 窗函数 ('hann', 'hamming', 'none')

        Returns:
            (frequencies, magnitudes, phases) 频率数组、幅值、相位（弧度）
        """
        series = np.asarray(series, dtype=float)
        n = len(series)

        if n < 4:
            return np.array([]), np.array([]), np.array([])

        # 去除线性趋势
        if detrend:
            t = np.arange(n)
            coeffs = np.polyfit(t, series, 1)
            series = series - np.polyval(coeffs, t)

        # 去均值
        series = series - np.mean(series)

        # 加窗以减少频谱泄漏
        if window == "hann":
            w = np.hanning(n)
        elif window == "hamming":
            w = np.hamming(n)
        else:
            w = np.ones(n)

        series = series * w

        # FFT 计算（使用 numpy，不依赖 scipy）
        fft_result = np.fft.rfft(series)
        magnitudes = np.abs(fft_result) * 2.0 / n
        phases = np.angle(fft_result)
        frequencies = np.fft.rfftfreq(n, d=1.0)

        return frequencies, magnitudes, phases

    @staticmethod
    def find_peaks(
        frequencies: np.ndarray,
        magnitudes: np.ndarray,
        min_freq: float = 0.0,
        max_peaks: int = 10,
        prominence_ratio: float = 0.1
    ) -> List[Tuple[int, float, float]]:
        """寻找频谱中的峰值

        Args:
            frequencies: 频率数组
            magnitudes: 幅值数组
            min_freq: 最小频率（过滤 DC 附近）
            max_peaks: 最大峰值数
            prominence_ratio: 显著性比例阈值

        Returns:
            列表 [(index, frequency, magnitude), ...] 按幅值降序
        """
        if len(magnitudes) < 3:
            return []

        # 过滤掉 DC 分量附近
        valid_mask = frequencies > min_freq
        valid_indices = np.where(valid_mask)[0]

        if len(valid_indices) < 3:
            return []

        # 局部最大值检测
        peaks: List[Tuple[int, float, float]] = []
        for i in valid_indices[1:-1]:
            if magnitudes[i] > magnitudes[i - 1] and magnitudes[i] > magnitudes[i + 1]:
                peaks.append((int(i), float(frequencies[i]), float(magnitudes[i])))

        if not peaks:
            return []

        # 按幅值排序
        peaks.sort(key=lambda x: x[2], reverse=True)

        # 显著性过滤：保留相对于最大峰值的比例
        max_mag = peaks[0][2]
        if max_mag <= 0:
            return []
        threshold = max_mag * prominence_ratio
        peaks = [p for p in peaks if p[2] >= threshold]

        return peaks[:max_peaks]


class AutocorrelationAnalyzer:
    """自相关分析器

    计算自相关函数 (ACF) 辅助周期检测，
    验证 FFT 检测到的周期长度。
    """

    @staticmethod
    def compute(series: np.ndarray, max_lag: Optional[int] = None) -> np.ndarray:
        """计算自相关函数 (ACF)

        Args:
            series: 输入序列
            max_lag: 最大滞后阶数

        Returns:
            自相关系数数组（lag 0 ~ max_lag）
        """
        series = np.asarray(series, dtype=float)
        n = len(series)

        if max_lag is None:
            max_lag = min(n // 2, 500)

        if n < 4 or max_lag < 1:
            return np.array([])

        series = series - np.mean(series)
        var = np.var(series)

        if var < 1e-10:
            return np.zeros(max_lag + 1)

        # 使用 FFT 加速自相关计算
        # ACF = IFFT(|FFT(x)|^2)
        fft_size = 1
        while fft_size < 2 * n:
            fft_size *= 2

        fft_x = np.fft.fft(series, n=fft_size)
        acf_full = np.fft.ifft(fft_x * np.conj(fft_x)).real[:max_lag + 1]
        acf_full = acf_full / (var * n)

        return acf_full

    @staticmethod
    def find_periods(
        acf: np.ndarray,
        min_lag: int = 2,
        max_periods: int = 5
    ) -> List[Tuple[int, float]]:
        """从自相关函数中识别周期

        Args:
            acf: 自相关系数数组
            min_lag: 最小滞后
            max_periods: 最大周期数

        Returns:
            列表 [(period, acf_value), ...] 按 ACF 值降序
        """
        if len(acf) < 4:
            return []

        # 寻找局部峰值（正的自相关峰值）
        peaks: List[Tuple[int, float]] = []
        for i in range(min_lag, len(acf) - 1):
            if acf[i] > acf[i - 1] and acf[i] > acf[i + 1] and acf[i] > 0:
                peaks.append((int(i), float(acf[i])))

        if not peaks:
            return []

        # 按自相关值排序
        peaks.sort(key=lambda x: x[1], reverse=True)

        # 去重：相近的周期合并
        filtered: List[Tuple[int, float]] = []
        for period, val in peaks:
            if all(abs(period - p) > max(2, period // 10) for p, _ in filtered):
                filtered.append((period, val))

        return filtered[:max_periods]


class CUSUMDetector:
    """CUSUM (Cumulative Sum) 变点检测器

    通过累积和统计量检测序列中均值发生突变的点，
    支持双边检测（上升和下降变点）。
    """

    @staticmethod
    def detect(
        series: np.ndarray,
        threshold: float = 5.0,
        drift: float = 0.02
    ) -> List[ChangePoint]:
        """CUSUM 变点检测

        Args:
            series: 输入序列
            threshold: 检测阈值（触发变点的累积和门限）
            drift: 允许的漂移量 k（参考值）

        Returns:
            变点列表
        """
        series = np.asarray(series, dtype=float)
        n = len(series)

        if n < 10:
            return []

        mean_val = np.mean(series)
        std_val = np.std(series)

        if std_val < 1e-10:
            return []

        # 标准化
        normalized = (series - mean_val) / std_val

        # 双边 CUSUM
        pos_sum = 0.0   # S+ 检测上升变点
        neg_sum = 0.0   # S- 检测下降变点
        k = drift       # 参考值

        changepoints: List[ChangePoint] = []
        last_cp = 0

        for i in range(n):
            pos_sum = max(0.0, pos_sum + normalized[i] - k)
            neg_sum = min(0.0, neg_sum + normalized[i] + k)

            # 上升变点
            if pos_sum > threshold:
                cp_pos = max(
                    last_cp,
                    i - CUSUMDetector._estimate_start(normalized[last_cp:i + 1], 'up')
                )
                confidence = min(1.0, pos_sum / (threshold * 2.0))
                magnitude = float(np.mean(series[cp_pos:]) - np.mean(series[:cp_pos]))
                changepoints.append(ChangePoint(
                    position=int(cp_pos),
                    confidence=float(confidence),
                    change_type=ChangePointType.MEAN,
                    magnitude=magnitude,
                    method=DetectionMethod.CUSUM,
                    detail=f"CUSUM上升变点 (S+={pos_sum:.2f})"
                ))
                pos_sum = 0.0
                last_cp = i

            # 下降变点
            if abs(neg_sum) > threshold:
                cp_pos = max(
                    last_cp,
                    i - CUSUMDetector._estimate_start(normalized[last_cp:i + 1], 'down')
                )
                confidence = min(1.0, abs(neg_sum) / (threshold * 2.0))
                magnitude = float(np.mean(series[cp_pos:]) - np.mean(series[:cp_pos]))
                changepoints.append(ChangePoint(
                    position=int(cp_pos),
                    confidence=float(confidence),
                    change_type=ChangePointType.MEAN,
                    magnitude=magnitude,
                    method=DetectionMethod.CUSUM,
                    detail=f"CUSUM下降变点 (S-={neg_sum:.2f})"
                ))
                neg_sum = 0.0
                last_cp = i

        return changepoints

    @staticmethod
    def _estimate_start(window: np.ndarray, direction: str = 'up') -> int:
        """估计 CUSUM 变点的起始位置

        通过累积和极值点定位变点发生位置。

        Args:
            window: 检测窗口数据
            direction: 'up' 上升变点 / 'down' 下降变点

        Returns:
            变点在窗口中的偏移量
        """
        n = len(window)
        if n < 2:
            return 0

        cumsum = np.cumsum(window - np.mean(window))
        if direction == 'up':
            # 上升变点：累积和最小值处为起始
            return int(np.argmin(cumsum))
        else:
            # 下降变点：累积和最大值处为起始
            return int(np.argmax(cumsum))


class PELTDetector:
    """PELT (Pruned Exact Linear Time) 变点检测器简化版

    基于动态规划寻找最优变点分割，使用剪枝策略降低复杂度。
    代价函数采用高斯负对数似然（平方误差）。
    """

    @staticmethod
    def detect(
        series: np.ndarray,
        penalty: Optional[float] = None,
        min_segment: int = 5
    ) -> List[ChangePoint]:
        """PELT 变点检测

        Args:
            series: 输入序列
            penalty: 惩罚系数（None 时自动计算）
            min_segment: 最小段长度

        Returns:
            变点列表
        """
        series = np.asarray(series, dtype=float)
        n = len(series)

        if n < 2 * min_segment:
            return []

        std_val = np.std(series)
        if std_val < 1e-10:
            return []

        # 自动计算惩罚值（基于 BIC 思想）
        if penalty is None:
            penalty = 2.0 * np.log(n) * (std_val ** 2)

        # 累积统计量加速段代价计算
        cumsum = np.concatenate([[0.0], np.cumsum(series)])
        cumsum_sq = np.concatenate([[0.0], np.cumsum(series ** 2)])

        def segment_cost(start: int, end: int) -> float:
            """计算段 [start, end) 的代价（平方误差和）"""
            length = end - start
            if length < 1:
                return 0.0
            seg_sum = cumsum[end] - cumsum[start]
            seg_sum_sq = cumsum_sq[end] - cumsum_sq[start]
            mean = seg_sum / length
            var = seg_sum_sq / length - mean ** 2
            var = max(var, 0.0)
            return var * length

        # PELT 动态规划
        # f[t] = min over tau < t of { f[tau] + C(tau, t) + penalty }
        f = np.full(n + 1, np.inf)
        f[0] = -penalty
        changepoint_sets: Dict[int, List[int]] = {0: []}

        # 候选集 R
        R: List[int] = [0]

        for t in range(1, n + 1):
            # 计算所有候选点的代价，选择最优
            best_cost = np.inf
            best_tau = 0
            for tau in R:
                if t - tau < min_segment:
                    continue
                cost = f[tau] + segment_cost(tau, t) + penalty
                if cost < best_cost:
                    best_cost = cost
                    best_tau = tau

            f[t] = best_cost
            prev_cps = changepoint_sets.get(best_tau, [])
            changepoint_sets[t] = prev_cps + ([best_tau] if best_tau > 0 else [])

            # 剪枝：移除不可能成为未来最优的候选点
            # 保留满足 f[tau] + C(tau, t) <= f[t] 的候选
            new_R: List[int] = [0]
            for tau in R:
                if t - tau >= min_segment:
                    pruned_cost = f[tau] + segment_cost(tau, t)
                    if pruned_cost <= f[t]:
                        new_R.append(tau)
            new_R.append(t)
            R = list(set(new_R))

            # 限制候选集大小以控制计算复杂度
            if len(R) > 300:
                R_sorted = sorted(R, key=lambda x: f[x])
                R = R_sorted[:300]

        # 提取最终变点
        final_cps = changepoint_sets.get(n, [])
        changepoints: List[ChangePoint] = []

        prev = 0
        for cp in final_cps:
            if cp <= 0 or cp >= n:
                continue
            # 计算置信度（基于段间均值差异）
            seg1 = series[prev:cp]
            seg2 = series[cp:min(cp + min_segment, n)]
            if len(seg1) > 0 and len(seg2) > 0:
                mean_diff = abs(np.mean(seg2) - np.mean(seg1))
                pooled_std = np.sqrt((np.var(seg1) + np.var(seg2)) / 2.0 + 1e-10)
                confidence = min(1.0, mean_diff / (pooled_std * 2.0 + 1e-10))
                magnitude = float(np.mean(seg2) - np.mean(seg1))
            else:
                confidence = 0.5
                magnitude = 0.0

            changepoints.append(ChangePoint(
                position=int(cp),
                confidence=float(confidence),
                change_type=ChangePointType.MEAN,
                magnitude=magnitude,
                method=DetectionMethod.PELT,
                detail=f"PELT变点 (penalty={penalty:.4f})"
            ))
            prev = cp

        return changepoints


class CycleDetector:
    """周期变化检测器主类

    整合 FFT、CUSUM、PELT 和自相关分析，
    提供周期检测、变点检测和周期变化趋势分析能力。
    """

    def __init__(
        self,
        fft_threshold: float = 0.1,
        cusum_threshold: float = 5.0,
        pelt_penalty: Optional[float] = None,
        min_cycle_length: int = 2,
        max_cycle_length: Optional[int] = None,
        confidence_threshold: float = 0.3,
        enable_pelt: bool = True
    ):
        """
        Args:
            fft_threshold: FFT 峰值显著性阈值
            cusum_threshold: CUSUM 检测阈值
            pelt_penalty: PELT 惩罚系数（None 时自动计算）
            min_cycle_length: 最小周期长度
            max_cycle_length: 最大周期长度
            confidence_threshold: 置信度阈值
            enable_pelt: 是否启用 PELT 算法
        """
        self.fft_threshold = fft_threshold
        self.cusum_threshold = cusum_threshold
        self.pelt_penalty = pelt_penalty
        self.min_cycle_length = min_cycle_length
        self.max_cycle_length = max_cycle_length
        self.confidence_threshold = confidence_threshold
        self.enable_pelt = enable_pelt

        logger.info("周期检测器初始化完成 "
                    f"(FFT阈值: {fft_threshold}, CUSUM阈值: {cusum_threshold}, "
                    f"PELT: {enable_pelt})")

    def detect_cycles(self, series: Union[np.ndarray, List[float]]) -> CycleResult:
        """检测数据中的周期性

        Args:
            series: 数值序列（numpy array 或 list）

        Returns:
            周期检测结果，包含检测到的周期列表
        """
        series = self._preprocess(series)
        if len(series) < 8:
            logger.warning(f"序列长度过短({len(series)})，无法进行周期检测")
            return CycleResult()

        # FFT 频域分析
        fft_cycles = self._detect_cycles_fft(series)

        # 自相关分析辅助验证
        acf_cycles = self._detect_cycles_acf(series)

        # 合并结果（FFT + ACF 交叉验证）
        merged = self._merge_cycle_results(fft_cycles, acf_cycles)

        if not merged:
            return CycleResult(is_periodic=False)

        # 评估总体周期性
        total_strength = sum(c.strength for c in merged)
        dominant = max(merged, key=lambda c: (c.strength, c.confidence))
        is_periodic = (dominant.strength >= self.fft_threshold
                       and dominant.confidence >= self.confidence_threshold)

        result = CycleResult(
            cycles=merged,
            dominant_cycle=dominant,
            total_strength=total_strength,
            is_periodic=is_periodic,
        )

        logger.info(f"周期检测完成: 检测到 {len(merged)} 个周期, "
                    f"主导周期长度={dominant.length}, 强度={dominant.strength:.4f}, "
                    f"周期性={is_periodic}")

        return result

    def detect_changepoints(self, series: Union[np.ndarray, List[float]]) -> List[ChangePoint]:
        """检测数据中的变点

        Args:
            series: 数值序列（numpy array 或 list）

        Returns:
            变点列表，每个变点含位置、置信度、变化类型
        """
        series = self._preprocess(series)
        if len(series) < 10:
            logger.warning(f"序列长度过短({len(series)})，无法进行变点检测")
            return []

        # CUSUM 检测
        cusum_cps = CUSUMDetector.detect(
            series, threshold=self.cusum_threshold
        )

        # PELT 检测
        pelt_cps: List[ChangePoint] = []
        if self.enable_pelt:
            try:
                pelt_cps = PELTDetector.detect(
                    series, penalty=self.pelt_penalty, min_segment=5
                )
            except Exception as e:
                logger.warning(f"PELT 检测失败: {e}")

        # 合并并去重变点
        all_cps = cusum_cps + pelt_cps
        merged = self._merge_changepoints(all_cps, series, min_distance=5)

        logger.info(f"变点检测完成: CUSUM={len(cusum_cps)}, PELT={len(pelt_cps)}, "
                    f"合并后={len(merged)}")

        return merged

    def detect_cycle_changes(self, series: Union[np.ndarray, List[float]]) -> CycleChangeResult:
        """分析周期变化趋势

        将序列分为前半段和后半段，分别检测周期，比较变化趋势
        （延长/缩短/消失/增强等）。

        Args:
            series: 数值序列（numpy array 或 list）

        Returns:
            周期变化趋势分析结果
        """
        series = self._preprocess(series)
        n = len(series)

        if n < 20:
            logger.warning(f"序列长度过短({n})，无法分析周期变化趋势")
            return CycleChangeResult(summary="数据量不足，无法分析周期变化趋势")

        # 分段：前半段 vs 后半段
        mid = n // 2
        early_series = series[:mid]
        late_series = series[mid:]

        early_result = self.detect_cycles(early_series)
        late_result = self.detect_cycles(late_series)

        early_cycles = early_result.cycles
        late_cycles = late_result.cycles

        # 分析变化类型
        change_type, length_trend, strength_trend, summary = self._analyze_cycle_change(
            early_cycles, late_cycles
        )

        result = CycleChangeResult(
            change_type=change_type,
            cycle_length_trend=length_trend,
            strength_trend=strength_trend,
            early_cycles=early_cycles,
            late_cycles=late_cycles,
            summary=summary,
        )

        logger.info(f"周期变化趋势分析完成: 类型={change_type.value}, "
                    f"长度趋势={length_trend:.4f}, 强度趋势={strength_trend:.4f}")

        return result

    # ==================== 内部方法 ====================

    def _preprocess(self, series: Union[np.ndarray, List[float]]) -> np.ndarray:
        """预处理输入序列

        - 转换为 numpy array
        - 展平
        - 插值填充 NaN/Inf
        """
        series = np.asarray(series, dtype=float).flatten()

        # 处理 NaN 和 Inf
        invalid_mask = np.isnan(series) | np.isinf(series)
        if np.any(invalid_mask):
            valid_mask = ~invalid_mask
            if not np.any(valid_mask):
                return np.array([])
            valid_indices = np.where(valid_mask)[0]
            invalid_indices = np.where(invalid_mask)[0]
            if len(valid_indices) >= 2:
                series[invalid_indices] = np.interp(
                    invalid_indices, valid_indices, series[valid_indices]
                )
            else:
                series[invalid_indices] = 0.0

        return series

    def _detect_cycles_fft(self, series: np.ndarray) -> List[CycleInfo]:
        """使用 FFT 检测周期"""
        n = len(series)
        frequencies, magnitudes, phases = FFTAnalyzer.analyze(
            series, detrend=True, window="hann"
        )

        if len(frequencies) == 0:
            return []

        # 确定频率下界（对应最大周期长度）
        max_len = self.max_cycle_length or (n // 2)
        min_freq = 1.0 / max_len if max_len > 0 else 0.0

        peaks = FFTAnalyzer.find_peaks(
            frequencies, magnitudes,
            min_freq=min_freq,
            max_peaks=10,
            prominence_ratio=0.15
        )

        if not peaks:
            return []

        # 总能量（用于强度归一化，排除 DC 分量）
        total_energy = float(np.sum(magnitudes[1:] ** 2))
        if total_energy < 1e-10:
            return []

        cycles: List[CycleInfo] = []
        for idx, freq, mag in peaks:
            if freq <= 0:
                continue
            period = int(round(1.0 / freq))
            if period < self.min_cycle_length or period > n // 2:
                continue

            # 强度：该频率能量占总能量的比例
            energy = mag ** 2
            strength = float(energy / total_energy)
            strength = min(1.0, strength * 2.0)  # 适当放大以便于解读

            # 稳定性：基于峰值显著性（峰值相对邻域均值的突出程度）
            lo = max(0, idx - 2)
            hi = idx + 3
            local_mean = float(np.mean(magnitudes[lo:hi]))
            prominence = (mag - local_mean) / (mag + 1e-10)
            stability = float(max(0.0, min(1.0, prominence)))

            # 置信度：综合强度和稳定性
            confidence = float(min(1.0, strength * 1.5 + stability * 0.5))

            cycles.append(CycleInfo(
                length=period,
                frequency=freq,
                strength=strength,
                confidence=confidence,
                stability=stability,
                phase=float(phases[idx]),
                method=DetectionMethod.FFT,
                detail=f"FFT峰值: freq={freq:.4f}, mag={mag:.4f}"
            ))

        # 去重：相近周期合并
        cycles = self._deduplicate_cycles(cycles)

        return cycles

    def _detect_cycles_acf(self, series: np.ndarray) -> List[CycleInfo]:
        """使用自相关函数辅助检测周期"""
        n = len(series)
        max_lag = min(n // 2, 500)

        acf = AutocorrelationAnalyzer.compute(series, max_lag=max_lag)
        if len(acf) == 0:
            return []

        periods = AutocorrelationAnalyzer.find_periods(
            acf, min_lag=self.min_cycle_length, max_periods=5
        )

        cycles: List[CycleInfo] = []
        for period, acf_val in periods:
            if period < self.min_cycle_length or period > n // 2:
                continue

            # 自相关值作为强度和置信度的参考
            strength = float(max(0.0, min(1.0, acf_val)))
            confidence = float(max(0.0, min(1.0, acf_val * 0.8)))
            stability = float(max(0.0, min(1.0, acf_val)))

            cycles.append(CycleInfo(
                length=period,
                frequency=1.0 / period,
                strength=strength,
                confidence=confidence,
                stability=stability,
                phase=0.0,
                method=DetectionMethod.AUTOCORRELATION,
                detail=f"ACF峰值: lag={period}, acf={acf_val:.4f}"
            ))

        return cycles

    def _merge_cycle_results(
        self,
        fft_cycles: List[CycleInfo],
        acf_cycles: List[CycleInfo]
    ) -> List[CycleInfo]:
        """合并 FFT 和 ACF 的周期检测结果

        当 FFT 和 ACF 检测到相近周期时，增强置信度和稳定性。
        """
        if not fft_cycles and not acf_cycles:
            return []

        merged: List[CycleInfo] = []
        used_acf: set = set()

        # 对每个 FFT 周期，查找 ACF 中是否有相近周期（交叉验证）
        for fft_c in fft_cycles:
            combined = fft_c
            for j, acf_c in enumerate(acf_cycles):
                if j in used_acf:
                    continue
                tolerance = max(1, fft_c.length // 10)
                if abs(acf_c.length - fft_c.length) <= tolerance:
                    # 交叉验证：增强置信度和稳定性
                    combined = CycleInfo(
                        length=fft_c.length,
                        frequency=fft_c.frequency,
                        strength=max(fft_c.strength, acf_c.strength),
                        confidence=min(1.0, fft_c.confidence + acf_c.confidence * 0.3),
                        stability=min(1.0, fft_c.stability + acf_c.stability * 0.3),
                        phase=fft_c.phase,
                        method=DetectionMethod.HYBRID,
                        detail=fft_c.detail + f"; ACF确认(lag={acf_c.length})"
                    )
                    used_acf.add(j)
                    break
            merged.append(combined)

        # 加入未被合并的 ACF 周期
        for j, acf_c in enumerate(acf_cycles):
            if j not in used_acf:
                merged.append(acf_c)

        # 按强度降序排序
        merged.sort(key=lambda c: (c.strength, c.confidence), reverse=True)

        # 去重
        merged = self._deduplicate_cycles(merged)

        return merged

    def _deduplicate_cycles(self, cycles: List[CycleInfo]) -> List[CycleInfo]:
        """周期去重：相近的周期合并，保留较强者"""
        if not cycles:
            return []

        cycles_sorted = sorted(cycles, key=lambda c: c.strength, reverse=True)
        result: List[CycleInfo] = []
        for c in cycles_sorted:
            if all(abs(c.length - r.length) > max(1, r.length // 10) for r in result):
                result.append(c)

        return result

    def _merge_changepoints(
        self,
        cps: List[ChangePoint],
        series: np.ndarray,
        min_distance: int = 5
    ) -> List[ChangePoint]:
        """合并相近的变点，并分类变点类型"""
        if not cps:
            return []

        # 按位置排序
        cps_sorted = sorted(cps, key=lambda c: c.position)
        merged: List[ChangePoint] = []

        for cp in cps_sorted:
            if merged and abs(cp.position - merged[-1].position) <= min_distance:
                # 合并：保留置信度较高者
                if cp.confidence > merged[-1].confidence:
                    merged[-1] = cp
            else:
                merged.append(cp)

        # 分类变点类型（均值/方差突变）
        n = len(series)
        for cp in merged:
            cp.change_type, cp.magnitude = self._classify_changepoint(series, cp.position, n)

        return merged

    def _classify_changepoint(
        self,
        series: np.ndarray,
        position: int,
        n: int
    ) -> Tuple[ChangePointType, float]:
        """分类变点类型

        通过比较变点前后窗口的均值和方差，
        判断变点属于均值突变还是方差突变。

        Returns:
            (变点类型, 变化幅度)
        """
        window = min(20, position, n - position)
        if window < 5:
            return ChangePointType.MEAN, 0.0

        before = series[position - window:position]
        after = series[position:position + window]

        mean_diff = abs(float(np.mean(after) - np.mean(before)))
        var_before = float(np.var(before)) + 1e-10
        var_after = float(np.var(after))
        var_ratio = var_after / var_before

        # 方差变化显著（比值超过 2 倍或低于 0.5 倍）则判为方差突变
        if var_ratio > 2.0 or var_ratio < 0.5:
            return ChangePointType.VARIANCE, float(np.log(var_ratio))
        else:
            return ChangePointType.MEAN, mean_diff

    def _analyze_cycle_change(
        self,
        early_cycles: List[CycleInfo],
        late_cycles: List[CycleInfo]
    ) -> Tuple[CycleChangeType, float, float, str]:
        """分析周期变化趋势

        比较前半段和后半段的周期检测结果，判断变化类型。

        Returns:
            (变化类型, 长度趋势, 强度趋势, 总结描述)
        """
        if not early_cycles and not late_cycles:
            return CycleChangeType.STABLE, 0.0, 0.0, "前后两段均无明显周期"

        if not early_cycles and late_cycles:
            return (CycleChangeType.EMERGING, 0.0,
                    late_cycles[0].strength,
                    f"新周期出现: 长度={late_cycles[0].length}")

        if early_cycles and not late_cycles:
            return (CycleChangeType.DISAPPEARING, 0.0,
                    -early_cycles[0].strength,
                    f"周期消失: 原长度={early_cycles[0].length}")

        # 两段都有周期，比较主导周期
        early_dominant = early_cycles[0]
        late_dominant = late_cycles[0]

        # 长度变化趋势
        length_diff = late_dominant.length - early_dominant.length
        length_trend = length_diff / max(early_dominant.length, 1)

        # 强度变化趋势
        strength_trend = late_dominant.strength - early_dominant.strength

        # 判断变化类型
        length_threshold = 0.15    # 长度变化 15% 视为显著
        strength_threshold = 0.1   # 强度变化 0.1 视为显著

        if abs(length_trend) < length_threshold and abs(strength_trend) < strength_threshold:
            change_type = CycleChangeType.STABLE
            summary = (f"周期稳定: 长度 {early_dominant.length}->{late_dominant.length}, "
                       f"强度 {early_dominant.strength:.3f}->{late_dominant.strength:.3f}")
        elif length_trend > length_threshold:
            change_type = CycleChangeType.EXTENDING
            summary = (f"周期延长: {early_dominant.length}->{late_dominant.length} "
                       f"(+{length_trend:.1%})")
        elif length_trend < -length_threshold:
            change_type = CycleChangeType.SHORTENING
            summary = (f"周期缩短: {early_dominant.length}->{late_dominant.length} "
                       f"({length_trend:.1%})")
        elif strength_trend < -strength_threshold:
            change_type = CycleChangeType.DISAPPEARING
            summary = (f"周期减弱: 强度 {early_dominant.strength:.3f}->{late_dominant.strength:.3f}")
        elif strength_trend > strength_threshold:
            change_type = CycleChangeType.EMERGING
            summary = (f"周期增强: 强度 {early_dominant.strength:.3f}->{late_dominant.strength:.3f}")
        else:
            change_type = CycleChangeType.SHIFTING
            summary = (f"周期变化: 长度 {early_dominant.length}->{late_dominant.length}, "
                       f"强度 {early_dominant.strength:.3f}->{late_dominant.strength:.3f}")

        return change_type, float(length_trend), float(strength_trend), summary


# 全局单例
_cycle_detector: Optional[CycleDetector] = None


def get_cycle_detector(**kwargs) -> CycleDetector:
    """获取全局周期检测器单例

    首次调用时创建实例，后续调用返回同一实例。

    Returns:
        CycleDetector 全局单例
    """
    global _cycle_detector
    if _cycle_detector is None:
        _cycle_detector = CycleDetector(**kwargs)
    return _cycle_detector
