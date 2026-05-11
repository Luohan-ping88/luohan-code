"""任务依赖管理器
管理系统任务之间的依赖关系，确保任务按正确顺序执行
"""

import logging
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    """任务定义"""

    name: str
    task_id: str
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskDependencyManager:
    """任务依赖管理器"""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.task_order: List[str] = []
        self._dependency_graph: Dict[str, Set[str]] = {}

    def add_task(self, task: Task) -> None:
        """添加任务

        Args:
            task: 任务对象
        """
        self.tasks[task.task_id] = task
        self._build_dependency_graph()
        logger.debug(f"[TaskDependencyManager] 添加任务: {task.task_id}")

    def add_task_simple(
        self,
        task_id: str,
        name: str,
        dependencies: List[str] = None,
        priority: int = 0,
        metadata: Dict[str, Any] = None,
    ) -> Task:
        """简化方式添加任务

        Args:
            task_id: 任务ID
            name: 任务名称
            dependencies: 依赖的任务ID列表
            priority: 优先级
            metadata: 元数据

        Returns:
            创建的任务对象
        """
        task = Task(
            name=name, task_id=task_id, dependencies=dependencies or [], priority=priority, metadata=metadata or {}
        )
        self.add_task(task)
        return task

    def _build_dependency_graph(self) -> None:
        """构建依赖图"""
        self._dependency_graph.clear()

        for task_id, task in self.tasks.items():
            self._dependency_graph[task_id] = set(task.dependencies)

    def get_execution_order(self) -> List[str]:
        """获取任务执行顺序（拓扑排序）

        Returns:
            按依赖顺序排列的任务ID列表

        Raises:
            ValueError: 如果存在循环依赖
        """
        # Kahn算法进行拓扑排序
        in_degree = {task_id: 0 for task_id in self.tasks}

        for task_id, deps in self._dependency_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[task_id] += 1

        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # 按优先级排序
            queue.sort(key=lambda x: -self.tasks[x].priority)
            current = queue.pop(0)
            result.append(current)

            for task_id, deps in self._dependency_graph.items():
                if current in deps:
                    in_degree[task_id] -= 1
                    if in_degree[task_id] == 0:
                        queue.append(task_id)

        if len(result) != len(self.tasks):
            raise ValueError("存在循环依赖")

        self.task_order = result
        return result

    def get_ready_tasks(self) -> List[Task]:
        """获取准备就绪的任务（所有依赖已完成）

        Returns:
            准备就绪的任务列表
        """
        ready_tasks = []

        for task_id, task in self.tasks.items():
            if task.status != TaskStatus.PENDING:
                continue

            # 检查所有依赖是否都已完成
            all_deps_completed = True
            for dep_id in task.dependencies:
                if dep_id not in self.tasks:
                    logger.warning(f"[TaskDependencyManager] 任务 {task_id} 的依赖 {dep_id} 不存在")
                    all_deps_completed = False
                    break

                dep_task = self.tasks[dep_id]
                if dep_task.status not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]:
                    all_deps_completed = False
                    break

            if all_deps_completed:
                task.status = TaskStatus.READY
                ready_tasks.append(task)

        # 按优先级排序
        ready_tasks.sort(key=lambda x: -x.priority)
        return ready_tasks

    def mark_task_started(self, task_id: str) -> bool:
        """标记任务开始执行

        Args:
            task_id: 任务ID

        Returns:
            是否成功
        """
        if task_id not in self.tasks:
            logger.error(f"[TaskDependencyManager] 任务不存在: {task_id}")
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.now()
        logger.info(f"[TaskDependencyManager] 任务开始: {task_id}")
        return True

    def mark_task_completed(self, task_id: str, result: Any = None) -> bool:
        """标记任务完成

        Args:
            task_id: 任务ID
            result: 任务结果

        Returns:
            是否成功
        """
        if task_id not in self.tasks:
            logger.error(f"[TaskDependencyManager] 任务不存在: {task_id}")
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.end_time = datetime.now()
        logger.info(f"[TaskDependencyManager] 任务完成: {task_id}")
        return True

    def mark_task_failed(self, task_id: str, error: str) -> bool:
        """标记任务失败

        Args:
            task_id: 任务ID
            error: 错误信息

        Returns:
            是否成功
        """
        if task_id not in self.tasks:
            logger.error(f"[TaskDependencyManager] 任务不存在: {task_id}")
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.error = error
        task.end_time = datetime.now()
        logger.error(f"[TaskDependencyManager] 任务失败: {task_id}, 错误: {error}")
        return True

    def mark_task_skipped(self, task_id: str) -> bool:
        """标记任务跳过

        Args:
            task_id: 任务ID

        Returns:
            是否成功
        """
        if task_id not in self.tasks:
            logger.error(f"[TaskDependencyManager] 任务不存在: {task_id}")
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.SKIPPED
        task.end_time = datetime.now()
        logger.info(f"[TaskDependencyManager] 任务跳过: {task_id}")
        return True

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态，如果任务不存在返回None
        """
        if task_id not in self.tasks:
            return None
        return self.tasks[task_id].status

    def is_all_completed(self) -> bool:
        """检查是否所有任务都已完成

        Returns:
            是否全部完成
        """
        return all(
            task.status in [TaskStatus.COMPLETED, TaskStatus.SKIPPED, TaskStatus.FAILED] for task in self.tasks.values()
        )

    def get_failed_tasks(self) -> List[Task]:
        """获取失败的任务列表

        Returns:
            失败的任务列表
        """
        return [task for task in self.tasks.values() if task.status == TaskStatus.FAILED]

    def get_statistics(self) -> Dict[str, Any]:
        """获取任务统计信息

        Returns:
            统计信息字典
        """
        status_counts = {}
        for task in self.tasks.values():
            status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1

        total_duration = 0
        completed_count = 0
        for task in self.tasks.values():
            if task.start_time and task.end_time:
                duration = (task.end_time - task.start_time).total_seconds()
                total_duration += duration
                completed_count += 1

        return {
            "total_tasks": len(self.tasks),
            "status_counts": status_counts,
            "avg_duration": total_duration / completed_count if completed_count > 0 else 0,
            "failed_count": len(self.get_failed_tasks()),
            "completion_rate": status_counts.get("completed", 0) / len(self.tasks) if self.tasks else 0,
        }

    def reset(self) -> None:
        """重置所有任务状态"""
        for task in self.tasks.values():
            task.status = TaskStatus.PENDING
            task.result = None
            task.error = None
            task.start_time = None
            task.end_time = None

        logger.info("[TaskDependencyManager] 任务状态已重置")

    def clear(self) -> None:
        """清空所有任务"""
        self.tasks.clear()
        self.task_order.clear()
        self._dependency_graph.clear()
        logger.info("[TaskDependencyManager] 任务管理器已清空")


# 创建从调度配置生成任务管理器的方法
def create_task_manager_from_config(config: Dict[str, Any]) -> TaskDependencyManager:
    """从调度配置创建任务管理器

    Args:
        config: 调度配置字典

    Returns:
        配置好的任务管理器
    """
    manager = TaskDependencyManager()

    tasks_config = config.get("tasks", {})

    # 定义任务依赖关系
    task_dependencies = {
        "data_fetch": [],
        "evaluation": ["data_fetch"],
        "optimization": ["evaluation"],
        "training": ["optimization", "data_fetch"],
        "incremental_training_morning": ["data_fetch"],
        "incremental_training_noon": ["incremental_training_morning"],
        "incremental_training_afternoon": ["incremental_training_noon"],
        "deep_strategy_optimization": ["training"],
        "prediction_preview": ["deep_strategy_optimization"],
        "final_prediction": ["prediction_preview", "deep_strategy_optimization"],
        "final_prediction_verification": ["final_prediction"],
        "pre_sale_prediction": ["final_prediction_verification"],
        "send_report": ["pre_sale_prediction"],
    }

    # 从配置创建任务
    for task_id, task_config in tasks_config.items():
        priority = task_config.get("priority", 0)
        dependencies = task_dependencies.get(task_id, [])

        manager.add_task_simple(
            task_id=task_id, name=task_config.get("name", task_id), dependencies=dependencies, priority=priority
        )

    logger.info(f"[TaskDependencyManager] 从配置创建了 {len(manager.tasks)} 个任务")
    return manager
