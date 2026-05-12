"""Features module initialization"""

from .feature_config_manager import (
    FeatureConfig,
    FeatureConfigManager,
    get_feature_config_manager
)

# 导入特征工程类
from .engineer import FeatureEngineerV9
from .engineer_v10 import FeatureEngineerV10

# 兼容别名：让外部可以用 FeatureEngineer 导入最新版本
FeatureEngineer = FeatureEngineerV10

__all__ = [
    "FeatureConfig",
    "FeatureConfigManager",
    "get_feature_config_manager",
    "FeatureEngineer",
    "FeatureEngineerV9",
    "FeatureEngineerV10",
]
