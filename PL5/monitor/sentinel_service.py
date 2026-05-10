#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5智能分析系统 - 哨兵服务
24/7全天候监控系统状态，自动检测和恢复故障
"""

import os
import sys
import time
import threading
import logging
import json
from datetime import datetime
from pathlib import Path

from src.core.utils import logger
from monitor.system_monitor import SystemMonitor
from monitor.perfect_monitor import PerfectSystemMonitor
from monitor.performance_monitor import PerformanceMonitor
from monitor.system_checker import PerfectSystemChecker

class SentinelService:
    """哨兵服务主类"""
    
    def __init__(self, config_path=None):
        self.config = self._load_config(config_path)
        self.is_running = False
        self.monitoring_thread = None
        self.pl5_process = None  # PL5系统进程
        
        # 初始化监控模块
        self.system_monitor = SystemMonitor()
        self.perfect_monitor = PerfectSystemMonitor()
        self.performance_monitor = PerformanceMonitor()
        self.system_checker = PerfectSystemChecker()
        
        # 初始化状态
        self.status = {
            'last_check': None,
            'health_status': 'unknown',
            'performance_status': 'unknown',
            'alerts': [],
            'recovery_history': [],
            'pl5_pid': None  # PL5系统PID
        }
        
        # 确保日志目录存在
        self.log_dir = Path('logs/sentinel')
        self.log_dir.mkdir(exist_ok=True, parents=True)
        
        # 配置日志
        self._setup_logger()
    
    def _load_config(self, config_path=None):
        """加载配置"""
        default_config = {
            'monitor_interval': 60,  # 监控间隔（秒）
            'health_check_interval': 300,  # 健康检查间隔（秒）
            'performance_check_interval': 120,  # 性能检查间隔（秒）
            'alert_thresholds': {
                'cpu_usage': 80,
                'memory_usage': 80,
                'disk_usage': 90,
                'response_time': 5
            },
            'recovery_attempts': 3,
            'recovery_delay': 5
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                logger.warning(f"加载配置失败: {e}")
        
        return default_config
    
    def _setup_logger(self):
        """设置日志"""
        log_file = self.log_dir / f"sentinel_{datetime.now().strftime('%Y%m%d')}.log"
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        self.sentinel_logger = logging.getLogger('sentinel')
        self.sentinel_logger.addHandler(handler)
        self.sentinel_logger.setLevel(logging.INFO)
    
    def start(self):
        """启动哨兵服务"""
        if self.is_running:
            logger.info("[哨兵服务] 服务已经在运行")
            return
        
        logger.info("[哨兵服务] 启动中...")
        self.is_running = True
        
        # 启动监控线程
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        logger.info("[哨兵服务] 启动成功！")
    
    def stop(self):
        """停止哨兵服务"""
        if not self.is_running:
            logger.info("[哨兵服务] 服务未运行")
            return
        
        logger.info("[哨兵服务] 停止中...")
        self.is_running = False
        
        # 停止PL5系统进程
        if self.pl5_process is not None:
            try:
                if self.pl5_process.poll() is None:
                    logger.info(f"[哨兵服务] 停止PL5系统，PID={self.pl5_process.pid}")
                    self.pl5_process.terminate()
                    time.sleep(2)
                    if self.pl5_process.poll() is None:
                        self.pl5_process.kill()
                self.pl5_process = None
                self.status['pl5_pid'] = None
            except Exception as e:
                logger.error(f"[哨兵服务] 停止PL5系统失败: {e}")
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
        
        logger.info("[哨兵服务] 已停止")
    
    def _monitoring_loop(self):
        """监控主循环"""
        health_check_timer = 0
        performance_check_timer = 0
        
        while self.is_running:
            try:
                # 基本系统监控
                self._check_system_status()
                
                # 健康检查
                health_check_timer += self.config['monitor_interval']
                if health_check_timer >= self.config['health_check_interval']:
                    self._check_health()
                    health_check_timer = 0
                
                # 性能检查
                performance_check_timer += self.config['monitor_interval']
                if performance_check_timer >= self.config['performance_check_interval']:
                    self._check_performance()
                    performance_check_timer = 0
                
                # 检查是否需要恢复
                self._check_recovery_needed()
                
                # 保存状态
                self._save_status()
                
                # 等待下一次检查
                time.sleep(self.config['monitor_interval'])
                
            except Exception as e:
                logger.error(f"[哨兵服务] 监控循环异常: {e}")
                time.sleep(self.config['monitor_interval'])
    
    def _check_system_status(self):
        """检查系统状态"""
        try:
            # 先检查我们自己管理的进程
            if self.pl5_process is not None:
                if self.pl5_process.poll() is None:
                    # 进程还在运行
                    self.status['health_status'] = 'healthy'
                else:
                    # 进程已经退出了
                    alert = {
                        'level': 'CRITICAL',
                        'message': f"PL5系统进程已退出！PID={self.status['pl5_pid']}",
                        'timestamp': datetime.now().isoformat()
                    }
                    self._add_alert(alert)
                    self.status['health_status'] = 'critical'
                    self.pl5_process = None
                    self.status['pl5_pid'] = None
            else:
                # 没有管理进程，检查系统中是否有PL5进程
                system_status = self.system_monitor.check_system_status()
                system_running = system_status.get('system_running', False)
                
                if not system_running:
                    alert = {
                        'level': 'CRITICAL',
                        'message': "PL5系统未运行！",
                        'timestamp': datetime.now().isoformat()
                    }
                    self._add_alert(alert)
                    self.status['health_status'] = 'critical'
                else:
                    self.status['health_status'] = 'healthy'
            
            self.status['last_check'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"[哨兵服务] 检查系统状态失败: {e}")
    
    def _check_health(self):
        """健康检查"""
        try:
            health_status = self.system_checker.check_all()
            
            if health_status['overall'] != 'healthy':
                alert = {
                    'level': 'WARNING',
                    'message': f"系统健康状态异常: {health_status['overall']}",
                    'details': health_status,
                    'timestamp': datetime.now().isoformat()
                }
                self._add_alert(alert)
            
        except Exception as e:
            logger.error(f"[哨兵服务] 健康检查失败: {e}")
    
    def _check_performance(self):
        """性能检查"""
        try:
            performance_data = self.performance_monitor.get_metrics()
            
            # 检查CPU使用率
            cpu_usage = performance_data.get('cpu_usage', 0)
            if cpu_usage > self.config['alert_thresholds']['cpu_usage']:
                alert = {
                    'level': 'WARNING',
                    'message': f"CPU使用率过高: {cpu_usage}%",
                    'timestamp': datetime.now().isoformat()
                }
                self._add_alert(alert)
            
            # 检查内存使用率
            memory_usage = performance_data.get('memory_usage', 0)
            if memory_usage > self.config['alert_thresholds']['memory_usage']:
                alert = {
                    'level': 'WARNING',
                    'message': f"内存使用率过高: {memory_usage}%",
                    'timestamp': datetime.now().isoformat()
                }
                self._add_alert(alert)
            
            self.status['performance_status'] = 'healthy'
            
        except Exception as e:
            logger.error(f"[哨兵服务] 性能检查失败: {e}")
    
    def _check_recovery_needed(self):
        """检查是否需要恢复"""
        try:
            # 检查PL5进程是否运行
            system_status = self.system_monitor.check_system_status()
            system_running = system_status.get('system_running', False)
            
            if not system_running:
                logger.warning("[哨兵服务] 检测到PL5系统未运行，尝试恢复...")
                self._recover_pl5_system()
                
        except Exception as e:
            logger.error(f"[哨兵服务] 检查恢复需求失败: {e}")
    
    def _recover_pl5_system(self):
        """恢复PL5系统"""
        try:
            logger.info("[哨兵服务] 开始恢复PL5系统...")
            
            # 先清理旧的进程
            if self.pl5_process is not None:
                try:
                    if self.pl5_process.poll() is None:
                        self.pl5_process.terminate()
                        time.sleep(2)
                        if self.pl5_process.poll() is None:
                            self.pl5_process.kill()
                except:
                    pass
            
            # 启动PL5系统
            import subprocess
            pl5_path = Path('src/app/auto_scheduler_v8.py')
            if pl5_path.exists():
                # 使用pythonw在后台运行
                self.pl5_process = subprocess.Popen([
                    sys.executable, '-m', 'src.app.auto_scheduler_v8'
                ], cwd=os.getcwd(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
                
                # 保存PID
                self.status['pl5_pid'] = self.pl5_process.pid
                
                # 等待启动
                time.sleep(5)
                
                # 检查是否启动成功
                if self.pl5_process.poll() is None:
                    logger.info(f"[哨兵服务] PL5系统恢复成功！PID={self.pl5_process.pid}")
                    recovery_record = {
                        'action': 'restart_pl5',
                        'status': 'success',
                        'timestamp': datetime.now().isoformat(),
                        'pid': self.pl5_process.pid
                    }
                    self.status['recovery_history'].append(recovery_record)
                else:
                    logger.error("[哨兵服务] PL5系统恢复失败")
                    recovery_record = {
                        'action': 'restart_pl5',
                        'status': 'failed',
                        'timestamp': datetime.now().isoformat()
                    }
                    self.status['recovery_history'].append(recovery_record)
                    self.pl5_process = None
                    self.status['pl5_pid'] = None
            else:
                logger.error("[哨兵服务] 找不到PL5主程序")
                
        except Exception as e:
            logger.error(f"[哨兵服务] 恢复PL5系统失败: {e}")
            self.pl5_process = None
            self.status['pl5_pid'] = None
    
    def _add_alert(self, alert):
        """添加告警"""
        self.status['alerts'].append(alert)
        # 只保留最近100条告警
        self.status['alerts'] = self.status['alerts'][-100:]
        
        # 记录告警
        level = alert.get('level', 'INFO')
        message = alert.get('message', '')
        
        if level == 'CRITICAL':
            logger.critical(f"[告警] {message}")
        elif level == 'WARNING':
            logger.warning(f"[告警] {message}")
        else:
            logger.info(f"[告警] {message}")
    
    def _save_status(self):
        """保存状态"""
        try:
            status_file = self.log_dir / 'sentinel_status.json'
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(self.status, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"[哨兵服务] 保存状态失败: {e}")
    
    def get_status(self):
        """获取当前状态"""
        return self.status.copy()
    
    def get_alerts(self):
        """获取告警列表"""
        return self.status['alerts']
    
    def clear_alerts(self):
        """清空告警"""
        self.status['alerts'] = []
        self._save_status()


def main():
    """主函数"""
    sentinel = SentinelService()
    
    try:
        sentinel.start()
        logger.info("[哨兵服务] 按 Ctrl+C 停止服务")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("[哨兵服务] 收到停止信号")
    finally:
        sentinel.stop()


if __name__ == "__main__":
    main()