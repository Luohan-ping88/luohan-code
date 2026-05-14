"""
智能自动化分析系统 - V8.0 升级版
调度流程优化：失败重试、监控报警、任务状态持久化
"""

# V8.0 导入增强版调度器
from .auto_scheduler_v8 import (
    AutoSchedulerV8,
    TaskRetryManager,
    TaskHistoryManager,
)

# 保持向后兼容
AutoScheduler = AutoSchedulerV8

__all__ = ["AutoScheduler", "TaskRetryManager", "TaskHistoryManager"]
