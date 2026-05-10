"""记忆层基础接口"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from ..ai_types import MemoryConfig, MemoryType, ConversationMessage, ExecutionRecord


class BaseMemory(ABC):
    """记忆抽象基类"""
    
    def __init__(self, config: MemoryConfig):
        """初始化记忆
        
        Args:
            config: 记忆配置
        """
        self.config = config
        self.memory_type = config.memory_type
        self.max_size = config.max_size
        self.ttl = config.ttl
        self.embedding_dim = config.embedding_dim
        self._store = []
    
    @abstractmethod
    def add(self, item: Any) -> bool:
        """添加记忆项
        
        Args:
            item: 记忆项
            
        Returns:
            是否添加成功
        """
        pass
    
    @abstractmethod
    def get(self, key: Any = None) -> Optional[Any]:
        """获取记忆项
        
        Args:
            key: 检索键
            
        Returns:
            记忆项
        """
        pass
    
    @abstractmethod
    def get_all(self) -> List[Any]:
        """获取所有记忆项
        
        Returns:
            记忆项列表
        """
        pass
    
    @abstractmethod
    def remove(self, key: Any) -> bool:
        """移除记忆项
        
        Args:
            key: 检索键
            
        Returns:
            是否移除成功
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """清空记忆
        
        Returns:
            是否清空成功
        """
        pass
    
    @abstractmethod
    def size(self) -> int:
        """获取记忆大小
        
        Returns:
            记忆项数量
        """
        pass
    
    def _check_expiry(self, item: Any) -> bool:
        """检查记忆项是否过期
        
        Args:
            item: 记忆项
            
        Returns:
            是否过期
        """
        if self.ttl is None:
            return False
        
        # 检查是否有timestamp属性
        if hasattr(item, 'timestamp'):
            expiry_time = item.timestamp + timedelta(seconds=self.ttl)
            return datetime.now() > expiry_time
        
        return False
    
    def _maintain_size(self):
        """维护记忆大小
        
        确保记忆大小不超过max_size
        """
        if self.max_size > 0 and len(self._store) > self.max_size:
            # 移除最旧的项
            self._store = self._store[-self.max_size:]
    
    def get_config(self) -> MemoryConfig:
        """获取配置
        
        Returns:
            记忆配置
        """
        return self.config
    
    def set_config(self, config: MemoryConfig) -> None:
        """设置配置
        
        Args:
            config: 记忆配置
        """
        self.config = config
        self.memory_type = config.memory_type
        self.max_size = config.max_size
        self.ttl = config.ttl
        self.embedding_dim = config.embedding_dim
        
        # 应用新的大小限制
        self._maintain_size()


class MemoryFactory:
    """记忆工厂
    
    用于创建不同类型的记忆实例。
    """
    
    @staticmethod
    def create_memory(memory_type: MemoryType, config: MemoryConfig) -> BaseMemory:
        """创建记忆实例
        
        Args:
            memory_type: 记忆类型
            config: 记忆配置
            
        Returns:
            记忆实例
        """
        from .conversation import ConversationMemory
        from .execution import ExecutionMemory
        from .long_term_memory import LongTermMemory
        from .vector_memory import VectorMemory
        
        config.memory_type = memory_type
        
        if memory_type == MemoryType.CONVERSATION:
            return ConversationMemory(config)
        elif memory_type == MemoryType.EXECUTION:
            return ExecutionMemory(config)
        elif memory_type == MemoryType.LONG_TERM:
            return LongTermMemory(config)
        elif memory_type == MemoryType.VECTOR:
            return VectorMemory(config)
        else:
            raise ValueError(f"Unsupported memory type: {memory_type}")


class MemoryManager:
    """记忆管理器
    
    管理不同类型的记忆实例。
    """
    
    def __init__(self):
        """初始化记忆管理器"""
        self._memories = {}
    
    def add_memory(self, name: str, memory: BaseMemory) -> None:
        """添加记忆实例
        
        Args:
            name: 记忆名称
            memory: 记忆实例
        """
        self._memories[name] = memory
    
    def create_and_add_memory(self, name: str, memory_type: MemoryType, config: MemoryConfig) -> BaseMemory:
        """创建并添加记忆实例
        
        Args:
            name: 记忆名称
            memory_type: 记忆类型
            config: 记忆配置
            
        Returns:
            创建的记忆实例
        """
        memory = MemoryFactory.create_memory(memory_type, config)
        self.add_memory(name, memory)
        return memory
    
    def get_memory(self, name: str) -> Optional[BaseMemory]:
        """获取记忆实例
        
        Args:
            name: 记忆名称
            
        Returns:
            记忆实例
        """
        return self._memories.get(name)
    
    def list_memories(self) -> List[str]:
        """列出所有记忆名称
        
        Returns:
            记忆名称列表
        """
        return list(self._memories.keys())
    
    def remove_memory(self, name: str) -> bool:
        """移除记忆实例
        
        Args:
            name: 记忆名称
            
        Returns:
            是否移除成功
        """
        if name in self._memories:
            del self._memories[name]
            return True
        return False
    
    def clear_all(self) -> None:
        """清空所有记忆"""
        for memory in self._memories.values():
            memory.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息
        """
        stats = {}
        for name, memory in self._memories.items():
            stats[name] = {
                "type": memory.memory_type.value,
                "size": memory.size(),
                "max_size": memory.max_size
            }
        return stats
