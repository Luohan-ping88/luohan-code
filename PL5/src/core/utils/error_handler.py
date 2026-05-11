#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 统一错误处理模块 V2.0
提供完善的异常捕获、分类、日志记录和恢复策略

功能特性：
- 异常分类和封装
- 自动重试机制（指数退避）
- 结构化错误日志记录
- 优雅降级策略
- 错误恢复策略
"""

import logging
import time
import functools
import traceback
import json
import os
from typing import Any, Callable, Optional, Type, Tuple, Dict, List, Union
from datetime import datetime
from enum import Enum, auto
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

# 配置日志
logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """错误严重程度"""

    LOW = "low"  # 轻微错误，不影响系统运行
    MEDIUM = "medium"  # 中等错误，可能影响部分功能
    HIGH = "high"  # 严重错误，影响核心功能
    CRITICAL = "critical"  # 致命错误，系统可能无法运行


class ErrorCategory(Enum):
    """错误类别"""

    DATA = "data"  # 数据相关错误
    MODEL = "model"  # 模型相关错误
    CONFIG = "config"  # 配置相关错误
    NETWORK = "network"  # 网络相关错误
    SYSTEM = "system"  # 系统相关错误
    VALIDATION = "validation"  # 验证错误
    RESOURCE = "resource"  # 资源错误
    UNKNOWN = "unknown"  # 未知错误


@dataclass
class ErrorContext:
    """错误上下文信息"""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    operation: str = "unknown"
    component: str = "unknown"
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None


@dataclass
class ErrorRecord:
    """错误记录"""

    error_id: str
    error_type: str
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    context: ErrorContext
    original_error: Optional[str] = None
    recovery_attempts: int = 0
    recovered: bool = False
    recovery_strategy: Optional[str] = None


class PL5BaseError(Exception):
    """PL5系统基础异常类"""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        context: Optional[Dict] = None,
        original_error: Optional[Exception] = None,
        error_code: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.context = context or {}
        self.original_error = original_error
        self.error_code = error_code or self._generate_error_code()
        self.timestamp = datetime.now().isoformat()
        self.error_type = self.__class__.__name__
        self.error_id = self._generate_error_id()

    def _generate_error_code(self) -> str:
        """生成错误代码"""
        category_prefix = self.category.value.upper()[:3]
        type_suffix = self.__class__.__name__.replace("Error", "").upper()[:3]
        return f"{category_prefix}_{type_suffix}"

    def _generate_error_id(self) -> str:
        """生成唯一错误ID"""
        import uuid

        return f"ERR_{uuid.uuid4().hex[:12].upper()}"

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "timestamp": self.timestamp,
            "context": self.context,
            "original_error": str(self.original_error) if self.original_error else None,
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __str__(self):
        return f"[{self.error_code}:{self.severity.value}] {self.message}"

    def __repr__(self):
        return f"{self.error_type}(code={self.error_code}, severity={self.severity.value}, message={self.message})"


# ==================== 数据相关错误 ====================


class DataError(PL5BaseError):
    """数据相关错误基类"""

    def __init__(self, message: str, data_source: str = "unknown", record_count: int = 0, **kwargs):
        super().__init__(message, category=ErrorCategory.DATA, **kwargs)
        self.data_source = data_source
        self.record_count = record_count
        self.context.update({"data_source": data_source, "record_count": record_count})


class DataLoadError(DataError):
    """数据加载失败"""

    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.file_path = file_path
        if file_path:
            self.context["file_path"] = file_path


class DataValidationError(DataError):
    """数据验证失败"""

    def __init__(self, message: str, validation_errors: Optional[List[str]] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, **kwargs)
        self.validation_errors = validation_errors or []
        self.context["validation_errors"] = self.validation_errors


class DataParseError(DataError):
    """数据解析失败"""

    def __init__(self, message: str, raw_data: Optional[str] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.raw_data = raw_data
        if raw_data:
            self.context["raw_data_preview"] = raw_data[:200] if len(raw_data) > 200 else raw_data


class DataCorruptionError(DataError):
    """数据损坏错误"""

    def __init__(
        self, message: str, checksum_expected: Optional[str] = None, checksum_actual: Optional[str] = None, **kwargs
    ):
        super().__init__(message, severity=ErrorSeverity.CRITICAL, **kwargs)
        self.checksum_expected = checksum_expected
        self.checksum_actual = checksum_actual
        self.context.update({"checksum_expected": checksum_expected, "checksum_actual": checksum_actual})


# ==================== 模型相关错误 ====================


class ModelError(PL5BaseError):
    """模型相关错误基类"""

    def __init__(self, message: str, model_name: str = "unknown", operation: str = "unknown", **kwargs):
        super().__init__(message, category=ErrorCategory.MODEL, **kwargs)
        self.model_name = model_name
        self.operation = operation
        self.context.update({"model_name": model_name, "operation": operation})


class ModelLoadError(ModelError):
    """模型加载失败"""

    def __init__(self, message: str, model_path: Optional[str] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.model_path = model_path
        if model_path:
            self.context["model_path"] = model_path


class ModelSaveError(ModelError):
    """模型保存失败"""

    def __init__(self, message: str, save_path: Optional[str] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.save_path = save_path
        if save_path:
            self.context["save_path"] = save_path


class ModelPredictionError(ModelError):
    """模型预测失败"""

    def __init__(self, message: str, input_shape: Optional[Tuple] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.input_shape = input_shape
        if input_shape:
            self.context["input_shape"] = input_shape


class ModelTrainingError(ModelError):
    """模型训练失败"""

    def __init__(self, message: str, epoch: Optional[int] = None, loss: Optional[float] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.epoch = epoch
        self.loss = loss
        self.context.update({"epoch": epoch, "loss": loss})


class ModelVersionError(ModelError):
    """模型版本错误"""

    def __init__(
        self, message: str, expected_version: Optional[str] = None, actual_version: Optional[str] = None, **kwargs
    ):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, **kwargs)
        self.expected_version = expected_version
        self.actual_version = actual_version
        self.context.update({"expected_version": expected_version, "actual_version": actual_version})


# ==================== 配置相关错误 ====================


class ConfigError(PL5BaseError):
    """配置相关错误基类"""

    def __init__(self, message: str, config_key: str = "unknown", config_file: str = "unknown", **kwargs):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, category=ErrorCategory.CONFIG, **kwargs)
        self.config_key = config_key
        self.config_file = config_file
        self.context.update({"config_key": config_key, "config_file": config_file})


class ConfigMissingKeyError(ConfigError):
    """配置键缺失"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)


