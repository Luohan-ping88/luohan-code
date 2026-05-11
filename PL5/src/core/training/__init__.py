"""
训练优化器模块 - 智能训练优化系统

提供学习率调度、早停机制和训练优化功能
"""

from .lr_scheduler import (
    LRSchedulerType,
    LRSchedulerConfig,
    CosineAnnealingConfig,
    ReduceLROnPlateauConfig,
    StepLRConfig,
    ExponentialLRConfig,
    BaseLRScheduler,
    CosineAnnealingScheduler,
    ReduceLROnPlateauScheduler,
    StepLRScheduler,
    ExponentialLRScheduler,
    create_lr_scheduler,
)

from .early_stopping import (
    EarlyStoppingMode,
    EarlyStoppingStatus,
    EarlyStoppingConfig,
    EarlyStoppingState,
    EarlyStopping,
    AdaptiveEarlyStopping,
)

from .optimizer import OptimizerStatus, TrainingMetrics, ResourceUsage, TrainingOptimizerConfig, TrainingOptimizer

__all__ = [
    # 学习率调度器
    "LRSchedulerType",
    "LRSchedulerConfig",
    "CosineAnnealingConfig",
    "ReduceLROnPlateauConfig",
    "StepLRConfig",
    "ExponentialLRConfig",
    "BaseLRScheduler",
    "CosineAnnealingScheduler",
    "ReduceLROnPlateauScheduler",
    "StepLRScheduler",
    "ExponentialLRScheduler",
    "create_lr_scheduler",
    # 早停机制
    "EarlyStoppingMode",
    "EarlyStoppingStatus",
    "EarlyStoppingConfig",
    "EarlyStoppingState",
    "EarlyStopping",
    "AdaptiveEarlyStopping",
    # 训练优化器
    "OptimizerStatus",
    "TrainingMetrics",
    "ResourceUsage",
    "TrainingOptimizerConfig",
    "TrainingOptimizer",
]
