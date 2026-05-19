"""
核心配置管理模块
支持环境变量和配置文件
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# 可选的dotenv支持
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


# 基础目录
BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"


def load_env():
    """加载环境变量"""
    if not HAS_DOTENV:
        return False
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        return True
    return False


def get_config_value(key: str, default: Any = None) -> Any:
    """获取配置值（优先从环境变量）"""
    # 首先检查环境变量
    env_value = os.environ.get(key.upper())
    if env_value is not None:
        return env_value
    
    # 然后尝试从配置文件
    config_file = CONFIG_DIR / "config.json"
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if key in config:
                return config[key]
        except Exception:
            pass
    
    return default


def get_bool_config(key: str, default: bool = False) -> bool:
    """获取布尔类型配置"""
    value = get_config_value(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', 'yes', '1', 't')
    return bool(value)


def get_int_config(key: str, default: int = 0) -> int:
    """获取整数类型配置"""
    value = get_config_value(key, default)
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# 确保必要的目录存在
for directory in [CONFIG_DIR, DATA_DIR, MODELS_DIR, LOGS_DIR, REPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# 自动加载环境变量
load_env()
