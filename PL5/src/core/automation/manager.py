#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化管理模块
管理PL5预测系统的24/7自动化后台运行
"""

import asyncio
from datetime import datetime

from src.core.automation.scheduler import PL5AutomationScheduler
from src.core.utils import logger


class PL5AutomationManager:
    """PL5预测系统自动化管理器"""

    def __init__(self):
        self.scheduler = PL5AutomationScheduler()
        self.is_running = False
        self.loop = None

        logger.info("[Automation] 初始化自动化管理器")

    def start(self):
        """启动自动化管理"""
        if not self.is_running:
            # 启动调度器
            self.scheduler.start()

            # 启动事件循环
            self.loop = asyncio.get_event_loop()
            self.is_running = True

            logger.info("[Automation] 自动化管理器已启动")

    def stop(self):
        """停止自动化管理"""
        if self.is_running:
            # 停止调度器
            self.scheduler.stop()

            # 停止事件循环
            if self.loop and not self.loop.is_closed():
                self.loop.stop()

            self.is_running = False
            logger.info("[Automation] 自动化管理器已停止")

    def get_status(self):
        """获取自动化系统状态"""
        status = {
            "is_running": self.is_running,
            "scheduler_status": self.scheduler.get_status(),
            "current_time": datetime.now().isoformat(),
        }
        return status

    def run_manually(self, task_name):
        """手动运行指定任务"""
        logger.info(f"[Automation] 手动运行任务: {task_name}")

        if not self.is_running:
            logger.error("[Automation] 自动化管理器未启动")
            return False

        try:
            if task_name == "data_collection":
                asyncio.run(self.scheduler._run_data_collection())
            elif task_name == "evaluation":
                asyncio.run(self.scheduler._run_evaluation())
            elif task_name == "learning":
                asyncio.run(self.scheduler._run_learning())
            elif task_name == "training":
                asyncio.run(self.scheduler._run_training())
            elif task_name == "report_generation":
                asyncio.run(self.scheduler._run_report_generation())
            else:
                logger.error(f"[Automation] 未知任务: {task_name}")
                return False

            logger.info(f"[Automation] 任务 {task_name} 执行完成")
            return True
        except Exception as e:
            logger.error(f"[Automation] 任务 {task_name} 执行失败: {str(e)}")
            return False
