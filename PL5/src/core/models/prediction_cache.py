"""
预测结果缓存 - V10.5
缓存预测结果，避免对相同数据的重复推理
"""

import hashlib
import time
from typing import Dict, List, Optional, Any
from collections import OrderedDict
import logging
import numpy as np

logger = logging.getLogger(__name__)


class PredictionCache:
    """
    预测结果缓存
    
    功能：
    1. 缓存模型预测结果
    2. 基于输入特征和配置生成缓存key
    3. LRU淘汰策略
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存有效期（秒）
        """
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._hit_count = 0
        self._miss_count = 0
        self._expired_count = 0
    
    def _compute_key(self, features: np.ndarray, model_config: Dict) -> str:
        """
        计算缓存key
        
        Args:
            features: 输入特征数组
            model_config: 模型配置
            
        Returns:
            缓存key
        """
        # 使用特征的hash
        hash_obj = hashlib.sha256()
        
        # 特征数组的hash（使用前100行和后100行）
        if len(features) > 200:
            sample = np.concatenate([features[:100], features[-100:]])
        else:
            sample = features
        
        hash_obj.update(sample.tobytes())
        hash_obj.update(str(features.shape).encode())
        
        # 添加模型配置的hash
        config_str = str(sorted(model_config.items()))
        hash_obj.update(config_str.encode())
        
        return hash_obj.hexdigest()[:16]
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """检查缓存是否过期"""
        if 'timestamp' not in entry:
            return True
        age = time.time() - entry['timestamp']
        return age > self._ttl_seconds
    
    def get(self, features: np.ndarray, model_config: Dict) -> Optional[Dict[str, Any]]:
        """
        获取缓存的预测结果
        
        Args:
            features: 输入特征
            model_config: 模型配置
            
        Returns:
            缓存的预测结果，或None
        """
        key = self._compute_key(features, model_config)
        
        if key in self._cache:
            entry = self._cache[key]
            
            # 检查是否过期
            if self._is_expired(entry):
                del self._cache[key]
                self._expired_count += 1
                self._miss_count += 1
                return None
            
            # 移动到末尾（LRU）
            self._cache.move_to_end(key)
            self._hit_count += 1
            return entry['prediction']
        
        self._miss_count += 1
        return None
    
    def put(self, features: np.ndarray, model_config: Dict, prediction: Dict[str, Any]):
        """
        保存预测结果到缓存
        
        Args:
            features: 输入特征
            model_config: 模型配置
            prediction: 预测结果
        """
        key = self._compute_key(features, model_config)
        
        # LRU淘汰
        if key not in self._cache and len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"缓存淘汰: {oldest_key}")
        
        self._cache[key] = {
            'prediction': prediction,
            'timestamp': time.time()
        }
        self._cache.move_to_end(key)
    
    def clear(self):
        """清空缓存"""
        size = len(self._cache)
        self._cache.clear()
        logger.info(f"预测缓存已清空，释放 {size} 条记录")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hit_count + self._miss_count
        return {
            'size': len(self._cache),
            'max_size': self._max_size,
            'hits': self._hit_count,
            'misses': self._miss_count,
            'hit_rate': self._hit_count / total if total > 0 else 0.0,
            'expired': self._expired_count
        }


# 全局单例
_global_prediction_cache: Optional[PredictionCache] = None


def get_prediction_cache() -> PredictionCache:
    """获取全局预测缓存"""
    global _global_prediction_cache
    if _global_prediction_cache is None:
        _global_prediction_cache = PredictionCache(max_size=100, ttl_seconds=3600)
    return _global_prediction_cache
