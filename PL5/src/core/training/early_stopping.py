"""
智能早停机制模块 - 基于验证集性能的早停策略
"""

import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class EarlyStoppingMode(Enum):
    """早停模式枚举"""

    MIN = "min"
    MAX = "max"


class EarlyStoppingStatus(Enum):
    """早停状态枚举"""

    NOT_STARTED = "not_started"
    TRAINING = "training"
    IMPROVED = "improved"
    NO_IMPROVEMENT = "no_improvement"
    STOPPED = "stopped"


@dataclass
class EarlyStoppingConfig:
    """早停机制配置"""

    patience: int = 10
    min_delta: float = 1e-4
    mode: EarlyStoppingMode = EarlyStoppingMode.MIN
    verbose: bool = True
    restore_best_weights: bool = True
    baseline: Optional[float] = None
    start_from_epoch: int = 0
    threshold: float = 0.0
    cooldown: int = 0


@dataclass
class EarlyStoppingState:
    """早停机制状态"""

    status: EarlyStoppingStatus = EarlyStoppingStatus.NOT_STARTED
    best_score: Optional[float] = None
    best_epoch: int = 0
    wait: int = 0
    cooldown_counter: int = 0
    stopped_epoch: Optional[int] = None
    improvement_history: List[Dict[str, Any]] = None
    validation_history: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.improvement_history is None:
            self.improvement_history = []
        if self.validation_history is None:
            self.validation_history = []


