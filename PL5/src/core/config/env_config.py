#!/usr/bin/env python3
"""
环境变量配置管理
统一管理项目配置，支持环境变量和配置文件
"""

import os
import json
from typing import Any, Optional
from pathlib import Path


class EnvConfig:
    """环境变量配置管理器"""

    def __init__(self, env_file: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            env_file: .env文件路径，默认查找项目根目录的.env
        """
        # 确定项目根目录
        self.project_root = self._find_project_root()
        
        # 加载环境变量
        self.env_file = env_file or str(self.project_root / '.env')
        self._load_env()
        
        # 缓存配置
        self._config_cache: dict = {}
        
    def _find_project_root(self) -> Path:
        """查找项目根目录"""
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / 'main.py').exists() or (parent / '.git').exists():
                return parent
        return current.parent.parent  # 默认回到项目根目录
    
    def _load_env(self) -> None:
        """加载环境变量"""
        # 尝试使用python-dotenv
        try:
            from dotenv import load_dotenv
            env_path = Path(self.env_file)
            if env_path.exists():
                load_dotenv(env_path)
                print(f"✅ 已加载环境变量: {env_path}")
            else:
                print(f"⚠️ 环境变量文件不存在: {env_path}")
        except ImportError:
            # 如果没有安装dotenv，尝试直接从环境读取
            print("ℹ️  python-dotenv未安装，使用系统环境变量")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        优先级: 环境变量 > .env文件 > 默认值
        """
        if key in os.environ:
            return os.environ[key]
        return default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数配置"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔配置
        
        支持的值: 'true', '1', 'yes', 't' (不区分大小写)
        """
        value = self.get(key, str(default)).lower()
        return value in ('true', '1', 'yes', 't', 'on')
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """获取浮点数配置"""
        value = self.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_path(self, key: str, default: Optional[str] = None) -> Optional[Path]:
        """获取路径配置"""
        value = self.get(key, default)
        if value:
            return Path(value)
        return None
    
    @property
    def email_config(self) -> dict:
        """获取邮件配置"""
        # 先尝试从环境变量读取
        config = {
            'smtp_server': self.get('EMAIL_SMTP_SERVER', 'smtp.qq.com'),
            'smtp_port': self.get_int('EMAIL_SMTP_PORT', 465),
            'from_email': self.get('EMAIL_FROM_ADDRESS', ''),
            'to_email': self.get('EMAIL_TO_ADDRESS', ''),
            'auth_code': self.get('EMAIL_AUTH_CODE', '')
        }
        
        # 如果环境变量没有配置，尝试从配置文件读取（向后兼容）
        if not config['from_email']:
            config_file = self.project_root / 'config' / 'email_config.json'
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        file_config = json.load(f)
                        config.update({
                            'smtp_server': file_config.get('smtp_server', config['smtp_server']),
                            'smtp_port': file_config.get('smtp_port', config['smtp_port']),
                            'from_email': file_config.get('from_email', config['from_email']),
                            'to_email': file_config.get('to_email', config['to_email']),
                            'auth_code': file_config.get('auth_code', config['auth_code'])
                        })
                except Exception as e:
                    print(f"⚠️ 读取邮件配置文件失败: {e}")
        
        return config
    
    @property
    def feature_config(self) -> dict:
        """获取特征工程配置"""
        return {
            'enable_cpp_acceleration': self.get_bool('ENABLE_CPP_ACCELERATION', True),
            'feature_mode': self.get('FEATURE_MODE', 'v11_advanced'),
            'max_features': self.get_int('MAX_FEATURES', 450)
        }
    
    @property
    def system_config(self) -> dict:
        """获取系统配置"""
        return {
            'log_level': self.get('LOG_LEVEL', 'INFO'),
            'data_dir': self.get_path('DATA_DIR', self.project_root / 'data'),
            'model_dir': self.get_path('MODEL_DIR', self.project_root / 'models'),
            'log_dir': self.get_path('LOG_DIR', self.project_root / 'logs'),
            'timezone': self.get('TZ', 'Asia/Shanghai')
        }
    
    def validate_email_config(self) -> tuple[bool, list[str]]:
        """验证邮件配置是否完整
        
        Returns:
            (是否有效, 错误信息列表)
        """
        config = self.email_config
        errors = []
        
        if not config['from_email']:
            errors.append("缺少发件人邮箱 (EMAIL_FROM_ADDRESS)")
        if not config['to_email']:
            errors.append("缺少收件人邮箱 (EMAIL_TO_ADDRESS)")
        if not config['auth_code']:
            errors.append("缺少授权码 (EMAIL_AUTH_CODE)")
        
        return len(errors) == 0, errors
    
    def summary(self) -> str:
        """生成配置摘要（隐藏敏感信息）"""
        lines = ["=" * 60, "PL5系统配置摘要", "=" * 60]
        
        # 邮件配置
        email_config = self.email_config
        lines.append("\n📧 邮件配置:")
        lines.append(f"   SMTP服务器: {email_config['smtp_server']}:{email_config['smtp_port']}")
        lines.append(f"   发件人: {email_config['from_email']}")
        lines.append(f"   收件人: {email_config['to_email']}")
        lines.append(f"   授权码: {'*' * 20}{email_config['auth_code'][-4:] if email_config['auth_code'] else '(未设置)'}")
        
        # 特征工程配置
        feature_config = self.feature_config
        lines.append("\n🔧 特征工程配置:")
        lines.append(f"   C++加速: {'✅ 启用' if feature_config['enable_cpp_acceleration'] else '❌ 禁用'}")
        lines.append(f"   特征模式: {feature_config['feature_mode']}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


# 全局配置实例
_config_instance: Optional[EnvConfig] = None


def get_config(env_file: Optional[str] = None) -> EnvConfig:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = EnvConfig(env_file)
    return _config_instance


if __name__ == "__main__":
    import sys
    
    # 测试配置管理
    config = get_config()
    
    print(config.summary())
    
    # 验证邮件配置
    valid, errors = config.validate_email_config()
    if not valid:
        print("\n⚠️ 邮件配置警告:")
        for error in errors:
            print(f"   - {error}")
        print("\n提示: 请设置以下环境变量或创建 .env 文件")
        print("      参考 .env.example 文件格式")
        sys.exit(1)
    else:
        print("\n✅ 配置验证通过！")
