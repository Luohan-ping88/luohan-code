"""
并行计算工具模块
提供统一的并行计算接口，支持joblib和multiprocessing
"""

import os
import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, TypeVar
from functools import wraps
import time

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')

# 检测可用的并行库
try:
    from joblib import Parallel, delayed
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False
    logger.warning("joblib未安装，将使用multiprocessing作为备选")

try:
    import multiprocessing as mp
    MULTIPROCESSING_AVAILABLE = True
except ImportError:
    MULTIPROCESSING_AVAILABLE = False


def get_optimal_n_jobs(n_jobs: int = -1) -> int:
    """获取最优的并行作业数"""
    cpu_count = os.cpu_count() or 1
    
    if n_jobs == -1:
        # 使用所有CPU，但保留1个给系统
        return max(1, cpu_count - 1)
    elif n_jobs == -2:
        # 使用一半CPU
        return max(1, cpu_count // 2)
    elif n_jobs <= 0:
        return 1
    else:
        return min(n_jobs, cpu_count)


def parallel_map(
    func: Callable[[T], R],
    iterable: Iterable[T],
    n_jobs: int = -1,
    backend: str = 'auto',
    prefer: str = 'processes',
    verbose: int = 0,
    timeout: Optional[float] = None
) -> List[R]:
    """
    并行映射函数
    
    Args:
        func: 要执行的函数
        iterable: 可迭代对象
        n_jobs: 并行作业数，-1表示使用所有CPU
        backend: 后端类型 ('auto', 'joblib', 'multiprocessing', 'threading')
        prefer: 偏好 ('processes', 'threads')
        verbose: 详细程度
        timeout: 超时时间（秒）
    
    Returns:
        结果列表
    """
    items = list(iterable)
    if not items:
        return []
    
    n_jobs = get_optimal_n_jobs(n_jobs)
    
    # 如果只有一个项目或n_jobs为1，直接串行执行
    if len(items) == 1 or n_jobs == 1:
        return [func(item) for item in items]
    
    # 选择后端
    if backend == 'auto':
        if JOBLIB_AVAILABLE:
            backend = 'joblib'
        elif MULTIPROCESSING_AVAILABLE:
            backend = 'multiprocessing'
        else:
            backend = 'serial'
    
    start_time = time.time()
    
    if backend == 'joblib' and JOBLIB_AVAILABLE:
        try:
            results = Parallel(n_jobs=n_jobs, prefer=prefer, verbose=verbose)(
                delayed(func)(item) for item in items
            )
            logger.debug(f"joblib并行执行完成: {len(items)}项, {time.time()-start_time:.3f}s")
            return list(results)
        except Exception as e:
            logger.warning(f"joblib执行失败，回退到串行: {e}")
            return [func(item) for item in items]
    
    elif backend == 'multiprocessing' and MULTIPROCESSING_AVAILABLE:
        try:
            with mp.Pool(processes=n_jobs) as pool:
                if timeout:
                    results = pool.map_async(func, items).get(timeout=timeout)
                else:
                    results = pool.map(func, items)
                logger.debug(f"multiprocessing并行执行完成: {len(items)}项, {time.time()-start_time:.3f}s")
                return results
        except Exception as e:
            logger.warning(f"multiprocessing执行失败，回退到串行: {e}")
            return [func(item) for item in items]
    
    elif backend == 'threading':
        from concurrent.futures import ThreadPoolExecutor, as_completed
        try:
            with ThreadPoolExecutor(max_workers=n_jobs) as executor:
                futures = {executor.submit(func, item): i for i, item in enumerate(items)}
                results = [None] * len(items)
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        results[idx] = future.result(timeout=timeout)
                    except Exception as e:
                        logger.error(f"线程执行错误: {e}")
                        results[idx] = None
                logger.debug(f"threading并行执行完成: {len(items)}项, {time.time()-start_time:.3f}s")
                return results
        except Exception as e:
            logger.warning(f"threading执行失败，回退到串行: {e}")
            return [func(item) for item in items]
    
    else:
        # 串行执行
        return [func(item) for item in items]


def parallel_starmap(
    func: Callable,
    iterable: Iterable[Tuple],
    n_jobs: int = -1,
    backend: str = 'auto',
    prefer: str = 'processes'
) -> List[Any]:
    """
    并行starmap（支持多参数）
    """
    items = list(iterable)
    if not items:
        return []
    
    def wrapper(args):
        return func(*args)
    
    return parallel_map(wrapper, items, n_jobs, backend, prefer)


class ParallelExecutor:
    """并行执行器 - 支持批量任务"""
    
    def __init__(self, n_jobs: int = -1, backend: str = 'auto', prefer: str = 'processes'):
        self.n_jobs = get_optimal_n_jobs(n_jobs)
        self.backend = backend
        self.prefer = prefer
        self._stats = {
            'tasks_executed': 0,
            'total_time': 0.0,
            'parallel_calls': 0
        }
    
    def map(self, func: Callable[[T], R], iterable: Iterable[T]) -> List[R]:
        """并行映射"""
        start = time.time()
        results = parallel_map(func, iterable, self.n_jobs, self.backend, self.prefer)
        elapsed = time.time() - start
        
        self._stats['tasks_executed'] += len(results)
        self._stats['total_time'] += elapsed
        self._stats['parallel_calls'] += 1
        
        return results
    
    def starmap(self, func: Callable, iterable: Iterable[Tuple]) -> List[Any]:
        """并行starmap"""
        return parallel_starmap(func, iterable, self.n_jobs, self.backend, self.prefer)
    
    def batch_process(
        self,
        func: Callable[[T], R],
        items: List[T],
        batch_size: int = 10,
        show_progress: bool = False
    ) -> List[R]:
        """分批处理大量数据"""
        results = []
        total_batches = (len(items) + batch_size - 1) // batch_size
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = self.map(func, batch)
            results.extend(batch_results)
            
            if show_progress:
                batch_num = i // batch_size + 1
                logger.info(f"批次进度: {batch_num}/{total_batches}")
        
        return results
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        avg_time = (self._stats['total_time'] / self._stats['parallel_calls'] 
                   if self._stats['parallel_calls'] > 0 else 0)
        return {
            **self._stats,
            'avg_time_per_call': avg_time,
            'n_jobs': self.n_jobs,
            'backend': self.backend
        }


def parallel_decorator(n_jobs: int = -1, backend: str = 'auto', prefer: str = 'processes'):
    """并行装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 检查是否有可并行化的参数
            # 这里简化处理，实际应用中需要根据具体情况调整
            return func(*args, **kwargs)
        
        # 添加并行map方法
        def parallel_method(iterable: Iterable, *args, **kwargs):
            return parallel_map(
                lambda x: func(x, *args, **kwargs),
                iterable,
                n_jobs=n_jobs,
                backend=backend,
                prefer=prefer
            )
        
        wrapper.parallel = parallel_method
        return wrapper
    return decorator


def chunked_parallel_map(
    func: Callable[[T], R],
    iterable: Iterable[T],
    chunk_size: int = 100,
    n_jobs: int = -1
) -> List[R]:
    """
    分块并行处理，适用于大量数据
    """
    items = list(iterable)
    if not items:
        return []
    
    results = []
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        chunk_results = parallel_map(func, chunk, n_jobs)
        results.extend(chunk_results)
    
    return results
