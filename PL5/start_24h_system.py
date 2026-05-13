#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5智能分析系统 - 24/7不间断运行启动脚本
用于启动系统并确保24小时持续运行，包含自动监控和故障恢复
"""

import sys
import os
import time
import logging
import subprocess
import signal
from pathlib import Path
from datetime import datetime
from threading import Thread

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
LOG_DIR = project_root / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)

LOG_FILE = LOG_DIR / f"system_24h_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PL5System24H:
    """PL5系统24/7运行管理器"""
    
    def __init__(self):
        self.is_running = False
        self.process = None
        self.restart_count = 0
        self.max_restarts = 100  # 最多重启100次
        self.check_interval = 300  # 检查间隔5分钟
        self.running_since = None
        
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，准备关闭系统...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """启动系统"""
        logger.info("=" * 80)
        logger.info("PL5智能分析系统 - 24/7不间断运行模式")
        logger.info("=" * 80)
        logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"日志文件: {LOG_FILE}")
        logger.info("=" * 80)
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.running_since = datetime.now()
        self.is_running = True
        
        # 启动主循环
        self.main_loop()
    
    def main_loop(self):
        """主运行循环"""
        while self.is_running and self.restart_count < self.max_restarts:
            try:
                # 检查是否需要重启
                if self.process is None or self.process.poll() is not None:
                    if self.restart_count > 0:
                        logger.info(f"检测到进程已退出，准备第 {self.restart_count + 1} 次启动...")
                    self._start_scheduler()
                
                # 定期检查系统状态
                self._check_system_health()
                
                # 打印状态
                uptime = datetime.now() - self.running_since
                logger.info(f"系统运行中 - 运行时间: {uptime} - 重启次数: {self.restart_count}")
                
                # 等待检查间隔
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("收到键盘中断信号")
                break
            except Exception as e:
                logger.error(f"主循环异常: {e}", exc_info=True)
                time.sleep(60)  # 等待1分钟后重试
        
        if self.restart_count >= self.max_restarts:
            logger.error(f"已达到最大重启次数 ({self.max_restarts})，系统将退出")
        else:
            logger.info("系统已停止")
    
    def _start_scheduler(self):
        """启动调度器"""
        try:
            logger.info("正在启动自动调度器...")
            
            # 使用auto_scheduler_v8作为后台调度器
            scheduler_script = project_root / "src" / "app" / "auto_scheduler_v8.py"
            
            if scheduler_script.exists():
                # 启动调度器进程
                self.process = subprocess.Popen(
                    [sys.executable, str(scheduler_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(project_root)
                )
                
                logger.info(f"调度器已启动 (PID: {self.process.pid})")
                self.restart_count += 1
                
            else:
                logger.error(f"调度器脚本不存在: {scheduler_script}")
                # 尝试使用哨兵服务
                self._start_sentinel()
                
        except Exception as e:
            logger.error(f"启动调度器失败: {e}", exc_info=True)
    
    def _start_sentinel(self):
        """启动哨兵服务"""
        try:
            logger.info("正在启动哨兵服务...")
            
            sentinel_script = project_root / "start_sentinel.py"
            
            if sentinel_script.exists():
                self.process = subprocess.Popen(
                    [sys.executable, str(sentinel_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(project_root)
                )
                
                logger.info(f"哨兵服务已启动 (PID: {self.process.pid})")
                self.restart_count += 1
            else:
                logger.error(f"哨兵服务脚本不存在: {sentinel_script}")
                
        except Exception as e:
            logger.error(f"启动哨兵服务失败: {e}", exc_info=True)
    
    def _check_system_health(self):
        """检查系统健康状态"""
        try:
            # 读取系统日志检查是否有错误
            log_file = LOG_DIR / "system.log"
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    recent_lines = lines[-100:] if len(lines) > 100 else lines
                    
                    # 检查是否有ERROR
                    errors = [l for l in recent_lines if 'ERROR' in l]
                    if errors:
                        logger.warning(f"检测到 {len(errors)} 个最近的错误")
            
            # 检查进程状态
            if self.process and self.process.poll() is not None:
                logger.warning(f"进程已退出，返回码: {self.process.returncode}")
                
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
    
    def stop(self):
        """停止系统"""
        logger.info("正在停止系统...")
        self.is_running = False
        
        if self.process:
            try:
                logger.info(f"终止进程 PID: {self.process.pid}")
                self.process.terminate()
                self.process.wait(timeout=10)
            except Exception as e:
                logger.error(f"终止进程失败: {e}")
                try:
                    self.process.kill()
                except:
                    pass
        
        # 打印统计信息
        if self.running_since:
            uptime = datetime.now() - self.running_since
            logger.info(f"系统运行时间: {uptime}")
            logger.info(f"总重启次数: {self.restart_count}")
        
        logger.info("系统已完全停止")

def main():
    """主函数"""
    try:
        system = PL5System24H()
        system.start()
    except Exception as e:
        logger.error(f"系统启动失败: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
