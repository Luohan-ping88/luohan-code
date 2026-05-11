"""
智能体时间协调器
支持多智能体按照任务特殊性进行智能协调分配时间
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskSlot:
    """任务时间槽"""
    task_name: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    priority: int = 1
    agent_assigned: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)


@dataclass
class TimeWindow:
    """时间窗口"""
    start: datetime
    end: datetime
    available_minutes: int


class TimeCoordinator:
    """时间协调器 - 智能分配任务时间"""

    def __init__(
        self,
        window_start_hour: int = 22,
        window_end_hour: int = 20,
        window_end_next_day: bool = True
    ):
        """
        初始化时间协调器

        Args:
            window_start_hour: 窗口开始小时（默认22:00）
            window_end_hour: 窗口结束小时（默认20:30）
            window_end_next_day: 结束时间是否在第二天
        """
        self.window_start_hour = window_start_hour
        self.window_end_hour = window_end_hour
        self.window_end_minute = 30
        self.window_end_next_day = window_end_next_day

        self.task_slots: Dict[str, TaskSlot] = {}
        self.task_dependencies: Dict[str, List[str]] = {}
        self.agent_capabilities: Dict[str, List[str]] = {}

    def get_time_window(self) -> TimeWindow:
        """
        获取当前的时间窗口

        Returns:
            TimeWindow: 时间窗口对象
        """
        now = datetime.now()

        # 计算开始时间（今日22:00）
        start_time = now.replace(
            hour=self.window_start_hour, minute=0, second=0, microsecond=0
        )

        # 计算结束时间
        if self.window_end_next_day:
            # 第二天20:30
            end_time = (now + timedelta(days=1)).replace(
                hour=self.window_end_hour, minute=self.window_end_minute, second=0, microsecond=0
            )
        else:
            # 当天结束时间
            end_time = now.replace(
                hour=self.window_end_hour, minute=self.window_end_minute, second=0, microsecond=0
            )

        # 如果开始时间已过，使用下一个周期
        if start_time < now:
            start_time += timedelta(days=1)
            if self.window_end_next_day:
                end_time += timedelta(days=1)

        total_minutes = int((end_time - start_time).total_seconds() / 60)

        return TimeWindow(
            start=start_time,
            end=end_time,
            available_minutes=total_minutes
        )

    def register_task(
        self,
        task_name: str,
        estimated_duration_minutes: int,
        priority: int = 1,
        dependencies: List[str] = None
    ):
        """
        注册任务

        Args:
            task_name: 任务名称
            estimated_duration_minutes: 预计耗时（分钟）
            priority: 优先级（1-5，越高越优先）
            dependencies: 依赖的任务列表
        """
        self.task_slots[task_name] = TaskSlot(
            task_name=task_name,
            start_time=datetime.min,
            end_time=datetime.min,
            duration_minutes=estimated_duration_minutes,
            priority=priority,
            dependencies=dependencies or []
        )
        self.task_dependencies[task_name] = dependencies or []
        logger.info(f"任务已注册: {task_name} (预计耗时: {estimated_duration_minutes}分钟, 优先级: {priority})")

    def register_agent(self, agent_id: str, capabilities: List[str]):
        """
        注册智能体能力

        Args:
            agent_id: 智能体ID
            capabilities: 能力列表
        """
        self.agent_capabilities[agent_id] = capabilities
        logger.info(f"智能体已注册: {agent_id} (能力: {capabilities})")

    def calculate_schedule(self) -> List[TaskSlot]:
        """
        智能计算任务调度表

        Returns:
            List[TaskSlot]: 任务时间槽列表
        """
        window = self.get_time_window()
        logger.info(f"时间窗口: {window.start} -> {window.end} (可用: {window.available_minutes}分钟)")

        # 1. 按优先级排序任务
        tasks_by_priority = sorted(
            self.task_slots.values(),
            key=lambda x: (-x.priority, x.task_name)
        )

        # 2. 构建依赖图
        schedule = []
        current_time = window.start
        completed_tasks = set()

        # 3. 按依赖关系调度
        while len(completed_tasks) < len(self.task_slots):
            # 查找可调度的任务（依赖已完成）
            schedulable = []
            for task in tasks_by_priority:
                if task.task_name not in completed_tasks:
                    deps_ok = all(dep in completed_tasks for dep in task.dependencies)
                    if deps_ok:
                        schedulable.append(task)

            if not schedulable:
                logger.warning("无法调度剩余任务，存在循环依赖")
                break

            # 选择最高优先级的任务
            next_task = max(schedulable, key=lambda x: x.priority)

            # 分配时间槽
            task_slot = TaskSlot(
                task_name=next_task.task_name,
                start_time=current_time,
                end_time=current_time + timedelta(minutes=next_task.duration_minutes),
                duration_minutes=next_task.duration_minutes,
                priority=next_task.priority,
                dependencies=next_task.dependencies
            )

            # 智能分配给合适的智能体
            task_slot.agent_assigned = self._assign_agent(next_task.task_name)

            schedule.append(task_slot)
            completed_tasks.add(next_task.task_name)
            current_time = task_slot.end_time

            logger.info(
                f"任务已调度: {next_task.task_name} @ "
                f"{task_slot.start_time.strftime('%H:%M')} -> "
                f"{task_slot.end_time.strftime('%H:%M')} "
                f"(Agent: {task_slot.agent_assigned})"
            )

        return schedule

    def _assign_agent(self, task_name: str) -> str:
        """
        智能分配智能体给任务

        Args:
            task_name: 任务名称

        Returns:
            str: 分配的智能体ID
        """
        # 简单的轮询分配策略，实际可以更复杂
        agents = list(self.agent_capabilities.keys())
        if not agents:
            return "default_agent"

        # 基于任务类型选择合适的智能体
        for agent_id, caps in self.agent_capabilities.items():
            if any(keyword in task_name.lower() for keyword in caps):
                return agent_id

        # 默认轮询
        task_hash = hash(task_name)
        return agents[task_hash % len(agents)]

    def print_schedule(self, schedule: List[TaskSlot]):
        """
        打印调度表

        Args:
            schedule: 任务时间槽列表
        """
        logger.info("\n" + "=" * 80)
        logger.info("智能任务调度表")
        logger.info("=" * 80)

        for i, slot in enumerate(schedule, 1):
            logger.info(
                f"[{i}] {slot.task_name:40} | "
                f"{slot.start_time.strftime('%H:%M')} -> {slot.end_time.strftime('%H:%M')} | "
                f"优先级:{slot.priority} | "
                f"Agent: {slot.agent_assigned}"
            )

        logger.info("=" * 80)

    def get_slot_for_task(self, task_name: str) -> Optional[TaskSlot]:
        """
        获取指定任务的时间槽

        Args:
            task_name: 任务名称

        Returns:
            Optional[TaskSlot]: 任务时间槽
        """
        schedule = self.calculate_schedule()
        for slot in schedule:
            if slot.task_name == task_name:
                return slot
        return None


class DynamicTimeCoordinator(TimeCoordinator):
    """动态时间协调器 - 支持实时调整"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actual_execution_times: Dict[str, timedelta] = {}

    def update_actual_duration(self, task_name: str, actual_duration: timedelta):
        """
        更新任务实际执行时间

        Args:
            task_name: 任务名称
            actual_duration: 实际耗时
        """
        self.actual_execution_times[task_name] = actual_duration
        logger.info(f"任务 {task_name} 实际耗时: {actual_duration.total_seconds()/60:.1f}分钟")

    def recalculate_schedule(self) -> List[TaskSlot]:
        """
        重新计算调度表（考虑实际执行时间）

        Returns:
            List[TaskSlot]: 调整后的任务时间槽列表
        """
        logger.info("重新计算调度表...")

        # 使用实际执行时间更新预计时间
        for task_name, actual_duration in self.actual_execution_times.items():
            if task_name in self.task_slots:
                self.task_slots[task_name].duration_minutes = int(
                    actual_duration.total_seconds() / 60
                )

        return self.calculate_schedule()
