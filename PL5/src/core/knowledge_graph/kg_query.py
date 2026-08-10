"""知识图谱 Query V1.0 - Cypher 查询 API

四大场景查询接口:
1. 闭环知识积累: get_model_accuracy_history / get_prediction_feedback_chain / get_period_hit_summary
2. 关系发现归因: find_high_hit_patterns / find_model_position_correlation / find_drift_strategy_correlation
3. 策略推理推荐: recommend_strategy_for_distribution / get_strategy_ranking
4. 可解释性审计: explain_prediction / get_decision_chain
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

try:
    import kuzu
    KUZU_AVAILABLE = True
except ImportError:
    KUZU_AVAILABLE = False
    kuzu = None  # type: ignore

from .kg_schema import KnowledgeGraphSchema, get_schema  # noqa: E402

logger = logging.getLogger(__name__)


class KnowledgeGraphQuery:
    """知识图谱查询器。kuzu未安装时所有方法返回空结果。"""

    def __init__(self, schema: KnowledgeGraphSchema | None = None):
        self.schema = schema or get_schema() if KUZU_AVAILABLE else None
        self._conn: Optional["kuzu.Connection"] = None
        if not KUZU_AVAILABLE:
            logger.warning("[KG_Query] kuzu 模块未安装，所有知识图谱查询将返回空结果")

    @property
    def conn(self):
        if not KUZU_AVAILABLE:
            raise RuntimeError("kuzu module not available")
        if self._conn is None:
            self._conn = kuzu.Connection(self.schema.db)
        return self._conn

    def _execute(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[List[Any]]:
        if not KUZU_AVAILABLE:
            return []
        try:
            r = self.conn.execute(cypher, params or {})
            rows = []
            while r.has_next():
                rows.append(list(r.get_next()))
            return rows
        except Exception as e:
            logger.error(f"[KG_Query] 查询失败: {e}\nCypher: {cypher}")
            raise

    # ============================================================
    # 场景1: 闭环知识积累
    # ============================================================

    def get_model_accuracy_history(self, model_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """查询模型的实际命中率历史（来自 FEEDBACK_TO 边）"""
        where = "WHERE m.name = $model" if model_name else ""
        cypher = f"""
            MATCH (h:HitRecord)-[f:FEEDBACK_TO]->(m:Model)
            {where}
            RETURN m.name AS model, h.period_id AS period, h.position AS position,
                   f.top3_acc AS top3_acc, f.top8_acc AS top8_acc,
                   f.samples AS samples, h.hit_id AS hit_id,
                   h.top8_hit AS top8_hit, h.top3_hit AS top3_hit
            ORDER BY period DESC, position
            LIMIT $limit
        """
        params = {"limit": limit}
        if model_name:
            params["model"] = model_name
        rows = self._execute(cypher, params)
        return [dict(zip(["model", "period", "position", "top3_acc", "top8_acc", "samples", "hit_id", "top8_hit", "top3_hit"], r)) for r in rows]

    def get_prediction_feedback_chain(self, pred_id: str) -> Dict[str, Any]:
        """查询预测→开奖→反馈的完整链路"""
        pred_rows = self._execute(
            "MATCH (p:Prediction {pred_id: $pid}) "
            "RETURN p.pred_id, p.period_id, p.strategy_name, p.timestamp, "
            "p.weights_used_json, p.ensemble_method, p.feature_version",
            {"pid": pred_id}
        )
        if not pred_rows:
            return {"error": f"Prediction not found: {pred_id}"}
        p = pred_rows[0]
        prediction = {
            "pred_id": p[0], "period_id": p[1], "strategy_name": p[2],
            "timestamp": p[3], "weights_used": json.loads(p[4]) if p[4] else {},
            "ensemble_method": p[5], "feature_version": p[6],
        }

        strat_rows = self._execute(
            "MATCH (p:Prediction {pred_id: $pid})-[:USED_STRATEGY]->(s:Strategy) "
            "RETURN s.name, s.ensemble_method, s.weights_json",
            {"pid": pred_id}
        )
        strategy = {
            "name": strat_rows[0][0], "ensemble_method": strat_rows[0][1],
            "weights": json.loads(strat_rows[0][2]) if strat_rows[0][2] else {},
        } if strat_rows else None

        model_rows = self._execute(
            "MATCH (p:Prediction {pred_id: $pid})-[r:USED_MODEL]->(m:Model) "
            "RETURN m.name, r.weight ORDER BY r.weight DESC",
            {"pid": pred_id}
        )
        models_used = [{"name": r[0], "weight": r[1]} for r in model_rows]

        detail_rows = self._execute(
            "MATCH (p:Prediction {pred_id: $pid})-[:HAS_DETAIL]->(d:PredictionDetail)"
            "-[:DETAIL_AT]->(pos:Position) "
            "RETURN pos.name, d.top_k_json, d.confidence, d.entropy ORDER BY pos.name",
            {"pid": pred_id}
        )
        details = [{
            "position": r[0], "top_k": json.loads(r[1]) if r[1] else [],
            "confidence": r[2], "entropy": r[3],
        } for r in detail_rows]

        hit_rows = self._execute(
            "MATCH (p:Prediction {pred_id: $pid})-[:RESULTED_IN]->(h:HitRecord) "
            "RETURN h.hit_id, h.position, h.actual_num, "
            "h.top1_hit, h.top3_hit, h.top5_hit, h.top8_hit ORDER BY h.position",
            {"pid": pred_id}
        )
        hit_records = []
        for hr in hit_rows:
            hit_id = hr[0]
            fb_rows = self._execute(
                "MATCH (h:HitRecord {hit_id: $hid})-[f:FEEDBACK_TO]->(m:Model) "
                "RETURN m.name, f.top3_acc, f.top8_acc, f.samples",
                {"hid": hit_id}
            )
            hit_records.append({
                "hit_id": hit_id, "position": hr[1], "actual": hr[2],
                "top1_hit": hr[3], "top3_hit": hr[4], "top5_hit": hr[5], "top8_hit": hr[6],
                "feedback_to": [{"model": f[0], "top3_acc": f[1], "top8_acc": f[2], "samples": f[3]} for f in fb_rows],
            })

        period_rows = self._execute(
            "MATCH (p:Prediction {pred_id: $pid})-[:PREDICTED_FOR]->(per:Period) "
            "RETURN per.period_id, per.date, per.actual_wan, per.actual_qian, "
            "per.actual_bai, per.actual_shi, per.actual_ge",
            {"pid": pred_id}
        )
        period = None
        if period_rows:
            pr = period_rows[0]
            period = {
                "period_id": pr[0], "date": pr[1],
                "actual": {"wan": pr[2], "qian": pr[3], "bai": pr[4], "shi": pr[5], "ge": pr[6]},
            }

        return {
            "prediction": prediction, "strategy": strategy, "models_used": models_used,
            "details": details, "hit_records": hit_records, "period": period,
        }

    def get_period_hit_summary(self, period_id: str) -> Dict[str, Any]:
        """查询单期命中汇总"""
        rows = self._execute(
            "MATCH (h:HitRecord {period_id: $pid}) "
            "RETURN h.position, h.actual_num, h.top1_hit, h.top3_hit, h.top5_hit, h.top8_hit "
            "ORDER BY h.position",
            {"pid": period_id}
        )
        hits = [{
            "position": r[0], "actual": r[1],
            "top1_hit": r[2], "top3_hit": r[3], "top5_hit": r[4], "top8_hit": r[5],
        } for r in rows]
        total = len(hits)
        return {
            "period_id": period_id, "total_positions": total,
            "top1_hits": sum(1 for h in hits if h["top1_hit"]),
            "top3_hits": sum(1 for h in hits if h["top3_hit"]),
            "top5_hits": sum(1 for h in hits if h["top5_hit"]),
            "top8_hits": sum(1 for h in hits if h["top8_hit"]),
            "top1_accuracy": sum(1 for h in hits if h["top1_hit"]) / total if total else 0,
            "top3_accuracy": sum(1 for h in hits if h["top3_hit"]) / total if total else 0,
            "top5_accuracy": sum(1 for h in hits if h["top5_hit"]) / total if total else 0,
            "top8_accuracy": sum(1 for h in hits if h["top8_hit"]) / total if total else 0,
            "hits": hits,
        }

    # ============================================================
    # 场景2: 关系发现与归因
    # ============================================================

    def find_high_hit_patterns(self, min_top8_acc: float = 0.8, limit: int = 20) -> List[Dict[str, Any]]:
        """发现高命中率预测的共同特征"""
        cypher = """
            MATCH (p:Prediction)-[:RESULTED_IN]->(h:HitRecord)
            WITH p, count(h) AS total_positions,
                 sum(CASE WHEN h.top8_hit = true THEN 1 ELSE 0 END) * 1.0 / count(h) AS top8_acc
            WHERE total_positions > 0 AND top8_acc >= $min_acc
            MATCH (p)-[:USED_STRATEGY]->(s:Strategy)
            OPTIONAL MATCH (p)-[um:USED_MODEL]->(m:Model)
            WITH p, s, top8_acc, collect({model: m.name, weight: um.weight}) AS models
            RETURN p.pred_id AS pred_id, p.period_id AS period_id,
                   s.name AS strategy, top8_acc, models, p.feature_version AS feature_version
            ORDER BY top8_acc DESC, period_id DESC
            LIMIT $limit
        """
        rows = self._execute(cypher, {"min_acc": min_top8_acc, "limit": limit})
        return [{
            "pred_id": r[0], "period_id": r[1], "strategy": r[2],
            "top8_acc": r[3],
            "models": [{"model": m["model"], "weight": m["weight"]} for m in r[4]],
            "feature_version": r[5],
        } for r in rows]

    def find_model_position_correlation(self) -> List[Dict[str, Any]]:
        """分析模型×位置的命中率矩阵（来自 FEEDBACK_TO 边聚合）"""
        cypher = """
            MATCH (h:HitRecord)-[f:FEEDBACK_TO]->(m:Model)
            RETURN m.name AS model, h.position AS position,
                   avg(f.top3_acc) AS avg_top3_acc,
                   avg(f.top8_acc) AS avg_top8_acc,
                   sum(f.samples) AS total_samples,
                   count(f) AS feedback_count
            ORDER BY model, position
        """
        rows = self._execute(cypher)
        return [{
            "model": r[0], "position": r[1],
            "avg_top3_acc": r[2], "avg_top8_acc": r[3],
            "total_samples": r[4], "feedback_count": r[5],
        } for r in rows]

    def find_drift_strategy_correlation(self) -> List[Dict[str, Any]]:
        """分析数据漂移与策略切换的关联"""
        cypher = """
            MATCH (s1:Strategy)-[sw:SWITCHED_TO]->(s2:Strategy)
            OPTIONAL MATCH (d:DataDistribution {period_id: sw.period})
            RETURN sw.period AS period, s1.name AS from_strategy,
                   s2.name AS to_strategy, sw.reason AS reason,
                   sw.score_gap AS score_gap,
                   CASE WHEN d IS NULL THEN NULL ELSE d.psi END AS psi,
                   CASE WHEN d IS NULL THEN NULL ELSE d.drift_detected END AS drift_detected,
                   sw.timestamp AS timestamp
            ORDER BY timestamp DESC
        """
        rows = self._execute(cypher)
        return [{
            "period": r[0], "from_strategy": r[1], "to_strategy": r[2],
            "reason": r[3], "score_gap": r[4], "psi": r[5],
            "drift_detected": r[6], "timestamp": r[7],
        } for r in rows]

    # ============================================================
    # 场景3: 策略推理与推荐
    # ============================================================

    def recommend_strategy_for_distribution(self, psi: float, mean: float, std: float, top_n: int = 3) -> List[Dict[str, Any]]:
        """基于当前数据分布推荐历史最优策略"""
        cypher = """
            MATCH (s:Strategy)-[pa:PERFORMED_AT]->(d:DataDistribution)
            WHERE d.psi IS NOT NULL AND d.mean IS NOT NULL AND d.std IS NOT NULL
            RETURN s.name AS strategy, d.dist_id AS dist_id, d.period_id AS period,
                   d.psi AS psi, d.mean AS mean, d.std AS std,
                   pa.top8_acc AS top8_acc, pa.top3_acc AS top3_acc, pa.samples AS samples
        """
        rows = self._execute(cypher)
        if not rows:
            return []

        records = []
        for r in rows:
            d_psi = abs(r[3] - psi) if r[3] is not None else 999
            d_mean = abs(r[4] - mean) if r[4] is not None else 999
            d_std = abs(r[5] - std) if r[5] is not None else 999
            similarity = 1.0 / (1.0 + 2.0 * d_psi + 0.1 * d_mean + 0.5 * d_std)
            records.append({
                "strategy": r[0], "dist_id": r[1], "period": r[2],
                "top8_acc": r[6] if r[6] is not None else 0,
                "top3_acc": r[7] if r[7] is not None else 0,
                "samples": r[8] if r[8] is not None else 0,
                "similarity": similarity,
            })

        seen = {}
        for rec in records:
            s = rec["strategy"]
            score = rec["similarity"] * rec["top8_acc"]
            if s not in seen or score > seen[s]["_score"]:
                rec["_score"] = score
                seen[s] = rec
        ranked = sorted(seen.values(), key=lambda x: x["_score"], reverse=True)
        for r in ranked:
            del r["_score"]
        return ranked[:top_n]

    def get_strategy_ranking(self, limit_periods: int = 50) -> List[Dict[str, Any]]:
        """策略综合排名（基于实际命中率）

        Kùzu 不支持嵌套聚合（avg of avg），因此分两步：
        1. Cypher 查询每个 (strategy, prediction) 的 top8 命中数和总位置数
        2. Python 层聚合计算策略级平均命中率
        """
        cypher = """
            MATCH (p:Prediction)-[:USED_STRATEGY]->(s:Strategy),
                  (p)-[:RESULTED_IN]->(h:HitRecord)
            WITH s, p,
                 count(h) AS positions,
                 sum(CASE WHEN h.top8_hit = true THEN 1 ELSE 0 END) AS top8_hits
            WHERE positions > 0
            RETURN s.name AS strategy, p.pred_id AS pred_id, positions, top8_hits
        """
        rows = self._execute(cypher)

        strategy_preds = defaultdict(list)
        for r in rows:
            strategy = r[0]
            top8_hits = float(r[3]) if r[3] is not None else 0
            positions = float(r[2]) if r[2] is not None else 1
            strategy_preds[strategy].append(top8_hits / positions)

        switch_rows = self._execute(
            "MATCH (s1:Strategy)-[sw:SWITCHED_TO]->() "
            "RETURN s1.name AS strategy, count(sw) AS cnt"
        )
        switch_counts = {r[0]: r[1] for r in switch_rows}

        result = []
        for strategy, accs in strategy_preds.items():
            result.append({
                "strategy": strategy,
                "total_predictions": len(accs),
                "avg_top8_acc": sum(accs) / len(accs) if accs else 0,
                "switch_count": switch_counts.get(strategy, 0),
            })
        result.sort(key=lambda x: x["avg_top8_acc"], reverse=True)
        return result

    # ============================================================
    # 场景4: 可解释性审计
    # ============================================================

    def explain_prediction(self, pred_id: str) -> Dict[str, Any]:
        """预测决策路径完整追溯"""
        chain = self.get_prediction_feedback_chain(pred_id)
        if "error" in chain:
            return chain

        pred = chain["prediction"]
        strategy = chain.get("strategy") or {}
        models = chain.get("models_used", [])
        hits = chain.get("hit_records", [])

        decision_path = []
        decision_path.append({
            "step": 1, "action": "选定策略",
            "detail": f"strategy={strategy.get('name', '?')}, method={strategy.get('ensemble_method', '?')}"
        })
        decision_path.append({
            "step": 2, "action": "融合模型权重",
            "detail": ", ".join(f"{m['name']}={m['weight']:.3f}" for m in models)
        })
        decision_path.append({
            "step": 3, "action": "生成预测",
            "detail": f"{len(chain.get('details', []))} 个位置, feature_version={pred.get('feature_version', '?')}"
        })
        if hits:
            top8_count = sum(1 for h in hits if h["top8_hit"])
            decision_path.append({
                "step": 4, "action": "开奖验证",
                "detail": f"Top-8 命中 {top8_count}/{len(hits)} 位置"
            })
            for h in hits:
                if h["feedback_to"]:
                    best_model = max(h["feedback_to"], key=lambda x: x["top8_acc"])
                    decision_path.append({
                        "step": 5, "action": f"反馈更新({h['position']}位)",
                        "detail": f"最佳模型 {best_model['model']} top8_acc={best_model['top8_acc']:.3f}"
                    })

        return {
            "pred_id": pred_id, "prediction": pred, "strategy": strategy,
            "models_used": models, "details": chain.get("details", []),
            "hit_records": hits, "period": chain.get("period"),
            "decision_path": decision_path, "audit_timestamp": pred.get("timestamp"),
        }

    def get_decision_chain(self, period_id: str) -> List[Dict[str, Any]]:
        """期号到决策的全链路：返回该期所有预测及其决策路径"""
        rows = self._execute(
            "MATCH (p:Prediction {period_id: $pid}) "
            "RETURN p.pred_id AS pred_id, p.timestamp AS ts ORDER BY ts",
            {"pid": period_id}
        )
        return [self.explain_prediction(r[0]) for r in rows]

    # ============================================================
    # 综合统计
    # ============================================================

    def get_kg_summary(self) -> Dict[str, Any]:
        """获取知识图谱整体摘要（用于日循环报告）"""
        stats = self.schema.get_stats()

        recent_period_row = self._execute(
            "MATCH (h:HitRecord) RETURN h.period_id AS pid ORDER BY pid DESC LIMIT 1"
        )
        latest_period = recent_period_row[0][0] if recent_period_row else None
        latest_summary = self.get_period_hit_summary(latest_period) if latest_period else {}

        model_acc_rows = self._execute("""
            MATCH (h:HitRecord)-[f:FEEDBACK_TO]->(m:Model)
            RETURN m.name AS model, avg(f.top3_acc) AS avg_top3,
                   avg(f.top8_acc) AS avg_top8, sum(f.samples) AS samples,
                   count(f) AS cnt
            ORDER BY avg_top8 DESC
        """)
        model_ranking = [{
            "model": r[0],
            "avg_top3_acc": r[1] if r[1] is not None else 0,
            "avg_top8_acc": r[2] if r[2] is not None else 0,
            "total_samples": r[3] if r[3] is not None else 0,
            "feedback_count": r[4],
        } for r in model_acc_rows]

        return {
            "stats": stats,
            "latest_period": latest_period,
            "latest_hit_summary": latest_summary,
            "model_ranking": model_ranking,
        }


_query_singleton: KnowledgeGraphQuery | None = None


def get_query() -> KnowledgeGraphQuery:
    """获取 Query 单例"""
    global _query_singleton
    if _query_singleton is None:
        _query_singleton = KnowledgeGraphQuery()
    return _query_singleton
