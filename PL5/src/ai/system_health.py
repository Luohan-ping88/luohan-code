"""系统健康监控模块

提供系统健康检查、自诊断和服务降级机制，提高系统稳定性。
"""

import time
import threading
import psutil
import logging
from typing import Dict, Any, Optional, Callable
from enum import Enum

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态枚举"""

    HEALTHY = "healthy"  # 健康
    DEGRADED = "degraded"  # 降级
    UNHEALTHY = "unhealthy"  # 不健康
    OFFLINE = "offline"  # 离线


class HealthCheckResult:
    """健康检查结果"""

    def __init__(
        self,
        service: str,
        status: ServiceStatus,
        message: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ):
        """初始化健康检查结果

        Args:
            service: 服务名称
            status: 服务状态
            message: 状态消息
            metrics: 服务指标
        """
        self.service = service
        self.status = status
        self.message = message
        self.metrics = metrics or {}
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            字典形式的健康检查结果
        """
        return {
            "service": self.service,
            "status": self.status.value,
            "message": self.message,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
        }


class SystemMonitor:
    """系统监控器"""

    def __init__(self, check_interval: int = 30):
        """初始化系统监控器

        Args:
            check_interval: 检查间隔（秒）
        """
        self.check_interval = check_interval
        self.services = {}
        self._lock = threading.RLock()
        self._running = False
        self._thread = None
        self._health_checks = {}

    def register_service(
        self, service_name: str, health_check: Callable[[], HealthCheckResult]
    ):
        """注册服务

        Args:
            service_name: 服务名称
            health_check: 健康检查函数
        """
        with self._lock:
            self._health_checks[service_name] = health_check

    def start(self):
        """启动监控"""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(
                target=self._monitor_loop, daemon=True
            )
            self._thread.start()
            logger.info("System monitor started")

    def stop(self):
        """停止监控"""
        if self._running:
            self._running = False
            if self._thread:
                self._thread.join()
            logger.info("System monitor stopped")

    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                self.run_health_checks()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
            time.sleep(self.check_interval)

    def run_health_checks(self) -> Dict[str, HealthCheckResult]:
        """运行健康检查

        Returns:
            健康检查结果字典
        """
        results = {}
        with self._lock:
            for service_name, health_check in self._health_checks.items():
                try:
                    result = health_check()
                    results[service_name] = result
                    self.services[service_name] = result

                    # 记录服务状态
                    if result.status == ServiceStatus.HEALTHY:
                        logger.info(
                            f"Service {service_name} is {result.status.value}: {result.message}"
                        )
                    elif result.status == ServiceStatus.DEGRADED:
                        logger.warning(
                            f"Service {service_name} is {result.status.value}: {result.message}"
                        )
                    else:
                        logger.error(
                            f"Service {service_name} is {result.status.value}: {result.message}"
                        )
                except Exception as e:
                    error_result = HealthCheckResult(
                        service=service_name,
                        status=ServiceStatus.UNHEALTHY,
                        message=f"Health check failed: {str(e)}",
                    )
                    results[service_name] = error_result
                    self.services[service_name] = error_result
                    logger.error(
                        f"Health check for {service_name} failed: {e}"
                    )
        return results

    def get_service_status(
        self, service_name: str
    ) -> Optional[HealthCheckResult]:
        """获取服务状态

        Args:
            service_name: 服务名称

        Returns:
            服务状态
        """
        with self._lock:
            return self.services.get(service_name)

    def get_all_statuses(self) -> Dict[str, HealthCheckResult]:
        """获取所有服务状态

        Returns:
            所有服务状态
        """
        with self._lock:
            return self.services.copy()

    def get_system_status(self) -> ServiceStatus:
        """获取系统整体状态

        Returns:
            系统整体状态
        """
        with self._lock:
            if not self.services:
                return ServiceStatus.OFFLINE

            # 检查是否有不健康的服务
            for result in self.services.values():
                if result.status == ServiceStatus.UNHEALTHY:
                    return ServiceStatus.UNHEALTHY
                elif result.status == ServiceStatus.DEGRADED:
                    return ServiceStatus.DEGRADED

            return ServiceStatus.HEALTHY


