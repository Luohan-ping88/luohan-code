#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统健康检查和自诊断模块
实现系统的全面健康状态检测和诊断功能
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from src.core.utils.logger import setup_logging
from src.core.backup.backup_manager import get_latest_backup
from src.core.monitoring.performance_monitor import get_performance_monitor
from src.core.monitoring.alerting import get_alert_statistics
from src.core.recovery.failure_recovery import get_failure_stats

logger = setup_logging(__name__)


class HealthChecker:
    """系统健康检查器"""

    def __init__(self):
        """初始化健康检查器"""
        self.health_history: List[Dict[str, Any]] = []
        self.last_health_check = None

        # 健康检查项
        self.checks = {
            "system_resources": self._check_system_resources,
            "disk_space": self._check_disk_space,
            "backup_status": self._check_backup_status,
            "component_health": self._check_component_health,
            "error_status": self._check_error_status,
            "performance_status": self._check_performance_status,
        }

        logger.info("系统健康检查器初始化完成")

    def check_health(self) -> Dict[str, Any]:
        """执行健康检查

        Returns:
            健康检查结果
        """
        logger.info("[健康检查] 开始执行系统健康检查")

        health_result = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "checks": {},
            "details": {},
        }

        # 执行各项检查
        for check_name, check_func in self.checks.items():
            try:
                check_result = check_func()
                health_result["checks"][check_name] = check_result

                # 更新整体状态
                if check_result["status"] == "critical":
                    health_result["overall_status"] = "critical"
                elif (
                    check_result["status"] == "unhealthy"
                    and health_result["overall_status"] != "critical"
                ):
                    health_result["overall_status"] = "unhealthy"
                elif (
                    check_result["status"] == "warning"
                    and health_result["overall_status"] == "healthy"
                ):
                    health_result["overall_status"] = "warning"

            except Exception as e:
                logger.error(f"执行健康检查 {check_name} 失败: {str(e)}")
                health_result["checks"][check_name] = {
                    "status": "error",
                    "message": f"检查失败: {str(e)}",
                }
                health_result["overall_status"] = "unhealthy"

        # 收集系统整体信息
        health_result["details"]["system_info"] = self._get_system_info()
        health_result["details"]["resource_usage"] = self._get_resource_usage()
        health_result["details"]["alert_statistics"] = get_alert_statistics()
        health_result["details"]["failure_stats"] = get_failure_stats()

        # 保存健康检查历史
        self.health_history.append(health_result)
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]

        # 保存健康检查结果
        self._save_health_check(health_result)

        self.last_health_check = datetime.now()

        logger.info(
            f"[健康检查] 健康检查完成，状态: {health_result['overall_status']}"
        )
        return health_result

    def _check_system_resources(self) -> Dict[str, Any]:
        """检查系统资源"""
        try:
            monitor = get_performance_monitor()
            metrics = monitor.get_current_metrics()

            if "system" not in metrics:
                return {"status": "error", "message": "无法获取系统指标"}

            system_metrics = metrics["system"]

            # 检查CPU使用率
            cpu_percent = system_metrics.get("cpu_percent", 0)
            if cpu_percent > 90:
                cpu_status = "critical"
                cpu_message = f"CPU使用率过高: {cpu_percent}%"
            elif cpu_percent > 75:
                cpu_status = "warning"
                cpu_message = f"CPU使用率较高: {cpu_percent}%"
            else:
                cpu_status = "healthy"
                cpu_message = f"CPU使用率正常: {cpu_percent}%"

            # 检查内存使用率
            memory_percent = system_metrics.get("memory_percent", 0)
            if memory_percent > 85:
                memory_status = "critical"
                memory_message = f"内存使用率过高: {memory_percent}%"
            elif memory_percent > 70:
                memory_status = "warning"
                memory_message = f"内存使用率较高: {memory_percent}%"
            else:
                memory_status = "healthy"
                memory_message = f"内存使用率正常: {memory_percent}%"

            # 确定整体状态
            if cpu_status == "critical" or memory_status == "critical":
                overall_status = "critical"
            elif cpu_status == "warning" or memory_status == "warning":
                overall_status = "warning"
            else:
                overall_status = "healthy"

            return {
                "status": overall_status,
                "message": f"系统资源状态: {overall_status}",
                "details": {
                    "cpu": {
                        "status": cpu_status,
                        "message": cpu_message,
                        "value": cpu_percent,
                    },
                    "memory": {
                        "status": memory_status,
                        "message": memory_message,
                        "value": memory_percent,
                    },
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"检查系统资源失败: {str(e)}",
            }

    def _check_disk_space(self) -> Dict[str, Any]:
        """检查磁盘空间"""
        try:
            import platform

            system = platform.system()

            if system == "Windows":
                # Windows系统使用subprocess获取磁盘信息
                try:
                    import subprocess

                    result = subprocess.run(
                        ["fsutil", "volume", "diskfree", "C:"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        output = result.stdout
                        # 解析fsutil输出
                        lines = output.strip().split("\n")
                        total_bytes = 0
                        free_bytes = 0

                        for line in lines:
                            if "总字节数" in line:
                                total_bytes = int(
                                    line.split(":")[1]
                                    .strip()
                                    .split(" ")[0]
                                    .replace(",", "")
                                )
                            elif "可用字节总数" in line:
                                free_bytes = int(
                                    line.split(":")[1]
                                    .strip()
                                    .split(" ")[0]
                                    .replace(",", "")
                                )

                        if total_bytes > 0:
                            disk_percent = (1 - free_bytes / total_bytes) * 100
                            disk_used_gb = (
                                (total_bytes - free_bytes) / 1024 / 1024 / 1024
                            )
                            disk_total_gb = total_bytes / 1024 / 1024 / 1024
                            disk_path = "C:"

                            if disk_percent > 90:
                                status = "critical"
                                message = f"磁盘空间不足: {disk_percent:.1f}%"
                            elif disk_percent > 75:
                                status = "warning"
                                message = f"磁盘空间较低: {disk_percent:.1f}%"
                            else:
                                status = "healthy"
                                message = f"磁盘空间正常: {disk_percent:.1f}%"

                            return {
                                "status": status,
                                "message": message,
                                "details": {
                                    "percent": disk_percent,
                                    "used_gb": disk_used_gb,
                                    "total_gb": disk_total_gb,
                                    "path": disk_path,
                                },
                            }
                except Exception as subprocess_error:
                    logger.error(
                        f"使用subprocess获取磁盘信息失败: {subprocess_error}"
                    )

            # 尝试使用psutil获取磁盘信息
            try:
                import psutil

                # 根据操作系统类型选择磁盘路径
                if system == "Windows":
                    disk_path = "C:"
                else:
                    disk_path = "/"

                disk = psutil.disk_usage(disk_path)
                disk_percent = disk.percent

                if disk_percent > 90:
                    status = "critical"
                    message = f"磁盘空间不足: {disk_percent}%"
                elif disk_percent > 75:
                    status = "warning"
                    message = f"磁盘空间较低: {disk_percent}%"
                else:
                    status = "healthy"
                    message = f"磁盘空间正常: {disk_percent}%"

                return {
                    "status": status,
                    "message": message,
                    "details": {
                        "percent": disk_percent,
                        "used_gb": disk.used / 1024 / 1024 / 1024,
                        "total_gb": disk.total / 1024 / 1024 / 1024,
                        "path": disk_path,
                    },
                }

            except Exception as psutil_error:
                logger.error(f"使用psutil获取磁盘信息失败: {psutil_error}")

            return {"status": "error", "message": "无法获取磁盘空间信息"}

        except Exception as e:
            return {
                "status": "error",
                "message": f"检查磁盘空间失败: {str(e)}",
            }

    def _check_backup_status(self) -> Dict[str, Any]:
        """检查备份状态"""
        try:
            latest_backup = get_latest_backup()

            if not latest_backup:
                return {"status": "critical", "message": "未找到备份"}

            backup_time = datetime.fromisoformat(latest_backup["timestamp"])
            time_since_backup = (
                datetime.now() - backup_time
            ).total_seconds() / 3600  # 小时

            if time_since_backup > 24:
                status = "warning"
                message = f"备份时间过长: {time_since_backup:.1f}小时"
            else:
                status = "healthy"
                message = f"备份状态正常，上次备份: {backup_time.strftime('%Y-%m-%d %H:%M:%S')}"

            return {
                "status": status,
                "message": message,
                "details": {
                    "last_backup": latest_backup["timestamp"],
                    "time_since_backup_hours": time_since_backup,
                    "backup_id": latest_backup["backup_id"],
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"检查备份状态失败: {str(e)}",
            }

    def _check_component_health(self) -> Dict[str, Any]:
        """检查组件健康状态"""
        try:
            # 检查关键目录是否存在
            critical_dirs = [
                Path("models"),
                Path("data"),
                Path("config"),
                Path("logs"),
            ]

            missing_dirs = []
            for directory in critical_dirs:
                if not directory.exists():
                    missing_dirs.append(str(directory))

            if missing_dirs:
                return {
                    "status": "critical",
                    "message": f"缺少关键目录: {', '.join(missing_dirs)}",
                }

            # 检查模型文件是否存在
            model_files = list(Path("models").glob("*.pkl"))
            if not model_files:
                return {"status": "warning", "message": "未找到模型文件"}

            return {
                "status": "healthy",
                "message": "组件状态正常",
                "details": {
                    "model_files_count": len(model_files),
                    "critical_dirs_exist": len(missing_dirs) == 0,
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"检查组件健康状态失败: {str(e)}",
            }

    def _check_error_status(self) -> Dict[str, Any]:
        """检查错误状态"""
        try:
            failure_stats = get_failure_stats()
            alert_stats = get_alert_statistics()

            # 检查最近的错误
            failure_count = failure_stats.get("failure_count", 0)
            active_alerts = alert_stats.get("active_alerts", 0)
            critical_alerts = alert_stats.get("alerts_by_level", {}).get(
                "critical", 0
            )

            if critical_alerts > 0:
                status = "critical"
                message = f"存在 {critical_alerts} 个严重告警"
            elif active_alerts > 3:
                status = "warning"
                message = f"存在 {active_alerts} 个活跃告警"
            elif failure_count > 5:
                status = "warning"
                message = f"最近发生 {failure_count} 次故障"
            else:
                status = "healthy"
                message = "错误状态正常"

            return {
                "status": status,
                "message": message,
                "details": {
                    "failure_count": failure_count,
                    "active_alerts": active_alerts,
                    "critical_alerts": critical_alerts,
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"检查错误状态失败: {str(e)}",
            }

    def _check_performance_status(self) -> Dict[str, Any]:
        """检查性能状态"""
        try:
            monitor = get_performance_monitor()
            summary = monitor.get_performance_summary()

            if not summary:
                return {"status": "warning", "message": "性能数据不足"}

            cpu_avg = summary.get("cpu", {}).get("avg", 0)
            memory_avg = summary.get("memory", {}).get("avg", 0)

            if cpu_avg > 80 or memory_avg > 80:
                status = "warning"
                message = f"系统性能负载较高 (CPU: {cpu_avg:.1f}%, 内存: {memory_avg:.1f}%)"
            else:
                status = "healthy"
                message = f"系统性能状态正常 (CPU: {cpu_avg:.1f}%, 内存: {memory_avg:.1f}%)"

            return {"status": status, "message": message, "details": summary}

        except Exception as e:
            return {
                "status": "error",
                "message": f"检查性能状态失败: {str(e)}",
            }

    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            import platform
            import psutil

            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "processor": platform.processor(),
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "cpu_count": psutil.cpu_count(logical=True),
                "cpu_count_physical": psutil.cpu_count(logical=False),
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_resource_usage(self) -> Dict[str, Any]:
        """获取资源使用情况"""
        try:
            import platform

            system = platform.system()

            resource_usage = {
                "cpu_percent": 0,
                "memory": {"percent": 0, "used_mb": 0, "total_mb": 0},
                "disk": {
                    "percent": 0,
                    "used_gb": 0,
                    "total_gb": 0,
                    "path": "",
                },
            }

            # 尝试使用psutil获取资源使用情况
            try:
                import psutil

                # 根据操作系统类型选择磁盘路径
                if system == "Windows":
                    disk_path = "C:"
                else:
                    disk_path = "/"

                resource_usage["cpu_percent"] = psutil.cpu_percent(
                    interval=0.1
                )
                memory = psutil.virtual_memory()
                resource_usage["memory"]["percent"] = memory.percent
                resource_usage["memory"]["used_mb"] = memory.used / 1024 / 1024
                resource_usage["memory"]["total_mb"] = (
                    memory.total / 1024 / 1024
                )

                disk = psutil.disk_usage(disk_path)
                resource_usage["disk"]["percent"] = disk.percent
                resource_usage["disk"]["used_gb"] = (
                    disk.used / 1024 / 1024 / 1024
                )
                resource_usage["disk"]["total_gb"] = (
                    disk.total / 1024 / 1024 / 1024
                )
                resource_usage["disk"]["path"] = disk_path

            except Exception as psutil_error:
                logger.warning(
                    f"使用psutil获取资源使用情况失败，尝试备用方法: {psutil_error}"
                )

                # 备用方法：使用ctypes和subprocess
                if system == "Windows":
                    # 使用ctypes获取内存信息
                    try:
                        import ctypes

                        class MEMORYSTATUSEX(ctypes.Structure):
                            _fields_ = [
                                ("dwLength", ctypes.c_ulong),
                                ("dwMemoryLoad", ctypes.c_ulong),
                                ("ullTotalPhys", ctypes.c_ulonglong),
                                ("ullAvailPhys", ctypes.c_ulonglong),
                                ("ullTotalPageFile", ctypes.c_ulonglong),
                                ("ullAvailPageFile", ctypes.c_ulonglong),
                                ("ullTotalVirtual", ctypes.c_ulonglong),
                                ("ullAvailVirtual", ctypes.c_ulonglong),
                                (
                                    "sullAvailExtendedVirtual",
                                    ctypes.c_ulonglong,
                                ),
                            ]

                        memory_status = MEMORYSTATUSEX()
                        memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                        ctypes.windll.kernel32.GlobalMemoryStatusEx(
                            ctypes.byref(memory_status)
                        )

                        resource_usage["memory"][
                            "percent"
                        ] = memory_status.dwMemoryLoad
                        resource_usage["memory"]["used_mb"] = (
                            (
                                memory_status.ullTotalPhys
                                - memory_status.ullAvailPhys
                            )
                            / 1024
                            / 1024
                        )
                        resource_usage["memory"]["total_mb"] = (
                            memory_status.ullTotalPhys / 1024 / 1024
                        )

                    except Exception as ctypes_error:
                        logger.error(
                            f"使用ctypes获取内存信息失败: {ctypes_error}"
                        )

                    # 使用subprocess获取磁盘信息
                    try:
                        import subprocess

                        result = subprocess.run(
                            ["fsutil", "volume", "diskfree", "C:"],
                            capture_output=True,
                            text=True,
                        )
                        if result.returncode == 0:
                            output = result.stdout
                            # 解析fsutil输出
                            lines = output.strip().split("\n")
                            total_bytes = 0
                            free_bytes = 0

                            for line in lines:
                                if "总字节数" in line:
                                    total_bytes = int(
                                        line.split(":")[1]
                                        .strip()
                                        .split(" ")[0]
                                        .replace(",", "")
                                    )
                                elif "可用字节总数" in line:
                                    free_bytes = int(
                                        line.split(":")[1]
                                        .strip()
                                        .split(" ")[0]
                                        .replace(",", "")
                                    )

                            if total_bytes > 0:
                                resource_usage["disk"]["percent"] = (
                                    1 - free_bytes / total_bytes
                                ) * 100
                                resource_usage["disk"]["used_gb"] = (
                                    (total_bytes - free_bytes)
                                    / 1024
                                    / 1024
                                    / 1024
                                )
                                resource_usage["disk"]["total_gb"] = (
                                    total_bytes / 1024 / 1024 / 1024
                                )
                                resource_usage["disk"]["path"] = "C:"
                    except Exception as subprocess_error:
                        logger.error(
                            f"使用subprocess获取磁盘信息失败: {subprocess_error}"
                        )

            return resource_usage
        except Exception as e:
            return {"error": str(e)}

    def _save_health_check(self, health_result: Dict[str, Any]):
        """保存健康检查结果"""
        try:
            health_dir = Path("health")
            health_dir.mkdir(parents=True, exist_ok=True)

            filename = (
                health_dir
                / f"health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(health_result, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存健康检查结果失败: {str(e)}")

    def get_health_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取健康检查历史"""
        return self.health_history[-limit:]

    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康状态摘要"""
        if not self.health_history:
            return {"status": "unknown", "message": "暂无健康检查数据"}

        latest_health = self.health_history[-1]
        return {
            "status": latest_health["overall_status"],
            "last_check": latest_health["timestamp"],
            "message": f"系统状态: {latest_health['overall_status']}",
            "checks": {
                k: v["status"] for k, v in latest_health["checks"].items()
            },
        }


# 全局健康检查器实例
_global_health_checker = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器实例"""
    global _global_health_checker
    if _global_health_checker is None:
        _global_health_checker = HealthChecker()
    return _global_health_checker


def check_health() -> Dict[str, Any]:
    """执行健康检查"""
    checker = get_health_checker()
    return checker.check_health()


def get_health_summary() -> Dict[str, Any]:
    """获取健康状态摘要"""
    checker = get_health_checker()
    return checker.get_health_summary()


def get_health_history(limit: int = 10) -> List[Dict[str, Any]]:
    """获取健康检查历史"""
    checker = get_health_checker()
    return checker.get_health_history(limit)
