#!/usr/bin/env python3
"""
智能时间调度器
根据开奖时间动态调整任务执行策略
支持灵活的任务执行时间和动态调整机制
"""

import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class TimeStrategy(Enum):
    """时间策略枚举"""
    NORMAL = "normal"           # 正常时间（>6小时）
    COMPRESSED = "compressed"   # 压缩时间（3-6小时）
    CRITICAL = "critical"       # 紧急时间（<3小时）


class IntelligentTimeScheduler:
    """智能时间调度器 - 增强版"""
    
    def __init__(self, draw_time: str = "21:25", email_time: str = "17:30"):
        """
        初始化智能时间调度器
        
        Args:
            draw_time: 开奖时间，格式 "HH:MM"
            email_time: 邮件发送时间，格式 "HH:MM"
        """
        self.draw_time = self._parse_time(draw_time)
        self.email_time = self._parse_time(email_time)
        self.min_email_buffer = timedelta(minutes=30)
        
        # 任务耗时估计（分钟）- 动态调整
        self.task_durations = {
            "data_fetch": 10,
            "evaluation": 60,
            "optimization": 60,
            "training": 300,
            "incremental_training": 30,
            "first_prediction_verification": 20,
            "deep_strategy_optimization": 90,
            "prediction_preview": 20,
            "final_prediction": 15,
            "final_prediction_verification": 20,
            "pre_sale_prediction": 15,
            "send_report": 10
        }
        
        self.extra_tasks = [
            "extra_training",
            "hyperparameter_tune",
            "ensemble_refine"
        ]
        
        self.critical_task_chain = [
            "evaluation",
            "optimization", 
            "training"
        ]
        
        self.task_deadlines = {}
        
    def _parse_time(self, time_str: str) -> time:
        """解析时间字符串"""
        hour, minute = map(int, time_str.split(":"))
        return time(hour, minute)
    
    def _get_datetime_from_time_str(self, time_str: str, base_date: datetime = None) -> datetime:
        """将时间字符串转换为datetime对象"""
        if base_date is None:
            base_date = datetime.now()
        hour, minute = map(int, time_str.split(":"))
        return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    def get_current_strategy(self) -> Tuple[TimeStrategy, timedelta]:
        """获取当前时间策略"""
        now = datetime.now()
        today = now.date()
        
        draw_datetime = datetime.combine(today, self.draw_time)
        
        if now > draw_datetime:
            draw_datetime = datetime.combine(today + timedelta(days=1), self.draw_time)
        
        time_to_draw = draw_datetime - now
        
        if time_to_draw > timedelta(hours=6):
            strategy = TimeStrategy.NORMAL
        elif time_to_draw > timedelta(hours=3):
            strategy = TimeStrategy.COMPRESSED
        else:
            strategy = TimeStrategy.CRITICAL
        
        return strategy, time_to_draw
    
    def calculate_task_execution_window(self, task_name: str, scheduled_time: str) -> Dict:
        """计算任务的执行时间窗口"""
        now = datetime.now()
        scheduled_start = self._get_datetime_from_time_str(scheduled_time, now)
        
        if scheduled_start < now:
            start_time = now
        else:
            start_time = scheduled_start
        
        duration_minutes = self.task_durations.get(task_name, 30)
        estimated_end = start_time + timedelta(minutes=duration_minutes)
        
        return {
            "start_time": start_time,
            "estimated_end_time": estimated_end,
            "duration_minutes": duration_minutes,
            "scheduled_time": scheduled_start
        }
    
    def can_task_complete_before(self, task_name: str, scheduled_time: str, 
                                  next_task_time: str) -> Tuple[bool, Dict]:
        """判断任务能否在下一个任务开始前完成"""
        task_window = self.calculate_task_execution_window(task_name, scheduled_time)
        next_start = self._get_datetime_from_time_str(next_task_time, datetime.now())
        
        if next_start < datetime.now():
            next_start = next_start + timedelta(days=1)
        
        can_complete = task_window["estimated_end_time"] <= next_start
        buffer_time = next_start - task_window["estimated_end_time"]
        
        return can_complete, {
            **task_window,
            "next_task_start": next_start,
            "can_complete": can_complete,
            "buffer_time": buffer_time
        }
    
    def get_next_available_slot(self, current_task: str, current_end_time: datetime) -> datetime:
        """获取当前任务完成后，下一个可用时间槽"""
        if current_task in self.critical_task_chain:
            return current_end_time
        return current_end_time
    
    def should_delay_task(self, task_name: str, scheduled_time: str) -> Tuple[bool, Optional[str], str]:
        """判断任务是否应该延迟执行"""
        now = datetime.now()
        scheduled_start = self._get_datetime_from_time_str(scheduled_time, now)
        
        if scheduled_start > now:
            return False, None, scheduled_time
        
        strategy, time_to_draw = self.get_current_strategy()
        
        duration_minutes = self.task_durations.get(task_name, 30)
        end_time = now + timedelta(minutes=duration_minutes)
        
        email_time_today = self._get_datetime_from_time_str(
            self.email_time.strftime("%H:%M"), now
        )
        if email_time_today < now:
            email_time_today = email_time_today + timedelta(days=1)
        
        if end_time > email_time_today - timedelta(minutes=60):
            reason = f"任务完成时间({end_time.strftime('%H:%M')})距离邮件发送时间太近"
            new_time = (email_time_today - timedelta(minutes=60)).strftime("%H:%M")
            return True, reason, new_time
        
        if strategy == TimeStrategy.CRITICAL and task_name not in self.critical_task_chain:
            reason = f"紧急模式({strategy.value})下延迟非关键任务"
            draw_time_today = self._get_datetime_from_time_str(
                self.draw_time.strftime("%H:%M"), now
            )
            new_time = (draw_time_today + timedelta(minutes=30)).strftime("%H:%M")
            return True, reason, new_time
        
        return False, None, scheduled_time
    
    def get_dynamic_schedule(self, base_schedule: Dict[str, str]) -> Dict[str, Dict]:
        """根据当前时间和策略，动态调整任务执行时间"""
        now = datetime.now()
        strategy, time_to_draw = self.get_current_strategy()
        
        dynamic_schedule = {}
        current_time = now
        
        sorted_tasks = sorted(base_schedule.items(), 
                            key=lambda x: self._get_datetime_from_time_str(x[1], now))
        
        for task_name, scheduled_time in sorted_tasks:
            task_info = {
                "original_time": scheduled_time,
                "status": "pending",
                "delay_reason": None,
                "suggested_time": scheduled_time
            }
            
            should_delay, reason, new_time = self.should_delay_task(task_name, scheduled_time)
            
            if should_delay:
                task_info["status"] = "delayed"
                task_info["delay_reason"] = reason
                task_info["suggested_time"] = new_time
                logger.info(f"[智能调度] 任务 {task_name} 建议延迟到 {new_time}，原因: {reason}")
            
            window = self.calculate_task_execution_window(task_name, 
                                                        task_info["suggested_time"])
            task_info["estimated_start"] = window["start_time"]
            task_info["estimated_end"] = window["estimated_end_time"]
            task_info["duration_minutes"] = window["duration_minutes"]
            
            dynamic_schedule[task_name] = task_info
            
            if window["estimated_end_time"] > current_time:
                current_time = window["estimated_end_time"]
        
        return dynamic_schedule
    
    def ensure_task_chain_completion(self, task_chain: List[str], 
                                     schedule: Dict[str, str]) -> bool:
        """确保任务链能够完整执行"""
        now = datetime.now()
        
        for i, task_name in enumerate(task_chain):
            if task_name not in schedule:
                logger.warning(f"[智能调度] 任务链中的任务 {task_name} 不在调度配置中")
                return False
            
            scheduled_time = schedule[task_name]
            task_start = self._get_datetime_from_time_str(scheduled_time, now)
            
            if i == 0:
                if task_start < now:
                    strategy, time_to_draw = self.get_current_strategy()
                    total_duration = sum(self.task_durations.get(t, 30) for t in task_chain)
                    if time_to_draw < timedelta(minutes=total_duration):
                        logger.warning(f"[智能调度] 任务链无法在开奖前完成，预计需要 {total_duration} 分钟")
                        return False
            else:
                pass
        
        return True
    
    def get_optimal_task_sequence(self, available_tasks: List[str], 
                                   current_time: datetime = None) -> List[Tuple[str, datetime]]:
        """获取最优任务执行序列"""
        if current_time is None:
            current_time = datetime.now()
        
        strategy, time_to_draw = self.get_current_strategy()
        
        if strategy == TimeStrategy.CRITICAL:
            filtered_tasks = [t for t in available_tasks 
                            if t in self.critical_task_chain or t == "send_report"]
        else:
            filtered_tasks = available_tasks
        
        task_sequence = []
        cursor_time = current_time
        
        for task_name in filtered_tasks:
            duration = self.task_durations.get(task_name, 30)
            end_time = cursor_time + timedelta(minutes=duration)
            
            email_deadline = self._get_datetime_from_time_str(
                self.email_time.strftime("%H:%M"), cursor_time
            )
            if email_deadline < cursor_time:
                email_deadline += timedelta(days=1)
            
            if end_time <= email_deadline - timedelta(minutes=30) or task_name == "send_report":
                task_sequence.append((task_name, cursor_time))
                cursor_time = end_time
            else:
                logger.warning(f"[智能调度] 任务 {task_name} 无法在邮件发送前完成，跳过")
        
        return task_sequence
    
    def should_delay_email(self, recovery_delay: int = 3) -> Tuple[bool, Optional[str]]:
        """判断是否应该延迟邮件发送"""
        strategy, time_to_draw = self.get_current_strategy()
        
        now = datetime.now()
        current_time = now.time()
        
        if current_time < self.email_time:
            return False, None
        
        delay_hours = recovery_delay
        new_email_datetime = datetime.combine(now.date(), self.email_time) + timedelta(hours=delay_hours)
        
        draw_datetime = datetime.combine(now.date(), self.draw_time)
        max_email_time = draw_datetime - self.min_email_buffer
        
        if new_email_datetime > max_email_time:
            new_email_datetime = max_email_time
        
        if now < new_email_datetime:
            new_time_str = new_email_datetime.strftime("%H:%M")
            logger.info(f"[智能调度] 建议延迟邮件发送到 {new_time_str}（距离开奖还有 {time_to_draw}）")
            return True, new_time_str
        
        return False, None
    
    def get_task_priority(self, task_name: str) -> int:
        """根据当前策略获取任务优先级"""
        strategy, _ = self.get_current_strategy()
        
        base_priorities = {
            "data_fetch": 1,
            "evaluation": 2,
            "optimization": 3,
            "training": 4,
            "first_prediction_verification": 5,
            "deep_strategy_optimization": 6,
            "prediction_preview": 7,
            "final_prediction": 8,
            "final_prediction_verification": 9,
            "pre_sale_prediction": 10,
            "send_report": 11
        }
        
        extra_priorities = {
            "extra_training": 12,
            "hyperparameter_tune": 13,
            "ensemble_refine": 14
        }
        
        if strategy == TimeStrategy.CRITICAL:
            if task_name in base_priorities:
                return base_priorities[task_name]
            return 999
        
        elif strategy == TimeStrategy.COMPRESSED:
            if task_name in base_priorities:
                return base_priorities[task_name]
            if task_name == "extra_training":
                return 5.5
            return 999
        
        else:
            if task_name in base_priorities:
                return base_priorities[task_name]
            return extra_priorities.get(task_name, 999)
    
    def get_executable_tasks(self) -> List[str]:
        """获取当前可执行的任务列表"""
        strategy, time_to_draw = self.get_current_strategy()
        
        all_tasks = list(self.task_durations.keys())
        
        if strategy == TimeStrategy.NORMAL:
            all_tasks.extend(self.extra_tasks)
        elif strategy == TimeStrategy.COMPRESSED:
            if "extra_training" not in all_tasks:
                all_tasks.append("extra_training")
        
        all_tasks.sort(key=lambda t: self.get_task_priority(t))
        
        return all_tasks
    
    def should_execute_extra_task(self, task_name: str) -> bool:
        """判断是否应该执行额外任务"""
        strategy, time_to_draw = self.get_current_strategy()
        
        if strategy == TimeStrategy.CRITICAL:
            return False
        
        if strategy == TimeStrategy.COMPRESSED:
            return task_name == "extra_training"
        
        return True
    
    def get_schedule_summary(self) -> Dict:
        """获取调度摘要信息"""
        strategy, time_to_draw = self.get_current_strategy()
        should_delay, new_time = self.should_delay_email()
        
        return {
            "strategy": strategy.value,
            "time_to_draw": str(time_to_draw),
            "should_delay_email": should_delay,
            "new_email_time": new_time,
            "executable_tasks": self.get_executable_tasks(),
            "critical_chain": self.critical_task_chain
        }
