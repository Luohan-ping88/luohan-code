"""
数据处理模块
"""
from .collector import DataValidator, DataVersionManager, PL5DataCollectorV8

# 兼容别名：让外部可以用 DataLoader 导入 PL5DataCollectorV8
DataLoader = PL5DataCollectorV8

__all__ = [
    "DataValidator",
    "DataVersionManager",
    "PL5DataCollectorV8",
    "DataLoader",
]