class SelfDiagnosis:
    """自诊断系统"""

    def __init__(self):
        """初始化自诊断系统"""
        self.diagnostics = {}
        self._lock = threading.RLock()

    def register_diagnostic(
        self, name: str, diagnostic: Callable[[], Dict[str, Any]]
    ):
        """注册诊断函数

        Args:
            name: 诊断名称
            diagnostic: 诊断函数
        """
        with self._lock:
            self.diagnostics[name] = diagnostic

    def run_diagnostics(self) -> Dict[str, Any]:
        """运行所有诊断

        Returns:
            诊断结果
        """
        results = {}
        with self._lock:
            for name, diagnostic in self.diagnostics.items():
                try:
                    result = diagnostic()
                    results[name] = result
                except Exception as e:
                    results[name] = {"success": False, "error": str(e)}
                    logger.error(f"Diagnostic {name} failed: {e}")
        return results

    def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标

        Returns:
            系统指标
        """
        try:
            # 获取CPU使用率
            cpu_usage = psutil.cpu_percent(interval=1)

            # 获取内存使用情况
            memory = psutil.virtual_memory()

            # 获取磁盘使用情况
            disk = psutil.disk_usage("/")

            # 获取网络统计
            net_io = psutil.net_io_counters()

            return {
                "cpu": {
                    "usage_percent": cpu_usage,
                    "count": psutil.cpu_count(),
                },
                "memory": {
                    "total": memory.total,
                    "used": memory.used,
                    "available": memory.available,
                    "percent": memory.percent,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                },
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {"error": str(e), "timestamp": time.time()}


class ServiceDegrader:
    """服务降级器"""

    def __init__(self):
        """初始化服务降级器"""
        self.services = {}
        self._lock = threading.RLock()

    def register_service(
        self,
        service_name: str,
        health_check: Callable[[], ServiceStatus],
        degrade_strategy: Callable[[], None],
        recover_strategy: Callable[[], None],
    ):
        """注册服务

        Args:
            service_name: 服务名称
            health_check: 健康检查函数
            degrade_strategy: 降级策略
            recover_strategy: 恢复策略
        """
        with self._lock:
            self.services[service_name] = {
                "health_check": health_check,
                "degrade_strategy": degrade_strategy,
                "recover_strategy": recover_strategy,
                "status": ServiceStatus.HEALTHY,
            }

    def check_and_degrade(self):
        """检查并执行服务降级"""
        with self._lock:
            for service_name, config in self.services.items():
                try:
                    status = config["health_check"]()
                    current_status = config["status"]

                    # 检查是否需要降级
                    if (
                        status == ServiceStatus.UNHEALTHY
                        and current_status != ServiceStatus.DEGRADED
                    ):
                        logger.warning(f"Degrading service {service_name}")
                        config["degrade_strategy"]()
                        config["status"] = ServiceStatus.DEGRADED
                    # 检查是否需要恢复
                    elif (
                        status == ServiceStatus.HEALTHY
                        and current_status == ServiceStatus.DEGRADED
                    ):
                        logger.info(f"Recovering service {service_name}")
                        config["recover_strategy"]()
                        config["status"] = ServiceStatus.HEALTHY
                except Exception as e:
                    logger.error(f"Error checking service {service_name}: {e}")

    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        """获取服务状态

        Args:
            service_name: 服务名称

        Returns:
            服务状态
        """
        with self._lock:
            service = self.services.get(service_name)
            return service["status"] if service else None

    def get_all_statuses(self) -> Dict[str, ServiceStatus]:
        """获取所有服务状态

        Returns:
            所有服务状态
        """
        with self._lock:
            return {
                service_name: config["status"]
                for service_name, config in self.services.items()
            }


class SystemHealthManager:
    """系统健康管理器"""

    def __init__(self, check_interval: int = 30):
        """初始化系统健康管理器

        Args:
            check_interval: 检查间隔（秒）
        """
        self.monitor = SystemMonitor(check_interval)
        self.diagnosis = SelfDiagnosis()
        self.degrader = ServiceDegrader()
        self._running = False
        self._thread = None

    def start(self):
        """启动系统健康管理"""
        if not self._running:
            self._running = True
            self.monitor.start()
            self._thread = threading.Thread(
                target=self._management_loop, daemon=True
            )
            self._thread.start()
            logger.info("System health manager started")

    def stop(self):
        """停止系统健康管理"""
        if self._running:
            self._running = False
            self.monitor.stop()
            if self._thread:
                self._thread.join()
            logger.info("System health manager stopped")

    def _management_loop(self):
        """管理循环"""
        while self._running:
            try:
                # 运行服务降级检查
                self.degrader.check_and_degrade()
            except Exception as e:
                logger.error(f"Error in management loop: {e}")
            time.sleep(10)  # 每10秒检查一次

    def register_service(
        self,
        service_name: str,
        health_check: Callable[[], HealthCheckResult],
        degrade_strategy: Optional[Callable[[], None]] = None,
        recover_strategy: Optional[Callable[[], None]] = None,
    ):
        """注册服务

        Args:
            service_name: 服务名称
            health_check: 健康检查函数
            degrade_strategy: 降级策略
            recover_strategy: 恢复策略
        """
        # 注册到监控器
        self.monitor.register_service(service_name, health_check)

        # 如果提供了降级和恢复策略，注册到降级器
        if degrade_strategy and recover_strategy:

            def status_check() -> ServiceStatus:
                result = health_check()
                return result.status

            self.degrader.register_service(
                service_name, status_check, degrade_strategy, recover_strategy
            )

    def register_diagnostic(
        self, name: str, diagnostic: Callable[[], Dict[str, Any]]
    ):
        """注册诊断函数

        Args:
            name: 诊断名称
            diagnostic: 诊断函数
        """
        self.diagnosis.register_diagnostic(name, diagnostic)

    def get_service_status(
        self, service_name: str
    ) -> Optional[HealthCheckResult]:
        """获取服务状态

        Args:
            service_name: 服务名称

        Returns:
            服务状态
        """
        return self.monitor.get_service_status(service_name)

    def get_all_statuses(self) -> Dict[str, HealthCheckResult]:
        """获取所有服务状态

        Returns:
            所有服务状态
        """
        return self.monitor.get_all_statuses()

    def get_system_status(self) -> ServiceStatus:
        """获取系统整体状态

        Returns:
            系统整体状态
        """
        return self.monitor.get_system_status()

    def run_diagnostics(self) -> Dict[str, Any]:
        """运行诊断

        Returns:
            诊断结果
        """
        return self.diagnosis.run_diagnostics()

    def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标

        Returns:
            系统指标
        """
        return self.diagnosis.get_system_metrics()


