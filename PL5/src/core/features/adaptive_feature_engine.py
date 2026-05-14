"""
自适应特征引擎 - PL5智能分析系统核心组件

设计理念：
    传统的特征工程采用固定特征组喂给训练模块，无法适应数据分布的变化。
    本引擎根据排列五开奖数据的实时变化，动态评估和调整特征组，实现真正的自适应学习。

核心功能：
    1. 数据特征分析：计算波动性、信息熵、分布漂移
    2. 模式检测：识别连续、周期、聚集等数据模式
    3. 自适应特征选择：根据数据特性动态选择最优特征组合
    4. 动态优化建议：提供特征调整建议和分布变化预警

版本历史：
    V1.0: 基础特征选择功能
    V2.0: 添加数据特征分析和模式检测
    V3.0: 增加分布漂移检测和自适应阈值
    V4.0: 集成动态优化器和特征推荐系统

架构位置：
    ┌─────────────────────────────────────────────────────────┐
    │                   PL5智能分析系统                        │
    ├─────────────────────────────────────────────────────────┤
    │  数据采集层                                              │
    │     ↓                                                   │
    │  ┌───────────────────────────────────────────────────┐  │
    │  │         AdaptiveFeatureEngine (本模块)             │  │
    │  │  ├─ 数据特征分析                                   │  │
    │  │  ├─ 模式检测                                       │  │
    │  │  ├─ 分布漂移检测                                   │  │
    │  │  └─ 自适应特征选择                                 │  │
    │  └───────────────────────────────────────────────────┘  │
    │     ↓                                                   │
    │  特征工程 → 模型训练 → 预测输出                           │
    └─────────────────────────────────────────────────────────┘
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from scipy import stats
from scipy.stats import entropy
import logging

logger = logging.getLogger(__name__)


@dataclass
class FeatureInfo:
    """
    特征信息数据结构

    用于存储和管理特征的元数据信息，支持特征的动态评估和生命周期管理。

    Attributes:
        name: 特征名称（唯一标识）
        description: 特征描述，说明特征的业务含义
        importance: 特征重要性分数（0-1），越高越重要
        stability: 特征稳定性分数（0-1），越高越稳定
        correlation_with_target: 与目标变量的相关性（-1到1）
        last_evaluated: 最后评估时间戳
        status: 特征状态：active(活跃)、deprecated(弃用)、new(新特征)、experimental(实验性)

    Example:
        >>> feature = FeatureInfo(
        ...     name="wan_mean",
        ...     description="万位数值的滚动均值",
        ...     importance=0.85,
        ...     stability=0.92,
        ...     correlation_with_target=0.35,
        ...     status="active"
        ... )
    """

    name: str
    description: str
    importance: float = 0.0
    stability: float = 0.0
    correlation_with_target: float = 0.0
    last_evaluated: str = ""
    status: str = "active"  # active, deprecated, new, experimental


@dataclass
class DataCharacteristics:
    """
    数据特征分析结果

    用于存储一次数据特征分析的完整结果，为自适应特征选择提供决策依据。

    Attributes:
        timestamp: 分析时间戳
        record_count: 分析的数据记录数
        distribution_shift: 分布漂移程度（0-1），超过0.15表示显著漂移
        volatility: 数据波动性（变异系数），越高表示数据越不稳定
        entropy: 信息熵（0-4.3），越高表示分布越均匀
        patterns_detected: 检测到的数据模式列表

    Key Metrics Interpretation:
        - volatility < 0.3: 低波动，数据稳定
        - volatility 0.3-0.5: 中等波动
        - volatility > 0.5: 高波动，需关注
        - entropy > 2.2: 高熵，数据分布均匀
        - distribution_shift > 0.15: 显著漂移，建议重新训练

    Example:
        >>> characteristics = DataCharacteristics(
        ...     timestamp="2024-01-01T12:00:00",
        ...     record_count=100,
        ...     volatility=0.45,
        ...     entropy=2.15,
        ...     distribution_shift=0.08,
        ...     patterns_detected=["wan_consecutive", "qian_periodic"]
        ... )
    """

    timestamp: str
    record_count: int
    distribution_shift: float = 0.0
    volatility: float = 0.0
    entropy: float = 0.0
    patterns_detected: List[str] = field(default_factory=list)


class AdaptiveFeatureEngine:
    """
    自适应特征引擎

    根据排列五开奖数据的实时变化，动态评估和调整特征组。
    核心思想是：特征选择不是一次性的，而是持续适应数据变化的过程。

    工作流程：
        1. 建立基准分布（首次运行时）
        2. 分析当前数据特征
        3. 检测数据分布漂移
        4. 根据数据特性动态选择特征
        5. 生成优化建议

    Args:
        history_window: 历史数据窗口大小，用于计算统计特征，默认100条

    Example:
        >>> # 初始化引擎
        >>> engine = AdaptiveFeatureEngine(history_window=100)
        >>>
        >>> # 设置基准分布（首次运行）
        >>> engine.set_baseline(historical_data)
        >>>
        >>> # 分析新数据并选择特征
        >>> features, importance = engine.evaluate_and_select_features(new_data)
        >>>
        >>> # 获取特征推荐
        >>> recommendations = engine.get_feature_recommendations()
    """

    def __init__(self, history_window: int = 100):
        """
        初始化自适应特征引擎

        Args:
            history_window: 历史数据窗口大小，用于计算滚动统计特征
                           建议范围：50-200，根据数据更新频率调整
        """
        self.history_window = history_window
        self.feature_registry: Dict[str, FeatureInfo] = {}
        self.data_history: List[DataCharacteristics] = []
        self.baseline_distribution: Optional[Dict[str, np.ndarray]] = None
        self.adaptation_threshold = (
            0.15  # 数据分布变化阈值，超过此值触发自适应调整
        )

    def analyze_data_characteristics(
        self, df: pd.DataFrame
    ) -> DataCharacteristics:
        """
        分析数据特征，为自适应特征选择提供数据基础

        该方法通过计算数据的波动性、信息熵和模式检测，来评估当前数据的特征分布，
        并与基准分布对比检测是否发生漂移。这些指标将用于决定是否需要调整特征组。

        Args:
            df: 包含历史数据的DataFrame，必须包含'wan', 'qian', 'bai', 'shi', 'ge'列

        Returns:
            DataCharacteristics: 数据特征对象，包含波动性、熵值、检测到的模式等

        Key Metrics:
            - volatility: 各位置数值的变异系数平均值，反映数据波动程度
            - entropy: 各位置的信息熵平均值，反映数据分布均匀性
            - distribution_shift: 通过KS检验计算的分布差异，超过0.15表示显著漂移
            - patterns_detected: 检测到的数据模式（连续、周期、聚集）

        Example:
            >>> engine = AdaptiveFeatureEngine()
            >>> engine.set_baseline(df)
            >>> characteristics = engine.analyze_data_characteristics(new_df)
            >>> if characteristics.distribution_shift > 0.15:
            ...     print("检测到数据分布漂移，建议重新训练")
        """
        latest = df.tail(self.history_window)

        characteristics = DataCharacteristics(
            timestamp=datetime.now().isoformat(),
            record_count=len(latest),
            volatility=self._calculate_volatility(latest),
            entropy=self._calculate_entropy(latest),
            patterns_detected=self._detect_patterns(latest),
        )

        # 计算分布变化（仅在设置了基准分布后）
        if self.baseline_distribution:
            characteristics.distribution_shift = (
                self._calculate_distribution_shift(latest)
            )
            if characteristics.distribution_shift > self.adaptation_threshold:
                logger.warning(
                    f"检测到显著分布变化: {characteristics.distribution_shift:.3f}"
                )

        self.data_history.append(characteristics)
        return characteristics

    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """
        计算数据波动性

        波动性使用变异系数（CV = 标准差/均值）来衡量，反映数据的离散程度。
        对于排列五数据，分别计算五个位置的波动性后取平均值。

        Args:
            df: 包含'wan', 'qian', 'bai', 'shi', 'ge'列的DataFrame

        Returns:
            float: 平均波动性值

        Interpretation:
            - < 0.3: 低波动，数据稳定
            - 0.3-0.5: 中等波动
            - > 0.5: 高波动，数据不稳定
        """
        volatilities = []
        for col in ["wan", "qian", "bai", "shi", "ge"]:
            if col in df.columns:
                mean_val = df[col].mean()
                std_val = df[col].std()
                # 避免除零错误，当均值为0时使用标准差作为波动性
                volatility = (
                    std_val / (mean_val + 1e-6) if mean_val != 0 else std_val
                )
                volatilities.append(volatility)
        return np.mean(volatilities) if volatilities else 0.0

    def _calculate_entropy(self, df: pd.DataFrame) -> float:
        """
        计算信息熵

        信息熵衡量数据分布的不确定性，熵值越高表示分布越均匀。
        对于排列五的每个位置（0-9的整数），理想均匀分布的熵约为2.32。

        Args:
            df: 包含'wan', 'qian', 'bai', 'shi', 'ge'列的DataFrame

        Returns:
            float: 平均信息熵值（0-4.3）

        Interpretation:
            - < 1.8: 低熵，数据集中在少数值
            - 1.8-2.2: 中等熵
            - > 2.2: 高熵，数据分布均匀
        """
        entropies = []
        for col in ["wan", "qian", "bai", "shi", "ge"]:
            if col in df.columns:
                value_counts = df[col].value_counts(normalize=True)
                ent = entropy(value_counts)
                entropies.append(ent)
        return np.mean(entropies) if entropies else 0.0

    def _detect_patterns(self, df: pd.DataFrame) -> List[str]:
        """
        检测数据模式

        识别数据中的连续模式、周期模式和聚集模式，为特征选择提供参考。

        Args:
            df: 包含'wan', 'qian', 'bai', 'shi', 'ge'列的DataFrame

        Returns:
            List[str]: 检测到的模式列表，格式为"{位置}_{模式类型}"

        Pattern Types:
            - consecutive: 连续数值模式（如1,2,3或9,8,7）
            - periodic: 周期性模式（自相关显著）
            - clustering: 聚集模式（少数值占比过高）

        Example:
            >>> patterns = _detect_patterns(df)
            >>> # 返回: ['wan_consecutive', 'qian_periodic']
        """
        patterns = []

        for col in ["wan", "qian", "bai", "shi", "ge"]:
            if col in df.columns:
                if self._has_consecutive_pattern(df[col]):
                    patterns.append(f"{col}_consecutive")

                if self._has_periodic_pattern(df[col]):
                    patterns.append(f"{col}_periodic")

                if self._has_clustering(df[col]):
                    patterns.append(f"{col}_clustering")

        return patterns

    def _has_consecutive_pattern(self, series: pd.Series) -> bool:
        """
        检测连续模式

        判断序列中是否存在连续递增或递减的模式。

        Args:
            series: 数值序列

        Returns:
            bool: 是否检测到连续模式

        Detection Logic:
            计算相邻元素差值的绝对值为1的比例，超过30%则认为存在连续模式
        """
        diffs = series.diff().dropna()
        consecutive_count = (diffs.abs() == 1).sum()
        return consecutive_count / len(diffs) > 0.3

    def _has_periodic_pattern(self, series: pd.Series) -> bool:
        """
        检测周期性模式

        使用自相关分析检测序列是否存在周期性。

        Args:
            series: 数值序列

        Returns:
            bool: 是否检测到周期模式

        Detection Logic:
            计算滞后1期的自相关系数，绝对值超过0.3则认为存在周期性
        """
        autocorr = series.autocorr(lag=1)
        return abs(autocorr) > 0.3

    def _has_clustering(self, series: pd.Series) -> bool:
        """
        检测聚集模式

        判断序列是否集中在少数几个值上。

        Args:
            series: 数值序列

        Returns:
            bool: 是否检测到聚集模式

        Detection Logic:
            计算出现频率最高的3个值占总数的比例，超过50%则认为存在聚集
        """
        value_counts = series.value_counts()
        top_3_ratio = value_counts.head(3).sum() / len(series)
        return top_3_ratio > 0.5

    def _calculate_distribution_shift(self, df: pd.DataFrame) -> float:
        """
        计算分布变化（漂移检测）

        使用Kolmogorov-Smirnov检验比较当前分布与基准分布的差异。

        Args:
            df: 当前数据

        Returns:
            float: 分布差异程度（0-1）

        Detection Logic:
            KS统计量越大，表示两个分布差异越大
            超过0.15认为是显著漂移

        Note:
            仅在设置了基准分布后有效
        """
        if not self.baseline_distribution:
            return 0.0

        shifts = []
        for col in ["wan", "qian", "bai", "shi", "ge"]:
            if col in df.columns and col in self.baseline_distribution:
                baseline = self.baseline_distribution[col]
                current = df[col].values

                # 使用KS检验计算分布差异
                ks_stat, _ = stats.ks_2samp(baseline, current)
                shifts.append(ks_stat)

        return np.mean(shifts) if shifts else 0.0

    def set_baseline(self, df: pd.DataFrame):
        """
        设置基准分布

        用于后续的分布漂移检测，建议使用至少1000条历史数据作为基准。

        Args:
            df: 历史数据，包含'wan', 'qian', 'bai', 'shi', 'ge'列

        Best Practice:
            在系统首次运行或数据发生重大变化后重新设置基准

        Example:
            >>> engine = AdaptiveFeatureEngine()
            >>> engine.set_baseline(historical_data)  # 使用历史数据建立基准
        """
        self.baseline_distribution = {
            col: df[col].values
            for col in ["wan", "qian", "bai", "shi", "ge"]
            if col in df.columns
        }
        logger.info(
            f"基准分布已设置，包含{len(self.baseline_distribution)}个特征"
        )

    def evaluate_and_select_features(
        self, df: pd.DataFrame, target_col: str = "ge"
    ) -> Tuple[List[str], Dict[str, float]]:
        """
        评估并选择特征（核心方法）

        根据当前数据特征，动态选择最适合的特征组合。

        选择策略：
            1. 始终保留基础特征（wan, qian, bai, shi, ge）
            2. 根据波动性调整特征权重：
               - 高波动：增加短期特征（last_1, last_2等）
               - 低波动：增加长期趋势特征（trend_5, trend_10等）
            3. 根据熵值调整：
               - 高熵：增加特征组合
            4. 根据分布漂移调整：
               - 显著漂移：添加漂移检测特征

        Args:
            df: 训练数据
            target_col: 目标列，默认为'ge'（个位）

        Returns:
            Tuple[List[str], Dict[str, float]]:
                - 选中的特征列表
                - 特征重要性字典

        Example:
            >>> engine = AdaptiveFeatureEngine()
            >>> engine.set_baseline(historical_data)
            >>> features, importance = engine.evaluate_and_select_features(new_data)
            >>> # features = ['wan', 'qian', 'bai', 'shi', 'ge', 'last_1', 'last_2', ...]
            >>> # importance = {'wan': 1.0, 'last_1': 0.9, ...}
        """
        characteristics = self.analyze_data_characteristics(df)

        logger.info(
            f"数据特征分析完成: 波动性={characteristics.volatility:.3f}, "
            f"熵={characteristics.entropy:.3f}, "
            f"分布变化={characteristics.distribution_shift:.3f}"
        )

        # 根据数据特征动态选择特征
        features = []
        importance_scores = {}

        # 基础特征（始终保留）
        basic_features = ["wan", "qian", "bai", "shi", "ge"]
        features.extend(basic_features)
        for feat in basic_features:
            importance_scores[feat] = 1.0

        # 基础统计特征
        for col in basic_features:
            importance_scores[f"{col}_mean"] = 0.7
            importance_scores[f"{col}_std"] = 0.6

        # 根据波动性调整特征
        if characteristics.volatility > 0.5:
            # 高波动：增加短期特征权重
            features.extend(["last_1", "last_2", "last_3"])
            importance_scores.update(
                {"last_1": 0.9, "last_2": 0.8, "last_3": 0.7}
            )
        else:
            # 低波动：增加长期特征权重
            features.extend(["trend_5", "trend_10"])
            importance_scores.update({"trend_5": 0.8, "trend_10": 0.7})

        # 根据熵值调整
        if characteristics.entropy > 2.0:
            # 高熵：增加组合特征
            features.extend(["combination_12", "combination_34"])
            importance_scores.update(
                {"combination_12": 0.6, "combination_34": 0.6}
            )

        # 根据分布变化调整
        if characteristics.distribution_shift > self.adaptation_threshold:
            # 检测到分布变化：添加漂移检测特征
            features.extend(["drift_indicator", "shift_magnitude"])
            importance_scores.update(
                {"drift_indicator": 0.8, "shift_magnitude": 0.7}
            )

        # 根据检测到的模式添加特征
        for pattern in characteristics.patterns_detected:
            col = pattern.split("_")[0]
            if "consecutive" in pattern:
                features.append(f"{col}_consecutive_strength")
                importance_scores[f"{col}_consecutive_strength"] = 0.75
            elif "periodic" in pattern:
                features.append(f"{col}_period_strength")
                importance_scores[f"{col}_period_strength"] = 0.7

        return features, importance_scores

    def adaptive_feature_selection(
        self, df: pd.DataFrame, performance_threshold: float = 0.6
    ) -> Dict[str, Any]:
        """
        自适应特征选择（完整流程）

        执行完整的特征选择流程，包括数据特征分析、特征评估和推荐生成。

        Args:
            df: 数据
            performance_threshold: 性能阈值，低于此值的特征将被排除

        Returns:
            Dict: 特征选择结果，包含：
                - selected_features: 选中的特征列表
                - feature_scores: 特征分数
                - characteristics: 数据特征分析结果
                - adaptation_needed: 是否需要自适应调整

        Example:
            >>> result = engine.adaptive_feature_selection(df)
            >>> if result['adaptation_needed']:
            ...     print("需要重新选择特征")
            ...     print(f"选中特征: {result['selected_features']}")
        """
        characteristics = self.analyze_data_characteristics(df)

        selected_features = []
        feature_scores = {}

        # 基于数据特征的自适应选择
        for col in ["wan", "qian", "bai", "shi", "ge"]:
            feature_name = col
            score = self._evaluate_feature_relevance(df[col], characteristics)

            feature_scores[feature_name] = score

            if score > performance_threshold:
                selected_features.append(feature_name)

                # 根据分数调整特征参数
                if score > 0.8:
                    self.feature_registry[feature_name] = FeatureInfo(
                        name=feature_name,
                        description=f"高频特征：{col}位置原始数值",
                        importance=score,
                        stability=0.9,
                        status="active",
                    )
                elif score > 0.7:
                    self.feature_registry[feature_name] = FeatureInfo(
                        name=feature_name,
                        description=f"中频特征：{col}位置原始数值",
                        importance=score,
                        stability=0.7,
                        status="active",
                    )

        return {
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "characteristics": characteristics,
            "adaptation_needed": characteristics.distribution_shift
            > self.adaptation_threshold,
        }

    def _evaluate_feature_relevance(
        self, series: pd.Series, characteristics: DataCharacteristics
    ) -> float:
        """
        评估特征相关性（内部方法）

        基于多个指标计算特征的综合相关性分数。

        Args:
            series: 特征序列
            characteristics: 数据特征分析结果

        Returns:
            float: 相关性分数（0-1）

        Evaluation Criteria:
            - 稳定性分数（30%权重）：基于变异系数
            - 预测性分数（40%权重）：基于自相关
            - 分布合理性分数（30%权重）：与均匀分布的偏离程度
        """
        scores = []

        # 稳定性分数
        mean_val = series.mean()
        std_val = series.std()
        stability = 1.0 - min(std_val / (mean_val + 1e-6), 1.0)
        scores.append(stability * 0.3)

        # 预测性分数（使用自相关）
        autocorr = abs(series.autocorr(lag=1))
        scores.append(autocorr * 0.4)

        # 分布合理性分数
        value_counts = series.value_counts(normalize=True)
        # 理想均匀分布每个值的概率约为0.1（0-9共10个值）
        distribution_score = 1.0 - abs(value_counts.max() - 0.1)
        scores.append(min(distribution_score, 1.0) * 0.3)

        return np.mean(scores)

    def generate_adaptive_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成自适应特征

        根据数据特征动态生成新特征，并添加到DataFrame中。

        Args:
            df: 原始数据

        Returns:
            pd.DataFrame: 添加了自适应特征的数据

        Generated Features:
            - 基础统计特征：rolling_mean, rolling_std, diff
            - 短期特征（高波动时）：lag_1, lag_2
            - 漂移检测特征（分布变化时）：drift_detected, drift_magnitude

        Example:
            >>> df = pd.DataFrame({'wan': [1,2,3,4,5,6,7,8,9,0]})
            >>> result = engine.generate_adaptive_features(df)
            >>> # result包含wan_rolling_mean_5, wan_rolling_std_5等特征
        """
        result_df = df.copy()
        characteristics = self.analyze_data_characteristics(df)

        # 基础统计特征
        for col in ["wan", "qian", "bai", "shi", "ge"]:
            if col in df.columns:
                result_df[f"{col}_rolling_mean_5"] = df[col].rolling(5).mean()
                result_df[f"{col}_rolling_std_5"] = df[col].rolling(5).std()
                result_df[f"{col}_diff"] = df[col].diff()

        # 自适应特征
        if characteristics.volatility > 0.5:
            # 添加短期特征
            for col in ["wan", "qian", "bai", "shi", "ge"]:
                if col in df.columns:
                    result_df[f"{col}_lag_1"] = df[col].shift(1)
                    result_df[f"{col}_lag_2"] = df[col].shift(2)

        if characteristics.distribution_shift > self.adaptation_threshold:
            # 添加漂移检测特征
            result_df["drift_detected"] = 1
            result_df["drift_magnitude"] = characteristics.distribution_shift

        return result_df.fillna(0)

    def get_feature_recommendations(self) -> Dict[str, Any]:
        """
        获取特征推荐

        基于历史分析结果，生成特征使用建议。

        Returns:
            Dict: 特征推荐和建议，包含：
                - active_features: 当前活跃的特征列表
                - deprecated_features: 已弃用的特征列表
                - new_features: 新特征列表
                - suggestions: 优化建议

        Example:
            >>> recommendations = engine.get_feature_recommendations()
            >>> for suggestion in recommendations['suggestions']:
            ...     print(f"{suggestion['type']}: {suggestion['message']}")
        """
        recommendations = {
            "active_features": [],
            "deprecated_features": [],
            "new_features": [],
            "suggestions": [],
        }

        for name, info in self.feature_registry.items():
            if info.status == "active":
                recommendations["active_features"].append(
                    {
                        "name": name,
                        "importance": info.importance,
                        "description": info.description,
                    }
                )
            elif info.status == "deprecated":
                recommendations["deprecated_features"].append(name)

        # 生成建议
        if self.data_history:
            latest = self.data_history[-1]
            if latest.distribution_shift > self.adaptation_threshold:
                recommendations["suggestions"].append(
                    {
                        "type": "warning",
                        "message": f"检测到数据分布变化 ({latest.distribution_shift:.3f})，建议重新训练模型",
                    }
                )

            if latest.entropy > 2.2:
                recommendations["suggestions"].append(
                    {
                        "type": "info",
                        "message": f"数据熵值较高 ({latest.entropy:.3f})，建议增加特征组合",
                    }
                )

            if latest.volatility > 0.5:
                recommendations["suggestions"].append(
                    {
                        "type": "info",
                        "message": f"数据波动性较高 ({latest.volatility:.3f})，建议关注短期特征",
                    }
                )

        return recommendations


