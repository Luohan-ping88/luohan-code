"""
自动调度器兼容模块
向后兼容旧的导入路径
"""

from src.app.auto_scheduler import AutoScheduler, AutoSchedulerV8

__all__ = ['AutoScheduler', 'AutoSchedulerV8']
