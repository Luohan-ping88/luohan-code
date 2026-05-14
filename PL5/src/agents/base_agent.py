"""
智能体基类 - 定义所有智能体的通用接口和行为
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentTask:
    """智能体任务定义"""

    task_id: str
    task_type: str
    params: Optional[Dict[str, Any]] = None
    priority: int = 5  # 1-10, 数字越小优先级越高
    created_at: datetime = None
    deadline: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "params": self.params,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
        }


@dataclass
class AgentResult:
    """智能体执行结果"""

    task_id: str
    success: bool = True
    data: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @classmethod
    def success(
        cls,
        task_id: str,
        data: Optional[Dict[str, Any]] = None,
        execution_time: float = 0.0,
    ) -> "AgentResult":
        return cls(
            task_id=task_id,
            success=True,
            data=data or {},
            execution_time=execution_time,
            error_message=None,
        )

    @classmethod
    def failure(
        cls, task_id: str, error: str, execution_time: float = 0.0
    ) -> "AgentResult":
        return cls(
            task_id=task_id,
            success=False,
            data=None,
            execution_time=execution_time,
            error_message=error,
        )

    @property
    def error(self) -> Optional[str]:
        return self.error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "data": self.data,
            "execution_time": self.execution_time,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseAgent:
    """
    智能体基类

    所有智能体必须继承此类，实现以下核心方法：
    - execute: 执行具体任务
    """

    def __init__(self, name: str, max_workers: int = 4):
        self.name = name
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.task_history: list = []
        self.is_running = False
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.total_execution_time = 0.0

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 1.0
        return self.tasks_completed / total

    async def execute(self, task: AgentTask) -> AgentResult:
        """执行智能体任务"""
        raise NotImplementedError("Subclasses must implement execute method")

    def validate(self, task: AgentTask) -> bool:
        """验证任务参数是否合法"""
        if not task or not task.task_id:
            return False
        return True

    def get_capabilities(self) -> Dict[str, Any]:
        """获取智能体能力描述"""
        return {
            "name": self.name,
            "supported_tasks": [],
            "max_workers": self.max_workers,
        }

    async def run_task(self, task: AgentTask) -> AgentResult:
        """运行任务并记录历史"""
        if not self.validate(task):
            return AgentResult.failure(
                task_id=task.task_id, error="Task validation failed"
            )

        start_time = datetime.now()
        self.is_running = True

        try:
            logger.info(f"[{self.name}] 开始执行任务: {task.task_id}")
            result = await self.execute(task)

            # 更新指标
            if result.success:
                self.tasks_completed += 1
            else:
                self.tasks_failed += 1

            self.total_execution_time += result.execution_time
            self.task_history.append(result)

            logger.info(
                f"[{self.name}] 任务完成: {task.task_id}, 耗时: {result.execution_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(
                f"[{self.name}] 任务执行异常: {task.task_id}, 错误: {str(e)}"
            )
            self.tasks_failed += 1

            return AgentResult.failure(
                task_id=task.task_id,
                error=str(e),
                execution_time=(datetime.now() - start_time).total_seconds(),
            )
        finally:
            self.is_running = False

    def get_metrics(self) -> Dict[str, Any]:
        """获取智能体性能指标"""
        total_tasks = self.tasks_completed + self.tasks_failed
        avg_time = (
            self.total_execution_time / total_tasks if total_tasks > 0 else 0.0
        )

        return {
            "agent_name": self.name,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "success_rate": self.success_rate,
            "avg_execution_time": avg_time,
            "is_running": self.is_running,
        }

    def save_state(self, path: Path):
        """保存智能体状态"""
        state = {
            "name": self.name,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "total_execution_time": self.total_execution_time,
            "task_history": [
                r.to_dict() for r in self.task_history[-100:]
            ],  # 只保留最近100条
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self, path: Path):
        """加载智能体状态"""
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        self.tasks_completed = state.get("tasks_completed", self.tasks_completed)
        self.tasks_failed = state.get("tasks_failed", self.tasks_failed)
        self.total_execution_time = state.get(
            "total_execution_time", self.total_execution_time
        )
        logger.info(f"[{self.name}] 状态已加载")

    async def shutdown(self):
        """关闭智能体，释放资源"""
        self.executor.shutdown(wait=True)
        logger.info(f"[{self.name}] 智能体已关闭")
