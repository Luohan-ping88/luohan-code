"""
多级缓存系统 V1.0
支持内存缓存、磁盘缓存和分布式缓存
优化缓存命中率，减少重复计算
"""

from .multi_level_cache import MultiLevelCache, CacheLevel, CacheStrategy, get_global_cache, reset_global_cache
from .feature_cache import FeatureCacheManager

__all__ = [
    "MultiLevelCache",
    "CacheLevel",
    "CacheStrategy",
    "FeatureCacheManager",
    "get_global_cache",
    "reset_global_cache",
]
