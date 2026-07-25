"""
高级模式识别模块 V1.0

针对排列五 (PL5) 数据，提供多维度的模式识别能力：
1. 数字频率模式识别 - 分析0-9各数字在各位的出现频率，识别热号/冷号/温号
2. 连号模式识别 - 检测连续号码出现的模式和规律（期内连号 + 时序连号）
3. 重复模式识别 - 检测历史重复模式和周期性重复
4. 位置关联模式 - 分析各位之间的关联性（万位与千位的关系等）
5. 趋势模式识别 - 识别上升/下降/震荡趋势
6. 异常模式识别 - 检测偏离正常统计规律的异常模式

模块独立运行，仅依赖标准库与 numpy。data 参数支持 pandas DataFrame 或 dict，
当 pandas 不可用时自动回退到 dict 处理路径。
"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# 默认位置定义（万/千/百/十/个）
DEFAULT_POSITIONS: Tuple[str, ...] = ('wan', 'qian', 'bai', 'shi', 'ge')

# 位置名称中文标签
POSITION_LABELS: Dict[str, str] = {
    'wan': '万位',
    'qian': '千位',
    'bai': '百位',
    'shi': '十位',
    'ge': '个位',
}

# 数字范围（排列五每位为 0-9）
DIGIT_RANGE: Tuple[int, int] = (0, 9)
ALL_DIGITS: List[int] = list(range(DIGIT_RANGE[0], DIGIT_RANGE[1] + 1))


class PatternType(Enum):
    """模式类型枚举"""
    FREQUENCY = "frequency"                          # 数字频率模式
    CONSECUTIVE = "consecutive"                      # 连号模式
    REPEAT = "repeat"                                # 重复模式
    POSITION_CORRELATION = "position_correlation"    # 位置关联模式
    TREND = "trend"                                  # 趋势模式
    ANOMALY = "anomaly"                              # 异常模式


class NumberCategory(Enum):
    """号码分类（热/温/冷）"""
    HOT = "hot"    # 热号：出现频率显著高于均值
    WARM = "warm"  # 温号：出现频率接近均值
    COLD = "cold"  # 冷号：出现频率显著低于均值


class TrendDirection(Enum):
    """趋势方向"""
    UP = "up"                      # 上升
    DOWN = "down"                  # 下降
    STABLE = "stable"              # 稳定
    OSCILLATING = "oscillating"    # 震荡


class AnomalyLevel(Enum):
    """异常级别"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class FrequencyPattern:
    """数字频率模式识别结果"""
    position: str                                              # 位置名
    total_samples: int = 0                                     # 样本总数
    digit_counts: Dict[int, int] = field(default_factory=dict)         # 各数字出现次数
    digit_frequencies: Dict[int, float] = field(default_factory=dict)  # 各数字出现频率
    hot_numbers: List[int] = field(default_factory=list)              # 热号
    warm_numbers: List[int] = field(default_factory=list)             # 温号
    cold_numbers: List[int] = field(default_factory=list)             # 冷号
    expected_frequency: float = 0.0                            # 期望频率（均匀分布下为 0.1）
    chi_square: float = 0.0                                    # 卡方统计量
    is_balanced: bool = True                                   # 分布是否均衡

    def to_dict(self) -> Dict[str, Any]:
        return {
            'position': self.position,
            'total_samples': self.total_samples,
            'digit_counts': {int(k): int(v) for k, v in self.digit_counts.items()},
            'digit_frequencies': {int(k): round(float(v), 6) for k, v in self.digit_frequencies.items()},
            'hot_numbers': list(self.hot_numbers),
            'warm_numbers': list(self.warm_numbers),
            'cold_numbers': list(self.cold_numbers),
            'expected_frequency': round(self.expected_frequency, 6),
            'chi_square': round(self.chi_square, 6),
            'is_balanced': self.is_balanced,
        }


@dataclass
class ConsecutivePattern:
    """连号模式识别结果"""
    position_pair: str                                          # 关联位置描述
    total_records: int = 0
    consecutive_count: int = 0                                  # 出现连号的总次数
    consecutive_ratio: float = 0.0                              # 连号出现比例
    ascending_sequences: List[List[int]] = field(default_factory=list)   # 上升连号样本
    descending_sequences: List[List[int]] = field(default_factory=list)  # 下降连号样本
    longest_run: int = 0                                        # 最长连续递增/递减长度
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'position_pair': self.position_pair,
            'total_records': self.total_records,
            'consecutive_count': self.consecutive_count,
            'consecutive_ratio': round(self.consecutive_ratio, 6),
            'ascending_sequences': [list(s) for s in self.ascending_sequences],
            'descending_sequences': [list(s) for s in self.descending_sequences],
            'longest_run': self.longest_run,
            'detail': self.detail,
        }


