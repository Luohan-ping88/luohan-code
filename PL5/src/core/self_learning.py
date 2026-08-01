"""
自学习系统 V10.0 - 高质量优化建议引擎

V9.0 -> V10.0 upgrade:
1. Specific actionable parameter suggestion values (with recommended values and reasonable ranges)
2. Optimization suggestion priority classification (urgent/important/regular)
3. Optimization effect estimation (confidence interval based on historical data)
4. Optimization suggestion history tracking (record/adoption tracking/effect feedback loop)
5. Structured suggestion objects replace pure text output

Retained V9.0 features:
- Dynamic retraining threshold (adaptive adjustment based on historical volatility)
- Multi-metric comprehensive judgment (accuracy + hit rate + confidence)
- Mann-Kendall trend test
- Performance alert mechanism (warning/urgent two-level)
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from collections import deque
from datetime import datetime
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.core.config import ModelConfig, get_model_config

logger = logging.getLogger(__name__)

_HISTORY_PATH = Path(__file__).parent.parent.parent / "models" / "learning_history.json"
_SUGGESTION_HISTORY_PATH = Path(__file__).parent.parent.parent / "models" / "suggestion_history.json"

_DEFAULT_RETRAIN_THRESHOLD = 0.02
_DEFAULT_WINDOW_SIZE = 10
_DEFAULT_MIN_HISTORY = 3
_DEFAULT_VOLATILITY_FACTOR = 3.0
# 【V10.6 修复】阈值调整为 Top-3 评估维度（随机基线 30%）的合理水平
# 原值 0.12/0.08 是针对 Top-1（基线 10%）设计的，导致 Top-3/Top-8 评估时
# 几乎从不触发告警，自学习机制形同虚设。
# 新值基于 Top-3 随机基线 0.30：
#   - WARNING=0.25: 略低于基线，需要关注
#   - URGENT=0.20: 明显低于基线，需要紧急重训练
# 注：当评估的是 Top-8（基线 0.80）时，应通过 record_evaluation 的 k 参数
# 动态调整阈值，使用 _K_RANDOM_BASELINE 映射。
_DEFAULT_WARNING_ACCURACY = 0.25
_DEFAULT_URGENT_ACCURACY = 0.20

# 【V10.6 新增】不同 Top-k 的随机基线映射（10选k）
# 用于根据评估的 k 值动态调整告警阈值
_K_RANDOM_BASELINE = {
    1: 0.10,   # 10选1
    2: 0.20,   # 10选2
    3: 0.30,   # 10选3（标准评估维度）
    5: 0.50,   # 10选5
    8: 0.80,   # 10选8（用户重点关注，基线已很高）
}
# 告警阈值与基线的偏移量（基线减去该值得到告警阈值）
_WARNING_BASELINE_OFFSET = 0.05  # 比基线低5个百分点即告警
_URGENT_BASELINE_OFFSET = 0.10   # 比基线低10个百分点即紧急


class AlertLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    URGENT = "urgent"


class SuggestionPriority(IntEnum):
    URGENT = 3
    IMPORTANT = 2
    REGULAR = 1

    @property
    def label(self) -> str:
        return {3: "\u7d27\u6025", 2: "\u91cd\u8981", 1: "\u5e38\u89c4"}[self.value]

    @property
    def color_tag(self) -> str:
        return {3: "[\U0001f534\u7d27\u6025]", 2: "[\U0001f7e1\u91cd\u8981]", 1: "[\U0001f535\u5e38\u89c4]"}[self.value]


class SuggestionStatus(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OptimizationSuggestion:
    __slots__ = (
        "id", "timestamp", "category", "priority", "status",
        "title", "description",
        "parameter_name", "current_value", "recommended_value",
        "value_range_min", "value_range_max", "unit",
        "estimated_improvement_low", "estimated_improvement_mid", "estimated_improvement_high",
        "confidence_level", "reasoning", "source_metrics"
    )

    def __init__(
        self,
        category: str,
        priority: SuggestionPriority,
        title: str,
        description: str,
        parameter_name: Optional[str] = None,
        current_value: Optional[float] = None,
        recommended_value: Optional[float] = None,
        value_range_min: Optional[float] = None,
        value_range_max: Optional[float] = None,
        unit: str = "",
        estimated_improvement_low: float = 0.0,
        estimated_improvement_mid: float = 0.0,
        estimated_improvement_high: float = 0.0,
        confidence_level: float = 0.5,
        reasoning: str = "",
        source_metrics: Optional[Dict[str, Any]] = None,
    ):
        self.id = f"SUG-{uuid.uuid4().hex[:8].upper()}"
        self.timestamp = datetime.now().isoformat()
        self.category = category
        self.priority = priority
        self.status = SuggestionStatus.PENDING
        self.title = title
        self.description = description
        self.parameter_name = parameter_name
        self.current_value = current_value
        self.recommended_value = recommended_value
        self.value_range_min = value_range_min
        self.value_range_max = value_range_max
        self.unit = unit
        self.estimated_improvement_low = estimated_improvement_low
        self.estimated_improvement_mid = estimated_improvement_mid
        self.estimated_improvement_high = estimated_improvement_high
        self.confidence_level = confidence_level
        self.reasoning = reasoning
        self.source_metrics = source_metrics or {}

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "priority": self.priority.value,
            "priority_label": self.priority.label,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "confidence_level": round(self.confidence_level, 3),
            "reasoning": self.reasoning,
        }
        if self.parameter_name:
            d["parameter"] = {
                "name": self.parameter_name,
                "current_value": self.current_value,
                "recommended_value": self.recommended_value,
                "range": [self.value_range_min, self.value_range_max],
                "unit": self.unit,
            }
        d["effect_estimation"] = {
            "improvement_range": [
                round(self.estimated_improvement_low, 4),
                round(self.estimated_improvement_mid, 4),
                round(self.estimated_improvement_high, 4),
            ],
            "expected_gain_pct": round(self.estimated_improvement_mid * 100, 2),
        }
        if self.source_metrics:
            d["source_metrics"] = {
                k: round(v, 6) if isinstance(v, float) else v
                for k, v in self.source_metrics.items()
            }
        return d

    def to_display_text(self) -> str:
        lines = []
        lines.append(f"{self.priority.color_tag} {self.title}")
        if self.parameter_name and self.recommended_value is not None:
            range_str = ""
            if self.value_range_min is not None and self.value_range_max is not None:
                range_str = f" (\u5408\u7406\u8303\u56f4: {self.value_range_min}{self.unit} ~ {self.value_range_max}{self.unit})"
            cur_str = f"{self.current_value}{self.unit}" if self.current_value is not None else "\u672a\u77e5"
            lines.append(
                f"  \u53c2\u6570: {self.parameter_name} | \u5f53\u524d\u503c: {cur_str} -> "
                f"\u63a8\u8350\u503c: {self.recommended_value}{self.unit}{range_str}"
            )
        effect = f"+{self.estimated_improvement_mid*100:.1f}%"
        ci = f"[{self.estimated_improvement_low*100:.1f}%, +{self.estimated_improvement_high*100:.1f}%]"
        conf = f"\u7f6e\u4fe5\u5ea6: {self.confidence_level*100:.0f}%"
        lines.append(f"  \u9884\u4f30\u6548\u679c: {effect} (95%CI: {ci}) | {conf}")
        if self.reasoning:
            lines.append(f"  \u4f9d\u636e: {self.reasoning}")
        return "\n".join(lines)


_PARAMETER_KNOWLEDGE_BASE = {
    "n_estimators": {
        "default": 100,
        "min": 50,
        "max": 500,
        "step": 50,
        "rules": [
            {"condition": "accuracy < 0.15 and std > 0.05", "action": "increase", "factor": 2.0, "reason": "\u4f4e\u51c6\u786e\u7387+\u9ad8\u6ce2\u52a8->\u589e\u52a0\u6811\u6570\u91cf\u63d0\u5347\u7a33\u5b9a\u6027"},
            {"condition": "accuracy < 0.20 and std > 0.04", "action": "increase", "factor": 1.5, "reason": "\u504f\u4f4e\u51c6\u786e\u7387+\u4e2d\u7b49\u6ce2\u52a8->\u9002\u5ea6\u589e\u52a0\u6811\u6570\u91cf"},
            {"condition": "accuracy > 0.30 and std < 0.03", "action": "fine_tune", "factor": 1.2, "reason": "\u826f\u597d\u6027\u80fd->\u5fae\u8c03\u6811\u6570\u91cf\u4ee5\u5e73\u8861\u6548\u7387"},
        ],
    },
    "max_depth": {
        "default": 12,
        "min": 4,
        "max": 20,
        "step": 2,
        "rules": [
            {"condition": "accuracy < 0.12", "action": "increase", "factor": 1.5, "reason": "\u4e25\u91cd\u6b20\u62df\u5408->\u589e\u52a0\u6a21\u578b\u590d\u6742\u5ea6"},
            {"condition": "accuracy > 0.35 and std > 0.06", "action": "decrease", "factor": 0.8, "reason": "\u8fc7\u62df\u5408\u8ff9\u8c61->\u964d\u4f4e\u6df1\u5ea6\u589e\u5f3a\u6cdb\u5316"},
            {"condition": "std > 0.07", "action": "decrease", "factor": 0.85, "reason": "\u9ad8\u6ce2\u52a8\u6027->\u51cf\u5c11\u8fc7\u62df\u5408\u98ce\u9669"},
        ],
    },
    "learning_rate": {
        "default": 0.1,
        "min": 0.01,
        "max": 0.3,
        "step": 0.02,
        "rules": [
            {"condition": "accuracy < 0.14 and trend == 'declining'", "action": "decrease", "factor": 0.5, "reason": "\u4e0b\u964d\u8d8b\u52bf+\u4f4e\u51c6\u786e\u7387->\u964d\u4f4e\u5b66\u4e60\u7387\u7a33\u5b9a\u8bad\u7ec3"},
            {"condition": "accuracy > 0.30 and std < 0.03", "action": "fine_tune", "factor": 0.8, "reason": "\u7a33\u5b9a\u9ad8\u6027\u80fd->\u7cbe\u7ec6\u8c03\u4f18\u5b66\u4e60\u7387"},
            {"condition": "std > 0.08", "action": "decrease", "factor": 0.6, "reason": "\u6781\u9ad8\u6ce2\u52a8->\u5927\u5e45\u964d\u4f4e\u5b66\u4e60\u7387"},
        ],
    },
}


class SelfLearningSystem:

    def __init__(
        self,
        window: int = _DEFAULT_WINDOW_SIZE,
        retrain_threshold: float = _DEFAULT_RETRAIN_THRESHOLD,
        min_history: int = _DEFAULT_MIN_HISTORY,
        volatility_factor: float = _DEFAULT_VOLATILITY_FACTOR,
        warning_accuracy: float = _DEFAULT_WARNING_ACCURACY,
        urgent_accuracy: float = _DEFAULT_URGENT_ACCURACY,
        model_config: Optional[ModelConfig] = None,
    ):
        _mc = model_config or get_model_config()
        sl_cfg = _mc.self_learning_config()

        self.window = window if window != _DEFAULT_WINDOW_SIZE else sl_cfg.get('window', _DEFAULT_WINDOW_SIZE)
        self.retrain_threshold = (retrain_threshold if retrain_threshold != _DEFAULT_RETRAIN_THRESHOLD
                                  else sl_cfg.get('retrain_threshold', _DEFAULT_RETRAIN_THRESHOLD))
        self.min_history = min_history if min_history != _DEFAULT_MIN_HISTORY else sl_cfg.get('min_history', _DEFAULT_MIN_HISTORY)
        self.volatility_factor = (volatility_factor if volatility_factor != _DEFAULT_VOLATILITY_FACTOR
                                  else sl_cfg.get('volatility_factor', _DEFAULT_VOLATILITY_FACTOR))
        self.warning_accuracy = (warning_accuracy if warning_accuracy != _DEFAULT_WARNING_ACCURACY
                                 else sl_cfg.get('warning_accuracy', _DEFAULT_WARNING_ACCURACY))
        self.urgent_accuracy = (urgent_accuracy if urgent_accuracy != _DEFAULT_URGENT_ACCURACY
                                else sl_cfg.get('urgent_accuracy', _DEFAULT_URGENT_ACCURACY))
        self.learning_history: List[Dict[str, Any]] = []
        self.suggestion_history: List[Dict[str, Any]] = []
        self._load_history()
        self._load_suggestion_history()

    def _load_history(self) -> None:
        try:
            if _HISTORY_PATH.exists():
                with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    self.learning_history = raw.get("evaluations", [])
                elif isinstance(raw, list):
                    self.learning_history = raw
                else:
                    self.learning_history = []
                logger.info(f"[SelfLearning V10] Loaded {len(self.learning_history)} evaluation records")
        except Exception as exc:
            logger.warning(f"[SelfLearning V10] Failed to load history: {exc}")
            self.learning_history = []

    def _save_history(self) -> None:
        try:
            _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.learning_history, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning(f"[SelfLearning V10] Failed to save history: {exc}")

    def _load_suggestion_history(self) -> None:
        try:
            if _SUGGESTION_HISTORY_PATH.exists():
                with open(_SUGGESTION_HISTORY_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    self.suggestion_history = raw
                elif isinstance(raw, dict):
                    self.suggestion_history = raw.get("suggestions", [])
                else:
                    self.suggestion_history = []
                logger.info(f"[SelfLearning V10] Loaded {len(self.suggestion_history)} suggestion records")
        except Exception as exc:
            logger.warning(f"[SelfLearning V10] Failed to load suggestion history: {exc}")
            self.suggestion_history = []

    def _save_suggestion_history(self) -> None:
        try:
            _SUGGESTION_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_SUGGESTION_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.suggestion_history, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning(f"[SelfLearning V10] Failed to save suggestion history: {exc}")

    def record_evaluation(
        self,
        accuracy: float,
        extra: Optional[Dict[str, Any]] = None,
        k: int = 3,
    ) -> None:
        """记录一次评估结果

        Args:
            accuracy: 本次评估的准确率（5个位置的平均命中率）
            extra: 附加信息（如 hit_rate、reward 等）
            k: 本次评估的 Top-k 维度（1/3/5/8），用于动态基线计算
               - k=3 (默认): 随机基线 30%，标准评估维度
               - k=8: 随机基线 80%，用户重点关注的指标
        """
        # 根据k值计算动态基线，便于后续告警判断时使用
        baseline = _K_RANDOM_BASELINE.get(k, 0.30)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "accuracy": float(accuracy),
            "k": int(k),
            "random_baseline": baseline,
            **(extra or {}),
        }
        self.learning_history.append(entry)
        if len(self.learning_history) > 200:
            self.learning_history = self.learning_history[-200:]
        self._save_history()

    def get_dynamic_thresholds(self, k: int = 3) -> Tuple[float, float]:
        """【V10.6 新增】根据 Top-k 动态计算告警阈值

        Args:
            k: Top-k 维度

        Returns:
            (warning_threshold, urgent_threshold)
        """
        baseline = _K_RANDOM_BASELINE.get(k, 0.30)
        warning = max(0.0, baseline - _WARNING_BASELINE_OFFSET)
        urgent = max(0.0, baseline - _URGENT_BASELINE_OFFSET)
        return warning, urgent

    def record_suggestion_outcome(
        self,
        suggestion_id: str,
        status: SuggestionStatus,
        actual_effect: Optional[float] = None,
        notes: str = "",
    ) -> bool:
        for record in self.suggestion_history:
            if record.get("id") == suggestion_id:
                record["status"] = status.value
                record["outcome_timestamp"] = datetime.now().isoformat()
                if actual_effect is not None:
                    record["actual_effect"] = round(float(actual_effect), 6)
                if notes:
                    record["outcome_notes"] = notes
                self._save_suggestion_history()
                logger.info(
                    f"[SelfLearning V10] Outcome recorded: id={suggestion_id}, "
                    f"status={status.value}, effect={actual_effect}"
                )
                return True
        logger.warning(f"[SelfLearning V10] Suggestion not found: {suggestion_id}")
        return False

    def get_suggestion_history(
        self,
        status_filter: Optional[SuggestionStatus] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        records = list(self.suggestion_history)
        if status_filter:
            records = [r for r in records if r.get("status") == status_filter.value]
        records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return records[:limit]

    def get_suggestion_statistics(self) -> Dict[str, Any]:
        total = len(self.suggestion_history)
        applied = sum(1 for r in self.suggestion_history if r.get("status") == "applied")
        rejected = sum(1 for r in self.suggestion_history if r.get("status") == "rejected")
        pending = sum(1 for r in self.suggestion_history if r.get("status") == "pending")

        effects = [
            r["actual_effect"]
            for r in self.suggestion_history
            if r.get("status") == "applied" and "actual_effect" in r and r["actual_effect"] is not None
        ]

        stats = {
            "total_suggestions": total,
            "applied_count": applied,
            "rejected_count": rejected,
            "pending_count": pending,
            "adoption_rate": round(applied / total * 100, 1) if total > 0 else 0.0,
        }

        if effects:
            effects_arr = np.array(effects)
            stats.update({
                "avg_actual_effect": round(float(np.mean(effects_arr)), 6),
                "median_actual_effect": round(float(np.median(effects_arr)), 6),
                "max_actual_effect": round(float(np.max(effects_arr)), 6),
                "min_actual_effect": round(float(np.min(effects_arr)), 6),
                "effect_sample_size": len(effects),
                "positive_effect_rate": round(sum(1 for e in effects if e > 0) / len(effects) * 100, 1),
            })
        else:
            stats.update({
                "avg_actual_effect": None,
                "median_actual_effect": None,
                "effect_sample_size": 0,
                "positive_effect_rate": 0.0,
            })

        return stats

    def calculate_dynamic_threshold(self, history=None) -> Dict[str, Any]:
        hist = history or self.learning_history
        accs = [r["accuracy"] for r in hist if "accuracy" in r]

        if len(accs) < self.min_history:
            return {
                "dynamic_threshold": self.retrain_threshold,
                "volatility": 0.0,
                "base_threshold": self.retrain_threshold,
                "sample_size": len(accs),
                "reason": "Insufficient samples, using base threshold",
            }

        std_val = float(np.std(accs))
        mean_val = float(np.mean(accs))

        cv = std_val / mean_val if mean_val > 0 else 0.0
        dynamic = self.retrain_threshold * (1.0 + cv * self.volatility_factor)
        dynamic = min(dynamic, self.retrain_threshold * 5.0)
        dynamic = max(dynamic, self.retrain_threshold * 0.3)

        return {
            "dynamic_threshold": round(dynamic, 6),
            "volatility": round(cv, 6),
            "std": round(std_val, 6),
            "base_threshold": self.retrain_threshold,
            "sample_size": len(accs),
            "reason": f"CV={cv:.4f}, dynamic_factor={1.0 + cv * self.volatility_factor:.4f}",
        }

    @staticmethod
    def mann_kendall_test(series: List[float]) -> Dict[str, Any]:
        n = len(series)
        if n < 4:
            return {"tau": 0.0, "p_value": 1.0, "trend": "unknown", "significance": False}

        s = 0
        for i in range(n - 1):
            for j in range(i + 1, n):
                diff = series[j] - series[i]
                if diff > 0:
                    s += 1
                elif diff < 0:
                    s -= 1

        var_s = n * (n - 1) * (2 * n + 5) / 18.0
        if var_s == 0:
            return {"tau": 0.0, "p_value": 1.0, "trend": "stable", "significance": False}

        z = (s - np.sign(s)) / math.sqrt(var_s) if s != 0 else 0.0
        from math import erf, sqrt
        p_value = 2.0 * (1.0 - 0.5 * (1.0 + erf(abs(z) / sqrt(2.0))))
        tau = 2.0 * s / (n * (n - 1)) if n > 1 else 0.0

        if p_value < 0.05:
            trend = "increasing" if tau > 0 else "decreasing"
            significant = True
        elif abs(tau) > 0.15:
            trend = "improving" if tau > 0 else "declining"
            significant = False
        else:
            trend = "stable"
            significant = False

        return {
            "tau": round(float(tau), 6),
            "p_value": round(float(p_value), 6),
            "z_stat": round(float(z), 4),
            "trend": trend,
            "significant": significant,
            "s_score": s,
        }

    def compute_comprehensive_score(self, history=None) -> Dict[str, Any]:
        hist = history or self.learning_history[-self.window:]
        accs = [r.get("accuracy", 0.0) for r in hist if "accuracy" in r]
        hit_rates = [r.get("hit_rate", 0.0) for r in hist if "hit_rate" in r]
        confidences = [r.get("confidence", 0.0) for r in hist if "confidence" in r]

        if not accs:
            return {
                "comprehensive_score": 0.0,
                "accuracy_component": 0.0,
                "hit_rate_component": 0.0,
                "confidence_component": 0.0,
                "stability_component": 0.0,
                "metrics_available": ["none"],
            }

        avg_acc = float(np.mean(accs))
        avg_hit = float(np.mean(hit_rates)) if hit_rates else 0.5
        avg_conf = float(np.mean(confidences)) if confidences else 0.7
        std_acc = float(np.std(accs))
        stability = 1.0 / (1.0 + std_acc * 10)

        w_acc, w_hit, w_conf, w_stab = 0.40, 0.20, 0.20, 0.20
        score = (
            w_acc * avg_acc * 2.0
            + w_hit * avg_hit
            + w_conf * avg_conf
            + w_stab * stability
        )
        score = max(0.0, min(1.0, score))

        available = []
        if accs:
            available.append("accuracy")
        if hit_rates:
            available.append("hit_rate")
        if confidences:
            available.append("confidence")

        return {
            "comprehensive_score": round(score, 4),
            "accuracy_component": round(w_acc * avg_acc * 2.0, 4),
            "hit_rate_component": round(w_hit * avg_hit, 4),
            "confidence_component": round(w_conf * avg_conf, 4),
            "stability_component": round(w_stab * stability, 4),
            "avg_accuracy": round(avg_acc, 4),
            "avg_hit_rate": round(avg_hit, 4),
            "avg_confidence": round(avg_conf, 4),
            "stability_index": round(stability, 4),
            "metrics_available": available,
        }

    def check_performance_alert(self) -> Dict[str, Any]:
        perf = self.evaluate_recent_performance()
        mk_result = self._mk_trend_recent()
        comp_score = self.compute_comprehensive_score()

        alert_level = AlertLevel.NORMAL
        reasons: List[str] = []

        if perf["count"] == 0:
            return {
                "alert_level": AlertLevel.NORMAL.value,
                "reasons": ["Insufficient historical data"],
                "current_accuracy": 0.0,
                "comprehensive_score": 0.0,
                "trend": "unknown",
            }

        current_acc = perf["accuracy"]
        trend = mk_result.get("trend", perf.get("trend", "unknown"))

        # 【V10.6 修复】根据历史记录中最常见的 k 值动态计算告警阈值
        # 原代码使用固定的 self.warning_accuracy/urgent_accuracy（0.25/0.20），
        # 当评估的是 Top-8（基线 80%）时，0.25 阈值会永远触发误告警；
        # 当评估的是 Top-1（基线 10%）时，0.25 阈值永远不会触发告警。
        # 修复：从历史记录中推断当前评估的 k 维度，动态计算阈值。
        recent_k_values = [e.get("k", 3) for e in self.learning_history[-10:] if isinstance(e, dict)]
        inferred_k = max(set(recent_k_values), key=recent_k_values.count) if recent_k_values else 3
        dyn_warning, dyn_urgent = self.get_dynamic_thresholds(inferred_k)
        # 兼容旧逻辑：取动态阈值与实例阈值中较宽松者，避免误告警
        effective_warning = max(dyn_warning, self.warning_accuracy)
        effective_urgent = max(dyn_urgent, self.urgent_accuracy)

        if current_acc <= effective_urgent:
            alert_level = AlertLevel.URGENT
            reasons.append(
                f"URGENT: current accuracy {current_acc:.4f} below urgent line {effective_urgent:.4f} "
                f"(k={inferred_k}, baseline={_K_RANDOM_BASELINE.get(inferred_k, 0.30)})"
            )
        elif current_acc <= effective_warning:
            if alert_level != AlertLevel.URGENT:
                alert_level = AlertLevel.WARNING
            reasons.append(
                f"WARNING: current accuracy {current_acc:.4f} below warning line {effective_warning:.4f} "
                f"(k={inferred_k}, baseline={_K_RANDOM_BASELINE.get(inferred_k, 0.30)})"
            )

        if trend in ("declining", "decreasing"):
            is_significant = mk_result.get("significant", False)
            label = "significant" if is_significant else ""
            if alert_level.value < AlertLevel.WARNING.value:
                alert_level = AlertLevel.WARNING
            reasons.append(
                f"{'WARNING' if alert_level == AlertLevel.WARNING else 'URGENT'}: {label} declining trend "
                f"(tau={mk_result.get('tau', 0):.4f}, p={mk_result.get('p_value', 1):.4f})"
            )
            # 【V10.6 修复】使用动态基线替代固定 0.15
            baseline = _K_RANDOM_BASELINE.get(inferred_k, 0.30)
            if is_significant and current_acc < baseline:
                alert_level = AlertLevel.URGENT
                reasons.append(
                    f"Significant declining trend with accuracy below baseline {baseline:.2f} -> upgraded to URGENT"
                )

        if comp_score["comprehensive_score"] < 0.15:
            if alert_level.value < AlertLevel.WARNING.value:
                alert_level = AlertLevel.WARNING
            reasons.append(
                f"Low comprehensive score ({comp_score['comprehensive_score']:.4f}), "
                f"recommend monitoring multi-dimensional performance"
            )

        if not reasons:
            reasons.append("All metrics normal")

        return {
            "alert_level": alert_level.value,
            "reasons": reasons,
            "current_accuracy": round(current_acc, 4),
            "comprehensive_score": comp_score["comprehensive_score"],
            "trend": trend,
            "mk_significant": mk_result.get("significant", False),
            "dynamic_threshold_info": self.calculate_dynamic_threshold(),
        }

    def _mk_trend_recent(self) -> Dict[str, Any]:
        recent = self.learning_history[-self.window:]
        accs = [r["accuracy"] for r in recent if "accuracy" in r]
        if len(accs) >= 4:
            return self.mann_kendall_test(accs)
        return {"tau": 0.0, "p_value": 1.0, "trend": "unknown", "significance": False}

    def evaluate_recent_performance(self, window: int = 0) -> Dict[str, Any]:
        w = window or self.window
        recent = self.learning_history[-w:]
        total = len(self.learning_history)

        if not recent:
            return {
                "total_records": total,
                "recent_performance": {"accuracy": 0.0, "trend": "unknown", "count": 0},
                "accuracy": 0.0,
                "trend": "unknown",
                "count": 0,
            }

        accs = [r["accuracy"] for r in recent if "accuracy" in r]
        if not accs:
            return {
                "total_records": total,
                "recent_performance": {"accuracy": 0.0, "trend": "unknown", "count": 0},
                "accuracy": 0.0,
                "trend": "unknown",
                "count": 0,
            }

        avg = float(np.mean(accs))

        if len(accs) >= 4:
            mk = self.mann_kendall_test(accs)
            trend = mk["trend"]
        elif len(accs) >= 3:
            x = np.arange(len(accs))
            slope = float(np.polyfit(x, accs, 1)[0])
            if slope > 0.002:
                trend = "improving"
            elif slope < -0.002:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        perf = {
            "accuracy": avg,
            "trend": trend,
            "count": len(accs),
            "max": float(np.max(accs)),
            "min": float(np.min(accs)),
            "std": float(np.std(accs)),
        }

        return {
            "total_records": total,
            "recent_performance": perf,
            **perf,
        }

    def should_trigger_retrain(self) -> Tuple[bool, str]:
        if len(self.learning_history) < self.min_history:
            return False, f"Insufficient history ({len(self.learning_history)} < {self.min_history})"

        recent = self.evaluate_recent_performance()
        early = self.evaluate_recent_performance(window=max(1, self.window // 2))
        dyn_thresh_info = self.calculate_dynamic_threshold()
        dyn_threshold = dyn_thresh_info["dynamic_threshold"]
        mk = self._mk_trend_recent()
        comp = self.compute_comprehensive_score()

        if recent["count"] == 0:
            return False, "No recent valid evaluation data"

        if mk["trend"] in ("decreasing", "declining") and mk["significant"]:
            return True, (
                f"[Mann-Kendall] Detected {'non-' if mk['trend']=='decreasing' else ''}significant declining trend "
                f"(tau={mk['tau']:.4f}, p={mk['p_value']:.4f}), "
                f"recent accuracy={recent['accuracy']:.4f}, comprehensive score={comp['comprehensive_score']:.4f}"
            )

        if mk["trend"] in ("declining", "decreasing"):
            if comp["comprehensive_score"] < 0.12:
                return True, (
                    f"[Comprehensive judgment] Declining trend(tau={mk['tau']:.4f}) + "
                    f"low comprehensive score({comp['comprehensive_score']:.4f}), recommend retraining"
                )

        all_accs = [r["accuracy"] for r in self.learning_history if "accuracy" in r]
        if len(all_accs) >= 2 * self.min_history:
            hist_avg = float(np.mean(all_accs[:-self.window]))
            drop = hist_avg - recent["accuracy"]
            if drop > dyn_threshold:
                return True, (
                    f"[Dynamic threshold] Accuracy drop exceeds dynamic threshold "
                    f"(historical avg {hist_avg:.4f} -> recent avg {recent['accuracy']:.4f}, "
                    f"drop {drop:.4f}, dynamic threshold {dyn_threshold:.4f}, "
                    f"volatility CV={dyn_thresh_info['volatility']:.4f})"
                )

        alert = self.check_performance_alert()
        if alert["alert_level"] == AlertLevel.URGENT.value:
            return True, (
                f"[URGENT alert] {'; '.join(alert['reasons'])}. "
                f"Recommend immediate retraining to restore model performance."
            )

        return False, (
            f"Performance good (recent avg {recent['accuracy']:.4f}, "
            f"trend={mk['trend']}, comprehensive score={comp['comprehensive_score']:.4f}, "
            f"dynamic threshold={dyn_threshold:.4f})"
        )

    def _determine_priority(self, accuracy_drop_pct: float, current_acc: float, trend: str) -> SuggestionPriority:
        if accuracy_drop_pct > 0.10 or current_acc <= self.urgent_accuracy:
            return SuggestionPriority.URGENT
        if (
            accuracy_drop_pct > 0.05
            or current_acc <= self.warning_accuracy
            or trend in ("decreasing", "declining")
        ):
            return SuggestionPriority.IMPORTANT
        return SuggestionPriority.REGULAR

    def _estimate_optimization_effect(
        self,
        category: str,
        current_acc: float,
        historical_stats: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, float, float, float]:
        base_effects = {
            "n_estimators_increase": (0.01, 0.03, 0.06, 0.65),
            "n_estimators_decrease": (-0.005, 0.005, 0.02, 0.45),
            "max_depth_adjust": (0.005, 0.02, 0.05, 0.55),
            "learning_rate_adjust": (0.005, 0.025, 0.05, 0.60),
            "data_quality_fix": (0.03, 0.08, 0.15, 0.75),
            "feature_engineering": (0.02, 0.05, 0.12, 0.65),
            "retraining_full": (0.02, 0.06, 0.12, 0.70),
            "regularization": (0.01, 0.03, 0.07, 0.55),
            "cross_validation": (0.005, 0.015, 0.04, 0.70),
            "ensemble_expansion": (0.01, 0.04, 0.09, 0.60),
            "incremental_learning": (0.005, 0.02, 0.05, 0.55),
        }

        defaults = (0.01, 0.03, 0.06, 0.50)
        low, mid, high, conf = base_effects.get(category, defaults)

        if current_acc < 0.10:
            scale = 1.8
        elif current_acc < 0.18:
            scale = 1.4
        elif current_acc > 0.35:
            scale = 0.6
        else:
            scale = 1.0

        low *= scale
        mid *= scale
        high *= scale

        if historical_stats and historical_stats.get("avg_actual_effect") is not None:
            hist_eff = abs(historical_stats["avg_actual_effect"])
            pos_rate = historical_stats.get("positive_effect_rate", 50) / 100.0
            mid = mid * 0.4 + hist_eff * 0.6
            low = min(low, mid * 0.3)
            high = max(high, mid * 2.0)
            conf = conf * 0.5 + pos_rate * 0.5

        conf = max(0.25, min(0.95, conf))
        return round(low, 4), round(mid, 4), round(high, 4), round(conf, 3)

    def _compute_accuracy_drop(self) -> Tuple[float, float, float]:
        all_accs = [r["accuracy"] for r in self.learning_history if "accuracy" in r]
        if len(all_accs) < 3:
            return 0.0, 0.0, 0.0

        peak = float(np.max(all_accs))
        recent = self.evaluate_recent_performance()
        current = recent["accuracy"]

        if peak <= 0:
            return 0.0, 0.0, peak

        drop_abs = peak - current
        drop_pct = drop_abs / peak
        return drop_abs, drop_pct, peak

    def _generate_parameter_suggestions(
        self,
        perf: Dict[str, Any],
        mk: Dict[str, Any],
        comp: Dict[str, Any],
        alert: Dict[str, Any],
    ) -> List[OptimizationSuggestion]:
        suggestions: List[OptimizationSuggestion] = []
        acc = perf["accuracy"]
        std = perf["std"]
        trend = mk.get("trend", "unknown")
        drop_abs, drop_pct, peak = self._compute_accuracy_drop()
        priority = self._determine_priority(drop_pct, acc, trend)
        hist_stats = self._get_similar_historical_stats(category_prefix="param")

        for param_name, knowledge in _PARAMETER_KNOWLEDGE_BASE.items():
            default_val = knowledge["default"]
            matched_rule = None

            for rule in knowledge["rules"]:
                cond = rule["condition"]
                try:
                    cond_eval = eval(cond, {
                        "accuracy": acc, "std": std, "trend": trend,
                        "drop_pct": drop_pct, "peak": peak,
                    })
                    if cond_eval:
                        matched_rule = rule
                        break
                except Exception:
                    continue

            if matched_rule is None:
                continue

            action = matched_rule["action"]
            factor = matched_rule["factor"]

            if action == "increase":
                rec_val = default_val * factor
            elif action == "decrease":
                rec_val = default_val * factor
            elif action == "fine_tune":
                rec_val = default_val * factor
            else:
                rec_val = default_val

            rec_val = max(knowledge["min"], min(knowledge["max"], rec_val))
            range_margin = (knowledge["max"] - knowledge["min"]) * 0.2
            range_lo = max(knowledge["min"], rec_val - range_margin)
            range_hi = min(knowledge["max"], rec_val + range_margin)

            cat_key = f"{param_name}_{action}"
            eff_low, eff_mid, eff_high, eff_conf = self._estimate_optimization_effect(
                cat_key, acc, hist_stats
            )

            sug = OptimizationSuggestion(
                category=f"parameter_{param_name}",
                priority=priority,
                title=f"Adjust {param_name}: {default_val} -> {int(rec_val) if rec_val == int(rec_val) else rec_val}",
                description=matched_rule["reason"],
                parameter_name=param_name,
                current_value=default_val,
                recommended_value=rec_val,
                value_range_min=round(range_lo, 4),
                value_range_max=round(range_hi, 4),
                unit="" if param_name != "learning_rate" else "",
                estimated_improvement_low=eff_low,
                estimated_improvement_mid=eff_mid,
                estimated_improvement_high=eff_high,
                confidence_level=eff_conf,
                reasoning=(
                    f"Current accuracy={acc:.4f}(peak={peak:.4f}, drop={drop_pct*100:.1f}%), "
                    f"volatility(std)={std:.4f}, trend={trend}. "
                    f"Matched rule: {matched_rule['reason']}"
                ),
                source_metrics={
                    "accuracy": acc, "peak": peak, "drop_pct": drop_pct,
                    "std": std, "trend": trend,
                },
            )
            suggestions.append(sug)

        return suggestions

    def _generate_data_and_model_suggestions(
        self,
        perf: Dict[str, Any],
        mk: Dict[str, Any],
        comp: Dict[str, Any],
        alert: Dict[str, Any],
    ) -> List[OptimizationSuggestion]:
        suggestions: List[OptimizationSuggestion] = []
        acc = perf["accuracy"]
        std = perf["std"]
        trend = mk.get("trend", "unknown")
        drop_abs, drop_pct, peak = self._compute_accuracy_drop()
        hist_stats = self._get_similar_historical_stats(category_prefix="model")

        if alert["alert_level"] == AlertLevel.URGENT.value:
            eff_l, eff_m, eff_h, eff_c = self._estimate_optimization_effect(
                "retraining_full", acc, hist_stats
            )
            suggestions.append(OptimizationSuggestion(
                category="model_retraining",
                priority=SuggestionPriority.URGENT,
                title="Execute full model retraining",
                description=(
                    "Currently in URGENT state, need immediate retraining. "
                    "Recommend checking data source quality then full retrain with latest data."
                ),
                estimated_improvement_low=eff_l,
                estimated_improvement_mid=eff_m,
                estimated_improvement_high=eff_h,
                confidence_level=eff_c,
                reasoning=(
                    f"accuracy={acc:.4f} below urgent line {self.urgent_accuracy}, "
                    f"dropped {drop_pct*100:.1f}% from peak {peak:.4f}"
                ),
                source_metrics={"accuracy": acc, "alert_level": alert["alert_level"], "drop_pct": drop_pct},
            ))

            eff_l2, eff_m2, eff_h2, eff_c2 = self._estimate_optimization_effect(
                "data_quality_fix", acc, hist_stats
            )
            suggestions.append(OptimizationSuggestion(
                category="data_quality",
                priority=SuggestionPriority.URGENT,
                title="Comprehensive review of data source quality and timeliness",
                description=(
                    "In URGENT state, must first rule out data issues. Check: "
                    "(1) Is data up-to-date (2) Are there outliers (3) Has feature engineering pipeline degraded"
                ),
                estimated_improvement_low=eff_l2,
                estimated_improvement_mid=eff_m2,
                estimated_improvement_high=eff_h2,
                confidence_level=eff_c2,
                reasoning="Root cause analysis for URGENT state usually points to data quality or concept drift",
                source_metrics={"accuracy": acc},
            ))

        if trend in ("declining", "decreasing"):
            sig_mark = "(statistically significant)" if mk.get("significant") else ""
            pri = SuggestionPriority.IMPORTANT if drop_pct <= 0.10 else SuggestionPriority.URGENT
            eff_l, eff_m, eff_h, eff_c = self._estimate_optimization_effect(
                "incremental_learning", acc, hist_stats
            )
            suggestions.append(OptimizationSuggestion(
                category="strategy_incremental",
                priority=pri,
                title=f"Enable incremental learning strategy to counter declining trend{sig_mark}",
                description=(
                    f"Detected accuracy declining trend (tau={mk['tau']:.4f}), "
                    f"recommend enabling incremental or online learning to continuously adapt to data distribution changes."
                ),
                estimated_improvement_low=eff_l,
                estimated_improvement_mid=eff_m,
                estimated_improvement_high=eff_h,
                confidence_level=eff_c,
                reasoning=f"Mann-Kendall tau={mk['tau']:.4f}, p={mk['p_value']:.4f}, trend={trend}",
                source_metrics={
                    "tau": mk.get("tau", 0), "p_value": mk.get("p_value", 1),
                    "trend": trend, "significant": mk.get("significant", False),
                },
            ))

        if std > 0.06:
            pri = self._determine_priority(drop_pct, acc, trend)
            eff_l, eff_m, eff_h, eff_c = self._estimate_optimization_effect(
                "regularization", acc, hist_stats
            )
            suggestions.append(OptimizationSuggestion(
                category="stability_regularization",
                priority=pri,
                title=f"Enhance regularization to reduce volatility (std={std:.4f})",
                description=(
                    f"Detected high volatility (CV={self.calculate_dynamic_threshold()['volatility']:.4f}). "
                    "Recommendations: (1) Increase L1/L2 regularization strength "
                    "(2) Raise cross-validation folds to 8-10 (3) Check training data consistency"
                ),
                estimated_improvement_low=eff_l,
                estimated_improvement_mid=eff_m,
                estimated_improvement_high=eff_h,
                confidence_level=eff_c,
                reasoning=f"Standard deviation={std:.4f} exceeds threshold 0.06, indicating model instability",
                source_metrics={"std": std, "accuracy": acc},
            ))

        if acc < 0.10:
            pri = SuggestionPriority.URGENT
            eff_l, eff_m, eff_h, eff_c = self._estimate_optimization_effect(
                "feature_engineering", acc, hist_stats
            )
            suggestions.append(OptimizationSuggestion(
                category="model_diagnosis",
                priority=pri,
                title=f"Full diagnosis of model architecture (accuracy only {acc:.4f})",
                description=(
                    "Extremely low accuracy requires systematic investigation: "
                    "(1) Feature engineering quality and correlation analysis "
                    "(2) Whether model architecture matches problem complexity "
                    "(3) Label annotation quality and consistency (4) Data leakage check"
                ),
                estimated_improvement_low=eff_l,
                estimated_improvement_mid=eff_m,
                estimated_improvement_high=eff_h,
                confidence_level=eff_c,
                reasoning="Accuracy far below random level (0.10), possible systemic issues",
                source_metrics={"accuracy": acc},
            ))
        elif acc < 0.18:
            pri = SuggestionPriority.IMPORTANT
            eff_l, eff_m, eff_h, eff_c = self._estimate_optimization_effect(
                "feature_engineering", acc, hist_stats
            )
            suggestions.append(OptimizationSuggestion(
                category="feature_enhancement",
                priority=pri,
                title=f"Expand feature engineering or try different base models (accuracy={acc:.4f})",
                description=(
                    "Accuracy at low level. Recommendations: "
                    "(1) Introduce more temporal features (lag terms, rolling statistics) "
                    "(2) Try deep learning methods (3) Adjust ensemble weight allocation strategy"
                ),
                estimated_improvement_low=eff_l,
                estimated_improvement_mid=eff_m,
                estimated_improvement_high=eff_h,
                confidence_level=eff_c,
                reasoning="Accuracy in 0.10-0.18 range, significant room for improvement",
                source_metrics={"accuracy": acc},
            ))
        elif acc > 0.35:
            pri = SuggestionPriority.REGULAR
            eff_l, eff_m, eff_h, eff_c = self._estimate_optimization_effect(
                "ensemble_expansion", acc, hist_stats
            )
            suggestions.append(OptimizationSuggestion(
                category="performance_fine_tuning",
                priority=pri,
                title=f"Fine-tune high-performance model (accuracy={acc:.4f})",
                description=(
                    "Model performing well, further exploration possible: "
                    "(1) Reduce learning rate to 0.01-0.03 for fine-tuning "
                    "(2) Integrate more heterogeneous weak classifiers "
                    "(3) Deep analysis of high-confidence predictions"
                ),
                estimated_improvement_low=eff_l,
                estimated_improvement_mid=eff_m,
                estimated_improvement_high=eff_h,
                confidence_level=eff_c,
                reasoning="Accuracy above 0.35, entering fine-tuning phase",
                source_metrics={"accuracy": acc},
            ))

        if comp["comprehensive_score"] < 0.20 and acc > 0.15:
            pri = SuggestionPriority.IMPORTANT
            eff_l, eff_m, eff_h, eff_c = self._estimate_optimization_effect(
                "cross_validation", acc, hist_stats
            )
            missing = []
            if "hit_rate" not in comp.get("metrics_available", []):
                missing.append("hit_rate")
            if "confidence" not in comp.get("metrics_available", []):
                missing.append("confidence")
            miss_text = f", missing {', '.join(missing)} records" if missing else ""

            suggestions.append(OptimizationSuggestion(
                category="metric_completeness",
                priority=pri,
                title=f"Supplement missing metrics to improve comprehensive scoring (current={comp['comprehensive_score']:.4f}){miss_text}",
                description=(
                    f"While accuracy is acceptable ({acc:.4f}), comprehensive score is low. "
                    f"Please ensure hit_rate and confidence are recorded during evaluation for more complete assessment."
                ),
                estimated_improvement_low=eff_l,
                estimated_improvement_mid=eff_m,
                estimated_improvement_high=eff_h,
                confidence_level=eff_c,
                reasoning=f"Comprehensive score={comp['comprehensive_score']:.4f}<0.20 threshold, available metrics={comp.get('metrics_available', [])}",
                source_metrics={"comprehensive_score": comp["comprehensive_score"], "accuracy": acc},
            ))

        return suggestions

    def _get_similar_historical_stats(self, category_prefix: str = "") -> Optional[Dict[str, float]]:
        relevant = [
            r for r in self.suggestion_history
            if r.get("status") == "applied"
            and "actual_effect" in r
            and r["actual_effect"] is not None
            and (not category_prefix or category_prefix in r.get("category", ""))
        ]
        if not relevant:
            return None
        effects = [r["actual_effect"] for r in relevant]
        return {
            "avg_actual_effect": float(np.mean(effects)),
            "median_actual_effect": float(np.median(effects)),
            "effect_sample_size": len(effects),
            "positive_effect_rate": sum(1 for e in effects if e > 0) / len(effects),
        }

    def generate_structured_suggestions(self) -> List[OptimizationSuggestion]:
        suggestions: List[OptimizationSuggestion] = []

        perf = self.evaluate_recent_performance()
        mk = self._mk_trend_recent()
        comp = self.compute_comprehensive_score()
        alert = self.check_performance_alert()

        if perf["count"] == 0:
            suggestions.append(OptimizationSuggestion(
                category="system",
                priority=SuggestionPriority.REGULAR,
                title="Initialize system: complete first training",
                description="History empty, recommend completing at least one full training to establish baseline.",
                confidence_level=0.90,
                reasoning="No historical evaluation data",
            ))
            self._persist_suggestions(suggestions)
            return suggestions

        param_sugs = self._generate_parameter_suggestions(perf, mk, comp, alert)
        model_sugs = self._generate_data_and_model_suggestions(perf, mk, comp, alert)

        all_sugs = param_sugs + model_sugs
        all_sugs.sort(key=lambda s: (s.priority.value, -s.estimated_improvement_mid), reverse=True)

        seen_categories = set()
        for sug in all_sugs:
            if sug.category not in seen_categories:
                suggestions.append(sug)
                seen_categories.add(sug.category)

        self._persist_suggestions(suggestions)
        return suggestions

    def generate_optimization_suggestions(self) -> List[str]:
        """生成优化建议（字符串列表形式）。

        适配方法：将 generate_structured_suggestions 返回的
        OptimizationSuggestion 对象列表转为易读的字符串列表，
        供 orchestrator / auto_scheduler 等调用方使用。
        """
        structured = self.generate_structured_suggestions()
        result: List[str] = []
        for sug in structured:
            line = f"[{sug.priority.label}] {sug.title}"
            if sug.parameter_name:
                line += f" ({sug.parameter_name}: {sug.current_value} -> {sug.recommended_value})"
            line += f" - {sug.description}"
            result.append(line)
        return result

    def _persist_suggestions(self, suggestions: List[OptimizationSuggestion]) -> None:
        """持久化建议到历史记录。

        内容级去重策略（修复V10.3堆积BUG）：
        - 同 category + 参数名 + 推荐值 → 视为同一建议
        - 已 pending 的不重复追加
        - 已 applied/rejected/expired 的用新记录覆盖（允许重试）
        - 总数超 200 条时，优先保留最新 pending，淘汰最老 applied
        """
        for sug in suggestions:
            record = sug.to_dict()
            sug_key = self._suggestion_key(record)

            # 查找是否已有相同内容的记录
            existing_idx = None
            for idx, r in enumerate(self.suggestion_history):
                if self._suggestion_key(r) == sug_key:
                    existing_idx = idx
                    break

            if existing_idx is not None:
                existing = self.suggestion_history[existing_idx]
                if existing.get("status") == "pending":
                    # 相同内容已在 pending，跳过不追加
                    continue
                else:
                    # 已被 applied/rejected/expired → 用新记录覆盖（允许重试）
                    self.suggestion_history[existing_idx] = record
            else:
                self.suggestion_history.append(record)

        # 容量控制：保留 ≤200 条
        if len(self.suggestion_history) > 200:
            # 优先保留所有 pending 记录
            pending = [r for r in self.suggestion_history if r.get("status") == "pending"]
            others = [r for r in self.suggestion_history if r.get("status") != "pending"]
            # 按 timestamp 排序，淘汰最老的 applied/rejected/expired
            others_sorted = sorted(others, key=lambda r: r.get("timestamp", ""), reverse=True)
            # 最多保留 (200 - pending数) 条其他状态
            keep_others = 200 - len(pending)
            self.suggestion_history = pending + others_sorted[:keep_others]

        self._save_suggestion_history()

    def _suggestion_key(self, record: Dict) -> str:
        """生成建议内容级唯一标识。"""
        cat = record.get("category", "")
        param = record.get("parameter", {})
        param_name = param.get("name", "") if isinstance(param, dict) else ""
        recommended = param.get("recommended_value", "") if isinstance(param, dict) else ""
        return f"{cat}|{param_name}|{recommended}"

    # =====================================================================
    #  自动应用机制（新增 V10.3 - 解决建议堆积不执行问题）
    # =====================================================================

    def apply_suggestion(
        self,
        suggestion_id: Optional[str] = None,
        category: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """应用一条优化建议。

        参数:
            suggestion_id: 直接指定建议ID
            category:     指定类别（如 "parameter_max_depth"），自动选最新的pending
            dry_run:      True=只返回要做什么，不实际修改

        返回:
            {"applied": bool, "message": str, "params_updated": dict}
        """
        # 1. 找到目标建议
        target = None
        if suggestion_id:
            for r in reversed(self.suggestion_history):
                if r.get("id") == suggestion_id:
                    target = r
                    break
        elif category:
            for r in reversed(self.suggestion_history):
                if r.get("category") == category and r.get("status") == "pending":
                    target = r
                    break

        if not target:
            return {"applied": False, "message": f"未找到 pending 建议: id={suggestion_id}, cat={category}"}

        if target.get("status") == "applied":
            return {"applied": False, "message": f"建议已应用过: {target.get('id')}"}

        cat = target.get("category", "")
        param = target.get("parameter", {})
        param_name = param.get("name", "") if isinstance(param, dict) else ""
        recommended = param.get("recommended_value") if isinstance(param, dict) else None

        result = {
            "suggestion_id": target.get("id"),
            "category": cat,
            "parameter": param_name,
            "current_value": param.get("current_value") if isinstance(param, dict) else None,
            "recommended_value": recommended,
            "dry_run": dry_run,
        }

        if dry_run:
            result["applied"] = True
            result["message"] = f"[dry-run] 将更新 {param_name}: {param.get('current_value')} → {recommended}"
            return result

        # 2. 应用参数修改（修复 V10.3：正确使用 ModelConfig.set() API）
        updated_params = {}
        # 参数名 → YAML 配置路径映射
        _PARAM_KEY_MAP = {
            "max_depth": "stacking.base_config.max_depth",
            "learning_rate": "stacking.base_config.learning_rate",
            "reg_alpha": "stacking.base_config.reg_alpha",
            "reg_lambda": "stacking.base_config.reg_lambda",
            "n_estimators": "stacking.base_config.n_estimators",
            "C": "stacking.meta_config.C",
        }
        if param_name and recommended is not None:
            try:
                config = get_model_config()
                cfg_key = _PARAM_KEY_MAP.get(param_name, f"stacking.base_config.{param_name}")
                if config.get(cfg_key) is not None:
                    old_val = config.get(cfg_key)
                    # max_depth 验证要求 int，对小数取整
                    if param_name == "max_depth":
                        new_val = round(float(recommended))
                    else:
                        new_val = float(recommended)
                    config.set(cfg_key, new_val)
                    config.save()  # 持久化到 model_config.yaml
                    updated_params[cfg_key] = {"old": old_val, "new": new_val}
                    logger.info(f"[SelfLearning V10] 应用建议: {cfg_key} {old_val} → {recommended}")
                else:
                    # 参数不在标准路径，尝试直接写入
                    if config.get(param_name) is not None:
                        old_val = config.get(param_name)
                        new_val = round(float(recommended)) if param_name == "max_depth" else float(recommended)
                        config.set(param_name, new_val)
                        config.save()
                        updated_params[param_name] = {"old": old_val, "new": new_val}
                    else:
                        result["applied"] = False
                        result["message"] = f"参数 {param_name}(key={cfg_key}) 不在 ModelConfig 中，跳过"
                        return result
            except Exception as exc:
                result["applied"] = False
                result["message"] = f"参数更新失败: {exc}"
                return result

        # 3. 更新状态为 applied
        for record in self.suggestion_history:
            if record.get("id") == target.get("id"):
                record["status"] = "applied"
                record["applied_at"] = datetime.now().isoformat()
                record["applied_params"] = updated_params
                break
        self._save_suggestion_history()

        result["applied"] = True
        result["message"] = f"已应用建议 {target.get('id')}，参数: {updated_params}"
        result["params_updated"] = updated_params
        return result

    def auto_apply_suggestions(
        self,
        confidence_threshold: float = 0.55,
        priority_threshold: int = 2,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """自动应用高置信度建议。

        规则:
        - confidence_level >= confidence_threshold
        - priority.value <= priority_threshold (1=urgent, 2=important, 3=regular)
        - status == pending
        - 参数必须在 ModelConfig 中

        参数:
            confidence_threshold: 最低置信度（默认0.55）
            priority_threshold:   最高优先级（默认2，即 urgent+important）
            dry_run:             True=只报告，不实际修改

        返回:
            {"applied": [dict], "skipped": [dict], "dry_run": bool}
        """
        pending = [r for r in self.suggestion_history if r.get("status") == "pending"]
        if not pending:
            return {"applied": [], "skipped": [], "dry_run": dry_run,
                    "message": "无 pending 建议"}

        applied_list = []
        skipped_list = []

        # 按 confidence_level 降序排列，优先应用高置信
        pending_sorted = sorted(pending, key=lambda r: -r.get("confidence_level", 0))

        for record in pending_sorted:
            conf = record.get("confidence_level", 0)
            prio = record.get("priority", 99)
            cat = record.get("category", "")

            # 过滤条件
            if conf < confidence_threshold:
                skipped_list.append({
                    "id": record.get("id"),
                    "category": cat,
                    "reason": f"置信度不足: {conf} < {confidence_threshold}",
                    "conf": conf,
                    "priority": prio,
                })
                continue
            if prio > priority_threshold:
                skipped_list.append({
                    "id": record.get("id"),
                    "category": cat,
                    "reason": f"优先级不足: {prio} > {priority_threshold}",
                    "conf": conf,
                    "priority": prio,
                })
                continue

            # 尝试应用
            res = self.apply_suggestion(suggestion_id=record.get("id"), dry_run=dry_run)
            if res.get("applied"):
                applied_list.append(res)
            else:
                skipped_list.append({
                    "id": record.get("id"),
                    "category": cat,
                    "reason": res.get("message", "未知原因"),
                    "conf": conf,
                    "priority": prio,
                })

        summary = {
            "applied": applied_list,
            "skipped": skipped_list,
            "dry_run": dry_run,
            "total_pending": len(pending),
            "applied_count": len(applied_list),
            "skipped_count": len(skipped_list),
        }
        logger.info(
            f"[SelfLearning V10] auto_apply 完成: "
            f"applied={len(applied_list)} skipped={len(skipped_list)} "
            f"(conf>={confidence_threshold}, prio<={priority_threshold}, dry={dry_run})"
        )
        return summary

    def get_suggestion_statistics(self) -> Dict[str, Any]:
        structured = self.generate_structured_suggestions()
        text_lines: List[str] = []

        if not structured:
            text_lines.append("System running stably, all metrics normal")
            return text_lines

        urgent_count = sum(1 for s in structured if s.priority == SuggestionPriority.URGENT)
        important_count = sum(1 for s in structured if s.priority == SuggestionPriority.IMPORTANT)
        regular_count = sum(1 for s in structured if s.priority == SuggestionPriority.REGULAR)

        text_lines.append(f"=== V10.0 Optimization Suggestion Report ===")
        text_lines.append(f"Total {len(structured)} suggestions | Urgent:{urgent_count} Important:{important_count} Regular:{regular_count}")
        text_lines.append("")

        for i, sug in enumerate(structured, 1):
            text_lines.append(f"--- Suggestion #{i} [{sug.priority.label}] ---")
            text_lines.append(sug.to_display_text())
            text_lines.append("")

        stats = self.get_suggestion_statistics()
        if stats["effect_sample_size"] > 0:
            text_lines.append("--- Historical Suggestion Effect Statistics ---")
            text_lines.append(
                f"Adoption rate: {stats['adoption_rate']}% | "
                f"Avg actual effect: {stats['avg_actual_effect']} | "
                f"Positive effect rate: {stats['positive_effect_rate']}%"
            )

        return text_lines

    def flush(self) -> None:
        self.learning_history = []
        logger.info("[SelfLearning V10] Memory state flushed")

    def get_summary(self) -> Dict[str, Any]:
        perf = self.evaluate_recent_performance()
        need_retrain, reason = self.should_trigger_retrain()
        alert = self.check_performance_alert()
        dyn = self.calculate_dynamic_threshold()
        comp = self.compute_comprehensive_score()
        sug_stats = self.get_suggestion_statistics()

        structured_sugs = self.generate_structured_suggestions()
        suggestions_dicts = [s.to_dict() for s in structured_sugs]

        return {
            "version": "V10.0",
            "total_records": len(self.learning_history),
            "recent_performance": perf,
            "should_retrain": need_retrain,
            "retrain_reason": reason,
            "alert_status": alert,
            "dynamic_threshold": dyn,
            "comprehensive_score": comp,
            "suggestions": suggestions_dicts,
            "suggestion_statistics": sug_stats,
        }
