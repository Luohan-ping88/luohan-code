"""
共享记忆系统 - 为智能体提供统一的记忆存储和检索机制
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from enum import Enum, auto
import uuid
import logging
from collections import deque
import asyncio
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """记忆类型"""

    SHORT_TERM = auto()
    LONG_TERM = auto()
    WORKING = auto()


@dataclass
class MemoryItem:
    """记忆项"""

    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: MemoryType
    content: Dict[str, Any]
    tags: Set[str] = field(default_factory=set)
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    agent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def access(self) -> None:
        """记录访问"""
        self.access_count += 1
        self.last_accessed = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "memory_id": self.memory_id,
            "memory_type": self.memory_type.name,
            "content": self.content,
            "tags": list(self.tags),
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "agent_id": self.agent_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """从字典创建"""
        return cls(
            memory_id=data["memory_id"],
            memory_type=MemoryType[data["memory_type"]],
            content=data["content"],
            tags=set(data.get("tags", [])),
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            agent_id=data.get("agent_id"),
            metadata=data.get("metadata", {}),
        )


class ShortTermMemory:
    """短期记忆 - 基于时间和容量的记忆"""

    def __init__(self, max_items: int = 100, ttl: int = 3600):
        self.max_items = max_items
        self.ttl = timedelta(seconds=ttl)
        self.memories: Dict[str, MemoryItem] = {}
        self._lock = asyncio.Lock()

    async def add(self, item: MemoryItem) -> bool:
        """添加记忆项"""
        async with self._lock:
            item.memory_type = MemoryType.SHORT_TERM
            item.expires_at = datetime.now() + self.ttl
            self.memories[item.memory_id] = item
            await self._cleanup()
            return True

    async def get(self, memory_id: str) -> Optional[MemoryItem]:
        """获取记忆项"""
        async with self._lock:
            item = self.memories.get(memory_id)
            if item and not item.is_expired():
                item.access()
                return item
            return None

    async def _cleanup(self) -> None:
        """清理过期记忆"""
        to_remove = [mid for mid, item in self.memories.items() if item.is_expired()]
        for mid in to_remove:
            del self.memories[mid]

        while len(self.memories) > self.max_items:
            oldest = min(self.memories.values(), key=lambda x: x.created_at)
            del self.memories[oldest.memory_id]

    async def search(
        self, tags: Optional[Set[str]] = None, query: Optional[str] = None, limit: int = 10
    ) -> List[MemoryItem]:
        """搜索记忆"""
        async with self._lock:
            await self._cleanup()
            items = list(self.memories.values())

            if tags:
                items = [item for item in items if tags & item.tags]

            if query:
                query_lower = query.lower()
                items = [item for item in items if query_lower in str(item.content).lower()]

            items.sort(key=lambda x: (-x.importance, -x.access_count))
            return items[:limit]


class LongTermMemory:
    """长期记忆 - 持久化存储"""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path
        self.memories: Dict[str, MemoryItem] = {}
        self._index: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

        if storage_path and storage_path.exists():
            self._load()

    def _load(self) -> None:
        """从文件加载"""
        if not self.storage_path:
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item_data in data:
                    item = MemoryItem.from_dict(item_data)
                    self.memories[item.memory_id] = item
                    for tag in item.tags:
                        if tag not in self._index:
                            self._index[tag] = set()
                        self._index[tag].add(item.memory_id)
            logger.info(f"长期记忆已加载: {len(self.memories)} 项")
        except Exception as e:
            logger.warning(f"加载长期记忆失败: {e}")

    async def save(self) -> None:
        """保存到文件"""
        if not self.storage_path:
            return
        async with self._lock:
            try:
                data = [item.to_dict() for item in self.memories.values()]
                with open(self.storage_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"长期记忆已保存: {len(self.memories)} 项")
            except Exception as e:
                logger.error(f"保存长期记忆失败: {e}")

    async def add(self, item: MemoryItem) -> bool:
        """添加记忆项"""
        async with self._lock:
            item.memory_type = MemoryType.LONG_TERM
            item.expires_at = None
            self.memories[item.memory_id] = item
            for tag in item.tags:
                if tag not in self._index:
                    self._index[tag] = set()
                self._index[tag].add(item.memory_id)
            return True

    async def get(self, memory_id: str) -> Optional[MemoryItem]:
        """获取记忆项"""
        async with self._lock:
            item = self.memories.get(memory_id)
            if item:
                item.access()
                return item
            return None

    async def search(
        self, tags: Optional[Set[str]] = None, query: Optional[str] = None, limit: int = 20
    ) -> List[MemoryItem]:
        """搜索记忆"""
        async with self._lock:
            items = list(self.memories.values())

            if tags:
                matching_ids = set.intersection(*[self._index.get(tag, set()) for tag in tags])
                items = [self.memories[mid] for mid in matching_ids if mid in self.memories]

            if query:
                query_lower = query.lower()
                items = [item for item in items if query_lower in str(item.content).lower()]

            items.sort(key=lambda x: (-x.importance, -x.access_count))
            return items[:limit]


class WorkingMemory:
    """工作记忆 - 当前任务上下文"""

    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.memories: deque = deque(maxlen=capacity)
        self._lock = asyncio.Lock()

    async def push(self, item: MemoryItem) -> bool:
        """添加工作记忆"""
        async with self._lock:
            item.memory_type = MemoryType.WORKING
            self.memories.append(item)
            return True

    async def pop(self) -> Optional[MemoryItem]:
        """弹出最新的工作记忆"""
        async with self._lock:
            if self.memories:
                return self.memories.pop()
            return None

    async def peek(self) -> Optional[MemoryItem]:
        """查看最新的工作记忆"""
        async with self._lock:
            if self.memories:
                return self.memories[-1]
            return None

    async def get_all(self) -> List[MemoryItem]:
        """获取所有工作记忆"""
        async with self._lock:
            return list(self.memories)

    async def clear(self) -> None:
        """清空工作记忆"""
        async with self._lock:
            self.memories.clear()


class SharedMemorySystem:
    """共享记忆系统"""

    def __init__(self, storage_path: Optional[Path] = None):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(storage_path)
        self.working_memory: Dict[str, WorkingMemory] = {}
        self._lock = asyncio.Lock()

    async def _get_working_memory(self, agent_id: str) -> WorkingMemory:
        """获取或创建工作记忆"""
        async with self._lock:
            if agent_id not in self.working_memory:
                self.working_memory[agent_id] = WorkingMemory()
            return self.working_memory[agent_id]

    async def store(
        self,
        content: Dict[str, Any],
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        tags: Optional[Set[str]] = None,
        importance: float = 0.5,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """存储记忆"""
        item = MemoryItem(
            memory_type=memory_type,
            content=content,
            tags=tags or set(),
            importance=importance,
            agent_id=agent_id,
            metadata=metadata or {},
        )

        if memory_type == MemoryType.SHORT_TERM:
            await self.short_term.add(item)
        elif memory_type == MemoryType.LONG_TERM:
            await self.long_term.add(item)
        elif memory_type == MemoryType.WORKING and agent_id:
            working = await self._get_working_memory(agent_id)
            await working.push(item)

        return item.memory_id

    async def retrieve(self, memory_id: str, memory_type: Optional[MemoryType] = None) -> Optional[MemoryItem]:
        """检索记忆"""
        if memory_type in (None, MemoryType.SHORT_TERM):
            item = await self.short_term.get(memory_id)
            if item:
                return item

        if memory_type in (None, MemoryType.LONG_TERM):
            item = await self.long_term.get(memory_id)
            if item:
                return item

        return None

    async def search(
        self,
        tags: Optional[Set[str]] = None,
        query: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        limit: int = 20,
    ) -> List[MemoryItem]:
        """搜索记忆"""
        results: List[MemoryItem] = []

        if memory_type in (None, MemoryType.SHORT_TERM):
            results.extend(await self.short_term.search(tags, query, limit))

        if memory_type in (None, MemoryType.LONG_TERM):
            results.extend(await self.long_term.search(tags, query, limit))

        results.sort(key=lambda x: (-x.importance, -x.access_count))
        return results[:limit]

    async def push_working(self, agent_id: str, content: Dict[str, Any], tags: Optional[Set[str]] = None) -> str:
        """推送工作记忆"""
        item = MemoryItem(memory_type=MemoryType.WORKING, content=content, tags=tags or set(), agent_id=agent_id)
        working = await self._get_working_memory(agent_id)
        await working.push(item)
        return item.memory_id

    async def get_working(self, agent_id: str) -> List[MemoryItem]:
        """获取工作记忆"""
        working = await self._get_working_memory(agent_id)
        return await working.get_all()

    async def clear_working(self, agent_id: str) -> None:
        """清空工作记忆"""
        working = await self._get_working_memory(agent_id)
        await working.clear()

    async def save_long_term(self) -> None:
        """保存长期记忆"""
        await self.long_term.save()
