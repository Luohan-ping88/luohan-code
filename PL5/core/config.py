"""
core.config 代理模块
从 src.core.config 转发所有配置。
"""

from src.core.config import (  # noqa: F401
    ROOT_DIR,
    BASE_DIR,
    DATA_DIR,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    RESULTS_DIR,
    MODELS_DIR,
    LOGS_DIR,
    DATA_SOURCES,
    PL5_CONFIG,
    MODEL_CONFIG,
    TRAINING_CONFIG,
    setup_logging,
)
