"""
PL5 统一错误分类系统 V1.0
包含: DataError, ModelError, ConfigError, NetworkError
以及错误恢复机制和结构化日志记录
"""

import logging
import time
import functools
import traceback
from typing import Any, Callable, Optional, Type, Tuple, Dict
from datetime import datetime
from enum import Enum


logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    ERROR_SEVERITY_LOW = "low"
    ERROR_SEVERITY_MEDIUM = "medium"
    ERROR_SEVERITY_HIGH = "high"
    ERROR_SEVERITY_CRITICAL = "critical"


class PL5BaseError(Exception):
    """PL5系统基础异常类"""

    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.ERROR_SEVERITY_MEDIUM,
                 context: Dict = None, original_error: Exception = None):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.context = context or {}
        self.original_error = original_error
        self.timestamp = datetime.now().isoformat()
        self.error_type = self.__class__.__name__

    def to_dict(self) -> Dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "context": self.context,
            "original_error": str(self.original_error) if self.original_error else None
        }

    def __str__(self):
        return f"[{self.error_type}:{self.severity.value}] {self.message}"


class DataError(PL5BaseError):
    """数据相关错误"""

    def __init__(self, message: str, data_source: str = "unknown",
                 record_count: int = 0, **kwargs):
        super().__init__(message, **kwargs)
        self.data_source = data_source
        self.record_count = record_count
        self.context.update({
            "data_source": data_source,
            "record_count": record_count
        })


class DataLoadError(DataError):
    """数据加载失败"""
    pass


class DataValidationError(DataError):
    """数据验证失败"""
    pass


class DataParseError(DataError):
    """数据解析失败"""
    pass


class FeatureError(PL5BaseError):
    """特征工程相关错误"""

    def __init__(self, message: str, feature_name: str = "unknown",
                 operation: str = "unknown", **kwargs):
        super().__init__(message, **kwargs)
        self.feature_name = feature_name
        self.operation = operation
        self.context.update({
            "feature_name": feature_name,
            "operation": operation
        })


class FeatureExtractionError(FeatureError):
    """特征提取失败"""
    pass


class FeatureTransformationError(FeatureError):
    """特征转换失败"""
    pass


class ModelError(PL5BaseError):
    """模型相关错误"""

    def __init__(self, message: str, model_name: str = "unknown",
                 operation: str = "unknown", **kwargs):
        super().__init__(message, **kwargs)
        self.model_name = model_name
        self.operation = operation
        self.context.update({
            "model_name": model_name,
            "operation": operation
        })


class ModelLoadError(ModelError):
    """模型加载失败"""
    pass


class ModelSaveError(ModelError):
    """模型保存失败"""
    pass


class ModelPredictionError(ModelError):
    """模型预测失败"""
    pass


class ModelTrainingError(ModelError):
    """模型训练失败"""
    pass


class ConfigError(PL5BaseError):
    """配置相关错误"""

    def __init__(self, message: str, config_key: str = "unknown",
                 config_file: str = "unknown", **kwargs):
        super().__init__(message, severity=ErrorSeverity.ERROR_SEVERITY_LOW, **kwargs)
        self.config_key = config_key
        self.config_file = config_file
        self.context.update({
            "config_key": config_key,
            "config_file": config_file
        })


class ConfigMissingKeyError(ConfigError):
    """配置键缺失"""
    pass


class ConfigValueError(ConfigError):
    """配置值无效"""
    pass


class NetworkError(PL5BaseError):
    """网络相关错误"""

    def __init__(self, message: str, url: str = "unknown",
                 status_code: int = 0, **kwargs):
        super().__init__(message, severity=ErrorSeverity.ERROR_SEVERITY_HIGH, **kwargs)
        self.url = url
        self.status_code = status_code
        self.context.update({
            "url": url,
            "status_code": status_code
        })


class NetworkTimeoutError(NetworkError):
    """网络超时"""
    pass


class NetworkConnectionError(NetworkError):
    """连接错误"""
    pass


class NetworkHTTPError(NetworkError):
    """HTTP错误"""
    pass


class StructuredLogger:
    """结构化日志记录器 - 为关键操作提供详细日志"""

    OPERATION_MODEL_LOAD = "MODEL_LOAD"
    OPERATION_MODEL_SAVE = "MODEL_SAVE"
    OPERATION_FEATURE_ENGINEERING = "FEATURE_ENGINEERING"
    OPERATION_PREDICTION = "PREDICTION"
    OPERATION_EMAIL_SEND = "EMAIL_SEND"
    OPERATION_TASK_SCHEDULE = "TASK_SCHEDULE"
    OPERATION_DATA_FETCH = "DATA_FETCH"
    OPERATION_DATA_PARSE = "DATA_PARSE"

    def __init__(self, logger_instance: logging.Logger = None):
        self.logger = logger_instance or logger

    def log_operation_start(self, operation: str, details: Dict = None):
        self.logger.info(
            f"[OPERATION_START] {operation} | "
            f"details={details or {}}"
        )

    def log_operation_success(self, operation: str, duration_ms: float = 0,
                              result_summary: Dict = None):
        self.logger.info(
            f"[OPERATION_SUCCESS] {operation} | "
            f"duration={duration_ms:.2f}ms | "
            f"result={result_summary or {}}"
        )

    def log_operation_failure(self, operation: str, error: PL5BaseError,
                              duration_ms: float = 0):
        self.logger.error(
            f"[OPERATION_FAILURE] {operation} | "
            f"duration={duration_ms:.2f}ms | "
            f"error={error.to_dict()}"
        )

    def log_operation_warning(self, operation: str, message: str,
                              details: Dict = None):
        self.logger.warning(
            f"[OPERATION_WARNING] {operation} | "
            f"message={message} | "
            f"details={details or {}}"
        )

    def log_recovery_attempt(self, operation: str, attempt: int,
                             max_attempts: int, strategy: str):
        self.logger.warning(
            f"[RECOVERY_ATTEMPT] {operation} | "
            f"attempt={attempt}/{max_attempts} | "
            f"strategy={strategy}"
        )

    def log_fallback_used(self, operation: str, fallback_type: str,
                          reason: str):
        self.logger.warning(
            f"[FALLBACK_USED] {operation} | "
            f"fallback_type={fallback_type} | "
            f"reason={reason}"
        )


structured_logger = StructuredLogger()


class RecoveryStrategy:
    """错误恢复策略枚举"""
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK_TO_CACHE = "fallback_to_cache"
    FALLBACK_TO_DEFAULT = "fallback_to_default"
    FALLBACK_TO_SIMPLE_STRATEGY = "fallback_to_simple_strategy"
    USE_LAST_GOOD_RESULT = "use_last_good_result"


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    operation_name: str = "unknown",
    on_retry: Callable[[int, float, Exception], None] = None
):
    """
    指数退避重试装饰器/上下文管理器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        backoff_factor: 退避因子
        exceptions: 需要捕获的异常类型
        operation_name: 操作名称，用于日志
        on_retry: 重试时的回调函数(attempt, delay, error)
    """

    class RetryContextManager:
        def __init__(self, func=None):
            if func is not None:
                self.func = func
                functools.update_wrapper(self, func)
            else:
                self.func = None

        def __call__(self, *args, **kwargs):
            if self.func is None:
                raise TypeError("Decorator must be called with a function")
            return self._execute_with_retry(lambda: self.func(*args, **kwargs))

        def _execute_with_retry(self, func: Callable) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    structured_logger.log_operation_start(operation_name)
                    start = time.time()
                    result = func()
                    duration = (time.time() - start) * 1000
                    structured_logger.log_operation_success(
                        operation_name, duration
                    )
                    return result
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                        structured_logger.log_recovery_attempt(
                            operation_name, attempt + 1,
                            max_retries + 1, RecoveryStrategy.RETRY_WITH_BACKOFF
                        )
                        if on_retry:
                            on_retry(attempt + 1, delay, e)
                        time.sleep(delay)
                    else:
                        duration = 0
                        structured_logger.log_operation_failure(
                            operation_name,
                            PL5BaseError(str(e), original_error=e) if not isinstance(e, PL5BaseError) else e,
                            duration
                        )
                        raise

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    return RetryContextManager()


