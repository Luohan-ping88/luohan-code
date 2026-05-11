"""
智能体时间协调器 V3.0
支持多智能体按照任务特殊性进行智能协调分配时间
充分利用时间窗口：22:00-次日20:30（22.5小时）
核心任务预算：6小时
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
    is_core_task: bool = True
    estimated_actual_minutes: int = 0  # 实际预估时间


@dataclass
class TimeWindow:
    """时间窗口"""
    start: datetime
    end: datetime
    available_minutes: int


class TimeCoordinatorV3:
    """时间协调器 V3.0 - 合理的核心任务预算"""

    CORE_TASK_BUDGET_MINUTES = 360  # 核心任务预算：6小时

    def __init__(
        self,
        window_start_hour: int = 22,
        window_end_hour: int = 20,
        window_end_next_day: bool = True
    ):
        self.window_start_hour = window_start_hour
        self.window_end_hour = window_end_hour
        self.window_end_minute = 30
        self.window_end_next_day = window_end_next_day

        self.task_slots: Dict[str, TaskSlot] = {}
        self.task_dependencies: Dict[str, List[str]] = {}
        self.agent_capabilities: Dict[str, List[str]] = {}

    def get_time_window(self) -> TimeWindow:
        """获取时间窗口"""
        now = datetime.now()

        start_time = now.replace(
            hour=self.window_start_hour, minute=0, second=0, microsecond=0
        )

        if self.window_end_next_day:
            end_time = (now + timedelta(days=1)).replace(
                hour=self.window_end_hour, minute=self.window_end_minute, second=0, microsecond=0
            )
        else:
            end_time = now.replace(
                hour=self.window_end_hour, minute=self.window_end_minute, second=0, microsecond=0
            )

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
        dependencies: List[str] = None,
        is_core_task: bool = True,
        estimated_actual_minutes: int = 0
    ):
        """
        注册任务

        Args:
            task_name: 任务名称
            estimated_duration_minutes: 理论耗时
            priority: 优先级
            dependencies: 依赖任务
            is_core_task: 是否核心任务
            estimated_actual_minutes: 实际预估耗时（更长）
        """
        actual_minutes = estimated_actual_minutes if estimated_actual_minutes > 0 else estimated_duration_minutes

        self.task_slots[task_name] = TaskSlot(
            task_name=task_name,
            start_time=datetime.min,
            end_time=datetime.min,
            duration_minutes=estimated_duration_minutes,
            priority=priority,
            dependencies=dependencies or [],
            is_core_task=is_core_task,
            estimated_actual_minutes=actual_minutes
        )
        self.task_dependencies[task_name] = dependencies or []

    def register_agent(self, agent_id: str, capabilities: List[str]):
        """注册智能体"""
        self.agent_capabilities[agent_id] = capabilities

    def calculate_schedule(self) -> List[TaskSlot]:
        """计算调度表 V3.0"""

        window = self.get_time_window()

        tasks_by_priority = sorted(
            self.task_slots.values(),
            key=lambda x: (-x.priority, x.task_name)
        )

        schedule = []
        current_time = window.start
        completed_tasks = set()

        # 核心任务阶段
        logger.info("\n=== 核心任务阶段 ===")
        core_total_theory = 0
        core_total_actual = 0

        while len(completed_tasks) < len(self.task_slots):
            schedulable = []
            for task in tasks_by_priority:
                if task.task_name not in completed_tasks:
                    deps_ok = all(dep in completed_tasks for dep in task.dependencies)
                    if deps_ok:
                        schedulable.append(task)

            if not schedulable:
                break

            next_task = max(schedulable, key=lambda x: x.priority)

            # 使用实际预估时间
            duration = next_task.estimated_actual_minutes

            task_slot = TaskSlot(
                task_name=next_task.task_name,
                start_time=current_time,
                end_time=current_time + timedelta(minutes=duration),
                duration_minutes=duration,
                priority=next_task.priority,
                dependencies=next_task.dependencies,
                is_core_task=next_task.is_core_task,
                estimated_actual_minutes=duration
            )

            task_slot.agent_assigned = self._assign_agent(next_task.task_name)

            schedule.append(task_slot)
            completed_tasks.add(next_task.task_name)
            current_time = task_slot.end_time

            core_total_theory += next_task.duration_minutes
            core_total_actual += duration

            logger.info(
                f"任务已调度: {next_task.task_name} @ "
                f"{task_slot.start_time.strftime('%H:%M')} -> {task_slot.end_time.strftime('%H:%M')} "
                f"(理论:{next_task.duration_minutes}分钟, 实际预估:{duration}分钟)"
            )

        # 持续优化阶段
        remaining_minutes = window.available_minutes - int((current_time - window.start).total_seconds() / 60)

        if remaining_minutes > 60:
            logger.info(f"\n=== 持续优化阶段 ===")
            logger.info(f"剩余时间: {remaining_minutes}分钟 ({remaining_minutes/60:.1f}小时)")

            optimization_rounds = remaining_minutes // 60
            optimization_task_names = [
                "模型微调",
                "策略评估",
                "预测验证",
                "结果分析",
                "参数优化",
                "特征更新"
            ]

            for round_num in range(min(optimization_rounds, 20)):
                for i, task_name in enumerate(optimization_task_names):
                    if current_time >= window.end:
                        break

                    task_duration = 10
                    if current_time + timedelta(minutes=task_duration) > window.end:
                        task_duration = int((window.end - current_time).total_seconds() / 60)

                    if task_duration < 5:
                        break

                    optimization_slot = TaskSlot(
                        task_name=f"{task_name} (轮次 {round_num + 1})",
                        start_time=current_time,
                        end_time=current_time + timedelta(minutes=task_duration),
                        duration_minutes=task_duration,
                        priority=1,
                        agent_assigned=self._get_round_agent(round_num, i),
                        is_core_task=False
                    )

                    schedule.append(optimization_slot)
                    current_time = optimization_slot.end_time

                    logger.info(
                        f"优化任务: {optimization_slot.task_name} @ "
                        f"{optimization_slot.start_time.strftime('%H:%M')} -> {optimization_slot.end_time.strftime('%H:%M')}"
                    )

                if current_time >= window.end:
                    break

        # 待命阶段
        final_remaining = int((window.end - current_time).total_seconds() / 60)
        if final_remaining > 5:
            standby_slot = TaskSlot(
                task_name="系统待命/监控",
                start_time=current_time,
                end_time=window.end,
                duration_minutes=final_remaining,
                priority=0,
                agent_assigned="monitor_agent",
                is_core_task=False
            )
            schedule.append(standby_slot)
            logger.info(f"\n系统待命: {current_time.strftime('%H:%M')} -> {window.end.strftime('%H:%M')} ({final_remaining}分钟)")

        return schedule

    def _assign_agent(self, task_name: str) -> str:
        """智能分配智能体"""
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
        print("🕐 PL5 智能任务调度表 V3.0")
        print("=" * 100)

        window = self.get_time_window()
        print(f"📅 时间窗口: {window.start.strftime('%Y-%m-%d %H:%M')} -> {window.end.strftime('%Y-%m-%d %H:%M')}")
        print(f"⏱️  总可用时间: {window.available_minutes}分钟 ({window.available_minutes/60:.1f}小时)")
        print(f"🎯 核心任务预算: {self.CORE_TASK_BUDGET_MINUTES}分钟 ({self.CORE_TASK_BUDGET_MINUTES/60:.1f}小时)")
        print("=" * 100)

        # 核心任务
        core_tasks = [s for s in schedule if s.is_core_task]
        if core_tasks:
            print("\n🔷 核心任务阶段")
            print(f"{'#':<3} {'任务':<35} {'开始':<10} {'结束':<10} {'耗时':<8} {'Agent':<15}")
            print("-" * 100)

            core_actual_total = 0
            for i, slot in enumerate(core_tasks, 1):
                core_actual_total += slot.duration_minutes
                print(
                    f"{i:<3} {slot.task_name:<35} "
                    f"{slot.start_time.strftime('%H:%M'):<10} "
                    f"{slot.end_time.strftime('%H:%M'):<10} "
                    f"{slot.duration_minutes:<8}分钟 "
                    f"{slot.agent_assigned:<15}"
                )

            print("-" * 100)
            print(f"核心任务总计: {core_actual_total}分钟 ({core_actual_total/60:.1f}小时)")

        # 优化任务
        opt_tasks = [s for s in schedule if not s.is_core_task and "待命" not in s.task_name]
        if opt_tasks:
            total_opt_minutes = sum(s.duration_minutes for s in opt_tasks)
            print(f"\n🔶 持续优化阶段 (共 {len(opt_tasks)} 个任务, {total_opt_minutes}分钟)")
            print("-" * 100)

            for slot in opt_tasks[:8]:
                print(
                    f"   {slot.task_name:<40} "
                    f"{slot.start_time.strftime('%H:%M'):<10} -> "
                    f"{slot.end_time.strftime('%H:%M'):<10} "
                    f"{slot.agent_assigned:<15}"
                )

            if len(opt_tasks) > 8:
                print(f"   ... 还有 {len(opt_tasks) - 8} 个优化任务")

        # 待命任务
        standby_tasks = [s for s in schedule if "待命" in s.task_name]
        if standby_tasks:
            for slot in standby_tasks:
                print(f"\n🔴 待命阶段: {slot.start_time.strftime('%H:%M')} -> {slot.end_time.strftime('%H:%M')} ({slot.duration_minutes}分钟)")

        # 统计
        total_duration = sum(s.duration_minutes for s in schedule)
        opt_duration = sum(s.duration_minutes for s in schedule if not s.is_core_task)

        print("\n" + "=" * 100)
        print("📊 统计信息")
        print("=" * 100)
        print(f"✅ 核心任务: {len(core_tasks)} 个, {sum(s.duration_minutes for s in core_tasks)}分钟 ({sum(s.duration_minutes for s in core_tasks)/60:.1f}小时)")
        print(f"🔄 优化任务: {len(opt_tasks)} 个, {opt_duration}分钟 ({opt_duration/60:.1f}小时)")
        print(f"⏸️  待命阶段: {standby_tasks[0].duration_minutes if standby_tasks else 0}分钟")
        print(f"📈 总执行时间: {total_duration}分钟 ({total_duration/60:.1f}小时)")
        print(f"📊 时间利用率: {total_duration/window.available_minutes*100:.1f}%")
        print("=" * 100)
