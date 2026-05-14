"""监控和日志

提供AI工具系统的监控和日志功能。
"""

import logging
import time
import threading
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import os
import traceback


class Logger:
    """日志系统

    提供不同级别的日志记录。
    """

    def __init__(self, name: str, log_level: str = "INFO"):
        """初始化日志系统

        Args:
            name: 日志名称
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger = logging.getLogger(name)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(self.log_level)

        # 配置控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)

        # 配置日志格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

        # 添加处理器
        if not self.logger.handlers:
            self.logger.addHandler(console_handler)

    def debug(self, message: str, **kwargs):
        """调试日志

        Args:
            message: 日志消息
            **kwargs: 额外参数
        """
        if kwargs:
            message = f"{message} - {json.dumps(kwargs, ensure_ascii=False)}"
        self.logger.debug(message)

    def info(self, message: str, **kwargs):
        """信息日志

        Args:
            message: 日志消息
            **kwargs: 额外参数
        """
        if kwargs:
            message = f"{message} - {json.dumps(kwargs, ensure_ascii=False)}"
        self.logger.info(message)

    def warning(self, message: str, **kwargs):
        """警告日志

        Args:
            message: 日志消息
            **kwargs: 额外参数
        """
        if kwargs:
            message = f"{message} - {json.dumps(kwargs, ensure_ascii=False)}"
        self.logger.warning(message)

    def error(self, message: str, **kwargs):
        """错误日志

        Args:
            message: 日志消息
            **kwargs: 额外参数
        """
        if kwargs:
            message = f"{message} - {json.dumps(kwargs, ensure_ascii=False)}"
        self.logger.error(message)

    def critical(self, message: str, **kwargs):
        """严重错误日志

        Args:
            message: 日志消息
            **kwargs: 额外参数
        """
        if kwargs:
            message = f"{message} - {json.dumps(kwargs, ensure_ascii=False)}"
        self.logger.critical(message)

    def exception(self, message: str, **kwargs):
        """异常日志

        Args:
            message: 日志消息
            **kwargs: 额外参数
        """
        if kwargs:
            message = f"{message} - {json.dumps(kwargs, ensure_ascii=False)}"
        self.logger.exception(message)


@dataclass
class Metric:
    """指标数据"""

    name: str  # 指标名称
    value: float  # 指标值
    timestamp: float  # 时间戳
    tags: Dict[str, str] = None  # 标签


class MetricsCollector:
    """指标收集器

    收集系统性能指标。
    """

    def __init__(self):
        """初始化指标收集器"""
        self.metrics = []
        self._lock = threading.RLock()

    def collect(self, name: str, value: float, **tags):
        """收集指标

        Args:
            name: 指标名称
            value: 指标值
            **tags: 标签
        """
        with self._lock:
            metric = Metric(
                name=name, value=value, timestamp=time.time(), tags=tags
            )
            self.metrics.append(metric)

    def get_metrics(
        self, name: Optional[str] = None, limit: int = 100
    ) -> List[Metric]:
        """获取指标

        Args:
            name: 指标名称，None表示所有指标
            limit: 限制数量

        Returns:
            指标列表
        """
        with self._lock:
            metrics = self.metrics

            if name:
                metrics = [m for m in metrics if m.name == name]

            return metrics[-limit:]

    def clear(self):
        """清空指标"""
        with self._lock:
            self.metrics.clear()

    def get_stats(self, name: str) -> Dict[str, Any]:
        """获取指标统计信息

        Args:
            name: 指标名称

        Returns:
            统计信息
        """
        with self._lock:
            metrics = [m for m in self.metrics if m.name == name]

            if not metrics:
                return {}

            values = [m.value for m in metrics]

            return {
                "count": len(metrics),
                "min": min(values),
                "max": max(values),
                "average": sum(values) / len(values),
                "latest": values[-1],
            }


class HealthChecker:
    """健康检查器

    检查系统健康状态。
    """

    def __init__(self):
        """初始化健康检查器"""
        self.checks = []

    def add_check(self, name: str, check_func: callable):
        """添加健康检查

        Args:
            name: 检查名称
            check_func: 检查函数，返回 (status, message)
        """
        self.checks.append((name, check_func))

    def check_health(self) -> Dict[str, Any]:
        """执行健康检查

        Returns:
            健康检查结果
        """
        results = {}
        overall_status = "healthy"

        for name, check_func in self.checks:
            try:
                status, message = check_func()
                results[name] = {"status": status, "message": message}

                if status != "healthy":
                    overall_status = "unhealthy"
            except Exception as e:
                results[name] = {"status": "error", "message": str(e)}
                overall_status = "unhealthy"

        return {
            "status": overall_status,
            "checks": results,
            "timestamp": time.time(),
        }

    def is_healthy(self) -> bool:
        """检查系统是否健康

        Returns:
            是否健康
        """
        result = self.check_health()
        return result["status"] == "healthy"


class AlertManager:
    """告警管理器

    管理系统告警。
    """

    def __init__(self):
        """初始化告警管理器"""
        self.alerts = []
        self._lock = threading.RLock()

    def create_alert(self, level: str, message: str, **details):
        """创建告警

        Args:
            level: 告警级别 (info, warning, error, critical)
            message: 告警消息
            **details: 详细信息
        """
        with self._lock:
            alert = {
                "level": level,
                "message": message,
                "details": details,
                "timestamp": time.time(),
                "id": f"alert_{int(time.time() * 1000)}",
            }
            self.alerts.append(alert)

            # 记录告警
            logger = Logger("AlertManager")
            if level == "error" or level == "critical":
                logger.error(message, **details)
            elif level == "warning":
                logger.warning(message, **details)
            else:
                logger.info(message, **details)

    def get_alerts(
        self, level: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取告警

        Args:
            level: 告警级别，None表示所有级别
            limit: 限制数量

        Returns:
            告警列表
        """
        with self._lock:
            alerts = self.alerts

            if level:
                alerts = [a for a in alerts if a["level"] == level]

            return alerts[-limit:]

    def clear_alerts(self):
        """清空告警"""
        with self._lock:
            self.alerts.clear()


