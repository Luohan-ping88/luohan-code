"""
数据采集器兼容模块
向后兼容旧的导入路径
"""

from src.core.data.collector import PL5DataCollectorV8, PL5DataCollector

__all__ = ['PL5DataCollectorV8', 'PL5DataCollector']
