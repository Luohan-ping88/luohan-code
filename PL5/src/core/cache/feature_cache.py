"""
特征缓存管理器 V2.1 - 专为特征工程优化的缓存
支持基于数据内容的智能缓存key生成，TTL过期，多级缓存策略
修复pandas 3.0+兼容性问题
"""

import hashlib
import time
import json
import pickle
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import pandas as pd
import numpy as np


class EvictionStrategy(Enum):
    """淘汰策略"""
    LRU = "lru"           # 最近最少使用
    LFU = "lfu"          # 最不经常使用
    SMART = "smart"      # 智能淘汰（LRU+LFU组合）
    FIFO = "fifo"        # 先进先出


@dataclass
class CacheConfig:
    """缓存配置"""
    max_size: int = 100
    default_ttl: int = 3600  # 默认TTL（秒）
    enable_persistence: bool = False
    persistence_path: Optional[str] = None
    eviction_strategy: str = "smart"
    auto_adjust_size: bool = True
    size_adjust_interval: int = 300  # 调整间隔（秒）


class FeatureCacheManager:
    """基于hash的特征缓存管理器 V2.1 - 增强版"""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._cache: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self._max_size = self.config.max_size
        self._hit_count = 0
        self._miss_count = 0
        self._cache_times: Dict[str, float] = {}  # 记录缓存时间
        self._access_patterns: Dict[str, int] = {}  # 访问频率
        self._ttl_times: Dict[str, float] = {}  # TTL过期时间
        self._eviction_strategy = EvictionStrategy(self.config.eviction_strategy)
        self._last_size_adjust = time.time()
        self._start_time = time.time()

    def get_key(self, df: pd.DataFrame, extra_tags: Tuple = ()) -> str:
        """生成缓存key（基于数据内容hash）"""
        core_cols = ['period']
        if 'full_number' in df.columns:
            core_cols.append('full_number')

        hash_obj = hashlib.sha256()
        for col in core_cols:
            if col in df.columns:
                try:
                    # 尝试直接tobytes
                    values = df[col].values.tobytes()
                except (AttributeError, TypeError):
                    # 兼容性处理：对于StringArray等类型
                    try:
                        # 转换为字符串表示
                        if pd.api.types.is_string_dtype(df[col]) or col == 'full_number':
                            # 对于字符串列，直接连接字符串
                            values = '|'.join(str(x) for x in df[col]).encode('utf-8')
                        else:
                            # 对于其他类型，转换为numpy数组
                            arr = np.array(df[col])
                            values = arr.tobytes()
                    except (AttributeError, TypeError, Exception):
                        # 最后的降级方案：使用列的前N个值的字符串表示
                        preview = '|'.join(str(x) for x in df[col].head(100))
                        values = preview.encode('utf-8')

                hash_obj.update(values)
                hash_obj.update(str(len(df)).encode())

        data_hash = hash_obj.hexdigest()[:16]
        tag_hash = hashlib.md5(str(extra_tags).encode()).hexdigest()[:8]
        return f"{data_hash}_{tag_hash}"

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """获取缓存"""
        # 检查TTL是否过期
        if key in self._ttl_times:
            if time.time() > self._ttl_times[key]:
                self._remove_key(key)
                self._miss_count += 1
                return None

        if key in self._cache:
            self._cache.move_to_end(key)
            self._hit_count += 1
            self._cache_times[key] = time.time()
            self._access_patterns[key] = self._access_patterns.get(key, 0) + 1
            return self._cache[key].copy()

        self._miss_count += 1
        return None

    def put(self, key: str, df: pd.DataFrame, ttl: Optional[int] = None):
        """存入缓存"""
        try:
            # 自动调整缓存大小
            if self.config.auto_adjust_size:
                self._auto_adjust_size()

            # 设置TTL
            if ttl is None:
                ttl = self.config.default_ttl
            self._ttl_times[key] = time.time() + ttl

            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = df.copy()
            else:
                if len(self._cache) >= self._max_size:
                    self._smart_evict()
                self._cache[key] = df.copy()

            self._cache_times[key] = time.time()
            self._access_patterns[key] = self._access_patterns.get(key, 0) + 1
        except Exception as e:
            # 出错时只记录警告，不影响主流程
            print(f"缓存警告: {e}")

    def _auto_adjust_size(self):
        """根据命中率动态调整缓存大小"""
        current_time = time.time()
        if current_time - self._last_size_adjust < self.config.size_adjust_interval:
            return

        stats = self.stats
        hit_rate = stats['hit_rate']

        # 如果命中率很低，增加缓存大小
        if hit_rate < 0.3 and self._max_size < 500:
            self._max_size = min(500, int(self._max_size * 1.5))
        # 如果命中率很高，可以减小缓存大小
        elif hit_rate > 0.8 and self._max_size > 50:
            self._max_size = max(50, int(self._max_size * 0.8))

        self._last_size_adjust = current_time

    def _smart_evict(self):
        """智能淘汰策略"""
        if not self._cache:
            return

        if self._eviction_strategy == EvictionStrategy.LRU:
            self._evict_lru()
        elif self._eviction_strategy == EvictionStrategy.LFU:
            self._evict_lfu()
        elif self._eviction_strategy == EvictionStrategy.SMART:
            self._evict_smart()
        elif self._eviction_strategy == EvictionStrategy.FIFO:
            self._evict_fifo()

    def _evict_lru(self):
        """LRU淘汰 - 淘汰最老的"""
        if self._cache:
            oldest_key = next(iter(self._cache))
            self._remove_key(oldest_key)

    def _evict_lfu(self):
        """LFU淘汰 - 淘汰访问频率最低的"""
        if not self._cache:
            return
        key_to_remove = min(self._cache, key=lambda k: self._access_patterns.get(k, 0))
        self._remove_key(key_to_remove)

    def _evict_smart(self):
        """智能淘汰 - 结合LRU和LFU"""
        current_time = time.time()
        scores = {}

        for key in self._cache:
            age = current_time - self._cache_times.get(key, 0)
            freq = self._access_patterns.get(key, 1)
            scores[key] = age / (freq + 1)

        if scores:
            key_to_remove = max(scores, key=scores.get)
            self._remove_key(key_to_remove)

    def _evict_fifo(self):
        """FIFO淘汰 - 先进先出"""
        self._evict_lru()

    def _remove_key(self, key: str):
        """移除缓存键"""
        if key in self._cache:
            del self._cache[key]
        if key in self._cache_times:
            del self._cache_times[key]
        if key in self._access_patterns:
            del self._access_patterns[key]
        if key in self._ttl_times:
            del self._ttl_times[key]

    def clear(self):
        """清空所有缓存"""
        size = len(self._cache)
        self._cache.clear()
        self._cache_times.clear()
        self._access_patterns.clear()
        self._ttl_times.clear()
        print(f"特征缓存已清空，释放 {size} 条记录")

    def clear_by_prefix(self, prefix: str):
        """按前缀清理缓存"""
        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_remove:
            self._remove_key(k)
        print(f"按前缀 '{prefix}' 清理了 {len(keys_to_remove)} 条缓存")

    def clear_expired(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [k for k, ttl in self._ttl_times.items() if current_time > ttl]
        for k in expired_keys:
            self._remove_key(k)
        if expired_keys:
            print(f"清理了 {len(expired_keys)} 条过期缓存")

    def prewarm(self, df: pd.DataFrame, common_configs: List[Tuple]):
        """缓存预热"""
        print(f"开始缓存预热，预计算 {len(common_configs)} 个配置...")
        for config in common_configs:
            key = self.get_key(df, config)
            if key not in self._cache:
                print(f"  预热配置: {config}")
        print("缓存预热完成")

    def get_similar_keys(self, key: str, threshold: float = 0.8) -> List[str]:
        """查找相似的缓存key"""
        similar = []
        key_prefix = key.split('_')[0]

        for cached_key in self._cache:
            if cached_key.startswith(key_prefix):
                similar.append(cached_key)

        return similar

    @property
    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0.0

        # 计算平均TTL剩余时间
        current_time = time.time()
        ttl_remaining = []
        for key, ttl_time in self._ttl_times.items():
            remaining = ttl_time - current_time
            if remaining > 0:
                ttl_remaining.append(remaining)

        avg_ttl_remaining = sum(ttl_remaining) / len(ttl_remaining) if ttl_remaining else 0

        return {
            'size': len(self._cache),
            'max_size': self._max_size,
            'hits': self._hit_count,
            'misses': self._miss_count,
            'hit_rate': round(hit_rate, 4),
            'utilization': round(len(self._cache) / self._max_size, 4) if self._max_size > 0 else 0.0,
            'avg_ttl_remaining': round(avg_ttl_remaining, 1),
            'eviction_strategy': self._eviction_strategy.value,
            'uptime_seconds': round(time.time() - self._start_time, 1),
            'total_requests': total
        }

    def save_to_disk(self, path: Optional[Path] = None):
        """保存缓存到磁盘"""
        if not self.config.enable_persistence:
            print("持久化未启用")
            return

        save_path = path or Path(self.config.persistence_path or "cache/feature_cache.pkl")
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                'cache': dict(self._cache),
                'cache_times': self._cache_times,
                'access_patterns': self._access_patterns,
                'ttl_times': self._ttl_times,
                'hit_count': self._hit_count,
                'miss_count': self._miss_count,
                'timestamp': time.time()
            }

            with open(save_path, 'wb') as f:
                pickle.dump(data, f)
            print(f"缓存已保存到: {save_path}")
        except Exception as e:
            print(f"缓存保存失败: {e}")

    def load_from_disk(self, path: Optional[Path] = None) -> bool:
        """从磁盘加载缓存"""
        if not self.config.enable_persistence:
            return False

        load_path = path or Path(self.config.persistence_path or "cache/feature_cache.pkl")
        if not load_path.exists():
            print(f"缓存文件不存在: {load_path}")
            return False

        try:
            with open(load_path, 'rb') as f:
                data = pickle.load(f)

            # 清理过期缓存
            current_time = time.time()
            for key, ttl_time in list(data['ttl_times'].items()):
                if current_time > ttl_time:
                    del data['cache'][key]
                    del data['ttl_times'][key]

            self._cache = OrderedDict(data['cache'])
            self._cache_times = data['cache_times']
            self._access_patterns = data['access_patterns']
            self._ttl_times = data['ttl_times']
            self._hit_count = data['hit_count']
            self._miss_count = data['miss_count']

            print(f"缓存已从 {load_path} 加载，共 {len(self._cache)} 条记录")
            return True

        except Exception as e:
            print(f"加载缓存失败: {e}")
            return False

    def __len__(self):
        return len(self._cache)

    def __repr__(self):
        stats = self.stats
        return f"FeatureCacheManager(size={stats['size']}/{stats['max_size']}, hit_rate={stats['hit_rate']:.2%})"
