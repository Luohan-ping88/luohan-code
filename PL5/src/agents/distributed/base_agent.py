"""
分布式智能体基类
提供智能体的基础功能，包括生命周期管理、状态管理、消息处理等
"""

import asyncio
import logging
from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .protocol import (
    AgentCommunicationProtocol,
    AgentInfo,
    AgentCapability,
    AgentMessage,
    MessageType,
    MessagePriority,
    AgentProtocolMixin,
)

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """智能体状态"""

    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    OFFLINE = "offline"


class TaskResult:
    """任务结果"""

    def __init__(
        self,
        success: bool,
        result: Any = None,
        error: str = "",
        metadata: Dict[str, Any] = None,
    ):
        self.success = success
        self.result = result
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentTask:
    """智能体任务"""

    task_id: str
    task_type: str
    input_data: Dict[str, Any]
    priority: int = 1
    deadline: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC, AgentProtocolMixin):
    """智能体基类"""

    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        capabilities: List[AgentCapability],
        protocol: Optional[AgentCommunicationProtocol] = None,
    ):
        AgentProtocolMixin.__init__(self, protocol)

        self.agent_name = agent_name
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.state = AgentState.IDLE
        self.tasks: Dict[str, AgentTask] = {}
        self.task_results: Dict[str, TaskResult] = {}

        self._running = False
        self._handlers: Dict[str, Callable] = {}

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @agent_id.setter
    def agent_id(self, value: str):
        self._agent_id = value

    def get_info(self) -> AgentInfo:
        """获取智能体信息"""
        return AgentInfo(
            agent_id=self._agent_id,
            name=self.agent_name,
            agent_type=self.agent_type,
            capabilities=self.capabilities,
            status=self.state.value,
            metadata={
                "tasks_count": len(self.tasks),
                "completed_tasks": sum(1 for r in self.task_results.values() if r.success)
            },
        )

    async def start(self):
        """启动智能体"""
        self._running = True
        self.state = AgentState.IDLE

        agent_info = self.get_info()
        await self.protocol.register_agent(agent_info)

        self._register_default_handlers()

        logger.info(f"Agent started: {self.agent_name} ({self._agent_id})")

        asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        """停止智能体"""
        self._running = False
        self.state = AgentState.OFFLINE
        logger.info(f"Agent stopped: {self.agent_name}")

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            try:
                await asyncio.sleep(10)
                if self._running:
                    await self.protocol.registry.update_status(
                        self._agent_id, self.state.value
                    )
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def _register_default_handlers(self):
        """注册默认处理器"""

        @self.on_message(MessageType.REQUEST)
        async def handle_request(msg: AgentMessage):
            await self._handle_request(msg)

        @self.on_message(MessageType.QUERY)
        async def handle_query(msg: AgentMessage):
            await self._handle_query(msg)

        @self.on_message(MessageType.COMMAND)
        async def handle_command(msg: AgentMessage):
            await self._handle_command(msg)

    async def _handle_request(self, msg: AgentMessage):
        """处理请求"""
        task_type = msg.content.get("task_type", "")

        if task_type in self._handlers:
            handler = self._handlers[task_type]
            try:
                result = await handler(msg.content)
                response = AgentMessage(
                    msg_type=MessageType.RESPONSE,
                    sender=self._agent_id,
                    receiver=msg.sender,
                    content=result.to_dict() if isinstance(result, TaskResult) else result,
                    correlation_id=msg.msg_id,
                )
            except Exception as e:
                logger.error(f"Task execution error: {e}")
                response = AgentMessage(
                    msg_type=MessageType.ERROR,
                    sender=self._agent_id,
                    receiver=msg.sender,
                    content={"error": str(e)},
                    correlation_id=msg.msg_id,
                )
        else:
            response = AgentMessage(
                msg_type=MessageType.ERROR,
                sender=self._agent_id,
                receiver=msg.sender,
                content={"error": f"Unknown task type: {task_type}"},
                correlation_id=msg.msg_id,
            )

        await self.protocol.message_queue.put(response)

    async def _handle_query(self, msg: AgentMessage):
        """处理查询"""
        query_type = msg.content.get("query_type", "")

        if query_type == "status":
            content = {"status": self.state.value, "tasks": list(self.tasks.keys())}
        elif query_type == "capabilities":
            content = {
                "capabilities": [
                    {"name": c.name, "description": c.description}
                    for c in self.capabilities
                ]
            }
        else:
            content = {"error": f"Unknown query type: {query_type}"}

        response = AgentMessage(
            msg_type=MessageType.RESPONSE,
            sender=self._agent_id,
            receiver=msg.sender,
            content=content,
            correlation_id=msg.msg_id,
        )

        await self.protocol.message_queue.put(response)

    async def _handle_command(self, msg: AgentMessage):
        """处理命令"""
        command = msg.content.get("command", "")

        if command == "stop":
            await self.stop()
        elif command == "pause":
            self.state = AgentState.IDLE
        elif command == "resume":
            self.state = AgentState.WORKING

    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._handlers[task_type] = handler

    async def submit_task(self, task: AgentTask) -> str:
        """提交任务"""
        self.tasks[task.task_id] = task
        logger.info(f"Task submitted: {task.task_id} to {self.agent_name}")
        return task.task_id

    async def execute_task(self, task: AgentTask) -> TaskResult:
        """执行任务"""
        self.state = AgentState.WORKING

        try:
            task_type = task.task_type
            if task_type in self._handlers:
                handler = self._handlers[task_type]
                result = await handler(task.input_data)

                task_result = TaskResult(
                    success=True,
                    result=result,
                    metadata={"task_id": task.task_id},
                )
            else:
                task_result = TaskResult(
                    success=False,
                    error=f"No handler for task type: {task_type}",
                )

        except Exception as e:
            logger.error(f"Task execution error: {e}")
            task_result = TaskResult(
                success=False,
                error=str(e),
            )
        finally:
            self.task_results[task.task_id] = task_result
            self.state = AgentState.IDLE

        return task_result

    async def wait_for_result(self, task_id: str, timeout: float = 60.0) -> Optional[TaskResult]:
        """等待任务结果"""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if task_id in self.task_results:
                return self.task_results[task_id]
            await asyncio.sleep(0.5)

        return None


