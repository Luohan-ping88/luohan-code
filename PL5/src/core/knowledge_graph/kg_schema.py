"""知识图谱 Schema V1.0 - Kùzu 图数据库表结构定义

11种节点表 + 15种关系表，覆盖闭环积累/归因/推理/审计四大场景。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

try:
    import kuzu
    KUZU_AVAILABLE = True
except ImportError:
    KUZU_AVAILABLE = False
    kuzu = None  # type: ignore

logger = logging.getLogger(__name__)

KG_DB_PATH = Path(__file__).parent.parent.parent.parent / "models" / "knowledge_graph_kuzu"

# ============================================================
# Schema DDL - 节点表
# ============================================================

NODE_TABLE_DDL = [
    """CREATE NODE TABLE IF NOT EXISTS Model(
        name STRING, type STRING, version STRING, created_at STRING,
        PRIMARY KEY(name))""",
    """CREATE NODE TABLE IF NOT EXISTS Strategy(
        name STRING, ensemble_method STRING, weights_json STRING, created_at STRING,
        PRIMARY KEY(name))""",
    """CREATE NODE TABLE IF NOT EXISTS Position(name STRING, PRIMARY KEY(name))""",
    """CREATE NODE TABLE IF NOT EXISTS Period(
        period_id STRING, date STRING,
        actual_wan INT64, actual_qian INT64, actual_bai INT64,
        actual_shi INT64, actual_ge INT64,
        PRIMARY KEY(period_id))""",
    """CREATE NODE TABLE IF NOT EXISTS Prediction(
        pred_id STRING, period_id STRING, strategy_name STRING, timestamp STRING,
        weights_used_json STRING, ensemble_method STRING, feature_version STRING,
        PRIMARY KEY(pred_id))""",
    """CREATE NODE TABLE IF NOT EXISTS PredictionDetail(
        detail_id STRING, pred_id STRING, position STRING,
        top_k_json STRING, confidence DOUBLE, entropy DOUBLE,
        PRIMARY KEY(detail_id))""",
    """CREATE NODE TABLE IF NOT EXISTS HitRecord(
        hit_id STRING, period_id STRING, position STRING, actual_num INT64,
        top1_hit BOOLEAN, top3_hit BOOLEAN, top5_hit BOOLEAN, top8_hit BOOLEAN,
        timestamp STRING,
        PRIMARY KEY(hit_id))""",
    """CREATE NODE TABLE IF NOT EXISTS Feature(
        feature_id STRING, name STRING, version STRING, importance DOUBLE,
        PRIMARY KEY(feature_id))""",
    """CREATE NODE TABLE IF NOT EXISTS Parameter(
        param_id STRING, name STRING, value DOUBLE, config_source STRING, updated_at STRING,
        PRIMARY KEY(param_id))""",
    """CREATE NODE TABLE IF NOT EXISTS Suggestion(
        sugg_id STRING, category STRING, priority INT64, status STRING,
        recommended_value DOUBLE, confidence DOUBLE, timestamp STRING, reasoning STRING,
        PRIMARY KEY(sugg_id))""",
    """CREATE NODE TABLE IF NOT EXISTS DataDistribution(
        dist_id STRING, period_id STRING, psi DOUBLE, mean DOUBLE, std DOUBLE,
        drift_detected BOOLEAN, timestamp STRING,
        PRIMARY KEY(dist_id))""",
]

# ============================================================
# Schema DDL - 关系表
# ============================================================

REL_TABLE_DDL = [
    "CREATE REL TABLE IF NOT EXISTS USED_STRATEGY(FROM Prediction TO Strategy)",
    "CREATE REL TABLE IF NOT EXISTS USED_MODEL(FROM Prediction TO Model, weight DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS PREDICTED_FOR(FROM Prediction TO Period)",
    "CREATE REL TABLE IF NOT EXISTS HAS_DETAIL(FROM Prediction TO PredictionDetail)",
    "CREATE REL TABLE IF NOT EXISTS DETAIL_AT(FROM PredictionDetail TO Position)",
    "CREATE REL TABLE IF NOT EXISTS RESULTED_IN(FROM Prediction TO HitRecord)",
    "CREATE REL TABLE IF NOT EXISTS HIT_AT(FROM HitRecord TO Position)",
    "CREATE REL TABLE IF NOT EXISTS ACTUAL_OF(FROM HitRecord TO Period)",
    "CREATE REL TABLE IF NOT EXISTS FEEDBACK_TO(FROM HitRecord TO Model, top3_acc DOUBLE, top8_acc DOUBLE, samples DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS OPTIMIZED_BY(FROM Model TO Suggestion)",
    "CREATE REL TABLE IF NOT EXISTS USES_FEATURE(FROM Model TO Feature, importance DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS HAS_PARAM(FROM Model TO Parameter)",
    "CREATE REL TABLE IF NOT EXISTS APPLIED_PARAM(FROM Suggestion TO Parameter)",
    "CREATE REL TABLE IF NOT EXISTS SIMILAR_TO(FROM DataDistribution TO DataDistribution, similarity DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS PERFORMED_AT(FROM Strategy TO DataDistribution, top8_acc DOUBLE, top3_acc DOUBLE, samples INT64)",
    "CREATE REL TABLE IF NOT EXISTS SWITCHED_TO(FROM Strategy TO Strategy, period STRING, reason STRING, score_gap DOUBLE, timestamp STRING)",
]


class KnowledgeGraphSchema:
    """图数据库 schema 管理器

    负责初始化 Kùzu 数据库、创建所有节点表和关系表。
    幂等执行：已存在的表会被跳过（IF NOT EXISTS）。
    """

    # 各节点表的主键字段映射
    PK_FIELDS = {
        "Model": "name", "Strategy": "name", "Position": "name",
        "Period": "period_id", "Prediction": "pred_id",
        "PredictionDetail": "detail_id", "HitRecord": "hit_id",
        "Feature": "feature_id", "Parameter": "param_id",
        "Suggestion": "sugg_id", "DataDistribution": "dist_id",
    }

    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path else KG_DB_PATH
        if KUZU_AVAILABLE:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: Optional["kuzu.Database"] = None
        if not KUZU_AVAILABLE:
            logger.warning("[KG_Schema] kuzu 模块未安装，知识图谱功能已禁用（Schema初始化将跳过）")

    @property
    def db(self):
        if not KUZU_AVAILABLE:
            raise RuntimeError("kuzu module not available")
        if self._db is None:
            self._db = kuzu.Database(str(self.db_path))
        return self._db

    def init_schema(self, force: bool = False) -> None:
        """初始化所有节点表和关系表。kuzu未安装时静默跳过。

        Args:
            force: True 时先 DROP 已有表再重建（谨慎使用，会丢数据）
        """
        if not KUZU_AVAILABLE:
            return
        conn = kuzu.Connection(self.db)

        if force:
            logger.warning("[KG_Schema] force=True，将清空并重建所有表")
            for ddl in reversed(REL_TABLE_DDL):
                table_name = self._extract_table_name(ddl)
                if table_name:
                    try:
                        conn.execute(f"DROP REL TABLE IF EXISTS {table_name}")
                    except Exception:
                        pass
            for ddl in reversed(NODE_TABLE_DDL):
                table_name = self._extract_table_name(ddl)
                if table_name:
                    try:
                        conn.execute(f"DROP NODE TABLE IF EXISTS {table_name}")
                    except Exception:
                        pass

        node_count = 0
        for ddl in NODE_TABLE_DDL:
            try:
                conn.execute(ddl)
                node_count += 1
            except Exception as e:
                if "already exists" in str(e).lower():
                    continue
                logger.error(f"[KG_Schema] 创建节点表失败: {e}")
                raise

        rel_count = 0
        for ddl in REL_TABLE_DDL:
            try:
                conn.execute(ddl)
                rel_count += 1
            except Exception as e:
                if "already exists" in str(e).lower():
                    continue
                logger.error(f"[KG_Schema] 创建关系表失败: {e}")
                raise

        logger.info(f"[KG_Schema] 初始化完成: {node_count} 节点表 + {rel_count} 关系表 @ {self.db_path}")

    @staticmethod
    def _extract_table_name(ddl: str) -> str | None:
        import re
        m = re.search(r"TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", ddl, re.IGNORECASE)
        return m.group(1) if m else None

    def get_stats(self) -> dict:
        """获取图谱统计信息（各表节点/边数量）。kuzu未安装时返回空统计。"""
        if not KUZU_AVAILABLE:
            return {"node_tables": {}, "rel_tables": {}, "kuzu_available": False}
        conn = kuzu.Connection(self.db)
        stats = {"node_tables": {}, "rel_tables": {}}

        for ddl in NODE_TABLE_DDL:
            name = self._extract_table_name(ddl)
            if not name:
                continue
            try:
                r = conn.execute(f"MATCH (n:{name}) RETURN count(n)")
                if r.has_next():
                    stats["node_tables"][name] = r.get_next()[0]
            except Exception:
                stats["node_tables"][name] = -1

        for ddl in REL_TABLE_DDL:
            name = self._extract_table_name(ddl)
            if not name:
                continue
            try:
                r = conn.execute(f"MATCH ()-[r:{name}]->() RETURN count(r)")
                if r.has_next():
                    stats["rel_tables"][name] = r.get_next()[0]
            except Exception:
                stats["rel_tables"][name] = -1

        return stats


# 模块级单例（懒加载）
_schema_singleton: KnowledgeGraphSchema | None = None


def get_schema() -> KnowledgeGraphSchema:
    """获取 schema 管理器单例"""
    global _schema_singleton
    if _schema_singleton is None:
        _schema_singleton = KnowledgeGraphSchema()
        _schema_singleton.init_schema()
    return _schema_singleton
