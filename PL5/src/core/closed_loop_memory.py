"""统一持久化记忆库 ClosedLoopMemoryStore。

将评估、动作、效果等闭环记忆统一持久化到单一 JSON 文件，
并在首启时并入旧格式的记忆文件（滑窗截断到指定条数）。
所有加载/保存失败均降级为内存运行并记录告警日志，绝不崩溃。
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 默认记忆文件：相对本文件（src/core/closed_loop_memory.py）上溯三级
_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "closed_loop_memory.json"

# 滑窗截断上限：每个列表保留最近 MAX_ITEMS_PER_KEY 条记录
_MAX_ITEMS_PER_KEY = 500


def _initial_data() -> Dict[str, Any]:
    return {
        "version": 1,
        "evaluations": [],
        "actions": [],
        "effects": [],
        "meta": {"last_period": None, "llm_usage": 0, "run_count": 0},
    }


def _sliding_truncate(items: List[Any], limit: int = _MAX_ITEMS_PER_KEY) -> List[Any]:
    """对列表进行滑窗截断，仅保留最近 limit 条。"""
    if len(items) > limit:
        return items[-limit:]
    return items


class ClosedLoopMemoryStore:
    """统一持久化记忆库。

    属性:
        path: 持久化文件路径。
        data: 内存中的数据字典。
    """

    def __init__(
        self,
        path: Path = _DEFAULT_PATH,
        legacy_sources: Optional[Dict[str, List[Path]]] = None,
    ) -> None:
        self.path = Path(path)
        self.data = _initial_data()
        self._load()
        if legacy_sources:
            self._merge_legacy(legacy_sources)

    def _load(self) -> None:
        """从磁盘读取记忆文件；缺失或损坏时降级为内存数据并告警。"""
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("记忆文件根节点不是字典")
            # 保留已持久化的已知键，历史键缺失时用默认值兜底
            base = _initial_data()
            for key, value in raw.items():
                if key in ("version", "meta"):
                    base[key] = value
                elif key in ("evaluations", "actions", "effects"):
                    base[key] = value if isinstance(value, list) else []
            self.data = base
        except Exception as exc:  # noqa: BLE001 加载失败不崩溃
            logger.warning("加载记忆文件失败(%s)，降级为内存模式运行: %s", self.path, exc)

    def _merge_legacy(self, legacy_sources: Dict[str, List[Path]]) -> None:
        """首启并入旧格式记忆文件，滑窗截断到 _MAX_ITEMS_PER_KEY 条。"""
        for key, paths in legacy_sources.items():
            merged: List[Any] = list(self.data.get(key, []))
            for legacy_path in paths:
                legacy = Path(legacy_path)
                try:
                    payload = json.loads(legacy.read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001 单文件解析失败不阻塞
                    logger.warning("解析旧记忆文件失败(%s): %s", legacy, exc)
                    continue
                if isinstance(payload, list):
                    merged.extend(payload)
                elif isinstance(payload, dict):
                    # 兼容"记录数组嵌套在某个字段"的旧格式
                    for k, v in payload.items():
                        if isinstance(v, list):
                            merged.extend(v)
                else:
                    logger.warning("忽略无法识别的旧记忆文件格式(%s)", legacy)
            if merged:
                self.data[key] = _sliding_truncate(merged)

    def append(self, key: str, record: Any) -> None:
        """向指定键追加一条记录。"""
        if key not in self.data or not isinstance(self.data[key], list):
            self.data.setdefault(key, record if isinstance(record, list) else [])
            return
        self.data[key].append(record)
        self.data[key] = _sliding_truncate(self.data[key])

    def get(self, key: str) -> List[Any]:
        """返回指定键的记录列表（不存在时返回空列表）。"""
        value = self.data.get(key, [])
        return value if isinstance(value, list) else []

    def set_meta(self, key: str, value: Any) -> None:
        """设置 meta 元数据字段。"""
        meta = self.data.setdefault("meta", {})
        if not isinstance(meta, dict):
            meta = {}
            self.data["meta"] = meta
        meta[key] = value

    def save(self) -> None:
        """将内存数据写入磁盘；失败时降级并告警，绝不崩溃。"""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001 保存失败不崩溃
            logger.warning("保存记忆文件失败(%s)，继续内存模式运行: %s", self.path, exc)