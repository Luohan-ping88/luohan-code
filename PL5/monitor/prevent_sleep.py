"""
防止电脑进入睡眠状态
让系统可以24小时后台运行
"""

import ctypes
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Windows API常量
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def prevent_sleep():
    """防止电脑进入睡眠状态"""
    logger.info("=" * 60)
    logger.info("启动防止睡眠模式")
    logger.info("=" * 60)
    logger.info("系统将保持唤醒状态，确保定时任务正常执行")
    logger.info("按 Ctrl+C 停止")
    logger.info("=" * 60)
    
    try:
        while True:
            # 设置系统状态，防止睡眠
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
            
            # 每30秒执行一次，确保持续有效
            time.sleep(30)
            
    except KeyboardInterrupt:
        logger.info("\n停止防止睡眠模式")
        # 恢复默认状态
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        logger.info("电脑可以正常进入睡眠状态了")


if __name__ == "__main__":
    prevent_sleep()
