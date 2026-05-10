"""
A/B测试框架
管理实验配置、流量分流、指标收集和统计
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from enum import Enum
from datetime import datetime
import hashlib
import logging
import math

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """实验状态"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class Variant:
    """实验变体"""
    id: str
    name: str
    description: str
    traffic_percentage: float
    config: Dict[str, Any] = field(default_factory=dict)
    is_control: bool = False


@dataclass
class MetricValue:
    """指标值"""
    metric_name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """实验结果"""
    experiment_id: str
    variant_id: str
    metric_name: str
    count: int = 0
    sum_value: float = 0.0
    sum_squared: float = 0.0
    min_value: float = float('inf')
    max_value: float = -float('inf')

    @property
    def mean(self) -> float:
        if self.count == 0:
            return 0.0
        return self.sum_value / self.count

    @property
    def variance(self) -> float:
        if self.count == 0:
            return 0.0
        mean = self.mean
        return (self.sum_squared / self.count) - mean ** 2

    @property
    def std_dev(self) -> float:
        return math.sqrt(max(self.variance, 0.0))


@dataclass
class Experiment:
    """A/B实验"""
    id: str
    name: str
    description: str
    status: ExperimentStatus
    variants: List[Variant]
    metrics: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    results: Dict[str, Dict[str, ExperimentResult]] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = ExperimentStatus(self.status)


class ABTestFramework:
    """A/B测试框架"""

    def __init__(self):
        self._experiments: Dict[str, Experiment] = {}
        self._variant_assignments: Dict[str, Dict[str, str]] = {}

    def create_experiment(self,
                          experiment_id: str,
                          name: str,
                          description: str,
                          variants: List[Variant],
                          metrics: List[str],
                          config: Optional[Dict[str, Any]] = None) -> Optional[Experiment]:
        """
        创建A/B实验

        Args:
            experiment_id: 实验ID
            name: 实验名称
            description: 实验描述
            variants: 变体列表
            metrics: 指标列表
            config: 实验配置

        Returns:
            创建的实验，失败返回 None
        """
        if experiment_id in self._experiments:
            logger.error(f"实验已存在: {experiment_id}")
            return None

        total_traffic = sum(v.traffic_percentage for v in variants)
        if not (99.99 <= total_traffic <= 100.01):
            logger.error(f"流量分配总和必须为100%，当前为: {total_traffic}%")
            return None

        if not any(v.is_control for v in variants):
            logger.warning("实验没有设置对照组")

        experiment = Experiment(
            id=experiment_id,
            name=name,
            description=description,
            status=ExperimentStatus.DRAFT,
            variants=variants,
            metrics=metrics,
            config=config or {}
        )

        self._experiments[experiment_id] = experiment
        logger.info(f"创建实验: {experiment_id}")
        return experiment

    def start_experiment(self, experiment_id: str) -> bool:
        """
        启动实验

        Args:
            experiment_id: 实验ID

        Returns:
            启动是否成功
        """
        if experiment_id not in self._experiments:
            logger.error(f"实验不存在: {experiment_id}")
            return False

        experiment = self._experiments[experiment_id]
        if experiment.status == ExperimentStatus.RUNNING:
            logger.warning(f"实验已经在运行: {experiment_id}")
            return True

        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now()
        logger.info(f"启动实验: {experiment_id}")
        return True

    def pause_experiment(self, experiment_id: str) -> bool:
        """
        暂停实验

        Args:
            experiment_id: 实验ID

        Returns:
            暂停是否成功
        """
        if experiment_id not in self._experiments:
            logger.error(f"实验不存在: {experiment_id}")
            return False

        experiment = self._experiments[experiment_id]
        if experiment.status != ExperimentStatus.RUNNING:
            logger.warning(f"实验不是运行状态: {experiment_id}")
            return False

        experiment.status = ExperimentStatus.PAUSED
        logger.info(f"暂停实验: {experiment_id}")
        return True

    def end_experiment(self, experiment_id: str) -> bool:
        """
        结束实验

        Args:
            experiment_id: 实验ID

        Returns:
            结束是否成功
        """
        if experiment_id not in self._experiments:
            logger.error(f"实验不存在: {experiment_id}")
            return False

        experiment = self._experiments[experiment_id]
        if experiment.status in [ExperimentStatus.COMPLETED, ExperimentStatus.ARCHIVED]:
            logger.warning(f"实验已经结束: {experiment_id}")
            return True

        experiment.status = ExperimentStatus.COMPLETED
        experiment.ended_at = datetime.now()
        logger.info(f"结束实验: {experiment_id}")
        return True

    def assign_variant(self, experiment_id: str, user_id: str) -> Optional[Variant]:
        """
        为用户分配实验变体

        Args:
            experiment_id: 实验ID
            user_id: 用户ID

        Returns:
            分配的变体，失败返回 None
        """
        if experiment_id not in self._experiments:
            logger.error(f"实验不存在: {experiment_id}")
            return None

        experiment = self._experiments[experiment_id]
        if experiment.status != ExperimentStatus.RUNNING:
            logger.warning(f"实验不是运行状态: {experiment_id}")
            return None

        if experiment_id not in self._variant_assignments:
            self._variant_assignments[experiment_id] = {}

        if user_id in self._variant_assignments[experiment_id]:
            variant_id = self._variant_assignments[experiment_id][user_id]
            variant = next((v for v in experiment.variants if v.id == variant_id), None)
            return variant

        hash_value = self._hash_user_id(experiment_id, user_id)
        traffic_value = (hash_value % 10000) / 100.0

        cumulative = 0.0
        selected_variant = None
        for variant in experiment.variants:
            cumulative += variant.traffic_percentage
            if traffic_value < cumulative:
                selected_variant = variant
                break

        if selected_variant is None:
            selected_variant = experiment.variants[-1]

        self._variant_assignments[experiment_id][user_id] = selected_variant.id
        return selected_variant

    def record_metric(self, experiment_id: str, user_id: str,
                      metric_name: str, value: float,
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        记录指标值

        Args:
            experiment_id: 实验ID
            user_id: 用户ID
            metric_name: 指标名称
            value: 指标值
            metadata: 附加元数据

        Returns:
            记录是否成功
        """
        if experiment_id not in self._experiments:
            logger.error(f"实验不存在: {experiment_id}")
            return False

        experiment = self._experiments[experiment_id]
        if experiment.status != ExperimentStatus.RUNNING:
            logger.warning(f"实验不是运行状态: {experiment_id}")
            return False

        if metric_name not in experiment.metrics:
            logger.warning(f"指标不在实验中: {metric_name}")

        variant = self.assign_variant(experiment_id, user_id)
        if not variant:
            return False

        if experiment_id not in experiment.results:
            experiment.results[experiment_id] = {}

        if variant.id not in experiment.results[experiment_id]:
            experiment.results[experiment_id][variant.id] = {}

        if metric_name not in experiment.results[experiment_id][variant.id]:
            experiment.results[experiment_id][variant.id][metric_name] = ExperimentResult(
                experiment_id=experiment_id,
                variant_id=variant.id,
                metric_name=metric_name
            )

        result = experiment.results[experiment_id][variant.id][metric_name]
        result.count += 1
        result.sum_value += value
        result.sum_squared += value ** 2
        result.min_value = min(result.min_value, value)
        result.max_value = max(result.max_value, value)

        return True

    def get_experiment_results(self, experiment_id: str) -> Optional[Dict[str, Dict[str, ExperimentResult]]]:
        """
        获取实验结果

        Args:
            experiment_id: 实验ID

        Returns:
            实验结果，失败返回 None
        """
        if experiment_id not in self._experiments:
            logger.error(f"实验不存在: {experiment_id}")
            return None

        return self._experiments[experiment_id].results

    def list_experiments(self, status: Optional[ExperimentStatus] = None) -> List[Experiment]:
        """
        列出所有实验

        Args:
            status: 按状态过滤（可选）

        Returns:
            实验列表
        """
        experiments = list(self._experiments.values())
        if status:
            experiments = [e for e in experiments if e.status == status]
        return sorted(experiments, key=lambda e: e.created_at, reverse=True)

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """
        获取指定实验

        Args:
            experiment_id: 实验ID

        Returns:
            实验，不存在返回 None
        """
        return self._experiments.get(experiment_id)

    def delete_experiment(self, experiment_id: str) -> bool:
        """
        删除实验

        Args:
            experiment_id: 实验ID

        Returns:
            删除是否成功
        """
        if experiment_id not in self._experiments:
            logger.error(f"实验不存在: {experiment_id}")
            return False

        del self._experiments[experiment_id]
        if experiment_id in self._variant_assignments:
            del self._variant_assignments[experiment_id]

        logger.info(f"删除实验: {experiment_id}")
        return True

    def _hash_user_id(self, experiment_id: str, user_id: str) -> int:
        """
        哈希用户ID用于变体分配

        Args:
            experiment_id: 实验ID
            user_id: 用户ID

        Returns:
            哈希值
        """
        combined = f"{experiment_id}:{user_id}".encode('utf-8')
        hash_obj = hashlib.md5(combined)
        return int(hash_obj.hexdigest(), 16)

    def clear(self) -> None:
        """清空所有实验数据"""
        self._experiments.clear()
        self._variant_assignments.clear()
        logger.info("A/B测试框架已清空")


_global_ab_framework: Optional[ABTestFramework] = None


def get_global_ab_framework() -> ABTestFramework:
    """获取全局A/B测试框架"""
    global _global_ab_framework
    if _global_ab_framework is None:
        _global_ab_framework = ABTestFramework()
    return _global_ab_framework
