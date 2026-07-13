"""统一错误处理模块测试

测试PL5统一错误处理系统的功能和可靠性。
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils.unified_error_handler import (
    PL5Error, DataError, DataLoadError, DataValidationError, DataParseError,
    ModelError, ModelLoadError, ModelPredictError,
    NetworkError, NetworkTimeoutError, NetworkConnectionError, NetworkHTTPError,
    ConfigError, ApiError, RateLimitError, AuthError, ServerError, ClientError,
    ErrorType, ErrorSeverity, RetryConfig, RetryResult,
    retry_with_backoff, ErrorHandler, handle_error, execute_with_retry, retry_on_failure
)


class TestPL5Error:
    """测试PL5Error基类"""
    
    def test_pl5_error_creation(self):
        """测试PL5Error的创建"""
        error = PL5Error(
            message="Test error",
            error_type=ErrorType.UNKNOWN_ERROR,
            severity=ErrorSeverity.ERROR_SEVERITY_MEDIUM,
            error_code=404,
            context={"test": "context"}
        )
        
        assert error.message == "Test error"
        assert error.error_type == ErrorType.UNKNOWN_ERROR
        assert error.severity == ErrorSeverity.ERROR_SEVERITY_MEDIUM
        assert error.error_code == 404
        assert error.context == {"test": "context"}
    
    def test_pl5_error_to_dict(self):
        """测试PL5Error转换为字典"""
        error = PL5Error(
            message="Test error",
            error_type=ErrorType.UNKNOWN_ERROR,
            severity=ErrorSeverity.ERROR_SEVERITY_MEDIUM
        )
        
        error_dict = error.to_dict()
        assert error_dict["message"] == "Test error"
        assert error_dict["error_type"] == "unknown_error"
        assert error_dict["severity"] == "medium"
    
    def test_pl5_error_str(self):
        """测试PL5Error的字符串表示"""
        error = PL5Error(
            message="Test error",
            error_type=ErrorType.UNKNOWN_ERROR,
            severity=ErrorSeverity.ERROR_SEVERITY_MEDIUM
        )
        
        error_str = str(error)
        assert "Test error" in error_str
        assert "unknown_error" in error_str
        assert "medium" in error_str


class TestDataErrors:
    """测试数据相关错误"""
    
    def test_data_error(self):
        """测试DataError"""
        error = DataError(
            message="Data error",
            data_source="test_source",
            record_count=100
        )
        
        assert error.message == "Data error"
        assert error.error_type == ErrorType.DATA_ERROR
        assert error.data_source == "test_source"
        assert error.record_count == 100
        assert error.context["data_source"] == "test_source"
        assert error.context["record_count"] == 100
    
    def test_data_load_error(self):
        """测试DataLoadError"""
        error = DataLoadError(message="Data load error")
        assert error.message == "Data load error"
        assert error.error_type == ErrorType.DATA_LOAD_ERROR
    
    def test_data_validation_error(self):
        """测试DataValidationError"""
        error = DataValidationError(message="Data validation error")
        assert error.message == "Data validation error"
        assert error.error_type == ErrorType.DATA_VALIDATION_ERROR
    
    def test_data_parse_error(self):
        """测试DataParseError"""
        error = DataParseError(message="Data parse error")
        assert error.message == "Data parse error"
        assert error.error_type == ErrorType.DATA_PARSE_ERROR


class TestModelErrors:
    """测试模型相关错误"""
    
    def test_model_error(self):
        """测试ModelError"""
        error = ModelError(
            message="Model error",
            model_name="test_model",
            operation="predict"
        )
        
        assert error.message == "Model error"
        assert error.error_type == ErrorType.MODEL_ERROR
        assert error.model_name == "test_model"
        assert error.operation == "predict"
        assert error.context["model_name"] == "test_model"
        assert error.context["operation"] == "predict"
    
    def test_model_load_error(self):
        """测试ModelLoadError"""
        error = ModelLoadError(message="Model load error")
        assert error.message == "Model load error"
        assert error.error_type == ErrorType.MODEL_LOAD_ERROR
    
    def test_model_predict_error(self):
        """测试ModelPredictError"""
        error = ModelPredictError(message="Model predict error")
        assert error.message == "Model predict error"
        assert error.error_type == ErrorType.MODEL_PREDICT_ERROR


class TestNetworkErrors:
    """测试网络相关错误"""
    
    def test_network_error(self):
        """测试NetworkError"""
        error = NetworkError(message="Network error")
        assert error.message == "Network error"
        assert error.error_type == ErrorType.NETWORK_ERROR
    
    def test_network_timeout_error(self):
        """测试NetworkTimeoutError"""
        error = NetworkTimeoutError(message="Network timeout error")
        assert error.message == "Network timeout error"
        assert error.error_type == ErrorType.NETWORK_TIMEOUT_ERROR
    
    def test_network_connection_error(self):
        """测试NetworkConnectionError"""
        error = NetworkConnectionError(message="Network connection error")
        assert error.message == "Network connection error"
        assert error.error_type == ErrorType.NETWORK_CONNECTION_ERROR
    
    def test_network_http_error(self):
        """测试NetworkHTTPError"""
        error = NetworkHTTPError(message="Network HTTP error", status_code=500)
        assert error.message == "Network HTTP error"
        assert error.error_type == ErrorType.NETWORK_HTTP_ERROR
        assert error.context["status_code"] == 500


class TestOtherErrors:
    """测试其他错误"""
    
    def test_config_error(self):
        """测试ConfigError"""
        error = ConfigError(
            message="Config error",
            config_key="test_key"
        )
        assert error.message == "Config error"
        assert error.error_type == ErrorType.CONFIG_ERROR
        assert error.config_key == "test_key"
        assert error.context["config_key"] == "test_key"
    
    def test_api_error(self):
        """测试ApiError"""
        error = ApiError(message="API error")
        assert error.message == "API error"
        assert error.error_type == ErrorType.API_ERROR
    
    def test_rate_limit_error(self):
        """测试RateLimitError"""
        error = RateLimitError(message="Rate limit error")
        assert error.message == "Rate limit error"
        assert error.error_type == ErrorType.RATE_LIMIT_ERROR
    
    def test_auth_error(self):
        """测试AuthError"""
        error = AuthError(message="Auth error")
        assert error.message == "Auth error"
        assert error.error_type == ErrorType.AUTH_ERROR
    
    def test_server_error(self):
        """测试ServerError"""
        error = ServerError(message="Server error")
        assert error.message == "Server error"
        assert error.error_type == ErrorType.SERVER_ERROR
    
    def test_client_error(self):
        """测试ClientError"""
        error = ClientError(message="Client error")
        assert error.message == "Client error"
        assert error.error_type == ErrorType.CLIENT_ERROR


class TestRetryFunctionality:
    """测试重试功能"""
    
    def test_retry_with_success(self):
        """测试成功的重试"""
        def success_func():
            return "success"
        
        result = retry_with_backoff(success_func)
        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1
    
    def test_retry_with_retryable_error(self):
        """测试可重试的错误"""
        call_count = 0
        
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Network error")
            return "success"
        
        config = RetryConfig(max_retries=3)
        result = retry_with_backoff(fail_then_succeed, config)
        
        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3
    
    def test_retry_with_non_retryable_error(self):
        """测试不可重试的错误"""
        def fail_with_non_retryable():
            raise DataValidationError("Validation error")
        
        result = retry_with_backoff(fail_with_non_retryable)
        
        assert result.success is False
        assert isinstance(result.error, DataValidationError)
        assert result.attempts == 1
    
    def test_retry_with_max_retries_exceeded(self):
        """测试超过最大重试次数"""
        def always_fail():
            raise NetworkError("Network error")
        
        config = RetryConfig(max_retries=2)
        result = retry_with_backoff(always_fail, config)
        
        assert result.success is False
        assert isinstance(result.error, NetworkError)
        assert result.attempts == 3  # 1 initial attempt + 2 retries


class TestErrorHandler:
    """测试错误处理器"""
    
    def test_handle_pl5_error(self):
        """测试处理PL5Error"""
        error_handler = ErrorHandler()
        original_error = PL5Error("Test error")
        
        handled_error = error_handler.handle_error(original_error)
        assert handled_error is original_error
    
    def test_handle_generic_exception(self):
        """测试处理普通异常"""
        error_handler = ErrorHandler()
        original_error = ValueError("Value error")
        
        handled_error = error_handler.handle_error(original_error)
        assert isinstance(handled_error, PL5Error)
        assert handled_error.error_type == ErrorType.UNKNOWN_ERROR
    
    def test_execute_with_retry(self):
        """测试执行带重试的函数"""
        error_handler = ErrorHandler()
        
        def success_func():
            return "success"
        
        result = error_handler.execute_with_retry(success_func)
        assert result.success is True
        assert result.result == "success"


class TestDecorators:
    """测试装饰器"""
    
    def test_retry_on_failure_decorator(self):
        """测试retry_on_failure装饰器"""
        call_count = 0
        
        @retry_on_failure(max_retries=2)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Test error")
            return "success"
        
        result = fail_then_succeed()
        assert result == "success"
        assert call_count == 3
    
    def test_retry_on_failure_decorator_max_retries(self):
        """测试retry_on_failure装饰器达到最大重试次数"""
        call_count = 0
        
        @retry_on_failure(max_retries=2)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("Test error")
        
        with pytest.raises(Exception):
            always_fail()
        assert call_count == 3


class TestUtilityFunctions:
    """测试工具函数"""
    
    def test_handle_error_function(self):
        """测试handle_error函数"""
        error = ValueError("Value error")
        handled_error = handle_error(error)
        assert isinstance(handled_error, PL5Error)
    
    def test_execute_with_retry_function(self):
        """测试execute_with_retry函数"""
        def success_func():
            return "success"
        
        result = execute_with_retry(success_func)
        assert result.success is True
        assert result.result == "success"


if __name__ == "__main__":
    pytest.main([__file__])
