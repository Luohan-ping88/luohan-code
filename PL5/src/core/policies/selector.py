"""
上下文感知策略选择器模块
上下文特征提取、策略匹配算法和置信度计算
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
import logging
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class SelectionStrategy(Enum):
    """选择策略枚举"""

    BEST_MATCH = "best_match"
    WEIGHTED_RANDOM = "weighted_random"
    TOP_K = "top_k"
    THRESHOLD = "threshold"


@dataclass
class ContextFeatures:
    """上下文特征"""

    numerical_features: Dict[str, float] = field(default_factory=dict)
    categorical_features: Dict[str, str] = field(default_factory=dict)
    temporal_features: Dict[str, Any] = field(default_factory=dict)
    custom_features: Dict[str, Any] = field(default_factory=dict)

    def to_vector(self, feature_order: Optional[List[str]] = None) -> np.ndarray:
        """将特征转换为向量"""
        all_features = {**self.numerical_features}
        if feature_order:
            return np.array([all_features.get(f, 0.0) for f in feature_order])
        return np.array(list(all_features.values()))


@dataclass
class PolicyMatch:
    """策略匹配结果"""

    policy_name: str
    policy_version: str
    similarity_score: float
    confidence: float
    context_features: ContextFeatures
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextFeatureExtractor:
    """上下文特征提取器"""

    def __init__(self):
        self.scaler = StandardScaler()
        self._is_fitted = False

    def extract_numerical(self, data: Dict[str, Any]) -> Dict[str, float]:
        """提取数值特征"""
        features = {}
        for key, value in data.items():
            if isinstance(value, (int, float)):
                features[key] = float(value)
        return features

    def extract_categorical(self, data: Dict[str, Any]) -> Dict[str, str]:
        """提取分类特征"""
        features = {}
        for key, value in data.items():
            if isinstance(value, str):
                features[key] = value
        return features

    def fit(self, features_list: List[ContextFeatures]) -> None:
        """拟合特征缩放器"""
        numerical_data = []
        for features in features_list:
            numerical_data.append(list(features.numerical_features.values()))

        if numerical_data:
            self.scaler.fit(np.array(numerical_data))
            self._is_fitted = True

    def transform(self, features: ContextFeatures) -> ContextFeatures:
        """变换特征"""
        if not self._is_fitted or not features.numerical_features:
            return features

        numerical_array = np.array(list(features.numerical_features.values())).reshape(1, -1)
        scaled_array = self.scaler.transform(numerical_array)

        scaled_features = ContextFeatures(
            numerical_features=dict(zip(features.numerical_features.keys(), scaled_array[0])),
            categorical_features=features.categorical_features,
            temporal_features=features.temporal_features,
            custom_features=features.custom_features,
        )
        return scaled_features


class ContextAwareSelector:
    """上下文感知策略选择器"""

    def __init__(self, selection_strategy: SelectionStrategy = SelectionStrategy.BEST_MATCH):
        self.selection_strategy = selection_strategy
        self.feature_extractor = ContextFeatureExtractor()
        self._policy_contexts: Dict[str, Tuple[str, ContextFeatures, Dict[str, float]]] = {}
        self._confidence_threshold = 0.5

    def register_policy_context(
        self,
        policy_name: str,
        policy_version: str,
        context_features: ContextFeatures,
        performance_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        注册策略的上下文特征

        Args:
            policy_name: 策略名称
            policy_version: 策略版本
            context_features: 上下文特征
            performance_weights: 性能权重
        """
        self._policy_contexts[f"{policy_name}:{policy_version}"] = (
            policy_name,
            policy_version,
            context_features,
            performance_weights or {},
        )
        logger.info(f"策略 {policy_name} v{policy_version} 上下文特征已注册")

    def calculate_similarity(self, context1: ContextFeatures, context2: ContextFeatures) -> float:
        """
        计算两个上下文之间的相似度

        Args:
            context1: 上下文1
            context2: 上下文2

        Returns:
            相似度分数
        """
        vec1 = context1.to_vector()
        vec2 = context2.to_vector()

        if len(vec1) == 0 or len(vec2) == 0:
            return 0.0

        min_len = min(len(vec1), len(vec2))
        vec1 = vec1[:min_len].reshape(1, -1)
        vec2 = vec2[:min_len].reshape(1, -1)

        return float(cosine_similarity(vec1, vec2)[0][0])

    def calculate_confidence(
        self,
        similarity: float,
        policy_performance: Optional[Dict[str, float]] = None,
        performance_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        计算置信度

        Args:
            similarity: 相似度
            policy_performance: 策略性能指标
            performance_weights: 性能权重

        Returns:
            置信度
        """
        confidence = similarity

        if policy_performance and performance_weights:
            performance_score = 0.0
            total_weight = 0.0
            for metric, weight in performance_weights.items():
                if metric in policy_performance:
                    performance_score += policy_performance[metric] * weight
                    total_weight += weight

            if total_weight > 0:
                performance_score /= total_weight
                confidence = 0.7 * similarity + 0.3 * performance_score

        return max(0.0, min(1.0, confidence))

    def match_policies(
        self, current_context: ContextFeatures, policy_performances: Optional[Dict[str, Dict[str, float]]] = None
    ) -> List[PolicyMatch]:
        """
        匹配策略

        Args:
            current_context: 当前上下文
            policy_performances: 策略性能字典

        Returns:
            策略匹配结果列表
        """
        policy_performances = policy_performances or {}
        matches = []

        for key, (name, version, context, weights) in self._policy_contexts.items():
            similarity = self.calculate_similarity(current_context, context)
            perf = policy_performances.get(name, {})
            confidence = self.calculate_confidence(similarity, perf, weights)

            matches.append(
                PolicyMatch(
                    policy_name=name,
                    policy_version=version,
                    similarity_score=similarity,
                    confidence=confidence,
                    context_features=current_context,
                )
            )

        return sorted(matches, key=lambda x: x.confidence, reverse=True)

    def select_policy(
        self,
        current_context: ContextFeatures,
        policy_performances: Optional[Dict[str, Dict[str, float]]] = None,
        top_k: int = 1,
        threshold: Optional[float] = None,
    ) -> List[PolicyMatch]:
        """
        选择策略

        Args:
            current_context: 当前上下文
            policy_performances: 策略性能字典
            top_k: 返回前k个策略
            threshold: 置信度阈值

        Returns:
            选中的策略匹配结果列表
        """
        matches = self.match_policies(current_context, policy_performances)

        if self.selection_strategy == SelectionStrategy.BEST_MATCH:
            return matches[:1] if matches else []
        elif self.selection_strategy == SelectionStrategy.TOP_K:
            return matches[:top_k]
        elif self.selection_strategy == SelectionStrategy.THRESHOLD:
            thresh = threshold or self._confidence_threshold
            return [m for m in matches if m.confidence >= thresh]
        elif self.selection_strategy == SelectionStrategy.WEIGHTED_RANDOM:
            if not matches:
                return []
            confidences = [m.confidence for m in matches]
            total = sum(confidences)
            if total == 0:
                return matches[:1]
            probs = [c / total for c in confidences]
            selected_idx = np.random.choice(len(matches), p=probs)
            return [matches[selected_idx]]

        return matches[:top_k]

    def set_confidence_threshold(self, threshold: float) -> None:
        """设置置信度阈值"""
        self._confidence_threshold = max(0.0, min(1.0, threshold))

    def clear_policy_contexts(self) -> None:
        """清除所有策略上下文"""
        self._policy_contexts.clear()
        logger.info("策略上下文已清除")
