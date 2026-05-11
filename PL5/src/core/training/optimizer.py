"""
训练优化器模块 - 集成学习率调度器和早停机制的训练优化器
"""

import numpy as np
import time
import psutil
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import deque

from .lr_scheduler import BaseLRScheduler, LRSchedulerType, create_lr_scheduler, LRSchedulerConfig
from .early_stopping import EarlyStopping, EarlyStoppingConfig, EarlyStoppingMode, AdaptiveEarlyStopping

logger = logging.getLogger(__name__)


class OptimizerStatus(Enum):
    """优化器状态枚举"""

    IDLE = "idle"
    TRAINING = "training"
    VALIDATING = "validating"
    PAUSED = "paused"
    COMPLETED = "completed"
    EARLY_STOPPED = "early_stopped"
    ERROR = "error"


@dataclass
class TrainingMetrics:
    """训练指标"""

    epoch: int = 0
    train_loss: Optional[float] = None
    train_score: Optional[float] = None
    val_loss: Optional[float] = None
    val_score: Optional[float] = None
    learning_rate: Optional[float] = None
    duration_seconds: float = 0.0
    extra_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceUsage:
    """资源使用情况"""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    disk_usage_percent: float = 0.0
    timestamp: float = 0.0


@dataclass
class TrainingOptimizerConfig:
    """训练优化器配置"""

    max_epochs: int = 100
    verbose: bool = True
    log_interval: int = 1
    checkpoint_interval: int = 10
    use_early_stopping: bool = True
    use_lr_scheduler: bool = True
    early_stopping_config: Optional[EarlyStoppingConfig] = None
    lr_scheduler_type: LRSchedulerType = LRSchedulerType.REDUCE_LR_ON_PLATEAU
    lr_scheduler_config: Optional[Dict[str, Any]] = None
    use_adaptive_early_stopping: bool = False
    track_resources: bool = True
    resource_monitor_interval: float = 5.0
    progress_window_size: int = 20


class TrainingOptimizer:
    """
    智能训练优化器

    集成学习率调度器、早停机制、进度监控和资源管理
    """

    def __init__(self, config: Optional[TrainingOptimizerConfig] = None):
        """
        初始化训练优化器

        Args:
            config: 优化器配置
        """
        self.config = config or TrainingOptimizerConfig()
        self.status = OptimizerStatus.IDLE

        self.early_stopping: Optional[EarlyStopping] = None
        self.lr_scheduler: Optional[BaseLRScheduler] = None
        self._init_components()

        self.current_epoch = 0
        self.best_epoch = 0
        self.best_val_score: Optional[float] = None
        self.training_history: List[TrainingMetrics] = []
        self.resource_history: List[ResourceUsage] = []

        self._start_time: Optional[float] = None
        self._epoch_start_time: Optional[float] = None
        self._resource_monitor_start_time: Optional[float] = None

        self._progress_queue: deque = deque(maxlen=self.config.progress_window_size)

    def _init_components(self) -> None:
        """初始化各组件"""
        if self.config.use_early_stopping:
            es_config = self.config.early_stopping_config or EarlyStoppingConfig()
            if self.config.use_adaptive_early_stopping:
                self.early_stopping = AdaptiveEarlyStopping(es_config)
            else:
                self.early_stopping = EarlyStopping(es_config)

        if self.config.use_lr_scheduler:
            lr_config = self.config.lr_scheduler_config or {}
            self.lr_scheduler = create_lr_scheduler(self.config.lr_scheduler_type, lr_config)

    def start_training(self) -> None:
        """开始训练"""
        self.status = OptimizerStatus.TRAINING
        self._start_time = time.time()
        self.current_epoch = 0
        self.training_history = []
        self.resource_history = []

        if self.early_stopping:
            self.early_stopping.start()

        if self.lr_scheduler:
            self.lr_scheduler.reset()

        if self.config.verbose:
            logger.info("TrainingOptimizer: 开始训练")

    def start_epoch(self) -> None:
        """开始一个 epoch"""
        self.status = OptimizerStatus.TRAINING
        self._epoch_start_time = time.time()
        self.current_epoch += 1

    def end_epoch(
        self,
        train_loss: Optional[float] = None,
        train_score: Optional[float] = None,
        val_loss: Optional[float] = None,
        val_score: Optional[float] = None,
        extra_metrics: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, TrainingMetrics]:
        """
        结束一个 epoch

        Args:
            train_loss: 训练损失
            train_score: 训练分数
            val_loss: 验证损失
            val_score: 验证分数
            extra_metrics: 额外指标

        Returns:
            (是否应该停止, 训练指标)
        """
        epoch_duration = time.time() - self._epoch_start_time if self._epoch_start_time else 0

        current_lr = self.lr_scheduler.get_lr() if self.lr_scheduler else None

        metrics = TrainingMetrics(
            epoch=self.current_epoch,
            train_loss=train_loss,
            train_score=train_score,
            val_loss=val_loss,
            val_score=val_score,
            learning_rate=current_lr,
            duration_seconds=epoch_duration,
            extra_metrics=extra_metrics or {},
        )

        self.training_history.append(metrics)
        self._update_progress_queue(metrics)

        should_stop = False

        if val_score is not None:
            if self.early_stopping:
                es_metrics = {"loss": val_loss} if val_loss else {}
                should_stop = self.early_stopping.step(self.current_epoch, val_score, es_metrics)

                if self.early_stopping.get_best_score() is not None:
                    self.best_val_score = self.early_stopping.get_best_score()
                    self.best_epoch = self.early_stopping.get_best_epoch()

            if self.lr_scheduler:
                lr_metrics = {"score": val_score}
                self.lr_scheduler.step(self.current_epoch, lr_metrics)

        if self.config.track_resources:
            self._record_resource_usage()

        if self.config.verbose and self.current_epoch % self.config.log_interval == 0:
            self._log_epoch_metrics(metrics)

        if should_stop:
            self.status = OptimizerStatus.EARLY_STOPPED
        elif self.current_epoch >= self.config.max_epochs:
            self.status = OptimizerStatus.COMPLETED
            should_stop = True

        return should_stop, metrics

    def _update_progress_queue(self, metrics: TrainingMetrics) -> None:
        """更新进度队列"""
        if metrics.val_score is not None:
            self._progress_queue.append(metrics.val_score)

    def _record_resource_usage(self) -> None:
        """记录资源使用情况"""
        try:
            process = psutil.Process()
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_used_mb = memory_info.rss / 1024 / 1024

            memory_percent = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage("/").percent

            usage = ResourceUsage(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                disk_usage_percent=disk_usage,
                timestamp=time.time(),
            )
            self.resource_history.append(usage)
        except Exception as e:
            logger.warning(f"TrainingOptimizer: 无法记录资源使用情况: {e}")

    def _log_epoch_metrics(self, metrics: TrainingMetrics) -> None:
        """记录 epoch 指标"""
        log_parts = [f"Epoch {metrics.epoch}/{self.config.max_epochs}"]

        if metrics.train_loss is not None:
            log_parts.append(f"train_loss={metrics.train_loss:.4f}")
        if metrics.train_score is not None:
            log_parts.append(f"train_score={metrics.train_score:.4f}")
        if metrics.val_loss is not None:
            log_parts.append(f"val_loss={metrics.val_loss:.4f}")
        if metrics.val_score is not None:
            log_parts.append(f"val_score={metrics.val_score:.4f}")
        if metrics.learning_rate is not None:
            log_parts.append(f"lr={metrics.learning_rate:.6f}")

        log_parts.append(f"duration={metrics.duration_seconds:.2f}s")

        logger.info("TrainingOptimizer: " + " | ".join(log_parts))

    def get_current_lr(self) -> Optional[float]:
        """获取当前学习率"""
        return self.lr_scheduler.get_lr() if self.lr_scheduler else None

    def get_best_metrics(self) -> Optional[TrainingMetrics]:
        """获取最佳指标"""
        if not self.training_history:
            return None

        if self.best_epoch > 0:
            for metrics in self.training_history:
                if metrics.epoch == self.best_epoch:
                    return metrics

        return None

    def get_training_history(self) -> List[TrainingMetrics]:
        """获取训练历史"""
        return self.training_history

    def get_resource_history(self) -> List[ResourceUsage]:
        """获取资源历史"""
        return self.resource_history

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_time = time.time() - self._start_time if self._start_time else 0
        avg_epoch_time = np.mean([m.duration_seconds for m in self.training_history]) if self.training_history else 0

        stats = {
            "status": self.status.value,
            "current_epoch": self.current_epoch,
            "max_epochs": self.config.max_epochs,
            "best_epoch": self.best_epoch,
            "best_val_score": self.best_val_score,
            "total_time_seconds": total_time,
            "avg_epoch_time_seconds": avg_epoch_time,
            "total_epochs_completed": len(self.training_history),
            "early_stopping_enabled": self.config.use_early_stopping,
            "lr_scheduler_enabled": self.config.use_lr_scheduler,
        }

        if self.early_stopping:
            stats["early_stopping"] = self.early_stopping.get_statistics()

        return stats

    def pause(self) -> None:
        """暂停训练"""
        if self.status == OptimizerStatus.TRAINING:
            self.status = OptimizerStatus.PAUSED
            if self.config.verbose:
                logger.info("TrainingOptimizer: 训练已暂停")

    def resume(self) -> None:
        """恢复训练"""
        if self.status == OptimizerStatus.PAUSED:
            self.status = OptimizerStatus.TRAINING
            if self.config.verbose:
                logger.info("TrainingOptimizer: 训练已恢复")

    def reset(self) -> None:
        """重置优化器"""
        self.status = OptimizerStatus.IDLE
        self.current_epoch = 0
        self.best_epoch = 0
        self.best_val_score = None
        self.training_history = []
        self.resource_history = []
        self._start_time = None
        self._epoch_start_time = None
        self._progress_queue.clear()

        if self.early_stopping:
            self.early_stopping.reset()
        if self.lr_scheduler:
            self.lr_scheduler.reset()

    def fit(
        self,
        train_fn: Callable[[int, float], Tuple[Optional[float], Optional[float], Dict[str, Any]]],
        val_fn: Optional[Callable[[], Tuple[Optional[float], Optional[float], Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        完整训练循环

        Args:
            train_fn: 训练函数 (epoch, lr) -> (loss, score, metrics)
            val_fn: 验证函数 -> (loss, score, metrics)

        Returns:
            训练结果
        """
        self.start_training()

        try:
            for epoch in range(self.config.max_epochs):
                self.start_epoch()

                current_lr = self.get_current_lr() or 0.001
                train_loss, train_score, train_metrics = train_fn(self.current_epoch, current_lr)

                val_loss, val_score, val_metrics = None, None, {}
                if val_fn:
                    self.status = OptimizerStatus.VALIDATING
                    val_loss, val_score, val_metrics = val_fn()

                extra_metrics = {**train_metrics, **val_metrics}

                should_stop, metrics = self.end_epoch(
                    train_loss=train_loss,
                    train_score=train_score,
                    val_loss=val_loss,
                    val_score=val_score,
                    extra_metrics=extra_metrics,
                )

                if should_stop:
                    break

        except Exception as e:
            self.status = OptimizerStatus.ERROR
            logger.error(f"TrainingOptimizer: 训练过程出错: {e}")
            raise

        return self.get_statistics()
