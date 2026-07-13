"""
数据模块配置
"""

from pathlib import Path
import logging
from typing import Dict, Any

# 项目根目录：src/core/data/config.py 上溯 4 级
ROOT_DIR = Path(__file__).parent.parent.parent.parent

# 数据目录配置
RAW_DATA_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"

# 模型目录
MODELS_DIR = ROOT_DIR / "models"

# 确保目录存在
RAW_DATA_DIR.mkdir(exist_ok=True, parents=True)
PROCESSED_DATA_DIR.mkdir(exist_ok=True, parents=True)
MODELS_DIR.mkdir(exist_ok=True, parents=True)

# 数据源配置
DATA_SOURCES: Dict[str, str] = {
    "lecai": "http://data.17500.cn/pl5_asc.txt",
    "local": str(RAW_DATA_DIR / "pl5_history.txt")
}

# PL5 配置
PL5_CONFIG: Dict[str, Any] = {
    "positions": ["wan", "qian", "bai", "shi", "ge"],
    "history_length": 1000,  # 历史数据长度
    "feature_window": 30,     # 特征窗口大小
    "prediction_window": 5     # 预测窗口大小
}

def setup_logging(name: str) -> logging.Logger:
    """设置日志"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 如果已有处理器，不再添加
    if not logger.handlers:
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger

