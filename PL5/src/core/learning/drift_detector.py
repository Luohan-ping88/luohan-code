"""
数据分布漂移检测模块 V1.0

提供多维度的数据分布漂移检测能力：
1. PSI (Population Stability Index) - 特征分布稳定性
2. KS检验 (Kolmogorov-Smirnov Test) - 单变量分布差异
3. ADWIN (Adaptive Windowing) - 在线概念漂移检测
4. 多变量漂移检测 - 基于特征矩阵的整体分布变化

当检测到数据分布漂移时，自动触发学习模式调整。
"""

from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# 漂移检测历史持久化路径
_DRIFT_HISTORY_PATH = Path(__file__).parent.parent.parent.parent / "models" / "drift_history.json"


class DriftLevel(Enum):
    """漂移严重程度"""
    NONE = "none"
    LOW = "low"        # 轻微漂移，建议增量训练
    MEDIUM = "medium"  # 中等漂移，建议调整特征策略
    HIGH = "high"      # 严重漂移，建议全量重训练


class DriftType(Enum):
    """漂移类型"""
    COVARIATE = "covariate"      # 协变量漂移（特征分布变化）
    CONCEPT = "concept"          # 概念漂移（输入-输出关系变化）
    LABEL = "label"              # 标签分布漂移
    TEMPORAL = "temporal"        # 时序漂移（周期/趋势变化）


@dataclass
class DriftResult:
    """单个漂移检测结果"""
    feature_name: str
    drift_type: DriftType
    drift_level: DriftLevel
    psi_value: float = 0.0
    ks_statistic: float = 0.0
    ks_pvalue: float = 1.0
    is_drifted: bool = False
    detail: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'feature_name': self.feature_name,
            'drift_type': self.drift_type.value,
            'drift_level': self.drift_level.value,
            'psi_value': round(self.psi_value, 6),
            'ks_statistic': round(self.ks_statistic, 6),
            'ks_pvalue': round(self.ks_pvalue, 6),
            'is_drifted': self.is_drifted,
            'detail': self.detail,
            'timestamp': self.timestamp,
        }


@dataclass
class DriftSummary:
    """漂移检测汇总报告"""
    total_features: int = 0
    drifted_features: int = 0
    drift_ratio: float = 0.0
    overall_level: DriftLevel = DriftLevel.NONE
    drifted_feature_names: List[str] = field(default_factory=list)
    results: List[DriftResult] = field(default_factory=list)
    recommendation: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_features': self.total_features,
            'drifted_features': self.drifted_features,
            'drift_ratio': round(self.drift_ratio, 4),
            'overall_level': self.overall_level.value,
            'drifted_feature_names': self.drifted_feature_names,
            'results': [r.to_dict() for r in self.results],
            'recommendation': self.recommendation,
            'timestamp': self.timestamp,
        }


class PSICalculator:
    """PSI (Population Stability Index) 计算器

    PSI < 0.1: 无显著漂移
    0.1 <= PSI < 0.25: 轻微漂移
    PSI >= 0.25: 显著漂移
    """

    @staticmethod
    def calculate(
        reference: np.ndarray,
        current: np.ndarray,
        bins: int = 10,
        strategy: str = "quantile"
    ) -> float:
        """计算 PSI 值

        Args:
            reference: 参考分布数据（基准期）
            current: 当前分布数据
            bins: 分箱数量
            strategy: 分箱策略 ('quantile' 或 'uniform')

        Returns:
            PSI 值
        """
        reference = np.asarray(reference, dtype=float)
        current = np.asarray(current, dtype=float)

        # 过滤 NaN
        reference = reference[~np.isnan(reference)]
        current = current[~np.isnan(current)]

        if len(reference) < 2 or len(current) < 2:
            return 0.0

        # 计算分箱边界（基于参考分布）
        if strategy == "quantile":
            quantiles = np.linspace(0, 100, bins + 1)
            boundaries = np.percentile(reference, quantiles)
        else:
            bmin, bmax = reference.min(), reference.max()
            if bmax == bmin:
                return 0.0
            boundaries = np.linspace(bmin, bmax, bins + 1)

        # 确保边界唯一
        boundaries = np.unique(boundaries)
        if len(boundaries) < 3:
            return 0.0

        # 计算各箱占比
        ref_counts = np.histogram(reference, bins=boundaries)[0]
        cur_counts = np.histogram(current, bins=boundaries)[0]

        ref_pct = ref_counts / len(reference)
        cur_pct = cur_counts / len(current)

        # 避免 0 值（加入小常数）
        epsilon = 1e-6
        ref_pct = np.where(ref_pct == 0, epsilon, ref_pct)
        cur_pct = np.where(cur_pct == 0, epsilon, cur_pct)

        # PSI = sum((cur% - ref%) * ln(cur% / ref%))
        psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))

        return float(psi)


