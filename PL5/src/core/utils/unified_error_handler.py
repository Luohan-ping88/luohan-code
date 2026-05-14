"""统一错误处理模块

整合错误处理系统，提供统一的错误分类、处理和重试机制。
"""

from enum import Enum
from typing import Optional, Callable, TypeVar, Generic, List, Dict
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """错误严重性枚举"""

    ERROR_SEVERITY_LOW = "low"
    ERROR_SEVERITY_MEDIUM = "medium"
    ERROR_SEVERITY_HIGH = "high"
    ERROR_SEVERITY_CRITICAL = "critical"


class ErrorType(Enum):
    """错误类型枚举"""

    # 数据相关错误
    DATA_ERROR = "data_error"
    DATA_LOAD_ERROR = "data_load_error"
    DATA_VALIDATION_ERROR = "data_validation_error"
    DATA_PARSE_ERROR = "data_parse_error"

    # 模型相关错误
    MODEL_ERROR = "model_error"
    MODEL_LOAD_ERROR = "model_load_error"
    MODEL_PREDICT_ERROR = "model_predict_error"

    # 网络相关错误
    NETWORK_ERROR = "network_error"
    NETWORK_TIMEOUT_ERROR = "network_timeout_error"
    NETWORK_CONNECTION_ERROR = "network_connection_error"
    NETWORK_HTTP_ERROR = "network_http_error"

    # 配置相关错误
    CONFIG_ERROR = "config_error"

    # API相关错误
    API_ERROR = "api_error"
    RATE_LIMIT_ERROR = "rate_limit_error"

    # 认证相关错误
    AUTH_ERROR = "auth_error"

    # 服务器相关错误
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"

    # 其他错误
    UNKNOWN_ERROR = "unknown_error"


class PL5Error(Exception):
    """PL5系统统一错误基类"""

    _error_type = ErrorType.UNKNOWN_ERROR

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR_SEVERITY_MEDIUM,
        error_code: Optional[int] = None,
        context: Optional[Dict] = None,
        original_error: Optional[Exception] = None,
        **kwargs,
    ):
        """初始化错误

        Args:
            message: 错误消息
            severity: 错误严重性
            error_code: 错误代码
            context: 上下文信息
            original_error: 原始错误
        """
        super().__init__(message)
        self.message = message
        self.error_type = self._error_type
        self.severity = severity
        self.error_code = error_code
        self.context = context or {}
        self.original_error = original_error
        self.timestamp = time.time()
        self.error_class = self.__class__.__name__

    def to_dict(self) -> Dict:
        """将错误转换为字典

        Returns:
            错误字典
        """
        return {
            "error_class": self.error_class,
            "error_type": self.error_type.value,
            "message": self.message,
            "severity": self.severity.value,
            "error_code": self.error_code,
            "timestamp": self.timestamp,
            "context": self.context,
            "original_error": (
                str(self.original_error) if self.original_error else None
            ),
        }

    def __str__(self):
        return f"[{self.error_class}:{self.error_type.value}:{self.severity.value}] {self.message}"


