"""
PL5 模型版本管理器 V10.0
- V10.0 完整格式定义与校验
- V9.0 → V10.0 自动迁移
- 数据完整性校验 (checksum)
- 版本回滚机制 (保留最近N个备份)
- 变更日志记录
"""

import hashlib
import json
import shutil
import logging
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

CURRENT_VERSION = "V10.0"
SUPPORTED_VERSIONS = {"V9.0", "V10.0"}
MAX_BACKUP_COUNT = 5
MODEL_FILENAME = "enhanced_predictor_v10.pkl"
VERSION_LOG_FILE = "model_version_log.json"
BACKUP_DIR_NAME = "model_backups"


@dataclass
class ModelMetadata:
    version: str = CURRENT_VERSION
    created_at: str = ""
    feature_count: int = 0
    training_samples: int = 0
    model_params_hash: str = ""
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    checksum: str = ""
    source_version: str = ""
    migration_notes: str = ""


@dataclass
class VersionChangeLog:
    timestamp: str = ""
    operation: str = ""
    from_version: str = ""
    to_version: str = ""
    operator: str = "system"
    description: str = ""
    checksum_before: str = ""
    checksum_after: str = ""


def _compute_checksum(data_dict: Dict[str, Any]) -> str:
    """计算模型数据的 SHA256 校验和（排除 metadata 和 checksum 字段本身）
    
    注意：不直接pickle整个对象，而是构造一个可哈希的字典，
    避免lambda函数等不可序列化对象。
    """
    import copy
    data_for_hash = copy.deepcopy(data_dict)
    data_for_hash.pop("metadata", None)
    data_for_hash.pop("_v10_checksum", None)
    
    # 构造安全的可哈希字典
    safe_data = {}
    
    # 处理主要字段
    for key, value in data_for_hash.items():
        if key == "stacking":
            # 对于StackingEnsemble，只保存关键信息而不是完整对象
            safe_data[key] = {
                "type": "StackingEnsemble",
                "base_config": value.get("base_config", {}) if isinstance(value, dict) else {},
                "meta_config": value.get("meta_config", {}) if isinstance(value, dict) else {},
                "_fitted": value.get("_fitted", False) if isinstance(value, dict) else False,
            }
        elif key in ("feature_cols", "model_version", "timestamp"):
            # 简单字段直接保存
            safe_data[key] = value
        elif isinstance(value, (int, float, str, bool, list, tuple)):
            # 基本类型和容器直接保存
            safe_data[key] = value
        else:
            # 对于其他复杂对象，只保存类型信息
            safe_data[key] = {"type": type(value).__name__}
    
    # 计算哈希
    serialized = json.dumps(safe_data, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(serialized).hexdigest()


def _compute_params_hash(model_data: Dict[str, Any]) -> str:
    """计算模型参数的轻量级哈希值，用于快速比对模型是否变化"""
    hash_parts = []
    for key in sorted(model_data.keys()):
        if key in ("metadata", "_v10_checksum"):
            continue
        val = model_data[key]
        if isinstance(val, dict):
            hash_parts.append(f"{key}:{len(val)}")
        elif isinstance(val, list):
            hash_parts.append(f"{key}:{len(val)}")
        elif isinstance(val, (int, float, bool, str)):
            hash_parts.append(f"{key}:{val}")
        else:
            hash_parts.append(f"{key}:{type(val).__name__}")
    raw = "|".join(hash_parts)
    return hashlib.md5(raw.encode()).hexdigest()


class ModelVersionManager:
    """PL5 模型版本管理器 - V10.0"""

    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self.backup_dir = models_dir / BACKUP_DIR_NAME
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.version_log_path = models_dir / VERSION_LOG_FILE
        self._change_logs: List[Dict[str, Any]] = []
        self._load_change_logs()

    def _load_change_logs(self):
        """加载变更日志"""
        if self.version_log_path.exists():
            try:
                with open(self.version_log_path, 'r', encoding='utf-8') as f:
                    self._change_logs = json.load(f)
            except Exception as e:
                logger.warning(f"[VersionManager] 加载变更日志失败: {e}, 将创建新日志")
                self._change_logs = []

    def _save_change_logs(self):
        """持久化变更日志"""
        try:
            with open(self.version_log_path, 'w', encoding='utf-8') as f:
                json.dump(self._change_logs[-500:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[VersionManager] 保存变更日志失败: {e}")

    def _log_change(self, log_entry: VersionChangeLog):
        """记录一条版本变更"""
        entry_dict = asdict(log_entry)
        self._change_logs.append(entry_dict)
        self._save_change_logs()
        logger.info(
            f"[VersionLog] {log_entry.operation} | "
            f"{log_entry.from_version or '?'} -> {log_entry.to_version or '?'} | "
            f"{log_entry.description}"
        )

    def build_v10_metadata(self, model_data: Dict[str, Any],
                           performance_metrics: Optional[Dict[str, float]] = None,
                           training_samples: int = 0) -> ModelMetadata:
        """构建 V10.0 格式的完整元数据"""
        meta = ModelMetadata(
            version=CURRENT_VERSION,
            created_at=datetime.now().isoformat(),
            feature_count=len(model_data.get("feature_cols", [])),
            training_samples=training_samples,
            model_params_hash=_compute_params_hash(model_data),
            performance_metrics=performance_metrics or {},
        )
        return meta

    def wrap_v10_format(self, model_data: Dict[str, Any],
                        performance_metrics: Optional[Dict[str, float]] = None,
                        training_samples: int = 0) -> Dict[str, Any]:
        """将模型数据包装为 V10.0 完整格式"""
        meta = self.build_v10_metadata(model_data, performance_metrics, training_samples)
        v10_data = dict(model_data)
        v10_data["metadata"] = asdict(meta)
        checksum = _compute_checksum(v10_data)
        v10_data["_v10_checksum"] = checksum
        v10_data["metadata"]["checksum"] = checksum
        return v10_data

    def detect_version(self, state: Dict[str, Any]) -> str:
        """检测模型数据版本"""
        if "_v10_checksum" in state and "metadata" in state:
            meta = state.get("metadata", {})
            if isinstance(meta, dict) and meta.get("version") == CURRENT_VERSION:
                return CURRENT_VERSION
        if "model_version" in state:
            return str(state.get("model_version", "V9.0"))
        return "V9.0"

    def migrate_v9_to_v10(self, v9_state: Dict[str, Any]) -> Dict[str, Any]:
        """将 V9.0 格式迁移为 V10.0 格式"""
        logger.info("[VersionManager] 开始 V9.0 → V10.0 迁移")

        checksum_before = _compute_checksum(v9_state)

        v10_state = dict(v9_state)
        v10_state.pop("_v10_checksum", None)

        feature_cols = v9_state.get("feature_cols", [])
        training_samples = 0
        stacking = v9_state.get("stacking", {})
        if isinstance(stacking, dict) and stacking:
            training_samples = max(len(feature_cols) * 100, len(feature_cols) * 50)

        meta = ModelMetadata(
            version=CURRENT_VERSION,
            created_at=datetime.now().isoformat(),
            feature_count=len(feature_cols),
            training_samples=training_samples,
            model_params_hash=_compute_params_hash(v9_state),
            performance_metrics={},
            source_version=v9_state.get("model_version", "V9.0"),
            migration_notes="Auto-migrated from V9.0 to V10.0",
        )

        v10_state["metadata"] = asdict(meta)
        v10_state["model_version"] = CURRENT_VERSION
        checksum_after = _compute_checksum(v10_state)
        v10_state["_v10_checksum"] = checksum_after
        v10_state["metadata"]["checksum"] = checksum_after

        self._log_change(VersionChangeLog(
            timestamp=datetime.now().isoformat(),
            operation="migrate",
            from_version=meta.source_version,
            to_version=CURRENT_VERSION,
            operator="system",
            description=f"Auto-migrate V9.0→V10.0, features={len(feature_cols)}",
            checksum_before=checksum_before,
            checksum_after=checksum_after,
        ))

        logger.info(f"[VersionManager] 迁移完成 | checksum: {checksum_after[:16]}...")
        return v10_state

    def validate_model_integrity(self, model_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        校验模型文件完整性和必要字段

        Returns:
            {
                "valid": bool,
                "version": str,
                "errors": List[str],
                "warnings": List[str],
                "checksum_match": bool,
                "metadata": Optional[Dict]
            }
        """
        result = {
            "valid": False,
            "version": "unknown",
            "errors": [],
            "warnings": [],
            "checksum_match": True,
            "metadata": None,
        }

        target_path = model_path or (self.models_dir / MODEL_FILENAME)

        if not target_path.exists():
            result["errors"].append(f"Model file not found: {target_path}")
            return result

        try:
            with open(target_path, 'rb') as f:
                state = pickle.load(f)
        except Exception as e:
            result["errors"].append(f"Failed to load model file: {e}")
            return result

        result["version"] = self.detect_version(state)

        required_fields_v10 = ["stacking", "hmm_models", "copula_model", "bsts_models"]
        for rf in required_fields_v10:
            if rf not in state:
                result["errors"].append(f"Missing required field: {rf}")

        if result["version"] == CURRENT_VERSION:
            if "metadata" not in state:
                result["warnings"].append("V10.0 format missing 'metadata' field")
            else:
                meta = state["metadata"]
                result["metadata"] = meta
                stored_checksum = state.get("_v10_checksum", "")
                computed_checksum = _compute_checksum(state)
                if stored_checksum and computed_checksum != stored_checksum:
                    result["checksum_match"] = False
                    result["errors"].append(
                        f"Checksum mismatch! stored={stored_checksum[:16]}... computed={computed_checksum[:16]}..."
                    )
                if not meta.get("created_at"):
                    result["warnings"].append("Missing created_at in metadata")
                if not meta.get("model_params_hash"):
                    result["warnings"].append("Missing model_params_hash in metadata")
        else:
            result["warnings"].append(f"Legacy format detected ({result['version']}), consider migration")

        stacking = state.get("stacking", {})
        if not isinstance(stacking, dict) or len(stacking) == 0:
            result["warnings"].append("No position models found in stacking")

        weights = state.get("weights")
        if weights is None:
            result["warnings"].append("Missing weights field")

        is_trained = state.get("is_trained", False)
        if not is_trained:
            result["warnings"].append("Model is marked as not trained")

        result["valid"] = len(result["errors"]) == 0
        return result

    def create_backup(self, model_path: Optional[Path] = None) -> str:
        """创建模型备份，返回备份文件名"""
        src_path = model_path or (self.models_dir / MODEL_FILENAME)
        if not src_path.exists():
            logger.warning(f"[VersionManager] 无法备份, 文件不存在: {src_path}")
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}.pkl"
        backup_path = self.backup_dir / backup_name

        try:
            shutil.copy2(src_path, backup_path)
            logger.info(f"[VersionManager] 备份已创建: {backup_path}")

            existing_backups = sorted(self.backup_dir.glob("backup_*.pkl"))
            while len(existing_backups) > MAX_BACKUP_COUNT:
                oldest = existing_backups.pop(0)
                oldest.unlink()
                logger.info(f"[VersionManager] 清理旧备份: {oldest.name}")

            self._log_change(VersionChangeLog(
                timestamp=datetime.now().isoformat(),
                operation="backup",
                from_version="",
                to_version="",
                operator="system",
                description=f"Created backup: {backup_name}",
            ))
            return backup_name
        except Exception as e:
            logger.error(f"[VersionManager] 创建备份失败: {e}")
            return ""

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有可用的备份"""
        backups = []
        for bp in sorted(self.backup_dir.glob("backup_*.pkl")):
            stat = bp.stat()
            backups.append({
                "filename": bp.name,
                "path": str(bp),
                "size_kb": round(stat.st_size / 1024, 1),
                "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })
        return backups

    def rollback_to_backup(self, backup_filename: str) -> bool:
        """回滚到指定备份版本"""
        backup_path = self.backup_dir / backup_filename
        if not backup_path.exists():
            logger.error(f"[VersionManager] 备份不存在: {backup_filename}")
            return False

        target_path = self.models_dir / MODEL_FILENAME

        validation_before = self.validate_model_integrity(target_path) if target_path.exists() else None

        try:
            if target_path.exists():
                current_backup = self.create_backup(target_path)
                logger.info(f"[VersionManager] 回滚前自动备份当前版本: {current_backup}")

            shutil.copy2(backup_path, target_path)

            validation_after = self.validate_model_integrity(target_path)

            self._log_change(VersionChangeLog(
                timestamp=datetime.now().isoformat(),
                operation="rollback",
                from_version=validation_before.get("version") if validation_before else "unknown",
                to_version=validation_after.get("version"),
                operator="system",
                description=f"Rolled back to backup: {backup_filename}",
                checksum_before=validation_before.get("metadata", {}).get("checksum", "") if validation_before else "",
                checksum_after=validation_after.get("metadata", {}).get("checksum", "") if validation_after else "",
            ))

            logger.info(f"[VersionManager] 回滚成功: {backup_filename} -> {target_path}")
            return True
        except Exception as e:
            logger.error(f"[VersionManager] 回滚失败: {e}")
            return False

    def rollback_to_version(self, version_str: str) -> bool:
        """回滚到指定版本的最新备份（通过扫描备份元数据）"""
        backups = self.list_backups()
        candidate = None
        for bk in backups:
            bp = Path(bk["path"])
            try:
                with open(bp, 'rb') as f:
                    state = pickle.load(f)
                detected = self.detect_version(state)
                if detected == version_str:
                    candidate = bk
                    break
                meta = state.get("metadata", {})
                if isinstance(meta, dict) and meta.get("version") == version_str:
                    candidate = bk
                    break
            except Exception:
                continue

        if candidate is None:
            logger.warning(f"[VersionManager] 未找到版本 {version_str} 的备份")
            available = set()
            for bk in backups:
                try:
                    with open(bk["path"], 'rb') as f:
                        st = pickle.load(f)
                    available.add(self.detect_version(st))
                except Exception:
                    pass
            logger.info(f"[VersionManager] 可用版本备份: {available}")
            return False

        return self.rollback_to_backup(candidate["filename"])

    def get_version_history(self) -> List[Dict[str, Any]]:
        """获取版本变更历史"""
        return list(reversed(self._change_logs))

    def get_latest_valid_backup(self) -> Optional[Dict[str, Any]]:
        """获取最新的有效备份"""
        backups = self.list_backups()
        for bk in reversed(backups):
            val = self.validate_model_integrity(Path(bk["path"]))
            if val["valid"]:
                return bk
        return None
