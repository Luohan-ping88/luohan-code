"""
自适应特征引擎
根据排列五开奖数据的变化动态评估和调整特征组
不是固定喂给训练模块，而是根据数据特性自适应选择
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
    """特征信息"""
    name: str
    description: str
    importance: float = 0.0
    stability: float = 0.0
    correlation_with_target: float = 0.0
    last_evaluated: str = ""
    status: str = "active"  # active, deprecated, new, experimental


@dataclass
class DataCharacteristics:
    """数据特征"""
    timestamp: str
    record_count: int
    distribution_shift: float = 0.0
    volatility: float = 0.0
    entropy: float = 0.0
    patterns_detected: List[str] = field(default_factory=list)


class AdaptiveFeatureEngine:
    """自适应特征引擎"""

    def __init__(self, history_window: int = 100):
        """
        初始化自适应特征引擎

        Args:
            history_window: 历史数据窗口大小
        """
        self.history_window = history_window
        self.feature_registry: Dict[str, FeatureInfo] = {}
        self.data_history: List[DataCharacteristics] = []
        self.baseline_distribution: Optional[Dict[str, np.ndarray]] = None
        self.adaptation_threshold = 0.15  # 数据分布变化阈值

    def analyze_data_characteristics(self, df: pd.DataFrame) -> DataCharacteristics:
        """
        分析数据特征

        Args:
            df: 包含历史数据的DataFrame

        Returns:
            DataCharacteristics: 数据特征对象
        """
        latest = df.tail(self.history_window)

        characteristics = DataCharacteristics(
            timestamp=datetime.now().isoformat(),
            record_count=len(latest),
            volatility=self._calculate_volatility(latest),
            entropy=self._calculate_entropy(latest),
            patterns_detected=self._detect_patterns(latest)
        )

        # 计算分布变化
        if self.baseline_distribution:
            characteristics.distribution_shift = self._calculate_distribution_shift(latest)

        self.data_history.append(characteristics)
        return characteristics

    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """计算波动性"""
        volatilities = []
        for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
            if col in df.columns:
                volatility = df[col].std() / (df[col].mean() + 1e-6)
                volatilities.append(volatility)
        return np.mean(volatilities) if volatilities else 0.0

    def _calculate_entropy(self, df: pd.DataFrame) -> float:
        """计算信息熵"""
        entropies = []
        for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
            if col in df.columns:
                value_counts = df[col].value_counts(normalize=True)
                ent = entropy(value_counts)
                entropies.append(ent)
        return np.mean(entropies) if entropies else 0.0

    def _detect_patterns(self, df: pd.DataFrame) -> List[str]:
        """检测数据模式"""
        patterns = []

        # 检测连续性
        for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
            if col in df.columns:
                if self._has_consecutive_pattern(df[col]):
                    patterns.append(f"{col}_consecutive")

                if self._has_periodic_pattern(df[col]):
                    patterns.append(f"{col}_periodic")

                if self._has_clustering(df[col]):
                    patterns.append(f"{col}_clustering")

        return patterns

    def _has_consecutive_pattern(self, series: pd.Series) -> bool:
        """检测连续模式"""
        diffs = series.diff().dropna()
        consecutive_count = (diffs.abs() == 1).sum()
        return consecutive_count / len(diffs) > 0.3

    def _has_periodic_pattern(self, series: pd.Series) -> bool:
        """检测周期性模式"""
        autocorr = series.autocorr(lag=1)
        return abs(autocorr) > 0.3

    def _has_clustering(self, series: pd.Series) -> bool:
        """检测聚集模式"""
        value_counts = series.value_counts()
        top_3_ratio = value_counts.head(3).sum() / len(series)
        return top_3_ratio > 0.5

    def _calculate_distribution_shift(self, df: pd.DataFrame) -> float:
        """计算分布变化"""
        if not self.baseline_distribution:
            return 0.0

        shifts = []
        for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
            if col in df.columns and col in self.baseline_distribution:
                baseline = self.baseline_distribution[col]
                current = df[col].values

                # 使用KS检验计算分布差异
                ks_stat, _ = stats.ks_2samp(baseline, current)
                shifts.append(ks_stat)

        return np.mean(shifts) if shifts else 0.0

    def set_baseline(self, df: pd.DataFrame):
        """设置基准分布"""
        self.baseline_distribution = {
            col: df[col].values for col in ['wan', 'qian', 'bai', 'shi', 'ge']
            if col in df.columns
        }
        logger.info("基准分布已设置")

    def evaluate_and_select_features(
        self, df: pd.DataFrame, target_col: str = 'ge'
    ) -> Tuple[List[str], Dict[str, float]]:
        """
        评估并选择特征

        Args:
            df: 训练数据
            target_col: 目标列

        Returns:
            Tuple[List[str], Dict[str, float]]: 选中的特征列表和特征重要性
        """
        characteristics = self.analyze_data_characteristics(df)

        logger.info(f"数据特征分析完成: 波动性={characteristics.volatility:.3f}, "
                    f"熵={characteristics.entropy:.3f}, "
                    f"分布变化={characteristics.distribution_shift:.3f}")

        # 根据数据特征动态选择特征
        features = []
        importance_scores = {}

        # 基础特征（始终保留）
        basic_features = ['wan', 'qian', 'bai', 'shi', 'ge']
        features.extend(basic_features)

        # 基础统计特征
        for col in basic_features:
            importance_scores[f"{col}_mean"] = 0.7
            importance_scores[f"{col}_std"] = 0.6

        # 根据波动性调整特征
        if characteristics.volatility > 0.5:
            # 高波动：增加短期特征权重
            features.extend(['last_1', 'last_2', 'last_3'])
            importance_scores.update({
                'last_1': 0.9,
                'last_2': 0.8,
                'last_3': 0.7
            })
        else:
            # 低波动：增加长期特征权重
            features.extend(['trend_5', 'trend_10'])
            importance_scores.update({
                'trend_5': 0.8,
                'trend_10': 0.7
            })

        # 根据熵值调整
        if characteristics.entropy > 2.0:
            # 高熵：增加组合特征
            features.extend(['combination_12', 'combination_34'])
            importance_scores.update({
                'combination_12': 0.6,
                'combination_34': 0.6
            })

        # 根据分布变化调整
        if characteristics.distribution_shift > self.adaptation_threshold:
            # 检测到分布变化：重新评估所有特征
            logger.warning(f"检测到显著分布变化: {characteristics.distribution_shift:.3f}")
            features.extend(['drift_indicator', 'shift_magnitude'])
            importance_scores.update({
                'drift_indicator': 0.8,
                'shift_magnitude': 0.7
            })

        # 根据检测到的模式添加特征
        for pattern in characteristics.patterns_detected:
            col = pattern.split('_')[0]
            if 'consecutive' in pattern:
                features.append(f"{col}_consecutive_strength")
                importance_scores[f"{col}_consecutive_strength"] = 0.75
            elif 'periodic' in pattern:
                features.append(f"{col}_period_strength")
                importance_scores[f"{col}_period_strength"] = 0.7

        return features, importance_scores

    def adaptive_feature_selection(
        self, df: pd.DataFrame, performance_threshold: float = 0.6
    ) -> Dict[str, Any]:
        """
        自适应特征选择

        Args:
            df: 数据
            performance_threshold: 性能阈值

        Returns:
            Dict: 特征选择结果
        """
        characteristics = self.analyze_data_characteristics(df)

        selected_features = []
        feature_scores = {}

        # 基于数据特征的自适应选择
        for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
            feature_name = col
            score = self._evaluate_feature_relevance(df[col], characteristics)

            feature_scores[feature_name] = score

            if score > performance_threshold:
                selected_features.append(feature_name)

                # 根据分数调整特征参数
                if score > 0.8:
                    self.feature_registry[feature_name] = FeatureInfo(
                        name=feature_name,
                        description=f"高频特征：{col}位置",
                        importance=score,
                        stability=0.9,
                        status="active"
                    )
                elif score > 0.7:
                    self.feature_registry[feature_name] = FeatureInfo(
                        name=feature_name,
                        description=f"中频特征：{col}位置",
                        importance=score,
                        stability=0.7,
                        status="active"
                    )

        return {
            'selected_features': selected_features,
            'feature_scores': feature_scores,
            'characteristics': characteristics,
            'adaptation_needed': characteristics.distribution_shift > self.adaptation_threshold
        }

    def _evaluate_feature_relevance(
        self, series: pd.Series, characteristics: DataCharacteristics
    ) -> float:
        """评估特征相关性"""
        # 基于多个指标计算综合分数
        scores = []

        # 稳定性分数
        stability = 1.0 - min(series.std() / (series.mean() + 1e-6), 1.0)
        scores.append(stability * 0.3)

        # 预测性分数（使用自相关）
        autocorr = abs(series.autocorr(lag=1))
        scores.append(autocorr * 0.4)

        # 分布合理性分数
        value_counts = series.value_counts(normalize=True)
        distribution_score = 1.0 - abs(value_counts.max() - 0.2)  # 理想均匀分布
        scores.append(distribution_score * 0.3)

        return np.mean(scores)

    def generate_adaptive_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成自适应特征

        Args:
            df: 原始数据

        Returns:
            pd.DataFrame: 添加了自适应特征的数据
        """
        result_df = df.copy()
        characteristics = self.analyze_data_characteristics(df)

        # 基础统计特征
        for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
            if col in df.columns:
                result_df[f"{col}_rolling_mean_5"] = df[col].rolling(5).mean()
                result_df[f"{col}_rolling_std_5"] = df[col].rolling(5).std()
                result_df[f"{col}_diff"] = df[col].diff()

        # 自适应特征
        if characteristics.volatility > 0.5:
            # 添加短期特征
            for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
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

        Returns:
            Dict: 特征推荐和建议
        """
        recommendations = {
            'active_features': [],
            'deprecated_features': [],
            'new_features': [],
            'suggestions': []
        }

        for name, info in self.feature_registry.items():
            if info.status == 'active':
                recommendations['active_features'].append({
                    'name': name,
                    'importance': info.importance,
                    'description': info.description
                })
            elif info.status == 'deprecated':
                recommendations['deprecated_features'].append(name)

        # 生成建议
        if self.data_history:
            latest = self.data_history[-1]
            if latest.distribution_shift > self.adaptation_threshold:
                recommendations['suggestions'].append({
                    'type': 'warning',
                    'message': f'检测到数据分布变化 ({latest.distribution_shift:.3f})，建议重新训练模型'
                })

            if latest.entropy > 2.2:
                recommendations['suggestions'].append({
                    'type': 'info',
                    'message': f'数据熵值较高 ({latest.entropy:.3f})，建议增加特征组合'
                })

        return recommendations


class DynamicFeatureOptimizer:
    """动态特征优化器"""

    def __init__(self, adaptive_engine: AdaptiveFeatureEngine):
        self.engine = adaptive_engine
        self.optimization_history: List[Dict] = []

    def optimize_for_current_data(
        self, df: pd.DataFrame
    ) -> Tuple[List[str], Dict[str, float], List[str]]:
        """
        为当前数据优化特征

        Args:
            df: 当前数据

        Returns:
            Tuple: 优化后的特征列表、特征分数、优化建议
        """
        logger.info("开始动态特征优化...")

        # 1. 分析数据特征
        characteristics = self.engine.analyze_data_characteristics(df)

        # 2. 选择特征
        selected_features, importance_scores = self.engine.evaluate_and_select_features(df)

        # 3. 生成优化建议
        suggestions = self._generate_suggestions(characteristics, selected_features)

        # 4. 记录优化历史
        self.optimization_history.append({
            'timestamp': datetime.now().isoformat(),
            'characteristics': characteristics,
            'selected_features': selected_features,
            'suggestions': suggestions
        })

        logger.info(f"特征优化完成: 选择了 {len(selected_features)} 个特征")

        return selected_features, importance_scores, suggestions

    def _generate_suggestions(
        self, characteristics: DataCharacteristics, selected_features: List[str]
    ) -> List[str]:
        """生成优化建议"""
        suggestions = []

        if characteristics.distribution_shift > self.engine.adaptation_threshold:
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

        return suggestions
