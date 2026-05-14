"""性能优化和调优

提供AI工具系统的性能优化功能，包括缓存、并发优化等。
"""

import functools
import asyncio
import time
from typing import Dict, Any, Optional, Callable, TypeVar, Generic, List
from dataclasses import dataclass
import threading

T = TypeVar("T")


@dataclass
class CacheItem(Generic[T]):
    """缓存项"""

    value: T  # 缓存值
    timestamp: float  # 缓存时间
    ttl: Optional[int]  # 过期时间（秒）


class SimpleCache:
    """简单缓存实现

    用于缓存工具执行结果，减少重复计算。
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """初始化缓存

        Args:
            max_size: 最大缓存数量
            default_ttl: 默认过期时间（秒）
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheItem] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._set_count = 0
        self._get_count = 0
        self._last_cleanup = time.time()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或过期返回None
        """
        with self._lock:
            self._get_count += 1

            # 定期清理过期项
            if time.time() - self._last_cleanup > 60:  # 每分钟清理一次
                self._clean_expired()
                self._last_cleanup = time.time()

            if key not in self._cache:
                self._misses += 1
                return None

            item = self._cache[key]
            # 检查是否过期
            if (
                item.ttl is not None
                and time.time() - item.timestamp > item.ttl
            ):
                del self._cache[key]
                self._evictions += 1
                self._misses += 1
                return None

            self._hits += 1
            return item.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None表示永不过期
        """
        with self._lock:
            self._set_count += 1

            # 如果缓存已满，删除最旧的项
            if len(self._cache) >= self.max_size:
                oldest_key = min(
                    self._cache, key=lambda k: self._cache[k].timestamp
                )
                del self._cache[oldest_key]
                self._evictions += 1

            # 设置缓存
            self._cache[key] = CacheItem(
                value=value,
                timestamp=time.time(),
                ttl=ttl if ttl is not None else self.default_ttl,
            )

    def delete(self, key: str) -> bool:
        """删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._set_count = 0
            self._get_count = 0

    def size(self) -> int:
        """获取缓存大小

        Returns:
            缓存项数量
        """
        with self._lock:
            return len(self._cache)

    def contains(self, key: str) -> bool:
        """检查缓存是否包含指定键

        Args:
            key: 缓存键

        Returns:
            是否包含
        """
        with self._lock:
            if key not in self._cache:
                return False

            item = self._cache[key]
            # 检查是否过期
            if (
                item.ttl is not None
                and time.time() - item.timestamp > item.ttl
            ):
                del self._cache[key]
                self._evictions += 1
                return False

            return True

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            缓存统计信息
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0

            return {
                "size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
                "max_size": self.max_size,
                "set_count": self._set_count,
                "get_count": self._get_count,
                "last_cleanup": self._last_cleanup,
            }

    def get_keys(self) -> List[str]:
        """获取所有缓存键

        Returns:
            缓存键列表
        """
        with self._lock:
            # 清理过期项
            self._clean_expired()
            return list(self._cache.keys())

    def _clean_expired(self) -> None:
        """清理过期的缓存项"""
        expired_keys = []
        for key, item in self._cache.items():
            if (
                item.ttl is not None
                and time.time() - item.timestamp > item.ttl
            ):
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]
            self._evictions += 1

    def warmup(self, items: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """缓存预热

        Args:
            items: 要预热的键值对
            ttl: 过期时间（秒）

        Returns:
            预热的项数
        """
        count = 0
        with self._lock:
            for key, value in items.items():
                self.set(key, value, ttl)
                count += 1
        return count


class ShardedCache:
    """分片缓存实现

    使用多个缓存实例来提高并发性能。
    """

    def __init__(
        self,
        num_shards: int = 8,
        max_size_per_shard: int = 1000,
        default_ttl: int = 3600,
    ):
        """初始化分片缓存

        Args:
            num_shards: 分片数量
            max_size_per_shard: 每个分片的最大缓存数量
            default_ttl: 默认过期时间（秒）
        """
        self.num_shards = num_shards
        self.shards = [
            SimpleCache(max_size=max_size_per_shard, default_ttl=default_ttl)
            for _ in range(num_shards)
        ]

    def _get_shard(self, key: str) -> SimpleCache:
        """根据键获取对应的分片

        Args:
            key: 缓存键

        Returns:
            对应的缓存分片
        """
        shard_index = hash(key) % self.num_shards
        return self.shards[shard_index]

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或过期返回None
        """
        shard = self._get_shard(key)
        return shard.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
        """
        shard = self._get_shard(key)
        shard.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        shard = self._get_shard(key)
        return shard.delete(key)

    def clear(self) -> None:
        """清空缓存"""
        for shard in self.shards:
            shard.clear()

    def size(self) -> int:
        """获取缓存大小

        Returns:
            缓存项数量
        """
        return sum(shard.size() for shard in self.shards)

    def contains(self, key: str) -> bool:
        """检查缓存是否包含指定键

        Args:
            key: 缓存键

        Returns:
            是否包含
        """
        shard = self._get_shard(key)
        return shard.contains(key)

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            缓存统计信息
        """
        stats = {
            "total_size": 0,
            "total_hits": 0,
            "total_misses": 0,
            "total_evictions": 0,
            "total_set_count": 0,
            "total_get_count": 0,
            "shards": [],
        }

        for i, shard in enumerate(self.shards):
            shard_stats = shard.get_stats()
            stats["total_size"] += shard_stats["size"]
            stats["total_hits"] += shard_stats["hits"]
            stats["total_misses"] += shard_stats["misses"]
            stats["total_evictions"] += shard_stats["evictions"]
            stats["total_set_count"] += shard_stats.get("set_count", 0)
            stats["total_get_count"] += shard_stats.get("get_count", 0)
            stats["shards"].append(
                {
                    "index": i,
                    "size": shard_stats["size"],
                    "hits": shard_stats["hits"],
                    "misses": shard_stats["misses"],
                    "evictions": shard_stats["evictions"],
                }
            )

        total = stats["total_hits"] + stats["total_misses"]
        stats["hit_rate"] = stats["total_hits"] / total if total > 0 else 0

        return stats

    def get_keys(self) -> List[str]:
        """获取所有缓存键

        Returns:
            缓存键列表
        """
        keys = []
        for shard in self.shards:
            keys.extend(shard.get_keys())
        return keys

    def warmup(self, items: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """缓存预热

        Args:
            items: 要预热的键值对
            ttl: 过期时间（秒）

        Returns:
            预热的项数
        """
        count = 0
        for key, value in items.items():
            self.set(key, value, ttl)
            count += 1
        return count


# 全局缓存实例
_global_cache = ShardedCache()


def get_cache() -> ShardedCache:
    """获取全局缓存实例

    Returns:
        缓存实例
    """
    return _global_cache


def cache_key_generator(func: Callable, *args, **kwargs) -> str:
    """生成缓存键

    Args:
        func: 函数
        *args: 函数参数
        **kwargs: 函数关键字参数

    Returns:
        缓存键
    """
    key_parts = [func.__module__, func.__name__]

    # 添加位置参数
    for arg in args:
        if isinstance(arg, (int, float, str, bool, tuple)):
            key_parts.append(str(arg))
        elif hasattr(arg, "__dict__"):
            # 对于对象，使用其__dict__的哈希值
            key_parts.append(str(hash(str(arg.__dict__))))

    # 添加关键字参数
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (int, float, str, bool, tuple)):
            key_parts.append(f"{k}={v}")
        elif hasattr(v, "__dict__"):
            key_parts.append(f"{k}={hash(str(v.__dict__))}")

    return "_".join(key_parts)


def cached(ttl: Optional[int] = None):
    """缓存装饰器

    用于缓存函数执行结果，支持同步和异步函数。

    Args:
        ttl: 过期时间（秒）

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = cache_key_generator(func, *args, **kwargs)

            # 尝试从缓存获取
            cached_value = get_cache().get(cache_key)
            if cached_value is not None:
                return cached_value

            # 执行异步函数
            result = await func(*args, **kwargs)

            # 缓存结果
            get_cache().set(cache_key, result, ttl)

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = cache_key_generator(func, *args, **kwargs)

            # 尝试从缓存获取
            cached_value = get_cache().get(cache_key)
            if cached_value is not None:
                return cached_value

            # 执行同步函数
            result = func(*args, **kwargs)

            # 缓存结果
            get_cache().set(cache_key, result, ttl)

            return result

        # 根据函数类型返回相应的包装器
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class RateLimiter:
    """速率限制器

    用于限制工具调用的速率，防止过度调用。
    """

    def __init__(self, max_calls: int, period: int):
        """初始化速率限制器

        Args:
            max_calls: 最大调用次数
            period: 时间窗口（秒）
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = []
        self._lock = threading.RLock()

    def allow(self) -> bool:
        """检查是否允许调用

        Returns:
            是否允许调用
        """
        with self._lock:
            # 清理过期的调用记录
            now = time.time()
            self.calls = [
                call for call in self.calls if now - call < self.period
            ]

            # 检查是否超过限制
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True

            return False

    def wait(self) -> None:
        """等待直到允许调用"""
        while not self.allow():
            time.sleep(0.1)


