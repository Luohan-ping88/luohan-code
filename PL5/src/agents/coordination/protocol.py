"""
智能体通信协议 - 定义智能体之间的消息格式和通信机制
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, AsyncQueue
from datetime import datetime
from enum import Enum, auto
import asyncio
import uuid
import logging

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型枚举"""

    REQUEST = auto()
    RESPONSE = auto()
    BROADCAST = auto()
    NOTIFICATION = auto()
    ACK = auto()


class MessagePriority(Enum):
    """消息优先级"""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10


@dataclass
class MessageHeader:
    """消息头部"""

    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str
    receiver_id: Optional[str] = None
    message_type: MessageType
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class Message:
    """消息数据结构"""

    header: MessageHeader
    content: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "header": {
                "message_id": self.header.message_id,
                "sender_id": self.header.sender_id,
                "receiver_id": self.header.receiver_id,
                "message_type": self.header.message_type.name,
                "priority": self.header.priority.value,
                "created_at": self.header.created_at.isoformat(),
                "correlation_id": self.header.correlation_id,
                "timestamp": (
                    self.header.timestamp.isoformat()
                    if self.header.timestamp
                    else None
                ),
            },
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建消息"""
        header = MessageHeader(
            message_id=data["header"]["message_id"],
            sender_id=data["header"]["sender_id"],
            receiver_id=data["header"]["receiver_id"],
            message_type=MessageType[data["header"]["message_type"]],
            priority=MessagePriority(data["header"]["priority"]),
            created_at=datetime.fromisoformat(data["header"]["created_at"]),
            correlation_id=data["header"]["correlation_id"],
            timestamp=(
                datetime.fromisoformat(data["header"]["timestamp"])
                if data["header"].get("timestamp")
                else None
            ),
        )
        return cls(
            header=header,
            content=data["content"],
            metadata=data.get("metadata", {}),
        )


class MessageQueue:
    """消息队列管理器"""

    def __init__(self, max_size: int = 1000):
        self.queues: Dict[str, AsyncQueue[Message]] = {}
        self.max_size = max_size
        self._lock = asyncio.Lock()

    async def get_or_create_queue(self, agent_id: str) -> AsyncQueue[Message]:
        """获取或创建智能体的消息队列"""
        async with self._lock:
            if agent_id not in self.queues:
                self.queues[agent_id] = asyncio.Queue(maxsize=self.max_size)
            return self.queues[agent_id]

    async def send_message(self, message: Message) -> bool:
        """发送消息"""
        try:
            if message.header.receiver_id:
                queue = await self.get_or_create_queue(
                    message.header.receiver_id
                )
                await queue.put(message)
                logger.debug(
                    f"消息发送成功: {message.header.message_id} -> {message.header.receiver_id}"
                )
                return True
            else:
                await self.broadcast(message)
                return True
        except Exception as e:
            logger.error(f"消息发送失败: {e}")
            return False

    async def broadcast(self, message: Message) -> None:
        """广播消息"""
        async with self._lock:
            for agent_id, queue in self.queues.items():
                try:
                    await queue.put(message)
                except asyncio.QueueFull:
                    logger.warning(f"队列满: {agent_id}, 消息丢弃")

    async def receive_message(
        self, agent_id: str, timeout: Optional[float] = None
    ) -> Optional[Message]:
        """接收消息"""
        queue = await self.get_or_create_queue(agent_id)
        try:
            if timeout:
                return await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                return await queue.get()
        except asyncio.TimeoutError:
            return None

    async def get_queue_size(self, agent_id: str) -> int:
        """获取队列大小"""
        if agent_id in self.queues:
            return self.queues[agent_id].qsize()
        return 0

    async def clear_queue(self, agent_id: str) -> None:
        """清空队列"""
        if agent_id in self.queues:
            while not self.queues[agent_id].empty():
                try:
                    self.queues[agent_id].get_nowait()
                except asyncio.QueueEmpty:
                    break


class CommunicationProtocol:
    """智能体通信协议"""

    def __init__(self):
        self.message_queue = MessageQueue()
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def send_request(
        self,
        sender_id: str,
        receiver_id: str,
        content: Dict[str, Any],
        timeout: float = 30.0,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> Optional[Message]:
        """发送请求并等待响应"""
        message_id = str(uuid.uuid4())
        header = MessageHeader(
            message_id=message_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=MessageType.REQUEST,
            priority=priority,
        )
        message = Message(header=header, content=content)

        future = asyncio.Future()
        async with self._lock:
            self._pending_requests[message_id] = future

        try:
            await self.message_queue.send_message(message)
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"请求超时: {message_id}")
            return None
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return None
        finally:
            async with self._lock:
                self._pending_requests.pop(message_id, None)

    async def send_response(
        self, request: Message, content: Dict[str, Any], success: bool = True
    ) -> bool:
        """发送响应"""
        header = MessageHeader(
            sender_id=request.header.receiver_id or "unknown",
            receiver_id=request.header.sender_id,
            message_type=MessageType.RESPONSE,
            priority=request.header.priority,
            correlation_id=request.header.message_id,
        )
        response_content = {**content, "success": success}
        message = Message(header=header, content=response_content)

        async with self._lock:
            if request.header.message_id in self._pending_requests:
                future = self._pending_requests[request.header.message_id]
                if not future.done():
                    future.set_result(message)
                return True

        return await self.message_queue.send_message(message)

    async def send_ack(self, message: Message) -> bool:
        """发送确认"""
        header = MessageHeader(
            sender_id=message.header.receiver_id or "unknown",
            receiver_id=message.header.sender_id,
            message_type=MessageType.ACK,
            priority=MessagePriority.LOW,
            correlation_id=message.header.message_id,
        )
        ack_message = Message(header=header, content={})
        return await self.message_queue.send_message(ack_message)

    async def send_broadcast(
        self,
        sender_id: str,
        content: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> bool:
        """广播消息"""
        header = MessageHeader(
            sender_id=sender_id,
            message_type=MessageType.BROADCAST,
            priority=priority,
        )
        message = Message(header=header, content=content)
        await self.message_queue.broadcast(message)
        return True

    async def send_notification(
        self,
        sender_id: str,
        receiver_id: str,
        content: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> bool:
        """发送通知"""
        header = MessageHeader(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=MessageType.NOTIFICATION,
            priority=priority,
        )
        message = Message(header=header, content=content)
        return await self.message_queue.send_message(message)

    async def listen(
        self, agent_id: str, handler, timeout: Optional[float] = None
    ) -> None:
        """监听消息队列"""
        while True:
            message = await self.message_queue.receive_message(
                agent_id, timeout=timeout
            )
            if message:
                await handler(message)
            else:
                break