class FallbackCache:
    """回退缓存 - 存储最近成功的预测结果用于回退"""

    def __init__(self, max_size: int = 10):
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self.max_size = max_size

    def store(self, key: str, value: Any):
        self._cache[key] = (value, datetime.now())
        if len(self._cache) > self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            return self._cache[key][0]
        return None

    def get_latest(self) -> Optional[Tuple[str, Any]]:
        if not self._cache:
            return None
        latest_key = max(self._cache.keys(), key=lambda k: self._cache[k][1])
        return (latest_key, self._cache[latest_key][0])

    def clear(self):
        self._cache.clear()

    def has(self, key: str) -> bool:
        return key in self._cache


prediction_cache = FallbackCache(max_size=5)


class ConfigSafeLoader:
    """安全配置加载器 - 配置错误时使用默认值并告警"""

    DEFAULT_CONFIG_VALUES = {
        "model_weights": {"stacking": 0.40, "hmm": 0.15, "copula": 0.25, "bayesian": 0.20},
        "training_params": {
            "n_estimators": 30,
            "max_depth": 8,
            "learning_rate": 0.1,
            "random_state": 42
        },
        "scheduler_config": {
            "data_fetch_time": "00:00",
            "evaluation_time": "00:30",
            "optimization_start": "01:00",
            "training_start": "02:00",
            "email_send_time": "17:30"
        },
        "feature_config": {
            "select_top": 100,
            "feature_selection_method": "rfe"
        },
        "network_config": {
            "timeout_connect": 10,
            "timeout_read": 30,
            "max_retries": 3,
            "backoff_factor": 2.0
        }
    }

    @classmethod
    def safe_get(cls, config_dict: Dict, key_path: str,
                 default: Any = None, warn_on_default: bool = True) -> Any:
        """
        安全获取嵌套配置值

        Args:
            config_dict: 配置字典
            key_path: 点分隔的键路径，如 "training_params.n_estimators"
            default: 默认值
            warn_on_default: 使用默认值时是否发出警告

        Returns:
            配置值或默认值
        """
        keys = key_path.split(".")
        current = config_dict

        try:
            for key in keys:
                current = current[key]

            if warn_on_default and default is not None and current is None:
                structured_logger.log_operation_warning(
                    "CONFIG_LOAD",
                    f"Config key '{key_path}' is None, using default value",
                    {"key_path": key_path, "default_value": default}
                )

            return current if current is not None else default

        except (KeyError, TypeError) as e:
            if default is not None:
                if warn_on_default:
                    structured_logger.log_fallback_used(
                        "CONFIG_LOAD",
                        RecoveryStrategy.FALLBACK_TO_DEFAULT,
                        f"Missing config key '{key_path}': {e}, using default: {default}"
                    )
                    logger.warning(
                        f"[ConfigWarning] Key '{key_path}' not found, using default: {default}"
                    )
                return default

            raise ConfigMissingKeyError(
                f"Required configuration key missing: {key_path}",
                config_key=key_path,
                original_error=e
            )

    @classmethod
    def safe_get_with_category(cls, category: str, key: str,
                                config_dict: Dict = None) -> Any:
        """
        从默认配置类别中安全获取值

        Args:
            category: 配置类别名
            key: 类别内的键
            config_dict: 可选的自定义配置（覆盖默认值）
        """
        defaults = cls.DEFAULT_CONFIG_VALUES.get(category, {})
        full_key = f"{category}.{key}"

        if config_dict:
            merged = {**defaults, **config_dict.get(category, {})}
        else:
            merged = defaults

        return cls.safe_get(merged, full_key, defaults.get(key))