class EarlyStopping:
    """
    智能早停机制类

    基于验证集性能监控，当性能不再改善时提前停止训练
    """

    def __init__(self, config: Optional[EarlyStoppingConfig] = None):
        """
        初始化早停机制

        Args:
            config: 早停配置
        """
        self.config = config or EarlyStoppingConfig()
        self.state = EarlyStoppingState()
        self._start_time: Optional[float] = None

    def _is_improvement(self, current: float, best: float) -> bool:
        """
        判断当前值是否比最佳值更好

        Args:
            current: 当前值
            best: 最佳值

        Returns:
            是否有改善
        """
        if self.config.mode == EarlyStoppingMode.MIN:
            return current < best - self.config.min_delta
        else:
            return current > best + self.config.min_delta

    def _is_better_than_baseline(self, current: float) -> bool:
        """
        判断当前值是否优于基线

        Args:
            current: 当前值

        Returns:
            是否优于基线
        """
        if self.config.baseline is None:
            return True

        if self.config.mode == EarlyStoppingMode.MIN:
            return current < self.config.baseline
        else:
            return current > self.config.baseline

    def start(self) -> None:
        """开始训练监控"""
        self.state = EarlyStoppingState()
        self.state.status = EarlyStoppingStatus.TRAINING
        self._start_time = time.time()

        if self.config.baseline is not None:
            self.state.best_score = self.config.baseline
            if self.config.verbose:
                logger.info(
                    f"EarlyStopping: 使用基线值 {self.config.baseline}"
                )

    def step(
        self,
        epoch: int,
        validation_score: float,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        更新早停状态

        Args:
            epoch: 当前 epoch
            validation_score: 验证集分数
            metrics: 其他指标

        Returns:
            是否应该停止训练
        """
        if self.state.status == EarlyStoppingStatus.NOT_STARTED:
            self.start()

        if self.state.status == EarlyStoppingStatus.STOPPED:
            return True

        if epoch < self.config.start_from_epoch:
            self._record_validation(epoch, validation_score, metrics)
            return False

        if self.state.cooldown_counter > 0:
            self.state.cooldown_counter -= 1
            self.state.status = EarlyStoppingStatus.NO_IMPROVEMENT
            self._record_validation(epoch, validation_score, metrics)
            return False

        if self.state.best_score is None:
            if not self._is_better_than_baseline(validation_score):
                self.state.status = EarlyStoppingStatus.NO_IMPROVEMENT
                self._record_validation(epoch, validation_score, metrics)
                return False

            self.state.best_score = validation_score
            self.state.best_epoch = epoch
            self.state.status = EarlyStoppingStatus.IMPROVED
            self._record_improvement(epoch, validation_score, metrics)
            self._record_validation(epoch, validation_score, metrics)
            return False

        if self._is_improvement(validation_score, self.state.best_score):
            improvement = abs(validation_score - self.state.best_score)
            self.state.best_score = validation_score
            self.state.best_epoch = epoch
            self.state.wait = 0
            self.state.status = EarlyStoppingStatus.IMPROVED
            self._record_improvement(
                epoch, validation_score, metrics, improvement
            )

            if self.config.verbose:
                logger.info(
                    f"EarlyStopping: Epoch {epoch}: 验证集分数改善 "
                    f"({self.state.best_score:.6f}). 保存最佳模型."
                )
        else:
            self.state.wait += 1
            self.state.status = EarlyStoppingStatus.NO_IMPROVEMENT

            if self.config.verbose:
                logger.info(
                    f"EarlyStopping: Epoch {epoch}: 验证集分数未改善. "
                    f"等待次数: {self.state.wait}/{self.config.patience}"
                )

            if self.state.wait >= self.config.patience:
                self.state.stopped_epoch = epoch
                self.state.status = EarlyStoppingStatus.STOPPED
                self.state.cooldown_counter = self.config.cooldown

                if self.config.verbose:
                    elapsed_time = (
                        time.time() - self._start_time
                        if self._start_time
                        else 0
                    )
                    logger.info(
                        f"EarlyStopping: 在 Epoch {epoch} 时早停. "
                        f"最佳 Epoch 是 {self.state.best_epoch}, "
                        f"最佳分数是 {self.state.best_score:.6f}. "
                        f"总训练时间: {elapsed_time:.2f}s"
                    )

        self._record_validation(epoch, validation_score, metrics)
        return self.state.status == EarlyStoppingStatus.STOPPED

    def _record_improvement(
        self,
        epoch: int,
        score: float,
        metrics: Optional[Dict[str, Any]] = None,
        improvement: Optional[float] = None,
    ) -> None:
        """记录性能改善"""
        record = {
            "epoch": epoch,
            "score": score,
            "improvement": improvement,
            "metrics": metrics or {},
            "timestamp": time.time(),
        }
        self.state.improvement_history.append(record)

    def _record_validation(
        self,
        epoch: int,
        score: float,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录验证结果"""
        record = {
            "epoch": epoch,
            "score": score,
            "metrics": metrics or {},
            "status": self.state.status.value,
            "timestamp": time.time(),
        }
        self.state.validation_history.append(record)

    def should_stop(self) -> bool:
        """判断是否应该停止训练"""
        return self.state.status == EarlyStoppingStatus.STOPPED

    def get_best_score(self) -> Optional[float]:
        """获取最佳分数"""
        return self.state.best_score

    def get_best_epoch(self) -> int:
        """获取最佳 epoch"""
        return self.state.best_epoch

    def get_state(self) -> EarlyStoppingState:
        """获取当前状态"""
        return self.state

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self._start_time is None:
            elapsed_time = 0
        else:
            elapsed_time = time.time() - self._start_time

        return {
            "status": self.state.status.value,
            "best_score": self.state.best_score,
            "best_epoch": self.state.best_epoch,
            "wait": self.state.wait,
            "patience": self.config.patience,
            "stopped_epoch": self.state.stopped_epoch,
            "total_improvements": len(self.state.improvement_history),
            "total_validations": len(self.state.validation_history),
            "elapsed_time_seconds": elapsed_time,
        }

    def reset(self) -> None:
        """重置早停机制"""
        self.state = EarlyStoppingState()
        self._start_time = None

    def get_validation_history(self) -> List[Dict[str, Any]]:
        """获取验证历史"""
        return self.state.validation_history

    def get_improvement_history(self) -> List[Dict[str, Any]]:
        """获取改善历史"""
        return self.state.improvement_history


class AdaptiveEarlyStopping(EarlyStopping):
    """
    自适应早停机制

    根据训练过程动态调整 patience 和 min_delta
    """

    def __init__(
        self,
        config: Optional[EarlyStoppingConfig] = None,
        adaptive_patience: bool = True,
        adaptive_min_delta: bool = True,
        window_size: int = 10,
    ):
        super().__init__(config)
        self.adaptive_patience = adaptive_patience
        self.adaptive_min_delta = adaptive_min_delta
        self.window_size = window_size
        self._original_patience = self.config.patience
        self._original_min_delta = self.config.min_delta

    def step(
        self,
        epoch: int,
        validation_score: float,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if epoch > self.window_size:
            self._adapt_parameters(epoch)

        return super().step(epoch, validation_score, metrics)

    def _adapt_parameters(self, epoch: int) -> None:
        """自适应调整参数"""
        recent_history = self.state.validation_history[-self.window_size :]

        if len(recent_history) < self.window_size:
            return

        scores = [h["score"] for h in recent_history]
        score_std = np.std(scores)

        if self.adaptive_patience:
            if score_std < self._original_min_delta:
                new_patience = max(5, self._original_patience // 2)
            else:
                new_patience = self._original_patience

            if new_patience != self.config.patience:
                self.config.patience = new_patience
                if self.config.verbose:
                    logger.info(
                        f"AdaptiveEarlyStopping: patience 调整为 {new_patience}"
                    )

        if self.adaptive_min_delta:
            new_min_delta = max(1e-6, score_std * 0.1)
            if abs(new_min_delta - self.config.min_delta) > 1e-6:
                self.config.min_delta = new_min_delta
                if self.config.verbose:
                    logger.info(
                        f"AdaptiveEarlyStopping: min_delta 调整为 {new_min_delta:.6f}"
                    )
