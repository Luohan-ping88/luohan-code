"""
特征工程兼容模块
向后兼容旧的导入路径
"""

from src.core.features.engineer import FeatureEngineer, FeatureEngineerV10

__all__ = ['FeatureEngineer', 'FeatureEngineerV10']