class MonitoringSystem:
    """监控系统

    整合日志、指标、健康检查和告警。
    """

    def __init__(self):
        """初始化监控系统"""
        self.logger = Logger("MonitoringSystem")
        self.metrics_collector = MetricsCollector()
        self.health_checker = HealthChecker()
        self.alert_manager = AlertManager()

    def log(self, level: str, message: str, **kwargs):
        """记录日志

        Args:
            level: 日志级别
            message: 日志消息
            **kwargs: 额外参数
        """
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, **kwargs)

    def collect_metric(self, name: str, value: float, **tags):
        """收集指标

        Args:
            name: 指标名称
            value: 指标值
            **tags: 标签
        """
        self.metrics_collector.collect(name, value, **tags)

    def add_health_check(self, name: str, check_func: callable):
        """添加健康检查

        Args:
            name: 检查名称
            check_func: 检查函数
        """
        self.health_checker.add_check(name, check_func)

    def check_health(self) -> Dict[str, Any]:
        """执行健康检查

        Returns:
            健康检查结果
        """
        return self.health_checker.check_health()

    def create_alert(self, level: str, message: str, **details):
        """创建告警

        Args:
            level: 告警级别
            message: 告警消息
            **details: 详细信息
        """
        self.alert_manager.create_alert(level, message, **details)

    def get_metrics(
        self, name: Optional[str] = None, limit: int = 100
    ) -> List[Metric]:
        """获取指标

        Args:
            name: 指标名称
            limit: 限制数量

        Returns:
            指标列表
        """
        return self.metrics_collector.get_metrics(name, limit)

    def get_alerts(
        self, level: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取告警

        Args:
            level: 告警级别
            limit: 限制数量

        Returns:
            告警列表
        """
        return self.alert_manager.get_alerts(level, limit)

    def get_stats(self, metric_name: str) -> Dict[str, Any]:
        """获取指标统计信息

        Args:
            metric_name: 指标名称

        Returns:
            统计信息
        """
        return self.metrics_collector.get_stats(metric_name)

    def clear(self):
        """清空监控数据"""
        self.metrics_collector.clear()
        self.alert_manager.clear_alerts()


# 全局监控系统实例
_global_monitoring = MonitoringSystem()


def get_monitoring() -> MonitoringSystem:
    """获取全局监控系统

    Returns:
        监控系统实例
    """
    return _global_monitoring


# 装饰器
def monitored_function(func):
    """监控函数执行

    记录函数执行时间和异常。
    """

    def wrapper(*args, **kwargs):
        monitoring = get_monitoring()
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            # 记录执行时间
            monitoring.collect_metric(
                "function_execution_time",
                execution_time,
                function=func.__name__,
            )

            # 记录成功
            monitoring.log(
                "info",
                f"Function executed successfully",
                function=func.__name__,
                execution_time=execution_time,
            )

            return result
        except Exception as e:
            execution_time = time.time() - start_time

            # 记录异常
            monitoring.log(
                "error",
                f"Function execution failed",
                function=func.__name__,
                error=str(e),
                traceback=traceback.format_exc(),
                execution_time=execution_time,
            )

            # 创建告警
            monitoring.create_alert(
                "error",
                f"Function execution failed: {func.__name__}",
                error=str(e),
                function=func.__name__,
            )

            raise

    return wrapper


class LogRotator:
    """日志轮转器

    管理日志文件的轮转。
    """

    def __init__(
        self, log_dir: str = "logs", max_size: int = 10 * 1024 * 1024
    ):
        """初始化日志轮转器

        Args:
            log_dir: 日志目录
            max_size: 最大文件大小（字节）
        """
        self.log_dir = log_dir
        self.max_size = max_size

        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)

    def get_log_file(self, name: str) -> str:
        """获取日志文件路径

        Args:
            name: 日志名称

        Returns:
            日志文件路径
        """
        return os.path.join(self.log_dir, f"{name}.log")

    def should_rotate(self, file_path: str) -> bool:
        """检查是否需要轮转

        Args:
            file_path: 文件路径

        Returns:
            是否需要轮转
        """
        if not os.path.exists(file_path):
            return False

        return os.path.getsize(file_path) >= self.max_size

    def rotate(self, file_path: str):
        """执行轮转

        Args:
            file_path: 文件路径
        """
        if not os.path.exists(file_path):
            return

        # 创建备份文件
        backup_path = f"{file_path}.{int(time.time())}"
        os.rename(file_path, backup_path)

        # 创建新文件
        open(file_path, "w").close()


# 初始化监控系统
def init_monitoring():
    """初始化监控系统"""
    monitoring = get_monitoring()

    # 添加健康检查
    def check_tool_registry():
        from src.ai.registry import get_registry

        try:
            registry = get_registry()
            tool_count = len(registry.list_tools())
            return (
                "healthy",
                f"Tool registry is healthy with {tool_count} tools",
            )
        except Exception as e:
            return "unhealthy", f"Tool registry check failed: {str(e)}"

    def check_memory():
        import psutil

        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            if usage_percent < 80:
                return "healthy", f"Memory usage: {usage_percent}%"
            else:
                return "warning", f"Memory usage high: {usage_percent}%"
        except Exception as e:
            return "unhealthy", f"Memory check failed: {str(e)}"

    def check_cpu():
        import psutil

        try:
            cpu_percent = psutil.cpu_percent()
            if cpu_percent < 80:
                return "healthy", f"CPU usage: {cpu_percent}%"
            else:
                return "warning", f"CPU usage high: {cpu_percent}%"
        except Exception as e:
            return "unhealthy", f"CPU check failed: {str(e)}"

    # 添加健康检查
    monitoring.add_health_check("tool_registry", check_tool_registry)
    monitoring.add_health_check("memory", check_memory)
    monitoring.add_health_check("cpu", check_cpu)

    # 记录初始化
    monitoring.log("info", "Monitoring system initialized")


# 导出监控相关的API端点
def register_monitoring_routes(app):
    """注册监控相关的API端点

    Args:
        app: FastAPI应用
    """
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

    @router.get("/health")
    def health_check():
        """健康检查"""
        monitoring = get_monitoring()
        return monitoring.check_health()

    @router.get("/metrics")
    def get_metrics(name: Optional[str] = None, limit: int = 100):
        """获取指标"""
        monitoring = get_monitoring()
        metrics = monitoring.get_metrics(name, limit)
        return [
            {
                "name": m.name,
                "value": m.value,
                "timestamp": m.timestamp,
                "tags": m.tags,
            }
            for m in metrics
        ]

    @router.get("/alerts")
    def get_alerts(level: Optional[str] = None, limit: int = 100):
        """获取告警"""
        monitoring = get_monitoring()
        return monitoring.get_alerts(level, limit)

    @router.get("/stats/{metric_name}")
    def get_stats(metric_name: str):
        """获取指标统计信息"""
        monitoring = get_monitoring()
        return monitoring.get_stats(metric_name)

    app.include_router(router)
