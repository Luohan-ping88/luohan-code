"""长期记忆实现"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import os
from pathlib import Path

from .base import BaseMemory
from ..ai_types import MemoryConfig, MemoryType


class LongTermMemory(BaseMemory):
    """长期记忆

    用于存储长期重要信息，支持持久化存储。
    """

    def __init__(self, config: MemoryConfig):
        super().__init__(config)
        self._storage_path = Path(config.storage_path or "./long_term_memory.json")
        self._store = self._load_from_disk()

    def _load_from_disk(self) -> List[Dict]:
        """从磁盘加载记忆"""
        try:
            if self._storage_path.exists():
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_to_disk(self):
        """保存记忆到磁盘"""
        try:
            # 确保目录存在
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)

            # 过滤过期项
            current_time = datetime.now().timestamp()
            valid_items = []
            for item in self._store:
                if "timestamp" in item and self.ttl:
                    if current_time - item["timestamp"] < self.ttl:
                        valid_items.append(item)
                else:
                    valid_items.append(item)

            # 应用大小限制
            if self.max_size > 0:
                valid_items = valid_items[-self.max_size :]

            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(valid_items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add(self, item: Any) -> bool:
        """添加记忆项"""
        try:
            # 标准化记忆项
            memory_item = {
                "content": item,
                "timestamp": datetime.now().timestamp(),
                "id": f"mem_{int(datetime.now().timestamp() * 1000)}",
            }

            # 如果是字典，合并到content
            if isinstance(item, dict):
                memory_item.update(item)
                memory_item.pop("content")

            self._store.append(memory_item)
            self._maintain_size()
            self._save_to_disk()
            return True
        except Exception:
            return False

    def get(self, key: Any = None) -> Optional[Any]:
        """获取记忆项"""
        try:
            if key is None:
                return self._store[-1] if self._store else None

            # 支持按ID或内容检索
            for item in reversed(self._store):
                if item.get("id") == key:
                    return item
                if isinstance(key, str) and key in str(item.get("content", "")):
                    return item
            return None
        except Exception:
            return None

    def get_all(self) -> List[Any]:
        """获取所有记忆项"""
        return self._store

    def remove(self, key: Any) -> bool:
        """移除记忆项"""
        try:
            # 支持按ID或内容移除
            to_remove = []
            for i, item in enumerate(self._store):
                if item.get("id") == key:
                    to_remove.append(i)
                elif isinstance(key, str):
                    # 检查content字段或整个字典
                    content = str(item.get("content", ""))
                    item_str = str(item)
                    if key in content or key in item_str:
                        to_remove.append(i)

            # 从后往前移除，避免索引变化
            for i in sorted(to_remove, reverse=True):
                self._store.pop(i)

            self._save_to_disk()
            return len(to_remove) > 0
        except Exception:
            return False

    def clear(self) -> bool:
        """清空记忆"""
        try:
            self._store.clear()
            self._save_to_disk()
            return True
        except Exception:
            return False

    def size(self) -> int:
        """获取记忆大小"""
        return len(self._store)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """搜索记忆项

        Args:
            query: 搜索关键词
            top_k: 返回前k个结果

        Returns:
            匹配的记忆项列表
        """
        results = []
        for item in self._store:
            # 检查content字段或整个字典
            content = str(item.get("content", ""))
            item_str = str(item)
            if query.lower() in content.lower() or query.lower() in item_str.lower():
                results.append(item)
        return results[-top_k:]

    def get_by_time_range(self, start_time: float, end_time: float) -> List[Dict]:
        """按时间范围获取记忆项

        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳

        Returns:
            时间范围内的记忆项列表
        """
        results = []
        for item in self._store:
            timestamp = item.get("timestamp", 0)
            if start_time <= timestamp <= end_time:
                results.append(item)
        return results
