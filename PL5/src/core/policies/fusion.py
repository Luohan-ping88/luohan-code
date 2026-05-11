"""
策略融合算法模块
加权融合、投票融合和堆叠融合
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import logging
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.linear_model import LogisticRegression, LinearRegression

logger = logging.getLogger(__name__)


class FusionStrategy(Enum):
    """融合策略枚举"""

    WEIGHTED_AVERAGE = "weighted_average"
    MAJORITY_VOTE = "majority_vote"
    SOFT_VOTE = "soft_vote"
    STACKING = "stacking"


@dataclass
class FusionResult:
    """融合结果"""

    predictions: np.ndarray
    strategy: FusionStrategy
    policy_weights: Optional[Dict[str, float]] = None
    confidence_scores: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PolicyFuser(BaseEstimator):
    """策略融合器"""

    def __init__(
        self,
        strategy: FusionStrategy = FusionStrategy.WEIGHTED_AVERAGE,
        weights: Optional[List[float]] = None,
        meta_learner: Optional[BaseEstimator] = None,
        is_classification: bool = True,
    ):
        self.strategy = strategy
        self.weights = weights
        self.meta_learner = meta_learner
        self.is_classification = is_classification
        self._policy_names: List[str] = []
        self._is_fitted = False

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        policy_predictions: Optional[Dict[str, np.ndarray]] = None,
        sample_weight: Optional[np.ndarray] = None,
    ) -> "PolicyFuser":
        """
        拟合融合器

        Args:
            X: 特征数据（用于堆叠融合）
            y: 目标变量
            policy_predictions: 各策略的预测结果字典
            sample_weight: 样本权重

        Returns:
            self
        """
        if self.strategy == FusionStrategy.STACKING:
            if policy_predictions is None:
                raise ValueError("堆叠融合需要提供policy_predictions")

            self._policy_names = list(policy_predictions.keys())
            meta_features = np.column_stack([policy_predictions[name] for name in self._policy_names])

            if self.meta_learner is None:
                if self.is_classification:
                    self.meta_learner = LogisticRegression(random_state=42)
                else:
                    self.meta_learner = LinearRegression()

            self.meta_learner.fit(meta_features, y, sample_weight=sample_weight)
        elif self.weights is None and policy_predictions is not None:
            self._policy_names = list(policy_predictions.keys())
            self.weights = [1.0 / len(self._policy_names)] * len(self._policy_names)

        self._is_fitted = True
        return self

    def predict(self, policy_predictions: Dict[str, np.ndarray], X: Optional[np.ndarray] = None) -> FusionResult:
        """
        预测

        Args:
            policy_predictions: 各策略的预测结果字典
            X: 特征数据（用于堆叠融合）

        Returns:
            融合结果
        """
        if not self._is_fitted and self.strategy == FusionStrategy.STACKING:
            raise ValueError("融合器尚未拟合，请先调用fit()")

        policy_names = list(policy_predictions.keys())
        predictions_list = [policy_predictions[name] for name in policy_names]

        if self.strategy == FusionStrategy.WEIGHTED_AVERAGE:
            return self._weighted_average(predictions_list, policy_names)
        elif self.strategy == FusionStrategy.MAJORITY_VOTE:
            return self._majority_vote(predictions_list, policy_names)
        elif self.strategy == FusionStrategy.SOFT_VOTE:
            return self._soft_vote(predictions_list, policy_names)
        elif self.strategy == FusionStrategy.STACKING:
            return self._stacking(predictions_list, policy_names)
        else:
            raise ValueError(f"未知的融合策略: {self.strategy}")

    def _weighted_average(self, predictions_list: List[np.ndarray], policy_names: List[str]) -> FusionResult:
        """加权平均融合"""
        weights = self.weights or [1.0 / len(predictions_list)] * len(predictions_list)

        if len(weights) != len(predictions_list):
            weights = [1.0 / len(predictions_list)] * len(predictions_list)

        weighted_preds = np.average(predictions_list, axis=0, weights=weights)

        return FusionResult(
            predictions=weighted_preds,
            strategy=FusionStrategy.WEIGHTED_AVERAGE,
            policy_weights=dict(zip(policy_names, weights)),
        )

    def _majority_vote(self, predictions_list: List[np.ndarray], policy_names: List[str]) -> FusionResult:
        """多数投票融合"""
        predictions_array = np.array(predictions_list)

        if predictions_array.ndim == 2:
            predictions_array = predictions_array.T

        voted_preds = []
        for i in range(predictions_array.shape[0]):
            unique, counts = np.unique(predictions_array[i], return_counts=True)
            voted_preds.append(unique[np.argmax(counts)])

        return FusionResult(predictions=np.array(voted_preds), strategy=FusionStrategy.MAJORITY_VOTE)

    def _soft_vote(self, predictions_list: List[np.ndarray], policy_names: List[str]) -> FusionResult:
        """软投票融合"""
        weights = self.weights or [1.0 / len(predictions_list)] * len(predictions_list)

        if len(weights) != len(predictions_list):
            weights = [1.0 / len(predictions_list)] * len(predictions_list)

        weighted_probs = np.average(predictions_list, axis=0, weights=weights)

        if weighted_probs.ndim > 1:
            final_preds = np.argmax(weighted_probs, axis=1)
        else:
            final_preds = (weighted_probs > 0.5).astype(int)

        return FusionResult(
            predictions=final_preds,
            strategy=FusionStrategy.SOFT_VOTE,
            policy_weights=dict(zip(policy_names, weights)),
            confidence_scores=weighted_probs,
        )

    def _stacking(self, predictions_list: List[np.ndarray], policy_names: List[str]) -> FusionResult:
        """堆叠融合"""
        if self.meta_learner is None:
            raise ValueError("堆叠融合需要meta_learner")

        meta_features = np.column_stack(predictions_list)
        final_preds = self.meta_learner.predict(meta_features)

        confidence_scores = None
        if hasattr(self.meta_learner, "predict_proba"):
            try:
                confidence_scores = self.meta_learner.predict_proba(meta_features)
            except:
                pass

        return FusionResult(
            predictions=final_preds, strategy=FusionStrategy.STACKING, confidence_scores=confidence_scores
        )

    def set_weights(self, weights: List[float]) -> None:
        """设置权重"""
        self.weights = weights

    def set_meta_learner(self, meta_learner: BaseEstimator) -> None:
        """设置元学习器"""
        self.meta_learner = meta_learner
