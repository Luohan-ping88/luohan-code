"""
多级缓存系统 - 核心实现
支持L1(内存)、L2(磁盘)、L3(远程)三级缓存
"""

import hashlib
import json
import pickle
import time
import threading
from collections import OrderedDict
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple
import logging

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """缓存级别"""

    L1_MEMORY = auto()  # 内存缓存 - 最快
    L2_DISK = auto()  # 磁盘缓存 - 持久化
    L3_REMOTE = auto()  # 远程缓存 - 分布式


class CacheStrategy(Enum):
    """缓存策略"""

    LRU = auto()  # 最近最少使用
    LFU = auto()  # 最不经常使用
    FIFO = auto()  # 先进先出
    TTL = auto()  # 时间过期


class CacheEntry:
    """缓存条目"""

    def __init__(self, value: Any, ttl: Optional[int] = None):
        self.value = value
        self.created_at = time.time()
        self.accessed_at = time.time()
        self.access_count = 1
        self.ttl = ttl

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self):
        self.accessed_at = time.time()
        self.access_count += 1


class L1MemoryCache:
    """L1 内存缓存 - 线程安全"""

    def __init__(self, max_size: int = 1000, strategy: CacheStrategy = CacheStrategy.LRU):
        self._max_size = max_size
        self._strategy = strategy
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            entry.touch()
            if self._strategy == CacheStrategy.LRU:
                self._cache.move_to_end(key)

            self._hits += 1
            return entry.value

    def put(self, key: str, value: Any, ttl: Optional[int] = None):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = CacheEntry(value, ttl)
                return

            if len(self._cache) >= self._max_size:
                self._evict()

            self._cache[key] = CacheEntry(value, ttl)

    def _evict(self):
        """根据策略淘汰缓存"""
        if not self._cache:
            return

        if self._strategy == CacheStrategy.LRU:
            self._cache.popitem(last=False)
        elif self._strategy == CacheStrategy.LFU:
            min_key = min(self._cache.keys(), key=lambda k: self._cache[k].access_count)
            del self._cache[min_key]
        elif self._strategy == CacheStrategy.FIFO:
            self._cache.popitem(last=False)

    def clear(self):
        with self._lock:
            self._cache.clear()

    def remove(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._cache.keys())

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "level": "L1_MEMORY",
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "strategy": self._strategy.name,
            }


class L2DiskCache:
    """L2 磁盘缓存"""

    def __init__(self, cache_dir: Path, max_size_mb: int = 500):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._hits = 0
        self._misses = 0
        self._lock = threading.RLock()
        self._metadata_file = self._cache_dir / ".cache_metadata.json"
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> Dict:
        if self._metadata_file.exists():
            try:
                with open(self._metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_metadata(self):
        try:
            with open(self._metadata_file, "w", encoding="utf-8") as f:
                json.dump(self._metadata, f)
        except Exception as e:
            logger.warning(f"保存缓存元数据失败: {e}")

    def _get_cache_path(self, key: str) -> Path:
        # 使用hash分目录，避免单目录文件过多
        key_hash = hashlib.md5(key.encode()).hexdigest()
        subdir = key_hash[:2]
        return self._cache_dir / subdir / f"{key_hash}.cache"

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            cache_path = self._get_cache_path(key)

            if not cache_path.exists():
                self._misses += 1
                return None

            # 检查元数据
            meta = self._metadata.get(key, {})
            if meta.get("expires_at") and time.time() > meta["expires_at"]:
                self._remove_file(cache_path)
                self._misses += 1
                return None

            try:
                with open(cache_path, "rb") as f:
                    value = pickle.load(f)

                # 更新访问时间
                meta["last_accessed"] = time.time()
                meta["access_count"] = meta.get("access_count", 0) + 1
                self._metadata[key] = meta
                self._save_metadata()

                self._hits += 1
                return value
            except Exception as e:
                logger.warning(f"读取磁盘缓存失败: {e}")
                self._misses += 1
                return None

    def put(self, key: str, value: Any, ttl: Optional[int] = None):
        with self._lock:
            cache_path = self._get_cache_path(key)
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                with open(cache_path, "wb") as f:
                    pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)

                self._metadata[key] = {
                    "created_at": time.time(),
                    "expires_at": time.time() + ttl if ttl else None,
                    "size": cache_path.stat().st_size,
                    "access_count": 0,
                    "last_accessed": time.time(),
                }
                self._save_metadata()

                # 检查并清理过期缓存
                self._cleanup_if_needed()
            except Exception as e:
                logger.warning(f"写入磁盘缓存失败: {e}")

    def _remove_file(self, path: Path):
        try:
            path.unlink()
            # 尝试删除空目录
            if path.parent != self._cache_dir:
                try:
                    path.parent.rmdir()
                except OSError:
                    pass
        except Exception:
            pass

    def _cleanup_if_needed(self):
        """清理过期或超出大小的缓存"""
        total_size = sum(m.get("size", 0) for m in self._metadata.values())

        if total_size <= self._max_size_bytes:
            return

        # 按最后访问时间排序，删除最旧的
        sorted_items = sorted(self._metadata.items(), key=lambda x: x[1].get("last_accessed", 0))

        for key, meta in sorted_items:
            if total_size <= self._max_size_bytes * 0.8:
                break

            cache_path = self._get_cache_path(key)
            self._remove_file(cache_path)
            total_size -= meta.get("size", 0)
            del self._metadata[key]

        self._save_metadata()

    def clear(self):
        with self._lock:
            for subdir in self._cache_dir.iterdir():
                if subdir.is_dir():
                    for f in subdir.iterdir():
                        f.unlink()
                    subdir.rmdir()
            self._metadata.clear()
            self._save_metadata()

    def remove(self, key: str) -> bool:
        with self._lock:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                self._remove_file(cache_path)
                if key in self._metadata:
                    del self._metadata[key]
                    self._save_metadata()
                return True
            return False

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            total_size = sum(m.get("size", 0) for m in self._metadata.values())
            return {
                "level": "L2_DISK",
                "size": len(self._metadata),
                "total_size_mb": total_size / (1024 * 1024),
                "max_size_mb": self._max_size_bytes / (1024 * 1024),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }


class MultiLevelCache:
    """多级缓存管理器"""

    def __init__(
        self,
        l1_size: int = 1000,
        l2_dir: Optional[Path] = None,
        l2_size_mb: int = 500,
        strategy: CacheStrategy = CacheStrategy.LRU,
    ):
        self._l1 = L1MemoryCache(max_size=l1_size, strategy=strategy)
        self._l2 = L2DiskCache(l2_dir or Path("./cache"), max_size_mb=l2_size_mb) if l2_dir else None
        self._l3 = None  # 远程缓存预留
        self._lock = threading.RLock()

    def _generate_key(self, *args, **kwargs) -> str:
        """生成缓存key"""
        content = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, key: str) -> Tuple[Optional[Any], Optional[CacheLevel]]:
        """
        获取缓存值
        返回: (value, level) 如果未命中返回 (None, None)
        """
        # L1
        value = self._l1.get(key)
        if value is not None:
            return value, CacheLevel.L1_MEMORY

        # L2
        if self._l2:
            value = self._l2.get(key)
            if value is not None:
                # 回填L1
                self._l1.put(key, value)
                return value, CacheLevel.L2_DISK

        # L3 (预留)

        return None, None

    def put(self, key: str, value: Any, ttl: Optional[int] = None, levels: List[CacheLevel] = None):
        """
        存入缓存
        levels: 指定要存入的缓存级别，默认全部
        """
        levels = levels or [CacheLevel.L1_MEMORY, CacheLevel.L2_DISK]

        with self._lock:
            if CacheLevel.L1_MEMORY in levels:
                self._l1.put(key, value, ttl)

            if CacheLevel.L2_DISK in levels and self._l2:
                self._l2.put(key, value, ttl)

    def get_or_compute(self, key: str, compute_fn: Callable, ttl: Optional[int] = None) -> Any:
        """
        获取缓存或计算
        """
        value, level = self.get(key)
        if value is not None:
            logger.debug(f"缓存命中 [{level.name if level else 'None'}]: {key[:16]}...")
            return value

        # 计算
        logger.debug(f"缓存未命中，执行计算: {key[:16]}...")
        value = compute_fn()

        # 存入缓存
        self.put(key, value, ttl)

        return value

    def invalidate(self, key: str) -> bool:
        """使特定key失效"""
        with self._lock:
            l1_removed = self._l1.remove(key)
            l2_removed = self._l2.remove(key) if self._l2 else False
            return l1_removed or l2_removed

    def invalidate_pattern(self, pattern: str):
        """按模式使缓存失效"""
        # 简化的模式匹配
        with self._lock:
            for key in self._l1.keys():
                if pattern in key:
                    self._l1.remove(key)

            if self._l2:
                for key in list(self._l2._metadata.keys()):
                    if pattern in key:
                        self._l2.remove(key)

    def clear(self, level: Optional[CacheLevel] = None):
        """清理缓存"""
        with self._lock:
            if level is None or level == CacheLevel.L1_MEMORY:
                self._l1.clear()
            if (level is None or level == CacheLevel.L2_DISK) and self._l2:
                self._l2.clear()

    @property
    def stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        stats = {"l1": self._l1.stats, "overall": {}}

        if self._l2:
            stats["l2"] = self._l2.stats

        # 计算整体命中率
        total_hits = stats["l1"]["hits"]
        total_misses = stats["l1"]["misses"]

        if self._l2:
            total_hits += stats["l2"]["hits"]
            total_misses += stats["l2"]["misses"]

        total = total_hits + total_misses
        stats["overall"] = {
            "total_hits": total_hits,
            "total_misses": total_misses,
            "hit_rate": total_hits / total if total > 0 else 0.0,
        }

        return stats

    def print_stats(self):
        """打印缓存统计"""
        stats = self.stats
        print("=" * 50)
        print("多级缓存统计")
        print("=" * 50)
        print(f"L1 内存缓存:")
        print(f"  大小: {stats['l1']['size']}/{stats['l1']['max_size']}")
        print(f"  命中: {stats['l1']['hits']}, 未命中: {stats['l1']['misses']}")
        print(f"  命中率: {stats['l1']['hit_rate']:.2%}")

        if "l2" in stats:
            print(f"\nL2 磁盘缓存:")
            print(f"  大小: {stats['l2']['size']}")
            print(f"  占用: {stats['l2']['total_size_mb']:.1f}MB/{stats['l2']['max_size_mb']:.1f}MB")
            print(f"  命中: {stats['l2']['hits']}, 未命中: {stats['l2']['misses']}")
            print(f"  命中率: {stats['l2']['hit_rate']:.2%}")

        print(f"\n整体统计:")
        print(f"  总命中: {stats['overall']['total_hits']}")
        print(f"  总未命中: {stats['overall']['total_misses']}")
        print(f"  总命中率: {stats['overall']['hit_rate']:.2%}")
        print("=" * 50)


# 全局缓存实例
_global_cache: Optional[MultiLevelCache] = None


def get_global_cache() -> MultiLevelCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        from src.core.config import MODELS_DIR

        _global_cache = MultiLevelCache(l1_size=2000, l2_dir=MODELS_DIR / "cache", l2_size_mb=1000)
    return _global_cache


def reset_global_cache():
    """重置全局缓存"""
    global _global_cache
    _global_cache = None