# 全局系统健康管理器实例
_global_health_manager = SystemHealthManager()


def get_health_manager() -> SystemHealthManager:
    """获取全局系统健康管理器

    Returns:
        系统健康管理器实例
    """
    return _global_health_manager


def start_health_monitoring():
    """启动健康监控"""
    _global_health_manager.start()


def stop_health_monitoring():
    """停止健康监控"""
    _global_health_manager.stop()


def register_service(
    service_name: str,
    health_check: Callable[[], HealthCheckResult],
    degrade_strategy: Optional[Callable[[], None]] = None,
    recover_strategy: Optional[Callable[[], None]] = None,
):
    """注册服务

    Args:
        service_name: 服务名称
        health_check: 健康检查函数
        degrade_strategy: 降级策略
        recover_strategy: 恢复策略
    """
    _global_health_manager.register_service(
        service_name, health_check, degrade_strategy, recover_strategy
    )


def register_diagnostic(name: str, diagnostic: Callable[[], Dict[str, Any]]):
    """注册诊断函数

    Args:
        name: 诊断名称
        diagnostic: 诊断函数
    """
    _global_health_manager.register_diagnostic(name, diagnostic)


def get_system_status() -> ServiceStatus:
    """获取系统整体状态

    Returns:
        系统整体状态
    """
    return _global_health_manager.get_system_status()


def get_service_status(service_name: str) -> Optional[HealthCheckResult]:
    """获取服务状态

    Args:
        service_name: 服务名称

    Returns:
        服务状态
    """
    return _global_health_manager.get_service_status(service_name)


def run_diagnostics() -> Dict[str, Any]:
    """运行诊断

    Returns:
        诊断结果
    """
    return _global_health_manager.run_diagnostics()


def get_system_metrics() -> Dict[str, Any]:
    """获取系统指标

    Returns:
        系统指标
    """
    return _global_health_manager.get_system_metrics()
