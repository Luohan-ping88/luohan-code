"""复盘闭环 ReviewEngine (Task: §6)。

复盘 预测结果 vs 实际开奖 的差异，回溯到可调杠杆（推理策略/特征工程/
学习率/超参数），并结合"状态空间 S"检索历史同态经验，产出调整动作并沉淀经验。

核心方法：
- build_state_vector: 构造状态向量 S（数据分布特征 + 近端命中率 + 漂移）。
- attribute_discrepancy: 按可调域做归因差分。
- match_state: 检索历史同态 (S', A', Δ) 中 Δ>0 的有效动作。
- propose_adjustments: 结合归因与同态经验产出本轮动作。
- record_experience: 沉淀 (S, A, Δ) 经验入库。
- run_review: 一站式复盘入口。

所有异常降级，绝不中断主流程。
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.core.closed_loop_memory import ClosedLoopMemoryStore

logger = logging.getLogger(__name__)

_DEFAULT_MEMORY_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "closed_loop_memory.json"

# 状态向量中参与相似度检索的连续数值键
_STATE_NUMERIC_KEYS = [
    "volatility", "hot_ratio", "span_mean", "sum_mean",
    "feature_discrimination", "psi_drift",
    "top1_rate", "top3_rate", "top8_rate",
]
# 归一化参考范围（min, max），用于相似度检索前的无量纲化
_STATE_RANGES = {
    "volatility": (0.0, 1.0),
    "hot_ratio": (0.0, 1.0),
    "span_mean": (0.0, 180.0),
    "sum_mean": (0.0, 800.0),
    "feature_discrimination": (0.0, 1.0),
    "psi_drift": (0.0, 1.0),
    "top1_rate": (0.0, 1.0),
    "top3_rate": (0.0, 1.0),
    "top8_rate": (0.0, 1.0),
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _extract_top_k(pred: Dict[str, Any]) -> List[Any]:
    """从预测记录中提取 top_k。兼容平铺格式与真实嵌套格式两种。"""
    if not isinstance(pred, dict):
        return []
    topk = pred.get("top_k")
    if topk:
        return topk
    pred_data = pred.get("predictions")
    if isinstance(pred_data, dict):
        for pos in ("shi", "wan", "qian", "bai", "ge"):
            pos_pred = pred_data.get(pos)
            if isinstance(pos_pred, dict) and pos_pred.get("top_k"):
                return pos_pred["top_k"]
    return []


def _topk_hit_rate(recent_preds: List[Dict], actual_opens: List[Any]) -> Dict[str, float]:
    """统计近期预测 top-1/3/8 命中率（0~1）。"""
    top1 = top3 = top8 = 0
    n = 0
    for pred, actual in zip(recent_preds, actual_opens):
        topk = _extract_top_k(pred)
        if not isinstance(actual, (list, tuple)) or not topk:
            continue
        target = set(actual)
        n += 1
        if target & set(topk[:1]):
            top1 += 1
        if target & set(topk[:3]):
            top3 += 1
        if target & set(topk[:8]):
            top8 += 1
    if n == 0:
        return {"top1_rate": 0.0, "top3_rate": 0.0, "top8_rate": 0.0}
    return {
        "top1_rate": top1 / n,
        "top3_rate": top3 / n,
        "top8_rate": top8 / n,
    }


class ReviewEngine:
    """状态空间复盘引擎。

    Attributes:
        memory: 统一持久化记忆库（需支持 experiences 键）。
    """

    def __init__(self, memory_path: Optional[Union[str, Path]] = None) -> None:
        path = Path(memory_path) if memory_path else _DEFAULT_MEMORY_PATH
        self.memory = ClosedLoopMemoryStore(path=path)

    # ---- ① 状态向量 ----
    def build_state_vector(
        self,
        recent_preds: Optional[List[Dict]] = None,
        actual_opens: Optional[List[Any]] = None,
        feature_stats: Optional[Dict[str, float]] = None,
        switcher_status: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """构造状态向量 S。只保留有限的数值特征，便于后续相似度检索。"""
        hit = _topk_hit_rate(recent_preds or [], actual_opens or [])
        feat = feature_stats or {}
        sw = switcher_status or {}
        state = {
            "volatility": float(feat.get("volatility", 0.0)),
            "hot_ratio": float(feat.get("hot_ratio", 0.0)),
            "span_mean": float(feat.get("span_mean", 30.0)),
            "sum_mean": float(feat.get("sum_mean", 120.0)),
            "feature_discrimination": float(feat.get("feature_discrimination", 0.0)),
            "psi_drift": float(sw.get("psi_drift", sw.get("last_psi", 0.0))),
            "top1_rate": float(hit["top1_rate"]),
            "top3_rate": float(hit["top3_rate"]),
            "top8_rate": float(hit["top8_rate"]),
        }
        return state

    # ---- ② 归因差分 ----
    def attribute_discrepancy(
        self,
        pred_topk: List[Any],
        actual: List[Any],
        ctx: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """按可调域做归因差分。

        返回候选调整域列表：[{"domain": "strategy"|"feature"|"learning_rate"|"hyperparam",
                               "strength": float, "reason": str}]
        """
        ctx = ctx or {}
        target = set(actual or [])
        preds = [p for p in (pred_topk or [])]
        hit_set = target & set(preds)
        if not target or not preds:
            return []
        hit_ratio = len(hit_set) / min(len(preds), max(1, len(target)))
        # 全命中 → 无需调整
        if hit_ratio >= 1.0:
            return []

        attribution: List[Dict[str, Any]] = []

        # 策略域：当前激活策略产生的权重贡献，差分显著时归因策略
        strategy = ctx.get("strategy", "default")
        miss_ratio = 1.0 - hit_ratio
        if miss_ratio > 0.4:
            attribution.append({
                "domain": "strategy",
                "strength": round(miss_ratio, 3),
                "reason": f"策略 '{strategy}' 命中率不足 (hit={hit_ratio:.2f})，建议切换/组合",
            })

        # 特征工程域：命中但分散（命中集合小却位置靠后）往往归因特征区分度不足
        if miss_ratio > 0.25:
            attribution.append({
                "domain": "feature",
                "strength": round(miss_ratio * 0.8, 3),
                "reason": "特征区分度不足，建议调整窗口/特征数/回看深度",
            })

        # 超参数 / 学习率域：整体偏低（含 top3 也未命中）时归因拟合或过拟合
        if not (target & set(preds[:3])) and miss_ratio > 0:  # top3 均未命中
            attribution.append({
                "domain": "hyperparam",
                "strength": round(0.5 + 0.4 * miss_ratio, 3),
                "reason": "Top-3 均未命中，疑似超参欠拟合/过拟合，建议调整",
            })
            attribution.append({
                "domain": "learning_rate",
                "strength": round(min(1.0, 0.3 + 0.4 * miss_ratio), 3),
                "reason": "更新幅度可能不足/过大，建议调整学习率",
            })

        return attribution

    # ---- ③ 同态经验检索 ----
    def match_state(
        self,
        state: Dict[str, float],
        experiences: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """对历史经验做"同态"相似度检索，返回 Δ>0 的有效经验（按相似度降序）。"""
        valid = [
            e for e in experiences
            if isinstance(e, dict)
            and isinstance(e.get("state"), dict)
            and e.get("delta_accuracy", 0.0) > 0
        ]
        if not valid:
            return []

        scored = []
        for e in valid:
            sim = self._state_similarity(state, e["state"])
            scored.append((sim, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    @staticmethod
    def _state_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
        """基于归一化欧氏距离的相似度（越接近 → 越 1）。"""
        total_sq = 0.0
        count = 0
        for key in _STATE_NUMERIC_KEYS:
            if key not in a or key not in b:
                continue
            lo, hi = _STATE_RANGES.get(key, (0.0, 1.0))
            span = (hi - lo) or 1.0
            an = _clamp(a[key], lo, hi) / span
            bn = _clamp(b[key], lo, hi) / span
            total_sq += (an - bn) ** 2
            count += 1
        if count == 0:
            return 0.0
        from math import sqrt
        return round(1.0 - sqrt(total_sq / count), 4)

    # ---- ③' 调整动作生成 ----
    def propose_adjustments(
        self,
        state: Dict[str, float],
        attribution: List[Dict[str, Any]],
        matches: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """结合归因与同态经验，产出本轮调整动作。"""
        actions: List[Dict[str, Any]] = []

        # 先用同态经验里 Δ>0 的动作兜底（若其域也被归因命中）
        att_domains = {a.get("domain") for a in attribution}
        for m in matches:
            for act in m.get("actions", []):
                domain = act.get("domain")
                if domain in att_domains and not any(
                    a.get("domain") == domain and a.get("source") == "experience" for a in actions
                ):
                    actions.append({**act, "source": "experience",
                                    "expected_gain": m.get("delta_accuracy")})

        # 归因里尚未被经验覆盖的域，给出保守的基础调整
        covered = {a.get("domain") for a in actions}
        default_by_domain = {
            "strategy": {"value": "review_strategy"},
            "feature": {"value": "review_feature_window"},
            "learning_rate": {"value": "review_lr_step"},
            "hyperparam": {"value": "review_hyperparam"},
        }
        for a in attribution:
            if a.get("domain") not in covered:
                actions.append({
                    "domain": a["domain"],
                    "strength": a.get("strength", 0.5),
                    "value": default_by_domain.get(a["domain"], {}).get("value", "monitor"),
                    "reason": a.get("reason", ""),
                    "source": "attribution",
                })
        return actions

    # ---- ④ 经验沉淀 ----
    def record_experience(
        self,
        state: Dict[str, float],
        actions: List[Dict[str, Any]],
        outcome_delta: float,
        period: Optional[str] = None,
    ) -> None:
        """沉淀一条 (S, A, Δ) 经验并持久化。"""
        from datetime import datetime
        self.memory.append("experiences", {
            "state": state,
            "actions": actions,
            "delta_accuracy": round(float(outcome_delta), 6),
            "period": period,
            "timestamp": datetime.now().isoformat(),
        })
        self.memory.save()
        logger.info("[ReviewEngine] 沉淀经验: period=%s, Δ=%.4f, 动作数=%d",
                    period, float(outcome_delta), len(actions))

    # ---- 一站式复盘入口 ----
    def run_review(
        self,
        period: Optional[str] = None,
        predictions: Optional[Dict[str, Any]] = None,
        actual: Optional[List[Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行一次完整复盘，返回 {"state", "attribution", "actions", "stored"}。"""
        context = context or {}
        predictions = predictions or {}
        recent_preds = predictions.get("recent_preds") or []
        actual_opens = predictions.get("actual_opens") or (actual if actual is not None else [])
        feature_stats = context.get("feature_stats") or {}
        switcher_status = context.get("switcher_status") or {}

        try:
            state = self.build_state_vector(
                recent_preds=recent_preds,
                actual_opens=actual_opens,
                feature_stats=feature_stats,
                switcher_status=switcher_status,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ReviewEngine] build_state_vector 失败: %s", exc)
            state = {}

        try:
            # 归因的 top_k：优先用显式传入，否则取最近一期预测的 top_k
            pred_topk = (predictions or {}).get("top_k") or (_extract_top_k(recent_preds[-1])
                                                             if recent_preds else [])
            attribution = self.attribute_discrepancy(
                pred_topk=pred_topk,
                actual=actual_opens[-1] if actual_opens else [],
                ctx=context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ReviewEngine] attribute_discrepancy 失败: %s", exc)
            attribution = []

        matches: List[Dict[str, Any]] = []
        actions: List[Dict[str, Any]] = []
        try:
            experiences = self.memory.get("experiences")
            if state:
                matches = self.match_state(state, experiences, top_k=context.get("top_k", 5))
                actions = self.propose_adjustments(state, attribution, matches)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ReviewEngine] 经验检索/调整生成失败: %s", exc)

        stored = False
        # 无归因也无动作时，仍记录一条 dimensionless 观察，用于评估回报
        # 但为避免污染，仅在有归因差分时沉淀可复用经验
        if state and actions:
            try:
                self.record_experience(
                    state=state,
                    actions=actions,
                    outcome_delta=0.0,
                    period=period,
                )
                stored = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("[ReviewEngine] 经验沉淀失败: %s", exc)

        return {
            "state": state,
            "attribution": attribution,
            "matches": matches,
            "actions": actions,
            "stored": stored,
        }