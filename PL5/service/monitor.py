"""系统监控模块"""

import psutil
import time
from threading import Thread

from core.utils import logger


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, check_interval=60):
        self.check_interval = check_interval
        self.running = False
        self.monitor_thread = None
    
    def start(self):
        """启动监控"""
        if self.running:
            logger.warning("监控器已经在运行")
            return
        
        self.running = True
        self.monitor_thread = Thread(target=self._monitor_system, daemon=True)
        self.monitor_thread.start()
        logger.info("系统监控已启动")
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("系统监控已停止")
    
    def get_system_metrics(self):
        """获取系统指标"""
        metrics = {}
        
        try:
            # CPU使用率
            metrics['cpu_percent'] = psutil.cpu_percent(interval=0.1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            metrics['memory_percent'] = memory.percent
            
            # 磁盘使用率
            try:
                disk = psutil.disk_usage('C:\\')
                metrics['disk_percent'] = disk.percent
            except:
                metrics['disk_percent'] = None
            
            # 系统负载
            metrics['system_load'] = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            
        except Exception as e:
            logger.error("获取系统指标失败", exception=e)
        
        return metrics
    
    def _monitor_system(self):
        """监控系统"""
        while self.running:
            try:
                metrics = self.get_system_metrics()
                logger.log_system_metrics(**metrics)
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error("系统监控异常", exception=e)
                time.sleep(self.check_interval)
