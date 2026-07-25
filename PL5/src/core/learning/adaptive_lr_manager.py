"""
自适应学习率管理器模块 V1.0

基于训练过程中的性能反馈自动优化学习率调度策略，提供以下核心能力：
1. 性能反馈驱动的学习率调整 - 监控损失和准确率，自动升降学习率
2. 学习率调度策略自动选择 - 根据训练阶段（初期/中期/后期/平台期）选择最佳调度器
3. 学习率历史分析 - 记录变化历史，分析最佳学习率区间，优化初始学习率
4. 多模型协同学习率管理 - 为万/千/百/十/个位模型独立管理并差异化调整

依赖现有的 src.core.training.lr_scheduler 模块提供的基础调度器。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.core.training.lr_scheduler import (
    create_lr_scheduler,
    LRSchedulerType,
    LRSchedulerConfig,
)

logger = logging.getLogger(__name__)

# 五个位置模型标识（万/千/百/十/个）
DEFAULT_POSITIONS: Tuple[str, ...] = ("wan", "qian", "bai", "shi", "ge")


class TrainingPhase(Enum):
    """训练阶段枚举"""
    EARLY = "early"        # 初期：快速收敛阶段，使用较高学习率
    MIDDLE = "middle"      # 中期：稳定优化阶段，逐步降低学习率
    LATE = "late"          # 后期：精细调优阶段，使用余弦退火
    PLATEAU = "plateau"    # 平台期：损失停滞，切换到 ReduceLROnPlateau


class AdjustmentAction(Enum):
    """学习率调整动作枚举"""
    INCREASE = "increase"  # 提高学习率
    DECREASE = "decrease"  # 降低学习率
    MAINTAIN = "maintain"  # 维持不变
    SWITCH = "switch"      # 切换调度策略


@dataclass
class MetricRecord:
    """单次训练指标记录"""
    epoch: int
    train_loss: float
    val_accuracy: float
    lr: float
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch": self.epoch,
            "train_loss": self.train_loss,
            "val_accuracy": self.val_accuracy,
            "lr": self.lr,
            "timestamp": self.timestamp,
        }


@dataclass
class CurveAnalysis:
    """训练曲线分析结果"""
    phase: TrainingPhase
    loss_slope: float              # 损失曲线斜率（负值表示下降）
    accuracy_slope: float          # 准确率曲线斜率（正值表示提升）
    loss_volatility: float         # 损失波动率
    accuracy_volatility: float     # 准确率波动率
    is_stagnant: bool              # 是否处于停滞
    stagnation_epochs: int         # 停滞持续的 epoch 数
    convergence_rate: float        # 收敛速率
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "loss_slope": round(self.loss_slope, 6),
            "accuracy_slope": round(self.accuracy_slope, 6),
            "loss_volatility": round(self.loss_volatility, 6),
            "accuracy_volatility": round(self.accuracy_volatility, 6),
            "is_stagnant": self.is_stagnant,
            "stagnation_epochs": self.stagnation_epochs,
            "convergence_rate": round(self.convergence_rate, 6),
            "detail": self.detail,
        }


@dataclass
class LRHistoryRecord:
    """学习率调整历史记录"""
    epoch: int
    lr: float
    train_loss: float
    val_accuracy: float
    action: AdjustmentAction
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch": self.epoch,
            "lr": self.lr,
            "train_loss": self.train_loss,
            "val_accuracy": self.val_accuracy,
            "action": self.action.value,
            "reason": self.reason,
        }


@dataclass
class AdaptiveLRConfig:
    """自适应学习率管理器配置"""
    # 初始学习率（每个位置默认）
    initial_lr: float = 0.01
    min_lr: float = 1e-7
    max_lr: float = 0.1
    # 阶段划分阈值（占总训练 epoch 的比例）
    early_phase_ratio: float = 0.3
    late_phase_ratio: float = 0.7
    # 损失停滞判定
    stagnation_patience: int = 5          # 停滞判定所需的连续 epoch 数
    stagnation_threshold: float = 1e-4    # 损失改善阈值
    # 学习率调整因子
    increase_factor: float = 1.5          # 提高学习率的因子
    decrease_factor: float = 0.5          # 降低学习率的因子
    # 准确率快速提升判定（每 epoch 准确率提升阈值）
    fast_improve_threshold: float = 0.01
    # 历史记录最大长度
    max_history_len: int = 1000
    # 斜率计算窗口
    slope_window: int = 5
    # 总训练 epoch 数（用于阶段判定）
    total_epochs: int = 100


@dataclass
class PositionState:
    """单个位置模型的学习率管理状态"""
    position: str
    current_lr: float = 0.01
    best_val_accuracy: float = 0.0
    best_lr: float = 0.01
    best_epoch: int = -1
    current_phase: TrainingPhase = TrainingPhase.EARLY
    current_strategy: LRSchedulerType = LRSchedulerType.COSINE_ANNEALING
    stagnation_counter: int = 0
    total_epochs: int = 0
    # 训练指标历史
    metrics_history: List[MetricRecord] = field(default_factory=list)
    # 学习率调整历史
    lr_history: List[LRHistoryRecord] = field(default_factory=list)
    # 累积的历史最优学习率区间 [(lower, upper, accuracy), ...]
    best_lr_intervals: List[Tuple[float, float, float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self.position,
            "current_lr": self.current_lr,
            "best_val_accuracy": self.best_val_accuracy,
            "best_lr": self.best_lr,
            "best_epoch": self.best_epoch,
            "current_phase": self.current_phase.value,
            "current_strategy": self.current_strategy.value,
            "stagnation_counter": self.stagnation_counter,
            "total_epochs": self.total_epochs,
            "recent_metrics": [m.to_dict() for m in self.metrics_history[-20:]],
            "recent_lr_actions": [h.to_dict() for h in self.lr_history[-20:]],
        }


class AdaptiveLRManager:
    """自适应学习率管理器主类

    根据训练过程中的性能反馈自动优化学习率调度策略，
    支持多模型协同管理（万/千/百/十/个位）。

    典型用法：
        manager = get_adaptive_lr_manager()
        manager.record_metrics("wan", epoch=0, train_loss=0.5, val_accuracy=0.6)
        optimal_lr = manager.get_optimal_lr("wan")
        scheduler_cfg = manager.get_scheduler_config("wan")
        scheduler = manager.create_scheduler("wan")
    """

    def __init__(
        self,
        config: Optional[AdaptiveLRConfig] = None,
        positions: Optional[Tuple[str, ...]] = None,
    ):
        """
        Args:
            config: 管理器配置，为 None 时使用默认配置
            positions: 模型位置元组，为 None 时使用 DEFAULT_POSITIONS
        """
        self.config = config or AdaptiveLRConfig()
        self.positions = positions or DEFAULT_POSITIONS

        # 初始化各位置的状态
        self.position_states: Dict[str, PositionState] = {
            pos: PositionState(
                position=pos,
                current_lr=self.config.initial_lr,
                best_lr=self.config.initial_lr,
            )
            for pos in self.positions
        }
        # 跨位置共享的全局经验学习率区间
        self._global_best_lr_intervals: List[Tuple[float, float, float]] = []

        logger.info(
            f"自适应学习率管理器初始化完成: positions={list(self.positions)}, "
            f"initial_lr={self.config.initial_lr}, total_epochs={self.config.total_epochs}"
        )

    # ------------------------------------------------------------------
    # 1. 性能反馈驱动的学习率调整
    # ------------------------------------------------------------------

    def record_metrics(
        self,
        position: str,
        epoch: int,
        train_loss: float,
        val_accuracy: float,
    ) -> AdjustmentAction:
        """记录训练指标并据此调整学习率

        Args:
            position: 模型位置（wan/qian/bai/shi/ge）
            epoch: 当前 epoch
            train_loss: 训练损失
            val_accuracy: 验证准确率

        Returns:
            本轮采取的调整动作
        """
        if position not in self.position_states:
            logger.warning(f"未知的位置: {position}，自动创建该位置的状态")
            self.position_states[position] = PositionState(
                position=position,
                current_lr=self.config.initial_lr,
                best_lr=self.config.initial_lr,
            )

        state = self.position_states[position]
        state.total_epochs = max(state.total_epochs, epoch + 1)

        # 记录训练指标
        record = MetricRecord(
            epoch=epoch,
            train_loss=train_loss,
            val_accuracy=val_accuracy,
            lr=state.current_lr,
        )
        state.metrics_history.append(record)
        if len(state.metrics_history) > self.config.max_history_len:
            state.metrics_history = state.metrics_history[-self.config.max_history_len:]

        # 更新最佳准确率及对应学习率
        if val_accuracy > state.best_val_accuracy:
            state.best_val_accuracy = val_accuracy
            state.best_lr = state.current_lr
            state.best_epoch = epoch

        # 更新训练阶段
        state.current_phase = self._determine_phase(state)

        # 分析训练曲线
        analysis = self.analyze_training_curve(position)

        # 根据分析结果决定调整动作
        action, reason = self._decide_adjustment(state, analysis)

        # 应用学习率调整
        new_lr = state.current_lr
        if action == AdjustmentAction.DECREASE:
            new_lr = max(state.current_lr * self.config.decrease_factor, self.config.min_lr)
        elif action == AdjustmentAction.INCREASE:
            new_lr = min(state.current_lr * self.config.increase_factor, self.config.max_lr)
        elif action == AdjustmentAction.SWITCH:
            # 平台期切换到 ReduceLROnPlateau，并适当降低学习率
            state.current_strategy = LRSchedulerType.REDUCE_LR_ON_PLATEAU
            new_lr = max(state.current_lr * self.config.decrease_factor, self.config.min_lr)

        # 记录学习率调整历史
        lr_record = LRHistoryRecord(
            epoch=epoch,
            lr=new_lr,
            train_loss=train_loss,
            val_accuracy=val_accuracy,
            action=action,
            reason=reason,
        )
        state.lr_history.append(lr_record)
        if len(state.lr_history) > self.config.max_history_len:
            state.lr_history = state.lr_history[-self.config.max_history_len:]

        old_lr = state.current_lr
        state.current_lr = new_lr

        logger.info(
            f"[{position}] epoch={epoch} loss={train_loss:.6f} "
            f"acc={val_accuracy:.4f} phase={state.current_phase.value} "
            f"action={action.value} lr={old_lr:.6f}->{new_lr:.6f} reason={reason}"
        )

        return action

    def _decide_adjustment(
        self,
        state: PositionState,
        analysis: CurveAnalysis,
    ) -> Tuple[AdjustmentAction, str]:
        """根据训练曲线分析结果决定学习率调整动作

        优先级：
        1. 损失停滞 -> 降低学习率 / 切换到 ReduceLROnPlateau
        2. 准确率快速提升 -> 适当提高学习率（仅初期/中期）
        3. 训练后期 -> 切换到余弦退火
        4. 默认维持当前学习率
        """
        # 1. 损失停滞处理
        if analysis.is_stagnant:
            state.stagnation_counter = analysis.stagnation_epochs
            # 持续停滞超过耐心阈值，切换到 ReduceLROnPlateau
            if analysis.stagnation_epochs >= self.config.stagnation_patience:
                return (
                    AdjustmentAction.SWITCH,
                    f"损失停滞 {analysis.stagnation_epochs} epoch，切换至 ReduceLROnPlateau",
                )
            return (
                AdjustmentAction.DECREASE,
                f"损失停滞 {analysis.stagnation_epochs} epoch，降低学习率",
            )

        # 2. 准确率快速提升：在初期/中期适当提高学习率
        if analysis.accuracy_slope > self.config.fast_improve_threshold:
            if state.current_phase in (TrainingPhase.EARLY, TrainingPhase.MIDDLE):
                return (
                    AdjustmentAction.INCREASE,
                    f"准确率快速提升(斜率={analysis.accuracy_slope:.4f})，提高学习率",
                )

        # 3. 训练后期自动切换到余弦退火
        if (
            state.current_phase == TrainingPhase.LATE
            and state.current_strategy != LRSchedulerType.COSINE_ANNEALING
        ):
            state.current_strategy = LRSchedulerType.COSINE_ANNEALING
            return (
                AdjustmentAction.MAINTAIN,
                "进入训练后期，切换至余弦退火精细调优",
            )

        # 4. 默认维持当前学习率
        return (AdjustmentAction.MAINTAIN, "训练正常，维持当前学习率")

    def _determine_phase(self, state: PositionState) -> TrainingPhase:
        """根据当前训练进度判定训练阶段

        Args:
            state: 位置状态

        Returns:
            当前训练阶段
        """
        if state.total_epochs <= 0 or self.config.total_epochs <= 0:
            return TrainingPhase.EARLY

        progress = state.total_epochs / self.config.total_epochs
        if progress < self.config.early_phase_ratio:
            return TrainingPhase.EARLY
        elif progress > self.config.late_phase_ratio:
            return TrainingPhase.LATE
        else:
            return TrainingPhase.MIDDLE

    # ------------------------------------------------------------------
    # 2. 学习率调度策略自动选择
    # ------------------------------------------------------------------

    def auto_select_strategy(self, position: str) -> LRSchedulerType:
        """根据训练阶段自动选择最佳调度策略

        策略选择规则：
        - 平台期：ReduceLROnPlateau（自适应降低学习率）
        - 初期：ExponentialLR（较高学习率快速收敛）
        - 中期：StepLR（稳定下降）
        - 后期：CosineAnnealing（精细调优）

        Args:
            position: 模型位置

        Returns:
            推荐的调度器类型
        """
        if position not in self.position_states:
            logger.warning(f"未知的位置: {position}，返回默认调度策略")
            return LRSchedulerType.COSINE_ANNEALING

        state = self.position_states[position]
        analysis = self.analyze_training_curve(position)
        phase = analysis.phase

        if analysis.is_stagnant and analysis.stagnation_epochs >= self.config.stagnation_patience:
            # 平台期：使用 ReduceLROnPlateau
            strategy = LRSchedulerType.REDUCE_LR_ON_PLATEAU
            reason = "检测到平台期，使用 ReduceLROnPlateau 自适应降低"
        elif phase == TrainingPhase.EARLY:
            # 初期：使用 ExponentialLR 快速收敛
            strategy = LRSchedulerType.EXPONENTIAL_LR
            reason = "训练初期，使用 ExponentialLR 快速收敛"
        elif phase == TrainingPhase.MIDDLE:
            # 中期：使用 StepLR 稳定下降
            strategy = LRSchedulerType.STEP_LR
            reason = "训练中期，使用 StepLR 稳定下降"
        elif phase == TrainingPhase.LATE:
            # 后期：使用余弦退火精细调优
            strategy = LRSchedulerType.COSINE_ANNEALING
            reason = "训练后期，使用余弦退火精细调优"
        else:
            strategy = LRSchedulerType.COSINE_ANNEALING
            reason = "默认使用余弦退火"

        state.current_strategy = strategy
        logger.info(f"[{position}] 自动选择调度策略: {strategy.value} ({reason})")
        return strategy

    # ------------------------------------------------------------------
    # 3. 学习率历史分析
    # ------------------------------------------------------------------

    def analyze_training_curve(self, position: str) -> CurveAnalysis:
        """分析指定位置的训练曲线

        基于最近若干个 epoch 的训练指标，计算损失和准确率的斜率、
        波动率、停滞情况以及收敛速率。

        Args:
            position: 模型位置

        Returns:
            训练曲线分析结果
        """
        # 未知位置返回默认分析结果
        if position not in self.position_states:
            logger.warning(f"未知的位置: {position}")
            return CurveAnalysis(
                phase=TrainingPhase.EARLY,
                loss_slope=0.0,
                accuracy_slope=0.0,
                loss_volatility=0.0,
                accuracy_volatility=0.0,
                is_stagnant=False,
                stagnation_epochs=0,
                convergence_rate=0.0,
                detail="未知位置，返回默认分析",
            )

        state = self.position_states[position]
        history = state.metrics_history
        window = self.config.slope_window

        # 历史数据不足时返回默认分析结果
        if len(history) < 2:
            return CurveAnalysis(
                phase=state.current_phase,
                loss_slope=0.0,
                accuracy_slope=0.0,
                loss_volatility=0.0,
                accuracy_volatility=0.0,
                is_stagnant=False,
                stagnation_epochs=0,
                convergence_rate=0.0,
                detail="历史数据不足，返回默认分析",
            )

        # 取最近 window 个数据点进行斜率分析
        recent = history[-window:] if len(history) >= window else history
        epochs = np.array([m.epoch for m in recent], dtype=float)
        losses = np.array([m.train_loss for m in recent], dtype=float)
        accuracies = np.array([m.val_accuracy for m in recent], dtype=float)

        # 计算损失和准确率曲线斜率（线性回归）
        loss_slope = self._compute_slope(epochs, losses)
        accuracy_slope = self._compute_slope(epochs, accuracies)

        # 计算波动率（标准差）
        loss_volatility = float(np.std(losses)) if len(losses) > 1 else 0.0
        accuracy_volatility = float(np.std(accuracies)) if len(accuracies) > 1 else 0.0

        # 停滞判定：从最新 epoch 往前统计损失未显著改善的连续 epoch 数
        stagnation_epochs = self._count_stagnation_epochs(history)
        is_stagnant = stagnation_epochs > 0

        # 收敛速率：窗口内损失相对下降比例
        convergence_rate = 0.0
        if len(losses) > 1 and losses[0] > 0:
            convergence_rate = float((losses[0] - losses[-1]) / max(losses[0], 1e-8))

        detail = (
            f"最近 {len(recent)} epoch: 损失斜率={loss_slope:.6f}, "
            f"准确率斜率={accuracy_slope:.6f}, 停滞={stagnation_epochs} epoch"
        )

        return CurveAnalysis(
            phase=state.current_phase,
            loss_slope=loss_slope,
            accuracy_slope=accuracy_slope,
            loss_volatility=loss_volatility,
            accuracy_volatility=accuracy_volatility,
            is_stagnant=is_stagnant,
            stagnation_epochs=stagnation_epochs,
            convergence_rate=convergence_rate,
            detail=detail,
        )

    def _compute_slope(self, x: np.ndarray, y: np.ndarray) -> float:
        """使用最小二乘法计算曲线斜率

        Args:
            x: 自变量（epoch）
            y: 因变量（损失或准确率）

        Returns:
            斜率值
        """
        if len(x) < 2:
            return 0.0
        try:
            x_mean = x.mean()
            y_mean = y.mean()
            cov = float(np.sum((x - x_mean) * (y - y_mean)))
            var = float(np.sum((x - x_mean) ** 2))
            if var == 0:
                return 0.0
            return cov / var
        except Exception:
            return 0.0

    def _count_stagnation_epochs(self, history: List[MetricRecord]) -> int:
        """统计损失停滞的连续 epoch 数

        从最新记录往前遍历，统计损失改善小于阈值的连续 epoch 数。

        Args:
            history: 训练指标历史

        Returns:
            停滞的连续 epoch 数
        """
        if len(history) < 2:
            return 0

        count = 0
        # 从后往前遍历，统计损失未显著改善的连续 epoch 数
        for i in range(len(history) - 1, 0, -1):
            prev_loss = history[i - 1].train_loss
            curr_loss = history[i].train_loss
            # 损失改善（下降）小于阈值视为停滞
            improvement = prev_loss - curr_loss
            if improvement < self.config.stagnation_threshold:
                count += 1
            else:
                break
        return count

    def get_optimal_lr(self, position: str) -> float:
        """获取指定位置的当前最优学习率

        综合考虑历史最佳学习率、当前训练曲线分析结果以及全局经验，
        给出推荐的学习率值。

        Args:
            position: 模型位置

        Returns:
            推荐的学习率
        """
        if position not in self.position_states:
            logger.warning(f"未知的位置: {position}，返回默认初始学习率")
            return self.config.initial_lr

        state = self.position_states[position]
        analysis = self.analyze_training_curve(position)

        # 有历史最佳记录时，基于最佳学习率结合当前阶段微调
        if state.best_val_accuracy > 0:
            base_lr = state.best_lr
            if analysis.is_stagnant:
                # 停滞时降低学习率
                return max(base_lr * self.config.decrease_factor, self.config.min_lr)
            elif (
                analysis.accuracy_slope > self.config.fast_improve_threshold
                and state.current_phase in (TrainingPhase.EARLY, TrainingPhase.MIDDLE)
            ):
                # 快速提升时适当提高
                return min(base_lr * self.config.increase_factor, self.config.max_lr)
            return state.current_lr

        # 无历史记录时，使用全局经验返回
        if self._global_best_lr_intervals:
            # 返回全局最优区间的中点（按准确率加权）
            best_interval = max(self._global_best_lr_intervals, key=lambda x: x[2])
            return (best_interval[0] + best_interval[1]) / 2

        return state.current_lr

    def get_scheduler_config(self, position: str) -> Dict[str, Any]:
        """获取指定位置的调度器配置建议

        Args:
            position: 模型位置

        Returns:
            包含调度器类型和配置参数的字典
        """
        if position not in self.position_states:
            logger.warning(f"未知的位置: {position}")
            return {
                "scheduler_type": LRSchedulerType.COSINE_ANNEALING.value,
                "config": {
                    "initial_lr": self.config.initial_lr,
                    "min_lr": self.config.min_lr,
                },
            }

        state = self.position_states[position]
        strategy = self.auto_select_strategy(position)
        optimal_lr = self.get_optimal_lr(position)

        # 构建基础配置
        base_config: Dict[str, Any] = {
            "initial_lr": optimal_lr,
            "min_lr": self.config.min_lr,
            "max_lr": self.config.max_lr,
        }

        # 根据调度器类型补充专属参数
        if strategy == LRSchedulerType.COSINE_ANNEALING:
            base_config.update({
                "t_max": max(self.config.total_epochs - state.total_epochs, 10),
                "eta_min": self.config.min_lr,
            })
        elif strategy == LRSchedulerType.REDUCE_LR_ON_PLATEAU:
            base_config.update({
                "factor": self.config.decrease_factor,
                "patience": self.config.stagnation_patience,
                "threshold": self.config.stagnation_threshold,
                "mode": "min",
                "min_lr": self.config.min_lr,
            })
        elif strategy == LRSchedulerType.STEP_LR:
            base_config.update({
                "step_size": max(self.config.total_epochs // 5, 5),
                "gamma": 0.5,
            })
        elif strategy == LRSchedulerType.EXPONENTIAL_LR:
            base_config.update({
                "gamma": 0.95,
            })

        return {
            "scheduler_type": strategy.value,
            "config": base_config,
            "current_phase": state.current_phase.value,
            "current_lr": state.current_lr,
            "best_lr": state.best_lr,
            "best_val_accuracy": state.best_val_accuracy,
        }

    def analyze_best_lr_range(self, position: str) -> Optional[Tuple[float, float]]:
        """分析指定位置的最佳学习率区间

        基于历史记录中表现最好的若干次训练，统计学习率分布的 25%-75% 分位数。

        Args:
            position: 模型位置

        Returns:
            (lower_bound, upper_bound) 最佳学习率区间，无数据时返回 None
        """
        if position not in self.position_states:
            return None

        state = self.position_states[position]
        if len(state.lr_history) < 3:
            return None

        # 按验证准确率排序，取表现最好的前 30% 记录
        sorted_records = sorted(
            state.lr_history, key=lambda r: r.val_accuracy, reverse=True
        )
        top_n = max(3, len(sorted_records) // 3)
        top_records = sorted_records[:top_n]
        top_lrs = np.array([r.lr for r in top_records], dtype=float)

        lower = float(np.percentile(top_lrs, 25))
        upper = float(np.percentile(top_lrs, 75))

        # 记录到历史最优区间
        state.best_lr_intervals.append((lower, upper, state.best_val_accuracy))
        # 同步到全局经验
        self._global_best_lr_intervals.append((lower, upper, state.best_val_accuracy))
        # 保留最近 50 条全局记录
        if len(self._global_best_lr_intervals) > 50:
            self._global_best_lr_intervals = self._global_best_lr_intervals[-50:]

        logger.info(
            f"[{position}] 最佳学习率区间: [{lower:.6f}, {upper:.6f}]，"
            f"基于 {top_n} 条最优记录"
        )
        return (lower, upper)

    def optimize_initial_lr(self, position: str) -> float:
        """基于历史经验优化初始学习率

        优先使用该位置的历史最优区间，其次使用全局跨位置经验。

        Args:
            position: 模型位置

        Returns:
            优化后的初始学习率
        """
        # 优先使用该位置的历史最优区间
        interval = self.analyze_best_lr_range(position)
        if interval is not None:
            return (interval[0] + interval[1]) / 2

        # 其次使用全局经验（按准确率加权平均）
        if self._global_best_lr_intervals:
            total_weight = sum(w for _, _, w in self._global_best_lr_intervals)
            if total_weight > 0:
                weighted_sum = sum(
                    (l + u) / 2 * w for l, u, w in self._global_best_lr_intervals
                )
                return weighted_sum / (2 * total_weight)

        return self.config.initial_lr

    # ------------------------------------------------------------------
    # 4. 多模型协同学习率管理
    # ------------------------------------------------------------------

    def get_all_positions_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有位置模型的当前状态"""
        return {pos: state.to_dict() for pos, state in self.position_states.items()}

    def differential_adjust(self) -> Dict[str, float]:
        """根据各位置模型的收敛情况差异化调整学习率

        收敛明显慢于平均的位置适当提高学习率，
        收敛明显快于平均或停滞的位置适当降低学习率。

        Returns:
            各位置调整后的学习率
        """
        results: Dict[str, float] = {}
        convergence_rates: Dict[str, float] = {}

        # 收集各位置的收敛速率
        for pos in self.position_states:
            analysis = self.analyze_training_curve(pos)
            convergence_rates[pos] = analysis.convergence_rate

        if not convergence_rates:
            return results

        rates = np.array(list(convergence_rates.values()), dtype=float)
        mean_rate = float(np.mean(rates)) if len(rates) > 0 else 0.0

        for pos, rate in convergence_rates.items():
            state = self.position_states[pos]
            old_lr = state.current_lr

            if mean_rate > 0 and rate < mean_rate * 0.5:
                # 收敛明显慢于平均，提高学习率
                new_lr = min(state.current_lr * self.config.increase_factor, self.config.max_lr)
                reason = f"收敛速率({rate:.4f})低于平均({mean_rate:.4f})，提高学习率"
            elif rate > mean_rate * 1.5:
                # 收敛明显快于平均，降低学习率以稳定
                new_lr = max(state.current_lr * self.config.decrease_factor, self.config.min_lr)
                reason = f"收敛速率({rate:.4f})高于平均({mean_rate:.4f})，降低学习率"
            else:
                new_lr = state.current_lr
                reason = "收敛速率接近平均，维持学习率"

            state.current_lr = new_lr
            results[pos] = new_lr
            logger.info(f"[{pos}] 差异化调整: {old_lr:.6f} -> {new_lr:.6f} ({reason})")

        return results

    def adjust_position_lr(self, position: str, factor: float) -> float:
        """手动调整指定位置的学习率

        Args:
            position: 模型位置
            factor: 调整因子（>1 提高，<1 降低）

        Returns:
            调整后的学习率
        """
        if position not in self.position_states:
            logger.warning(f"未知的位置: {position}")
            return self.config.initial_lr

        state = self.position_states[position]
        new_lr = max(min(state.current_lr * factor, self.config.max_lr), self.config.min_lr)
        old_lr = state.current_lr
        state.current_lr = new_lr
        logger.info(f"[{position}] 手动调整学习率: {old_lr:.6f} -> {new_lr:.6f} (factor={factor})")
        return new_lr

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def create_scheduler(self, position: str):
        """为指定位置创建学习率调度器实例

        Args:
            position: 模型位置

        Returns:
            学习率调度器实例（来自 src.core.training.lr_scheduler）
        """
        config_info = self.get_scheduler_config(position)
        scheduler_type = LRSchedulerType(config_info["scheduler_type"])
        scheduler_config = config_info["config"]
        return create_lr_scheduler(scheduler_type, scheduler_config)

    def reset_position(self, position: str) -> bool:
        """重置指定位置的状态

        Args:
            position: 模型位置

        Returns:
            是否重置成功
        """
        if position not in self.position_states:
            return False
        self.position_states[position] = PositionState(
            position=position,
            current_lr=self.config.initial_lr,
            best_lr=self.config.initial_lr,
        )
        logger.info(f"[{position}] 状态已重置")
        return True

    def get_summary(self) -> Dict[str, Any]:
        """获取管理器整体摘要"""
        return {
            "config": {
                "initial_lr": self.config.initial_lr,
                "min_lr": self.config.min_lr,
                "max_lr": self.config.max_lr,
                "total_epochs": self.config.total_epochs,
                "stagnation_patience": self.config.stagnation_patience,
            },
            "positions": self.get_all_positions_status(),
            "global_best_lr_intervals": [
                {"lower": l, "upper": u, "accuracy": w}
                for l, u, w in self._global_best_lr_intervals[-10:]
            ],
        }


# 全局单例
_adaptive_lr_manager: Optional[AdaptiveLRManager] = None


def get_adaptive_lr_manager(
    config: Optional[AdaptiveLRConfig] = None,
    positions: Optional[Tuple[str, ...]] = None,
    force_new: bool = False,
) -> AdaptiveLRManager:
    """获取全局自适应学习率管理器单例

    Args:
        config: 管理器配置（仅在首次创建时生效）
        positions: 模型位置元组（仅在首次创建时生效）
        force_new: 是否强制创建新实例（用于测试）

    Returns:
        AdaptiveLRManager 实例
    """
    global _adaptive_lr_manager
    if _adaptive_lr_manager is None or force_new:
        _adaptive_lr_manager = AdaptiveLRManager(config=config, positions=positions)
    return _adaptive_lr_manager
