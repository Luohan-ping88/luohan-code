#!/usr/bin/env python3
"""
策略自适应切换器 V1.0 - 基于性能反馈的闭环自动策略切换

功能:
1. 持续跟踪各策略的历史表现
2. 基于滑动窗口性能评估自动选择最佳策略
3. 支持策略组合优化（多策略加权融合）
4. 漂移触发的策略重评估
5. 闭环反馈: 预测结果验证后自动更新策略评分
"""

import json
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from collections import deque, defaultdict

logger = logging.getLogger(__name__)

_STRATEGY_SWITCHER_PATH = Path(__file__).parent.parent.parent.parent / "models" / "strategy_switcher_state.json"


class StrategyAdaptiveSwitcher:
    """
    策略自适应切换器

    核心机制:
    - 每次预测后记录实际命中率，更新策略评分
    - 使用滑动窗口（最近N期）评估策略表现
    - 当当前策略连续表现不佳时，自动切换到历史最优策略
    - 支持策略组合: 对Top-2策略进行加权融合
    - 数据分布漂移时触发全策略重评估
    """

    # 策略定义（与 StrategyEvaluator.define_strategies() 对齐）
    STRATEGY_DEFINITIONS = {
        'default': {
            'model_weights': {'stacking': 0.4, 'hmm': 0.2, 'copula': 0.2, 'bsts': 0.2},
            'ensemble_method': 'weighted_average'
        },
        'stacking_dominant': {
            'model_weights': {'stacking': 0.7, 'hmm': 0.1, 'copula': 0.1, 'bsts': 0.1},
            'ensemble_method': 'weighted_average'
        },
        'hmm_dominant': {
            'model_weights': {'stacking': 0.1, 'hmm': 0.7, 'copula': 0.1, 'bsts': 0.1},
            'ensemble_method': 'weighted_average'
        },
        'copula_dominant': {
            'model_weights': {'stacking': 0.1, 'hmm': 0.1, 'copula': 0.7, 'bsts': 0.1},
            'ensemble_method': 'weighted_average'
        },
        'voting_ensemble': {
            'model_weights': {'stacking': 0.25, 'hmm': 0.25, 'copula': 0.25, 'bsts': 0.25},
            'ensemble_method': 'voting'
        },
    }

    def __init__(self, window_size: int = 20, min_switch_interval: int = 5,
                 underperform_threshold: float = 0.15, drift_trigger_psi: float = 0.25):
        """
        Args:
            window_size: 滑动窗口大小（评估最近N期）
            min_switch_interval: 最小切换间隔（避免频繁切换）
            underperform_threshold: 连续表现不佳触发切换的阈值
            drift_trigger_psi: 数据漂移PSI阈值，触发全策略重评估
        """
        self.window_size = window_size
        self.min_switch_interval = min_switch_interval
        self.underperform_threshold = underperform_threshold
        self.drift_trigger_psi = drift_trigger_psi

        # 当前激活策略
        self.current_strategy: str = "default"
        # 策略切换计数
        self._switch_count: int = 0
        # 上次切换的期号索引
        self._last_switch_idx: int = -999
        # 当前已连续评估的期数
        self._eval_count: int = 0

        # 各策略的滑动窗口性能记录
        # structure: {strategy_name: deque([(period, top1_hit, top3_hit, top8_hit), ...])}
        self.strategy_performance: Dict[str, deque] = {
            name: deque(maxlen=window_size) for name in self.STRATEGY_DEFINITIONS
        }

        # 策略组合模式: 当多个策略表现接近时，使用加权融合
        self.combo_mode: bool = False
        self.combo_weights: Dict[str, float] = {}

        # 漂移检测状态
        self._last_psi: float = 0.0
        self._drift_detected: bool = False

        self._load_state()

    def get_active_strategy(self) -> str:
        """获取当前激活的策略名称"""
        return self.current_strategy

    def get_active_weights(self) -> Dict[str, float]:
        """获取当前激活策略的模型权重"""
        if self.combo_mode and self.combo_weights:
            # 组合模式: 加权融合多个策略的权重
            fused = defaultdict(float)
            for strategy_name, weight in self.combo_weights.items():
                if strategy_name in self.STRATEGY_DEFINITIONS:
                    for model, w in self.STRATEGY_DEFINITIONS[strategy_name]['model_weights'].items():
                        fused[model] += w * weight
            total = sum(fused.values())
            if total > 0:
                return {k: v / total for k, v in fused.items()}
        return self.STRATEGY_DEFINITIONS.get(self.current_strategy, self.STRATEGY_DEFINITIONS['default'])['model_weights']

    def record_outcome(self, strategy_used: str, period: str,
                       top1_hit: bool, top3_hit: bool, top8_hit: bool):
        """
        记录一次预测的实际结果（闭环反馈）

        Args:
            strategy_used: 本次预测使用的策略名
            period: 期号
            top1_hit: Top-1是否命中
            top3_hit: Top-3是否命中
            top8_hit: Top-8是否命中
        """
        self._eval_count += 1

        if strategy_used not in self.strategy_performance:
            self.strategy_performance[strategy_used] = deque(maxlen=self.window_size)

        self.strategy_performance[strategy_used].append({
            'period': period,
            'top1': int(top1_hit),
            'top3': int(top3_hit),
            'top8': int(top8_hit),
            'timestamp': datetime.now().isoformat()
        })

        logger.info(
            f"[StrategySwitcher] 记录策略 '{strategy_used}' 结果: "
            f"top1={top1_hit}, top3={top3_hit}, top8={top8_hit} (期号 {period})"
        )

        # 触发策略评估与切换
        self._evaluate_and_switch()

        self._save_state()

    def _evaluate_and_switch(self):
        """评估各策略表现，决定是否切换"""
        # 检查最小切换间隔
        if self._eval_count - self._last_switch_idx < self.min_switch_interval:
            return

        # 计算各策略的综合得分
        scores = {}
        for name, history in self.strategy_performance.items():
            if len(history) < 3:
                scores[name] = 0.0
                continue
            recent = list(history)[-self.window_size:]
            top1_rate = np.mean([r['top1'] for r in recent])
            top3_rate = np.mean([r['top3'] for r in recent])
            top8_rate = np.mean([r['top8'] for r in recent])
            # 综合得分: Top-8为主，Top-3和Top-1为辅
            scores[name] = 0.5 * top8_rate + 0.3 * top3_rate + 0.2 * top1_rate

        if not scores:
            return

        # 找到最佳策略
        best_strategy = max(scores, key=scores.get)
        best_score = scores[best_strategy]
        current_score = scores.get(self.current_strategy, 0.0)

        # 切换条件1: 当前策略表现低于阈值且最佳策略明显更好
        if current_score < self.underperform_threshold and best_score > current_score + 0.05:
            self._switch_to(best_strategy, scores, reason="underperform")
            return

        # 切换条件2: 最佳策略显著优于当前（差距>15%）
        if best_score > current_score * 1.15 and best_strategy != self.current_strategy:
            self._switch_to(best_strategy, scores, reason="significant_better")
            return

        # 组合模式评估: Top-2策略得分接近时启用融合
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_scores) >= 2:
            top1_name, top1_score = sorted_scores[0]
            top2_name, top2_score = sorted_scores[1]
            if top2_score > 0 and (top1_score - top2_score) / top2_score < 0.05:
                # 得分接近，启用组合模式
                if not self.combo_mode:
                    self.combo_mode = True
                    total = top1_score + top2_score
                    self.combo_weights = {
                        top1_name: top1_score / total,
                        top2_name: top2_score / total
                    }
                    logger.info(
                        f"[StrategySwitcher] 启用策略组合模式: "
                        f"{top1_name}({top1_score:.3f}) + {top2_name}({top2_score:.3f})"
                    )
            elif self.combo_mode:
                # 得分差距拉大，关闭组合模式
                self.combo_mode = False
                self.combo_weights = {}
                logger.info("[StrategySwitcher] 关闭策略组合模式，回归单一策略")

    def _switch_to(self, new_strategy: str, scores: Dict[str, float], reason: str):
        """执行策略切换"""
        old_strategy = self.current_strategy
        self.current_strategy = new_strategy
        self._last_switch_idx = self._eval_count
        self._switch_count += 1
        self.combo_mode = False
        self.combo_weights = {}

        logger.info(
            f"[StrategySwitcher] 策略切换: {old_strategy} → {new_strategy} "
            f"(原因: {reason}, 得分: {scores.get(old_strategy, 0):.3f} → {scores.get(new_strategy, 0):.3f}, "
            f"总切换次数: {self._switch_count})"
        )

    def trigger_drift_reassessment(self, psi_value: float):
        """
        数据分布漂移触发全策略重评估

        Args:
            psi_value: 当前PSI值
        """
        self._last_psi = psi_value
        if psi_value > self.drift_trigger_psi:
            self._drift_detected = True
            logger.warning(
                f"[StrategySwitcher] 检测到数据漂移 (PSI={psi_value:.4f} > {self.drift_trigger_psi}), "
                f"触发策略重评估"
            )
            # 漂移时清空历史性能记录，让所有策略重新平等竞争
            for name in self.strategy_performance:
                self.strategy_performance[name].clear()
            # 重置为默认策略
            self.current_strategy = "default"
            self.combo_mode = False
            self.combo_weights = {}
            self._last_switch_idx = self._eval_count
        else:
            self._drift_detected = False

    def get_status_report(self) -> Dict[str, Any]:
        """获取策略切换器状态报告"""
        scores = {}
        for name, history in self.strategy_performance.items():
            if len(history) == 0:
                scores[name] = {"score": 0, "samples": 0, "top1": 0, "top3": 0, "top8": 0}
                continue
            recent = list(history)
            scores[name] = {
                "score": 0.5 * np.mean([r['top8'] for r in recent]) +
                         0.3 * np.mean([r['top3'] for r in recent]) +
                         0.2 * np.mean([r['top1'] for r in recent]),
                "samples": len(recent),
                "top1_rate": float(np.mean([r['top1'] for r in recent])),
                "top3_rate": float(np.mean([r['top3'] for r in recent])),
                "top8_rate": float(np.mean([r['top8'] for r in recent])),
            }

        return {
            "current_strategy": self.current_strategy,
            "combo_mode": self.combo_mode,
            "combo_weights": self.combo_weights,
            "switch_count": self._switch_count,
            "eval_count": self._eval_count,
            "last_psi": self._last_psi,
            "drift_detected": self._drift_detected,
            "strategy_scores": scores,
            "timestamp": datetime.now().isoformat(),
        }

    def _save_state(self):
        """持久化状态"""
        try:
            _STRATEGY_SWITCHER_PATH.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "current_strategy": self.current_strategy,
                "switch_count": self._switch_count,
                "eval_count": self._eval_count,
                "last_switch_idx": self._last_switch_idx,
                "combo_mode": self.combo_mode,
                "combo_weights": self.combo_weights,
                "last_psi": self._last_psi,
                "strategy_performance": {
                    name: list(hist) for name, hist in self.strategy_performance.items()
                }
            }
            with open(_STRATEGY_SWITCHER_PATH, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[StrategySwitcher] 状态保存失败: {e}")

    def _load_state(self):
        """加载持久化状态"""
        try:
            if _STRATEGY_SWITCHER_PATH.exists():
                with open(_STRATEGY_SWITCHER_PATH, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.current_strategy = state.get("current_strategy", "default")
                self._switch_count = state.get("switch_count", 0)
                self._eval_count = state.get("eval_count", 0)
                self._last_switch_idx = state.get("last_switch_idx", -999)
                self.combo_mode = state.get("combo_mode", False)
                self.combo_weights = state.get("combo_weights", {})
                self._last_psi = state.get("last_psi", 0.0)
                perf = state.get("strategy_performance", {})
                for name, hist in perf.items():
                    if name not in self.strategy_performance:
                        self.strategy_performance[name] = deque(maxlen=self.window_size)
                    self.strategy_performance[name].extend(hist)
                logger.info(f"[StrategySwitcher] 状态已加载: 当前策略={self.current_strategy}, 评估次数={self._eval_count}")
        except Exception as e:
            logger.warning(f"[StrategySwitcher] 状态加载失败，使用默认状态: {e}")
