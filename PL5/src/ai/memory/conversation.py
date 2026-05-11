"""对话记忆实现"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from .base import BaseMemory
from ..ai_types import MemoryConfig, MemoryType, ConversationMessage


class ConversationMemory(BaseMemory):
    """对话记忆

    存储和管理对话消息历史。
    """

    def __init__(self, config: MemoryConfig):
        """初始化对话记忆

        Args:
            config: 记忆配置
        """
        if config.memory_type != MemoryType.CONVERSATION:
            config.memory_type = MemoryType.CONVERSATION
        super().__init__(config)

    def add(self, item: ConversationMessage) -> bool:
        """添加对话消息

        Args:
            item: 对话消息

        Returns:
            是否添加成功
        """
        if not isinstance(item, ConversationMessage):
            return False

        # 检查是否过期
        if self._check_expiry(item):
            return False

        # 添加到存储
        self._store.append(item)

        # 维护大小
        self._maintain_size()

        return True

    def get(self, key: Any = None) -> Optional[ConversationMessage]:
        """获取对话消息

        Args:
            key: 检索键，可以是索引或角色

        Returns:
            对话消息
        """
        if key is None:
            # 返回最新的消息
            return self._store[-1] if self._store else None

        if isinstance(key, int):
            # 按索引获取
            if 0 <= key < len(self._store):
                return self._store[key]
            return None

        if isinstance(key, str):
            # 按角色获取最新的消息
            for msg in reversed(self._store):
                if msg.role == key:
                    return msg
            return None

        return None

    def get_all(self) -> List[ConversationMessage]:
        """获取所有对话消息

        Returns:
            对话消息列表
        """
        # 过滤过期消息
        return [msg for msg in self._store if not self._check_expiry(msg)]

    def remove(self, key: Any) -> bool:
        """移除对话消息

        Args:
            key: 检索键，可以是索引或角色

        Returns:
            是否移除成功
        """
        if isinstance(key, int):
            # 按索引移除
            if 0 <= key < len(self._store):
                del self._store[key]
                return True
            return False

        if isinstance(key, str):
            # 按角色移除所有消息
            original_length = len(self._store)
            self._store = [msg for msg in self._store if msg.role != key]
            return len(self._store) < original_length

        return False

    def clear(self) -> bool:
        """清空对话记忆

        Returns:
            是否清空成功
        """
        self._store = []
        return True

    def size(self) -> int:
        """获取对话消息数量

        Returns:
            对话消息数量
        """
        # 过滤过期消息
        return len([msg for msg in self._store if not self._check_expiry(msg)])

    def get_last_n_messages(self, n: int) -> List[ConversationMessage]:
        """获取最近的n条消息

        Args:
            n: 消息数量

        Returns:
            对话消息列表
        """
        messages = self.get_all()
        return messages[-n:] if n > 0 else []

    def get_messages_by_role(self, role: str) -> List[ConversationMessage]:
        """获取指定角色的消息

        Args:
            role: 角色

        Returns:
            对话消息列表
        """
        messages = self.get_all()
        return [msg for msg in messages if msg.role == role]

    def get_message_history(self, max_tokens: Optional[int] = None) -> str:
        """获取消息历史文本

        Args:
            max_tokens: 最大token数（估算）

        Returns:
            消息历史文本
        """
        messages = self.get_all()
        history = []
        total_tokens = 0

        for msg in reversed(messages):
            msg_text = f"{msg.role}: {msg.content}"
            msg_tokens = len(msg_text.split())

            if max_tokens is not None and total_tokens + msg_tokens > max_tokens:
                break

            history.insert(0, msg_text)
            total_tokens += msg_tokens

        return "\n".join(history)

    def add_user_message(self, content: str) -> bool:
        """添加用户消息

        Args:
            content: 消息内容

        Returns:
            是否添加成功
        """
        message = ConversationMessage(role="user", content=content)
        return self.add(message)

    def add_assistant_message(self, content: str) -> bool:
        """添加助手消息

        Args:
            content: 消息内容

        Returns:
            是否添加成功
        """
        message = ConversationMessage(role="assistant", content=content)
        return self.add(message)

    def add_tool_message(self, tool_call_id: str, result: Any) -> bool:
        """添加工具消息

        Args:
            tool_call_id: 工具调用ID
            result: 工具执行结果

        Returns:
            是否添加成功
        """
        message = ConversationMessage(role="tool", content=str(result), tool_call_id=tool_call_id)
        return self.add(message)
