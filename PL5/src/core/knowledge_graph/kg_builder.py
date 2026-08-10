"""知识图谱 Builder V1.0 - 节点/边写入与主流程事件落图

提供低层 upsert API 和高层事件 API（record_prediction/record_actual_hits等）。
所有写入方法幂等，基于 PRIMARY KEY 去重。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import kuzu
    KUZU_AVAILABLE = True
except ImportError:
    KUZU_AVAILABLE = False
    kuzu = None  # type: ignore

from .kg_schema import KnowledgeGraphSchema, get_schema  # noqa: E402

logger = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now().isoformat()


def _safe(v: Any) -> Any:
    """JSON 序列化无法用 Kùzu 原生类型存储的字段"""
    if isinstance(v, (dict, list, tuple)):
        return json.dumps(v, ensure_ascii=False)
    return v


class KnowledgeGraphBuilder:
    """知识图谱构建器（所有写入方法幂等）"""

    BUILTIN_MODELS = [
        ("stacking", "ensemble"), ("hmm", "sequence"),
        ("copula", "dependency"), ("bsts", "bayesian"),
        ("mamba", "deep_sequence"), ("itransformer", "deep_transformer"),
    ]
    BUILTIN_STRATEGIES = [
        ("default", "weighted_average", {"stacking": 0.4, "hmm": 0.2, "copula": 0.2, "bsts": 0.2}),
        ("stacking_dominant", "weighted_average", {"stacking": 0.7, "hmm": 0.1, "copula": 0.1, "bsts": 0.1}),
        ("hmm_dominant", "weighted_average", {"stacking": 0.1, "hmm": 0.7, "copula": 0.1, "bsts": 0.1}),
        ("copula_dominant", "weighted_average", {"stacking": 0.1, "hmm": 0.1, "copula": 0.7, "bsts": 0.1}),
        ("voting_ensemble", "voting", {"stacking": 0.25, "hmm": 0.25, "copula": 0.25, "bsts": 0.25}),
    ]
    BUILTIN_POSITIONS = ["wan", "qian", "bai", "shi", "ge"]

    _PK_FIELDS = {
        "Model": "name", "Strategy": "name", "Position": "name",
        "Period": "period_id", "Prediction": "pred_id",
        "PredictionDetail": "detail_id", "HitRecord": "hit_id",
        "Feature": "feature_id", "Parameter": "param_id",
        "Suggestion": "sugg_id", "DataDistribution": "dist_id",
    }

    def __init__(self, schema: KnowledgeGraphSchema | None = None):
        self.schema = schema or get_schema() if KUZU_AVAILABLE else None
        self._conn: "kuzu.Connection | None" = None
        self._seeded = False
        if not KUZU_AVAILABLE:
            logger.warning("[KG_Builder] kuzu 模块未安装，知识图谱功能已禁用（所有写入操作将静默跳过）")

    @property
    def conn(self):
        if not KUZU_AVAILABLE:
            raise RuntimeError("kuzu module not available")
        if self._conn is None:
            self._conn = kuzu.Connection(self.schema.db)
        return self._conn

    def seed_builtin_data(self, force: bool = False) -> None:
        """播种内置模型/策略/位置节点（幂等）。kuzu未安装时静默跳过。"""
        if not KUZU_AVAILABLE:
            return
        if self._seeded and not force:
            return
        for name, mtype in self.BUILTIN_MODELS:
            self.upsert_node("Model", {"name": name, "type": mtype, "version": "v1", "created_at": _ts()})
        for name, method, weights in self.BUILTIN_STRATEGIES:
            self.upsert_node("Strategy", {
                "name": name, "ensemble_method": method,
                "weights_json": json.dumps(weights, ensure_ascii=False), "created_at": _ts(),
            })
        for pos in self.BUILTIN_POSITIONS:
            self.upsert_node("Position", {"name": pos})
        self._seeded = True
        logger.info(f"[KG_Builder] 播种完成: {len(self.BUILTIN_MODELS)} 模型 + {len(self.BUILTIN_STRATEGIES)} 策略 + {len(self.BUILTIN_POSITIONS)} 位置")

    # ============================================================
    # 低层 upsert API
    # ============================================================

    def upsert_node(self, table: str, props: Dict[str, Any]) -> bool:
        """幂等写入节点：已存在则跳过，不存在则创建。kuzu未安装时静默跳过。"""
        if not KUZU_AVAILABLE:
            return False
        pk_field = self._PK_FIELDS.get(table, "id")
        pk_value = props.get(pk_field)
        if pk_value is None:
            logger.warning(f"[KG_Builder] upsert_node 缺少主键 {pk_field}: {props}")
            return False

        if self._node_exists(table, pk_field, pk_value):
            return False

        cols = list(props.keys())
        col_clauses = ", ".join(f"{c}: ${c}" for c in cols)
        params = {c: _safe(v) for c, v in props.items()}
        cypher = f"CREATE (n:{table} {{{col_clauses}}})"
        try:
            self.conn.execute(cypher, params)
            return True
        except Exception as e:
            if "already exists" in str(e).lower():
                return False
            logger.error(f"[KG_Builder] upsert_node 失败 table={table}: {e}")
            raise

    def upsert_rel(
        self, rel_table: str, from_table: str, from_pk_field: str, from_pk_value: Any,
        to_table: str, to_pk_field: str, to_pk_value: Any,
        props: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """幂等写入关系：已存在则跳过。kuzu未安装时静默跳过。"""
        if not KUZU_AVAILABLE:
            return False
        if self._rel_exists(rel_table, from_table, from_pk_field, from_pk_value, to_table, to_pk_field, to_pk_value):
            return False

        props = props or {}
        rel_props = ""
        params: Dict[str, Any] = {"fpk": from_pk_value, "tpk": to_pk_value}
        if props:
            prop_clauses = []
            for k, v in props.items():
                prop_clauses.append(f"{k}: ${k}")
                params[k] = _safe(v)
            rel_props = "{" + ", ".join(prop_clauses) + "}"

        cypher = (
            f"MATCH (a:{from_table} {{{from_pk_field}: $fpk}}), "
            f"(b:{to_table} {{{to_pk_field}: $tpk}}) "
            f"CREATE (a)-[:{rel_table} {rel_props}]->(b)"
        )
        try:
            self.conn.execute(cypher, params)
            return True
        except Exception as e:
            if "already exists" in str(e).lower():
                return False
            logger.error(f"[KG_Builder] upsert_rel 失败 rel={rel_table}: {e}")
            raise

    # ============================================================
    # 高层事件 API - 主流程落图入口
    # ============================================================

    def record_prediction(self, prediction: Dict[str, Any]) -> str:
        """记录一次预测到图谱。kuzu未安装时静默返回占位pred_id。

        创建: Prediction + PredictionDetail + Period + 各关系边
        Returns: pred_id
        """
        period_id = str(prediction.get("period", ""))
        pred_id = prediction.get("pred_id") or f"PRED-{period_id}-{uuid.uuid4().hex[:8]}"
        if not KUZU_AVAILABLE:
            return pred_id  # 静默跳过，仍返回可用的id供主流程记录
        ts = prediction.get("timestamp") or _ts()
        strategy_name = prediction.get("strategy_name", "default")
        weights_used = prediction.get("weights_used", {}) or {}
        ensemble_method = prediction.get("ensemble_method", "weighted_average")
        feature_version = prediction.get("feature_version", "")

        # Period 节点
        if not self._node_exists("Period", "period_id", period_id):
            self.upsert_node("Period", {
                "period_id": period_id,
                "date": period_id[:8] if len(period_id) >= 8 else "",
                "actual_wan": -1, "actual_qian": -1, "actual_bai": -1,
                "actual_shi": -1, "actual_ge": -1,
            })

        # Prediction 节点
        self.upsert_node("Prediction", {
            "pred_id": pred_id, "period_id": period_id, "strategy_name": strategy_name,
            "timestamp": ts, "weights_used_json": json.dumps(weights_used, ensure_ascii=False),
            "ensemble_method": ensemble_method, "feature_version": feature_version,
        })

        self.upsert_rel("PREDICTED_FOR", "Prediction", "pred_id", pred_id, "Period", "period_id", period_id)
        self.upsert_rel("USED_STRATEGY", "Prediction", "pred_id", pred_id, "Strategy", "name", strategy_name)

        for model_name, weight in weights_used.items():
            try:
                w = float(weight)
            except (TypeError, ValueError):
                continue
            self.upsert_rel("USED_MODEL", "Prediction", "pred_id", pred_id, "Model", "name", model_name, props={"weight": w})

        position_preds = prediction.get("predictions", {}) or {}
        for pos, pos_data in position_preds.items():
            if pos not in self.BUILTIN_POSITIONS:
                continue
            detail_id = f"DET-{pred_id}-{pos}"
            top_k = pos_data.get("top_k", []) if isinstance(pos_data, dict) else []
            confidence = float(pos_data.get("confidence", 0.0)) if isinstance(pos_data, dict) else 0.0
            entropy = float(pos_data.get("entropy", 0.0)) if isinstance(pos_data, dict) else 0.0

            self.upsert_node("PredictionDetail", {
                "detail_id": detail_id, "pred_id": pred_id, "position": pos,
                "top_k_json": json.dumps(top_k, ensure_ascii=False),
                "confidence": confidence, "entropy": entropy,
            })
            self.upsert_rel("HAS_DETAIL", "Prediction", "pred_id", pred_id, "PredictionDetail", "detail_id", detail_id)
            self.upsert_rel("DETAIL_AT", "PredictionDetail", "detail_id", detail_id, "Position", "name", pos)

        logger.info(f"[KG_Builder] 预测落图: pred_id={pred_id}, period={period_id}, strategy={strategy_name}")
        return pred_id

    def record_actual_hits(
        self, period_id: str, actual_numbers: Dict[str, int],
        hit_records: List[Dict[str, Any]],
        per_model_accuracy: Optional[Dict[str, Dict[str, float]]] = None,
        pred_id: Optional[str] = None,
    ) -> int:
        """记录实际开奖与命中评估到图谱。kuzu未安装时静默返回0。

        创建: HitRecord + HIT_AT + ACTUAL_OF + RESULTED_IN + FEEDBACK_TO
        Returns: HitRecord 数量
        """
        if not KUZU_AVAILABLE:
            return 0
        ts = _ts()
        count = 0

        self._update_period_actuals(period_id, actual_numbers)

        for hr in hit_records:
            pos = hr.get("position", "")
            if pos not in self.BUILTIN_POSITIONS:
                continue
            actual_num = int(hr.get("actual", -1))
            hit_id = f"HIT-{period_id}-{pos}"

            self.upsert_node("HitRecord", {
                "hit_id": hit_id, "period_id": period_id, "position": pos,
                "actual_num": actual_num,
                "top1_hit": bool(hr.get("top1_hit", False)),
                "top3_hit": bool(hr.get("top3_hit", False)),
                "top5_hit": bool(hr.get("top5_hit", False)),
                "top8_hit": bool(hr.get("top8_hit", False)),
                "timestamp": ts,
            })
            self.upsert_rel("HIT_AT", "HitRecord", "hit_id", hit_id, "Position", "name", pos)
            self.upsert_rel("ACTUAL_OF", "HitRecord", "hit_id", hit_id, "Period", "period_id", period_id)
            if pred_id:
                self.upsert_rel("RESULTED_IN", "Prediction", "pred_id", pred_id, "HitRecord", "hit_id", hit_id)
            count += 1

        if per_model_accuracy:
            for hr in hit_records:
                pos = hr.get("position", "")
                if pos not in self.BUILTIN_POSITIONS:
                    continue
                hit_id = f"HIT-{period_id}-{pos}"
                for model_name, acc_data in per_model_accuracy.items():
                    if not isinstance(acc_data, dict):
                        continue
                    props = {
                        "top3_acc": float(acc_data.get("top3_accuracy", 0.0)),
                        "top8_acc": float(acc_data.get("top8_accuracy", 0.0)),
                        "samples": float(acc_data.get("samples_weighted", 0.0)),
                    }
                    self.upsert_rel("FEEDBACK_TO", "HitRecord", "hit_id", hit_id, "Model", "name", model_name, props=props)

        logger.info(f"[KG_Builder] 命中评估落图: period={period_id}, hit_records={count}, pred_id={pred_id}")
        return count

    def record_strategy_switch(self, from_strategy: str, to_strategy: str, period: str, reason: str, score_gap: float = 0.0) -> None:
        """记录策略切换事件。kuzu未安装时静默跳过。"""
        if not KUZU_AVAILABLE:
            return
        self.upsert_rel("SWITCHED_TO", "Strategy", "name", from_strategy, "Strategy", "name", to_strategy,
                        props={"period": str(period), "reason": reason, "score_gap": float(score_gap), "timestamp": _ts()})
        logger.info(f"[KG_Builder] 策略切换落图: {from_strategy} -> {to_strategy} (reason={reason})")

    def record_suggestion(self, suggestion: Dict[str, Any]) -> str:
        """记录自学习优化建议到图谱。kuzu未安装时静默返回占位sugg_id。"""
        sugg_id = suggestion.get("sugg_id") or suggestion.get("id") or f"SUG-{uuid.uuid4().hex[:8]}"
        if not KUZU_AVAILABLE:
            return sugg_id
        self.upsert_node("Suggestion", {
            "sugg_id": sugg_id, "category": str(suggestion.get("category", "")),
            "priority": int(suggestion.get("priority", 1)), "status": str(suggestion.get("status", "pending")),
            "recommended_value": float(suggestion.get("recommended_value", 0.0) or 0.0),
            "confidence": float(suggestion.get("confidence_level", 0.0) or 0.0),
            "timestamp": _ts(), "reasoning": str(suggestion.get("reasoning", ""))[:500],
        })
        model_name = suggestion.get("model_name")
        if model_name and self._node_exists("Model", "name", model_name):
            self.upsert_rel("OPTIMIZED_BY", "Model", "name", model_name, "Suggestion", "sugg_id", sugg_id)
        param_name = suggestion.get("parameter_name")
        if param_name:
            param_id = f"PARAM-{param_name}"
            if not self._node_exists("Parameter", "param_id", param_id):
                self.upsert_node("Parameter", {
                    "param_id": param_id, "name": param_name,
                    "value": float(suggestion.get("recommended_value", 0.0) or 0.0),
                    "config_source": "suggestion", "updated_at": _ts(),
                })
            self.upsert_rel("APPLIED_PARAM", "Suggestion", "sugg_id", sugg_id, "Parameter", "param_id", param_id)
        logger.info(f"[KG_Builder] 建议落图: sugg_id={sugg_id}")
        return sugg_id

    def record_data_distribution(self, period_id: str, psi: float, mean: float, std: float, drift_detected: bool = False) -> str:
        """记录数据分布快照。kuzu未安装时静默返回占位dist_id。"""
        dist_id = f"DIST-{period_id}"
        if not KUZU_AVAILABLE:
            return dist_id
        self.upsert_node("DataDistribution", {
            "dist_id": dist_id, "period_id": period_id,
            "psi": float(psi), "mean": float(mean), "std": float(std),
            "drift_detected": bool(drift_detected), "timestamp": _ts(),
        })
        logger.info(f"[KG_Builder] 分布落图: period={period_id}, psi={psi:.4f}")
        return dist_id

    def record_strategy_performance(self, strategy_name: str, dist_id: str, top8_acc: float, top3_acc: float, samples: int) -> None:
        """记录策略在某种数据分布下的表现（PERFORMED_AT 关系）。kuzu未安装时静默跳过。"""
        if not KUZU_AVAILABLE:
            return
        self.upsert_rel("PERFORMED_AT", "Strategy", "name", strategy_name, "DataDistribution", "dist_id", dist_id,
                        props={"top8_acc": float(top8_acc), "top3_acc": float(top3_acc), "samples": int(samples)})

    # ============================================================
    # 内部辅助方法
    # ============================================================

    def _node_exists(self, table: str, pk_field: str, pk_value: Any) -> bool:
        if not KUZU_AVAILABLE:
            return False
        cypher = f"MATCH (n:{table} {{{pk_field}: $pk}}) RETURN count(n)"
        try:
            r = self.conn.execute(cypher, {"pk": pk_value})
            return r.has_next() and r.get_next()[0] > 0
        except Exception:
            return False

    def _rel_exists(self, rel_table: str, from_table: str, from_pk_field: str, from_pk_value: Any,
                    to_table: str, to_pk_field: str, to_pk_value: Any) -> bool:
        if not KUZU_AVAILABLE:
            return False
        cypher = (
            f"MATCH (a:{from_table} {{{from_pk_field}: $fpk}})"
            f"-[r:{rel_table}]->"
            f"(b:{to_table} {{{to_pk_field}: $tpk}}) RETURN count(r)"
        )
        try:
            r = self.conn.execute(cypher, {"fpk": from_pk_value, "tpk": to_pk_value})
            return r.has_next() and r.get_next()[0] > 0
        except Exception:
            return False

    def _update_period_actuals(self, period_id: str, actual_numbers: Dict[str, int]) -> None:
        if not KUZU_AVAILABLE or not actual_numbers:
            return
        set_clauses = []
        params: Dict[str, Any] = {"pid": period_id}
        field_map = {"wan": "actual_wan", "qian": "actual_qian", "bai": "actual_bai", "shi": "actual_shi", "ge": "actual_ge"}
        for pos_key, field in field_map.items():
            if pos_key in actual_numbers:
                set_clauses.append(f"p.{field} = ${field}")
                params[field] = int(actual_numbers[pos_key])
        if not set_clauses:
            return
        cypher = f"MATCH (p:Period {{period_id: $pid}}) SET {', '.join(set_clauses)}"
        try:
            self.conn.execute(cypher, params)
        except Exception as e:
            logger.debug(f"[KG_Builder] _update_period_actuals 异常: {e}")


_builder_singleton: KnowledgeGraphBuilder | None = None


def get_builder() -> KnowledgeGraphBuilder:
    """获取 Builder 单例（自动播种内置数据）"""
    global _builder_singleton
    if _builder_singleton is None:
        _builder_singleton = KnowledgeGraphBuilder()
        _builder_singleton.seed_builtin_data()
    return _builder_singleton