class CollaborativeAgent(BaseAgent):
    """协作型智能体 - 支持多智能体协作"""

    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        capabilities: List[AgentCapability],
        protocol: Optional[AgentCommunicationProtocol] = None,
    ):
        super().__init__(agent_name, agent_type, capabilities, protocol)

        self.collaborators: List[str] = []
        self.shared_state: Dict[str, Any] = {}

    async def add_collaborator(self, agent_id: str):
        """添加协作者"""
        if agent_id not in self.collaborators:
            self.collaborators.append(agent_id)
            logger.info(f"Collaborator added: {agent_id} to {self.agent_name}")

    async def remove_collaborator(self, agent_id: str):
        """移除协作者"""
        if agent_id in self.collaborators:
            self.collaborators.remove(agent_id)
            logger.info(f"Collaborator removed: {agent_id} from {self.agent_name}")

    async def delegate_task(
        self, target: str, task: AgentTask, wait_result: bool = False
    ) -> Optional[Dict[str, Any]]:
        """委托任务给其他智能体"""
        message = AgentMessage(
            msg_type=MessageType.REQUEST,
            sender=self._agent_id,
            receiver=target,
            content={
                "task_type": task.task_type,
                "task_id": task.task_id,
                "input_data": task.input_data,
            },
        )

        await self.protocol.message_queue.put(message)

        if wait_result:
            return await self.protocol.send_and_wait(
                target, {"task_type": task.task_type, "task_id": task.task_id, "input_data": task.input_data}
            )

        return None

    async def share_state(self, key: str, value: Any):
        """共享状态"""
        self.shared_state[key] = value

        for collaborator in self.collaborators:
            await self.send_to(
                collaborator,
                {
                    "task_type": "state_update",
                    "key": key,
                    "value": value,
                    "sender": self._agent_id,
                },
            )

    async def request_state(self, agent_id: str, key: str) -> Optional[Any]:
        """请求状态"""
        response = await self.request(
            agent_id, {"query_type": "shared_state", "key": key}, timeout=10.0
        )
        return response.get("value") if response else None


class MasterAgent(BaseAgent):
    """主智能体 - 负责任务分解和分发"""

    def __init__(
        self,
        agent_name: str,
        agent_type: str = "master",
        capabilities: Optional[List[AgentCapability]] = None,
        protocol: Optional[AgentCommunicationProtocol] = None,
    ):
        if capabilities is None:
            capabilities = [
                AgentCapability(
                    name="task_decomposition",
                    description="分解复杂任务为子任务",
                    input_schema={},
                    output_schema={},
                ),
                AgentCapability(
                    name="task_dispatch",
                    description="分发任务给合适的智能体",
                    input_schema={},
                    output_schema={},
                ),
                AgentCapability(
                    name="result_aggregation",
                    description="聚合多个智能体的结果",
                    input_schema={},
                    output_schema={},
                ),
            ]

        super().__init__(agent_name, agent_type, capabilities, protocol)

        self.workers: Dict[str, BaseAgent] = {}
        self.task_queue: List[AgentTask] = []

    def register_worker(self, worker: BaseAgent):
        """注册工作智能体"""
        self.workers[worker.agent_id] = worker
        logger.info(f"Worker registered: {worker.agent_name}")

    async def decompose_task(self, task: Dict[str, Any]) -> List[AgentTask]:
        """分解任务"""
        task_type = task.get("type", "")
        subtasks = []

        if task_type == "prediction":
            for position in ["wan", "qian", "bai", "shi", "ge"]:
                subtasks.append(
                    AgentTask(
                        task_id=f"{task.get('task_id', 'task')}_{position}",
                        task_type="predict_position",
                        input_data={"position": position, **task},
                    )
                )

        return subtasks

    async def dispatch_task(self, task: AgentTask) -> Dict[str, Any]:
        """分发任务"""
        workers_by_capability = {}

        for worker_id, worker in self.workers.items():
            for cap in worker.capabilities:
                if cap.name not in workers_by_capability:
                    workers_by_capability[cap.name] = []
                workers_by_capability[cap.name].append(worker_id)

        for capability in self.capabilities:
            if capability.name == "task_dispatch":
                subtasks = await self.decompose_task(task.input_data)

                results = {}
                for subtask in subtasks:
                    position = subtask.input_data.get("position")
                    worker_id = workers_by_capability.get(f"predict_{position}")

                    if worker_id:
                        result = await self.delegate_task(worker_id[0], subtask, wait_result=True)
                        results[position] = result

                return {"success": True, "results": results}

        return {"success": False, "error": "No suitable worker found"}