@dataclass
class RepeatPattern:
    """重复模式识别结果"""
    exact_repeats: Dict[str, int] = field(default_factory=dict)         # 完全重复组合 -> 出现次数
    near_repeats: List[Dict[str, Any]] = field(default_factory=list)    # 近似重复（差1位）
    periodic_patterns: List[Dict[str, Any]] = field(default_factory=list)  # 周期性重复
    most_common_combination: Optional[str] = None              # 出现次数最多的组合
    max_repeat_count: int = 0                                  # 最大重复次数
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exact_repeats': dict(self.exact_repeats),
            'near_repeats': list(self.near_repeats),
            'periodic_patterns': list(self.periodic_patterns),
            'most_common_combination': self.most_common_combination,
            'max_repeat_count': self.max_repeat_count,
            'detail': self.detail,
        }


@dataclass
class PositionCorrelation:
    """位置关联模式识别结果"""
    position_a: str
    position_b: str
    correlation: float = 0.0                                   # 皮尔逊相关系数
    conditional_top: Dict[str, List[Tuple[int, float]]] = field(default_factory=dict)  # 条件概率 top
    mutual_info: float = 0.0                                   # 互信息
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'position_a': self.position_a,
            'position_b': self.position_b,
            'correlation': round(self.correlation, 6),
            'conditional_top': {
                k: [[int(d), round(float(p), 6)] for d, p in v]
                for k, v in self.conditional_top.items()
            },
            'mutual_info': round(self.mutual_info, 6),
            'detail': self.detail,
        }


@dataclass
class TrendPattern:
    """趋势模式识别结果"""
    position: str
    direction: TrendDirection = TrendDirection.STABLE
    slope: float = 0.0                          # 线性回归斜率
    mean_recent: float = 0.0                    # 近期均值
    mean_overall: float = 0.0                   # 整体均值
    volatility: float = 0.0                     # 波动率（标准差）
    momentum: float = 0.0                       # 动量（近期均值 - 整体均值）
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'position': self.position,
            'direction': self.direction.value,
            'slope': round(self.slope, 6),
            'mean_recent': round(self.mean_recent, 6),
            'mean_overall': round(self.mean_overall, 6),
            'volatility': round(self.volatility, 6),
            'momentum': round(self.momentum, 6),
            'detail': self.detail,
        }


@dataclass
class AnomalyPattern:
    """异常模式识别结果"""
    anomaly_type: str                           # 异常类型
    level: AnomalyLevel = AnomalyLevel.NONE
    position: Optional[str] = None
    value: Optional[float] = None
    expected: Optional[float] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'anomaly_type': self.anomaly_type,
            'level': self.level.value,
            'position': self.position,
            'value': None if self.value is None else round(float(self.value), 6),
            'expected': None if self.expected is None else round(float(self.expected), 6),
            'description': self.description,
        }


@dataclass
class PatternAnalysisResult:
    """综合模式分析结果"""
    timestamp: str = ""
    total_records: int = 0
    positions_analyzed: List[str] = field(default_factory=list)
    frequency_patterns: List[FrequencyPattern] = field(default_factory=list)
    consecutive_patterns: List[ConsecutivePattern] = field(default_factory=list)
    repeat_patterns: RepeatPattern = field(default_factory=RepeatPattern)
    position_correlations: List[PositionCorrelation] = field(default_factory=list)
    trend_patterns: List[TrendPattern] = field(default_factory=list)
    anomaly_patterns: List[AnomalyPattern] = field(default_factory=list)
    summary: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'total_records': self.total_records,
            'positions_analyzed': list(self.positions_analyzed),
            'frequency_patterns': [p.to_dict() for p in self.frequency_patterns],
            'consecutive_patterns': [p.to_dict() for p in self.consecutive_patterns],
            'repeat_patterns': self.repeat_patterns.to_dict(),
            'position_correlations': [p.to_dict() for p in self.position_correlations],
            'trend_patterns': [p.to_dict() for p in self.trend_patterns],
            'anomaly_patterns': [p.to_dict() for p in self.anomaly_patterns],
            'summary': self.summary,
        }


class PatternRecognizer:
    """高级模式识别器主类

    整合数字频率、连号、重复、位置关联、趋势、异常 6 类模式识别能力，
    提供 analyze_patterns 入口方法返回综合分析结果。
    """

    def __init__(
        self,
        hot_threshold: float = 1.2,
        cold_threshold: float = 0.8,
        chi_square_alpha: float = 0.05,
        recent_window: int = 30,
        min_samples: int = 10,
        anomaly_z_threshold: float = 2.0,
        long_gap_quantile: float = 0.95,
    ):
        """
        Args:
            hot_threshold: 热号频率倍数阈值（相对期望频率）
            cold_threshold: 冷号频率倍数阈值（相对期望频率）
            chi_square_alpha: 卡方检验显著性水平
            recent_window: 近期窗口大小（用于趋势/突变分析）
            min_samples: 最小样本数（低于此值将记录警告）
            anomaly_z_threshold: 异常 Z 分数阈值
            long_gap_quantile: 长间隔分位数阈值
        """
        self.hot_threshold = hot_threshold
        self.cold_threshold = cold_threshold
        self.chi_square_alpha = chi_square_alpha
        self.recent_window = recent_window
        self.min_samples = min_samples
        self.anomaly_z_threshold = anomaly_z_threshold
        self.long_gap_quantile = long_gap_quantile

        # 卡方临界值表（自由度 9，对应 0-9 共 10 个数字）
        self._chi2_critical: Dict[float, float] = {
            0.10: 14.684,
            0.05: 16.919,
            0.01: 21.666,
            0.001: 27.877,
        }

        logger.info(
            "模式识别器初始化完成 "
            f"(热号阈值: {hot_threshold}, 冷号阈值: {cold_threshold}, "
            f"近期窗口: {recent_window}, 卡方 alpha: {chi_square_alpha})"
        )

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def analyze_patterns(
        self,
        data: Union["pd.DataFrame", Dict[str, Any]],  # noqa: F821
        positions: Optional[List[str]] = None,
    ) -> PatternAnalysisResult:
        """执行综合模式分析

        Args:
            data: pandas DataFrame 或 dict，包含各位位置列（0-9 整数）
            positions: 待分析的位置列表，默认 ['wan','qian','bai','shi','ge']

        Returns:
            PatternAnalysisResult 综合分析结果
        """
        if positions is None:
            positions = list(DEFAULT_POSITIONS)

        # 提取各位置数据
        position_data = self._extract_position_data(data, positions)
        if not position_data:
            logger.warning("未能提取任何位置数据，返回空结果")
            return PatternAnalysisResult(positions_analyzed=list(positions))

        total_records = len(next(iter(position_data.values())))
        if total_records < self.min_samples:
            logger.warning(
                f"样本数不足 ({total_records} < {self.min_samples})，分析结果可靠性较低"
            )

        logger.info(f"开始模式分析: {total_records} 条记录, 位置 {list(position_data.keys())}")

        result = PatternAnalysisResult(
            total_records=total_records,
            positions_analyzed=list(position_data.keys()),
        )

        # 逐项分析，单点异常不影响整体流程
        try:
            result.frequency_patterns = self._analyze_frequency_patterns(position_data)
        except Exception as e:
            logger.error(f"数字频率模式分析失败: {e}", exc_info=True)

        try:
            result.consecutive_patterns = self._analyze_consecutive_patterns(position_data)
        except Exception as e:
            logger.error(f"连号模式分析失败: {e}", exc_info=True)

        try:
            result.repeat_patterns = self._analyze_repeat_patterns(position_data)
        except Exception as e:
            logger.error(f"重复模式分析失败: {e}", exc_info=True)

        try:
            result.position_correlations = self._analyze_position_correlations(position_data)
        except Exception as e:
            logger.error(f"位置关联模式分析失败: {e}", exc_info=True)

        try:
            result.trend_patterns = self._analyze_trend_patterns(position_data)
        except Exception as e:
            logger.error(f"趋势模式分析失败: {e}", exc_info=True)

        try:
            result.anomaly_patterns = self._analyze_anomaly_patterns(position_data)
        except Exception as e:
            logger.error(f"异常模式分析失败: {e}", exc_info=True)

        result.summary = self._generate_summary(result)
        logger.info(
            f"模式分析完成: 频率模式 {len(result.frequency_patterns)} 个, "
            f"连号模式 {len(result.consecutive_patterns)} 个, "
            f"位置关联 {len(result.position_correlations)} 个, "
            f"趋势模式 {len(result.trend_patterns)} 个, "
            f"异常 {len(result.anomaly_patterns)} 个"
        )
        return result

    # ------------------------------------------------------------------
    # 数据提取
    # ------------------------------------------------------------------

    def _extract_position_data(
        self,
        data: Union["pd.DataFrame", Dict[str, Any]],  # noqa: F821
        positions: List[str],
    ) -> Dict[str, np.ndarray]:
        """从输入数据中提取各位置的整数序列

        支持 pandas DataFrame 或 dict 输入。所有位置按行对齐，
        丢弃任何位置存在缺失值或越界的行。
        """
        raw: Dict[str, List[float]] = {}

        # 尝试以 pandas DataFrame 方式访问
        is_dataframe = False
        try:
            import pandas as pd  # type: ignore
            if isinstance(data, pd.DataFrame):
                is_dataframe = True
        except ImportError:
            pass

        if is_dataframe:
            for pos in positions:
                if pos not in data.columns:
                    logger.warning(f"DataFrame 中缺少位置列: {pos}")
                    continue
                col = data[pos].values
                raw[pos] = [float(v) for v in col]
        elif isinstance(data, dict):
            for pos in positions:
                if pos not in data:
                    logger.warning(f"dict 中缺少位置键: {pos}")
                    continue
                col = data[pos]
                raw[pos] = [float(v) for v in col]
        else:
            logger.error(f"不支持的数据类型: {type(data)}")
            return {}

        if not raw:
            return {}

        # 确定公共长度（按最短截断，保证位置间对齐）
        min_len = min(len(v) for v in raw.values())

        # 对齐并过滤缺失/越界值（所有位置必须同时有效）
        result: Dict[str, List[int]] = {pos: [] for pos in raw}
        for i in range(min_len):
            row_vals = [raw[pos][i] for pos in raw]
            if any(math.isnan(v) for v in row_vals):
                continue
            if any(v < DIGIT_RANGE[0] or v > DIGIT_RANGE[1] for v in row_vals):
                logger.warning(f"第 {i} 行数据超出 0-9 范围, 跳过: {row_vals}")
                continue
            for pos in raw:
                result[pos].append(int(raw[pos][i]))

        return {pos: np.array(arr, dtype=int) for pos, arr in result.items()}

    # ------------------------------------------------------------------
    # 1. 数字频率模式识别
    # ------------------------------------------------------------------

    def _analyze_frequency_patterns(
        self,
        position_data: Dict[str, np.ndarray],
    ) -> List[FrequencyPattern]:
        """数字频率模式识别

        分析每位 0-9 各数字的出现频率，识别热号/冷号/温号，
        并通过卡方检验判断分布是否均衡。
        """
        patterns: List[FrequencyPattern] = []
        expected = 1.0 / len(ALL_DIGITS)  # 均匀分布下的期望频率 = 0.1

        for pos, arr in position_data.items():
            n = len(arr)
            if n == 0:
                continue

            # 各数字频次
            counts = {d: int(np.sum(arr == d)) for d in ALL_DIGITS}
            freqs = {d: counts[d] / n for d in ALL_DIGITS}

            # 识别热号/温号/冷号
            hot, warm, cold = [], [], []
            for d in ALL_DIGITS:
                ratio = freqs[d] / expected if expected > 0 else 0.0
                if ratio >= self.hot_threshold:
                    hot.append(d)
                elif ratio <= self.cold_threshold:
                    cold.append(d)
                else:
                    warm.append(d)

            # 卡方统计量（期望频数 = n / 10）
            expected_count = n / len(ALL_DIGITS)
            if expected_count > 0:
                chi2 = float(sum(
                    (counts[d] - expected_count) ** 2 / expected_count
                    for d in ALL_DIGITS
                ))
            else:
                chi2 = 0.0

            # 判断是否均衡
            critical = self._chi2_critical.get(self.chi_square_alpha, 16.919)
            is_balanced = chi2 <= critical

            patterns.append(FrequencyPattern(
                position=pos,
                total_samples=n,
                digit_counts=counts,
                digit_frequencies=freqs,
                hot_numbers=sorted(hot),
                warm_numbers=sorted(warm),
                cold_numbers=sorted(cold),
                expected_frequency=expected,
                chi_square=chi2,
                is_balanced=is_balanced,
            ))

            logger.debug(
                f"[{POSITION_LABELS.get(pos, pos)}] "
                f"热号={sorted(hot)}, 温号={sorted(warm)}, 冷号={sorted(cold)}, "
                f"卡方={chi2:.2f}({'均衡' if is_balanced else '不均衡'})"
            )

        return patterns

    # ------------------------------------------------------------------
    # 2. 连号模式识别
    # ------------------------------------------------------------------

    def _analyze_consecutive_patterns(
        self,
        position_data: Dict[str, np.ndarray],
    ) -> List[ConsecutivePattern]:
        """连号模式识别

        检测每期号码中的连号（如 1-2-3）以及时序上的连续递增/递减。
        """
        patterns: List[ConsecutivePattern] = []
        positions = list(position_data.keys())

        if len(positions) < 2:
            return patterns

        n = len(next(iter(position_data.values())))
        if n == 0:
            return patterns

        # 1) 期内连号：每期记录中相邻位置之间是否构成连号
        consecutive_count = 0
        asc_seqs: List[List[int]] = []
        desc_seqs: List[List[int]] = []
        longest_run = 0

        for i in range(n):
            digits = [int(position_data[p][i]) for p in positions]
            has_consec = False

            # 提取当前期的上升/下降连号 run
            cur_asc = [digits[0]]
            cur_desc = [digits[0]]
            for j in range(1, len(digits)):
                diff = digits[j] - digits[j - 1]
                if diff == 1:
                    cur_asc.append(digits[j])
                    has_consec = True
                else:
                    if len(cur_asc) >= 2:
                        asc_seqs.append(list(cur_asc))
                    cur_asc = [digits[j]]

                if diff == -1:
                    cur_desc.append(digits[j])
                    has_consec = True
                else:
                    if len(cur_desc) >= 2:
                        desc_seqs.append(list(cur_desc))
                    cur_desc = [digits[j]]

            if len(cur_asc) >= 2:
                asc_seqs.append(list(cur_asc))
            if len(cur_desc) >= 2:
                desc_seqs.append(list(cur_desc))

            # 当前期内最长 run
            run_asc, run_desc = 1, 1
            for j in range(1, len(digits)):
                diff = digits[j] - digits[j - 1]
                if diff == 1:
                    run_asc += 1
                    run_desc = 1
                elif diff == -1:
                    run_desc += 1
                    run_asc = 1
                else:
                    run_asc, run_desc = 1, 1
                longest_run = max(longest_run, run_asc, run_desc)

            if has_consec:
                consecutive_count += 1

        ratio = consecutive_count / n if n > 0 else 0.0

        # 仅保留前若干样本以便阅读
        asc_sample = asc_seqs[:20]
        desc_sample = desc_seqs[:20]

        detail = (
            f"期内连号出现 {consecutive_count}/{n} 期 ({ratio:.1%}), "
            f"最长连号 run={longest_run}"
        )

        patterns.append(ConsecutivePattern(
            position_pair="-".join(positions),
            total_records=n,
            consecutive_count=consecutive_count,
            consecutive_ratio=ratio,
            ascending_sequences=asc_sample,
            descending_sequences=desc_sample,
            longest_run=longest_run,
            detail=detail,
        ))

        # 2) 时序连号：每个位置在时间维度上的连续递增/递减
        for pos, arr in position_data.items():
            if len(arr) < 3:
                continue
            longest_asc, longest_desc = 1, 1
            cur_asc, cur_desc = 1, 1
            for i in range(1, len(arr)):
                diff = int(arr[i]) - int(arr[i - 1])
                if diff == 1:
                    cur_asc += 1
                    cur_desc = 1
                elif diff == -1:
                    cur_desc += 1
                    cur_asc = 1
                else:
                    cur_asc, cur_desc = 1, 1
                longest_asc = max(longest_asc, cur_asc)
                longest_desc = max(longest_desc, cur_desc)

            max_ts = max(longest_asc, longest_desc)
            if max_ts >= 3:
                direction = "递增" if longest_asc >= longest_desc else "递减"
                patterns.append(ConsecutivePattern(
                    position_pair=f"{pos}(时序)",
                    total_records=len(arr),
                    consecutive_count=max_ts,
                    consecutive_ratio=max_ts / len(arr) if len(arr) > 0 else 0.0,
                    ascending_sequences=[],
                    descending_sequences=[],
                    longest_run=max_ts,
                    detail=(
                        f"{POSITION_LABELS.get(pos, pos)} 时序最长连续{direction} "
                        f"run={max_ts}"
                    ),
                ))

        return patterns

    # ------------------------------------------------------------------
    # 3. 重复模式识别
    # ------------------------------------------------------------------

    def _analyze_repeat_patterns(
        self,
        position_data: Dict[str, np.ndarray],
    ) -> RepeatPattern:
        """重复模式识别

        检测完全重复、近似重复（差1位）和周期性重复。
        """
        positions = list(position_data.keys())
        n = len(next(iter(position_data.values())))

        if n == 0:
            return RepeatPattern(detail="无数据")

        # 构造每期组合字符串
        combos: List[str] = []
        for i in range(n):
            combo = "".join(str(int(position_data[p][i])) for p in positions)
            combos.append(combo)

        # 1) 完全重复
        combo_counter = Counter(combos)
        exact_repeats = {k: v for k, v in combo_counter.items() if v > 1}
        most_common_combo: Optional[str] = None
        most_common_count = 0
        if combo_counter:
            most_common_combo, most_common_count = combo_counter.most_common(1)[0]

        # 2) 近似重复（差1位）- O(n^2) 比对，限制规模保护性能
        near_repeats: List[Dict[str, Any]] = []
        max_pairs = min(n, 500)
        for i in range(max_pairs):
            ci = combos[i]
            for j in range(i + 1, max_pairs):
                cj = combos[j]
                diff = sum(1 for a, b in zip(ci, cj) if a != b)
                if diff == 1:
                    near_repeats.append({
                        'combo_a': ci,
                        'combo_b': cj,
                        'index_a': i,
                        'index_b': j,
                    })
                    if len(near_repeats) >= 50:
                        break
            if len(near_repeats) >= 50:
                break

        # 3) 周期性重复 - 检查相同组合在不同周期出现
        periodic_patterns: List[Dict[str, Any]] = []
        combo_indices: Dict[str, List[int]] = defaultdict(list)
        for idx, c in enumerate(combos):
            combo_indices[c].append(idx)

        for combo, indices in combo_indices.items():
            if len(indices) < 3:
                continue
            # 计算间隔
            gaps = [indices[k + 1] - indices[k] for k in range(len(indices) - 1)]
            if len(gaps) < 2:
                continue
            gap_mean = float(np.mean(gaps))
            gap_std = float(np.std(gaps))
            # 间隔标准差较小 => 具备周期性
            if gap_std <= max(1.0, gap_mean * 0.2):
                periodic_patterns.append({
                    'combination': combo,
                    'indices': indices,
                    'gaps': gaps,
                    'mean_gap': round(gap_mean, 2),
                    'gap_std': round(gap_std, 2),
                })

        detail = (
            f"完全重复组合 {len(exact_repeats)} 种, "
            f"近似重复 {len(near_repeats)} 对, "
            f"周期性模式 {len(periodic_patterns)} 种"
        )

        return RepeatPattern(
            exact_repeats=exact_repeats,
            near_repeats=near_repeats,
            periodic_patterns=periodic_patterns,
            most_common_combination=most_common_combo,
            max_repeat_count=most_common_count,
            detail=detail,
        )

    # ------------------------------------------------------------------
    # 4. 位置关联模式识别
    # ------------------------------------------------------------------

    def _analyze_position_correlations(
        self,
        position_data: Dict[str, np.ndarray],
    ) -> List[PositionCorrelation]:
        """位置关联模式识别

        计算各位置之间的皮尔逊相关系数、条件概率和互信息。
        """
        correlations: List[PositionCorrelation] = []
        positions = list(position_data.keys())

        if len(positions) < 2:
            return correlations

        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                pa, pb = positions[i], positions[j]
                arr_a = position_data[pa].astype(float)
                arr_b = position_data[pb].astype(float)
                n = min(len(arr_a), len(arr_b))
                if n < self.min_samples:
                    continue

                # 皮尔逊相关
                if np.std(arr_a) > 0 and np.std(arr_b) > 0:
                    corr = float(np.corrcoef(arr_a, arr_b)[0, 1])
                    if math.isnan(corr):
                        corr = 0.0
                else:
                    corr = 0.0

                # 条件概率 P(b=d | a=x) 的 top 3
                conditional_top: Dict[str, List[Tuple[int, float]]] = {}
                for x in ALL_DIGITS:
                    mask = arr_a == x
                    if not np.any(mask):
                        continue
                    b_given_a = arr_b[mask]
                    if len(b_given_a) == 0:
                        continue
                    cnt = Counter(b_given_a.astype(int).tolist())
                    total = sum(cnt.values())
                    top = [(d, cnt.get(d, 0) / total) for d in ALL_DIGITS if cnt.get(d, 0) > 0]
                    top.sort(key=lambda t: -t[1])
                    conditional_top[str(x)] = top[:3]

                # 互信息
                mi = self._mutual_information(arr_a.astype(int), arr_b.astype(int))

                detail = (
                    f"{POSITION_LABELS.get(pa, pa)} vs {POSITION_LABELS.get(pb, pb)}: "
                    f"相关={corr:.3f}, 互信息={mi:.4f}"
                )

                correlations.append(PositionCorrelation(
                    position_a=pa,
                    position_b=pb,
                    correlation=corr,
                    conditional_top=conditional_top,
                    mutual_info=mi,
                    detail=detail,
                ))

        return correlations

    def _mutual_information(self, x: np.ndarray, y: np.ndarray) -> float:
        """计算两个离散变量的互信息（单位：bit）"""
        n = len(x)
        if n == 0:
            return 0.0

        px = Counter(x.tolist())
        py = Counter(y.tolist())
        pxy = Counter(zip(x.tolist(), y.tolist()))

        mi = 0.0
        for (xi, yi), c_xy in pxy.items():
            p_xy = c_xy / n
            p_x = px[xi] / n
            p_y = py[yi] / n
            if p_xy > 0 and p_x > 0 and p_y > 0:
                mi += p_xy * math.log2(p_xy / (p_x * p_y))
        return float(mi)

    # ------------------------------------------------------------------
    # 5. 趋势模式识别
    # ------------------------------------------------------------------

    def _analyze_trend_patterns(
        self,
        position_data: Dict[str, np.ndarray],
    ) -> List[TrendPattern]:
        """趋势模式识别

        通过线性回归斜率、动量和波动率判断各位置的趋势方向。
        """
        patterns: List[TrendPattern] = []

        for pos, arr in position_data.items():
            n = len(arr)
            if n < self.min_samples:
                continue

            x = np.arange(n, dtype=float)
            y = arr.astype(float)

            # 线性回归斜率
            if np.var(x) > 0:
                slope = float(np.polyfit(x, y, 1)[0])
            else:
                slope = 0.0

            # 近期 vs 整体均值
            recent_n = min(self.recent_window, n)
            mean_recent = float(np.mean(y[-recent_n:]))
            mean_overall = float(np.mean(y))
            momentum = mean_recent - mean_overall

            # 波动率
            volatility = float(np.std(y))

            # 趋势方向判断（斜率归一化 + 动量 + 波动率综合）
            norm_slope = slope * n / len(ALL_DIGITS) if n > 0 else 0.0

            if abs(norm_slope) < 0.05 and volatility > 2.5:
                direction = TrendDirection.OSCILLATING
            elif slope > 0.02 and momentum > 0.1:
                direction = TrendDirection.UP
            elif slope < -0.02 and momentum < -0.1:
                direction = TrendDirection.DOWN
            elif abs(norm_slope) < 0.05 and abs(momentum) < 0.1:
                direction = TrendDirection.STABLE
            else:
                # 斜率和动量不一致时，跟随动量
                if momentum > 0.1:
                    direction = TrendDirection.UP
                elif momentum < -0.1:
                    direction = TrendDirection.DOWN
                else:
                    direction = TrendDirection.STABLE

            detail = (
                f"{POSITION_LABELS.get(pos, pos)} 趋势={direction.value}, "
                f"斜率={slope:.4f}, 动量={momentum:.3f}, 波动={volatility:.3f}"
            )

            patterns.append(TrendPattern(
                position=pos,
                direction=direction,
                slope=slope,
                mean_recent=mean_recent,
                mean_overall=mean_overall,
                volatility=volatility,
                momentum=momentum,
                detail=detail,
            ))

        return patterns

    # ------------------------------------------------------------------
    # 6. 异常模式识别
    # ------------------------------------------------------------------

    def _analyze_anomaly_patterns(
        self,
        position_data: Dict[str, np.ndarray],
    ) -> List[AnomalyPattern]:
        """异常模式识别

        检测偏离正常统计规律的异常：分布失衡、长间隔、频率突变、异常组合。
        """
        anomalies: List[AnomalyPattern] = []
        positions = list(position_data.keys())
        n = len(next(iter(position_data.values())))

        if n < self.min_samples or len(positions) == 0:
            return anomalies

        # 1) 分布失衡（卡方显著）
        expected_count = n / len(ALL_DIGITS)
        for pos, arr in position_data.items():
            counts = {d: int(np.sum(arr == d)) for d in ALL_DIGITS}
            if expected_count > 0:
                chi2 = float(sum(
                    (counts[d] - expected_count) ** 2 / expected_count
                    for d in ALL_DIGITS
                ))
            else:
                chi2 = 0.0

            critical = self._chi2_critical.get(self.chi_square_alpha, 16.919)
            if chi2 > critical:
                # 找到偏差最大的数字
                max_dev_digit = max(
                    ALL_DIGITS,
                    key=lambda d: abs(counts[d] - expected_count),
                )

                if chi2 > self._chi2_critical.get(0.001, 27.877):
                    level = AnomalyLevel.HIGH
                elif chi2 > self._chi2_critical.get(0.01, 21.666):
                    level = AnomalyLevel.MEDIUM
                else:
                    level = AnomalyLevel.LOW

                anomalies.append(AnomalyPattern(
                    anomaly_type="distribution_imbalance",
                    level=level,
                    position=pos,
                    value=chi2,
                    expected=critical,
                    description=(
                        f"{POSITION_LABELS.get(pos, pos)} 分布失衡: "
                        f"卡方={chi2:.2f} > 临界值={critical:.2f}, "
                        f"偏差最大数字={max_dev_digit} "
                        f"(频次={counts[max_dev_digit]}, 期望={expected_count:.1f})"
                    ),
                ))

        # 2) 长间隔异常 - 某数字长期未出现
        for pos, arr in position_data.items():
            for d in ALL_DIGITS:
                occurrences = np.where(arr == d)[0]
                if len(occurrences) == 0:
                    # 从未出现
                    if n >= 50:
                        anomalies.append(AnomalyPattern(
                            anomaly_type="long_absence",
                            level=AnomalyLevel.HIGH,
                            position=pos,
                            value=float(n),
                            expected=float(n / len(ALL_DIGITS)),
                            description=(
                                f"{POSITION_LABELS.get(pos, pos)} 数字 {d} "
                                f"在最近 {n} 期内未出现"
                            ),
                        ))
                    continue

                # 计算历史间隔分布
                if len(occurrences) < 4:
                    continue
                gaps = [
                    int(occurrences[k] - occurrences[k - 1] - 1)
                    for k in range(1, len(occurrences))
                ]
                if len(gaps) < 3:
                    continue

                # 当前间隔（距离最后一次出现的期数）
                current_gap = int(n - 1 - occurrences[-1])

                gap_threshold = float(np.quantile(gaps, self.long_gap_quantile))
                if current_gap > gap_threshold and current_gap >= 5:
                    if current_gap > 2 * gap_threshold:
                        level = AnomalyLevel.HIGH
                    elif current_gap > 1.5 * gap_threshold:
                        level = AnomalyLevel.MEDIUM
                    else:
                        level = AnomalyLevel.LOW

                    anomalies.append(AnomalyPattern(
                        anomaly_type="long_gap",
                        level=level,
                        position=pos,
                        value=float(current_gap),
                        expected=gap_threshold,
                        description=(
                            f"{POSITION_LABELS.get(pos, pos)} 数字 {d} "
                            f"已 {current_gap} 期未出现 "
                            f"(历史 {self.long_gap_quantile:.0%} 分位={gap_threshold:.1f})"
                        ),
                    ))

        # 3) 频率突变 - 近期频率 vs 整体频率
        recent_n = min(self.recent_window, n)
        for pos, arr in position_data.items():
            recent = arr[-recent_n:]
            for d in ALL_DIGITS:
                overall_freq = float(np.mean(arr == d))
                recent_freq = float(np.mean(recent == d))

                if overall_freq == 0:
                    continue

                # Z 分数（伯努利近似，标准差 = sqrt(p(1-p)/n)）
                std = math.sqrt(overall_freq * (1 - overall_freq) / recent_n)
                if std == 0:
                    continue
                z = (recent_freq - overall_freq) / std

                if abs(z) > self.anomaly_z_threshold:
                    if abs(z) > 3.0:
                        level = AnomalyLevel.HIGH
                    elif abs(z) > 2.5:
                        level = AnomalyLevel.MEDIUM
                    else:
                        level = AnomalyLevel.LOW

                    direction = "激增" if z > 0 else "骤降"
                    anomalies.append(AnomalyPattern(
                        anomaly_type="frequency_shift",
                        level=level,
                        position=pos,
                        value=recent_freq,
                        expected=overall_freq,
                        description=(
                            f"{POSITION_LABELS.get(pos, pos)} 数字 {d} 近期频率{direction}: "
                            f"近期={recent_freq:.3f}, 整体={overall_freq:.3f}, Z={z:.2f}"
                        ),
                    ))

        # 4) 异常组合 - 全相同、全连续等
        for i in range(n):
            digits = [int(position_data[p][i]) for p in positions]
            if len(set(digits)) == 1:
                anomalies.append(AnomalyPattern(
                    anomaly_type="all_same",
                    level=AnomalyLevel.MEDIUM,
                    value=float(digits[0]),
                    description=(
                        f"第 {i} 期全位相同: {''.join(str(d) for d in digits)}"
                    ),
                ))
            elif len(digits) >= 3 and len(set(digits)) == len(digits):
                # 全连续（升序排列后相邻差 1）
                sorted_asc = sorted(digits)
                is_asc = all(
                    sorted_asc[k + 1] - sorted_asc[k] == 1
                    for k in range(len(sorted_asc) - 1)
                )
                if is_asc:
                    anomalies.append(AnomalyPattern(
                        anomaly_type="all_consecutive",
                        level=AnomalyLevel.MEDIUM,
                        value=float(digits[0]),
                        description=(
                            f"第 {i} 期全位连续: {''.join(str(d) for d in digits)}"
                        ),
                    ))

        # 按严重程度排序
        level_order = {
            AnomalyLevel.HIGH: 3,
            AnomalyLevel.MEDIUM: 2,
            AnomalyLevel.LOW: 1,
            AnomalyLevel.NONE: 0,
        }
        anomalies.sort(key=lambda a: -level_order.get(a.level, 0))

        return anomalies

    # ------------------------------------------------------------------
    # 汇总
    # ------------------------------------------------------------------

    def _generate_summary(self, result: PatternAnalysisResult) -> str:
        """生成总结性描述"""
        parts: List[str] = []

        if result.frequency_patterns:
            imbalanced = [p for p in result.frequency_patterns if not p.is_balanced]
            if imbalanced:
                parts.append(f"{len(imbalanced)} 个位置分布失衡")

            all_hot: List[Tuple[str, int]] = []
            for p in result.frequency_patterns:
                all_hot.extend([(p.position, d) for d in p.hot_numbers])
            if all_hot:
                hot_str = ", ".join(
                    f"{POSITION_LABELS.get(p, p)}-{d}" for p, d in all_hot[:8]
                )
                parts.append(f"热号: {hot_str}")

        if result.trend_patterns:
            up = [p for p in result.trend_patterns if p.direction == TrendDirection.UP]
            down = [p for p in result.trend_patterns if p.direction == TrendDirection.DOWN]
            osc = [p for p in result.trend_patterns if p.direction == TrendDirection.OSCILLATING]
            if up:
                parts.append(
                    "上升趋势: " + ",".join(
                        POSITION_LABELS.get(p.position, p.position) for p in up
                    )
                )
            if down:
                parts.append(
                    "下降趋势: " + ",".join(
                        POSITION_LABELS.get(p.position, p.position) for p in down
                    )
                )
            if osc:
                parts.append(
                    "震荡: " + ",".join(
                        POSITION_LABELS.get(p.position, p.position) for p in osc
                    )
                )

        if result.anomaly_patterns:
            high = sum(1 for a in result.anomaly_patterns if a.level == AnomalyLevel.HIGH)
            medium = sum(1 for a in result.anomaly_patterns if a.level == AnomalyLevel.MEDIUM)
            if high or medium:
                parts.append(f"异常: {high}高/{medium}中")

        if result.repeat_patterns.max_repeat_count > 1:
            parts.append(
                f"最高重复组合出现 {result.repeat_patterns.max_repeat_count} 次"
            )

        if not parts:
            return "未识别到显著模式，数据整体表现正常"

        return "; ".join(parts)


# 全局单例
_pattern_recognizer: Optional[PatternRecognizer] = None


def get_pattern_recognizer(**kwargs) -> PatternRecognizer:
    """获取全局模式识别器单例

    Args:
        **kwargs: 传递给 PatternRecognizer 构造函数的参数（仅首次创建生效）

    Returns:
        PatternRecognizer 全局实例
    """
    global _pattern_recognizer
    if _pattern_recognizer is None:
        _pattern_recognizer = PatternRecognizer(**kwargs)
    return _pattern_recognizer


if __name__ == "__main__":
    # 模块独立运行示例：生成随机数据并执行分析
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    np.random.seed(42)
    n = 100
    demo_data = {
        'wan': np.random.randint(0, 10, n),
        'qian': np.random.randint(0, 10, n),
        'bai': np.random.randint(0, 10, n),
        'shi': np.random.randint(0, 10, n),
        'ge': np.random.randint(0, 10, n),
    }

    recognizer = get_pattern_recognizer()
    result = recognizer.analyze_patterns(demo_data)

    print("\n===== 模式识别结果摘要 =====")
    print(f"总记录数: {result.total_records}")
    print(f"分析位置: {result.positions_analyzed}")
    print(f"总结: {result.summary}")
    print(f"\n异常模式数: {len(result.anomaly_patterns)}")
    for a in result.anomaly_patterns[:5]:
        print(f"  - [{a.level.value}] {a.description}")
