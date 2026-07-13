"""安全加固

提供AI工具系统的安全功能，包括输入验证、权限控制、敏感信息保护等。
"""

import re
import hashlib
import secrets
import string
import os
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class InputValidator:
    """输入验证器
    
    用于验证和清理用户输入，防止注入攻击。
    """
    
    @staticmethod
    def validate_string(value: str, max_length: int = 1000, allow_empty: bool = False) -> bool:
        """验证字符串
        
        Args:
            value: 字符串值
            max_length: 最大长度
            allow_empty: 是否允许空字符串
            
        Returns:
            是否有效
        """
        if not isinstance(value, str):
            return False
        
        if not allow_empty and not value:
            return False
        
        if len(value) > max_length:
            return False
        
        return True
    
    @staticmethod
    def validate_integer(value: int, min_value: Optional[int] = None, max_value: Optional[int] = None) -> bool:
        """验证整数
        
        Args:
            value: 整数值
            min_value: 最小值
            max_value: 最大值
            
        Returns:
            是否有效
        """
        if not isinstance(value, int):
            return False
        
        if min_value is not None and value < min_value:
            return False
        
        if max_value is not None and value > max_value:
            return False
        
        return True
    
    @staticmethod
    def validate_float(value: float, min_value: Optional[float] = None, max_value: Optional[float] = None) -> bool:
        """验证浮点数
        
        Args:
            value: 浮点数值
            min_value: 最小值
            max_value: 最大值
            
        Returns:
            是否有效
        """
        if not isinstance(value, (int, float)):
            return False
        
        if min_value is not None and value < min_value:
            return False
        
        if max_value is not None and value > max_value:
            return False
        
        return True
    
    @staticmethod
    def validate_boolean(value: bool) -> bool:
        """验证布尔值
        
        Args:
            value: 布尔值
            
        Returns:
            是否有效
        """
        return isinstance(value, bool)
    
    @staticmethod
    def validate_list(value: list, min_length: int = 0, max_length: int = 100) -> bool:
        """验证列表
        
        Args:
            value: 列表
            min_length: 最小长度
            max_length: 最大长度
            
        Returns:
            是否有效
        """
        if not isinstance(value, list):
            return False
        
        if len(value) < min_length:
            return False
        
        if len(value) > max_length:
            return False
        
        return True
    
    @staticmethod
    def validate_dict(value: dict, required_keys: Optional[List[str]] = None) -> bool:
        """验证字典
        
        Args:
            value: 字典
            required_keys: 必需的键
            
        Returns:
            是否有效
        """
        if not isinstance(value, dict):
            return False
        
        if required_keys:
            for key in required_keys:
                if key not in value:
                    return False
        
        return True
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """清理字符串
        
        Args:
            value: 字符串
            
        Returns:
            清理后的字符串
        """
        if not isinstance(value, str):
            return str(value)
        
        # 移除危险字符
        dangerous_chars = [';', '\'', '"', '`', '$', '|', '&', '>', '<', '!', '\\']
        for char in dangerous_chars:
            value = value.replace(char, '')
        
        # 移除多余的空白字符
        value = ' '.join(value.split())
        
        return value
    
    @staticmethod
    def validate_email(value: str) -> bool:
        """验证邮箱格式
        
        Args:
            value: 邮箱地址
            
        Returns:
            是否有效
        """
        if not isinstance(value, str):
            return False
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, value) is not None
    
    @staticmethod
    def validate_url(value: str) -> bool:
        """验证URL格式
        
        Args:
            value: URL地址
            
        Returns:
            是否有效
        """
        if not isinstance(value, str):
            return False
        
        url_pattern = r'^https?://[^\s]+$'
        return re.match(url_pattern, value) is not None
    
    @staticmethod
    def validate_ip_address(value: str) -> bool:
        """验证IP地址格式
        
        Args:
            value: IP地址
            
        Returns:
            是否有效
        """
        if not isinstance(value, str):
            return False
        
        # IPv4 正则
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ipv4_pattern, value):
            parts = value.split('.')
            return all(0 <= int(part) <= 255 for part in parts)
        
        # IPv6 正则（简化版）
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        return re.match(ipv6_pattern, value) is not None
    
    @staticmethod
    def validate_password_strength(value: str) -> tuple[bool, Optional[str]]:
        """验证密码强度
        
        Args:
            value: 密码
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(value, str):
            return False, "Password must be a string"
        
        if len(value) < 12:
            return False, "Password must be at least 12 characters long"
        
        if not re.search(r'[A-Z]', value):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', value):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'[0-9]', value):
            return False, "Password must contain at least one digit"
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            return False, "Password must contain at least one special character"
        
        return True, None
    
    @staticmethod
    def validate_username(value: str) -> tuple[bool, Optional[str]]:
        """验证用户名格式
        
        Args:
            value: 用户名
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(value, str):
            return False, "Username must be a string"
        
        if len(value) < 3:
            return False, "Username must be at least 3 characters long"
        
        if len(value) > 32:
            return False, "Username must be at most 32 characters long"
        
        # 只允许字母、数字和下划线
        if not re.match(r'^[a-zA-Z0-9_]+$', value):
            return False, "Username can only contain letters, numbers, and underscores"
        
        return True, None
    
    @staticmethod
    def detect_sql_injection(value: str) -> bool:
        """检测SQL注入攻击
        
        Args:
            value: 输入字符串
            
        Returns:
            是否检测到SQL注入
        """
        if not isinstance(value, str):
            return False
        
        sql_patterns = [
            r'\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b',
            r'\b(OR|AND)\s+\d+\s*=\s*\d+',
            r'\bUNION\s+SELECT\b',
            r'\b--\b',
            r'\b;\b',
            r'\b\'\b',
            r'\b\"\b',
            r'\bEXEC\b',
            r'\bEXECUTE\b',
            r'\bXP_\w+\b',
            r'\bsp_\w+\b'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def detect_xss(value: str) -> bool:
        """检测XSS攻击
        
        Args:
            value: 输入字符串
            
        Returns:
            是否检测到XSS攻击
        """
        if not isinstance(value, str):
            return False
        
        xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>',
            r'<img[^>]*onerror=',
            r'<svg[^>]*onload=',
            r'data:text/html',
            r'vbscript:',
            r'mshtml:'
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def detect_command_injection(value: str) -> bool:
        """检测命令注入攻击
        
        Args:
            value: 输入字符串
            
        Returns:
            是否检测到命令注入
        """
        if not isinstance(value, str):
            return False
        
        cmd_patterns = [
            r'\b(bash|sh|cmd|powershell|python|perl|ruby|php)\b',
            r'\b(echo|cat|ls|dir|rm|del|mkdir|touch|chmod|chown)\b',
            r'\b(\|\||\&\&|;|\`|\$\()\b',
            r'\b(wget|curl|nc|netcat|telnet)\b',
            r'\b(/bin/|/usr/bin/|/usr/local/bin/)\b'
        ]
        
        for pattern in cmd_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def validate_json(value: str) -> tuple[bool, Optional[str]]:
        """验证JSON格式
        
        Args:
            value: JSON字符串
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(value, str):
            return False, "Input must be a string"
        
        try:
            import json
            json.loads(value)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
    
    @staticmethod
    def validate_numeric_range(value: float, min_value: float, max_value: float) -> tuple[bool, Optional[str]]:
        """验证数值范围
        
        Args:
            value: 数值
            min_value: 最小值
            max_value: 最大值
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(value, (int, float)):
            return False, "Value must be a number"
        
        if value < min_value:
            return False, f"Value must be greater than or equal to {min_value}"
        
        if value > max_value:
            return False, f"Value must be less than or equal to {max_value}"
        
        return True, None
    
    @staticmethod
    def validate_and_sanitize(value: Any, expected_type: str, **kwargs) -> tuple[Any, Optional[str]]:
        """验证并清理输入
        
        Args:
            value: 输入值
            expected_type: 期望类型 (string, integer, float, boolean, list, dict, email, url, ip)
            **kwargs: 额外参数
            
        Returns:
            (清理后的值, 错误信息)
        """
        # 类型验证
        if expected_type == "string":
            if not isinstance(value, str):
                return None, "Expected string type"
            max_length = kwargs.get("max_length", 1000)
            if len(value) > max_length:
                return None, f"String exceeds maximum length of {max_length}"
            
            # 检测攻击
            if InputValidator.detect_sql_injection(value):
                return None, "Potential SQL injection detected"
            if InputValidator.detect_xss(value):
                return None, "Potential XSS attack detected"
            if InputValidator.detect_command_injection(value):
                return None, "Potential command injection detected"
            
            # 清理字符串
            return InputValidator.sanitize_string(value), None
        
        elif expected_type == "integer":
            if not isinstance(value, int):
                return None, "Expected integer type"
            min_value = kwargs.get("min_value")
            max_value = kwargs.get("max_value")
            if min_value is not None and value < min_value:
                return None, f"Value must be at least {min_value}"
            if max_value is not None and value > max_value:
                return None, f"Value must be at most {max_value}"
            return value, None
        
        elif expected_type == "float":
            if not isinstance(value, (int, float)):
                return None, "Expected float type"
            min_value = kwargs.get("min_value")
            max_value = kwargs.get("max_value")
            if min_value is not None and value < min_value:
                return None, f"Value must be at least {min_value}"
            if max_value is not None and value > max_value:
                return None, f"Value must be at most {max_value}"
            return float(value), None
        
        elif expected_type == "boolean":
            if not isinstance(value, bool):
                return None, "Expected boolean type"
            return value, None
        
        elif expected_type == "list":
            if not isinstance(value, list):
                return None, "Expected list type"
            max_length = kwargs.get("max_length", 100)
            if len(value) > max_length:
                return None, f"List exceeds maximum length of {max_length}"
            return value, None
        
        elif expected_type == "dict":
            if not isinstance(value, dict):
                return None, "Expected dict type"
            required_keys = kwargs.get("required_keys", [])
            for key in required_keys:
                if key not in value:
                    return None, f"Missing required key: {key}"
            return value, None
        
        elif expected_type == "email":
            if not InputValidator.validate_email(value):
                return None, "Invalid email format"
            return value.lower(), None
        
        elif expected_type == "url":
            if not InputValidator.validate_url(value):
                return None, "Invalid URL format"
            return value, None
        
        elif expected_type == "ip":
            if not InputValidator.validate_ip_address(value):
                return None, "Invalid IP address format"
            return value, None
        
        else:
            return None, f"Unknown type: {expected_type}"
    
    @staticmethod
    def validate_tool_parameters(parameters: Dict[str, Any], tool_schema: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证工具参数
        
        Args:
            parameters: 工具参数
            tool_schema: 工具参数 schema
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(parameters, dict):
            return False, "Parameters must be a dictionary"
        
        # 检查必需参数
        required = tool_schema.get("required", [])
        for param_name in required:
            if param_name not in parameters:
                return False, f"Missing required parameter: {param_name}"
        
        # 检查参数类型
        properties = tool_schema.get("properties", {})
        for param_name, param_value in parameters.items():
            if param_name in properties:
                param_schema = properties[param_name]
                param_type = param_schema.get("type")
                
                if param_type == "string" and not isinstance(param_value, str):
                    return False, f"Parameter {param_name} must be a string"
                elif param_type == "integer" and not isinstance(param_value, int):
                    return False, f"Parameter {param_name} must be an integer"
                elif param_type == "number" and not isinstance(param_value, (int, float)):
                    return False, f"Parameter {param_name} must be a number"
                elif param_type == "boolean" and not isinstance(param_value, bool):
                    return False, f"Parameter {param_name} must be a boolean"
                elif param_type == "array" and not isinstance(param_value, list):
                    return False, f"Parameter {param_name} must be a list"
                elif param_type == "object" and not isinstance(param_value, dict):
                    return False, f"Parameter {param_name} must be a dictionary"
        
        return True, None


class PermissionManager:
    """权限管理器
    
    用于管理工具系统的权限。
    """
    
    def __init__(self):
        """初始化权限管理器"""
        self.permissions = {
            "admin": ["*"],  # 管理员拥有所有权限
            "user": ["calculator", "search", "file"],  # 普通用户只能使用基础工具
            "guest": ["calculator"]  # 访客只能使用计算器
        }
        # 资源权限映射
        self.resource_permissions = {
            "workflow": {
                "admin": ["create", "run", "list", "resume", "delete"],
                "user": ["create", "run", "list"],
                "guest": []
            },
            "template": {
                "admin": ["save", "load", "list", "delete"],
                "user": ["load", "list"],
                "guest": []
            },
            "memory": {
                "admin": ["create", "add", "get"],
                "user": ["create", "add", "get"],
                "guest": []
            }
        }
    
    def has_permission(self, role: str, tool_name: str) -> bool:
        """检查用户是否有使用工具的权限
        
        Args:
            role: 用户角色
            tool_name: 工具名称
            
        Returns:
            是否有权限
        """
        if role not in self.permissions:
            return False
        
        # 检查是否有通配符权限
        if "*" in self.permissions[role]:
            return True
        
        return tool_name in self.permissions[role]
    
    def has_resource_permission(self, role: str, resource: str, action: str) -> bool:
        """检查用户是否有操作资源的权限
        
        Args:
            role: 用户角色
            resource: 资源类型
            action: 操作类型
            
        Returns:
            是否有权限
        """
        if role not in self.permissions:
            return False
        
        # 检查是否有通配符权限
        if "*" in self.permissions[role]:
            return True
        
        # 检查资源权限
        if resource in self.resource_permissions:
            resource_actions = self.resource_permissions[resource].get(role, [])
            return action in resource_actions
        
        return False
    
    def add_permission(self, role: str, tool_name: str) -> None:
        """添加权限
        
        Args:
            role: 用户角色
            tool_name: 工具名称
        """
        if role not in self.permissions:
            self.permissions[role] = []
        
        if tool_name not in self.permissions[role]:
            self.permissions[role].append(tool_name)
    
    def add_resource_permission(self, role: str, resource: str, action: str) -> None:
        """添加资源权限
        
        Args:
            role: 用户角色
            resource: 资源类型
            action: 操作类型
        """
        if resource not in self.resource_permissions:
            self.resource_permissions[resource] = {}
        
        if role not in self.resource_permissions[resource]:
            self.resource_permissions[resource][role] = []
        
        if action not in self.resource_permissions[resource][role]:
            self.resource_permissions[resource][role].append(action)
    
    def remove_permission(self, role: str, tool_name: str) -> None:
        """移除权限
        
        Args:
            role: 用户角色
            tool_name: 工具名称
        """
        if role in self.permissions and tool_name in self.permissions[role]:
            self.permissions[role].remove(tool_name)
    
    def remove_resource_permission(self, role: str, resource: str, action: str) -> None:
        """移除资源权限
        
        Args:
            role: 用户角色
            resource: 资源类型
            action: 操作类型
        """
        if (resource in self.resource_permissions and 
            role in self.resource_permissions[resource] and 
            action in self.resource_permissions[resource][role]):
            self.resource_permissions[resource][role].remove(action)
    
    def list_permissions(self, role: str) -> List[str]:
        """列出角色的所有权限
        
        Args:
            role: 用户角色
            
        Returns:
            权限列表
        """
        if role not in self.permissions:
            return []
        
        return self.permissions[role]
    
    def list_resource_permissions(self, role: str) -> Dict[str, List[str]]:
        """列出角色的所有资源权限
        
        Args:
            role: 用户角色
            
        Returns:
            资源权限映射
        """
        if role not in self.permissions:
            return {}
        
        # 检查是否有通配符权限
        if "*" in self.permissions[role]:
            return {resource: ["*"] for resource in self.resource_permissions}
        
        resource_perms = {}
        for resource, actions in self.resource_permissions.items():
            if role in actions:
                resource_perms[resource] = actions[role]
        
        return resource_perms


class SecretsManager:
    """密钥管理器
    
    用于管理敏感信息，如API密钥等。
    """
    
    def __init__(self):
        """初始化密钥管理器"""
        self.secrets = {}
        self._salt = self._generate_salt()
        self._encryption_key = self._generate_encryption_key()
    
    def _generate_salt(self) -> str:
        """生成盐值
        
        Returns:
            盐值
        """
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    def _generate_encryption_key(self) -> bytes:
        """生成加密密钥
        
        Returns:
            加密密钥
        """
        return hashlib.sha256(self._salt.encode()).digest()
    
    def _hash_key(self, key: str) -> str:
        """哈希密钥
        
        Args:
            key: 密钥
            
        Returns:
            哈希值
        """
        combined = key + self._salt
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _encrypt(self, value: str) -> str:
        """加密值
        
        Args:
            value: 原始值
            
        Returns:
            加密后的值
        """
        import base64
        from cryptography.fernet import Fernet
        
        # 使用密钥派生函数生成Fernet密钥
        fernet_key = base64.urlsafe_b64encode(self._encryption_key)
        fernet = Fernet(fernet_key)
        
        # 加密数据
        encrypted = fernet.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()
    
    def _decrypt(self, encrypted_value: str) -> str:
        """解密值
        
        Args:
            encrypted_value: 加密后的值
            
        Returns:
            原始值
        """
        import base64
        from cryptography.fernet import Fernet
        
        try:
            # 使用密钥派生函数生成Fernet密钥
            fernet_key = base64.urlsafe_b64encode(self._encryption_key)
            fernet = Fernet(fernet_key)
            
            # 解密数据
            encrypted = base64.b64decode(encrypted_value.encode())
            decrypted = fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception:
            return ""
    
    def set_secret(self, name: str, value: str) -> None:
        """设置密钥
        
        Args:
            name: 密钥名称
            value: 密钥值
        """
        hashed_name = self._hash_key(name)
        encrypted_value = self._encrypt(value)
        self.secrets[hashed_name] = encrypted_value
    
    def get_secret(self, name: str) -> Optional[str]:
        """获取密钥
        
        Args:
            name: 密钥名称
            
        Returns:
            密钥值，如果不存在返回None
        """
        hashed_name = self._hash_key(name)
        encrypted_value = self.secrets.get(hashed_name)
        if encrypted_value:
            return self._decrypt(encrypted_value)
        return None
    
    def delete_secret(self, name: str) -> bool:
        """删除密钥
        
        Args:
            name: 密钥名称
            
        Returns:
            是否删除成功
        """
        hashed_name = self._hash_key(name)
        if hashed_name in self.secrets:
            del self.secrets[hashed_name]
            return True
        return False
    
    def clear_secrets(self) -> None:
        """清空所有密钥"""
        self.secrets.clear()
    
    def mask_secret(self, value: str, show_chars: int = 4) -> str:
        """掩码密钥
        
        Args:
            value: 密钥值
            show_chars: 显示的字符数
            
        Returns:
            掩码后的字符串
        """
        if not value:
            return ""
        
        if len(value) <= show_chars:
            return "*" * len(value)
        
        return value[:show_chars] + "*" * (len(value) - show_chars)
    
    def export_secrets(self, password: str) -> str:
        """导出密钥（加密格式）
        
        Args:
            password: 导出密码
            
        Returns:
            加密后的密钥数据
        """
        import json
        import base64
        from cryptography.fernet import Fernet
        
        # 使用密码生成导出密钥
        export_key = hashlib.sha256(password.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(export_key)
        fernet = Fernet(fernet_key)
        
        # 序列化密钥数据
        secrets_data = json.dumps(self.secrets)
        encrypted_data = fernet.encrypt(secrets_data.encode())
        
        return base64.b64encode(encrypted_data).decode()
    
    def import_secrets(self, encrypted_data: str, password: str) -> bool:
        """导入密钥
        
        Args:
            encrypted_data: 加密的密钥数据
            password: 导入密码
            
        Returns:
            是否导入成功
        """
        import json
        import base64
        from cryptography.fernet import Fernet
        
        try:
            # 使用密码生成导出密钥
            export_key = hashlib.sha256(password.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(export_key)
            fernet = Fernet(fernet_key)
            
            # 解密数据
            encrypted = base64.b64decode(encrypted_data.encode())
            decrypted_data = fernet.decrypt(encrypted)
            secrets_data = json.loads(decrypted_data.decode())
            
            # 更新密钥
            self.secrets.update(secrets_data)
            return True
        except Exception:
            return False


class SecurityAuditor:
    """安全审计器
    
    用于记录安全相关的事件。
    """
    
    # 事件类型常量
    EVENT_LOGIN = "login"
    EVENT_LOGIN_FAILED = "login_failed"
    EVENT_LOGOUT = "logout"
    EVENT_PERMISSION_CHANGE = "permission_change"
    EVENT_TOOL_EXECUTION = "tool_execution"
    EVENT_TOOL_EXECUTION_FAILED = "tool_execution_failed"
    EVENT_ERROR = "error"
    EVENT_SENSITIVE_OPERATION = "sensitive_operation"
    EVENT_DATA_ACCESS = "data_access"
    EVENT_SESSION_CREATE = "session_create"
    EVENT_SESSION_INVALIDATE = "session_invalidate"
    EVENT_CONFIG_CHANGE = "config_change"
    EVENT_MODEL_ACCESS = "model_access"
    EVENT_BACKUP_RESTORE = "backup_restore"
    
    def __init__(self, log_file: Optional[str] = None, max_logs: int = 100000):
        """初始化安全审计器
        
        Args:
            log_file: 日志文件路径
            max_logs: 最大日志条数（超过后自动清理旧日志）
        """
        self.audit_logs = []
        self.log_file = log_file
        self.max_logs = max_logs
        # 加载历史日志
        if log_file and os.path.exists(log_file):
            self._load_logs()
    
    def _load_logs(self) -> None:
        """加载历史日志"""
        try:
            import json
            with open(self.log_file, "r", encoding="utf-8") as f:
                self.audit_logs = json.load(f)
            # 确保不超过最大日志数
            if len(self.audit_logs) > self.max_logs:
                self.audit_logs = self.audit_logs[-self.max_logs:]
        except Exception as e:
            logger.error(f"Failed to load audit logs: {e}")
    
    def _save_logs(self) -> None:
        """保存日志到文件"""
        if self.log_file:
            try:
                import json
                # 确保目录存在
                log_dir = os.path.dirname(self.log_file)
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)
                with open(self.log_file, "w", encoding="utf-8") as f:
                    json.dump(self.audit_logs, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Failed to save audit logs: {e}")
    
    def _clean_old_logs(self, days_to_keep: int = 90) -> None:
        """清理指定天数之前的日志
        
        Args:
            days_to_keep: 保留的天数
        """
        import time
        cutoff_time = time.time() - (days_to_keep * 24 * 3600)
        original_count = len(self.audit_logs)
        self.audit_logs = [log for log in self.audit_logs if log["timestamp"] >= cutoff_time]
        removed_count = original_count - len(self.audit_logs)
        if removed_count > 0:
            logger.info(f"Cleaned {removed_count} old audit logs")
    
    def _create_log_entry(self, event_type: str, user: str, action: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """创建日志条目
        
        Args:
            event_type: 事件类型
            user: 用户
            action: 操作
            details: 详细信息
            
        Returns:
            日志条目
        """
        import time
        import socket
        
        return {
            "timestamp": time.time(),
            "event_type": event_type,
            "user": user,
            "action": action,
            "details": details,
            "ip_address": self._get_client_ip(),
            "process_id": os.getpid(),
            "hostname": socket.gethostname()
        }
    
    def _get_client_ip(self) -> str:
        """获取客户端IP地址"""
        import socket
        try:
            # 尝试获取外部IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(("8.8.8.8", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return socket.gethostbyname(socket.gethostname())
    
    def log_event(self, event_type: str, user: str, action: str, details: Dict[str, Any]) -> None:
        """记录安全事件
        
        Args:
            event_type: 事件类型 (login, logout, tool_execution, error, etc.)
            user: 用户
            action: 操作
            details: 详细信息
        """
        # 创建日志条目
        log_entry = self._create_log_entry(event_type, user, action, details)
        
        # 添加到日志列表
        self.audit_logs.append(log_entry)
        
        # 记录到应用日志
        logger.info(f"Security event: {event_type} - {action} by {user} from {log_entry['ip_address']}")
        
        # 检查日志数量并清理旧日志
        if len(self.audit_logs) > self.max_logs:
            self._clean_old_logs()
        
        # 保存日志到文件
        self._save_logs()
    
    def log_login(self, user: str, success: bool, ip_address: str = None, reason: str = None) -> None:
        """记录登录事件
        
        Args:
            user: 用户
            success: 是否成功
            ip_address: IP地址
            reason: 失败原因（如果失败）
        """
        event_type = self.EVENT_LOGIN if success else self.EVENT_LOGIN_FAILED
        details = {
            "success": success,
            "ip_address": ip_address or self._get_client_ip()
        }
        if reason:
            details["reason"] = reason
        
        self.log_event(event_type, user, "login", details)
    
    def log_logout(self, user: str) -> None:
        """记录登出事件
        
        Args:
            user: 用户
        """
        self.log_event(self.EVENT_LOGOUT, user, "logout", {})
    
    def log_permission_change(self, user: str, role: str, action: str, details: Dict[str, Any]) -> None:
        """记录权限变更事件
        
        Args:
            user: 用户
            role: 角色
            action: 操作 (add, remove, update)
            details: 详细信息
        """
        log_details = {"role": role, "action": action}
        log_details.update(details)
        self.log_event(self.EVENT_PERMISSION_CHANGE, user, f"permission_{action}", log_details)
    
    def log_tool_execution(self, user: str, tool_name: str, success: bool, parameters: Dict[str, Any] = None, error: str = None) -> None:
        """记录工具执行事件
        
        Args:
            user: 用户
            tool_name: 工具名称
            success: 是否成功
            parameters: 参数
            error: 错误信息
        """
        event_type = self.EVENT_TOOL_EXECUTION if success else self.EVENT_TOOL_EXECUTION_FAILED
        details = {
            "tool_name": tool_name,
            "success": success
        }
        if parameters:
            # 脱敏处理敏感参数
            sanitized_params = {}
            for key, value in parameters.items():
                if key.lower() in ["password", "secret", "token", "api_key"]:
                    sanitized_params[key] = "***"
                else:
                    sanitized_params[key] = value
            details["parameters"] = sanitized_params
        if error:
            details["error"] = error
        
        action = f"execute_tool_{tool_name}"
        self.log_event(event_type, user, action, details)
    
    def log_error(self, user: str, error_type: str, message: str, stack_trace: str = None) -> None:
        """记录错误事件
        
        Args:
            user: 用户
            error_type: 错误类型
            message: 错误消息
            stack_trace: 堆栈跟踪
        """
        details = {
            "error_type": error_type,
            "message": message
        }
        if stack_trace:
            details["stack_trace"] = stack_trace
        
        self.log_event(self.EVENT_ERROR, user, "error", details)
    
    def log_sensitive_operation(self, user: str, operation: str, resource: str, success: bool, details: Dict[str, Any] = None) -> None:
        """记录敏感操作事件
        
        Args:
            user: 用户
            operation: 操作类型
            resource: 资源
            success: 是否成功
            details: 详细信息
        """
        log_details = {
            "operation": operation,
            "resource": resource,
            "success": success
        }
        if details:
            log_details.update(details)
        
        self.log_event(self.EVENT_SENSITIVE_OPERATION, user, operation, log_details)
    
    def log_data_access(self, user: str, data_type: str, action: str, success: bool, details: Dict[str, Any] = None) -> None:
        """记录数据访问事件
        
        Args:
            user: 用户
            data_type: 数据类型
            action: 操作 (read, write, delete)
            success: 是否成功
            details: 详细信息
        """
        log_details = {
            "data_type": data_type,
            "action": action,
            "success": success
        }
        if details:
            log_details.update(details)
        
        self.log_event(self.EVENT_DATA_ACCESS, user, f"data_{action}", log_details)
    
    def log_config_change(self, user: str, config_key: str, old_value: Any, new_value: Any) -> None:
        """记录配置变更事件
        
        Args:
            user: 用户
            config_key: 配置键
            old_value: 旧值
            new_value: 新值
        """
        # 脱敏处理敏感配置
        if config_key.lower() in ["password", "secret", "token", "api_key"]:
            old_value = "***"
            new_value = "***"
        
        details = {
            "config_key": config_key,
            "old_value": old_value,
            "new_value": new_value
        }
        
        self.log_event(self.EVENT_CONFIG_CHANGE, user, "config_change", details)
    
    def log_model_access(self, user: str, model_name: str, action: str, success: bool, details: Dict[str, Any] = None) -> None:
        """记录模型访问事件
        
        Args:
            user: 用户
            model_name: 模型名称
            action: 操作 (load, save, train, predict)
            success: 是否成功
            details: 详细信息
        """
        log_details = {
            "model_name": model_name,
            "action": action,
            "success": success
        }
        if details:
            log_details.update(details)
        
        self.log_event(self.EVENT_MODEL_ACCESS, user, f"model_{action}", log_details)
    
    def get_logs(self, event_type: Optional[str] = None, user: Optional[str] = None, 
                start_time: Optional[float] = None, end_time: Optional[float] = None, 
                limit: int = 100) -> List[Dict[str, Any]]:
        """获取审计日志
        
        Args:
            event_type: 事件类型，None表示所有类型
            user: 用户，None表示所有用户
            start_time: 开始时间戳
            end_time: 结束时间戳
            limit: 限制数量
            
        Returns:
            审计日志列表
        """
        logs = self.audit_logs
        
        # 过滤日志
        if event_type:
            logs = [log for log in logs if log["event_type"] == event_type]
        
        if user:
            logs = [log for log in logs if log["user"] == user]
        
        if start_time:
            logs = [log for log in logs if log["timestamp"] >= start_time]
        
        if end_time:
            logs = [log for log in logs if log["timestamp"] <= end_time]
        
        return logs[-limit:]
    
    def get_event_statistics(self, days: int = 7) -> Dict[str, Any]:
        """获取事件统计信息
        
        Args:
            days: 统计天数
            
        Returns:
            事件统计信息
        """
        import time
        import collections
        
        start_time = time.time() - (days * 24 * 3600)
        recent_logs = [log for log in self.audit_logs if log["timestamp"] >= start_time]
        
        # 统计事件类型
        event_counts = collections.Counter([log["event_type"] for log in recent_logs])
        
        # 统计用户活动
        user_counts = collections.Counter([log["user"] for log in recent_logs])
        
        # 统计操作
        action_counts = collections.Counter([log["action"] for log in recent_logs])
        
        return {
            "total_events": len(recent_logs),
            "event_counts": dict(event_counts),
            "user_counts": dict(user_counts),
            "action_counts": dict(action_counts),
            "time_range": {
                "start": start_time,
                "end": time.time()
            }
        }
    
    def detect_anomalies(self, threshold: int = 100) -> List[Dict[str, Any]]:
        """检测异常活动
        
        Args:
            threshold: 异常阈值
            
        Returns:
            异常事件列表
        """
        import time
        import collections
        
        # 检查最近1小时的事件
        start_time = time.time() - 3600
        recent_logs = [log for log in self.audit_logs if log["timestamp"] >= start_time]
        
        # 按IP地址统计事件数
        ip_counts = collections.Counter([log.get("ip_address", "unknown") for log in recent_logs])
        
        # 按用户统计事件数
        user_counts = collections.Counter([log["user"] for log in recent_logs])
        
        # 检测异常
        anomalies = []
        
        # IP地址异常
        for ip, count in ip_counts.items():
            if count > threshold:
                anomalies.append({
                    "type": "ip_anomaly",
                    "ip": ip,
                    "count": count,
                    "message": f"IP {ip} generated {count} events in the last hour"
                })
        
        # 用户活动异常
        for user, count in user_counts.items():
            if count > threshold:
                anomalies.append({
                    "type": "user_anomaly",
                    "user": user,
                    "count": count,
                    "message": f"User {user} generated {count} events in the last hour"
                })
        
        return anomalies
    
    def clear_logs(self) -> None:
        """清空审计日志"""
        self.audit_logs.clear()
        self._save_logs()


class AntiDosProtection:
    """防DoS保护
    
    用于防止DoS攻击。
    """
    
    def __init__(self, max_requests: int = 100, window: int = 60):
        """初始化防DoS保护
        
        Args:
            max_requests: 时间窗口内的最大请求数
            window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.window = window
        self.requests = {}
    
    def check_request(self, ip: str) -> bool:
        """检查请求是否允许
        
        Args:
            ip: 请求IP
            
        Returns:
            是否允许请求
        """
        import time
        
        now = time.time()
        
        # 清理过期的请求记录
        if ip in self.requests:
            self.requests[ip] = [t for t in self.requests[ip] if now - t < self.window]
        
        # 检查请求数
        if ip not in self.requests:
            self.requests[ip] = []
        
        if len(self.requests[ip]) >= self.max_requests:
            return False
        
        # 记录请求
        self.requests[ip].append(now)
        return True
    
    def get_request_count(self, ip: str) -> int:
        """获取IP的请求数
        
        Args:
            ip: 请求IP
            
        Returns:
            请求数
        """
        import time
        
        now = time.time()
        
        if ip in self.requests:
            self.requests[ip] = [t for t in self.requests[ip] if now - t < self.window]
            return len(self.requests[ip])
        
        return 0


class VulnerabilityScanner:
    """漏洞扫描器
    
    用于扫描系统中的安全漏洞。
    """
    
    def __init__(self):
        """初始化漏洞扫描器"""
        self.vulnerabilities = []
    
    def scan_input_validation(self, input_data: Any) -> List[Dict[str, Any]]:
        """扫描输入验证漏洞
        
        Args:
            input_data: 输入数据
            
        Returns:
            漏洞列表
        """
        vulnerabilities = []
        
        # 检查字符串长度
        if isinstance(input_data, str) and len(input_data) > 1000:
            vulnerabilities.append({
                "type": "input_validation",
                "severity": "medium",
                "message": "Input string too long",
                "details": {"length": len(input_data), "limit": 1000}
            })
        
        # 检查SQL注入
        if isinstance(input_data, str) and any(pattern in input_data.lower() for pattern in ["union select", "drop table", "insert into"]):
            vulnerabilities.append({
                "type": "sql_injection",
                "severity": "high",
                "message": "Potential SQL injection",
                "details": {"input": input_data[:100]}
            })
        
        # 检查XSS
        if isinstance(input_data, str) and any(pattern in input_data.lower() for pattern in ["<script>", "javascript:", "onerror="]):
            vulnerabilities.append({
                "type": "xss",
                "severity": "high",
                "message": "Potential XSS attack",
                "details": {"input": input_data[:100]}
            })
        
        self.vulnerabilities.extend(vulnerabilities)
        return vulnerabilities
    
    def scan_config(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """扫描配置漏洞
        
        Args:
            config: 配置数据
            
        Returns:
            漏洞列表
        """
        vulnerabilities = []
        
        # 检查调试模式
        if config.get("debug", False):
            vulnerabilities.append({
                "type": "config",
                "severity": "medium",
                "message": "Debug mode is enabled",
                "details": {"setting": "debug", "value": True}
            })
        
        # 检查密钥配置
        if "secret" in config and len(config["secret"]) < 8:
            vulnerabilities.append({
                "type": "config",
                "severity": "high",
                "message": "Weak secret key",
                "details": {"setting": "secret", "length": len(config["secret"])}
            })
        
        self.vulnerabilities.extend(vulnerabilities)
        return vulnerabilities
    
    def scan_filesystem(self, directory: str = ".") -> List[Dict[str, Any]]:
        """扫描文件系统漏洞
        
        Args:
            directory: 扫描目录
            
        Returns:
            漏洞列表
        """
        vulnerabilities = []
        
        # 检查敏感文件
        sensitive_files = [".env", "config.py", "secrets.json"]
        for file in sensitive_files:
            if os.path.exists(os.path.join(directory, file)):
                vulnerabilities.append({
                    "type": "filesystem",
                    "severity": "medium",
                    "message": f"Sensitive file found: {file}",
                    "details": {"file": file, "path": os.path.join(directory, file)}
                })
        
        self.vulnerabilities.extend(vulnerabilities)
        return vulnerabilities
    
    def run_full_scan(self, input_data: Optional[Any] = None, 
                      config: Optional[Dict[str, Any]] = None, 
                      directory: str = ".") -> List[Dict[str, Any]]:
        """运行完整扫描
        
        Args:
            input_data: 输入数据
            config: 配置数据
            directory: 扫描目录
            
        Returns:
            漏洞列表
        """
        all_vulnerabilities = []
        
        if input_data is not None:
            all_vulnerabilities.extend(self.scan_input_validation(input_data))
        
        if config is not None:
            all_vulnerabilities.extend(self.scan_config(config))
        
        all_vulnerabilities.extend(self.scan_filesystem(directory))
        
        return all_vulnerabilities
    
    def generate_report(self) -> Dict[str, Any]:
        """生成扫描报告
        
        Returns:
            扫描报告
        """
        import time
        
        # 按严重程度分组
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for vuln in self.vulnerabilities:
            severity = vuln.get("severity", "low")
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        report = {
            "scan_time": time.time(),
            "total_vulnerabilities": len(self.vulnerabilities),
            "severity_counts": severity_counts,
            "vulnerabilities": self.vulnerabilities
        }
        
        return report
    
    def get_vulnerabilities(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取漏洞列表
        
        Args:
            severity: 严重程度过滤
            
        Returns:
            漏洞列表
        """
        if severity:
            return [vuln for vuln in self.vulnerabilities if vuln.get("severity") == severity]
        return self.vulnerabilities
    
    def clear_vulnerabilities(self) -> None:
        """清空漏洞列表"""
        self.vulnerabilities.clear()


# 全局安全组件实例
_global_validator = InputValidator()
_global_permission_manager = PermissionManager()
_global_secrets_manager = SecretsManager()
_global_auditor = SecurityAuditor(log_file="./security_audit.log")
_global_anti_dos = AntiDosProtection()
_global_scanner = VulnerabilityScanner()


def get_scanner() -> VulnerabilityScanner:
    """获取全局漏洞扫描器
    
    Returns:
        漏洞扫描器实例
    """
    return _global_scanner

def get_validator() -> InputValidator:
    """获取全局输入验证器
    
    Returns:
        输入验证器实例
    """
    return _global_validator

def get_permission_manager() -> PermissionManager:
    """获取全局权限管理器
    
    Returns:
        权限管理器实例
    """
    return _global_permission_manager

def get_secrets_manager() -> SecretsManager:
    """获取全局密钥管理器
    
    Returns:
        密钥管理器实例
    """
    return _global_secrets_manager

def get_auditor() -> SecurityAuditor:
    """获取全局安全审计器
    
    Returns:
        安全审计器实例
    """
    return _global_auditor

def get_anti_dos() -> AntiDosProtection:
    """获取全局防DoS保护
    
    Returns:
        防DoS保护实例
    """
    return _global_anti_dos


# 安全装饰器
def secure_tool(func: Callable) -> Callable:
    """安全工具装饰器
    
    为工具添加安全检查。
    """
    def wrapper(*args, **kwargs):
        # 记录工具执行
        get_auditor().log_event(
            "tool_execution",
            "system",
            f"Executing tool: {func.__name__}",
            {"args": args, "kwargs": kwargs}
        )
        
        try:
            # 执行工具
            result = func(*args, **kwargs)
            
            # 记录成功
            get_auditor().log_event(
                "tool_execution",
                "system",
                f"Tool execution success: {func.__name__}",
                {"success": True}
            )
            
            return result
        except Exception as e:
            # 记录错误
            get_auditor().log_event(
                "error",
                "system",
                f"Tool execution error: {func.__name__}",
                {"error": str(e)}
            )
            raise
    
    return wrapper


class VulnerabilityScanner:
    """漏洞扫描器
    
    用于扫描系统中的安全漏洞。
    """
    
    def __init__(self):
        """初始化漏洞扫描器"""
        self.vulnerabilities = []
    
    def scan_input_validation(self, input_data: Any) -> List[Dict[str, Any]]:
        """扫描输入验证漏洞
        
        Args:
            input_data: 输入数据
            
        Returns:
            漏洞列表
        """
        vulnerabilities = []
        
        # 检查SQL注入
        if isinstance(input_data, str):
            sql_patterns = [
                r'\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b',
                r'\b(OR|AND)\s+\d+\s*=\s*\d+',
                r'\bUNION\s+SELECT\b',
                r'\b--\b',
                r'\b;\b',
                r'\b\'\b',
                r'\b\"\b'
            ]
            
            for pattern in sql_patterns:
                if re.search(pattern, input_data, re.IGNORECASE):
                    vulnerabilities.append({
                        "type": "SQL_INJECTION",
                        "severity": "high",
                        "description": "Potential SQL injection vulnerability",
                        "input": input_data[:100]
                    })
        
        # 检查XSS
        if isinstance(input_data, str):
            xss_patterns = [
                r'<script[^>]*>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
                r'<iframe[^>]*>',
                r'<img[^>]*onerror='
            ]
            
            for pattern in xss_patterns:
                if re.search(pattern, input_data, re.IGNORECASE):
                    vulnerabilities.append({
                        "type": "XSS",
                        "severity": "medium",
                        "description": "Potential XSS vulnerability",
                        "input": input_data[:100]
                    })
        
        # 检查命令注入
        if isinstance(input_data, str):
            cmd_patterns = [
                r'\b(bash|sh|cmd|powershell|python|perl|ruby|php)\b',
                r'\b(echo|cat|ls|dir|rm|del|mkdir|touch)\b',
                r'\b(\|\||\&\&|;|\`|\$\()\b'
            ]
            
            for pattern in cmd_patterns:
                if re.search(pattern, input_data, re.IGNORECASE):
                    vulnerabilities.append({
                        "type": "COMMAND_INJECTION",
                        "severity": "high",
                        "description": "Potential command injection vulnerability",
                        "input": input_data[:100]
                    })
        
        return vulnerabilities
    
    def scan_configuration(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """扫描配置漏洞
        
        Args:
            config: 配置数据
            
        Returns:
            漏洞列表
        """
        vulnerabilities = []
        
        # 检查弱密码
        if "password" in config and isinstance(config["password"], str):
            is_valid, error = SecurityConfig.validate_password(config["password"])
            if not is_valid:
                vulnerabilities.append({
                    "type": "WEAK_PASSWORD",
                    "severity": "medium",
                    "description": f"Weak password: {error}",
                    "key": "password"
                })
        
        # 检查硬编码密钥
        sensitive_keys = ["api_key", "secret", "token", "password", "key"]
        for key, value in config.items():
            if key.lower() in sensitive_keys and isinstance(value, str):
                if len(value) > 10:  # 简单判断，实际应该更复杂
                    vulnerabilities.append({
                        "type": "HARDCODED_SECRET",
                        "severity": "high",
                        "description": f"Potential hardcoded secret in configuration: {key}",
                        "key": key
                    })
        
        # 检查不安全的配置
        if "debug" in config and config["debug"] is True:
            vulnerabilities.append({
                "type": "DEBUG_MODE",
                "severity": "medium",
                "description": "Debug mode is enabled",
                "key": "debug"
            })
        
        if "cors" in config and config["cors"] == "*":
            vulnerabilities.append({
                "type": "INSECURE_CORS",
                "severity": "medium",
                "description": "CORS is set to allow all origins",
                "key": "cors"
            })
        
        return vulnerabilities
    
    def scan_file_system(self, directory: str = ".") -> List[Dict[str, Any]]:
        """扫描文件系统漏洞
        
        Args:
            directory: 目录路径
            
        Returns:
            漏洞列表
        """
        vulnerabilities = []
        
        # 检查敏感文件
        sensitive_files = [
            "config.json", "config.yaml", "config.yml",
            "secrets.json", "secrets.yaml", "secrets.yml",
            "api_keys.json", "api_keys.yaml", "api_keys.yml",
            ".env", ".env.local", ".env.development",
            "requirements.txt", "package.json"
        ]
        
        for root, dirs, files in os.walk(directory):
            # 跳过某些目录
            dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git", "node_modules"]]
            
            for file in files:
                if file in sensitive_files:
                    file_path = os.path.join(root, file)
                    vulnerabilities.append({
                        "type": "SENSITIVE_FILE",
                        "severity": "medium",
                        "description": f"Potentially sensitive file found: {file_path}",
                        "file": file_path
                    })
        
        return vulnerabilities
    
    def run_full_scan(self, input_data: Any = None, config: Dict[str, Any] = None, directory: str = ".") -> List[Dict[str, Any]]:
        """运行完整扫描
        
        Args:
            input_data: 输入数据
            config: 配置数据
            directory: 目录路径
            
        Returns:
            漏洞列表
        """
        vulnerabilities = []
        
        # 扫描输入验证
        if input_data is not None:
            vulnerabilities.extend(self.scan_input_validation(input_data))
        
        # 扫描配置
        if config is not None:
            vulnerabilities.extend(self.scan_configuration(config))
        
        # 扫描文件系统
        vulnerabilities.extend(self.scan_file_system(directory))
        
        self.vulnerabilities = vulnerabilities
        return vulnerabilities
    
    def get_vulnerabilities(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取漏洞列表
        
        Args:
            severity: 严重程度过滤
            
        Returns:
            漏洞列表
        """
        if severity:
            return [v for v in self.vulnerabilities if v.get("severity") == severity]
        return self.vulnerabilities
    
    def generate_report(self) -> Dict[str, Any]:
        """生成漏洞报告
        
        Returns:
            漏洞报告
        """
        import collections
        
        # 按严重程度分组
        severity_counts = collections.Counter([v.get("severity", "unknown") for v in self.vulnerabilities])
        
        # 按类型分组
        type_counts = collections.Counter([v.get("type", "unknown") for v in self.vulnerabilities])
        
        return {
            "total_vulnerabilities": len(self.vulnerabilities),
            "severity_counts": dict(severity_counts),
            "type_counts": dict(type_counts),
            "vulnerabilities": self.vulnerabilities
        }


class SecurityConfig:
    """安全配置
    
    安全相关的配置。
    """
    
    # 输入验证配置
    MAX_STRING_LENGTH = 500
    MAX_LIST_LENGTH = 50
    MAX_DICT_DEPTH = 5
    
    # 防DoS配置
    MAX_REQUESTS_PER_MINUTE = 60
    MAX_REQUESTS_PER_HOUR = 500
    
    # 密码策略
    PASSWORD_MIN_LENGTH = 12
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SPECIAL = True
    PASSWORD_EXPIRATION_DAYS = 60
    PASSWORD_HISTORY_SIZE = 10
    
    # 会话配置
    SESSION_TIMEOUT = 1800  # 30分钟
    SESSION_MAX_INACTIVE_INTERVAL = 900  # 15分钟
    
    # 令牌配置
    TOKEN_EXPIRATION = 1800  # 30分钟
    REFRESH_TOKEN_EXPIRATION = 43200  # 12小时
    
    # 安全策略
    ENABLE_CORS = True
    ENABLE_RATE_LIMITING = True
    ENABLE_XSS_PROTECTION = True
    ENABLE_CSRF_PROTECTION = True
    ENABLE_CONTENT_SECURITY_POLICY = True
    ENABLE_HTTPS_REDIRECT = True
    ENABLE_HSTS = True
    
    # 日志配置
    LOG_SECURITY_EVENTS = True
    LOG_AUDIT_EVENTS = True
    LOG_ERRORS = True
    LOG_ACCESS = True
    
    # 数据保护
    ENCRYPT_SENSITIVE_DATA = True
    DATA_RETENTION_DAYS = 30
    ENABLE_DATA_ENCRYPTION = True
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, Optional[str]]:
        """验证密码强度
        
        Args:
            password: 密码
            
        Returns:
            (是否有效, 错误信息)
        """
        if len(password) < SecurityConfig.PASSWORD_MIN_LENGTH:
            return False, f"Password must be at least {SecurityConfig.PASSWORD_MIN_LENGTH} characters long"
        
        if SecurityConfig.PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if SecurityConfig.PASSWORD_REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if SecurityConfig.PASSWORD_REQUIRE_DIGIT and not re.search(r'[0-9]', password):
            return False, "Password must contain at least one digit"
        
        if SecurityConfig.PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        
        return True, None
    
    @classmethod
    def load_from_file(cls, config_file: str) -> 'SecurityConfig':
        """从文件加载安全配置
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            安全配置实例
        """
        import json
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            
            # 更新配置
            for key, value in config_data.items():
                if hasattr(cls, key):
                    setattr(cls, key, value)
        except Exception:
            pass
        return cls
    
    @classmethod
    def save_to_file(cls, config_file: str) -> bool:
        """保存安全配置到文件
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            是否保存成功
        """
        import json
        try:
            config_data = {
                "MAX_STRING_LENGTH": cls.MAX_STRING_LENGTH,
                "MAX_LIST_LENGTH": cls.MAX_LIST_LENGTH,
                "MAX_DICT_DEPTH": cls.MAX_DICT_DEPTH,
                "MAX_REQUESTS_PER_MINUTE": cls.MAX_REQUESTS_PER_MINUTE,
                "MAX_REQUESTS_PER_HOUR": cls.MAX_REQUESTS_PER_HOUR,
                "PASSWORD_MIN_LENGTH": cls.PASSWORD_MIN_LENGTH,
                "PASSWORD_REQUIRE_UPPERCASE": cls.PASSWORD_REQUIRE_UPPERCASE,
                "PASSWORD_REQUIRE_LOWERCASE": cls.PASSWORD_REQUIRE_LOWERCASE,
                "PASSWORD_REQUIRE_DIGIT": cls.PASSWORD_REQUIRE_DIGIT,
                "PASSWORD_REQUIRE_SPECIAL": cls.PASSWORD_REQUIRE_SPECIAL,
                "PASSWORD_EXPIRATION_DAYS": cls.PASSWORD_EXPIRATION_DAYS,
                "PASSWORD_HISTORY_SIZE": cls.PASSWORD_HISTORY_SIZE,
                "SESSION_TIMEOUT": cls.SESSION_TIMEOUT,
                "SESSION_MAX_INACTIVE_INTERVAL": cls.SESSION_MAX_INACTIVE_INTERVAL,
                "TOKEN_EXPIRATION": cls.TOKEN_EXPIRATION,
                "REFRESH_TOKEN_EXPIRATION": cls.REFRESH_TOKEN_EXPIRATION,
                "ENABLE_CORS": cls.ENABLE_CORS,
                "ENABLE_RATE_LIMITING": cls.ENABLE_RATE_LIMITING,
                "ENABLE_XSS_PROTECTION": cls.ENABLE_XSS_PROTECTION,
                "ENABLE_CSRF_PROTECTION": cls.ENABLE_CSRF_PROTECTION,
                "ENABLE_CONTENT_SECURITY_POLICY": cls.ENABLE_CONTENT_SECURITY_POLICY,
                "LOG_SECURITY_EVENTS": cls.LOG_SECURITY_EVENTS,
                "LOG_AUDIT_EVENTS": cls.LOG_AUDIT_EVENTS,
                "LOG_ERRORS": cls.LOG_ERRORS,
                "ENCRYPT_SENSITIVE_DATA": cls.ENCRYPT_SENSITIVE_DATA,
                "DATA_RETENTION_DAYS": cls.DATA_RETENTION_DAYS
            }
            
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