def handle_data_load_failure(func: Callable = None, *,
                             max_retries: int = 3,
                             fallback_to_backup: bool = True) -> Callable:
    """数据加载失败处理装饰器 - 重试3次+间隔递增+备份恢复"""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    structured_logger.log_operation_start(
                        StructuredLogger.OPERATION_DATA_FETCH,
                        {"attempt": attempt, "max_retries": max_retries}
                    )
                    start = time.time()
                    result = fn(*args, **kwargs)
                    duration = (time.time() - start) * 1000
                    structured_logger.log_operation_success(
                        StructuredLogger.OPERATION_DATA_FETCH, duration,
                        {"attempt": attempt}
                    )
                    return result
                except (FileNotFoundError, PermissionError, UnicodeDecodeError,
                        OSError, DataError) as e:
                    last_error = e
                    delay = attempt * 2
                    structured_logger.log_recovery_attempt(
                        StructuredLogger.OPERATION_DATA_FETCH,
                        attempt, max_retries,
                        RecoveryStrategy.RETRY_WITH_BACKOFF
                    )
                    logger.warning(
                        f"[DataRetry] Attempt {attempt}/{max_retries} failed: {e}, "
                        f"retrying in {delay}s..."
                    )
                    time.sleep(delay)

            error_msg = f"Data load failed after {max_retries} attempts: {last_error}"
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_DATA_FETCH,
                DataLoadError(error_msg, original_error=last_error)
            )
            raise DataLoadError(error_msg, original_error=last_error)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def handle_model_prediction_failure(func: Callable = None, *,
                                    use_cache: bool = True,
                                    use_simple_strategy: bool = True) -> Callable:
    """模型预测失败处理装饰器 - 回退到缓存结果或简单策略"""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                structured_logger.log_operation_start(
                    StructuredLogger.OPERATION_PREDICTION
                )
                start = time.time()
                result = fn(*args, **kwargs)
                duration = (time.time() - start) * 1000
                structured_logger.log_operation_success(
                    StructuredLogger.OPERATION_PREDICTION, duration
                )

                if use_cache:
                    cache_key = f"pred_{datetime.now().strftime('%Y%m%d%H')}"
                    prediction_cache.store(cache_key, result)

                return result

            except Exception as e:
                if use_cache:
                    cached = prediction_cache.get_latest()
                    if cached:
                        cache_key, cached_result = cached
                        structured_logger.log_fallback_used(
                            StructuredLogger.OPERATION_PREDICTION,
                            RecoveryStrategy.FALLBACK_TO_CACHE,
                            f"Prediction failed ({e}), using cached result from {cache_key}"
                        )
                        logger.warning(f"[ModelFallback] Using cached prediction due to: {e}")
                        return cached_result

                if use_simple_strategy:
                    structured_logger.log_fallback_used(
                        StructuredLogger.OPERATION_PREDICTION,
                        RecoveryStrategy.FALLBACK_TO_SIMPLE_STRATEGY,
                        f"Prediction failed ({e}), using uniform distribution fallback"
                    )
                    logger.warning(f"[ModelFallback] Using simple strategy due to: {e}")
                    return _get_uniform_prediction()

                raise ModelPredictionError(
                    f"Model prediction failed: {e}",
                    operation="predict",
                    original_error=e,
                    severity=ErrorSeverity.ERROR_SEVERITY_HIGH
                )

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def _get_uniform_prediction() -> Dict:
    """生成均匀分布的简单预测结果作为回退"""
    positions = ["wan", "qian", "bai", "shi", "ge"]
    result = {}
    for pos in positions:
        probs = [0.1] * 10
        top_k = list(range(10))[:8]
        result[pos] = {
            "top_k": top_k,
            "probabilities": [0.125] * 8,
            "uncertainty": 1.0,
            "weights_used": {"stacking": 0.25, "hmm": 0.25, "copula": 0.25, "bsts": 0.25},
            "fallback": True
        }
    return result


def handle_network_failure(func: Callable = None, *,
                           max_retries: int = 3,
                           base_delay: float = 2.0,
                           backoff_factor: float = 2.0) -> Callable:
    """网络错误处理装饰器 - 指数退避重试"""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    structured_logger.log_operation_start(
                        StructuredLogger.OPERATION_DATA_FETCH,
                        {"attempt": attempt, "type": "network"}
                    )
                    import requests
                    start = time.time()
                    result = fn(*args, **kwargs)
                    duration = (time.time() - start) * 1000
                    structured_logger.log_operation_success(
                        StructuredLogger.OPERATION_DATA_FETCH, duration
                    )
                    return result
                except (requests.RequestException, TimeoutError,
                        ConnectionError, OSError) as e:
                    last_error = e
                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), 60)
                    structured_logger.log_recovery_attempt(
                        StructuredLogger.OPERATION_DATA_FETCH,
                        attempt, max_retries,
                        RecoveryStrategy.RETRY_WITH_BACKOFF
                    )
                    logger.warning(
                        f"[NetworkRetry] Attempt {attempt}/{max_retries} failed: {e}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)

            error_msg = f"Network request failed after {max_retries} attempts: {last_error}"
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_DATA_FETCH,
                NetworkError(error_msg, original_error=last_error)
            )
            raise NetworkError(error_msg, original_error=last_error)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
