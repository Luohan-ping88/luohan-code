"""
特征工程模块配置
"""

from pathlib import Path
import logging
from typing import Dict, Any

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent

# 数据目录配置
PROCESSED_DATA_DIR = ROOT_DIR / "core" / "data" / "processed"

# 模型目录
MODELS_DIR = ROOT_DIR / "models"

# 确保目录存在
PROCESSED_DATA_DIR.mkdir(exist_ok=True, parents=True)
MODELS_DIR.mkdir(exist_ok=True, parents=True)

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
