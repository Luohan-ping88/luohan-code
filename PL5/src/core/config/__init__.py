"""
配置管理模块
"""
from .env_config import get_config, EnvConfig

# 向后兼容 - 延迟导入避免循环依赖
import sys
from pathlib import Path


class _LazyConfig:
    _loaded = False
    _config = None
    
    @classmethod
    def _load(cls):
        if not cls._loaded:
            # 添加 src/core 到路径
            core_path = str(Path(__file__).parent.parent)
            if core_path not in sys.path:
                sys.path.insert(0, core_path)
            
            # 导入旧版配置
            try:
                from config import (
                    ModelConfig as _ModelConfig, get_model_config as _get_model_config,
                    ROOT_DIR as _ROOT_DIR, BASE_DIR as _BASE_DIR, DATA_DIR as _DATA_DIR,
                    RAW_DATA_DIR as _RAW_DATA_DIR, PROCESSED_DATA_DIR as _PROCESSED_DATA_DIR,
                    RESULTS_DIR as _RESULTS_DIR, MODELS_DIR as _MODELS_DIR,
                    LOGS_DIR as _LOGS_DIR, CONFIG_DIR as _CONFIG_DIR,
                    DATA_SOURCES as _DATA_SOURCES, PL5_CONFIG as _PL5_CONFIG,
                    MODEL_CONFIG as _MODEL_CONFIG, TRAINING_CONFIG as _TRAINING_CONFIG,
                    setup_logging as _setup_logging
                )
                cls._config = {
                    'ModelConfig': _ModelConfig,
                    'get_model_config': _get_model_config,
                    'ROOT_DIR': _ROOT_DIR,
                    'BASE_DIR': _BASE_DIR,
                    'DATA_DIR': _DATA_DIR,
                    'RAW_DATA_DIR': _RAW_DATA_DIR,
                    'PROCESSED_DATA_DIR': _PROCESSED_DATA_DIR,
                    'RESULTS_DIR': _RESULTS_DIR,
                    'MODELS_DIR': _MODELS_DIR,
                    'LOGS_DIR': _LOGS_DIR,
                    'CONFIG_DIR': _CONFIG_DIR,
                    'DATA_SOURCES': _DATA_SOURCES,
                    'PL5_CONFIG': _PL5_CONFIG,
                    'MODEL_CONFIG': _MODEL_CONFIG,
                    'TRAINING_CONFIG': _TRAINING_CONFIG,
                    'setup_logging': _setup_logging,
                }
            except (ImportError, Exception) as e:
                # 创建占位符
                class ModelConfig:
                    def __init__(self, *args, **kwargs):
                        pass
                
                def get_model_config(*args, **kwargs):
                    return ModelConfig()
                
                root_dir = Path(__file__).parent.parent.parent
                cls._config = {
                    'ModelConfig': ModelConfig,
                    'get_model_config': get_model_config,
                    'ROOT_DIR': root_dir,
                    'BASE_DIR': root_dir,
                    'DATA_DIR': root_dir / 'data',
                    'RAW_DATA_DIR': root_dir / 'data' / 'raw',
                    'PROCESSED_DATA_DIR': root_dir / 'data' / 'processed',
                    'RESULTS_DIR': root_dir / 'results',
                    'MODELS_DIR': root_dir / 'models',
                    'LOGS_DIR': root_dir / 'logs',
                    'CONFIG_DIR': root_dir / 'config',
                    'DATA_SOURCES': {'lecai': 'http://data.17500.cn/pl5_asc.txt'},
                    'PL5_CONFIG': {},
                    'MODEL_CONFIG': {},
                    'TRAINING_CONFIG': {},
                    'setup_logging': lambda *args, **kwargs: None,
                }
            cls._loaded = True
    
    @classmethod
    def get(cls, name):
        cls._load()
        return cls._config.get(name)


# 属性访问器
def __getattr__(name):
    return _LazyConfig.get(name)


__all__ = [
    'get_config', 'EnvConfig',
    'ModelConfig', 'get_model_config',
    'ROOT_DIR', 'BASE_DIR', 'DATA_DIR', 'RAW_DATA_DIR', 'PROCESSED_DATA_DIR',
    'RESULTS_DIR', 'MODELS_DIR', 'LOGS_DIR', 'CONFIG_DIR',
    'DATA_SOURCES', 'PL5_CONFIG', 'MODEL_CONFIG', 'TRAINING_CONFIG',
    'setup_logging'
]
