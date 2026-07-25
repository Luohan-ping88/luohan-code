"""
策略自适应选择器模块 V1.0

实现策略的动态切换与组合优化，包含四大能力：
1. 策略性能追踪 - 记录每种策略近期表现、维护策略排行榜、识别适用场景
2. 动态策略切换 - 根据近期表现自动切换到最佳策略、当前策略表现下降时触发切换评估、
                  支持权重平滑过渡（渐变而非硬切换）
3. 策略组合优化 - 多策略加权组合、使用 Bandit 算法（UCB / Thompson Sampling）进行策略选择、
                  自动学习最优组合权重
4. 场景感知策略选择 - 根据数据特征（漂移级别、周期阶段等）选择策略、不同位置可使用不同策略、
                      支持策略覆盖规则（如高置信度时使用保守策略）

支持的 6 种预设策略（与 StrategyEvaluator.define_strategies 保持一致）：
    default, stacking_dominant, hmm_dominant, copula_dominant, rfe_features, voting_ensemble
"""

from __future__ import annotations

import json
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# 选择器状态持久化路径（与 drift_detector 保持一致的定位方式）
_SELECTOR_STATE_PATH = (
    Path(__file__).parent.parent.parent.parent / "models" / "strategy_selector_state.json"
)

# 6 种预设策略（与 StrategyEvaluator.define_strategies 保持一致）
PRESET_STRATEGIES: List[str] = [
    'default',
    'stacking_dominant',
    'hmm_dominant',
    'copula_dominant',
    'rfe_features',
    'voting_ensemble',
]

# 5 个位置（与 strategy_evaluator.POSITION_NAMES 保持一致）
POSITION_NAMES: List[str] = ['wan', 'qian', 'bai', 'shi', 'ge']

# 高置信度阈值（超过该值触发保守策略覆盖）
_HIGH_CONFIDENCE_THRESHOLD = 0.85


class SelectionMode(Enum):
    """策略选择模式"""
    SINGLE = "single"                    # 单一最佳策略：直接选择近期表现最好的策略
    COMBINATION = "combination"          # 多策略加权组合：融合多个策略的预测结果
    BANDIT_UCB = "bandit_ucb"            # UCB Bandit 选择：平衡探索与利用
    BANDIT_THOMPSON = "bandit_thompson"  # Thompson Sampling 选择：基于 Beta 分布采样
    SCENE_AWARE = "scene_aware"          # 场景感知选择：根据数据特征匹配最佳策略


class SwitchTrigger(Enum):
    """策略切换触发原因"""
    PERFORMANCE_DROP = "performance_drop"  # 当前策略表现下降
    DRIFT_DETECTED = "drift_detected"      # 检测到数据分布漂移
    PERIODIC = "periodic"                  # 定期评估触发切换
    CONTEXT_CHANGE = "context_change"      # 场景上下文变化
    MANUAL = "manual"                      # 手动触发


@dataclass
class StrategyPerformanceRecord:
    """单次策略表现记录"""
    strategy_name: str
    position: str
    accuracy: float       # 命中准确率（0-1）
    confidence: float     # 预测置信度（0-1）
    reward: float = 0.0   # 由准确率计算得到的奖励值（0-1）
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'strategy_name': self.strategy_name,
            'position': self.position,
            'accuracy': round(self.accuracy, 6),
            'confidence': round(self.confidence, 6),
            'reward': round(self.reward, 6),
            'timestamp': self.timestamp,
        }


