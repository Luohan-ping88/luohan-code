"""
智能体时间协调器 V2.0
支持多智能体按照任务特殊性进行智能协调分配时间
充分利用时间窗口：22:00-次日20:30（22.5小时）
"""

import logging
from typing import Dict, List, Optional
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
    is_core_task: bool = True  # 是否核心任务


@dataclass
class TimeWindow:
    """时间窗口"""

    start: datetime
    end: datetime
    available_minutes: int


class TimeCoordinatorV2:
    """时间协调器 V2.0 - 充分利用时间窗口"""

    def __init__(
        self,
        window_start_hour: int = 22,
        window_end_hour: int = 20,
        window_end_next_day: bool = True,
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
        """获取当前的时间窗口"""
        now = datetime.now()

        # 计算开始时间（今日22:00）
        start_time = now.replace(
            hour=self.window_start_hour, minute=0, second=0, microsecond=0
        )

        # 计算结束时间
        if self.window_end_next_day:
            end_time = (now + timedelta(days=1)).replace(
                hour=self.window_end_hour,
                minute=self.window_end_minute,
                second=0,
                microsecond=0,
            )
        else:
            end_time = now.replace(
                hour=self.window_end_hour,
                minute=self.window_end_minute,
                second=0,
                microsecond=0,
            )

        # 如果开始时间已过，使用下一个周期
        if start_time < now:
            start_time += timedelta(days=1)
            if self.window_end_next_day:
                end_time += timedelta(days=1)

        total_minutes = int((end_time - start_time).total_seconds() / 60)

        return TimeWindow(
            start=start_time, end=end_time, available_minutes=total_minutes
        )

    def register_task(
        self,
        task_name: str,
        estimated_duration_minutes: int,
        priority: int = 1,
        dependencies: List[str] = None,
        is_core_task: bool = True,
    ):
        """
        注册任务

        Args:
            task_name: 任务名称
            estimated_duration_minutes: 预计耗时（分钟）
            priority: 优先级（1-5，越高越优先）
            dependencies: 依赖的任务列表
            is_core_task: 是否为核心任务
        """
        self.task_slots[task_name] = TaskSlot(
            task_name=task_name,
            start_time=datetime.min,
            end_time=datetime.min,
            duration_minutes=estimated_duration_minutes,
            priority=priority,
            dependencies=dependencies or [],
            is_core_task=is_core_task,
        )
        self.task_dependencies[task_name] = dependencies or []
        logger.info(
            f"任务已注册: {task_name} (预计耗时: {estimated_duration_minutes}分钟, 优先级: {priority}, 核心:{is_core_task})"
        )

    def register_agent(self, agent_id: str, capabilities: List[str]):
        """注册智能体能力"""
        self.agent_capabilities[agent_id] = capabilities
        logger.info(f"智能体已注册: {agent_id} (能力: {capabilities})")

    def calculate_schedule(self) -> List[TaskSlot]:
        """智能计算任务调度表 V2.0 - 充分利用时间窗口"""

        window = self.get_time_window()
        logger.info(
            f"时间窗口: {window.start} -> {window.end} (可用: {window.available_minutes}分钟)"
        )

        # 1. 按优先级排序任务
        tasks_by_priority = sorted(
            self.task_slots.values(), key=lambda x: (-x.priority, x.task_name)
        )

        # 2. 构建依赖图
        schedule = []
        current_time = window.start
        completed_tasks = set()

        # 3. 核心任务调度
        logger.info("\n=== 核心任务阶段 ===")
        while len(completed_tasks) < len(self.task_slots):
            schedulable = []
            for task in tasks_by_priority:
                if task.task_name not in completed_tasks:
                    deps_ok = all(
                        dep in completed_tasks for dep in task.dependencies
                    )
                    if deps_ok:
                        schedulable.append(task)

            if not schedulable:
                break

            next_task = max(schedulable, key=lambda x: x.priority)

            task_slot = TaskSlot(
                task_name=next_task.task_name,
                start_time=current_time,
                end_time=current_time
                + timedelta(minutes=next_task.duration_minutes),
                duration_minutes=next_task.duration_minutes,
                priority=next_task.priority,
                dependencies=next_task.dependencies,
                is_core_task=next_task.is_core_task,
            )

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

        # 4. 持续优化阶段 - 充分利用剩余时间
        core_end_time = current_time
        remaining_minutes = window.available_minutes - int(
            (core_end_time - window.start).total_seconds() / 60
        )

        if remaining_minutes > 60:  # 如果剩余时间超过1小时
            logger.info(f"\n=== 持续优化阶段 ===")
            logger.info(
                f"剩余时间: {remaining_minutes}分钟 ({remaining_minutes/60:.1f}小时)"
            )

            optimization_rounds = remaining_minutes // 90  # 每轮约90分钟
            optimization_task_names = [
                "模型微调",
                "策略评估",
                "预测验证",
                "结果分析",
                "参数优化",
                "特征更新",
            ]

            for round_num in range(min(optimization_rounds, 10)):  # 最多10轮
                for i, task_name in enumerate(optimization_task_names):
                    if current_time >= window.end:
                        break

                    task_duration = min(
                        15,
                        int((window.end - current_time).total_seconds() / 60),
                    )
                    if task_duration < 5:
                        break

                    optimization_slot = TaskSlot(
                        task_name=f"{task_name} (优化轮次 {round_num + 1})",
                        start_time=current_time,
                        end_time=current_time
                        + timedelta(minutes=task_duration),
                        duration_minutes=task_duration,
                        priority=1,
                        agent_assigned=self._get_round_agent(round_num, i),
                        is_core_task=False,
                    )

                    schedule.append(optimization_slot)
                    current_time = optimization_slot.end_time

                    logger.info(
                        f"优化任务: {optimization_slot.task_name} @ "
                        f"{optimization_slot.start_time.strftime('%H:%M')} -> "
                        f"{optimization_slot.end_time.strftime('%H:%M')}"
                    )

                if current_time >= window.end:
                    break

        # 5. 等待/待命阶段
        final_remaining = int((window.end - current_time).total_seconds() / 60)
        if final_remaining > 5:
            standby_slot = TaskSlot(
                task_name="系统待命/监控",
                start_time=current_time,
                end_time=window.end,
                duration_minutes=final_remaining,
                priority=0,
                agent_assigned="monitor_agent",
                is_core_task=False,
            )
            schedule.append(standby_slot)
            logger.info(
                f"\n系统待命: {current_time.strftime('%H:%M')} -> {window.end.strftime('%H:%M')} ({final_remaining}分钟)"
            )

        return schedule

    def _assign_agent(self, task_name: str) -> str:
        """智能分配智能体给任务"""
        agents = list(self.agent_capabilities.keys())
        if not agents:
            return "default_agent"

        for agent_id, caps in self.agent_capabilities.items():
            if any(keyword in task_name.lower() for keyword in caps):
                return agent_id

        task_hash = hash(task_name)
        return agents[task_hash % len(agents)]

    def _get_round_agent(self, round_num: int, task_num: int) -> str:
        """为优化任务分配智能体"""
        agents = ["analysis_agent", "prediction_agent", "data_agent"]
        return agents[(round_num + task_num) % len(agents)]

    def print_schedule(self, schedule: List[TaskSlot]):
        """打印调度表"""
        print("\n" + "=" * 100)
        print("🕐 PL5 智能任务调度表 V2.0")
        print("=" * 100)

        window = self.get_time_window()
        print(
            f"📅 时间窗口: {window.start.strftime('%Y-%m-%d %H:%M')} -> {window.end.strftime('%Y-%m-%d %H:%M')}"
        )
        print(
            f"⏱️  总可用时间: {window.available_minutes}分钟 ({window.available_minutes/60:.1f}小时)"
        )
        print("=" * 100)

        # 核心任务
        core_tasks = [s for s in schedule if s.is_core_task]
        if core_tasks:
            print("\n🔷 核心任务阶段")
            print(
                f"{'#':<3} {'任务':<40} {'开始':<10} {'结束':<10} {'耗时':<6} {'优先级':<6} {'Agent':<15}"
            )
            print("-" * 100)

            for i, slot in enumerate(core_tasks, 1):
                print(
                    f"{i:<3} {slot.task_name:<40} "
                    f"{slot.start_time.strftime('%H:%M'):<10} "
                    f"{slot.end_time.strftime('%H:%M'):<10} "
                    f"{slot.duration_minutes:<6}分钟 "
                    f"{slot.priority:<6} "
                    f"{slot.agent_assigned:<15}"
                )

        # 优化任务
        opt_tasks = [
            s
            for s in schedule
            if not s.is_core_task and "待命" not in s.task_name
        ]
        if opt_tasks:
            total_opt_minutes = sum(s.duration_minutes for s in opt_tasks)
            print(
                f"\n🔶 持续优化阶段 (共 {len(opt_tasks)} 个任务, {total_opt_minutes}分钟)"
            )
            print("-" * 100)

            for slot in opt_tasks[:5]:  # 只显示前5个
                print(
                    f"   {slot.task_name:<40} "
                    f"{slot.start_time.strftime('%H:%M'):<10} -> "
                    f"{slot.end_time.strftime('%H:%M'):<10} "
                    f"{slot.agent_assigned:<15}"
                )

            if len(opt_tasks) > 5:
                print(f"   ... 还有 {len(opt_tasks) - 5} 个优化任务")

        # 待命任务
        standby_tasks = [s for s in schedule if "待命" in s.task_name]
        if standby_tasks:
            for slot in standby_tasks:
                print(
                    f"\n🔴 待命阶段: {slot.start_time.strftime('%H:%M')} -> {slot.end_time.strftime('%H:%M')} ({slot.duration_minutes}分钟)"
                )

        # 统计
        total_duration = sum(s.duration_minutes for s in schedule)
        core_duration = sum(
            s.duration_minutes for s in schedule if s.is_core_task
        )
        opt_duration = sum(
            s.duration_minutes for s in schedule if not s.is_core_task
        )

        print("\n" + "=" * 100)
        print("📊 统计信息")
        print("=" * 100)
        print(
            f"✅ 核心任务: {len(core_tasks)} 个, {core_duration}分钟 ({core_duration/60:.1f}小时)"
        )
        print(
            f"🔄 优化任务: {len(opt_tasks)} 个, {opt_duration}分钟 ({opt_duration/60:.1f}小时)"
        )
        print(
            f"⏸️  待命阶段: {standby_tasks[0].duration_minutes if standby_tasks else 0}分钟"
        )
        print(
            f"📈 总执行时间: {total_duration}分钟 ({total_duration/60:.1f}小时)"
        )
        print(
            f"📊 时间利用率: {total_duration/window.available_minutes*100:.1f}%"
        )
        print("=" * 100)


class DynamicTimeCoordinator(TimeCoordinatorV2):
    """动态时间协调器 - 支持实时调整"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actual_execution_times: Dict[str, timedelta] = {}

    def update_actual_duration(
        self, task_name: str, actual_duration: timedelta
    ):
        """更新任务实际执行时间"""
        self.actual_execution_times[task_name] = actual_duration
        logger.info(
            f"任务 {task_name} 实际耗时: {actual_duration.total_seconds()/60:.1f}分钟"
        )

    def recalculate_schedule(self) -> List[TaskSlot]:
        """重新计算调度表（考虑实际执行时间）"""
        logger.info("重新计算调度表...")

        for task_name, actual_duration in self.actual_execution_times.items():
            if task_name in self.task_slots:
                self.task_slots[task_name].duration_minutes = int(
                    actual_duration.total_seconds() / 60
                )

        return self.calculate_schedule()
