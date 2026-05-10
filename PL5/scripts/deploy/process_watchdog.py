#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PL5 进程监控守护程序
自动监控主进程，崩溃时自动重启
【修复V3.0】使用严格的三重匹配规则，避免误杀外部Python进程
"""

import os
import sys
import time
import subprocess
import psutil
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 配置日志
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "watchdog.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PL5_Watchdog")

# PL5项目根目录路径（用于精确匹配，避免误杀其他项目）
PL5_PROJECT_PATHS = [
    '\\PL5\\',
    '/PL5/',
    'E:\\PL5',
    'D:\\PL5',
]

# PL5特定标识符（更具体，避免通用词误匹配）
PL5_SPECIFIC_IDENTIFIERS = [
    'auto_scheduler_v8',
    'process_watchdog',
    'prevent_sleep',
    'pl5_intelligent_system',
    'start_system',
    'start_sentinel',
    'launch_simple',
    'src.app.auto_scheduler_v8',
]


def _is_in_pl5_project(cmdline_str: str) -> bool:
    """检查命令行是否在PL5项目目录下"""
    if not cmdline_str:
        return False
    return any(path.lower() in cmdline_str.lower() for path in PL5_PROJECT_PATHS)


def _check_module_mode(cmdline_str: str) -> bool:
    """检查是否是模块方式启动的PL5进程"""
    if not cmdline_str:
        return False
    cmdline_lower = cmdline_str.lower()
    if 'src.app.auto_scheduler_v8' in cmdline_lower and 'python' in cmdline_lower:
        return True
    return False


def _is_pl5_process_strict(cmdline_str: str, process_name: str) -> bool:
    """
    严格检查进程是否属于PL5系统【V3.1修复】

    匹配规则（必须同时满足）：
    1. 是Python进程（包含python或pythonw）
    2. 包含至少一个PL5特定标识符
    3. 在PL5项目目录下运行 OR 使用PL5模块方式启动

    Args:
        cmdline_str: 命令行字符串
        process_name: 进程名

    Returns:
        bool: 是否属于PL5系统进程
    """
    if not cmdline_str:
        return False

    cmdline_str_lower = cmdline_str.lower()

    # 规则1：必须是Python进程
    is_python = 'python' in process_name.lower() if process_name else False
    if not is_python:
        return False

    # 规则2：必须包含至少一个PL5特定标识符
    has_pl5_id = any(pid in cmdline_str_lower for pid in PL5_SPECIFIC_IDENTIFIERS)
    if not has_pl5_id:
        return False

    # 规则3：在PL5项目目录下 OR 使用模块方式启动
    has_pl5_path = _is_in_pl5_project(cmdline_str_lower)
    has_module_mode = _check_module_mode(cmdline_str_lower)
    return has_pl5_path or has_module_mode


# 配置
WATCHDOG_CONFIG = {
    "main_process": "auto_scheduler_v8",
    "check_interval": 30,  # 秒
    "max_restarts": 10,
    "restart_cooldown": 60,  # 秒
    "prevent_sleep": True
}


class ProcessWatchdog:
    """进程监控器"""

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.config_file = self.project_root / "config" / "watchdog_config.json"
        self.status_file = LOG_DIR / "watchdog_status.json"
        self.restart_count = 0
        self.last_restart_time = 0
        self.load_config()

    def load_config(self):
        """加载配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    WATCHDOG_CONFIG.update(config)
                logger.info("配置加载成功")
            except Exception as e:
                logger.warning(f"加载配置失败: {e}，使用默认配置")

    def save_status(self):
        """保存状态"""
        status = {
            "restart_count": self.restart_count,
            "last_restart_time": self.last_restart_time,
            "last_check": datetime.now().isoformat(),
            "status": "running"
        }
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"保存状态失败: {e}")

    def find_pythonw(self):
        """查找pythonw.exe"""
        import shutil
        pythonw = shutil.which("pythonw")
        if pythonw:
            return pythonw

        # 尝试从python.exe推断
        python = shutil.which("python")
        if python:
            python_dir = os.path.dirname(python)
            pythonw = os.path.join(python_dir, "pythonw.exe")
            if os.path.exists(pythonw):
                return pythonw

        return sys.executable.replace("python.exe", "pythonw.exe")

    def is_process_running(self):
        """检查主进程是否在运行【V3.0修复】使用严格匹配"""
        main_script = WATCHDOG_CONFIG["main_process"]

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline'] or []
                cmdline_str = ' '.join(cmdline)
                process_name = proc.info['name'] or ''

                if _is_pl5_process_strict(cmdline_str, process_name):
                    # 额外检查是否匹配主脚本标识
                    if main_script in cmdline_str or 'auto_scheduler_v8' in cmdline_str:
                        return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return None

    def start_main_process(self):
        """启动主进程【V3.0修复】使用模块方式启动"""
        logger.info("正在启动主进程...")

        pythonw = self.find_pythonw()
        main_module = "src.app.auto_scheduler_v8"  # 【修复】使用模块方式

        # 启动防睡眠
        if WATCHDOG_CONFIG["prevent_sleep"]:
            sleep_script = self.project_root / "monitor" / "prevent_sleep.py"
            if sleep_script.exists():
                try:
                    subprocess.Popen(
                        [pythonw, str(sleep_script)],
                        cwd=str(self.project_root),
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    logger.info("防睡眠进程已启动")
                except Exception as e:
                    logger.warning(f"启动防睡眠失败: {e}")

        # 启动主调度器（使用模块方式）【修复】
        try:
            process = subprocess.Popen(
                [pythonw, "-m", main_module],
                cwd=str(self.project_root),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logger.info(f"主进程已启动，PID: {process.pid}")
            return process.pid
        except Exception as e:
            logger.error(f"启动主进程失败: {e}")
            return None

    def check_and_restart(self):
        """检查并重启"""
        pid = self.is_process_running()

        if pid:
            logger.debug(f"主进程运行中，PID: {pid}")
            return True

        # 检查是否超过重启限制
        current_time = time.time()
        if (current_time - self.last_restart_time) < WATCHDOG_CONFIG["restart_cooldown"]:
            logger.warning("重启冷却中，跳过本次重启")
            return False

        if self.restart_count >= WATCHDOG_CONFIG["max_restarts"]:
            logger.error(f"已达到最大重启次数 ({WATCHDOG_CONFIG['max_restarts']})，停止重启")
            return False

        # 执行重启
        logger.warning("主进程未运行，执行重启...")
        self.restart_count += 1
        self.last_restart_time = current_time

        new_pid = self.start_main_process()
        if new_pid:
            logger.info(f"重启成功 (第 {self.restart_count} 次)")
            self.save_status()
            return True
        else:
            logger.error("重启失败")
            return False

    def run(self):
        """运行监控循环"""
        logger.info("=" * 60)
        logger.info("PL5 进程监控守护程序启动")
        logger.info("【V3.0修复】严格匹配PL5进程，避免误杀外部Python进程")
        logger.info(f"检查间隔: {WATCHDOG_CONFIG['check_interval']}秒")
        logger.info(f"最大重启次数: {WATCHDOG_CONFIG['max_restarts']}")
        logger.info("=" * 60)

        # 首次检查，确保进程在运行
        self.check_and_restart()

        try:
            while True:
                self.check_and_restart()
                self.save_status()
                time.sleep(WATCHDOG_CONFIG["check_interval"])
        except KeyboardInterrupt:
            logger.info("监控程序被用户中断")
        except Exception as e:
            logger.error(f"监控程序异常: {e}", exc_info=True)


def main():
    watchdog = ProcessWatchdog()
    watchdog.run()


if __name__ == "__main__":
    main()
