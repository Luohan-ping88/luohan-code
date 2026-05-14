"""错误处理模块

提供详细的错误分类和重试机制，提高系统的稳定性和可靠性。
"""

from enum import Enum
from typing import Optional, Callable, TypeVar, Generic, List
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""

    NETWORK_ERROR = "network_error"  # 网络错误
    API_ERROR = "api_error"  # API错误
    RATE_LIMIT_ERROR = "rate_limit_error"  # 速率限制错误
    VALIDATION_ERROR = "validation_error"  # 验证错误
    AUTH_ERROR = "auth_error"  # 认证错误
    SERVER_ERROR = "server_error"  # 服务器错误
    CLIENT_ERROR = "client_error"  # 客户端错误
    TIMEOUT_ERROR = "timeout_error"  # 超时错误
    UNKNOWN_ERROR = "unknown_error"  # 未知错误


class AIError(Exception):
    """AI系统基础错误类"""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.UNKNOWN_ERROR,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        """初始化错误

        Args:
            message: 错误消息
            error_type: 错误类型
            error_code: 错误代码
            details: 错误详情
        """
        super().__init__(message)
        self.error_type = error_type
        self.error_code = error_code
        self.details = details
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        """将错误转换为字典

        Returns:
            错误字典
        """
        return {
            "message": str(self),
            "error_type": self.error_type.value,
            "error_code": self.error_code,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class NetworkError(AIError):
    """网络错误"""

    def __init__(
        self,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, ErrorType.NETWORK_ERROR, error_code, details)


class ApiError(AIError):
    """API错误"""

    def __init__(
        self,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, ErrorType.API_ERROR, error_code, details)


class RateLimitError(AIError):
    """速率限制错误"""

    def __init__(
        self,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(
            message, ErrorType.RATE_LIMIT_ERROR, error_code, details
        )


class ValidationError(AIError):
    """验证错误"""

    def __init__(
        self,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(
            message, ErrorType.VALIDATION_ERROR, error_code, details
        )


class AuthError(AIError):
    """认证错误"""

    def __init__(
        self,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, ErrorType.AUTH_ERROR, error_code, details)


class ServerError(AIError):
    """服务器错误"""

    def __init__(
        self,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, ErrorType.SERVER_ERROR, error_code, details)


class ClientError(AIError):
    """客户端错误"""

    def __init__(
        self,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, ErrorType.CLIENT_ERROR, error_code, details)


class TimeoutError(AIError):
    """超时错误"""

    def __init__(
        self,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, ErrorType.TIMEOUT_ERROR, error_code, details)


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
            ErrorType.RATE_LIMIT_ERROR,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.SERVER_ERROR,
        ]


class RetryResult(Generic[T]):
    """重试结果"""

    def __init__(
        self,
        success: bool,
        result: Optional[T] = None,
        error: Optional[AIError] = None,
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
        except AIError as e:
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
            # 将普通异常转换为AIError
            last_error = AIError(str(e), ErrorType.UNKNOWN_ERROR)
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
        self, error: Exception, context: Optional[dict] = None
    ) -> AIError:
        """处理错误

        Args:
            error: 原始错误
            context: 上下文信息

        Returns:
            标准化的AIError
        """
        # 已经是AIError的直接返回
        if isinstance(error, AIError):
            if self.log_errors:
                self._log_error(error, context)
            return error

        # 转换为AIError
        ai_error = self._convert_to_ai_error(error, context)
        if self.log_errors:
            self._log_error(ai_error, context)
        return ai_error

    def _convert_to_ai_error(
        self, error: Exception, context: Optional[dict] = None
    ) -> AIError:
        """将普通异常转换为AIError

        Args:
            error: 原始错误
            context: 上下文信息

        Returns:
            AIError
        """
        error_type = ErrorType.UNKNOWN_ERROR
        error_code = None

        # 根据异常类型进行分类
        import requests

        if isinstance(error, requests.exceptions.RequestException):
            if isinstance(error, requests.exceptions.Timeout):
                error_type = ErrorType.TIMEOUT_ERROR
            elif isinstance(error, requests.exceptions.ConnectionError):
                error_type = ErrorType.NETWORK_ERROR
            elif isinstance(error, requests.exceptions.HTTPError):
                status_code = (
                    error.response.status_code
                    if hasattr(error, "response")
                    else None
                )
                error_code = status_code
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
            error_type = ErrorType.TIMEOUT_ERROR

        return AIError(
            message=str(error),
            error_type=error_type,
            error_code=error_code,
            details=context,
        )

    def _log_error(self, error: AIError, context: Optional[dict] = None):
        """记录错误

        Args:
            error: AIError
            context: 上下文信息
        """
        log_message = f"Error: {error.error_type.value} - {str(error)}"
        if error.error_code:
            log_message += f" (Code: {error.error_code})"
        if context:
            log_message += f" Context: {context}"

        # 根据错误类型选择日志级别
        if error.error_type in [
            ErrorType.CLIENT_ERROR,
            ErrorType.VALIDATION_ERROR,
        ]:
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


def handle_error(error: Exception, context: Optional[dict] = None) -> AIError:
    """处理错误的便捷函数

    Args:
        error: 原始错误
        context: 上下文信息

    Returns:
        标准化的AIError
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