class DynamicFeatureOptimizer:
    """
    动态特征优化器

    封装自适应特征引擎，提供更高级的优化接口。

    Args:
        adaptive_engine: AdaptiveFeatureEngine实例

    Example:
        >>> engine = AdaptiveFeatureEngine()
        >>> optimizer = DynamicFeatureOptimizer(engine)
        >>> features, importance, suggestions = optimizer.optimize_for_current_data(df)
    """

    def __init__(self, adaptive_engine: AdaptiveFeatureEngine):
        self.engine = adaptive_engine
        self.optimization_history: List[Dict] = []

    def optimize_for_current_data(
        self, df: pd.DataFrame
    ) -> Tuple[List[str], Dict[str, float], List[str]]:
        """
        为当前数据优化特征（推荐使用）

        执行完整的特征优化流程，包括数据特征分析、特征选择和建议生成。

        Args:
            df: 当前数据

        Returns:
            Tuple[List[str], Dict[str, float], List[str]]:
                - 优化后的特征列表
                - 特征分数字典
                - 优化建议列表

        Workflow:
            1. 分析数据特征（波动性、熵、分布漂移）
            2. 执行自适应特征选择
            3. 生成优化建议
            4. 记录优化历史

        Example:
            >>> optimizer = DynamicFeatureOptimizer(engine)
            >>> features, importance, suggestions = optimizer.optimize_for_current_data(df)
            >>> print(f"选中{len(features)}个特征")
            >>> for suggestion in suggestions:
            ...     print(f"建议: {suggestion}")
        """
        logger.info("开始动态特征优化...")

        # 1. 分析数据特征
        characteristics = self.engine.analyze_data_characteristics(df)

        # 2. 选择特征
        selected_features, importance_scores = (
            self.engine.evaluate_and_select_features(df)
        )

        # 3. 生成优化建议
        suggestions = self._generate_suggestions(
            characteristics, selected_features
        )

        # 4. 记录优化历史
        self.optimization_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "characteristics": characteristics,
                "selected_features": selected_features,
                "suggestions": suggestions,
            }
        )

        logger.info(f"特征优化完成: 选择了 {len(selected_features)} 个特征")

        return selected_features, importance_scores, suggestions

    def _generate_suggestions(
        self,
        characteristics: DataCharacteristics,
        selected_features: List[str],
    ) -> List[str]:
        """
        生成优化建议（内部方法）

        根据数据特征分析结果生成针对性的优化建议。

        Args:
            characteristics: 数据特征分析结果
            selected_features: 当前选中的特征列表

        Returns:
            List[str]: 优化建议列表

        Suggestion Types:
            - warning: 需要关注的问题
            - info: 一般性建议
        """
        suggestions = []

        if (
            characteristics.distribution_shift
            > self.engine.adaptation_threshold
        ):
            suggestions.append(
                f"⚠️ 数据分布发生显著变化 ({characteristics.distribution_shift:.3f})，"
                "建议重新训练模型"
            )

        if characteristics.volatility > 0.5:
            suggestions.append(
                f"📈 检测到高波动性 ({characteristics.volatility:.3f})，"
                "已增加短期特征权重"
            )

        if characteristics.entropy > 2.2:
            suggestions.append(
                f"🔄 数据熵值较高 ({characteristics.entropy:.3f})，"
                "建议增加特征组合"
            )

        if characteristics.patterns_detected:
            suggestions.append(
                f"🔍 检测到 {len(characteristics.patterns_detected)} 种数据模式："
                f"{', '.join(characteristics.patterns_detected[:3])}"
            )

        if len(selected_features) < 5:
            suggestions.append(
                f"⚠️ 选中特征数量较少 ({len(selected_features)}个)，"
                "建议检查数据质量或调整阈值"
            )

        return suggestions