@dataclass
class StrategyStats:
    """策略统计信息（按位置聚合）

    维护单个策略在某位置上的累计与近期统计，以及 Bandit 所需参数。
    """
    strategy_name: str
    total_runs: int = 0
    sum_reward: float = 0.0
    sum_accuracy: float = 0.0
    sum_confidence: float = 0.0
    # Thompson Sampling 参数：Beta(alpha, beta)
    alpha: float = 1.0
    beta: float = 1.0
    # 最近窗口的奖励序列（用于感知表现下降与近期均值）
    recent_rewards: deque = field(default_factory=lambda: deque(maxlen=50))
    last_used: str = ""
    # 场景适用性：scene_key -> 奖励序列
    scene_rewards: Dict[str, List[float]] = field(default_factory=dict)

    @property
    def mean_reward(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.sum_reward / self.total_runs

    @property
    def mean_accuracy(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.sum_accuracy / self.total_runs

    @property
    def mean_confidence(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.sum_confidence / self.total_runs

    @property
    def recent_mean_reward(self) -> float:
        if not self.recent_rewards:
            return 0.0
        return float(np.mean(list(self.recent_rewards)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'strategy_name': self.strategy_name,
            'total_runs': self.total_runs,
            'sum_reward': round(self.sum_reward, 6),
            'sum_accuracy': round(self.sum_accuracy, 6),
            'sum_confidence': round(self.sum_confidence, 6),
            'alpha': round(self.alpha, 6),
            'beta': round(self.beta, 6),
            'recent_rewards': [round(x, 6) for x in self.recent_rewards],
            'last_used': self.last_used,
            'scene_rewards': {k: [round(x, 6) for x in v] for k, v in self.scene_rewards.items()},
            'mean_reward': round(self.mean_reward, 6),
            'mean_accuracy': round(self.mean_accuracy, 6),
            'recent_mean_reward': round(self.recent_mean_reward, 6),
        }


@dataclass
class SelectorConfig:
    """策略选择器配置"""
    mode: SelectionMode = SelectionMode.BANDIT_UCB
    window_size: int = 50            # 滑动窗口大小（recent_rewards 容量）
    switch_threshold: float = 0.05   # 表现下降阈值（差值超过该值触发切换评估）
    smoothing_factor: float = 0.2    # 平滑过渡因子（0-1，越大权重切换越快）
    ucb_c: float = 2.0               # UCB 探索系数
    exploration_rate: float = 0.1    # epsilon-greedy 探索率
    min_samples: int = 5             # 最少样本数（不足时强制探索）
    enable_smoothing: bool = True    # 是否启用权重平滑过渡
    auto_switch_on_drop: bool = True  # 当前策略表现下降时是否自动触发切换评估
    # 场景覆盖规则：scene_key（或 'high_confidence' 等特殊标签）-> 策略名
    scene_overrides: Dict[str, str] = field(default_factory=dict)
    history_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'mode': self.mode.value,
            'window_size': self.window_size,
            'switch_threshold': self.switch_threshold,
            'smoothing_factor': self.smoothing_factor,
            'ucb_c': self.ucb_c,
            'exploration_rate': self.exploration_rate,
            'min_samples': self.min_samples,
            'enable_smoothing': self.enable_smoothing,
            'auto_switch_on_drop': self.auto_switch_on_drop,
            'scene_overrides': dict(self.scene_overrides),
        }


class StrategyAdaptiveSelector:
    """策略自适应选择器

    整合策略性能追踪、动态切换、组合优化和场景感知选择。
    每个位置维护独立的策略统计与权重，支持位置级别的差异化策略。

    典型用法::

        selector = get_strategy_selector()
        # 记录某策略在某位置的表现
        selector.record_strategy_performance('stacking_dominant', 'wan',
                                             accuracy=1.0, confidence=0.8)
        # 选择当前最佳策略
        best = selector.select_best_strategy('wan', context={'drift_level': 'low'})
        # 获取策略组合权重（COMBINATION 模式）
        weights = selector.get_strategy_combination('wan')
        # Bandit 反馈更新组合权重
        selector.update_weights('wan', reward=0.75)
    """

    def __init__(
        self,
        config: Optional[SelectorConfig] = None,
        strategies: Optional[List[str]] = None,
    ):
        self.config = config or SelectorConfig()
        self.strategies: List[str] = list(strategies) if strategies else list(PRESET_STRATEGIES)
        if len(self.strategies) == 0:
            raise ValueError("strategies 不能为空")
        self.history_path: Path = self.config.history_path or _SELECTOR_STATE_PATH

        # 每个位置的策略统计：position -> {strategy_name -> StrategyStats}
        self._stats: Dict[str, Dict[str, StrategyStats]] = {
            pos: {s: StrategyStats(strategy_name=s) for s in self.strategies}
            for pos in POSITION_NAMES
        }
        # 每个位置的当前激活策略
        self._current_strategy: Dict[str, str] = {
            pos: self.strategies[0] for pos in POSITION_NAMES
        }
        # 每个位置的当前组合权重（平滑过渡用）
        init_w = 1.0 / len(self.strategies)
        self._current_weights: Dict[str, Dict[str, float]] = {
            pos: {s: init_w for s in self.strategies} for pos in POSITION_NAMES
        }
        # 每个位置的目标组合权重
        self._target_weights: Dict[str, Dict[str, float]] = {
            pos: {s: init_w for s in self.strategies} for pos in POSITION_NAMES
        }
        # 每个位置的总拉取次数（用于 UCB 公式中的 N）
        self._total_pulls: Dict[str, int] = {pos: 0 for pos in POSITION_NAMES}
        # 切换历史
        self._switch_history: List[Dict[str, Any]] = []

        # 加载持久化状态
        self._load_state()

        logger.info(
            f"策略自适应选择器初始化完成 (模式: {self.config.mode.value}, "
            f"策略数: {len(self.strategies)}, 位置数: {len(POSITION_NAMES)})"
        )

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def record_strategy_performance(
        self,
        strategy_name: str,
        position: str,
        accuracy: float,
        confidence: float,
    ) -> StrategyPerformanceRecord:
        """记录策略在某位置上的预测表现

        Args:
            strategy_name: 策略名称
            position: 位置名（wan/qian/bai/shi/ge）
            accuracy: 命中准确率（0-1）
            confidence: 预测置信度（0-1）

        Returns:
            本次表现记录
        """
        self._validate_position(position)
        self._validate_strategy(strategy_name)

        accuracy = float(np.clip(accuracy, 0.0, 1.0))
        confidence = float(np.clip(confidence, 0.0, 1.0))
        # 奖励以命中准确率为主信号（0-1，便于 Beta 分布更新）
        reward = accuracy

        record = StrategyPerformanceRecord(
            strategy_name=strategy_name,
            position=position,
            accuracy=accuracy,
            confidence=confidence,
            reward=reward,
        )

        stats = self._stats[position][strategy_name]
        stats.total_runs += 1
        stats.sum_reward += reward
        stats.sum_accuracy += accuracy
        stats.sum_confidence += confidence
        stats.recent_rewards.append(reward)
        stats.last_used = record.timestamp
        # Thompson Sampling：Beta 分布参数更新
        stats.alpha += reward
        stats.beta += (1.0 - reward)

        self._total_pulls[position] += 1

        logger.debug(
            f"记录策略表现: pos={position} strategy={strategy_name} "
            f"acc={accuracy:.3f} conf={confidence:.3f} reward={reward:.3f} "
            f"(累计均值={stats.mean_reward:.3f}, 近期均值={stats.recent_mean_reward:.3f})"
        )

        # 当前策略表现下降时自动触发切换评估
        if (
            self.config.auto_switch_on_drop
            and strategy_name == self._current_strategy[position]
            and self.config.mode in (SelectionMode.SINGLE, SelectionMode.BANDIT_UCB,
                                     SelectionMode.BANDIT_THOMPSON, SelectionMode.SCENE_AWARE)
        ):
            self._maybe_trigger_switch(position, SwitchTrigger.PERFORMANCE_DROP)

        return record

    def select_best_strategy(
        self,
        position: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """选择最佳策略

        Args:
            position: 位置名
            context: 场景上下文（可含 drift_level/cycle_phase/confidence 等）

        Returns:
            策略名称
        """
        self._validate_position(position)

        # 优先应用场景覆盖规则
        override = self._apply_overrides(position, context)
        if override is not None:
            logger.debug(f"位置 {position} 命中覆盖规则 -> {override}")
            return override

        mode = self.config.mode
        if mode == SelectionMode.SINGLE:
            chosen = self._select_single(position)
        elif mode == SelectionMode.COMBINATION:
            # 组合模式下返回当前主策略（权重最大的）
            chosen = self._select_single(position)
        elif mode == SelectionMode.BANDIT_UCB:
            chosen = self._select_ucb(position)
        elif mode == SelectionMode.BANDIT_THOMPSON:
            chosen = self._select_thompson(position)
        elif mode == SelectionMode.SCENE_AWARE:
            chosen = self._select_scene_aware(position, context)
        else:
            chosen = self._select_single(position)

        # 同步更新当前激活策略与目标权重
        self._current_strategy[position] = chosen
        self._set_target_around(position, chosen)

        logger.debug(f"位置 {position} 选择策略: {chosen} (模式={mode.value})")
        return chosen

    def get_strategy_combination(self, position: str) -> Dict[str, float]:
        """获取策略组合权重

        返回归一化后的策略权重字典。若启用平滑过渡，每次调用都会将
        当前权重向目标权重逐步逼近。

        Args:
            position: 位置名

        Returns:
            {strategy_name: weight}，所有权重之和为 1
        """
        self._validate_position(position)

        if self.config.enable_smoothing:
            self._smooth_weights(position)

        weights = self._current_weights[position]
        normalized = self._normalize_weights(weights)
        # 回写归一化结果，避免数值漂移
        self._current_weights[position] = dict(normalized)
        return dict(normalized)

    def update_weights(self, position: str, reward: float) -> Dict[str, float]:
        """更新策略组合权重（Bandit 反馈）

        根据累积的各策略近期表现，通过 softmax 自动学习最优组合权重，
        并以平滑因子逐步过渡到新目标。reward 用于调节 softmax 温度：
        高奖励时温度升高（更倾向于表现好的策略），低奖励时温度降低（更平均/探索）。

        Args:
            position: 位置名
            reward: 本次预测的奖励值（0-1）

        Returns:
            更新后的目标组合权重
        """
        self._validate_position(position)
        reward = float(np.clip(reward, 0.0, 1.0))

        stats = self._stats[position]
        rewards = np.array(
            [stats[s].recent_mean_reward for s in self.strategies], dtype=float
        )
        temperature = self._compute_temperature(reward)
        # softmax(rewards * temperature)
        logits = rewards * temperature
        target = self._softmax(logits)

        for i, s in enumerate(self.strategies):
            self._target_weights[position][s] = float(target[i])

        logger.debug(
            f"更新组合权重: pos={position} reward={reward:.3f} temp={temperature:.3f} "
            f"target={ {s: round(float(target[i]), 3) for i, s in enumerate(self.strategies)} }"
        )
        return dict(self._target_weights[position])

    def get_strategy_ranking(
        self, position: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取策略排行榜

        Args:
            position: 指定位置则返回该位置排行；None 则聚合所有位置

        Returns:
            按近期表现降序排列的策略统计列表
        """
        if position is not None:
            self._validate_position(position)
            return self._rank_position(position)

        # 聚合所有位置
        agg: Dict[str, List[float]] = {s: [] for s in self.strategies}
        for pos in POSITION_NAMES:
            for s in self.strategies:
                st = self._stats[pos][s]
                if st.total_runs > 0:
                    agg[s].append(st.recent_mean_reward if st.recent_rewards else st.mean_reward)

        ranked: List[Dict[str, Any]] = []
        for s in self.strategies:
            rewards = agg[s]
            ranked.append({
                'strategy_name': s,
                'mean_reward': round(float(np.mean(rewards)), 6) if rewards else 0.0,
                'sample_positions': len(rewards),
                'total_runs': sum(self._stats[p][s].total_runs for p in POSITION_NAMES),
            })
        ranked.sort(key=lambda x: x['mean_reward'], reverse=True)
        return ranked

    def auto_switch_strategy(self, position: str) -> Dict[str, Any]:
        """自动切换策略

        评估当前策略是否需要切换：若当前策略近期表现显著低于最佳替代策略，
        或当前策略近期表现较其历史均值明显下降，则切换到最佳替代策略。

        Args:
            position: 位置名

        Returns:
            切换结果 dict：
            - switched: 是否发生切换
            - position: 位置
            - old_strategy / new_strategy: 切换前后策略
            - old_reward / best_reward: 表现对比
            - reason: 切换原因（SwitchTrigger.value）
        """
        self._validate_position(position)
        return self._evaluate_and_switch(position, SwitchTrigger.PERFORMANCE_DROP)

    # ------------------------------------------------------------------
    # 辅助查询
    # ------------------------------------------------------------------
    def get_current_strategy(self, position: str) -> str:
        """获取某位置当前激活的策略"""
        self._validate_position(position)
        return self._current_strategy[position]

    def get_strategy_stats(self, position: str, strategy_name: str) -> StrategyStats:
        """获取某位置某策略的统计信息"""
        self._validate_position(position)
        self._validate_strategy(strategy_name)
        return self._stats[position][strategy_name]

    def get_switch_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的策略切换历史"""
        return list(self._switch_history[-limit:])

    def get_status(self) -> Dict[str, Any]:
        """获取选择器整体状态摘要（用于调试/日志）"""
        return {
            'mode': self.config.mode.value,
            'strategies': list(self.strategies),
            'current_strategy': dict(self._current_strategy),
            'total_pulls': dict(self._total_pulls),
            'ranking_global': self.get_strategy_ranking(None),
            'switch_history_count': len(self._switch_history),
        }

    def set_mode(self, mode: SelectionMode):
        """切换选择模式"""
        self.config.mode = mode
        logger.info(f"策略选择模式切换为: {mode.value}")

    def notify_drift(self, position: Optional[str] = None, drift_level: str = "medium"):
        """通知选择器发生了数据漂移，触发对应位置的策略切换评估

        Args:
            position: 指定位置；None 则对所有位置评估
            drift_level: 漂移级别描述（用于日志）
        """
        targets = [position] if position else list(POSITION_NAMES)
        for pos in targets:
            self._evaluate_and_switch(pos, SwitchTrigger.DRIFT_DETECTED)
        logger.info(f"漂移通知已处理 (level={drift_level}, positions={targets})")

    # ------------------------------------------------------------------
    # 内部：选择算法
    # ------------------------------------------------------------------
    def _rank_position(self, position: str) -> List[Dict[str, Any]]:
        """生成单个位置的策略排行榜（按近期表现降序）"""
        ranked: List[Dict[str, Any]] = []
        for s in self.strategies:
            st = self._stats[position][s]
            score = st.recent_mean_reward if st.recent_rewards else st.mean_reward
            ranked.append({
                'strategy_name': s,
                'mean_reward': round(st.mean_reward, 6),
                'recent_mean_reward': round(st.recent_mean_reward, 6),
                'score': round(score, 6),
                'mean_accuracy': round(st.mean_accuracy, 6),
                'mean_confidence': round(st.mean_confidence, 6),
                'total_runs': st.total_runs,
                'last_used': st.last_used,
            })
        ranked.sort(key=lambda x: x['score'], reverse=True)
        return ranked

    def _select_single(self, position: str) -> str:
        """选择近期表现最好的策略（带 epsilon 探索）"""
        if self._should_explore(position):
            return self._random_strategy()
        return self._best_by_recent(position)

    def _select_ucb(self, position: str) -> str:
        """UCB Bandit 选择"""
        total = self._total_pulls[position]
        log_total = math.log(total + 1.0)
        c = self.config.ucb_c
        best_score = -float('inf')
        best_strategy = self.strategies[0]
        for s in self.strategies:
            st = self._stats[position][s]
            n = st.total_runs
            if n == 0:
                # 未尝试过的策略强制探索
                return s
            mean = st.recent_mean_reward if st.recent_rewards else st.mean_reward
            ucb = mean + c * math.sqrt(log_total / (n + 1.0))
            if ucb > best_score:
                best_score = ucb
                best_strategy = s
        return best_strategy

    def _select_thompson(self, position: str) -> str:
        """Thompson Sampling 选择（基于 Beta 分布采样）"""
        best_sample = -float('inf')
        best_strategy = self.strategies[0]
        for s in self.strategies:
            st = self._stats[position][s]
            sample = float(np.random.beta(st.alpha, st.beta))
            if sample > best_sample:
                best_sample = sample
                best_strategy = s
        return best_strategy

    def _select_scene_aware(
        self, position: str, context: Optional[Dict[str, Any]]
    ) -> str:
        """场景感知选择：根据上下文匹配在该场景下表现最好的策略"""
        if context is None:
            return self._best_by_recent(position)

        scene = self._context_to_scene(context)
        stats = self._stats[position]
        best_mean = -float('inf')
        best_strategy = self._best_by_recent(position)
        for s in self.strategies:
            st = stats[s]
            scene_rewards = st.scene_rewards.get(scene, [])
            if scene_rewards:
                m = float(np.mean(scene_rewards))
                if m > best_mean:
                    best_mean = m
                    best_strategy = s
        return best_strategy

    def _best_by_recent(self, position: str) -> str:
        """近期表现最好的策略（近期均值为 0 时回退到累计均值）"""
        best_score = -float('inf')
        best_strategy = self.strategies[0]
        for s in self.strategies:
            st = self._stats[position][s]
            score = st.recent_mean_reward if st.recent_rewards else st.mean_reward
            if score > best_score:
                best_score = score
                best_strategy = s
        return best_strategy

    def _should_explore(self, position: str) -> bool:
        """是否触发探索（epsilon-greedy 或样本不足）"""
        stats = self._stats[position]
        # 样本不足时强制探索
        if any(stats[s].total_runs < self.config.min_samples for s in self.strategies):
            return True
        return float(np.random.random()) < self.config.exploration_rate

    def _random_strategy(self) -> str:
        """随机选择一个策略（探索）"""
        idx = int(np.random.randint(0, len(self.strategies)))
        return self.strategies[idx]

    # ------------------------------------------------------------------
    # 内部：场景与覆盖
    # ------------------------------------------------------------------
    def _context_to_scene(self, context: Dict[str, Any]) -> str:
        """将上下文转换为场景键（用于场景适用性统计）"""
        drift = str(context.get('drift_level', 'unknown'))
        phase = str(context.get('cycle_phase', 'unknown'))
        return f"drift={drift}|phase={phase}"

    def _apply_overrides(
        self, position: str, context: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """应用策略覆盖规则

        优先级：
        1. 高置信度覆盖：当 context['confidence'] >= 阈值且存在 'high_confidence' 覆盖
        2. 场景覆盖：scene_key 命中 scene_overrides
        """
        overrides = self.config.scene_overrides
        if not overrides:
            return None

        if context is not None:
            conf = context.get('confidence')
            if conf is not None and float(conf) >= _HIGH_CONFIDENCE_THRESHOLD:
                override = overrides.get('high_confidence')
                if override and override in self.strategies:
                    return override

            scene = self._context_to_scene(context)
            override = overrides.get(scene)
            if override and override in self.strategies:
                return override
        return None

    # ------------------------------------------------------------------
    # 内部：权重与平滑
    # ------------------------------------------------------------------
    def _set_target_around(self, position: str, main_strategy: str):
        """以主策略为中心设置目标权重（主策略占大头，其余均分）"""
        main_weight = 0.7
        rest = (1.0 - main_weight) / max(1, len(self.strategies) - 1)
        for s in self.strategies:
            self._target_weights[position][s] = main_weight if s == main_strategy else rest

    def _smooth_weights(self, position: str):
        """将当前权重向目标权重平滑过渡"""
        factor = float(np.clip(self.config.smoothing_factor, 0.0, 1.0))
        cur = self._current_weights[position]
        tgt = self._target_weights[position]
        for s in self.strategies:
            cur[s] = cur[s] + factor * (tgt[s] - cur[s])

    @staticmethod
    def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
        """归一化权重，使和为 1"""
        total = sum(max(0.0, w) for w in weights.values())
        if total <= 0.0:
            n = len(weights)
            return {k: 1.0 / n for k in weights}
        return {k: max(0.0, v) / total for k, v in weights.items()}

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """数值稳定的 softmax"""
        x = np.asarray(x, dtype=float)
        if x.size == 0:
            return x
        x_max = np.max(x)
        e = np.exp(x - x_max)
        return e / np.sum(e)

    def _compute_temperature(self, reward: float) -> float:
        """根据奖励计算 softmax 温度

        奖励越高 → 温度越高 → 越倾向于表现好的策略；
        奖励越低 → 温度越低 → 越趋向均匀分布（增加探索）。
        """
        base = 5.0
        return base * (0.5 + reward)

    # ------------------------------------------------------------------
    # 内部：切换评估
    # ------------------------------------------------------------------
    def _maybe_trigger_switch(self, position: str, trigger: SwitchTrigger):
        """当前策略表现下降时触发切换评估（仅评估+切换，不记录每次评估日志）"""
        current = self._current_strategy[position]
        cur_stats = self._stats[position][current]
        if cur_stats.total_runs < self.config.min_samples:
            return
        # 当前策略近期表现较其累计均值明显下降
        if cur_stats.recent_rewards and (
            cur_stats.mean_reward - cur_stats.recent_mean_reward
        ) > self.config.switch_threshold:
            self._evaluate_and_switch(position, trigger)

    def _evaluate_and_switch(
        self, position: str, trigger: SwitchTrigger
    ) -> Dict[str, Any]:
        """评估并执行切换"""
        current = self._current_strategy[position]
        cur_stats = self._stats[position][current]
        cur_reward = (
            cur_stats.recent_mean_reward if cur_stats.recent_rewards else cur_stats.mean_reward
        )

        # 找最佳替代策略（排除当前策略）
        best_alt = current
        best_alt_reward = cur_reward
        for s in self.strategies:
            if s == current:
                continue
            st = self._stats[position][s]
            r = st.recent_mean_reward if st.recent_rewards else st.mean_reward
            if r > best_alt_reward:
                best_alt_reward = r
                best_alt = s

        # 切换条件：最佳替代显著优于当前，或当前近期表现明显下降
        performance_gap = best_alt_reward - cur_reward
        dropped = (
            cur_stats.recent_rewards
            and (cur_stats.mean_reward - cur_stats.recent_mean_reward)
            > self.config.switch_threshold
        )
        need_switch = (best_alt != current and performance_gap > self.config.switch_threshold) or (
            dropped and best_alt != current
        )

        result = {
            'switched': need_switch,
            'position': position,
            'old_strategy': current,
            'new_strategy': best_alt if need_switch else current,
            'old_reward': round(cur_reward, 6),
            'best_reward': round(best_alt_reward, 6),
            'performance_gap': round(performance_gap, 6),
            'reason': trigger.value,
            'timestamp': datetime.now().isoformat(),
        }

        if need_switch:
            self._current_strategy[position] = best_alt
            self._set_target_around(position, best_alt)
            self._switch_history.append(result)
            if len(self._switch_history) > 200:
                self._switch_history = self._switch_history[-200:]
            logger.info(
                f"策略切换: pos={position} {current}->{best_alt} "
                f"(gap={performance_gap:.3f}, reason={trigger.value})"
            )

        return result

    # ------------------------------------------------------------------
    # 内部：校验
    # ------------------------------------------------------------------
    def _validate_position(self, position: str):
        if position not in POSITION_NAMES:
            raise ValueError(
                f"无效位置 {position!r}，有效位置: {POSITION_NAMES}"
            )

    def _validate_strategy(self, strategy_name: str):
        if strategy_name not in self.strategies:
            raise ValueError(
                f"未知策略 {strategy_name!r}，已注册策略: {self.strategies}"
            )

    # ------------------------------------------------------------------
    # 内部：持久化
    # ------------------------------------------------------------------
    def _load_state(self):
        """从磁盘加载选择器状态"""
        try:
            if not self.history_path.exists():
                return
            with open(self.history_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except Exception as e:
            logger.warning(f"加载策略选择器状态失败: {e}")
            return

        try:
            # 恢复模式
            mode_val = state.get('config', {}).get('mode')
            if mode_val:
                self.config.mode = SelectionMode(mode_val)
            # 恢复覆盖规则
            overrides = state.get('config', {}).get('scene_overrides')
            if isinstance(overrides, dict):
                self.config.scene_overrides = dict(overrides)

            # 恢复当前策略
            cur = state.get('current_strategy', {})
            for pos in POSITION_NAMES:
                if pos in cur and cur[pos] in self.strategies:
                    self._current_strategy[pos] = cur[pos]

            # 恢复统计
            stats_state = state.get('stats', {})
            for pos, strat_map in stats_state.items():
                if pos not in self._stats:
                    continue
                for s_name, sd in strat_map.items():
                    if s_name not in self._stats[pos]:
                        continue
                    st = self._stats[pos][s_name]
                    st.total_runs = int(sd.get('total_runs', 0))
                    st.sum_reward = float(sd.get('sum_reward', 0.0))
                    st.sum_accuracy = float(sd.get('sum_accuracy', 0.0))
                    st.sum_confidence = float(sd.get('sum_confidence', 0.0))
                    st.alpha = float(sd.get('alpha', 1.0))
                    st.beta = float(sd.get('beta', 1.0))
                    st.last_used = sd.get('last_used', '')
                    rr = sd.get('recent_rewards', [])
                    st.recent_rewards = deque(rr, maxlen=self.config.window_size)
                    sr = sd.get('scene_rewards', {})
                    st.scene_rewards = {k: list(v) for k, v in sr.items()} if isinstance(sr, dict) else {}

            # 恢复总拉取次数
            for pos in POSITION_NAMES:
                self._total_pulls[pos] = sum(
                    self._stats[pos][s].total_runs for s in self.strategies
                )

            # 恢复切换历史
            history = state.get('switch_history', [])
            if isinstance(history, list):
                self._switch_history = list(history)[-200:]

            logger.info(
                f"策略选择器状态已加载: 切换历史 {len(self._switch_history)} 条"
            )
        except Exception as e:
            logger.warning(f"解析策略选择器状态失败: {e}")

    def save_state(self):
        """将选择器状态持久化到磁盘"""
        state = {
            'config': self.config.to_dict(),
            'current_strategy': dict(self._current_strategy),
            'stats': {
                pos: {s: st.to_dict() for s, st in strat_map.items()}
                for pos, strat_map in self._stats.items()
            },
            'switch_history': list(self._switch_history[-200:]),
            'saved_at': datetime.now().isoformat(),
        }
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.debug(f"策略选择器状态已保存: {self.history_path}")
        except Exception as e:
            logger.warning(f"保存策略选择器状态失败: {e}")


# ----------------------------------------------------------------------
# 全局单例
# ----------------------------------------------------------------------
_strategy_selector: Optional[StrategyAdaptiveSelector] = None


def get_strategy_selector(
    config: Optional[SelectorConfig] = None,
    strategies: Optional[List[str]] = None,
    force_new: bool = False,
) -> StrategyAdaptiveSelector:
    """获取全局策略自适应选择器单例

    Args:
        config: 选择器配置（仅首次创建时生效）
        strategies: 策略列表（仅首次创建时生效）
        force_new: 是否强制创建新实例（忽略缓存的单例）

    Returns:
        StrategyAdaptiveSelector 实例
    """
    global _strategy_selector
    if _strategy_selector is None or force_new:
        _strategy_selector = StrategyAdaptiveSelector(config=config, strategies=strategies)
    return _strategy_selector
