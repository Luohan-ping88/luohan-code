"""
智能体基类 - 定义所有智能体的通用接口和行为
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentTask:
    """智能体任务定义"""

    task_id: str
    task_type: str
    params: Dict[str, Any]
    priority: int = 5  # 1-10, 数字越小优先级越高
    created_at: datetime = None
    deadline: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class AgentResult:
    """智能体执行结果"""

    task_id: str
    success: bool
    data: Dict[str, Any]
    execution_time: float
    error_message: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "data": self.data,
            "execution_time": self.execution_time,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseAgent(ABC):
    """
    智能体基类

    所有智能体必须继承此类，实现以下核心方法：
    - execute: 执行具体任务
    - validate: 验证任务参数
    - get_capabilities: 获取能力描述
    """

    def __init__(self, name: str, max_workers: int = 4):
        self.name = name
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.task_history: list = []
        self.is_running = False
        self.metrics = {"tasks_completed": 0, "tasks_failed": 0, "total_execution_time": 0.0}

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResult:
        """执行智能体任务"""
        pass

    @abstractmethod
    def validate(self, task: AgentTask) -> bool:
        """验证任务参数是否合法"""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """获取智能体能力描述"""
        pass

    async def run_task(self, task: AgentTask) -> AgentResult:
        """运行任务并记录历史"""
        if not self.validate(task):
            return AgentResult(
                task_id=task.task_id, success=False, data={}, execution_time=0.0, error_message="Task validation failed"
            )

        start_time = datetime.now()
        self.is_running = True

        try:
            logger.info(f"[{self.name}] 开始执行任务: {task.task_id}")
            result = await self.execute(task)

            # 更新指标
            if result.success:
                self.metrics["tasks_completed"] += 1
            else:
                self.metrics["tasks_failed"] += 1

            self.metrics["total_execution_time"] += result.execution_time
            self.task_history.append(result)

            logger.info(f"[{self.name}] 任务完成: {task.task_id}, 耗时: {result.execution_time:.2f}s")

            return result

        except Exception as e:
            logger.error(f"[{self.name}] 任务执行异常: {task.task_id}, 错误: {str(e)}")
            self.metrics["tasks_failed"] += 1

            return AgentResult(
                task_id=task.task_id,
                success=False,
                data={},
                execution_time=(datetime.now() - start_time).total_seconds(),
                error_message=str(e),
            )
        finally:
            self.is_running = False

    def get_metrics(self) -> Dict[str, Any]:
        """获取智能体性能指标"""
        total_tasks = self.metrics["tasks_completed"] + self.metrics["tasks_failed"]
        avg_time = self.metrics["total_execution_time"] / total_tasks if total_tasks > 0 else 0.0

        return {
            "agent_name": self.name,
            "tasks_completed": self.metrics["tasks_completed"],
            "tasks_failed": self.metrics["tasks_failed"],
            "success_rate": (self.metrics["tasks_completed"] / total_tasks if total_tasks > 0 else 0.0),
            "avg_execution_time": avg_time,
            "is_running": self.is_running,
        }

    def save_state(self, path: Path):
        """保存智能体状态"""
        state = {
            "name": self.name,
            "metrics": self.metrics,
            "task_history": [r.to_dict() for r in self.task_history[-100:]],  # 只保留最近100条
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self, path: Path):
        """加载智能体状态"""
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        self.metrics = state.get("metrics", self.metrics)
        logger.info(f"[{self.name}] 状态已加载")

    def shutdown(self):
        """关闭智能体，释放资源"""
        self.executor.shutdown(wait=True)
        logger.info(f"[{self.name}] 智能体已关闭")
