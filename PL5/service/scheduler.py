"""任务调度模块"""

import schedule
import time
from datetime import datetime
from threading import Thread

from core.utils import logger


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.tasks = []
        self.running = False
        self.scheduler_thread = None
    
    def add_task(self, time_str, task_func, description=""):
        """添加定时任务"""
        job = schedule.every().day.at(time_str).do(task_func)
        self.tasks.append({
            'time': time_str,
            'description': description,
            'job': job
        })
        logger.info(f"添加定时任务", extra={
            "time": time_str,
            "description": description
        })
    
    def start(self):
        """启动调度器"""
        if self.running:
            logger.warning("调度器已经在运行")
            return
        
        self.running = True
        self.scheduler_thread = Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("调度器已停止")
    
    def _run_scheduler(self):
        """运行调度器"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)
            except Exception as e:
                logger.error("调度器运行异常", exception=e)
                time.sleep(60)
    
    def get_tasks(self):
        """获取所有任务"""
        return self.tasks
