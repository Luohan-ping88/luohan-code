"""系统恢复模块"""

import subprocess
from datetime import datetime, time as dt_time
from pathlib import Path

from core.utils import logger


class RecoveryManager:
    """系统恢复管理器"""
    
    def __init__(self):
        self.recovery_flag = Path('.recovery_executed_today')
    
    def check_recovery_needed(self):
        """检查是否需要补偿训练"""
        now = datetime.now()
        current_time = now.time()
        compensation_deadline = dt_time(20, 0)
        today_str = now.strftime('%Y-%m-%d')
        
        logger.info("启动恢复检测", extra={
            "current_time": current_time.strftime('%H:%M'),
            "compensation_deadline": compensation_deadline.strftime('%H:%M'),
            "today": today_str
        })
        
        # 检查今天是否已经执行过恢复
        if self.recovery_flag.exists():
            flag_date = self.recovery_flag.read_text().strip()
            if flag_date == today_str:
                logger.info("今天已经执行过恢复任务")
                return False, "今天已经执行过恢复任务"
        
        # 如果当前时间超过20:00，跳过补偿
        if current_time >= compensation_deadline:
            logger.info("当前时间已超过20:00，跳过补偿")
            return False, f"当前时间 {current_time.strftime('%H:%M')} 已超过20:00，跳过补偿"
        
        return True, "需要执行补偿训练"
    
    def execute_recovery(self):
        """执行补偿训练"""
        logger.info("启动补偿训练")
        
        try:
            # 创建恢复标志文件
            self.recovery_flag.write_text(datetime.now().strftime('%Y-%m-%d'))
            
            # 启动补偿训练
            process = subprocess.Popen(
                ['python', 'run_recovery_training.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            logger.info(f"补偿训练已启动", extra={"process_id": process.pid})
            return True
            
        except Exception as e:
            logger.error("启动补偿训练失败", exception=e)
            return False
    
    def clear_recovery_flag(self):
        """清除恢复标志"""
        if self.recovery_flag.exists():
            self.recovery_flag.unlink()
            logger.info("已清理恢复执行标志")
