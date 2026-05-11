#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控模块
实现系统性能数据的实时收集、分析和可视化
"""

import time
import psutil
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import threading
import queue
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.core.utils.logger import setup_logging

logger = setup_logging(__name__)


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, log_interval: int = 60, data_dir: Optional[Path] = None):
        """初始化性能监控器"""
        self.log_interval = log_interval  # 日志记录间隔（秒）
        self.data_dir = data_dir or Path("logs") / "performance"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.is_running = False
        self.monitor_thread = None
        self.data_queue = queue.Queue()
        self.performance_history = []
        self.baseline_metrics = {}
        self.peak_metrics = {}
        self.anomaly_history = []

        # 性能告警阈值
        self.thresholds = {"cpu_percent": 80, "memory_percent": 85, "disk_percent": 90}

        # 告警配置
        self.alert_config = {
            "enabled": True,
            "email": {
                "enabled": False,
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "from_email": "alerts@example.com",
                "to_emails": ["admin@example.com"],
            },
            "webhook": {"enabled": False, "url": ""},
            "callbacks": [],
        }

        # 告警历史
        self.alert_history = []

        logger.info("性能监控器初始化完成")

    def start(self):
        """启动性能监控"""
        if not self.is_running:
            self.is_running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("性能监控已启动")

    def stop(self):
        """停止性能监控"""
        if self.is_running:
            self.is_running = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            logger.info("性能监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        counter = 0
        while self.is_running:
            metrics = self.collect_metrics()
            self.data_queue.put(metrics)
            self.performance_history.append(metrics)

            # 限制历史数据长度
            if len(self.performance_history) > 1000:
                self.performance_history = self.performance_history[-1000:]

            # 定期保存数据
            if len(self.performance_history) % 10 == 0:
                self.save_metrics(metrics)

            # 定期检测异常
            if len(self.performance_history) % 5 == 0:
                anomalies = self.detect_anomalies()
                if anomalies:
                    logger.warning(f"检测到性能异常: {anomalies}")

            # 定期建立/更新基线
            if counter == 0 and len(self.performance_history) >= 30:
                self.establish_baseline()
            elif counter % 3600 == 0:  # 每小时更新一次基线
                self.update_baseline()

            counter += 1
            time.sleep(self.log_interval)

    def collect_metrics(self) -> Dict[str, Any]:
        """收集性能指标"""
        try:
            import platform

            system = platform.system()

            # 初始化指标字典
            metrics = {"timestamp": datetime.now().isoformat(), "system": {}, "process": {}}

            # 尝试使用psutil获取指标
            try:
                # 系统级指标
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()

                # 根据操作系统类型选择磁盘路径
                if system == "Windows":
                    disk_path = "C:"
                else:
                    disk_path = "/"
                disk = psutil.disk_usage(disk_path)

                network = psutil.net_io_counters()

                # 进程级指标
                process = psutil.Process()
                process_memory = process.memory_info()
                process_cpu = process.cpu_percent(interval=0.1)

                metrics["system"] = {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_mb": memory.used / 1024 / 1024,
                    "memory_total_mb": memory.total / 1024 / 1024,
                    "disk_percent": disk.percent,
                    "disk_used_gb": disk.used / 1024 / 1024 / 1024,
                    "disk_total_gb": disk.total / 1024 / 1024 / 1024,
                    "network_sent_mb": network.bytes_sent / 1024 / 1024,
                    "network_recv_mb": network.bytes_recv / 1024 / 1024,
                }

                metrics["process"] = {
                    "cpu_percent": process_cpu,
                    "memory_mb": process_memory.rss / 1024 / 1024,
                    "memory_percent": process.memory_percent(),
                    "threads": process.num_threads(),
                    "open_files": len(process.open_files()) if hasattr(process, "open_files") else 0,
                }

            except Exception as psutil_error:
                logger.warning(f"使用psutil获取指标失败，尝试备用方法: {psutil_error}")

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
                                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                            ]

                        memory_status = MEMORYSTATUSEX()
                        memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))

                        metrics["system"]["memory_percent"] = memory_status.dwMemoryLoad
                        metrics["system"]["memory_used_mb"] = (
                            (memory_status.ullTotalPhys - memory_status.ullAvailPhys) / 1024 / 1024
                        )
                        metrics["system"]["memory_total_mb"] = memory_status.ullTotalPhys / 1024 / 1024

                    except Exception as ctypes_error:
                        logger.error(f"使用ctypes获取内存信息失败: {ctypes_error}")

                    # 使用subprocess获取磁盘信息
                    try:
                        import subprocess

                        result = subprocess.run(["fsutil", "volume", "diskfree", "C:"], capture_output=True, text=True)
                        if result.returncode == 0:
                            output = result.stdout
                            # 解析fsutil输出
                            lines = output.strip().split("\n")
                            total_bytes = 0
                            free_bytes = 0
                            for line in lines:
                                if "总字节数" in line:
                                    total_bytes = int(line.split(":")[1].strip().split(" ")[0].replace(",", ""))
                                    metrics["system"]["disk_total_gb"] = total_bytes / 1024 / 1024 / 1024
                                elif "可用字节总数" in line:
                                    free_bytes = int(line.split(":")[1].strip().split(" ")[0].replace(",", ""))
                                    if total_bytes > 0:
                                        metrics["system"]["disk_used_gb"] = (
                                            (total_bytes - free_bytes) / 1024 / 1024 / 1024
                                        )
                                        metrics["system"]["disk_percent"] = (1 - free_bytes / total_bytes) * 100
                    except Exception as subprocess_error:
                        logger.error(f"使用subprocess获取磁盘信息失败: {subprocess_error}")

                    # 简单的CPU使用率估算
                    metrics["system"]["cpu_percent"] = 0  # 暂时设为0
                    metrics["system"]["network_sent_mb"] = 0
                    metrics["system"]["network_recv_mb"] = 0

                    # 进程信息
                    metrics["process"]["cpu_percent"] = 0
                    metrics["process"]["memory_mb"] = 0
                    metrics["process"]["memory_percent"] = 0
                    metrics["process"]["threads"] = 0
                    metrics["process"]["open_files"] = 0

            return metrics

        except Exception as e:
            logger.error(f"收集性能指标失败: {str(e)}")
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}

    def save_metrics(self, metrics: Dict[str, Any]):
        """保存性能指标到文件"""
        try:
            filename = self.data_dir / f"performance_{datetime.now().strftime('%Y%m%d')}.jsonl"
            with open(filename, "a", encoding="utf-8") as f:
                json.dump(metrics, f, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            logger.error(f"保存性能指标失败: {str(e)}")

    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前性能指标"""
        return self.collect_metrics()

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取历史性能指标"""
        return self.performance_history[-limit:]

    def establish_baseline(self):
        """建立性能基线"""
        if len(self.performance_history) < 30:
            logger.warning("性能数据不足，无法建立基线")
            return

        # 计算基线值
        recent_metrics = self.performance_history[-30:]

        cpu_values = [
            m["system"]["cpu_percent"] for m in recent_metrics if "system" in m and "cpu_percent" in m["system"]
        ]
        memory_values = [
            m["system"]["memory_percent"] for m in recent_metrics if "system" in m and "memory_percent" in m["system"]
        ]
        disk_values = [
            m["system"]["disk_percent"] for m in recent_metrics if "system" in m and "disk_percent" in m["system"]
        ]

        if cpu_values:
            self.baseline_metrics["cpu_percent"] = sum(cpu_values) / len(cpu_values)
        if memory_values:
            self.baseline_metrics["memory_percent"] = sum(memory_values) / len(memory_values)
        if disk_values:
            self.baseline_metrics["disk_percent"] = sum(disk_values) / len(disk_values)

        logger.info(f"性能基线已建立: {self.baseline_metrics}")

    def update_baseline(self):
        """更新性能基线"""
        if len(self.performance_history) < 60:
            logger.warning("性能数据不足，无法更新基线")
            return

        # 使用最近60个数据点更新基线
        recent_metrics = self.performance_history[-60:]

        cpu_values = [
            m["system"]["cpu_percent"] for m in recent_metrics if "system" in m and "cpu_percent" in m["system"]
        ]
        memory_values = [
            m["system"]["memory_percent"] for m in recent_metrics if "system" in m and "memory_percent" in m["system"]
        ]
        disk_values = [
            m["system"]["disk_percent"] for m in recent_metrics if "system" in m and "disk_percent" in m["system"]
        ]

        if cpu_values:
            self.baseline_metrics["cpu_percent"] = sum(cpu_values) / len(cpu_values)
        if memory_values:
            self.baseline_metrics["memory_percent"] = sum(memory_values) / len(memory_values)
        if disk_values:
            self.baseline_metrics["disk_percent"] = sum(disk_values) / len(disk_values)

        logger.info(f"性能基线已更新: {self.baseline_metrics}")

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """检测性能异常"""
        anomalies = []

        if len(self.performance_history) < 10:
            return anomalies

        # 检查最新指标
        latest = self.performance_history[-1]
        if "system" in latest:
            # 使用基线进行异常检测
            if self.baseline_metrics:
                # 检查CPU异常
                if "cpu_percent" in latest["system"] and "cpu_percent" in self.baseline_metrics:
                    cpu_value = latest["system"]["cpu_percent"]
                    cpu_baseline = self.baseline_metrics["cpu_percent"]

                    if cpu_value > cpu_baseline * 1.5 or cpu_value > self.thresholds["cpu_percent"]:
                        anomaly = {
                            "type": "cpu_anomaly",
                            "value": cpu_value,
                            "baseline": cpu_baseline,
                            "threshold": self.thresholds["cpu_percent"],
                            "timestamp": latest["timestamp"],
                        }
                        anomalies.append(anomaly)
                        self.anomaly_history.append(anomaly)
                        # 触发告警
                        self.trigger_alert(anomaly)

                # 检查内存异常
                if "memory_percent" in latest["system"] and "memory_percent" in self.baseline_metrics:
                    memory_value = latest["system"]["memory_percent"]
                    memory_baseline = self.baseline_metrics["memory_percent"]

                    if memory_value > memory_baseline * 1.5 or memory_value > self.thresholds["memory_percent"]:
                        anomaly = {
                            "type": "memory_anomaly",
                            "value": memory_value,
                            "baseline": memory_baseline,
                            "threshold": self.thresholds["memory_percent"],
                            "timestamp": latest["timestamp"],
                        }
                        anomalies.append(anomaly)
                        self.anomaly_history.append(anomaly)
                        # 触发告警
                        self.trigger_alert(anomaly)

                # 检查磁盘异常
                if "disk_percent" in latest["system"] and "disk_percent" in self.baseline_metrics:
                    disk_value = latest["system"]["disk_percent"]
                    disk_baseline = self.baseline_metrics["disk_percent"]

                    if disk_value > disk_baseline * 1.2 or disk_value > self.thresholds["disk_percent"]:
                        anomaly = {
                            "type": "disk_anomaly",
                            "value": disk_value,
                            "baseline": disk_baseline,
                            "threshold": self.thresholds["disk_percent"],
                            "timestamp": latest["timestamp"],
                        }
                        anomalies.append(anomaly)
                        self.anomaly_history.append(anomaly)
                        # 触发告警
                        self.trigger_alert(anomaly)
            else:
                # 没有基线时使用简单的统计方法
                recent_metrics = self.performance_history[-10:]

                # 计算平均值
                cpu_values = [
                    m["system"]["cpu_percent"] for m in recent_metrics if "system" in m and "cpu_percent" in m["system"]
                ]
                memory_values = [
                    m["system"]["memory_percent"]
                    for m in recent_metrics
                    if "system" in m and "memory_percent" in m["system"]
                ]

                if cpu_values:
                    avg_cpu = sum(cpu_values) / len(cpu_values)
                    if "cpu_percent" in latest["system"] and latest["system"]["cpu_percent"] > avg_cpu * 1.5:
                        anomaly = {
                            "type": "cpu_spike",
                            "value": latest["system"]["cpu_percent"],
                            "average": avg_cpu,
                            "timestamp": latest["timestamp"],
                        }
                        anomalies.append(anomaly)
                        self.anomaly_history.append(anomaly)

                if memory_values:
                    avg_memory = sum(memory_values) / len(memory_values)
                    if "memory_percent" in latest["system"] and latest["system"]["memory_percent"] > avg_memory * 1.5:
                        anomaly = {
                            "type": "memory_spike",
                            "value": latest["system"]["memory_percent"],
                            "average": avg_memory,
                            "timestamp": latest["timestamp"],
                        }
                        anomalies.append(anomaly)
                        self.anomaly_history.append(anomaly)

        # 限制异常历史记录数量
        if len(self.anomaly_history) > 100:
            self.anomaly_history = self.anomaly_history[-100:]

        return anomalies

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.performance_history:
            return {}

        # 计算统计信息
        cpu_values = [
            m["system"]["cpu_percent"]
            for m in self.performance_history
            if "system" in m and "cpu_percent" in m["system"]
        ]
        memory_values = [
            m["system"]["memory_percent"]
            for m in self.performance_history
            if "system" in m and "memory_percent" in m["system"]
        ]
        disk_values = [
            m["system"]["disk_percent"]
            for m in self.performance_history
            if "system" in m and "disk_percent" in m["system"]
        ]

        summary = {
            "sample_count": len(self.performance_history),
            "cpu": {
                "avg": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                "max": max(cpu_values) if cpu_values else 0,
                "min": min(cpu_values) if cpu_values else 0,
            },
            "memory": {
                "avg": sum(memory_values) / len(memory_values) if memory_values else 0,
                "max": max(memory_values) if memory_values else 0,
                "min": min(memory_values) if memory_values else 0,
            },
            "disk": {
                "avg": sum(disk_values) / len(disk_values) if disk_values else 0,
                "max": max(disk_values) if disk_values else 0,
                "min": min(disk_values) if disk_values else 0,
            },
            "baseline": self.baseline_metrics,
            "anomaly_count": len(self.anomaly_history),
            "last_updated": self.performance_history[-1]["timestamp"] if self.performance_history else None,
        }

        return summary

    def get_baseline(self) -> Dict[str, Any]:
        """获取性能基线"""
        return self.baseline_metrics

    def get_anomaly_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取异常历史"""
        return self.anomaly_history[-limit:]

    def set_thresholds(self, thresholds: Dict[str, float]):
        """设置性能告警阈值"""
        self.thresholds.update(thresholds)
        logger.info(f"性能告警阈值已更新: {self.thresholds}")

    def set_alert_config(self, config: Dict[str, Any]):
        """设置告警配置"""
        self.alert_config.update(config)
        logger.info(f"告警配置已更新: {self.alert_config}")

    def add_alert_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """添加告警回调函数"""
        self.alert_config["callbacks"].append(callback)
        logger.info("告警回调函数已添加")

    def send_email_alert(self, alert: Dict[str, Any]):
        """发送邮件告警"""
        if not self.alert_config["email"]["enabled"]:
            return

        try:
            smtp_server = self.alert_config["email"]["smtp_server"]
            smtp_port = self.alert_config["email"]["smtp_port"]
            username = self.alert_config["email"]["username"]
            password = self.alert_config["email"]["password"]
            from_email = self.alert_config["email"]["from_email"]
            to_emails = self.alert_config["email"]["to_emails"]

            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = f"[PL5] 性能告警: {alert['type']}"

            # 邮件正文
            body = f"""
            性能告警通知
            
            告警类型: {alert['type']}
            告警时间: {alert['timestamp']}
            告警详情: {json.dumps(alert, indent=2, ensure_ascii=False)}
            
            请及时处理！
            """
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # 发送邮件
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)

            logger.info(f"邮件告警已发送: {alert['type']}")
        except Exception as e:
            logger.error(f"发送邮件告警失败: {str(e)}")

    def send_webhook_alert(self, alert: Dict[str, Any]):
        """发送webhook告警"""
        if not self.alert_config["webhook"]["enabled"]:
            return

        try:
            import requests

            webhook_url = self.alert_config["webhook"]["url"]

            # 发送webhook
            response = requests.post(webhook_url, json=alert, headers={"Content-Type": "application/json"})

            if response.status_code == 200:
                logger.info(f"Webhook告警已发送: {alert['type']}")
            else:
                logger.error(f"发送Webhook告警失败: {response.status_code}")
        except Exception as e:
            logger.error(f"发送Webhook告警失败: {str(e)}")

    def trigger_alert(self, alert: Dict[str, Any]):
        """触发告警"""
        if not self.alert_config["enabled"]:
            return

        # 记录告警历史
        self.alert_history.append(alert)
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]

        # 发送邮件告警
        self.send_email_alert(alert)

        # 发送webhook告警
        self.send_webhook_alert(alert)

        # 执行回调函数
        for callback in self.alert_config["callbacks"]:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"执行告警回调失败: {str(e)}")

    def get_alert_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取告警历史"""
        return self.alert_history[-limit:]

    def clear_alert_history(self):
        """清空告警历史"""
        self.alert_history.clear()
        logger.info("告警历史已清空")


class PerformanceTracker:
    """性能跟踪器 - 用于跟踪特定函数的执行性能"""

    def __init__(self, monitor: Optional[PerformanceMonitor] = None):
        """初始化性能跟踪器"""
        self.monitor = monitor
        self.timings = {}

    def track(self, func):
        """装饰器，用于跟踪函数执行时间"""

        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss

            result = func(*args, **kwargs)

            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss

            execution_time = end_time - start_time
            memory_used = (end_memory - start_memory) / 1024 / 1024  # MB

            # 记录执行时间
            func_name = func.__name__
            if func_name not in self.timings:
                self.timings[func_name] = []

            timing_data = {
                "timestamp": datetime.now().isoformat(),
                "execution_time": execution_time,
                "memory_used": memory_used,
                "args_count": len(args),
                "kwargs_count": len(kwargs),
            }

            self.timings[func_name].append(timing_data)

            # 限制每个函数的记录数量
            if len(self.timings[func_name]) > 100:
                self.timings[func_name] = self.timings[func_name][-100:]

            # 记录到性能监控器
            if self.monitor:
                self.monitor.data_queue.put(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "function": func_name,
                        "execution_time": execution_time,
                        "memory_used": memory_used,
                    }
                )

            logger.debug(f"函数 {func_name} 执行时间: {execution_time:.4f} 秒, 内存使用: {memory_used:.2f} MB")

            return result

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    def get_function_stats(self, func_name: str) -> Dict[str, Any]:
        """获取函数执行统计信息"""
        if func_name not in self.timings:
            return {}

        timings = self.timings[func_name]
        execution_times = [t["execution_time"] for t in timings]
        memory_used = [t["memory_used"] for t in timings]

        return {
            "calls": len(timings),
            "avg_execution_time": sum(execution_times) / len(execution_times),
            "max_execution_time": max(execution_times),
            "min_execution_time": min(execution_times),
            "avg_memory_used": sum(memory_used) / len(memory_used),
            "max_memory_used": max(memory_used),
            "last_execution": timings[-1]["timestamp"] if timings else None,
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有函数的统计信息"""
        stats = {}
        for func_name in self.timings:
            stats[func_name] = self.get_function_stats(func_name)
        return stats


# 全局性能监控器实例
_global_monitor = None
global_tracker = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def get_performance_tracker() -> PerformanceTracker:
    """获取全局性能跟踪器实例"""
    global global_tracker
    if global_tracker is None:
        global_tracker = PerformanceTracker(get_performance_monitor())
    return global_tracker


def start_performance_monitoring():
    """启动性能监控"""
    monitor = get_performance_monitor()
    monitor.start()
    logger.info("全局性能监控已启动")


def stop_performance_monitoring():
    """停止性能监控"""
    monitor = get_performance_monitor()
    monitor.stop()
    logger.info("全局性能监控已停止")


# 便捷装饰器
def track_performance(func):
    """性能跟踪装饰器"""
    tracker = get_performance_tracker()
    return tracker.track(func)