class KSTestDetector:
    """KS检验 (Kolmogorov-Smirnov) 分布差异检测器"""

    @staticmethod
    def detect(
        reference: np.ndarray,
        current: np.ndarray,
        alpha: float = 0.05
    ) -> Tuple[float, float, bool]:
        """执行 KS 检验

        Returns:
            (ks_statistic, p_value, is_drifted)
        """
        reference = np.asarray(reference, dtype=float)
        current = np.asarray(current, dtype=float)

        reference = reference[~np.isnan(reference)]
        current = current[~np.isnan(current)]

        if len(reference) < 2 or len(current) < 2:
            return 0.0, 1.0, False

        try:
            from scipy.stats import ks_2samp
            result = ks_2samp(reference, current)
            is_drifted = result.pvalue < alpha
            return float(result.statistic), float(result.pvalue), is_drifted
        except ImportError:
            # scipy 不可用时，使用简化版 KS 统计量
            return KSTestDetector._approximate_ks(reference, current, alpha)
        except Exception:
            return 0.0, 1.0, False

    @staticmethod
    def _approximate_ks(
        reference: np.ndarray,
        current: np.ndarray,
        alpha: float
    ) -> Tuple[float, float, bool]:
        """简化版 KS 统计量计算（无 scipy 依赖）"""
        ref_sorted = np.sort(reference)
        cur_sorted = np.sort(current)

        # 合并计算经验 CDF 差异
        all_values = np.sort(np.unique(np.concatenate([ref_sorted, cur_sorted])))
        ref_cdf = np.searchsorted(ref_sorted, all_values, side='right') / len(ref_sorted)
        cur_cdf = np.searchsorted(cur_sorted, all_values, side='right') / len(cur_sorted)

        ks_stat = float(np.max(np.abs(ref_cdf - cur_cdf)))

        # 近似 p 值
        n1, n2 = len(ref_sorted), len(cur_sorted)
        en = np.sqrt(n1 * n2 / (n1 + n2))
        p_value = 2.0 * np.exp(-2.0 * (en * ks_stat) ** 2)
        p_value = min(1.0, max(0.0, p_value))

        return ks_stat, p_value, p_value < alpha


