"""
Agent Communication Protocol (ACP)
分布式智能体通信协议
支持智能体间的消息传递、协作和协调
"""

import json
import uuid
import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""

    REQUEST = "request"
    RESPONSE = "response"
    QUERY = "query"
    COMMAND = "command"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    BROADCAST = "broadcast"
    ERROR = "error"


class MessagePriority(Enum):
    """消息优先级"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class AgentMessage:
    """智能体消息"""

    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    msg_type: MessageType = MessageType.REQUEST
    sender: str = ""
    receiver: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    ttl: int = 300
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "msg_id": self.msg_id,
                "msg_type": self.msg_type.value,
                "sender": self.sender,
                "receiver": self.receiver,
                "content": self.content,
                "priority": self.priority.value,
                "timestamp": self.timestamp,
                "ttl": self.ttl,
                "reply_to": self.reply_to,
                "correlation_id": self.correlation_id,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AgentMessage":
        data = json.loads(json_str)
        return cls(
            msg_id=data["msg_id"],
            msg_type=MessageType(data["msg_type"]),
            sender=data["sender"],
            receiver=data["receiver"],
            content=data["content"],
            priority=MessagePriority(data["priority"]),
            timestamp=data["timestamp"],
            ttl=data["ttl"],
            reply_to=data.get("reply_to"),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentCapability:
    """智能体能力描述"""

    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    version: str = "1.0"


@dataclass
class AgentInfo:
    """智能体信息"""

    agent_id: str
    name: str
    agent_type: str
    capabilities: List[AgentCapability]
    status: str = "online"
    host: str = "localhost"
    port: int = 9000
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())


class MessageQueue:
    """消息队列"""

    def __init__(self, max_size: int = 1000):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._handlers: Dict[str, List[Callable]] = {}

    async def put(self, message: AgentMessage):
        await self._queue.put((-message.priority.value, message))

    async def get(self) -> AgentMessage:
        _, message = await self._queue.get()
        return message

    def register_handler(self, msg_type: MessageType, handler: Callable):
        if msg_type.value not in self._handlers:
            self._handlers[msg_type.value] = []
        self._handlers[msg_type.value].append(handler)

    async def dispatch(self, message: AgentMessage):
        handlers = self._handlers.get(message.msg_type.value, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")


class AgentRegistry:
    """智能体注册表"""

    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._lock = asyncio.Lock()

    async def register(self, agent_info: AgentInfo):
        async with self._lock:
            self._agents[agent_info.agent_id] = agent_info
            logger.info(f"Agent registered: {agent_info.agent_id}")

    async def unregister(self, agent_id: str):
        async with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                logger.info(f"Agent unregistered: {agent_id}")

    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        async with self._lock:
            return self._agents.get(agent_id)

    async def find_agents_by_capability(self, capability: str) -> List[AgentInfo]:
        async with self._lock:
            return [
                agent
                for agent in self._agents.values()
                if any(cap.name == capability for cap in agent.capabilities)
            ]

    async def list_agents(self) -> List[AgentInfo]:
        async with self._lock:
            return list(self._agents.values())

    async def update_status(self, agent_id: str, status: str):
        async with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].status = status
                self._agents[agent_id].last_seen = datetime.now().isoformat()


class AgentCommunicationProtocol:
    """智能体通信协议"""

    def __init__(self):
        self.registry = AgentRegistry()
        self.message_queue = MessageQueue()
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._running = False

    async def start(self):
        """启动协议"""
        self._running = True
        logger.info("Agent Communication Protocol started")

        asyncio.create_task(self._process_messages())

    async def stop(self):
        """停止协议"""
        self._running = False
        logger.info("Agent Communication Protocol stopped")

    async def _process_messages(self):
        """处理消息队列"""
        while self._running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self.message_queue.dispatch(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Message processing error: {e}")

    async def send_message(
        self,
        receiver: str,
        content: Dict[str, Any],
        msg_type: MessageType = MessageType.REQUEST,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """发送消息"""
        message = AgentMessage(
            msg_type=msg_type,
            sender="",
            receiver=receiver,
            content=content,
            priority=priority,
        )

        await self.message_queue.put(message)
        logger.debug(f"Message sent to {receiver}: {message.msg_id}")

        return message.msg_id

    async def send_and_wait(
        self,
        receiver: str,
        content: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        """发送消息并等待响应"""
        msg_id = await self.send_message(receiver, content, MessageType.REQUEST)

        future = asyncio.get_event_loop().create_future()
        self.pending_requests[msg_id] = future

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout: {msg_id}")
            return None
        finally:
            self.pending_requests.pop(msg_id, None)

    async def broadcast(
        self,
        content: Dict[str, Any],
        exclude: Optional[List[str]] = None,
    ):
        """广播消息"""
        agents = await self.registry.list_agents()
        exclude = exclude or []

        for agent in agents:
            if agent.agent_id not in exclude:
                await self.send_message(
                    agent.agent_id, content, MessageType.BROADCAST
                )

    async def register_agent(self, agent_info: AgentInfo):
        """注册智能体"""
        await self.registry.register(agent_info)

    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.message_queue.register_handler(msg_type, handler)

    async def handle_response(self, message: AgentMessage):
        """处理响应消息"""
        if message.correlation_id and message.correlation_id in self.pending_requests:
            future = self.pending_requests[message.correlation_id]
            future.set_result(message.content)


class AgentProtocolMixin:
    """智能体协议混入类"""

    def __init__(self, protocol: Optional[AgentCommunicationProtocol] = None):
        self.protocol = protocol or AgentCommunicationProtocol()
        self.agent_id = str(uuid.uuid4())
        self._running = False

    async def send_to(
        self, target: str, content: Dict[str, Any]
    ) -> str:
        """发送消息到指定智能体"""
        return await self.protocol.send_message(target, content)

    async def broadcast(self, content: Dict[str, Any]):
        """广播消息"""
        await self.protocol.broadcast(content, exclude=[self.agent_id])

    async def request(
        self, target: str, content: Dict[str, Any], timeout: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """发送请求并等待响应"""
        return await self.protocol.send_and_wait(target, content, timeout)

    def on_message(self, msg_type: MessageType):
        """消息处理装饰器"""

        def decorator(func: Callable):
            self.protocol.register_handler(msg_type, func)
            return func

        return decorator
