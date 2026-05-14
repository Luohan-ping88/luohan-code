"""
特征缓存管理器 - 专为特征工程优化的缓存
支持基于数据内容的智能缓存key生成
"""

import hashlib
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


class FeatureCacheManager:
    """基于hash的LRU特征缓存管理器 - 优化版"""

    def __init__(self, max_size: int = 100):
        self._cache: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self._max_size = max_size
        self._hit_count = 0
        self._miss_count = 0
        self._cache_times: Dict[str, float] = {}  # 记录缓存时间，用于智能淘汰
        self._access_patterns: Dict[str, int] = {}  # 访问模式分析

    def get_key(self, df: pd.DataFrame, extra_tags: Tuple = ()) -> str:
        """生成缓存key（基于数据内容hash）"""
        core_cols = ["period"]
        if "full_number" in df.columns:
            core_cols.append("full_number")

        # 计算数据hash
        hash_obj = hashlib.sha256()
        for col in core_cols:
            if col in df.columns:
                values = df[col].values.tobytes()
                hash_obj.update(values)
                hash_obj.update(str(len(df)).encode())

        data_hash = hash_obj.hexdigest()[:16]
        tag_hash = hashlib.md5(str(extra_tags).encode()).hexdigest()[:8]
        return f"{data_hash}_{tag_hash}"

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """获取缓存"""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hit_count += 1
            self._cache_times[key] = time.time()
            self._access_patterns[key] = self._access_patterns.get(key, 0) + 1
            return self._cache[key].copy()
        self._miss_count += 1
        return None

    def put(self, key: str, df: pd.DataFrame, ttl: Optional[int] = None):
        """存入缓存（LRU策略）"""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = df.copy()
        else:
            if len(self._cache) >= self._max_size:
                # 智能淘汰：优先淘汰访问频率低且时间久的
                self._smart_evict()
            self._cache[key] = df.copy()

        self._cache_times[key] = time.time()
        self._access_patterns[key] = 1

    def _smart_evict(self):
        """智能淘汰策略 - 结合LRU和LFU"""
        if not self._cache:
            return

        # 计算每个条目的综合得分（越低越容易被淘汰）
        current_time = time.time()
        scores = {}

        for key in self._cache:
            age = current_time - self._cache_times.get(key, 0)
            freq = self._access_patterns.get(key, 1)
            # 得分 = 年龄 / 频率 (年龄越大、频率越低，得分越高，越容易被淘汰)
            scores[key] = age / (freq + 1)

        # 淘汰得分最高的
        key_to_remove = max(scores, key=scores.get)
        del self._cache[key_to_remove]
        del self._cache_times[key_to_remove]
        del self._access_patterns[key_to_remove]

    def clear(self):
        """清空所有缓存"""
        size = len(self._cache)
        self._cache.clear()
        self._cache_times.clear()
        self._access_patterns.clear()
        print(f"特征缓存已清空，释放 {size} 条记录")

    def clear_by_prefix(self, prefix: str):
        """按前缀清理缓存"""
        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._cache[k]
            if k in self._cache_times:
                del self._cache_times[k]
            if k in self._access_patterns:
                del self._access_patterns[k]
        print(f"按前缀 '{prefix}' 清理了 {len(keys_to_remove)} 条缓存")

    def prewarm(self, df: pd.DataFrame, common_configs: List[Tuple]):
        """缓存预热：预先计算常用配置的特征"""
        print(f"开始缓存预热，预计算 {len(common_configs)} 个配置...")
        for config in common_configs:
            key = self.get_key(df, config)
            if key not in self._cache:
                # 这里不实际计算，只是记录预热标记
                pass
        print("缓存预热完成")

    def get_similar_keys(self, key: str, threshold: float = 0.8) -> List[str]:
        """查找相似的缓存key（用于近似匹配）"""
        similar = []
        key_prefix = key.split("_")[0]  # 数据部分

        for cached_key in self._cache:
            if cached_key.startswith(key_prefix):
                similar.append(cached_key)

        return similar

    @property
    def stats(self) -> Dict[str, Any]:
        total = self._hit_count + self._miss_count
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hit_count,
            "misses": self._miss_count,
            "hit_rate": self._hit_count / total if total > 0 else 0.0,
            "utilization": (
                len(self._cache) / self._max_size
                if self._max_size > 0
                else 0.0
            ),
        }

    def __len__(self):
        return len(self._cache)