class PerformanceMonitor:
    """性能监控器

    用于监控工具执行的性能。
    """

    def __init__(self, log_file: Optional[str] = None):
        """初始化性能监控器

        Args:
            log_file: 性能日志文件路径
        """
        self.metrics = {}
        self._lock = threading.RLock()
        self.log_file = log_file
        self._execution_times = {}  # 存储每次执行的时间

    def start(self, name: str) -> None:
        """开始监控

        Args:
            name: 监控名称
        """
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = {
                    "count": 0,
                    "total_time": 0,
                    "start_time": None,
                    "min_time": float("inf"),
                    "max_time": 0,
                }

            if name not in self._execution_times:
                self._execution_times[name] = []

            self.metrics[name]["start_time"] = time.time()

    def stop(self, name: str) -> float:
        """停止监控

        Args:
            name: 监控名称

        Returns:
            执行时间（秒）
        """
        with self._lock:
            if (
                name not in self.metrics
                or self.metrics[name]["start_time"] is None
            ):
                return 0

            execution_time = time.time() - self.metrics[name]["start_time"]
            self.metrics[name]["count"] += 1
            self.metrics[name]["total_time"] += execution_time
            self.metrics[name]["min_time"] = min(
                self.metrics[name]["min_time"], execution_time
            )
            self.metrics[name]["max_time"] = max(
                self.metrics[name]["max_time"], execution_time
            )
            self.metrics[name]["start_time"] = None

            # 存储执行时间
            self._execution_times[name].append(execution_time)
            # 限制存储的执行时间数量
            if len(self._execution_times[name]) > 1000:
                self._execution_times[name] = self._execution_times[name][
                    -1000:
                ]

            # 记录到文件
            if self.log_file:
                self._log_performance(name, execution_time)

            return execution_time

    def _log_performance(self, name: str, execution_time: float) -> None:
        """记录性能数据到文件

        Args:
            name: 监控名称
            execution_time: 执行时间
        """
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{timestamp},{name},{execution_time:.6f}\n")
        except Exception:
            pass

    def get_metrics(self, name: str) -> Optional[Dict[str, Any]]:
        """获取监控指标

        Args:
            name: 监控名称

        Returns:
            监控指标
        """
        with self._lock:
            if name not in self.metrics:
                return None

            metric = self.metrics[name].copy()
            if metric["count"] > 0:
                metric["average_time"] = metric["total_time"] / metric["count"]
                # 计算标准差
                if len(self._execution_times.get(name, [])) > 1:
                    import statistics

                    metric["std_dev"] = statistics.stdev(
                        self._execution_times[name]
                    )
                else:
                    metric["std_dev"] = 0
            else:
                metric["average_time"] = 0
                metric["std_dev"] = 0

            return metric

    def list_metrics(self) -> List[str]:
        """列出所有监控指标

        Returns:
            监控名称列表
        """
        with self._lock:
            return list(self.metrics.keys())

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """获取所有监控指标

        Returns:
            所有监控指标
        """
        with self._lock:
            all_metrics = {}
            for name in self.metrics:
                all_metrics[name] = self.get_metrics(name)
            return all_metrics

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要

        Returns:
            性能摘要
        """
        with self._lock:
            total_calls = 0
            total_time = 0
            slowest_metric = None
            slowest_time = 0

            for name, metric in self.metrics.items():
                total_calls += metric["count"]
                total_time += metric["total_time"]
                if metric["average_time"] > slowest_time:
                    slowest_time = metric["average_time"]
                    slowest_metric = name

            return {
                "total_calls": total_calls,
                "total_time": total_time,
                "slowest_metric": slowest_metric,
                "slowest_average_time": slowest_time,
                "metrics_count": len(self.metrics),
            }

    def clear(self) -> None:
        """清空监控指标"""
        with self._lock:
            self.metrics.clear()
            self._execution_times.clear()


# 全局性能监控器
_global_monitor = PerformanceMonitor(log_file="./performance.log")


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器

    Returns:
        性能监控器实例
    """
    return _global_monitor


