"""
反向预测模块 - PL5 V10.3

核心理念：彩票的可持续性要求庄家控制开奖结果
因此，"看似规律"和"高概率"反而是需要反转的信号

模块组成：
1. 异常值检测器 (AnomalyDetector) - 寻找与"标准随机"偏离最大的模式
2. 周期反转检测器 (CycleReversalDetector) - 当规律太明显时预判反转
3. 庄家行为推断器 (HouseBehaviorDetector) - 通过指标推断干预时机
4. 反向预测引擎 (ReversePredictor) - 综合输出"反向"预测

作者：AI Assistant
日期：2026-05-28
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter, defaultdict
from math import gamma, sqrt, pi, exp
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class AnomalyScore:
    period: str
    position: str
    digit: int
    anomaly_score: float
    anomaly_type: str
    details: Dict[str, Any]

@dataclass
class ReversalSignal:
    period: str
    pattern_type: str
    consecutive_count: int
    reversal_probability: float
    confidence: float
    description: str

@dataclass
class HouseBehaviorIndicator:
    period: str
    indicator_name: str
    value: float
    threshold: float
    interpretation: str

@dataclass
class ReversePrediction:
    period: str
    position: str
    recommended_digits: List[int]
    excluded_digits: List[int]
    confidence: float
    reasoning: List[str]
    signals: Dict[str, Any]


class AnomalyDetector:
    """
    异常值检测器

    核心逻辑：
    - 真正的随机应该符合均匀分布
    - 如果某个组合"太随机"或"太不随机"，都可能是异常
    - 寻找偏离标准随机分布最大的模式

    异常类型：
    1. 过度有序 - 数字排列过于规律
    2. 过度无序 - 违背随机预期的模式
    3. 统计异常 - 偏离均值超过阈值
    4. 周期性异常 - 重复出现的非随机模式
    """

    def __init__(
        self,
        window_size: int = 100,
        z_threshold: float = 2.0,
        entropy_threshold: float = 0.9
    ):
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.entropy_threshold = entropy_threshold
        self.historical_frequencies: Dict[str, Dict[int, int]] = {}

    def calculate_expected_frequency(self, n_periods: int, n_digits: int = 10) -> float:
        """计算期望频率（均匀分布）"""
        return n_periods / n_digits

    def calculate_chi_square_statistic(
        self,
        observed: Dict[int, int],
        n_periods: int
    ) -> Tuple[float, float]:
        """
        计算卡方统计量
        返回：(统计量, p值)
        """
        expected = self.calculate_expected_frequency(n_periods)
        chi_square = 0.0

        for digit in range(10):
            obs = observed.get(digit, 0)
            chi_square += ((obs - expected) ** 2) / expected

        # 自由度为9的卡方分布的p值近似
        from math import gamma, sqrt, pi
        k = 9  # 自由度
        # 使用卡方分布的近似p值计算
        p_value = 1.0 - self._chi_square_cdf(chi_square, k)

        return chi_square, p_value

    def _chi_square_cdf(self, x: float, k: int) -> float:
        """卡方分布CDF的近似计算"""
        from math import gamma, exp
        if x <= 0:
            return 0.0
        return gamma(k/2) * self._lower_incomplete_gamma(k/2, x/2) / gamma(k/2)

    def _lower_incomplete_gamma(self, s: float, x: float, max_iter: int = 100) -> float:
        """不完全Gamma函数近似"""
        result = 0.0
        term = 1.0 / s
        for n in range(max_iter):
            result += term
            term *= x / (s + n + 1)
            if abs(term) < 1e-10:
                break
        return result * exp(-x)

    def calculate_entropy(self, frequencies: Dict[int, int], n_periods: int) -> float:
        """
        计算香农熵
        - 熵值高 = 分布均匀（正常随机）
        - 熵值低 = 分布集中（可能异常）
        """
        entropy = 0.0
        for digit in range(10):
            freq = frequencies.get(digit, 0)
            if freq > 0:
                p = freq / n_periods
                entropy -= p * np.log2(p)

        # 归一化到0-1范围
        max_entropy = np.log2(10)  # 均匀分布的熵
        return entropy / max_entropy

    def detect_position_anomalies(
        self,
        data: pd.DataFrame,
        position: str,
        window: int = None
    ) -> List[AnomalyScore]:
        """
        检测某位置的异常值

        返回：按异常程度排序的异常记录列表
        """
        window = window or self.window_size
        results = []

        if len(data) < window:
            return results

        # 计算滚动窗口内的统计
        for i in range(window, len(data)):
            window_data = data.iloc[i-window:i]
            recent_data = data.iloc[i-1:i]

            recent_digits = window_data[position].values
            digit_counts = Counter(recent_digits)
            n = len(recent_digits)

            # 1. 检测过度有序（连续重复）
            consecutive = self._detect_consecutive_patterns(recent_digits)

            # 2. 计算Z分数
            z_scores = self._calculate_z_scores(digit_counts, n)

            # 3. 计算熵值
            entropy = self.calculate_entropy(digit_counts, n)

            # 4. 检测周期性
            periodicity = self._detect_periodicity(recent_digits)

            # 综合异常分数
            anomaly_score = 0.0
            anomaly_types = []
            details = {}

            # 连续性异常
            if consecutive['max_run'] > 3:
                anomaly_score += 0.3
                anomaly_types.append('consecutive')
                details['consecutive'] = consecutive

            # 频率异常
            max_z = max(z_scores.values()) if z_scores else 0
            if abs(max_z) > self.z_threshold:
                anomaly_score += min(0.4, abs(max_z) * 0.15)
                anomaly_types.append('frequency')
                details['z_scores'] = z_scores

            # 熵异常
            if entropy < self.entropy_threshold:
                anomaly_score += (1 - entropy) * 0.2
                anomaly_types.append('low_entropy')
                details['entropy'] = entropy

            # 周期性异常
            if periodicity['strength'] > 0.7:
                anomaly_score += periodicity['strength'] * 0.1
                anomaly_types.append('periodicity')
                details['periodicity'] = periodicity

            if anomaly_score > 0.1:
                period = str(data.iloc[i]['period'])
                for digit, z in z_scores.items():
                    if abs(z) > 1.5:
                        results.append(AnomalyScore(
                            period=period,
                            position=position,
                            digit=digit,
                            anomaly_score=abs(z),
                            anomaly_type=','.join(anomaly_types),
                            details={
                                'window_size': window,
                                'digit_frequency': digit_counts.get(digit, 0),
                                **details
                            }
                        ))

        # 按异常分数排序
        results.sort(key=lambda x: x.anomaly_score, reverse=True)
        return results

    def _detect_consecutive_patterns(self, digits: np.ndarray) -> Dict[str, Any]:
        """检测连续重复模式"""
        runs = []
        current_run = 1

        for i in range(1, len(digits)):
            if digits[i] == digits[i-1]:
                current_run += 1
            else:
                if current_run > 1:
                    runs.append(current_run)
                current_run = 1

        if current_run > 1:
            runs.append(current_run)

        return {
            'max_run': max(runs) if runs else 0,
            'total_runs': len(runs),
            'avg_run_length': np.mean(runs) if runs else 0
        }

    def _calculate_z_scores(
        self,
        digit_counts: Dict[int, int],
        n: int
    ) -> Dict[int, float]:
        """计算每个数字的Z分数"""
        expected = n / 10
        std = np.sqrt(expected * (1 - 1/10))

        z_scores = {}
        for digit in range(10):
            observed = digit_counts.get(digit, 0)
            z_scores[digit] = (observed - expected) / std if std > 0 else 0

        return z_scores

    def _detect_periodicity(self, digits: np.ndarray) -> Dict[str, Any]:
        """检测周期性模式"""
        if len(digits) < 10:
            return {'strength': 0, 'period': 0}

        # 使用自相关检测周期性
        correlations = []
        for lag in range(1, min(20, len(digits) // 2)):
            corr = np.corrcoef(digits[:-lag], digits[lag:])[0, 1]
            if not np.isnan(corr):
                correlations.append(abs(corr))

        return {
            'strength': max(correlations) if correlations else 0,
            'detected_period': np.argmax(correlations) + 1 if correlations else 0
        }

    def get_comprehensive_anomaly_report(
        self,
        data: pd.DataFrame
    ) -> Dict[str, Any]:
        """获取综合异常报告"""
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        report = {
            'analysis_time': datetime.now().isoformat(),
            'total_records': len(data),
            'anomalies_by_position': {},
            'top_anomalies': [],
            'chi_square_test': {},
            'entropy_analysis': {}
        }

        for pos in positions:
            anomalies = self.detect_position_anomalies(data, pos)
            report['anomalies_by_position'][pos] = {
                'count': len(anomalies),
                'max_score': anomalies[0].anomaly_score if anomalies else 0
            }

            # 收集前10个最显著的异常
            for anomaly in anomalies[:10]:
                report['top_anomalies'].append({
                    'period': anomaly.period,
                    'position': anomaly.position,
                    'digit': anomaly.digit,
                    'score': anomaly.anomaly_score,
                    'type': anomaly.anomaly_type
                })

            # 计算整体卡方检验
            digit_counts = Counter(data[pos].values)
            chi2, p_value = self.calculate_chi_square_statistic(
                digit_counts, len(data)
            )
            report['chi_square_test'][pos] = {
                'chi_square': chi2,
                'p_value': p_value,
                'is_uniform': p_value > 0.05
            }

            # 熵分析
            entropy = self.calculate_entropy(digit_counts, len(data))
            report['entropy_analysis'][pos] = {
                'entropy': entropy,
                'interpretation': '正常随机' if entropy > 0.95 else '偏分离散'
            }

        report['top_anomalies'].sort(key=lambda x: x['score'], reverse=True)
        report['top_anomalies'] = report['top_anomalies'][:50]

        return report


class CycleReversalDetector:
    """
    周期反转检测器

    核心理念：
    - 当某个规律连续出现多次后，系统会"自我修正"
    - 规律越明显，反转的可能性越大
    - 关键：识别"规律变得太明显"的临界点

    检测的规律类型：
    1. 连续奇偶性规律
    2. 连续大小数规律
    3. 连续和值规律
    4. 连续位置规律
    5. 连续遗漏规律
    """

    def __init__(
        self,
        reversal_threshold: int = 5,
        confidence_boost: float = 0.15
    ):
        self.reversal_threshold = reversal_threshold
        self.confidence_boost = confidence_boost
        self.pattern_history: Dict[str, List[int]] = defaultdict(list)

    def detect_patterns(self, data: pd.DataFrame) -> List[ReversalSignal]:
        """
        检测需要反转的规律

        返回：需要关注反转的信号列表
        """
        signals = []
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']

        # 1. 检测奇偶连续
        for pos in positions:
            signals.extend(self._detect_odd_even_pattern(data, pos))

        # 2. 检测大小连续
        for pos in positions:
            signals.extend(self._detect_size_pattern(data, pos))

        # 3. 检测和值连续
        signals.extend(self._detect_sum_pattern(data))

        # 4. 检测跨度连续
        signals.extend(self._detect_span_pattern(data))

        # 5. 检测位置关系规律
        signals.extend(self._detect_position_relation_pattern(data))

        return signals

    def _detect_odd_even_pattern(
        self,
        data: pd.DataFrame,
        position: str,
        window: int = 10
    ) -> List[ReversalSignal]:
        """检测奇偶连续模式"""
        signals = []

        if len(data) < window:
            return signals

        odd_even = [1 if d % 2 == 1 else 0 for d in data[position].values]

        for i in range(window, len(odd_even)):
            window_data = odd_even[i-window:i]

            # 检查连续相同
            if len(set(window_data)) == 1:
                # 连续相同奇偶性
                consecutive = window_data.count(window_data[0])

                if consecutive >= self.reversal_threshold:
                    reversal_prob = self._calculate_reversal_probability(
                        consecutive, 'odd_even'
                    )

                    signals.append(ReversalSignal(
                        period=str(data.iloc[i]['period']),
                        pattern_type='odd_even_consecutive',
                        consecutive_count=consecutive,
                        reversal_probability=reversal_prob,
                        confidence=min(0.9, 0.5 + consecutive * 0.05),
                        description=f'连续{consecutive}期{"奇" if window_data[0] else "偶"}数后反转概率: {reversal_prob:.1%}'
                    ))

        return signals

    def _detect_size_pattern(
        self,
        data: pd.DataFrame,
        position: str,
        window: int = 10
    ) -> List[ReversalSignal]:
        """检测大小连续模式"""
        signals = []

        if len(data) < window:
            return signals

        # 大数: 5-9, 小数: 0-4
        size_pattern = [1 if d >= 5 else 0 for d in data[position].values]

        for i in range(window, len(size_pattern)):
            window_data = size_pattern[i-window:i]

            if len(set(window_data)) == 1:
                consecutive = window_data.count(window_data[0])

                if consecutive >= self.reversal_threshold:
                    reversal_prob = self._calculate_reversal_probability(
                        consecutive, 'size'
                    )

                    signals.append(ReversalSignal(
                        period=str(data.iloc[i]['period']),
                        pattern_type='size_consecutive',
                        consecutive_count=consecutive,
                        reversal_probability=reversal_prob,
                        confidence=min(0.9, 0.5 + consecutive * 0.05),
                        description=f'连续{consecutive}期{"大" if window_data[0] else "小"}数后反转概率: {reversal_prob:.1%}'
                    ))

        return signals

    def _detect_sum_pattern(
        self,
        data: pd.DataFrame,
        window: int = 10
    ) -> List[ReversalSignal]:
        """检测和值连续"""
        signals = []

        if len(data) < window:
            return signals

        # 计算和值
        sums = []
        for _, row in data.iterrows():
            sum_val = sum([row[pos] for pos in ['wan', 'qian', 'bai', 'shi', 'ge']])
            # 大小
            sums.append(1 if sum_val >= 22 else 0)  # 和值中心点约22

        for i in range(window, len(sums)):
            window_data = sums[i-window:i]

            if len(set(window_data)) == 1:
                consecutive = window_data.count(window_data[0])

                if consecutive >= self.reversal_threshold:
                    reversal_prob = self._calculate_reversal_probability(
                        consecutive, 'sum'
                    )

                    signals.append(ReversalSignal(
                        period=str(data.iloc[i]['period']),
                        pattern_type='sum_consecutive',
                        consecutive_count=consecutive,
                        reversal_probability=reversal_prob,
                        confidence=min(0.9, 0.5 + consecutive * 0.05),
                        description=f'和值连续{consecutive}期{"大" if window_data[0] else "小"}后反转概率: {reversal_prob:.1%}'
                    ))

        return signals

    def _detect_span_pattern(
        self,
        data: pd.DataFrame,
        window: int = 10
    ) -> List[ReversalSignal]:
        """检测跨度连续"""
        signals = []

        if len(data) < window:
            return signals

        # 计算跨度
        spans = []
        for _, row in data.iterrows():
            digits = [row[pos] for pos in ['wan', 'qian', 'bai', 'shi', 'ge']]
            span = max(digits) - min(digits)
            # 大小
            spans.append(1 if span >= 5 else 0)

        for i in range(window, len(spans)):
            window_data = spans[i-window:i]

            if len(set(window_data)) == 1:
                consecutive = window_data.count(window_data[0])

                if consecutive >= self.reversal_threshold:
                    reversal_prob = self._calculate_reversal_probability(
                        consecutive, 'span'
                    )

                    signals.append(ReversalSignal(
                        period=str(data.iloc[i]['period']),
                        pattern_type='span_consecutive',
                        consecutive_count=consecutive,
                        reversal_probability=reversal_prob,
                        confidence=min(0.9, 0.5 + consecutive * 0.05),
                        description=f'跨度连续{consecutive}期{"大" if window_data[0] else "小"}后反转概率: {reversal_prob:.1%}'
                    ))

        return signals

    def _detect_position_relation_pattern(
        self,
        data: pd.DataFrame,
        window: int = 10
    ) -> List[ReversalSignal]:
        """检测位置关系规律"""
        signals = []

        if len(data) < window:
            return signals

        # 检测位置大小关系：前一位 > 后一位 的连续性
        for pos1, pos2 in [('wan', 'qian'), ('qian', 'bai'), ('bai', 'shi'), ('shi', 'ge')]:
            relations = []
            for _, row in data.iterrows():
                relations.append(1 if row[pos1] > row[pos2] else 0)

            for i in range(window, len(relations)):
                window_data = relations[i-window:i]

                if len(set(window_data)) == 1:
                    consecutive = window_data.count(window_data[0])

                    if consecutive >= self.reversal_threshold:
                        reversal_prob = self._calculate_reversal_probability(
                            consecutive, 'relation'
                        )

                        signals.append(ReversalSignal(
                            period=str(data.iloc[i]['period']),
                            pattern_type=f'relation_{pos1}_{pos2}',
                            consecutive_count=consecutive,
                            reversal_probability=reversal_prob,
                            confidence=min(0.9, 0.5 + consecutive * 0.05),
                            description=f'{pos1}>{pos2}关系连续{consecutive}期{"是" if window_data[0] else "否"}后反转概率: {reversal_prob:.1%}'
                        ))

        return signals

    def _calculate_reversal_probability(
        self,
        consecutive_count: int,
        pattern_type: str
    ) -> float:
        """
        计算反转概率

        核心理念：连续次数越多，反转概率越高
        """
        # 基础反转概率
        base_prob = 0.5

        # 连续次数的指数增长
        growth_factor = min(3.0, 1 + (consecutive_count - self.reversal_threshold) * 0.1)

        # 根据模式类型调整
        type_multipliers = {
            'odd_even': 1.2,  # 奇偶反转最常见
            'size': 1.1,
            'sum': 1.0,
            'span': 0.9,
            'relation': 0.8
        }

        multiplier = type_multipliers.get(pattern_type, 1.0)

        # 计算最终概率（限制在0.5-0.95之间）
        final_prob = min(0.95, max(0.5, base_prob * growth_factor * multiplier))

        return final_prob

    def get_reversal_signals_for_next_period(
        self,
        data: pd.DataFrame
    ) -> Dict[str, Any]:
        """获取下一期的反转信号"""
        signals = self.detect_patterns(data)

        return {
            'next_period': str(data.iloc[-1]['period'] + 1) if len(data) > 0 else 'unknown',
            'signal_count': len(signals),
            'high_confidence_signals': [
                {
                    'pattern': s.pattern_type,
                    'reversal_prob': s.reversal_probability,
                    'description': s.description
                }
                for s in signals if s.confidence > 0.7
            ],
            'all_signals': [
                {
                    'period': s.period,
                    'pattern': s.pattern_type,
                    'consecutive': s.consecutive_count,
                    'reversal_prob': s.reversal_probability,
                    'confidence': s.confidence
                }
                for s in sorted(signals, key=lambda x: x.confidence, reverse=True)
            ]
        }


class HouseBehaviorDetector:
    """
    庄家行为推断器

    核心理念：
    - 庄家需要保持长期盈利
    - 当某些指标出现极端值时，可能需要"调整"
    - 通过识别这些极端值来推断干预时机

    检测的庄家行为指标：
    1. 奖池异常 - 奖金池过高或过低
    2. 投注分布异常 - 某些数字被过度投注
    3. 返奖率异常 - 实际返奖率偏离设定值
    4. 销售截止时间效应 - 截止前后的模式变化
    5. 节假日效应 - 特定时期的特殊模式
    """

    def __init__(
        self,
        volatility_threshold: float = 2.5,
        deviation_threshold: float = 0.15
    ):
        self.volatility_threshold = volatility_threshold
        self.deviation_threshold = deviation_threshold
        self.historical_metrics: Dict[str, List[float]] = defaultdict(list)

    def detect_volatility_anomalies(
        self,
        data: pd.DataFrame,
        window: int = 30
    ) -> List[HouseBehaviorIndicator]:
        """检测波动率异常"""
        indicators = []
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']

        for pos in positions:
            # 计算滚动波动率
            for i in range(window, len(data)):
                window_data = data.iloc[i-window:i][pos].values

                mean = np.mean(window_data)
                std = np.std(window_data)

                # 当前值与均值的偏离
                current_value = data.iloc[i][pos]
                deviation = abs(current_value - mean) / (std + 1e-6)

                # 记录历史
                self.historical_metrics[f'{pos}_deviation'].append(deviation)

                if deviation > self.volatility_threshold:
                    interpretation = '极端偏离，可能需要修正'
                    if deviation > self.volatility_threshold * 1.5:
                        interpretation = '严重偏离，干预概率较高'

                    indicators.append(HouseBehaviorIndicator(
                        period=str(data.iloc[i]['period']),
                        indicator_name=f'{pos}_volatility',
                        value=deviation,
                        threshold=self.volatility_threshold,
                        interpretation=interpretation
                    ))

        return indicators

    def detect_distribution_anomalies(
        self,
        data: pd.DataFrame,
        window: int = 50
    ) -> List[HouseBehaviorIndicator]:
        """检测分布异常"""
        indicators = []

        if len(data) < window:
            return indicators

        # 计算每个位置最近window期的分布
        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            recent = data.iloc[-window:][pos].values
            digit_counts = Counter(recent)

            # 计算分布的均匀度
            expected = window / 10
            chi_square = sum(
                ((count - expected) ** 2) / expected
                for count in digit_counts.values()
            )

            # 自由度为9的卡方检验临界值约为16.9
            critical_value = 16.919

            if chi_square > critical_value * 1.5:
                # 分布极度不均匀
                most_common = digit_counts.most_common(3)
                least_common = digit_counts.most_common()[-3:]

                indicators.append(HouseBehaviorIndicator(
                    period=str(data.iloc[-1]['period']),
                    indicator_name=f'{pos}_distribution',
                    value=chi_square,
                    threshold=critical_value,
                    interpretation=f'分布异常不均匀，{most_common}高频，{least_common}低频，可能需要调整'
                ))

        return indicators

    def detect_hot_cold_pattern(
        self,
        data: pd.DataFrame,
        hot_threshold: int = 15,
        cold_threshold: int = 5
    ) -> Dict[str, List[int]]:
        """
        检测冷热号

        返回：热号和冷号列表
        """
        window = 50
        if len(data) < window:
            return {'hot': [], 'cold': []}

        result = {'hot': [], 'cold': []}

        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            recent = data.iloc[-window:][pos].values
            digit_counts = Counter(recent)

            # 找出热号（出现超过阈值）
            for digit, count in digit_counts.items():
                if count >= hot_threshold:
                    result['hot'].append(digit)

            # 找出冷号（出现低于阈值）
            for digit in range(10):
                if digit_counts.get(digit, 0) <= cold_threshold:
                    result['cold'].append(digit)

        return result

    def calculate_intervention_probability(
        self,
        data: pd.DataFrame
    ) -> float:
        """
        计算干预概率

        综合多个指标计算庄家可能干预的概率
        """
        if len(data) < 50:
            return 0.0

        signals = []

        # 1. 波动率信号
        volatility_indicators = self.detect_volatility_anomalies(data)
        if len(volatility_indicators) > 3:
            signals.append(0.3)

        # 2. 分布信号
        distribution_indicators = self.detect_distribution_anomalies(data)
        if len(distribution_indicators) > 2:
            signals.append(0.4)

        # 3. 冷热信号
        hot_cold = self.detect_hot_cold_pattern(data)
        if len(hot_cold['hot']) > 10 or len(hot_cold['cold']) > 10:
            signals.append(0.2)

        # 4. 连续性信号检测
        reversal_detector = CycleReversalDetector()
        reversal_signals = reversal_detector.detect_patterns(data)
        if len([s for s in reversal_signals if s.confidence > 0.7]) > 2:
            signals.append(0.3)

        # 综合计算
        if not signals:
            return 0.0

        # 使用加权平均，重复信号权重递减
        total_weight = 0
        weighted_sum = 0
        for i, signal in enumerate(signals):
            weight = 1.0 / (i + 1)
            weighted_sum += signal * weight
            total_weight += weight

        return min(0.9, weighted_sum / total_weight if total_weight > 0 else 0)

    def get_house_behavior_report(
        self,
        data: pd.DataFrame
    ) -> Dict[str, Any]:
        """获取庄家行为分析报告"""
        return {
            'analysis_time': datetime.now().isoformat(),
            'next_period': str(data.iloc[-1]['period'] + 1) if len(data) > 0 else 'unknown',
            'intervention_probability': self.calculate_intervention_probability(data),
            'volatility_anomalies': [
                {
                    'period': ind.period,
                    'indicator': ind.indicator_name,
                    'value': ind.value,
                    'interpretation': ind.interpretation
                }
                for ind in self.detect_volatility_anomalies(data)[-10:]
            ],
            'distribution_anomalies': [
                {
                    'period': ind.period,
                    'indicator': ind.indicator_name,
                    'value': ind.value,
                    'interpretation': ind.interpretation
                }
                for ind in self.detect_distribution_anomalies(data)
            ],
            'hot_cold_analysis': self.detect_hot_cold_pattern(data)
        }


class ReversePredictor:
    """
    反向预测引擎

    综合三大检测器的结果，生成"反向"预测

    核心逻辑：
    1. 异常检测 -> 识别"不应该出现"的模式
    2. 反转检测 -> 预测规律即将反转
    3. 庄家检测 -> 判断干预时机

    输出：
    - 建议排除的数字（高概率不出现）
    - 建议关注的数字（反转概率高）
    - 预测置信度
    """

    def __init__(
        self,
        anomaly_detector: Optional[AnomalyDetector] = None,
        reversal_detector: Optional[CycleReversalDetector] = None,
        house_detector: Optional[HouseBehaviorDetector] = None
    ):
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.reversal_detector = reversal_detector or CycleReversalDetector()
        self.house_detector = house_detector or HouseBehaviorDetector()

        self.prediction_cache: Dict[str, List[ReversePrediction]] = {}

    def generate_reverse_prediction(
        self,
        data: pd.DataFrame,
        target_period: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成反向预测

        Args:
            data: 历史数据
            target_period: 目标期号

        Returns:
            综合预测结果
        """
        if len(data) < 50:
            return {
                'success': False,
                'error': '数据不足，无法进行反向预测'
            }

        target_period = target_period or str(data.iloc[-1]['period'] + 1)

        # 1. 获取综合分析报告
        anomaly_report = self.anomaly_detector.get_comprehensive_anomaly_report(data)
        reversal_signals = self.reversal_detector.get_reversal_signals_for_next_period(data)
        house_report = self.house_detector.get_house_behavior_report(data)

        # 2. 生成每个位置的预测
        position_predictions = {}
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']

        for pos in positions:
            prediction = self._predict_position(
                data, pos, anomaly_report, reversal_signals, house_report
            )
            position_predictions[pos] = prediction

        # 3. 综合置信度
        overall_confidence = self._calculate_overall_confidence(
            anomaly_report, reversal_signals, house_report
        )

        return {
            'success': True,
            'target_period': target_period,
            'prediction_time': datetime.now().isoformat(),
            'confidence': overall_confidence,
            'position_predictions': position_predictions,
            'analysis_summary': {
                'anomaly_count': anomaly_report['total_records'],
                'reversal_signals': len(reversal_signals.get('all_signals', [])),
                'intervention_probability': house_report['intervention_probability']
            },
            'reasoning': self._generate_reasoning(
                anomaly_report, reversal_signals, house_report
            )
        }

    def _predict_position(
        self,
        data: pd.DataFrame,
        position: str,
        anomaly_report: Dict,
        reversal_signals: Dict,
        house_report: Dict
    ) -> Dict[str, Any]:
        """预测单个位置"""

        # 1. 获取该位置的异常记录
        position_anomalies = [
            a for a in anomaly_report.get('top_anomalies', [])
            if a['position'] == position
        ]

        # 2. 获取该位置相关的反转信号
        position_reversals = [
            s for s in reversal_signals.get('all_signals', [])
            if position in s['pattern'] or s['pattern'] in ['sum_consecutive', 'span_consecutive']
        ]

        # 3. 冷热分析
        hot_cold = house_report.get('hot_cold_analysis', {})
        hot_digits = hot_cold.get('hot', [])
        cold_digits = hot_cold.get('cold', [])

        # 4. 构建排除列表和关注列表
        excluded_digits = []
        recommended_digits = []

        # 排除：异常高分 + 热号
        for anomaly in position_anomalies[:3]:
            if anomaly['score'] > 2.0:
                excluded_digits.append(anomaly['digit'])

        # 排除：高频出现（热号）
        for digit in hot_digits[:3]:
            if digit not in excluded_digits:
                excluded_digits.append(digit)

        # 推荐：低频出现（冷号）+ 反转信号
        for digit in cold_digits[:3]:
            if digit not in recommended_digits:
                recommended_digits.append(digit)

        # 如果反转信号强烈，添加反转数字
        strong_reversals = [r for r in position_reversals if r['confidence'] > 0.7]
        if strong_reversals:
            # 取最近的反转信号，预期反转
            latest_reversal = strong_reversals[0]
            if 'odd_even' in latest_reversal['pattern']:
                # 预期奇偶反转，添加当前出现少的奇偶性
                recent = data.iloc[-5:][position].values
                avg_odd = np.mean([1 if d % 2 == 1 else 0 for d in recent])
                if avg_odd > 0.6:
                    # 奇数太多，添加偶数
                    for d in range(0, 10, 2):
                        if d not in recommended_digits:
                            recommended_digits.append(d)
                            break
                else:
                    for d in range(1, 10, 2):
                        if d not in recommended_digits:
                            recommended_digits.append(d)
                            break

        # 确保推荐数字有10个
        all_digits = set(range(10))
        recommended_set = set(recommended_digits)
        excluded_set = set(excluded_digits)

        # 补充推荐
        remaining = list(all_digits - recommended_set - excluded_set)
        remaining.sort(key=lambda x: np.random.random())  # 随机补充
        recommended_digits.extend(remaining[:10 - len(recommended_digits)])

        # 确保不重复且有10个
        recommended_digits = list(set(recommended_digits))[:10]
        while len(recommended_digits) < 10:
            for d in range(10):
                if d not in recommended_digits:
                    recommended_digits.append(d)
                    if len(recommended_digits) >= 10:
                        break

        excluded_digits = list(set(excluded_digits))

        # 计算置信度
        confidence = 0.5
        if position_anomalies:
            confidence += min(0.2, len(position_anomalies) * 0.03)
        if position_reversals:
            confidence += max([r['confidence'] for r in position_reversals]) * 0.2
        confidence = min(0.85, confidence)

        return {
            'excluded_digits': excluded_digits,
            'recommended_digits': recommended_digits,
            'confidence': confidence,
            'signals': {
                'anomaly_count': len(position_anomalies),
                'reversal_count': len(position_reversals),
                'is_hot': len([d for d in hot_digits if d in range(10)]) > 2
            }
        }

    def _calculate_overall_confidence(
        self,
        anomaly_report: Dict,
        reversal_signals: Dict,
        house_report: Dict
    ) -> float:
        """计算整体置信度"""

        # 基础置信度
        confidence = 0.3

        # 反转信号加分
        high_conf_reversals = [
            s for s in reversal_signals.get('high_confidence_signals', [])
        ]
        confidence += min(0.25, len(high_conf_reversals) * 0.08)

        # 庄家干预概率加分
        intervention_prob = house_report.get('intervention_probability', 0)
        if intervention_prob > 0.5:
            confidence += 0.15

        # 异常检测加分
        total_anomalies = sum(
            a['count'] for a in anomaly_report.get('anomalies_by_position', {}).values()
        )
        if total_anomalies > 20:
            confidence += 0.1

        return min(0.8, max(0.3, confidence))

    def _generate_reasoning(
        self,
        anomaly_report: Dict,
        reversal_signals: Dict,
        house_report: Dict
    ) -> List[str]:
        """生成推理说明"""

        reasoning = []

        # 异常分析
        total_anomalies = len(anomaly_report.get('top_anomalies', []))
        if total_anomalies > 0:
            reasoning.append(
                f'检测到{total_anomalies}个统计异常，'
                f'这些模式偏离标准随机分布，需要反向思考'
            )

        # 反转信号
        reversal_count = len(reversal_signals.get('all_signals', []))
        high_conf = len(reversal_signals.get('high_confidence_signals', []))
        if reversal_count > 0:
            reasoning.append(
                f'发现{reversal_count}个规律信号，'
                f'其中{high_conf}个高置信度反转信号'
            )

        # 庄家行为
        intervention_prob = house_report.get('intervention_probability', 0)
        if intervention_prob > 0.3:
            reasoning.append(
                f'庄家干预概率评估为{intervention_prob:.0%}，'
                f'系统处于{"高" if intervention_prob > 0.6 else "中等"}干预风险期'
            )

        # 冷热分析
        hot_cold = house_report.get('hot_cold_analysis', {})
        hot_count = len(hot_cold.get('hot', []))
        cold_count = len(hot_cold.get('cold', []))
        if hot_count > 5:
            reasoning.append(
                f'检测到{hot_count}个热号，系统可能需要"冷却"这些数字'
            )
        if cold_count > 5:
            reasoning.append(
                f'检测到{cold_count}个冷号，这些数字可能被低估'
            )

        if not reasoning:
            reasoning.append('系统运行正常，未检测到明显的反向信号')

        return reasoning


def load_data() -> pd.DataFrame:
    """加载PL5数据"""
    from src.core.data.collector import PL5DataCollector

    collector = PL5DataCollector()
    df = collector.load_processed_data()

    return df


def run_reverse_prediction(period: Optional[str] = None) -> Dict[str, Any]:
    """
    运行反向预测

    Args:
        period: 目标期号

    Returns:
        预测结果
    """
    logger.info("开始反向预测...")

    # 加载数据
    try:
        data = load_data()
    except Exception as e:
        logger.error(f"数据加载失败: {e}")
        return {'success': False, 'error': str(e)}

    # 创建反向预测器
    predictor = ReversePredictor()

    # 生成预测
    result = predictor.generate_reverse_prediction(data, period)

    # 格式化输出
    if result['success']:
        logger.info(f"反向预测完成，置信度: {result['confidence']:.1%}")
        logger.info(f"推理说明: {'; '.join(result['reasoning'])}")

    return result


if __name__ == '__main__':
    result = run_reverse_prediction()
    print(json.dumps(result, indent=2, ensure_ascii=False))
