"""
多策略并行评估器模块
并行评估多个策略、性能指标收集和策略排名
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
from datetime import datetime
import logging
import concurrent.futures
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """性能指标类型"""
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1 = "f1"
    MSE = "mse"
    RMSE = "rmse"
    CUSTOM = "custom"


@dataclass
class EvaluationResult:
    """评估结果"""
    policy_name: str
    policy_version: str
    metrics: Dict[str, float]
    evaluation_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_metric(self, metric_name: str) -> Optional[float]:
        """获取指定指标值"""
        return self.metrics.get(metric_name)


@dataclass
class PolicyRank:
    """策略排名"""
    policy_name: str
    policy_version: str
    rank: int
    score: float
    evaluation_result: EvaluationResult


class ParallelEvaluator:
    """多策略并行评估器"""

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers
        self.results: List[EvaluationResult] = []

    def evaluate_policy(self,
                        policy: BaseEstimator,
                        policy_name: str,
                        policy_version: str,
                        X_test: np.ndarray,
                        y_test: np.ndarray,
                        metrics: List[MetricType],
                        custom_metrics: Optional[Dict[str, Callable]] = None) -> EvaluationResult:
        """
        评估单个策略

        Args:
            policy: 策略模型
            policy_name: 策略名称
            policy_version: 策略版本
            X_test: 测试特征
            y_test: 测试标签
            metrics: 指标列表
            custom_metrics: 自定义指标字典

        Returns:
            评估结果
        """
        start_time = datetime.now()
        y_pred = policy.predict(X_test)
        end_time = datetime.now()
        evaluation_time = (end_time - start_time).total_seconds()

        metric_values = {}
        for metric in metrics:
            if metric == MetricType.ACCURACY:
                metric_values[metric.value] = accuracy_score(y_test, y_pred)
            elif metric == MetricType.PRECISION:
                metric_values[metric.value] = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            elif metric == MetricType.RECALL:
                metric_values[metric.value] = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            elif metric == MetricType.F1:
                metric_values[metric.value] = f1_score(y_test, y_pred, average='weighted', zero_division=0)
            elif metric == MetricType.MSE:
                metric_values[metric.value] = mean_squared_error(y_test, y_pred)
            elif metric == MetricType.RMSE:
                metric_values[metric.value] = np.sqrt(mean_squared_error(y_test, y_pred))

        if custom_metrics:
            for name, func in custom_metrics.items():
                metric_values[name] = func(y_test, y_pred)

        result = EvaluationResult(
            policy_name=policy_name,
            policy_version=policy_version,
            metrics=metric_values,
            evaluation_time=evaluation_time
        )

        logger.info(f"策略 {policy_name} v{policy_version} 评估完成: {metric_values}")
        return result

    def evaluate_parallel(self,
                          policies: List[Tuple[BaseEstimator, str, str]],
                          X_test: np.ndarray,
                          y_test: np.ndarray,
                          metrics: List[MetricType],
                          custom_metrics: Optional[Dict[str, Callable]] = None) -> List[EvaluationResult]:
        """
        并行评估多个策略

        Args:
            policies: 策略列表 [(policy, name, version)]
            X_test: 测试特征
            y_test: 测试标签
            metrics: 指标列表
            custom_metrics: 自定义指标字典

        Returns:
            评估结果列表
        """
        self.results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_policy = {
                executor.submit(
                    self.evaluate_policy,
                    policy, name, version, X_test, y_test, metrics, custom_metrics
                ): (name, version)
                for policy, name, version in policies
            }

            for future in concurrent.futures.as_completed(future_to_policy):
                name, version = future_to_policy[future]
                try:
                    result = future.result()
                    self.results.append(result)
                except Exception as e:
                    logger.error(f"策略 {name} v{version} 评估失败: {e}")

        return self.results

    def rank_policies(self,
                      primary_metric: str,
                      higher_is_better: bool = True) -> List[PolicyRank]:
        """
        对策略进行排名

        Args:
            primary_metric: 主指标名称
            higher_is_better: 指标值越高越好

        Returns:
            策略排名列表
        """
        if not self.results:
            logger.warning("没有评估结果可用于排名")
            return []

        sorted_results = sorted(
            self.results,
            key=lambda x: x.metrics.get(primary_metric, 0),
            reverse=higher_is_better
        )

        ranks = []
        for i, result in enumerate(sorted_results, 1):
            ranks.append(PolicyRank(
                policy_name=result.policy_name,
                policy_version=result.policy_version,
                rank=i,
                score=result.metrics.get(primary_metric, 0),
                evaluation_result=result
            ))

        return ranks

    def get_best_policy(self,
                        primary_metric: str,
                        higher_is_better: bool = True) -> Optional[PolicyRank]:
        """
        获取最佳策略

        Args:
            primary_metric: 主指标名称
            higher_is_better: 指标值越高越好

        Returns:
            最佳策略排名，None表示无结果
        """
        ranks = self.rank_policies(primary_metric, higher_is_better)
        return ranks[0] if ranks else None

    def get_results_by_policy(self, policy_name: str) -> List[EvaluationResult]:
        """
        获取指定策略的所有评估结果

        Args:
            policy_name: 策略名称

        Returns:
            评估结果列表
        """
        return [r for r in self.results if r.policy_name == policy_name]

    def clear_results(self) -> None:
        """清除所有评估结果"""
        self.results.clear()
        logger.info("评估结果已清除")
