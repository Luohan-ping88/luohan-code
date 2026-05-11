"""
进程保护守护模块 V2.0
确保系统进程持续运行，定时任务正常执行
【修复】精确匹配PL5系统进程，避免误杀外部Python进程
"""

import os
import sys
import time
import psutil
import subprocess
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from threading import Thread, Event

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ProcessGuardian")

# PL5系统进程标识关键字（用于精确匹配）
# 【修复V3.0】使用更严格的组合匹配，避免误杀外部Python进程
# 规则：必须包含 python 关键字 + 至少一个 PL5 特定标识符
PL5_PROCESS_IDENTIFIERS = [
    "auto_scheduler_v8",
    "process_watchdog",
    "prevent_sleep",
    "pl5_intelligent_system",
    "start_system",
    "start_sentinel",
    "launch_simple",
    "src.app.auto_scheduler_v8",
]

# PL5项目根目录路径（用于精确匹配，避免误杀其他项目）
PL5_PROJECT_PATHS = [
    "\\PL5\\",
    "/PL5/",
    "E:\\PL5",
    "D:\\PL5",
]


def _is_in_pl5_project(cmdline_str: str) -> bool:
    """检查命令行是否在PL5项目目录下（避免误杀其他项目）"""
    if not cmdline_str:
        return False
    return any(path.lower() in cmdline_str.lower() for path in PL5_PROJECT_PATHS)


def _check_module_mode(cmdline_str: str) -> bool:
    """检查是否是模块方式启动的PL5进程【V3.1修复】"""
    if not cmdline_str:
        return False
    cmdline_lower = cmdline_str.lower()
    # 模块方式启动：pythonw.exe -m src.app.auto_scheduler_v8
    if "src.app.auto_scheduler_v8" in cmdline_lower and "python" in cmdline_lower:
        return True
    return False


def _is_pl5_process_strict(cmdline: list) -> bool:
    """
    严格检查进程是否属于PL5系统（避免误杀）【V3.1修复】

    匹配规则（必须同时满足）：
    1. 是Python进程（包含python或pythonw）
    2. 包含至少一个PL5特定标识符
    3. 在PL5项目目录下运行 OR 使用PL5模块方式启动

    Args:
        cmdline: 进程命令行参数列表

    Returns:
        bool: 是否属于PL5系统进程
    """
    if not cmdline:
        return False

    cmdline_str = " ".join(cmdline).lower()

    # 规则1：必须是Python进程
    is_python = "python" in cmdline_str
    if not is_python:
        return False

    # 规则2：必须包含至少一个PL5特定标识符
    has_pl5_identifier = any(pid in cmdline_str for pid in PL5_PROCESS_IDENTIFIERS)
    if not has_pl5_identifier:
        return False

    # 规则3：在PL5项目目录下 OR 使用模块方式启动【V3.1修复】
    has_pl5_path = _is_in_pl5_project(cmdline_str)
    has_module_mode = _check_module_mode(cmdline_str)
    return has_pl5_path or has_module_mode


class ProcessGuardian:
    """
    进程保护守护类 V2.0

    功能：
    1. 监控主进程状态（精确匹配PL5系统进程）
    2. 自动重启崩溃的进程
    3. 确保定时任务按时执行
    4. 记录进程健康状态

    修复：
    - 使用多个标识符精确匹配PL5进程，避免误杀外部Python进程
    - 停止进程时只终止属于PL5系统的进程
    """

    def __init__(self, config_path: str = None):
        self.config_path = config_path or Path(__file__).parent.parent.parent / "config" / "guardian_config.json"
        self.config = self._load_config()
        self.stop_event = Event()
        self.main_process = None
        self.restart_count = 0
        self.max_restarts = self.config.get("max_restarts", 5)
        self.restart_window = self.config.get("restart_window", 3600)  # 1小时
        self.restart_history = []

    def _load_config(self) -> dict:
        """加载配置"""
        default_config = {
            "enabled": True,
            "check_interval": 30,
            "max_restarts": 5,
            "restart_window": 3600,
            "main_script": "pl5_intelligent_system.py",
            "service_script": "scripts/service.py",
            "auto_start": True,
            "health_check": {"enabled": True, "cpu_threshold": 90, "memory_threshold": 90, "disk_threshold": 95},
        }

        if Path(self.config_path).exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    default_config.update(config)
            except Exception as e:
                logger.error(f"加载配置失败: {e}")

        return default_config

    def _save_config(self):
        """保存配置"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def _is_pl5_process(self, cmdline: list) -> bool:
        """
        检查命令行是否属于PL5系统进程

        Args:
            cmdline: 进程命令行参数列表

        Returns:
            bool: 是否属于PL5系统进程
        """
        return _is_pl5_process_strict(cmdline)

    def is_process_running(self, process_name: str = None) -> bool:
        """检查PL5主进程是否运行（精确匹配）"""
        process_name = process_name or self.config.get("main_script", "pl5_intelligent_system.py")

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info["cmdline"] or []
                if self._is_pl5_process(cmdline):
                    # 额外检查是否匹配特定的主脚本
                    cmdline_str = " ".join(cmdline)
                    if process_name in cmdline_str:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def get_process_info(self) -> dict:
        """获取PL5主进程信息（精确匹配）"""
        process_name = self.config.get("main_script", "pl5_intelligent_system.py")

        for proc in psutil.process_iter(["pid", "name", "cmdline", "cpu_percent", "memory_percent"]):
            try:
                cmdline = proc.info["cmdline"] or []
                if self._is_pl5_process(cmdline):
                    cmdline_str = " ".join(cmdline)
                    if process_name in cmdline_str:
                        return {
                            "pid": proc.info["pid"],
                            "cpu_percent": proc.info["cpu_percent"],
                            "memory_percent": proc.info["memory_percent"],
                            "status": "running",
                        }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return {"status": "not_running"}

    def get_all_pl5_processes(self) -> list:
        """获取所有PL5相关的进程列表"""
        pl5_processes = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info["cmdline"] or []
                if self._is_pl5_process(cmdline):
                    pl5_processes.append({"pid": proc.info["pid"], "cmdline": " ".join(cmdline)[:200]})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return pl5_processes

    def _can_restart(self) -> bool:
        """检查是否允许重启（防止无限重启）"""
        now = datetime.now()
        # 清理过期的重启记录
        self.restart_history = [t for t in self.restart_history if now - t < timedelta(seconds=self.restart_window)]

        if len(self.restart_history) >= self.max_restarts:
            logger.error(f"重启次数过多 ({len(self.restart_history)}次/{self.restart_window}秒)，停止重启")
            return False

        return True

    def start_main_process(self) -> subprocess.Popen:
        """启动主进程"""
        if not self._can_restart():
            logger.error("无法重启主进程，已达到最大重启次数")
            return None

        try:
            main_script = self.config.get("main_script", "pl5_intelligent_system.py")
            base_dir = Path(__file__).parent.parent.parent
            script_path = base_dir / main_script

            logger.info(f"启动主进程: {script_path}")

            # 使用 subprocess 启动进程
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(base_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )

            self.restart_history.append(datetime.now())
            self.restart_count += 1

            logger.info(f"主进程已启动，PID: {process.pid}")
            return process

        except Exception as e:
            logger.error(f"启动主进程失败: {e}")
            return None

    def stop_main_process(self):
        """停止主进程（只停止PL5系统进程）"""
        if self.main_process and self.main_process.poll() is None:
            try:
                logger.info("停止主进程...")
                self.main_process.terminate()
                self.main_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("主进程未响应，强制终止")
                self.main_process.kill()
            except Exception as e:
                logger.error(f"停止主进程失败: {e}")

    def stop_all_pl5_processes(self):
        """停止所有PL5相关进程（安全停止，不杀外部Python进程）"""
        logger.info("正在停止所有PL5相关进程...")
        pl5_processes = self.get_all_pl5_processes()

        if not pl5_processes:
            logger.info("未发现PL5相关进程")
            return

        for proc_info in pl5_processes:
            try:
                pid = proc_info["pid"]
                proc = psutil.Process(pid)
                logger.info(f"  终止PL5进程 PID={pid}: {proc_info['cmdline'][:80]}...")
                proc.terminate()

                # 等待进程终止
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    logger.warning(f"  进程 {pid} 未响应，强制终止")
                    proc.kill()

            except psutil.NoSuchProcess:
                logger.debug(f"  进程 {pid} 已不存在")
            except Exception as e:
                logger.error(f"  终止进程 {pid} 失败: {e}")

        logger.info("PL5进程清理完成")

    def health_check(self) -> dict:
        """健康检查"""
        result = {"timestamp": datetime.now().isoformat(), "status": "healthy", "issues": []}

        # 检查进程状态
        if not self.is_process_running():
            result["status"] = "critical"
            result["issues"].append("主进程未运行")
            return result

        # 获取进程信息
        proc_info = self.get_process_info()

        # 检查资源使用
        health_config = self.config.get("health_check", {})

        if health_config.get("enabled", True):
            cpu_threshold = health_config.get("cpu_threshold", 90)
            memory_threshold = health_config.get("memory_threshold", 90)

            if proc_info.get("cpu_percent", 0) > cpu_threshold:
                result["issues"].append(f"CPU使用率过高: {proc_info['cpu_percent']:.1f}%")

            if proc_info.get("memory_percent", 0) > memory_threshold:
                result["issues"].append(f"内存使用率过高: {proc_info['memory_percent']:.1f}%")

        if result["issues"]:
            result["status"] = "warning"

        return result

    def run(self):
        """运行守护进程"""
        logger.info("=" * 80)
        logger.info("进程保护守护 V2.0 启动")
        logger.info("【修复】精确匹配PL5系统进程，避免误杀外部Python进程")
        logger.info("=" * 80)

        if not self.config.get("enabled", True):
            logger.info("守护进程已禁用")
            return

        check_interval = self.config.get("check_interval", 30)

        # 启动时如果配置了自动启动，则启动主进程
        if self.config.get("auto_start", True) and not self.is_process_running():
            logger.info("自动启动主进程")
            self.main_process = self.start_main_process()

        while not self.stop_event.is_set():
            try:
                # 健康检查
                health = self.health_check()

                if health["status"] == "critical":
                    logger.error("健康检查失败，尝试重启主进程")
                    self.stop_main_process()
                    time.sleep(2)
                    self.main_process = self.start_main_process()

                elif health["status"] == "warning":
                    logger.warning(f"健康检查警告: {health['issues']}")

                else:
                    logger.debug("健康检查通过")

                # 等待下一次检查
                self.stop_event.wait(check_interval)

            except Exception as e:
                logger.error(f"守护进程异常: {e}")
                time.sleep(5)

        logger.info("守护进程停止")
        self.stop_main_process()

    def stop(self):
        """停止守护进程"""
        logger.info("收到停止信号")
        self.stop_event.set()


def start_guardian_daemon():
    """启动守护进程（后台运行）"""
    guardian = ProcessGuardian()

    # 创建守护线程
    guardian_thread = Thread(target=guardian.run, daemon=True)
    guardian_thread.start()

    return guardian


if __name__ == "__main__":
    # 直接运行守护进程
    guardian = ProcessGuardian()

    try:
        guardian.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
        guardian.stop()