class ConfigValueError(ConfigError):
    """配置值无效"""

    def __init__(self, message: str, expected_type: Optional[str] = None, actual_value: Optional[Any] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, **kwargs)
        self.expected_type = expected_type
        self.actual_value = actual_value
        self.context.update(
            {"expected_type": expected_type, "actual_value": str(actual_value) if actual_value is not None else None}
        )


class ConfigFileError(ConfigError):
    """配置文件错误"""

    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.file_path = file_path
        if file_path:
            self.context["file_path"] = file_path


# ==================== 网络相关错误 ====================


class NetworkError(PL5BaseError):
    """网络相关错误基类"""

    def __init__(self, message: str, url: str = "unknown", status_code: int = 0, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, category=ErrorCategory.NETWORK, **kwargs)
        self.url = url
        self.status_code = status_code
        self.context.update({"url": url, "status_code": status_code})


class NetworkTimeoutError(NetworkError):
    """网络超时"""

    def __init__(self, message: str, timeout_seconds: Optional[float] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.timeout_seconds = timeout_seconds
        if timeout_seconds:
            self.context["timeout_seconds"] = timeout_seconds


class NetworkConnectionError(NetworkError):
    """连接错误"""

    def __init__(self, message: str, retry_count: int = 0, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.retry_count = retry_count
        self.context["retry_count"] = retry_count


class NetworkHTTPError(NetworkError):
    """HTTP错误"""

    def __init__(self, message: str, method: str = "GET", **kwargs):
        super().__init__(message, **kwargs)
        self.method = method
        self.context["http_method"] = method


class NetworkRateLimitError(NetworkError):
    """请求频率限制"""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, **kwargs)
        self.retry_after = retry_after
        if retry_after:
            self.context["retry_after_seconds"] = retry_after


# ==================== 系统相关错误 ====================


class SystemError(PL5BaseError):
    """系统相关错误基类"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.SYSTEM, **kwargs)


class ResourceExhaustedError(SystemError):
    """资源耗尽错误"""

    def __init__(
        self,
        message: str,
        resource_type: str = "unknown",
        current_usage: Optional[float] = None,
        limit: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(message, severity=ErrorSeverity.CRITICAL, **kwargs)
        self.resource_type = resource_type
        self.current_usage = current_usage
        self.limit = limit
        self.context.update({"resource_type": resource_type, "current_usage": current_usage, "limit": limit})


class ServiceUnavailableError(SystemError):
    """服务不可用错误"""

    def __init__(self, message: str, service_name: str = "unknown", downtime_seconds: Optional[int] = None, **kwargs):
        super().__init__(message, severity=ErrorSeverity.CRITICAL, **kwargs)
        self.service_name = service_name
        self.downtime_seconds = downtime_seconds
        self.context.update({"service_name": service_name, "downtime_seconds": downtime_seconds})


class ConcurrencyError(SystemError):
    """并发错误"""

    def __init__(
        self, message: str, max_concurrency: Optional[int] = None, current_concurrency: Optional[int] = None, **kwargs
    ):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.max_concurrency = max_concurrency
        self.current_concurrency = current_concurrency
        self.context.update({"max_concurrency": max_concurrency, "current_concurrency": current_concurrency})


# ==================== 错误日志记录器 ====================


class ErrorLogger:
    """结构化错误日志记录器"""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.error_history: List[ErrorRecord] = []
        self.max_history_size = 1000
        self.error_counts: Dict[str, int] = {}
        self._initialized = True

        # 确保日志目录存在
        self.log_dir = Path("logs/errors")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_error(
        self,
        error: Union[PL5BaseError, Exception],
        operation: str = "unknown",
        component: str = "unknown",
        recovery_strategy: Optional[str] = None,
    ) -> ErrorRecord:
        """记录错误"""

        if isinstance(error, PL5BaseError):
            error_id = error.error_id
            error_type = error.error_type
            severity = error.severity
            category = error.category
            message = error.message
            context_data = error.context
            original_error_str = str(error.original_error) if error.original_error else None
        else:
            error_id = f"ERR_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            error_type = error.__class__.__name__
            severity = ErrorSeverity.HIGH
            category = ErrorCategory.UNKNOWN
            message = str(error)
            context_data = {}
            original_error_str = None

        # 创建错误上下文
        context = ErrorContext(
            operation=operation, component=component, metadata=context_data, stack_trace=traceback.format_exc()
        )

        # 创建错误记录
        record = ErrorRecord(
            error_id=error_id,
            error_type=error_type,
            severity=severity,
            category=category,
            message=message,
            context=context,
            original_error=original_error_str,
            recovery_strategy=recovery_strategy,
        )

        # 添加到历史记录
        self.error_history.append(record)
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size :]

        # 更新错误计数
        error_key = f"{category.value}:{error_type}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        # 记录到日志
        self._write_to_log(record)

        return record

    def _write_to_log(self, record: ErrorRecord):
        """写入日志文件"""
        try:
            log_file = self.log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.jsonl"

            log_entry = {
                "error_id": record.error_id,
                "error_type": record.error_type,
                "severity": record.severity.value,
                "category": record.category.value,
                "message": record.message,
                "timestamp": record.context.timestamp,
                "operation": record.context.operation,
                "component": record.context.component,
                "recovered": record.recovered,
                "recovery_strategy": record.recovery_strategy,
            }

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        except Exception as e:
            logger.error(f"写入错误日志失败: {e}")

    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        stats = {
            "total_errors": len(self.error_history),
            "errors_by_severity": {},
            "errors_by_category": {},
            "errors_by_type": {},
            "recent_errors": [],
        }

        for record in self.error_history:
            # 按严重程度统计
            severity = record.severity.value
            stats["errors_by_severity"][severity] = stats["errors_by_severity"].get(severity, 0) + 1

            # 按类别统计
            category = record.category.value
            stats["errors_by_category"][category] = stats["errors_by_category"].get(category, 0) + 1

            # 按类型统计
            error_type = record.error_type
            stats["errors_by_type"][error_type] = stats["errors_by_type"].get(error_type, 0) + 1

        # 最近10个错误
        stats["recent_errors"] = [
            {
                "error_id": r.error_id,
                "error_type": r.error_type,
                "severity": r.severity.value,
                "message": r.message,
                "timestamp": r.context.timestamp,
            }
            for r in self.error_history[-10:]
        ]

        return stats

    def clear_history(self):
        """清除历史记录"""
        self.error_history.clear()
        self.error_counts.clear()


# 全局错误日志记录器实例
error_logger = ErrorLogger()


# ==================== 恢复策略 ====================


class RecoveryStrategy:
    """恢复策略枚举"""

    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK_TO_CACHE = "fallback_to_cache"
    FALLBACK_TO_DEFAULT = "fallback_to_default"
    FALLBACK_TO_SIMPLE_STRATEGY = "fallback_to_simple_strategyy"
    USE_LAST_GOOD_RESULT = "use_last_good_result"
    SKIP_OPERATION = "skip_operation"
    USE_BACKUP = "use_backup"


class RecoveryManager:
    """恢复管理器"""

    def __init__(self):
        self.recovery_stats = {"total_attempts": 0, "successful_recoveries": 0, "failed_recoveries": 0}
        self.last_good_results: Dict[str, Any] = {}

    def record_success(self, operation: str, result: Any):
        """记录成功的结果"""
        self.last_good_results[operation] = {"result": result, "timestamp": datetime.now().isoformat()}

    def get_last_good_result(self, operation: str) -> Optional[Any]:
        """获取上次成功的结果"""
        if operation in self.last_good_results:
            return self.last_good_results[operation]["result"]
        return None

    def record_recovery_attempt(self, success: bool):
        """记录恢复尝试"""
        self.recovery_stats["total_attempts"] += 1
        if success:
            self.recovery_stats["successful_recoveries"] += 1
        else:
            self.recovery_stats["failed_recoveries"] += 1

    def get_recovery_stats(self) -> Dict[str, Any]:
        """获取恢复统计信息"""
        total = self.recovery_stats["total_attempts"]
        successful = self.recovery_stats["successful_recoveries"]
        return {**self.recovery_stats, "success_rate": successful / total if total > 0 else 0.0}


# 全局恢复管理器实例
recovery_manager = RecoveryManager()


# ==================== 装饰器和工具函数 ====================


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, float, Exception], None]] = None,
    on_failure: Optional[Callable[[Exception], None]] = None,
    operation_name: Optional[str] = None,
):
    """
    指数退避重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        backoff_factor: 退避因子
        exceptions: 需要捕获的异常类型
        on_retry: 重试时的回调函数(attempt, delay, error)
        on_failure: 失败时的回调函数(error)
        operation_name: 操作名称
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    # 记录成功结果
                    recovery_manager.record_success(op_name, result)
                    return result
                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        delay = min(base_delay * (backoff_factor**attempt), max_delay)

                        logger.warning(
                            f"[Retry] {op_name} attempt {attempt + 1}/{max_retries + 1} failed: {e}, "
                            f"retrying in {delay:.1f}s..."
                        )

                        if on_retry:
                            on_retry(attempt + 1, delay, e)

                        time.sleep(delay)
                    else:
                        logger.error(f"[Retry] {op_name} failed after {max_retries + 1} attempts: {e}")

                        if on_failure:
                            on_failure(e)

                        # 尝试使用上次成功的结果
                        last_good = recovery_manager.get_last_good_result(op_name)
                        if last_good is not None:
                            logger.warning(f"[Fallback] Using last good result for {op_name}")
                            recovery_manager.record_recovery_attempt(True)
                            return last_good

                        recovery_manager.record_recovery_attempt(False)
                        raise

            return None  # 不会执行到这里

        return wrapper

    return decorator


def safe_execute(
    func: Callable,
    fallback_value: Any = None,
    log_errors: bool = True,
    operation_name: Optional[str] = None,
    *args,
    **kwargs,
) -> Any:
    """
    安全执行函数，出错时返回默认值

    Args:
        func: 要执行的函数
        fallback_value: 出错时的返回值
        log_errors: 是否记录错误
        operation_name: 操作名称
        *args, **kwargs: 函数参数

    Returns:
        函数执行结果或fallback_value
    """
    op_name = operation_name or func.__name__

    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            error_logger.log_error(
                e, operation=op_name, component="safe_execute", recovery_strategy=RecoveryStrategy.FALLBACK_TO_DEFAULT
            )
            logger.warning(f"[SafeExecute] {op_name} failed: {e}, using fallback value")

        return fallback_value


def handle_errors(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    fallback_value: Any = None,
    log_errors: bool = True,
    reraise: bool = False,
    error_message: Optional[str] = None,
):
    """
    错误处理装饰器

    Args:
        exceptions: 要捕获的异常类型
        fallback_value: 出错时的返回值
        log_errors: 是否记录错误
        reraise: 是否重新抛出异常
        error_message: 自定义错误消息
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_errors:
                    msg = error_message or str(e)
                    logger.error(f"[ErrorHandler] {func.__name__}: {msg}")

                    if isinstance(e, PL5BaseError):
                        error_logger.log_error(e, operation=func.__name__)

                if reraise:
                    raise

                return fallback_value

        return wrapper

    return decorator


def circuit_breaker(
    failure_threshold: int = 5, recovery_timeout: float = 60.0, expected_exception: Type[Exception] = Exception
):
    """
    熔断器装饰器

    Args:
        failure_threshold: 失败阈值
        recovery_timeout: 恢复超时（秒）
        expected_exception: 预期的异常类型
    """

    def decorator(func: Callable) -> Callable:
        failures = 0
        last_failure_time = None
        state = "closed"  # closed, open, half-open
        lock = Lock()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal failures, last_failure_time, state

            with lock:
                if state == "open":
                    if last_failure_time and (time.time() - last_failure_time) > recovery_timeout:
                        state = "half-open"
                        logger.info(f"[CircuitBreaker] {func.__name__} entering half-open state")
                    else:
                        raise ServiceUnavailableError(
                            f"Circuit breaker is open for {func.__name__}", service_name=func.__name__
                        )

            try:
                result = func(*args, **kwargs)

                with lock:
                    if state == "half-open":
                        state = "closed"
                        failures = 0
                        logger.info(f"[CircuitBreaker] {func.__name__} circuit closed")

                return result

            except expected_exception as e:
                with lock:
                    failures += 1
                    last_failure_time = time.time()

                    if failures >= failure_threshold:
                        state = "open"
                        logger.error(f"[CircuitBreaker] {func.__name__} circuit opened after {failures} failures")

                raise

        return wrapper

    return decorator


# ==================== 便捷函数 ====================


def get_error_stats() -> Dict[str, Any]:
    """获取错误统计信息"""
    return error_logger.get_error_stats()


def get_recovery_stats() -> Dict[str, Any]:
    """获取恢复统计信息"""
    return recovery_manager.get_recovery_stats()


def clear_error_history():
    """清除错误历史记录"""
    error_logger.clear_history()


def wrap_exception(exception: Exception, target_class: Type[PL5BaseError], **kwargs) -> PL5BaseError:
    """
    将普通异常包装为PL5BaseError

    Args:
        exception: 原始异常
        target_class: 目标异常类
        **kwargs: 额外的参数

    Returns:
        包装后的异常
    """
    return target_class(message=str(exception), original_error=exception, **kwargs)


# ==================== 导出 ====================

__all__ = [
    # 枚举
    "ErrorSeverity",
    "ErrorCategory",
    "RecoveryStrategy",
    # 基础异常类
    "PL5BaseError",
    # 数据错误
    "DataError",
    "DataLoadError",
    "DataValidationError",
    "DataParseError",
    "DataCorruptionError",
    # 模型错误
    "ModelError",
    "ModelLoadError",
    "ModelSaveError",
    "ModelPredictionError",
    "ModelTrainingError",
    "ModelVersionError",
    # 配置错误
    "ConfigError",
    "ConfigMissingKeyError",
    "ConfigValueError",
    "ConfigFileError",
    # 网络错误
    "NetworkError",
    "NetworkTimeoutError",
    "NetworkConnectionError",
    "NetworkHTTPError",
    "NetworkRateLimitError",
    # 系统错误
    "SystemError",
    "ResourceExhaustedError",
    "ServiceUnavailableError",
    "ConcurrencyError",
    # 日志和恢复
    "ErrorLogger",
    "ErrorRecord",
    "ErrorContext",
    "RecoveryManager",
    "error_logger",
    "recovery_manager",
    # 装饰器和工具
    "retry_with_exponential_backoff",
    "safe_execute",
    "handle_errors",
    "circuit_breaker",
    "wrap_exception",
    # 便捷函数
    "get_error_stats",
    "get_recovery_stats",
    "clear_error_history",
]
