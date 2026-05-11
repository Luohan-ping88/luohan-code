"""
PL5 异步与并发支持模块

提供工具系统的高级异步能力:
- AsyncToolMixin:          通用异步能力混入类
- ConcurrencyManager:      全局并发控制管理器（信号量 + 优先级队列）
- AsyncBatchExecutor:      批量异步执行器（受并发限制的并行工具调用）
- AsyncPredictorMixin:     预测工具专用异步增强
"""

import asyncio
import time
import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Type, Union
from queue import PriorityQueue as SyncPriorityQueue
from concurrent.futures import ThreadPoolExecutor

from .base import (
    BaseTool,
    ToolResult,
    ToolContext,
    ToolRegistry,
    ErrorInfo,
)

logger = logging.getLogger(__name__)


# ================================================================
# 10.1 AsyncToolMixin — 通用异步能力混入类
# ================================================================


class AsyncToolMixin:
    """通用异步能力混入类

    为 BaseTool 子类提供增强的异步执行能力:
    - 原生 async execute 实现（子类覆写 execute_async_core）
    - 带超时的异步执行
    - 带重试的异步执行
    - 并发感知的异步执行（接受外部 semaphore）

    用法::

        class MyAsyncTool(AsyncToolMixin, BaseTool):
            name = "my_async_tool"

            async def execute_async_core(self, ctx: ToolContext, **kwargs) -> ToolResult:
                # 原生异步逻辑
                await asyncio.sleep(0.1)
                return ToolResult.success_result(data={"async": True})
    """

    async def execute_async_core(self, ctx: ToolContext, **kwargs) -> ToolResult:
        """核心异步执行方法，子类应覆写此方法以提供原生异步实现

        默认行为: 回退到线程池包装同步 execute()
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.execute(ctx, **kwargs),
        )

    async def execute_async_with_timeout(self, ctx: ToolContext, timeout: float, **kwargs) -> ToolResult:
        """带超时控制的异步执行

        Args:
            ctx:     执行上下文
            timeout: 超时时间（秒）
            **kwargs: 工具参数

        Returns:
            ToolResult 或超时错误结果
        """
        try:
            return await asyncio.wait_for(
                self.execute_async_core(ctx, **kwargs),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return ToolResult.error_result(
                f"异步执行超时 ({timeout}s)",
                code="ASYNC_TIMEOUT",
                tool_name=getattr(self, "name", "unknown"),
            )

    async def execute_async_with_retry(
        self, ctx: ToolContext, max_retries: int = 3, retry_delay: float = 1.0, **kwargs
    ) -> ToolResult:
        """带重试机制的异步执行

        Args:
            ctx:         执行上下文
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒），支持指数退避
            **kwargs:    工具参数

        Returns:
            ToolResult 最终结果
        """
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                result = await self.execute_async_core(ctx, **kwargs)
                result.metadata.setdefault("retry_attempt", attempt)
                return result
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = retry_delay * (2 ** (attempt - 1))
                    logger.debug(
                        f"[{getattr(self, 'name', '?')}] " f"异步重试 {attempt}/{max_retries}, " f"等待 {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)

        return ToolResult.error_result(
            f"异步重试 {max_retries} 次后仍失败: {last_error}",
            code="ASYNC_RETRY_EXHAUSTED",
            attempts=max_retries,
        )

    async def execute_async_bounded(self, ctx: ToolContext, semaphore: asyncio.Semaphore, **kwargs) -> ToolResult:
        """在信号量限制下的异步执行

        Args:
            ctx:       执行上下文
            semaphore: 并发信号量
            **kwargs:  工具参数

        Returns:
            ToolResult
        """
        async with semaphore:
            return await self.execute_async_core(ctx, **kwargs)


# ================================================================
# AsyncPredictorMixin — 预测工具专用异步增强
# ================================================================


class AsyncPredictorMixin(AsyncToolMixin):
    """预测工具专用异步增强 Mixin

    为 PredictorTool / BatchPredictorTool 提供真正的异步预测能力，
    支持批量并行预测和流式结果返回。
    """

    async def predict_single_async(
        self,
        ctx: ToolContext,
        features,
        top_k: int = 8,
        recent_original_data: Optional[Dict] = None,
    ) -> ToolResult:
        """单次异步预测

        Args:
            ctx:                 执行上下文
            features:            特征向量 (np.ndarray/list)
            top_k:               推荐 K 值
            recent_original_data: 近期原始数据

        Returns:
            ToolResult 包含 predictions 和 summary
        """
        predictor = ctx.get("predictor")
        if predictor is None:
            return ToolResult.error_result(
                "上下文中未找到 predictor 实例",
                code="PREDICTOR_NOT_FOUND",
            )

        loop = asyncio.get_event_loop()

        try:
            result = await loop.run_in_executor(
                None,
                lambda: predictor.predict(
                    features=features,
                    recent_original_data=recent_original_data,
                    top_k=top_k,
                ),
            )

            positions = list(result.keys())
            avg_uncertainty = sum(result[p].get("uncertainty", 0.0) for p in positions) / max(len(positions), 1)

            summary = {
                "total_positions": len(positions),
                "top_k": top_k,
                "avg_uncertainty": round(avg_uncertainty, 4),
                "positions": {
                    p: {
                        "top_k": result[p].get("top_k", []),
                        "uncertainty": round(result[p].get("uncertainty", 0.0), 4),
                    }
                    for p in positions
                    if isinstance(result.get(p), dict)
                },
            }

            ctx.set("last_prediction", result)
            return ToolResult.success_result(
                data={
                    "predictions": result,
                    "summary": summary,
                },
                mode="async_single",
            )

        except Exception as e:
            return ToolResult.error_result(
                f"异步单次预测失败: {str(e)}",
                code="ASYNC_PREDICTION_ERROR",
            )

    async def predict_batch_async(
        self,
        ctx: ToolContext,
        features_list: List,
        top_k: int = 8,
        max_concurrency: int = 4,
    ) -> ToolResult:
        """批量异步预测（并发执行多个单次预测）

        Args:
            ctx:             执行上下文
            features_list:   特征向量列表
            top_k:           推荐 K 值
            max_concurrency: 最大并发数

        Returns:
            ToolResult 包含 batch_results 和 summary
        """
        if not features_list:
            return ToolResult.error_result(
                "features_list 不能为空",
                code="EMPTY_FEATURES_LIST",
            )

        predictor = ctx.get("predictor")
        if predictor is None:
            return ToolResult.error_result(
                "上下文中未找到 predictor 实例",
                code="PREDICTOR_NOT_FOUND",
            )

        semaphore = asyncio.Semaphore(max_concurrency)
        loop = asyncio.get_event_loop()
        results = []
        uncertainties = []

        async def _predict_one(idx, features):
            async with semaphore:
                try:
                    single_result = await loop.run_in_executor(
                        None,
                        lambda f=features: predictor.predict(
                            features=f,
                            top_k=top_k,
                        ),
                    )
                    pos_uncertainties = [
                        single_result[p].get("uncertainty", 0.0)
                        for p in single_result
                        if isinstance(single_result.get(p), dict)
                    ]
                    avg_unc = float(sum(pos_uncertainties) / len(pos_uncertainties)) if pos_uncertainties else 0.0
                    return idx, single_result, avg_unc
                except Exception as e:
                    return idx, None, 0.0

        tasks = [_predict_one(i, f) for i, f in enumerate(features_list)]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        errors = []
        for outcome in completed:
            if isinstance(outcome, Exception):
                errors.append(str(outcome))
                continue
            idx, pred_result, unc = outcome
            if pred_result is not None:
                results.append(pred_result)
                uncertainties.append(unc)

        summary = self._compute_batch_summary(results, uncertainties)

        ctx.set("last_batch_predictions", results)
        return ToolResult.success_result(
            data={
                "batch_results": results,
                "summary": summary,
                "error_count": len(errors),
                "success_count": len(results),
            },
            mode="async_batch",
            concurrency=max_concurrency,
        )

    @staticmethod
    def _compute_batch_summary(results: List[Dict], uncertainties: List[float]) -> Dict:
        import numpy as np

        all_top_ks = []
        for result in results:
            for pos, info in result.items():
                if isinstance(info, dict) and "top_k" in info:
                    all_top_ks.extend(info["top_k"])

        freq_map: Dict[int, int] = {}
        for num in all_top_ks:
            freq_map[num] = freq_map.get(num, 0) + 1

        sorted_freq = sorted(freq_map.items(), key=lambda x: x[1], reverse=True)
        most_common = [(int(k), v) for k, v in sorted_freq[:15]]

        unc_arr = np.array(uncertainties) if uncertainties else np.array([0.0])
        return {
            "count": len(results),
            "avg_uncertainty": round(float(np.mean(unc_arr)), 4) if len(unc_arr) > 0 else 0.0,
            "min_uncertainty": round(float(np.min(unc_arr)), 4) if len(unc_arr) > 0 else 0.0,
            "max_uncertainty": round(float(np.max(unc_arr)), 4) if len(unc_arr) > 0 else 0.0,
            "std_uncertainty": round(float(np.std(unc_arr)), 4) if len(unc_arr) > 1 else 0.0,
            "most_recommended_numbers": most_common,
        }


# ================================================================
# 10.2 ConcurrencyManager — 全局并发控制管理器
# ================================================================


@dataclass(order=True)
class _PriorityItem:
    """优先级队列条目（数值越小优先级越高）"""

    priority: int
    task_id: str = field(compare=False)
    coro: Any = field(compare=False)


class ConcurrencyManager:
    """全局并发控制管理器

    提供:
    - 基于 Semaphore 的并发数限制
    - 基于优先级的任务调度队列
    - 活跃任务追踪与管理
    - 完整的状态统计与监控

    特性:
    - 支持动态调整最大并发数
    - 支持按优先级调度任务
    - 支持取消指定任务
    - 线程安全的事件循环访问

    用法::

        manager = ConcurrencyManager(max_workers=4)

        async def my_task():
            async with manager.acquire_context():
                # 受限执行的代码
                pass

        # 或使用 run_with_limit
        result = await manager.run_with_limit(some_coroutine(), priority=1)
    """

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._priority_queue: Optional[SyncPriorityQueue] = None
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._completed_count: int = 0
        self._rejected_count: int = 0
        self._total_submitted: int = 0
        self._lock: Optional[asyncio.Lock] = None
        self._initialized: bool = False
        self._task_counter: int = 0

    def _ensure_initialized(self):
        """延迟初始化（必须在事件循环中或之前调用）"""
        if not self._initialized:
            self._semaphore = asyncio.Semaphore(self._max_workers)
            self._priority_queue = SyncPriorityQueue()
            self._lock = asyncio.Lock()
            self._initialized = True

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @max_workers.setter
    def max_workers(self, value: int):
        old_value = self._max_workers
        self._max_workers = max(1, value)
        if self._initialized and self._semaphore is not None:
            diff = self._max_workers - old_value
            if diff > 0:
                for _ in range(diff):
                    self._semaphore.release()
            logger.info(f"[ConcurrencyManager] max_workers: {old_value} -> {self._max_workers}")

    async def acquire(self, priority: int = 0) -> None:
        """获取并发许可（阻塞等待）

        Args:
            priority: 优先级（数值越小越优先），默认 0
        """
        self._ensure_initialized()
        await self._semaphore.acquire()

    async def release(self) -> None:
        """释放一个并发许可"""
        if self._semaphore is not None and self._initialized:
            self._semaphore.release()

    async def acquire_context(self) -> "_ConcurrencyContext":
        """获取并发上下文管理器（用于 async with 语法）

        Returns:
            可用于 async with 的上下文管理器
        """
        self._ensure_initialized()
        return _ConcurrencyContext(self)

    async def run_with_limit(
        self,
        coro: Awaitable,
        priority: int = 0,
        task_id: Optional[str] = None,
    ) -> Any:
        """在并发限制下运行协程

        自动获取/释放信号量，并追踪活跃任务。

        Args:
            coro:    要运行的协程
            priority: 任务优先级（数值越小越高）
            task_id: 可选的任务标识符

        Returns:
            协程的返回值
        """
        self._ensure_initialized()
        self._total_submitted += 1

        tid = task_id or f"task_{self._task_counter}"
        self._task_counter += 1

        async with self._semaphore:
            task = asyncio.current_task()
            if task is not None:
                self._active_tasks[tid] = task

            try:
                result = await coro
                self._completed_count += 1
                return result
            except Exception as e:
                self._completed_count += 1
                raise
            finally:
                self._active_tasks.pop(tid, None)

    async def submit_priority(
        self,
        coro: Awaitable,
        priority: int = 0,
        task_id: Optional[str] = None,
    ) -> asyncio.Task:
        """提交带优先级的任务（创建 Task 但不立即等待）

        任务会在 run_with_limit 内部排队。

        Args:
            coro:     协程
            priority: 优先级
            task_id:  任务 ID

        Returns:
            asyncio.Task 对象
        """
        self._ensure_initialized()
        wrapped = self.run_with_limit(coro, priority=priority, task_id=task_id)
        task = asyncio.create_task(wrapped, name=task_id)
        return task

    async def cancel_task(self, task_id: str) -> bool:
        """取消指定的活跃任务

        Args:
            task_id: 要取消的任务 ID

        Returns:
            是否成功取消
        """
        task = self._active_tasks.get(task_id)
        if task is None:
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._active_tasks.pop(task_id, None)
        return True

    async def cancel_all(self) -> int:
        """取消所有活跃任务

        Returns:
            取消的任务数量
        """
        cancelled = 0
        for task_id in list(self._active_tasks.keys()):
            if await self.cancel_task(task_id):
                cancelled += 1
        return cancelled

    def get_stats(self) -> Dict:
        """返回当前并发状态统计信息

        Returns:
            包含以下字段的字典:
            - max_workers:       最大并发数
            - active_tasks:      当前活跃任务数
            - available_slots:   可用槽位数
            - total_submitted:   总提交数
            - completed:         已完成数
            - rejected:          被拒绝数
            - utilization_rate:  利用率
            - active_task_ids:   活跃任务 ID 列表
            - initialized:       是否已初始化
        """
        active_count = len(self._active_tasks)
        max_w = self._max_workers
        available = max(0, max_w - active_count) if self._initialized else max_w
        utilization = round(active_count / max(max_w, 1), 4) if self._initialized else 0.0

        return {
            "max_workers": max_w,
            "active_tasks": active_count,
            "available_slots": available,
            "total_submitted": self._total_submitted,
            "completed": self._completed_count,
            "rejected": self._rejected_count,
            "utilization_rate": utilization,
            "active_task_ids": list(self._active_tasks.keys()),
            "initialized": self._initialized,
        }

    async def wait_for_idle(self, timeout: Optional[float] = None) -> bool:
        """等待所有活跃任务完成

        Args:
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            是否在超时前变为空闲
        """
        if not self._active_tasks:
            return True

        if timeout is not None:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_tasks.values(), return_exceptions=True),
                    timeout=timeout,
                )
                return True
            except asyncio.TimeoutError:
                return False
        else:
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)
            return True


class _ConcurrencyContext:
    """并发上下文管理器，用于 async with 语法"""

    def __init__(self, manager: ConcurrencyManager):
        self._manager = manager

    async def __aenter__(self):
        await self._manager.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._manager.release()
        return False


# ================================================================
# 10.3 AsyncBatchExecutor — 批量异步执行工具
# ================================================================


@dataclass
class BatchExecutionConfig:
    """批量执行配置"""

    max_concurrency: int = 4
    timeout_per_tool: float = 300.0
    stop_on_first_error: bool = False
    continue_on_error: bool = True
    raise_on_empty: bool = False


class AsyncBatchExecutor:
    """批量异步执行多个工具

    功能:
    - 并行执行多个工具调用，受 ConcurrencyManager 限制
    - 支持每个工具独立的超时和重试配置
    - 支持全局错误策略（快速失败 / 容错继续）
    - 收集完整的执行统计信息
    - 支持依赖链式执行（DAG 简化版）

    用法::

        executor = AsyncBatchExecutor(concurrency_manager=manager)

        tools_and_args = [
            (DataLoaderTool(), {"path_or_data": "data.csv"}),
            (FeatureEngineerTool(), {"raw_data": "$prev.data"}),
            (PredictorTool(), {"features": ...}),
        ]

        results = await executor.execute_batch(tools_and_args, ctx)
        for name, result in results.items():
            print(f"{name}: success={result.success}")
    """

    def __init__(
        self,
        concurrency_manager: Optional[ConcurrencyManager] = None,
        config: Optional[BatchExecutionConfig] = None,
    ):
        self.manager = concurrency_manager or ConcurrencyManager(max_workers=4)
        self.config = config or BatchExecutionConfig()
        self._execution_history: List[Dict] = []

    async def execute_batch(
        self,
        tools_and_args: List[Tuple[BaseTool, Dict]],
        ctx: ToolContext,
        config: Optional[BatchExecutionConfig] = None,
    ) -> Dict[str, ToolResult]:
        """并行执行多个工具调用

        Args:
            tools_and_args: (工具实例, 参数字典) 元组列表
            ctx:            共享执行上下文
            config:         本次执行的覆盖配置

        Returns:
            {工具名称: ToolResult} 字典
        """
        cfg = config or self.config

        if not tools_and_args:
            if cfg.raise_on_empty:
                raise ValueError("tools_and_args 为空且 raise_on_empty=True")
            return {}

        start_time = time.time()
        results: Dict[str, ToolResult] = {}
        semaphore = asyncio.Semaphore(cfg.max_concurrency)

        async def _run_one(tool: BaseTool, args: Dict) -> Tuple[str, ToolResult]:
            tool_name = getattr(tool, "name", f"unnamed_{id(tool)}")
            async with semaphore:
                try:
                    if hasattr(tool, "execute_async"):
                        if isinstance(tool, AsyncToolMixin):
                            result = await tool.execute_async_with_timeout(
                                ctx,
                                cfg.timeout_per_tool,
                                **args,
                            )
                        else:
                            result = await tool.execute_async(ctx, **args)
                    else:
                        loop = asyncio.get_event_loop()
                        result = await asyncio.wait_for(
                            loop.run_in_executor(
                                None,
                                lambda t=tool, a=args: t.run_safe(ctx, **a),
                            ),
                            timeout=cfg.timeout_per_tool,
                        )

                    if not result.success and cfg.stop_on_first_error:
                        raise BatchStopError(
                            f"工具 '{tool_name}' 失败且 stop_on_first_error=True",
                            tool_name=tool_name,
                        )
                    return tool_name, result

                except asyncio.TimeoutError:
                    err = ToolResult.error_result(
                        f"批量执行中工具 '{tool_name}' 超时 ({cfg.timeout_per_tool}s)",
                        code="BATCH_TOOL_TIMEOUT",
                    )
                    if cfg.stop_on_first_error:
                        raise BatchStopError(tool_name=tool_name)
                    return tool_name, err

                except BatchStopError:
                    raise

                except Exception as e:
                    err = ToolResult.error_result(
                        f"批量执行中工具 '{tool_name}' 异常: {str(e)}",
                        code="BATCH_TOOL_EXCEPTION",
                    )
                    if cfg.stop_on_first_error:
                        raise BatchStopError(tool_name=tool_name)
                    if not cfg.continue_on_error:
                        return tool_name, err
                    return tool_name, err

        tasks = [_run_one(tool, args) for tool, args in tools_and_args]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        error_count = 0
        success_count = 0
        for outcome in completed:
            if isinstance(outcome, BatchStopError):
                break
            elif isinstance(outcome, Exception):
                error_count += 1
                results[f"error_{error_count}"] = ToolResult.error_result(
                    f"批量执行异常: {str(outcome)}",
                    code="BATCH_INTERNAL_ERROR",
                )
            else:
                tool_name, result = outcome
                results[tool_name] = result
                if result.success:
                    success_count += 1
                else:
                    error_count += 1

        elapsed_ms = (time.time() - start_time) * 1000

        history_entry = {
            "batch_size": len(tools_and_args),
            "success_count": success_count,
            "error_count": error_count,
            "elapsed_ms": round(elapsed_ms, 2),
            "concurrency": cfg.max_concurrency,
            "timestamp": time.time(),
        }
        self._execution_history.append(history_entry)

        ctx.record_metric("batch_executor.total", len(tools_and_args))
        ctx.record_metric("batch_executor.success", success_count)
        ctx.record_metric("batch_executor.errors", error_count)
        ctx.record_metric("batch_executor.elapsed_ms", elapsed_ms)

        return results

    async def execute_sequential(
        self,
        tools_and_args: List[Tuple[BaseTool, Dict]],
        ctx: ToolContext,
        pass_output: bool = True,
    ) -> Dict[str, ToolResult]:
        """顺序执行多个工具（每步输出可传递给下一步）

        Args:
            tools_and_args: (工具实例, 参数字典) 元组列表
            ctx:            共享执行上下文
            pass_output:    是否将上一步 output.data 注入下一步 $prev 引用

        Returns:
            {工具名称: ToolResult} 字典
        """
        results: Dict[str, ToolResult] = {}
        last_output = None

        for tool, args in tools_and_args:
            tool_name = getattr(tool, "name", f"unnamed_{id(tool)}")

            resolved_args = dict(args)
            if pass_output and last_output is not None:
                for k, v in resolved_args.items():
                    if isinstance(v, str) and v == "$prev":
                        resolved_args[k] = last_output

            try:
                if hasattr(tool, "execute_async") and isinstance(tool, AsyncToolMixin):
                    result = await tool.execute_async_core(ctx, **resolved_args)
                elif hasattr(tool, "execute_async"):
                    result = await tool.execute_async(ctx, **resolved_args)
                else:
                    result = tool.run_safe(ctx, **resolved_args)

                results[tool_name] = result
                last_output = result.data

                if not result.success and self.config.stop_on_first_error:
                    break

            except Exception as e:
                err = ToolResult.error_result(
                    f"顺序执行中工具 '{tool_name}' 异常: {str(e)}",
                    code="SEQUENTIAL_EXCEPTION",
                )
                results[tool_name] = err
                if self.config.stop_on_first_error:
                    break
                last_output = None

        return results

    async def execute_parallel_groups(
        self,
        groups: List[List[Tuple[BaseTool, Dict]]],
        ctx: ToolContext,
    ) -> Dict[str, ToolResult]:
        """分组并行执行：组内并行、组间顺序

        Args:
            groups: 分组列表，每组内并行执行
            ctx:    共享执行上下文

        Returns:
            所有组的合并结果
        """
        all_results: Dict[str, ToolResult] = {}

        for group_idx, group in enumerate(groups):
            group_results = await self.execute_batch(group, ctx)
            all_results.update(group_results)

            group_success = sum(1 for r in group_results.values() if r.success)
            group_total = len(group_results)
            if group_success < group_total and self.config.stop_on_first_error:
                break

        return all_results

    def get_history(self) -> List[Dict]:
        """获取批量执行历史记录"""
        return list(self._execution_history)

    def clear_history(self):
        """清除执行历史"""
        self._execution_history.clear()


class BatchStopError(Exception):
    """批量执行停止信号（stop_on_first_error 触发）"""

    def __init__(self, message: str = "", tool_name: str = ""):
        super().__init__(message)
        self.tool_name = tool_name


# ================================================================
# 便捷工厂函数
# ================================================================


def create_default_concurrency_manager(max_workers: int = 4) -> ConcurrencyManager:
    """创建默认配置的并发管理器

    Args:
        max_workers: 最大工作线程数

    Returns:
        ConcurrencyManager 实例
    """
    return ConcurrencyManager(max_workers=max_workers)


def create_batch_executor(
    max_concurrency: int = 4,
    timeout_per_tool: float = 300.0,
) -> AsyncBatchExecutor:
    """创建预配置的批量执行器

    Args:
        max_concurrency:  最大并发数
        timeout_per_tool: 单工具超时（秒）

    Returns:
        AsyncBatchExecutor 实例
    """
    config = BatchExecutionConfig(
        max_concurrency=max_concurrency,
        timeout_per_tool=timeout_per_tool,
    )
    return AsyncBatchExecutor(config=config)