def monitored(name: Optional[str] = None):
    """性能监控装饰器

    用于监控函数执行性能，支持同步和异步函数。

    Args:
        name: 监控名称，默认为函数名

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        monitor_name = name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 开始监控
            get_performance_monitor().start(monitor_name)

            try:
                # 执行异步函数
                result = await func(*args, **kwargs)
                return result
            finally:
                # 停止监控
                get_performance_monitor().stop(monitor_name)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 开始监控
            get_performance_monitor().start(monitor_name)

            try:
                # 执行同步函数
                result = func(*args, **kwargs)
                return result
            finally:
                # 停止监控
                get_performance_monitor().stop(monitor_name)

        # 根据函数类型返回相应的包装器
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class AsyncOptimizer:
    """异步优化器

    用于优化异步操作。
    """

    def __init__(self, max_concurrency: int = 10):
        """初始化异步优化器

        Args:
            max_concurrency: 最大并发数
        """
        self.max_concurrency = max_concurrency
        self.semaphore = None

    async def init(self):
        """初始化信号量"""
        import asyncio

        self.semaphore = asyncio.Semaphore(self.max_concurrency)

    async def execute(self, coro: Callable):
        """执行协程，限制并发

        Args:
            coro: 协程函数

        Returns:
            协程执行结果
        """
        if self.semaphore is None:
            await self.init()

        async with self.semaphore:
            return await coro()

    async def execute_batch(self, coros: List[Callable]) -> List[Any]:
        """批量执行协程

        Args:
            coros: 协程函数列表

        Returns:
            协程执行结果列表
        """
        import asyncio

        tasks = []
        for coro in coros:
            tasks.append(self.execute(coro))

        return await asyncio.gather(*tasks)


class WorkStealingQueue:
    """工作窃取队列

    实现工作窃取算法，提高并发处理效率。
    """

    def __init__(self, max_size: int = 1000):
        """初始化工作窃取队列

        Args:
            max_size: 队列最大大小
        """
        self.max_size = max_size
        self.queues = []  # 每个工作线程的本地队列
        self._lock = threading.RLock()
        self._task_count = 0

    def add_worker(self):
        """添加工作线程

        Returns:
            工作线程ID
        """
        with self._lock:
            worker_id = len(self.queues)
            self.queues.append([])
            return worker_id

    def push(self, worker_id: int, task: Callable) -> bool:
        """推送任务到指定工作线程的本地队列

        Args:
            worker_id: 工作线程ID
            task: 任务函数

        Returns:
            是否推送成功
        """
        with self._lock:
            if worker_id >= len(self.queues):
                return False

            if len(self.queues[worker_id]) >= self.max_size:
                return False

            self.queues[worker_id].append(task)
            self._task_count += 1
            return True

    def pop(self, worker_id: int) -> Optional[Callable]:
        """从指定工作线程的本地队列弹出任务

        Args:
            worker_id: 工作线程ID

        Returns:
            任务函数，如果队列为空则返回None
        """
        with self._lock:
            if worker_id >= len(self.queues):
                return None

            queue = self.queues[worker_id]
            if not queue:
                # 尝试从其他队列窃取任务
                return self._steal(worker_id)

            task = queue.pop()
            self._task_count -= 1
            return task

    def _steal(self, worker_id: int) -> Optional[Callable]:
        """从其他工作线程窃取任务

        Args:
            worker_id: 当前工作线程ID

        Returns:
            任务函数，如果所有队列都为空则返回None
        """
        for i, queue in enumerate(self.queues):
            if i != worker_id and queue:
                # 从队列头部窃取任务（FIFO）
                task = queue.pop(0)
                self._task_count -= 1
                return task
        return None

    def size(self) -> int:
        """获取队列大小

        Returns:
            任务数量
        """
        with self._lock:
            return self._task_count

    def is_empty(self) -> bool:
        """检查队列是否为空

        Returns:
            是否为空
        """
        return self.size() == 0

    def clear(self) -> None:
        """清空队列"""
        with self._lock:
            for queue in self.queues:
                queue.clear()
            self._task_count = 0


class AsyncTaskQueue:
    """异步任务队列

    用于管理和执行异步任务。
    """

    def __init__(self, max_concurrency: int = 10, max_queue_size: int = 1000):
        """初始化异步任务队列

        Args:
            max_concurrency: 最大并发数
            max_queue_size: 队列最大大小
        """
        self.max_concurrency = max_concurrency
        self.max_queue_size = max_queue_size
        self.queue = []
        self._lock = threading.RLock()
        self._semaphore = None
        self._running = False
        self._tasks = set()

    async def init(self):
        """初始化信号量"""
        import asyncio

        self._semaphore = asyncio.Semaphore(self.max_concurrency)

    async def start(self):
        """启动任务队列"""
        if not self._running:
            self._running = True
            import asyncio

            asyncio.create_task(self._process_queue())

    async def stop(self):
        """停止任务队列"""
        self._running = False
        # 等待所有任务完成
        import asyncio

        if self._tasks:
            await asyncio.gather(*self._tasks)

    async def _process_queue(self):
        """处理队列中的任务"""
        import asyncio

        while self._running:
            if not self.queue:
                await asyncio.sleep(0.1)
                continue

            task = None
            with self._lock:
                if self.queue:
                    task = self.queue.pop(0)

            if task:
                async with self._semaphore:
                    task_future = asyncio.create_task(self._execute_task(task))
                    self._tasks.add(task_future)
                    task_future.add_done_callback(
                        lambda f: self._tasks.remove(f)
                    )

    async def _execute_task(self, task):
        """执行单个任务

        Args:
            task: 任务函数
        """
        try:
            if asyncio.iscoroutinefunction(task):
                await task()
            else:
                task()
        except Exception as e:
            print(f"Task execution error: {e}")

    def enqueue(self, task: Callable) -> bool:
        """入队任务

        Args:
            task: 任务函数

        Returns:
            是否入队成功
        """
        with self._lock:
            if len(self.queue) >= self.max_queue_size:
                return False

            self.queue.append(task)
            return True

    def size(self) -> int:
        """获取队列大小

        Returns:
            队列中的任务数量
        """
        with self._lock:
            return len(self.queue)

    def clear(self) -> None:
        """清空队列"""
        with self._lock:
            self.queue.clear()


class LoadBalancer:
    """负载均衡器

    用于在多个服务实例之间分配负载。
    """

    def __init__(self):
        """初始化负载均衡器"""
        self.services = {}
        self.health_checks = {}

    def register_service(
        self, service_id: str, service_url: str, weight: int = 1
    ):
        """注册服务

        Args:
            service_id: 服务ID
            service_url: 服务URL
            weight: 服务权重
        """
        self.services[service_id] = {
            "url": service_url,
            "weight": weight,
            "health": True,
            "last_check": time.time(),
        }
        # 启动健康检查
        self.health_checks[service_id] = self._start_health_check(service_id)

    def unregister_service(self, service_id: str):
        """注销服务

        Args:
            service_id: 服务ID
        """
        if service_id in self.services:
            del self.services[service_id]
        if service_id in self.health_checks:
            self.health_checks[service_id].cancel()
            del self.health_checks[service_id]

    def get_service(self) -> Optional[str]:
        """获取服务URL

        Returns:
            服务URL
        """
        # 过滤健康的服务
        healthy_services = [
            (service_id, info)
            for service_id, info in self.services.items()
            if info["health"]
        ]

        if not healthy_services:
            return None

        # 根据权重选择服务
        import random

        total_weight = sum(info["weight"] for _, info in healthy_services)
        r = random.randint(1, total_weight)
        current_weight = 0

        for service_id, info in healthy_services:
            current_weight += info["weight"]
            if r <= current_weight:
                return info["url"]

        return healthy_services[0][1]["url"]

    def _start_health_check(self, service_id: str):
        """启动健康检查

        Args:
            service_id: 服务ID

        Returns:
            健康检查任务
        """
        import asyncio

        async def health_check():
            while True:
                if service_id not in self.services:
                    break

                service_info = self.services[service_id]
                try:
                    # 简单的健康检查
                    import aiohttp

                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"{service_info['url']}/api/health"
                        ) as response:
                            service_info["health"] = response.status == 200
                except Exception:
                    service_info["health"] = False

                service_info["last_check"] = time.time()
                await asyncio.sleep(30)  # 每30秒检查一次

        loop = asyncio.get_event_loop()
        return loop.create_task(health_check())

    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """列出所有服务

        Returns:
            服务列表
        """
        return self.services


class AutoScaler:
    """自动扩展器

    根据系统负载自动调整资源。
    """

    def __init__(
        self,
        min_instances: int = 1,
        max_instances: int = 10,
        cpu_threshold: float = 0.7,
        memory_threshold: float = 0.8,
    ):
        """初始化自动扩展器

        Args:
            min_instances: 最小实例数
            max_instances: 最大实例数
            cpu_threshold: CPU阈值
            memory_threshold: 内存阈值
        """
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.instances = {}
        self.instance_counter = 0

    def get_instance_count(self) -> int:
        """获取实例数量

        Returns:
            实例数量
        """
        return len(self.instances)

    def scale(self, cpu_usage: float, memory_usage: float) -> Dict[str, Any]:
        """执行扩展决策

        Args:
            cpu_usage: CPU使用率
            memory_usage: 内存使用率

        Returns:
            扩展决策
        """
        current_instances = len(self.instances)
        decision = {"action": "no_change", "instances": current_instances}

        # 扩展逻辑
        if (
            cpu_usage > self.cpu_threshold
            or memory_usage > self.memory_threshold
        ):
            if current_instances < self.max_instances:
                new_instance_id = self._create_instance()
                decision = {
                    "action": "scale_up",
                    "instances": current_instances + 1,
                    "instance_id": new_instance_id,
                }
        elif (
            cpu_usage < self.cpu_threshold * 0.5
            and memory_usage < self.memory_threshold * 0.5
        ):
            if current_instances > self.min_instances:
                removed_instance_id = self._remove_instance()
                decision = {
                    "action": "scale_down",
                    "instances": current_instances - 1,
                    "instance_id": removed_instance_id,
                }

        return decision

    def _create_instance(self) -> str:
        """创建实例

        Returns:
            实例ID
        """
        instance_id = f"instance_{self.instance_counter}"
        self.instance_counter += 1

        # 这里只是模拟创建实例，实际应该启动一个新的服务实例
        self.instances[instance_id] = {
            "id": instance_id,
            "status": "running",
            "created_at": time.time(),
        }

        return instance_id

    def _remove_instance(self) -> str:
        """移除实例

        Returns:
            实例ID
        """
        if not self.instances:
            return None

        # 移除最早创建的实例
        oldest_instance = min(
            self.instances.items(), key=lambda x: x[1]["created_at"]
        )
        instance_id = oldest_instance[0]
        del self.instances[instance_id]

        return instance_id

    def list_instances(self) -> Dict[str, Dict[str, Any]]:
        """列出所有实例

        Returns:
            实例列表
        """
        return self.instances


# 全局异步优化器
_global_async_optimizer = AsyncOptimizer()
# 全局工作窃取队列
_global_work_stealing_queue = WorkStealingQueue()
# 全局异步任务队列
_global_task_queue = AsyncTaskQueue()
# 全局负载均衡器
_global_load_balancer = LoadBalancer()
# 全局自动扩展器
_global_auto_scaler = AutoScaler()


def get_async_optimizer() -> AsyncOptimizer:
    """获取全局异步优化器

    Returns:
        异步优化器实例
    """
    return _global_async_optimizer


def get_work_stealing_queue() -> WorkStealingQueue:
    """获取全局工作窃取队列

    Returns:
        工作窃取队列实例
    """
    return _global_work_stealing_queue


def get_task_queue() -> AsyncTaskQueue:
    """获取全局异步任务队列

    Returns:
        异步任务队列实例
    """
    return _global_task_queue


def get_load_balancer() -> LoadBalancer:
    """获取全局负载均衡器

    Returns:
        负载均衡器实例
    """
    return _global_load_balancer


def get_auto_scaler() -> AutoScaler:
    """获取全局自动扩展器

    Returns:
        自动扩展器实例
    """
    return _global_auto_scaler


# 工具执行优化装饰器
def optimized_tool(func: Callable) -> Callable:
    """工具执行优化装饰器

    为工具添加缓存和性能监控。
    """

    @functools.wraps(func)
    @cached(ttl=300)  # 5分钟缓存
    @monitored()
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper
