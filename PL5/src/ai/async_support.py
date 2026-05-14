"""并发执行和异步支持

提供工具系统的并发执行能力和异步支持。
"""

import asyncio
import concurrent.futures
from typing import Dict, List, Any, Optional, Callable, Coroutine
from dataclasses import dataclass
import time
import threading

from .ai_types import ToolResult


class ConcurrencyManager:
    """并发管理器

    管理并发执行的线程池和协程池。
    """

    def __init__(self, max_workers: int = 10):
        """初始化并发管理器

        Args:
            max_workers: 最大工作线程数
        """
        self.max_workers = max_workers
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        )
        self.semaphore = asyncio.Semaphore(max_workers)
        self.lock = threading.RLock()
        self.running_tasks = 0

    def execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """同步执行函数

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果
        """
        return self.thread_pool.submit(func, *args, **kwargs).result()

    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """异步执行函数

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果
        """
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.thread_pool, func, *args, **kwargs
            )

    async def execute_async_coroutine(self, coro: Coroutine) -> Any:
        """执行协程

        Args:
            coro: 要执行的协程

        Returns:
            协程执行结果
        """
        async with self.semaphore:
            return await coro

    async def execute_batch(
        self, tasks: List[Callable], *args, **kwargs
    ) -> List[Any]:
        """批量执行任务

        Args:
            tasks: 任务列表
            *args: 任务参数
            **kwargs: 任务关键字参数

        Returns:
            任务执行结果列表
        """
        async_tasks = []
        for task in tasks:
            async_tasks.append(self.execute_async(task, *args, **kwargs))

        return await asyncio.gather(*async_tasks)

    def shutdown(self, wait: bool = True):
        """关闭线程池

        Args:
            wait: 是否等待所有任务完成
        """
        self.thread_pool.shutdown(wait=wait)

    def __enter__(self):
        """【V10.4新增】上下文管理器支持"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """【V10.4新增】退出时自动释放资源"""
        self.shutdown()
        return False

    def __del__(self):
        """【V10.4新增】析构时确保资源释放"""
        try:
            self.shutdown(wait=False)
        except Exception:
            pass

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息
        """
        return {
            "max_workers": self.max_workers,
            "running_tasks": self.running_tasks,
        }


class AsyncBatchExecutor:
    """异步批量执行器

    用于批量执行工具调用。
    """

    def __init__(
        self, concurrency_manager: Optional[ConcurrencyManager] = None
    ):
        """初始化批量执行器

        Args:
            concurrency_manager: 并发管理器
        """
        self.concurrency_manager = concurrency_manager or ConcurrencyManager()

    async def execute_tools(
        self, tool_calls: List[Dict[str, Any]]
    ) -> List[ToolResult]:
        """批量执行工具

        Args:
            tool_calls: 工具调用列表，每个元素包含 "tool" 和 "params"

        Returns:
            工具执行结果列表
        """
        from .registry import get_registry

        registry = get_registry()
        tasks = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("tool")
            params = tool_call.get("params", {})

            async def execute_tool(tool_name, params):
                return registry.execute_tool(tool_name, params)

            tasks.append(execute_tool(tool_name, params))

        # 限制并发数量
        semaphore = asyncio.Semaphore(self.concurrency_manager.max_workers)

        async def execute_with_semaphore(task):
            async with semaphore:
                return await task

        semaphore_tasks = [execute_with_semaphore(task) for task in tasks]
        return await asyncio.gather(*semaphore_tasks)

    async def execute_functions(
        self, functions: List[Callable], *args, **kwargs
    ) -> List[Any]:
        """批量执行函数

        Args:
            functions: 函数列表
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果列表
        """
        tasks = []
        for func in functions:
            tasks.append(
                self.concurrency_manager.execute_async(func, *args, **kwargs)
            )

        return await asyncio.gather(*tasks)

    def execute_sync_batch(
        self, functions: List[Callable], *args, **kwargs
    ) -> List[Any]:
        """同步批量执行函数

        Args:
            functions: 函数列表
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果列表
        """
        results = []
        for func in functions:
            result = self.concurrency_manager.execute_sync(
                func, *args, **kwargs
            )
            results.append(result)
        return results


@dataclass
class AsyncToolResult:
    """异步工具执行结果"""

    task_id: str  # 任务ID
    success: bool  # 执行是否成功
    data: Any = None  # 结果数据
    error: Optional[str] = None  # 错误信息
    execution_time: float = 0.0  # 执行时间(秒)


class AsyncToolRunner:
    """异步工具运行器

    用于异步执行工具。
    """

    def __init__(self):
        """初始化异步工具运行器"""
        self.concurrency_manager = ConcurrencyManager()

    async def run_tool(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> AsyncToolResult:
        """异步运行工具

        Args:
            tool_name: 工具名称
            parameters: 工具参数

        Returns:
            异步工具执行结果
        """
        from .registry import get_registry

        registry = get_registry()
        task_id = f"task_{int(time.time() * 1000)}"

        start_time = time.time()

        try:
            result = await self.concurrency_manager.execute_async(
                registry.execute_tool, tool_name, parameters
            )

            execution_time = time.time() - start_time

            return AsyncToolResult(
                task_id=task_id,
                success=result.success,
                data=result.data,
                error=result.error,
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = time.time() - start_time

            return AsyncToolResult(
                task_id=task_id,
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def run_tools(
        self, tool_calls: List[Dict[str, Any]]
    ) -> List[AsyncToolResult]:
        """异步运行多个工具

        Args:
            tool_calls: 工具调用列表

        Returns:
            异步工具执行结果列表
        """
        tasks = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool")
            params = tool_call.get("params", {})
            tasks.append(self.run_tool(tool_name, params))

        return await asyncio.gather(*tasks)

    def shutdown(self):
        """关闭运行器"""
        self.concurrency_manager.shutdown()


# 全局并发管理器实例
_global_concurrency_manager = None


def get_concurrency_manager() -> ConcurrencyManager:
    """获取全局并发管理器

    Returns:
        并发管理器实例
    """
    global _global_concurrency_manager
    if _global_concurrency_manager is None:
        _global_concurrency_manager = ConcurrencyManager()
    return _global_concurrency_manager


def reset_concurrency_manager():
    """重置全局并发管理器"""
    global _global_concurrency_manager
    if _global_concurrency_manager:
        _global_concurrency_manager.shutdown()
    _global_concurrency_manager = None


# 异步工具装饰器
def async_tool(func):
    """异步工具装饰器

    将同步工具函数转换为异步函数。
    """

    async def wrapper(*args, **kwargs):
        concurrency_manager = get_concurrency_manager()
        return await concurrency_manager.execute_async(func, *args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper
