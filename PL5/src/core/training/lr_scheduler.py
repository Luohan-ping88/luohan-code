"""
学习率调度器模块 - 提供多种学习率调度策略
"""

import math
import numpy as np
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LRSchedulerType(Enum):
    """学习率调度器类型枚举"""
    COSINE_ANNEALING = "cosine_annealing"
    REDUCE_LR_ON_PLATEAU = "reduce_lr_on_plateau"
    STEP_LR = "step_lr"
    EXPONENTIAL_LR = "exponential_lr"


@dataclass
class LRSchedulerConfig:
    """学习率调度器配置基类"""
    initial_lr: float = 0.001
    min_lr: float = 1e-7
    max_lr: float = 0.1


@dataclass
class CosineAnnealingConfig(LRSchedulerConfig):
    """Cosine Annealing 调度器配置"""
    t_max: int = 100
    eta_min: float = 1e-7


@dataclass
class ReduceLROnPlateauConfig(LRSchedulerConfig):
    """ReduceLROnPlateau 调度器配置"""
    factor: float = 0.1
    patience: int = 10
    threshold: float = 1e-4
    threshold_mode: str = "rel"
    cooldown: int = 0
    min_lr: float = 1e-7
    mode: str = "min"


@dataclass
class StepLRConfig(LRSchedulerConfig):
    """StepLR 调度器配置"""
    step_size: int = 10
    gamma: float = 0.1


@dataclass
class ExponentialLRConfig(LRSchedulerConfig):
    """ExponentialLR 调度器配置"""
    gamma: float = 0.9


class BaseLRScheduler:
    """学习率调度器基类"""
    
    def __init__(self, config: LRSchedulerConfig):
        self.config = config
        self.current_lr: float = config.initial_lr
        self.last_epoch: int = -1
        self.history: List[float] = []
        
    def step(self, epoch: Optional[int] = None, metrics: Optional[Dict[str, float]] = None) -> float:
        """
        更新学习率
        
        Args:
            epoch: 当前 epoch
            metrics: 验证集指标
            
        Returns:
            更新后的学习率
        """
        if epoch is not None:
            self.last_epoch = epoch
        else:
            self.last_epoch += 1
            
        self.current_lr = self._compute_lr()
        self.history.append(self.current_lr)
        return self.current_lr
        
    def _compute_lr(self) -> float:
        """计算当前学习率，由子类实现"""
        raise NotImplementedError
        
    def get_lr(self) -> float:
        """获取当前学习率"""
        return self.current_lr
        
    def reset(self) -> None:
        """重置调度器"""
        self.current_lr = self.config.initial_lr
        self.last_epoch = -1
        self.history = []


class CosineAnnealingScheduler(BaseLRScheduler):
    """Cosine Annealing 学习率调度器"""
    
    def __init__(self, config: CosineAnnealingConfig):
        super().__init__(config)
        self.t_max = config.t_max
        self.eta_min = config.eta_min
        
    def _compute_lr(self) -> float:
        if self.last_epoch == 0:
            return self.config.initial_lr
            
        progress = self.last_epoch / self.t_max
        cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))
        lr = self.eta_min + (self.config.initial_lr - self.eta_min) * cosine_decay
        return max(lr, self.config.min_lr)


class ReduceLROnPlateauScheduler(BaseLRScheduler):
    """ReduceLROnPlateau 学习率调度器"""
    
    def __init__(self, config: ReduceLROnPlateauConfig):
        super().__init__(config)
        self.factor = config.factor
        self.patience = config.patience
        self.threshold = config.threshold
        self.threshold_mode = config.threshold_mode
        self.cooldown = config.cooldown
        self.mode = config.mode
        
        self.cooldown_counter = 0
        self.best = -float('inf') if self.mode == 'max' else float('inf')
        self.num_bad_epochs = 0
        
    def _is_better(self, current: float, best: float) -> bool:
        if self.mode == 'min':
            if self.threshold_mode == 'rel':
                rel_epsilon = 1. - self.threshold
                return current < best * rel_epsilon
            else:
                return current < best - self.threshold
        else:
            if self.threshold_mode == 'rel':
                rel_epsilon = self.threshold + 1.
                return current > best * rel_epsilon
            else:
                return current > best + self.threshold
                
    def _compute_lr(self) -> float:
        return self.current_lr
        
    def step(self, epoch: Optional[int] = None, metrics: Optional[Dict[str, float]] = None) -> float:
        if metrics is None or 'score' not in metrics:
            return self.current_lr
            
        current = metrics['score']
        
        if epoch is not None:
            self.last_epoch = epoch
        else:
            self.last_epoch += 1
            
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            self.num_bad_epochs = 0
        elif self._is_better(current, self.best):
            self.best = current
            self.num_bad_epochs = 0
        else:
            self.num_bad_epochs += 1
            if self.num_bad_epochs > self.patience:
                new_lr = max(self.current_lr * self.factor, self.config.min_lr)
                logger.info(f"ReduceLROnPlateau: 学习率从 {self.current_lr:.6f} 调整到 {new_lr:.6f}")
                self.current_lr = new_lr
                self.cooldown_counter = self.cooldown
                self.num_bad_epochs = 0
                
        self.history.append(self.current_lr)
        return self.current_lr


class StepLRScheduler(BaseLRScheduler):
    """StepLR 学习率调度器"""
    
    def __init__(self, config: StepLRConfig):
        super().__init__(config)
        self.step_size = config.step_size
        self.gamma = config.gamma
        
    def _compute_lr(self) -> float:
        num_steps = self.last_epoch // self.step_size
        lr = self.config.initial_lr * (self.gamma ** num_steps)
        return max(lr, self.config.min_lr)


class ExponentialLRScheduler(BaseLRScheduler):
    """ExponentialLR 学习率调度器"""
    
    def __init__(self, config: ExponentialLRConfig):
        super().__init__(config)
        self.gamma = config.gamma
        
    def _compute_lr(self) -> float:
        lr = self.config.initial_lr * (self.gamma ** self.last_epoch)
        return max(lr, self.config.min_lr)


def create_lr_scheduler(
    scheduler_type: LRSchedulerType,
    config: Optional[Dict[str, Any]] = None
) -> BaseLRScheduler:
    """
    工厂函数：创建学习率调度器
    
    Args:
        scheduler_type: 调度器类型
        config: 配置参数
        
    Returns:
        学习率调度器实例
    """
    if config is None:
        config = {}
        
    if scheduler_type == LRSchedulerType.COSINE_ANNEALING:
        cfg = CosineAnnealingConfig(**config)
        return CosineAnnealingScheduler(cfg)
    elif scheduler_type == LRSchedulerType.REDUCE_LR_ON_PLATEAU:
        cfg = ReduceLROnPlateauConfig(**config)
        return ReduceLROnPlateauScheduler(cfg)
    elif scheduler_type == LRSchedulerType.STEP_LR:
        cfg = StepLRConfig(**config)
        return StepLRScheduler(cfg)
    elif scheduler_type == LRSchedulerType.EXPONENTIAL_LR:
        cfg = ExponentialLRConfig(**config)
        return ExponentialLRScheduler(cfg)
    else:
        raise ValueError(f"未知的调度器类型: {scheduler_type}")