# 数据相关错误
class DataError(PL5Error):
    """数据相关错误"""

    _error_type = ErrorType.DATA_ERROR

    def __init__(
        self,
        message: str,
        data_source: str = "unknown",
        record_count: int = 0,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.data_source = data_source
        self.record_count = record_count
        self.context.update(
            {"data_source": data_source, "record_count": record_count}
        )


class DataLoadError(DataError):
    """数据加载失败"""

    _error_type = ErrorType.DATA_LOAD_ERROR


class DataValidationError(DataError):
    """数据验证失败"""

    _error_type = ErrorType.DATA_VALIDATION_ERROR


class DataParseError(DataError):
    """数据解析失败"""

    _error_type = ErrorType.DATA_PARSE_ERROR


# 模型相关错误
class ModelError(PL5Error):
    """模型相关错误"""

    _error_type = ErrorType.MODEL_ERROR

    def __init__(
        self,
        message: str,
        model_name: str = "unknown",
        operation: str = "unknown",
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.model_name = model_name
        self.operation = operation
        self.context.update({"model_name": model_name, "operation": operation})


class ModelLoadError(ModelError):
    """模型加载失败"""

    _error_type = ErrorType.MODEL_LOAD_ERROR


class ModelPredictError(ModelError):
    """模型预测失败"""

    _error_type = ErrorType.MODEL_PREDICT_ERROR


# 网络相关错误
class NetworkError(PL5Error):
    """网络相关错误"""

    _error_type = ErrorType.NETWORK_ERROR


class NetworkTimeoutError(NetworkError):
    """网络超时错误"""

    _error_type = ErrorType.NETWORK_TIMEOUT_ERROR


class NetworkConnectionError(NetworkError):
    """网络连接错误"""

    _error_type = ErrorType.NETWORK_CONNECTION_ERROR


class NetworkHTTPError(NetworkError):
    """网络HTTP错误"""

    _error_type = ErrorType.NETWORK_HTTP_ERROR

    def __init__(self, message: str, status_code: int = None, **kwargs):
        super().__init__(message, **kwargs)
        if status_code:
            self.context.update({"status_code": status_code})


# 配置相关错误
class ConfigError(PL5Error):
    """配置相关错误"""

    _error_type = ErrorType.CONFIG_ERROR

    def __init__(self, message: str, config_key: str = "unknown", **kwargs):
        super().__init__(message, **kwargs)
        self.config_key = config_key
        self.context.update({"config_key": config_key})


# API相关错误
class ApiError(PL5Error):
    """API错误"""

    _error_type = ErrorType.API_ERROR


class RateLimitError(PL5Error):
    """速率限制错误"""

    _error_type = ErrorType.RATE_LIMIT_ERROR


# 认证相关错误
class AuthError(PL5Error):
    """认证错误"""

    _error_type = ErrorType.AUTH_ERROR


# 服务器相关错误
class ServerError(PL5Error):
    """服务器错误"""

    _error_type = ErrorType.SERVER_ERROR


class ClientError(PL5Error):
    """客户端错误"""

    _error_type = ErrorType.CLIENT_ERROR


T = TypeVar("T")


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        retryable_errors: Optional[List[ErrorType]] = None,
    ):
        """初始化重试配置

        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
            backoff_factor: 退避因子
            retryable_errors: 可重试的错误类型
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retryable_errors = retryable_errors or [
            ErrorType.NETWORK_ERROR,
            ErrorType.NETWORK_TIMEOUT_ERROR,
            ErrorType.NETWORK_CONNECTION_ERROR,
            ErrorType.NETWORK_HTTP_ERROR,
            ErrorType.RATE_LIMIT_ERROR,
            ErrorType.SERVER_ERROR,
        ]


class RetryResult(Generic[T]):
    """重试结果"""

    def __init__(
        self,
        success: bool,
        result: Optional[T] = None,
        error: Optional[PL5Error] = None,
        attempts: int = 1,
    ):
        """初始化重试结果

        Args:
            success: 是否成功
            result: 结果
            error: 错误
            attempts: 尝试次数
        """
        self.success = success
        self.result = result
        self.error = error
        self.attempts = attempts


def retry_with_backoff(
    func: Callable[..., T],
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs,
) -> RetryResult[T]:
    """带退避的重试装饰器

    Args:
        func: 要执行的函数
        config: 重试配置
        *args: 函数参数
        **kwargs: 函数关键字参数

    Returns:
        重试结果
    """
    if config is None:
        config = RetryConfig()

    attempts = 0
    last_error = None

    while attempts <= config.max_retries:
        try:
            attempts += 1
            result = func(*args, **kwargs)
            return RetryResult(success=True, result=result, attempts=attempts)
        except PL5Error as e:
            last_error = e

            # 检查是否可重试
            if e.error_type not in config.retryable_errors:
                break

            # 计算退避延迟
            if attempts <= config.max_retries:
                delay = min(
                    config.base_delay
                    * (config.backoff_factor ** (attempts - 1)),
                    config.max_delay,
                )
                logger.info(
                    f"Retrying {func.__name__} in {delay:.2f} seconds... (Attempt {attempts}/{config.max_retries})"
                )
                time.sleep(delay)
        except Exception as e:
            # 将普通异常转换为PL5Error
            last_error = PL5Error(
                str(e), original_error=e
            )
            break

    return RetryResult(success=False, error=last_error, attempts=attempts)


class ErrorHandler:
    """错误处理器"""

    def __init__(
        self,
        log_errors: bool = True,
        default_retry_config: Optional[RetryConfig] = None,
    ):
        """初始化错误处理器

        Args:
            log_errors: 是否记录错误
            default_retry_config: 默认重试配置
        """
        self.log_errors = log_errors
        self.default_retry_config = default_retry_config or RetryConfig()

    def handle_error(
        self, error: Exception, context: Optional[Dict] = None
    ) -> PL5Error:
        """处理错误

        Args:
            error: 原始错误
            context: 上下文信息

        Returns:
            标准化的PL5Error
        """
        # 已经是PL5Error的直接返回
        if isinstance(error, PL5Error):
            if self.log_errors:
                self._log_error(error, context)
            return error

        # 转换为PL5Error
        pl5_error = self._convert_to_pl5_error(error, context)
        if self.log_errors:
            self._log_error(pl5_error, context)
        return pl5_error

    def _convert_to_pl5_error(
        self, error: Exception, context: Optional[Dict] = None
    ) -> PL5Error:
        """将普通异常转换为PL5Error

        Args:
            error: 原始错误
            context: 上下文信息

        Returns:
            PL5Error
        """
        error_type = ErrorType.UNKNOWN_ERROR
        error_code = None
        severity = ErrorSeverity.ERROR_SEVERITY_MEDIUM

        # 根据异常类型进行分类
        import requests

        if isinstance(error, requests.exceptions.RequestException):
            if isinstance(error, requests.exceptions.Timeout):
                error_type = ErrorType.NETWORK_TIMEOUT_ERROR
            elif isinstance(error, requests.exceptions.ConnectionError):
                error_type = ErrorType.NETWORK_CONNECTION_ERROR
            elif isinstance(error, requests.exceptions.HTTPError):
                status_code = (
                    error.response.status_code
                    if hasattr(error, "response")
                    else None
                )
                error_code = status_code
                error_type = ErrorType.NETWORK_HTTP_ERROR
                if status_code:
                    context = context or {}
                    context.update({"status_code": status_code})
                    if 400 <= status_code < 500:
                        if status_code == 401:
                            error_type = ErrorType.AUTH_ERROR
                        elif status_code == 429:
                            error_type = ErrorType.RATE_LIMIT_ERROR
                        else:
                            error_type = ErrorType.CLIENT_ERROR
                    else:
                        error_type = ErrorType.SERVER_ERROR
        elif isinstance(error, TimeoutError):
            error_type = ErrorType.NETWORK_TIMEOUT_ERROR

        return PL5Error(
            message=str(error),
            error_code=error_code,
            severity=severity,
            context=context,
            original_error=error,
        )

    def _log_error(self, error: PL5Error, context: Optional[Dict] = None):
        """记录错误

        Args:
            error: PL5Error
            context: 上下文信息
        """
        log_message = f"Error: {error.error_type.value} - {str(error)}"
        if error.error_code:
            log_message += f" (Code: {error.error_code})"
        if context:
            log_message += f" Context: {context}"

        # 根据错误严重性选择日志级别
        if error.severity == ErrorSeverity.ERROR_SEVERITY_LOW:
            logger.info(log_message)
        elif error.severity == ErrorSeverity.ERROR_SEVERITY_MEDIUM:
            logger.warning(log_message)
        else:
            logger.error(log_message)

    def execute_with_retry(
        self, func: Callable[..., T], *args, **kwargs
    ) -> RetryResult[T]:
        """执行函数并自动重试

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            重试结果
        """
        return retry_with_backoff(
            func, self.default_retry_config, *args, **kwargs
        )


# 全局错误处理器实例
_global_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器

    Returns:
        错误处理器实例
    """
    return _global_error_handler


def handle_error(error: Exception, context: Optional[Dict] = None) -> PL5Error:
    """处理错误的便捷函数

    Args:
        error: 原始错误
        context: 上下文信息

    Returns:
        标准化的PL5Error
    """
    return _global_error_handler.handle_error(error, context)


def execute_with_retry(
    func: Callable[..., T], *args, **kwargs
) -> RetryResult[T]:
    """执行函数并自动重试的便捷函数

    Args:
        func: 要执行的函数
        *args: 函数参数
        **kwargs: 函数关键字参数

    Returns:
        重试结果
    """
    return _global_error_handler.execute_with_retry(func, *args, **kwargs)


# 装饰器
def retry_on_failure(
    max_retries=3, delay=1, backoff=2, exceptions=(Exception,)
):
    """重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 基础延迟
        backoff: 退避因子
        exceptions: 可重试的异常类型
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            retry_count = 0
            current_delay = delay
            last_error = None

            while retry_count <= max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    retry_count += 1
                    if retry_count <= max_retries:
                        logger.info(
                            f"Retrying {func.__name__} in {current_delay} seconds... (Attempt {retry_count}/{max_retries})"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Max retries reached for {func.__name__}"
                        )
                        raise
            return last_error

        return wrapper

    return decorator