class ADWINDetector:
    """ADWIN (Adaptive Windowing) 在线概念漂移检测器

    维护一个自适应窗口，当窗口内分布发生显著变化时发出漂移警报。
    适用于流式数据的实时漂移检测。
    """

    def __init__(self, delta: float = 0.002, min_window: int = 30, max_window: int = 5000):
        """
        Args:
            delta: 显著性水平阈值（越小越保守）
            min_window: 最小窗口长度
            max_window: 最大窗口长度
        """
        self.delta = delta
        self.min_window = min_window
        self.max_window = max_window
        self.window: deque = deque(maxlen=max_window)
        self.total_elements = 0
        self.num_drifts = 0
        self.drift_points: List[int] = []

    def add_element(self, value: float) -> bool:
        """添加新元素并检测漂移

        Returns:
            是否检测到漂移
        """
        self.window.append(value)
        self.total_elements += 1

        if len(self.window) < self.min_window * 2:
            return False

        # 在窗口中寻找最佳分割点
        return self._check_cut()

    def _check_cut(self) -> bool:
        """检查窗口中是否存在显著分割点"""
        window_array = np.array(self.window)
        n = len(window_array)

        if n < self.min_window * 2:
            return False

        # 遍历可能的分割点
        best_cut = -1
        best_diff = 0.0

        step = max(1, n // 50)  # 采样以加速
        for i in range(self.min_window, n - self.min_window, step):
            w0 = window_array[:i]
            w1 = window_array[i:]

            mean_diff = abs(w0.mean() - w1.mean())

            # ADWIN 方差修正
            n0, n1 = len(w0), len(w1)
            variance = (w0.var() * n0 + w1.var() * n1) / n
            epsilon_cut = np.sqrt(2.0 * variance * np.log(2.0 / self.delta) / n)

            if mean_diff > epsilon_cut and mean_diff > best_diff:
                best_diff = mean_diff
                best_cut = i

        if best_cut > 0:
            # 检测到漂移，缩小窗口
            self.num_drifts += 1
            self.drift_points.append(self.total_elements)
            # 保留分割点之后的数据
            new_window = list(window_array[best_cut:])
            self.window = deque(new_window, maxlen=self.max_window)
            logger.info(f"ADWIN检测到漂移: 位置={self.total_elements}, "
                       f"分割点={best_cut}, 均值差异={best_diff:.4f}")
            return True

        return False

    def reset(self):
        """重置检测器"""
        self.window.clear()
        self.total_elements = 0
        self.num_drifts = 0
        self.drift_points = []

    def get_stats(self) -> Dict[str, Any]:
        return {
            'window_size': len(self.window),
            'total_elements': self.total_elements,
            'num_drifts': self.num_drifts,
            'drift_points': self.drift_points[-10:],
            'current_mean': float(np.mean(self.window)) if self.window else 0.0,
        }


class DataDriftDetector:
    """数据分布漂移检测器主类

    整合 PSI、KS 检验和 ADWIN 三种检测方法，
    提供特征级和全局级的漂移检测能力。
    """

    def __init__(
        self,
        psi_threshold_low: float = 0.1,
        psi_threshold_high: float = 0.25,
        ks_alpha: float = 0.05,
        reference_ratio: float = 0.7,
        bins: int = 10,
        enable_adwin: bool = True,
        history_path: Optional[Path] = None
    ):
        """
        Args:
            psi_threshold_low: PSI 低阈值（轻微漂移）
            psi_threshold_high: PSI 高阈值（显著漂移）
            ks_alpha: KS 检验显著性水平
            reference_ratio: 参考集占比
            bins: PSI 分箱数
            enable_adwin: 是否启用 ADWIN 在线检测
            history_path: 漂移历史持久化路径
        """
        self.psi_threshold_low = psi_threshold_low
        self.psi_threshold_high = psi_threshold_high
        self.ks_alpha = ks_alpha
        self.reference_ratio = reference_ratio
        self.bins = bins
        self.enable_adwin = enable_adwin
        self.history_path = history_path or _DRIFT_HISTORY_PATH

        # 各特征的 ADWIN 检测器（按需创建）
        self._adwin_detectors: Dict[str, ADWINDetector] = {}

        # 漂移历史
        self.drift_history: List[Dict] = []
        self._load_history()

        # 参考分布缓存
        self._reference_distributions: Optional[Dict[str, np.ndarray]] = None

        logger.info("数据漂移检测器初始化完成 "
                    f"(PSI阈值: {psi_threshold_low}/{psi_threshold_high}, "
                    f"KS alpha: {ks_alpha}, ADWIN: {enable_adwin})")

    def set_reference(self, data: np.ndarray, feature_names: List[str]):
        """设置参考分布（基准数据）

        Args:
            data: 参考数据矩阵 (n_samples, n_features)
            feature_names: 特征名列表
        """
        self._reference_distributions = {}
        for i, name in enumerate(feature_names):
            self._reference_distributions[name] = data[:, i].copy()

        # 重置 ADWIN 检测器
        if self.enable_adwin:
            self._adwin_detectors = {}
            for name in feature_names:
                self._adwin_detectors[name] = ADWINDetector()

        logger.info(f"参考分布已设置: {len(feature_names)} 个特征")

    def detect_drift(
        self,
        current_data: np.ndarray,
        feature_names: List[str],
        drift_type: DriftType = DriftType.COVARIATE
    ) -> DriftSummary:
        """检测数据分布漂移

        Args:
            current_data: 当前数据矩阵 (n_samples, n_features)
            feature_names: 特征名列表
            drift_type: 漂移类型

        Returns:
            漂移检测汇总报告
        """
        if self._reference_distributions is None:
            # 无参考分布时，从当前数据中划分参考集和当前集
            return self._detect_without_reference(current_data, feature_names, drift_type)

        results: List[DriftResult] = []
        drifted_count = 0

        for i, name in enumerate(feature_names):
            if name not in self._reference_distributions:
                continue

            ref_data = self._reference_distributions[name]
            cur_data = current_data[:, i]

            # PSI 检测
            psi_value = PSICalculator.calculate(ref_data, cur_data, bins=self.bins)

            # KS 检验
            ks_stat, ks_pval, ks_drifted = KSTestDetector.detect(
                ref_data, cur_data, alpha=self.ks_alpha
            )

            # ADWIN 在线检测
            adwin_drifted = False
            if self.enable_adwin and name in self._adwin_detectors:
                detector = self._adwin_detectors[name]
                for val in cur_data:
                    if detector.add_element(float(val)):
                        adwin_drifted = True
                        break

            # 综合判定漂移级别
            is_drifted = psi_value >= self.psi_threshold_low or ks_drifted or adwin_drifted
            if psi_value >= self.psi_threshold_high:
                level = DriftLevel.HIGH
            elif psi_value >= self.psi_threshold_low or ks_drifted:
                level = DriftLevel.MEDIUM
            elif adwin_drifted:
                level = DriftLevel.LOW
            else:
                level = DriftLevel.NONE

            if is_drifted:
                drifted_count += 1

            detail_parts = []
            if psi_value >= self.psi_threshold_low:
                detail_parts.append(f"PSI={psi_value:.4f}")
            if ks_drifted:
                detail_parts.append(f"KS p={ks_pval:.4e}")
            if adwin_drifted:
                detail_parts.append("ADWIN drift detected")

            result = DriftResult(
                feature_name=name,
                drift_type=drift_type,
                drift_level=level,
                psi_value=psi_value,
                ks_statistic=ks_stat,
                ks_pvalue=ks_pval,
                is_drifted=is_drifted,
                detail="; ".join(detail_parts) if detail_parts else "no drift",
            )
            results.append(result)

        # 计算整体漂移级别
        total = len(results)
        drift_ratio = drifted_count / total if total > 0 else 0.0

        if drift_ratio >= 0.3 or any(r.drift_level == DriftLevel.HIGH for r in results):
            overall_level = DriftLevel.HIGH
        elif drift_ratio >= 0.15 or any(r.drift_level == DriftLevel.MEDIUM for r in results):
            overall_level = DriftLevel.MEDIUM
        elif drift_ratio >= 0.05 or any(r.drift_level == DriftLevel.LOW for r in results):
            overall_level = DriftLevel.LOW
        else:
            overall_level = DriftLevel.NONE

        # 生成建议
        recommendation = self._generate_recommendation(overall_level, drift_ratio, drifted_count, total)

        summary = DriftSummary(
            total_features=total,
            drifted_features=drifted_count,
            drift_ratio=drift_ratio,
            overall_level=overall_level,
            drifted_feature_names=[r.feature_name for r in results if r.is_drifted],
            results=results,
            recommendation=recommendation,
        )

        # 持久化
        self._save_drift_record(summary)

        logger.info(f"漂移检测完成: {drifted_count}/{total} 特征漂移 "
                    f"({drift_ratio:.1%}), 整体级别: {overall_level.value}")

        return summary

    def _detect_without_reference(
        self,
        data: np.ndarray,
        feature_names: List[str],
        drift_type: DriftType
    ) -> DriftSummary:
        """无参考分布时的漂移检测（时间窗口对比法）"""
        n_samples = data.shape[0]
        split_idx = int(n_samples * self.reference_ratio)

        if split_idx < 10 or n_samples - split_idx < 10:
            return DriftSummary(
                total_features=len(feature_names),
                recommendation="数据量不足，无法进行漂移检测"
            )

        ref_data = data[:split_idx]
        cur_data = data[split_idx:]

        # 临时设置参考分布后递归调用
        self.set_reference(ref_data, feature_names)
        return self.detect_drift(cur_data, feature_names, drift_type)

    def _generate_recommendation(
        self,
        level: DriftLevel,
        ratio: float,
        drifted: int,
        total: int
    ) -> str:
        """根据漂移级别生成学习模式调整建议"""
        if level == DriftLevel.NONE:
            return "数据分布稳定，维持当前学习模式"
        elif level == DriftLevel.LOW:
            return (f"检测到轻微漂移({drifted}/{total}特征)，"
                    "建议执行增量训练以适应分布变化")
        elif level == DriftLevel.MEDIUM:
            return (f"检测到中等漂移({drifted}/{total}特征, {ratio:.1%})，"
                    "建议调整特征选择策略并执行中等强度训练")
        else:
            return (f"检测到严重漂移({drifted}/{total}特征, {ratio:.1%})，"
                    "建议立即执行全量深度重训练，并重新评估特征工程方案")

    def _load_history(self):
        """加载漂移检测历史"""
        try:
            if self.history_path.exists():
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    self.drift_history = json.load(f)
        except Exception as e:
            logger.warning(f"加载漂移历史失败: {e}")
            self.drift_history = []

    def _save_drift_record(self, summary: DriftSummary):
        """保存漂移检测记录"""
        record = summary.to_dict()
        self.drift_history.append(record)
        # 保留最近 100 条
        if len(self.drift_history) > 100:
            self.drift_history = self.drift_history[-100:]

        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self.drift_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存漂移历史失败: {e}")

    def get_drift_trend(self, window: int = 10) -> Dict[str, Any]:
        """获取漂移趋势分析

        Args:
            window: 分析窗口（最近 N 次检测）

        Returns:
            趋势分析结果
        """
        recent = self.drift_history[-window:]
        if not recent:
            return {'trend': 'no_data', 'message': '无漂移检测历史'}

        drift_ratios = [r.get('drift_ratio', 0) for r in recent]
        levels = [r.get('overall_level', 'none') for r in recent]

        # 趋势判断
        if len(drift_ratios) >= 3:
            first_half = np.mean(drift_ratios[:len(drift_ratios)//2])
            second_half = np.mean(drift_ratios[len(drift_ratios)//2:])
            if second_half > first_half * 1.5:
                trend = "increasing"
                message = "漂移趋势加剧，需要关注数据质量"
            elif second_half < first_half * 0.5:
                trend = "decreasing"
                message = "漂移趋势缓解，数据趋于稳定"
            else:
                trend = "stable"
                message = "漂移趋势保持稳定"
        else:
            trend = "insufficient"
            message = "历史数据不足，无法判断趋势"

        return {
            'trend': trend,
            'message': message,
            'recent_ratios': drift_ratios,
            'recent_levels': levels,
            'avg_ratio': float(np.mean(drift_ratios)) if drift_ratios else 0.0,
            'max_ratio': float(np.max(drift_ratios)) if drift_ratios else 0.0,
        }


# 全局单例
_drift_detector: Optional[DataDriftDetector] = None


def get_drift_detector(**kwargs) -> DataDriftDetector:
    """获取全局漂移检测器单例"""
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = DataDriftDetector(**kwargs)
    return _drift_detector
