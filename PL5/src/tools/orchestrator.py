"""
PL5 工作流编排引擎与内置模板

提供:
- WorkflowStep:     工作流步骤定义（工具调用 + 控制参数）
- Workflow:         工作流定义（步骤编排 / 条件分支 / 并行组）
- WorkflowResult:   工作流执行结果（聚合各步骤输出 + 日志）
- WorkflowEngine:   执行引擎（线性 / 分支 / 并行 三种模式）
- BuiltInWorkflows: 预置工作流模板工厂
"""

import time
import asyncio
import copy
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .base import (
    BaseTool,
    ErrorInfo,
    ToolContext,
    ToolResult,
    ToolRegistry,
    get_registry,
)

logger = logging.getLogger(__name__)


# ── 数据结构 ────────────────────────────────────────────────────


@dataclass
class WorkflowStep:
    """工作流步骤

    每个步骤对应一次工具调用，支持丰富的控制参数:
    - 输入来源: 可指定从某个命名步骤获取输入，或默认使用上一步的输出
    - 条件执行: 通过 condition 函数动态决定是否执行此步
    - 容错策略: retry_count / continue_on_error 控制失败后的行为
    - 超时保护: timeout 限制单步最大执行时间
    - 并行分组: parallel_group 相同的步骤会被并行执行
    """

    tool_name: str
    args: Dict = field(default_factory=dict)
    input_from_step: Optional[str] = None
    condition: Optional[Callable[[Dict], bool]] = None
    retry_count: int = 0
    retry_delay: float = 1.0
    timeout: float = 300.0
    continue_on_error: bool = False
    parallel_group: Optional[str] = None

    def to_dict(self) -> Dict:
        d = {
            "tool_name": self.tool_name,
            "args": self.args,
            "input_from_step": self.input_from_step,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "timeout": self.timeout,
            "continue_on_error": self.continue_on_error,
            "parallel_group": self.parallel_group,
        }
        if self.condition is not None:
            d["condition"] = f"{self.condition.__module__}.{self.condition.__qualname__}"
        else:
            d["condition"] = None
        return d


@dataclass
class WorkflowResult:
    """工作流执行结果

    聚合所有步骤的执行结果，包含完整的执行日志和错误信息。
    """

    success: bool
    results: Dict[str, ToolResult]
    final_output: Any = None
    execution_log: List[Dict] = field(default_factory=list)
    total_time_ms: float = 0
    errors: List[ErrorInfo] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "final_output": ToolResult._serialize_data(self.final_output),
            "execution_log": self.execution_log,
            "total_time_ms": round(self.total_time_ms, 2),
            "errors": [e.to_dict() for e in self.errors],
            "step_count": len(self.results),
        }

    @property
    def step_count(self) -> int:
        return len(self.results)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def failed_steps(self) -> List[str]:
        return [k for k, v in self.results.items() if not v.success]


# ── 工作流定义 ────────────────────────────────────────────────


class Workflow:
    """工作流定义

    支持三种编排方式:
    1. 线性顺序: add_step() 依次添加，按顺序执行
    2. 并行分组: add_parallel() 将多个步骤归入同一 parallel_group 同时执行
    3. 条件分支: add_conditional() 根据 condition 选择 true_steps 或 false_steps

    用法示例::

        wf = Workflow("my_pipeline", "我的处理流水线")
        wf.add_step(WorkflowStep("data_loader", {"path_or_data": "data.csv"}))
        wf.add_step(WorkflowStep("feature_engineer", {"raw_data": "$prev.data"}))
        wf.add_step(WorkflowStep("predictor", {"features": "$prev.X"}))
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []
        self.state: Dict = {}
        self._step_counter = 0

    def add_step(self, step: WorkflowStep) -> "Workflow":
        """添加一个步骤到工作流末尾"""
        if not isinstance(step, WorkflowStep):
            raise TypeError(f"期望 WorkflowStep, 实际 {type(step).__name__}")
        if not step.tool_name:
            raise ValueError("WorkflowStep 的 tool_name 不能为空")
        self._step_counter += 1
        step._internal_id = f"step_{self._step_counter}"
        self.steps.append(step)
        return self

    def add_parallel(self, *steps: WorkflowStep) -> "Workflow":
        """添加一组并行步骤

        所有传入的步骤会被分配相同的 parallel_group 名称，
        引擎在执行时会对同组步骤使用并发执行。

        Args:
            *steps: 至少一个 WorkflowStep 实例

        Returns:
            self (链式调用)
        """
        if not steps:
            raise ValueError("add_parallel 需要至少一个步骤")
        group_name = f"parallel_{self._step_counter + 1}_{time.time():.0f}"
        for step in steps:
            step.parallel_group = group_name
            self.add_step(step)
        return self

    def add_conditional(
        self,
        condition: Callable[[Dict], bool],
        true_steps: List[WorkflowStep],
        false_steps: Optional[List[WorkflowStep]] = None,
    ) -> "Workflow":
        """添加条件分支

        在执行到此处时，引擎会评估 condition(ctx.state)，
        根据结果选择执行 true_steps 或 false_steps。

        Args:
            condition: 条件函数，接收 ctx.state 字典，返回 bool
            true_steps:  条件为 True 时执行的步骤列表
            false_steps: 条件为 False 时执行的步骤列表（可选）

        Returns:
            self (链式调用)
        """
        branch_marker = WorkflowStep(
            tool_name="__conditional_branch__",
            args={
                "__condition_ref__": condition,
                "__true_steps__": true_steps,
                "__false_steps__": false_steps or [],
            },
        )
        branch_marker.is_branch = True
        self.add_step(branch_marker)
        return self

    def insert_step(self, index: int, step: WorkflowStep) -> "Workflow":
        """在指定位置插入步骤"""
        if not isinstance(step, WorkflowStep):
            raise TypeError(f"期望 WorkflowStep, 实际 {type(step).__name__}")
        self._step_counter += 1
        step._internal_id = f"step_{self._step_counter}"
        self.steps.insert(index, step)
        return self

    def remove_step(self, index: int) -> "Workflow":
        """移除指定位置的步骤"""
        if 0 <= index < len(self.steps):
            self.steps.pop(index)
        return self

    def get_step(self, index: int) -> Optional[WorkflowStep]:
        """获取指定位置的步骤"""
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    def to_dict(self) -> Dict:
        """序列化为字典（可用于持久化或传输）"""
        steps_data = []
        for s in self.steps:
            sd = s.to_dict()
            if getattr(s, "is_branch", False):
                sd["is_branch"] = True
                true_raw = s.args.get("__true_steps__", [])
                false_raw = s.args.get("__false_steps__", [])
                sd["branch_true_steps"] = [ts.to_dict() for ts in true_raw]
                sd["branch_false_steps"] = [fs.to_dict() for fs in false_raw]
            steps_data.append(sd)
        return {
            "name": self.name,
            "description": self.description,
            "steps": steps_data,
            "state": self.state,
            "total_steps": len(self.steps),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Workflow":
        """从字典反序列化恢复工作流

        注意: condition Callable 无法被序列化，
        反序列化后条件分支中的 condition 将设为 None，
        需要调用方手动重新设置。
        """
        wf = cls(name=data.get("name", ""), description=data.get("description", ""))
        wf.state = data.get("state", {})
        for sd in data.get("steps", []):
            step = WorkflowStep(
                tool_name=sd["tool_name"],
                args=sd.get("args", {}),
                input_from_step=sd.get("input_from_step"),
                retry_count=sd.get("retry_count", 0),
                retry_delay=sd.get("retry_delay", 1.0),
                timeout=sd.get("timeout", 300.0),
                continue_on_error=sd.get("continue_on_error", False),
                parallel_group=sd.get("parallel_group"),
            )
            if sd.get("is_branch"):
                step.is_branch = True
                step.args["__true_steps__"] = [WorkflowStep(**ts) for ts in sd.get("branch_true_steps", [])]
                step.args["__false_steps__"] = [WorkflowStep(**fs) for fs in sd.get("branch_false_steps", [])]
            wf.add_step(step)
        return wf

    def __len__(self) -> int:
        return len(self.steps)

    def __repr__(self) -> str:
        return f"Workflow(name={self.name!r}, " f"steps={len(self.steps)}, " f"description={self.description!r})"


# ── 执行引擎 ──────────────────────────────────────────────────


class _StepTimeoutError(Exception):
    pass


def _run_with_timeout(func, args, kwargs, timeout_sec: float):
    """在线程中运行函数并施加超时限制"""
    result_container = [None]
    exception_container = [None]

    def target():
        try:
            result_container[0] = func(*args, **kwargs)
        except Exception as e:
            exception_container[0] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)
    if thread.is_alive():
        raise _StepTimeoutError(f"步骤执行超时 ({timeout_sec}s)")
    if exception_container[0] is not None:
        raise exception_container[0]
    return result_container[0]


async def _run_with_timeout_async(coro, timeout_sec: float):
    """异步协程超时包装"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_sec)
    except asyncio.TimeoutError:
        raise _StepTimeoutError(f"异步步骤执行超时 ({timeout_sec}s)")


class WorkflowEngine:
    """工作流执行引擎

    支持三种执行模式:
    1. 线性顺序执行 (_execute_linear): 步骤按添加顺序逐一执行
    2. 带条件分支执行 (_execute_with_branches): 遇到条件分支标记时动态选择路径
    3. 并发执行 (_execute_parallel): 对同一 parallel_group 的步骤并发调用

    特性:
    - 步骤间自动数据传递: 上一步 output.data 自动注入下一步 args 中的 $prev 引用
    - 重试机制: 失败后可配置重试次数和间隔
    - 超时保护: 每步独立超时控制
    - 错误策略: continue_on_error 允许跳过失败步骤继续执行
    - 详细日志: 记录每步耗时、输入摘要、输出状态
    """

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or get_registry()
        self.max_concurrency: int = 4
        self.default_timeout: float = 300.0
        self.execution_history: List[Dict] = []

    async def execute_async(self, workflow: Workflow, ctx: ToolContext) -> WorkflowResult:
        """异步执行工作流

        使用 asyncio 并发执行并行组内的步骤，
        对于不支持异步的工具会回退到线程池执行。

        Args:
            workflow: 待执行的工作流定义
            ctx:      共享执行上下文

        Returns:
            WorkflowResult 聚合结果
        """
        start_time = time.time()
        results: Dict[str, ToolResult] = {}
        execution_log: List[Dict] = []
        errors: List[ErrorInfo] = []
        last_output = None
        named_outputs: Dict[str, Any] = {}

        ctx.set("__workflow_name", workflow.name)
        ctx.set("__workflow_start_time", start_time)

        execution_log.append(
            {
                "event": "workflow_started",
                "workflow": workflow.name,
                "timestamp": time.time(),
                "total_steps": len(workflow.steps),
            }
        )

        has_parallel_groups = any(s.parallel_group for s in workflow.steps)
        has_branches = any(getattr(s, "is_branch", False) for s in workflow.steps)

        try:
            if has_branches:
                result = await self._async_execute_with_branches(
                    workflow,
                    ctx,
                    results,
                    execution_log,
                    errors,
                    named_outputs,
                )
                last_output = result
            elif has_parallel_groups:
                await self._async_execute_mixed(
                    workflow,
                    ctx,
                    results,
                    execution_log,
                    errors,
                    named_outputs,
                )
                last_output = self._extract_last_output(results)
            else:
                await self._async_execute_linear(
                    workflow,
                    ctx,
                    results,
                    execution_log,
                    errors,
                    named_outputs,
                )
                last_output = self._extract_last_output(results)
        except Exception as e:
            logger.exception(f"[WorkflowEngine] 工作流 '{workflow.name}' 异常终止")
            errors.append(
                ErrorInfo(
                    code="WORKFLOW_EXCEPTION",
                    message=f"工作流异常终止: {str(e)}",
                    severity="error",
                    details={"exception_type": type(e).__name__},
                )
            )

        total_ms = (time.time() - start_time) * 1000
        all_success = all(r.success for r in results.values()) if results else False

        wf_result = WorkflowResult(
            success=all_success and len(errors) == 0,
            results=results,
            final_output=last_output,
            execution_log=execution_log,
            total_time_ms=round(total_ms, 2),
            errors=errors,
        )

        self.execution_history.append(
            {
                "workflow": workflow.name,
                "success": wf_result.success,
                "total_time_ms": wf_result.total_time_ms,
                "step_count": len(results),
                "error_count": len(errors),
                "timestamp": time.time(),
            }
        )

        execution_log.append(
            {
                "event": "workflow_finished",
                "success": wf_result.success,
                "total_time_ms": round(total_ms, 2),
                "steps_completed": len(results),
                "errors": len(errors),
                "timestamp": time.time(),
            }
        )

        logger.info(
            f"[WorkflowEngine] 工作流 '{workflow.name}' 完成: "
            f"success={wf_result.success}, "
            f"steps={len(results)}, "
            f"time={total_ms:.0f}ms"
        )
        return wf_result

    def execute(self, workflow: Workflow, ctx: ToolContext) -> WorkflowResult:
        """同步执行工作流

        内部通过事件循环桥接异步实现。

        Args:
            workflow: 待执行的工作流定义
            ctx:      共享执行上下文

        Returns:
            WorkflowResult 聚合结果
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self.execute_async(workflow, ctx))
                    return future.result()
            else:
                return loop.run_until_complete(self.execute_async(workflow, ctx))
        except RuntimeError:
            return asyncio.run(self.execute_async(workflow, ctx))

    # ── 同步内部执行方法 ──────────────────────────────────

    def _execute_linear(
        self,
        workflow: Workflow,
        ctx: ToolContext,
    ) -> WorkflowResult:
        """线性顺序执行所有步骤"""
        start_time = time.time()
        results: Dict[str, ToolResult] = {}
        execution_log: List[Dict] = []
        errors: List[ErrorInfo] = []
        last_output = None
        named_outputs: Dict[str, Any] = {}

        for idx, step in enumerate(workflow.steps):
            step_key = getattr(step, "_internal_id", f"step_{idx}")
            step_result = self._execute_single_step(
                step,
                step_key,
                ctx,
                named_outputs,
                last_output,
                execution_log,
                errors,
            )
            results[step_key] = step_result
            last_output = step_result.data
            named_outputs[step_key] = step_result.data

            if not step_result.success and not step.continue_on_error:
                logger.warning(f"[WorkflowEngine] 步骤 '{step.tool_name}' 失败且未设置 continue_on_error，中止工作流")
                break

        total_ms = (time.time() - start_time) * 1000
        return WorkflowResult(
            success=all(r.success for r in results.values()) and len(errors) == 0,
            results=results,
            final_output=last_output,
            execution_log=execution_log,
            total_time_ms=round(total_ms, 2),
            errors=errors,
        )

    def _execute_with_branches(
        self,
        workflow: Workflow,
        ctx: ToolContext,
    ) -> WorkflowResult:
        """带条件分支的工作流执行"""
        start_time = time.time()
        results: Dict[str, ToolResult] = {}
        execution_log: List[Dict] = []
        errors: List[ErrorInfo] = []
        last_output = None
        named_outputs: Dict[str, Any] = {}

        flat_steps = self._flatten_workflow(workflow.steps)
        has_parallel = any(s.parallel_group for s in flat_steps)

        if has_parallel:
            parallel_groups = self._group_by_parallel(flat_steps)
            linear_steps = [s for s in flat_steps if s.parallel_group is None]
            for step in linear_steps:
                step_key = getattr(step, "_internal_id", f"step_{len(results)}")
                step_result = self._execute_single_step(
                    step,
                    step_key,
                    ctx,
                    named_outputs,
                    last_output,
                    execution_log,
                    errors,
                )
                results[step_key] = step_result
                last_output = step_result.data
                named_outputs[step_key] = step_result.data
                if not step_result.success and not step.continue_on_error:
                    break

            for group_name, group_steps in parallel_groups.items():
                group_results = self._execute_parallel(
                    group_steps, ctx, named_outputs, last_output, execution_log, errors
                )
                results.update(group_results)
                for sk, sr in group_results.items():
                    named_outputs[sk] = sr.data
                    last_output = sr.data
        else:
            for step in flat_steps:
                step_key = getattr(step, "_internal_id", f"step_{len(results)}")
                step_result = self._execute_single_step(
                    step,
                    step_key,
                    ctx,
                    named_outputs,
                    last_output,
                    execution_log,
                    errors,
                )
                results[step_key] = step_result
                last_output = step_result.data
                named_outputs[step_key] = step_result.data
                if not step_result.success and not step.continue_on_error:
                    break

        total_ms = (time.time() - start_time) * 1000
        return WorkflowResult(
            success=all(r.success for r in results.values()) and len(errors) == 0,
            results=results,
            final_output=last_output,
            execution_log=execution_log,
            total_time_ms=round(total_ms, 2),
            errors=errors,
        )

    def _execute_parallel(
        self,
        steps: List[WorkflowStep],
        ctx: ToolContext,
        named_outputs: Dict[str, Any],
        last_output: Any,
        execution_log: List[Dict],
        errors: List[ErrorInfo],
    ) -> Dict[str, ToolResult]:
        """同步并行执行一组步骤（基于线程池）"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: Dict[str, ToolResult] = {}
        max_workers = min(len(steps), self.max_concurrency)

        def _run_step(step: WorkflowStep) -> Tuple[str, ToolResult]:
            step_key = getattr(step, "_internal_id", f"parallel_{id(step)}")
            result = self._execute_single_step(
                step,
                step_key,
                ctx,
                named_outputs,
                last_output,
                execution_log,
                errors,
            )
            return step_key, result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_run_step, s): s for s in steps}
            for future in as_completed(futures):
                try:
                    step_key, step_result = future.result()
                    results[step_key] = step_result
                except Exception as e:
                    step = futures[future]
                    step_key = getattr(step, "_internal_id", f"parallel_err_{id(step)}")
                    err_result = ToolResult.error_result(
                        f"并行步骤异常: {str(e)}",
                        code="PARALLEL_STEP_ERROR",
                    )
                    results[step_key] = err_result
                    errors.append(
                        ErrorInfo(
                            code="PARALLEL_STEP_ERROR",
                            message=f"并行步骤 '{step.tool_name}' 异常: {str(e)}",
                            severity="error",
                        )
                    )

        return results

    # ── 异步内部执行方法 ──────────────────────────────────

    async def _async_execute_linear(
        self,
        workflow: Workflow,
        ctx: ToolContext,
        results: Dict[str, ToolResult],
        execution_log: List[Dict],
        errors: List[ErrorInfo],
        named_outputs: Dict[str, Any],
    ):
        """异步线性顺序执行"""
        last_output = None
        for idx, step in enumerate(workflow.steps):
            step_key = getattr(step, "_internal_id", f"step_{idx}")
            step_result = await self._async_execute_single_step(
                step,
                step_key,
                ctx,
                named_outputs,
                last_output,
                execution_log,
                errors,
            )
            results[step_key] = step_result
            last_output = step_result.data
            named_outputs[step_key] = step_result.data
            if not step_result.success and not step.continue_on_error:
                break

    async def _async_execute_with_branches(
        self,
        workflow: Workflow,
        ctx: ToolContext,
        results: Dict[str, ToolResult],
        execution_log: List[Dict],
        errors: List[ErrorInfo],
        named_outputs: Dict[str, Any],
    ) -> Any:
        """异步带条件分支执行"""
        flat_steps = self._flatten_workflow(workflow.steps)
        last_output = None
        has_parallel = any(s.parallel_group for s in flat_steps)

        if has_parallel:
            parallel_groups = self._group_by_parallel(flat_steps)
            linear_steps = [s for s in flat_steps if s.parallel_group is None]
            for step in linear_steps:
                step_key = getattr(step, "_internal_id", f"step_{len(results)}")
                step_result = await self._async_execute_single_step(
                    step,
                    step_key,
                    ctx,
                    named_outputs,
                    last_output,
                    execution_log,
                    errors,
                )
                results[step_key] = step_result
                last_output = step_result.data
                named_outputs[step_key] = step_result.data
                if not step_result.success and not step.continue_on_error:
                    break

            for group_name, group_steps in parallel_groups.items():
                group_results = await self._async_execute_parallel(
                    group_steps,
                    ctx,
                    named_outputs,
                    last_output,
                    execution_log,
                    errors,
                )
                results.update(group_results)
                for sk, sr in group_results.items():
                    named_outputs[sk] = sr.data
                    last_output = sr.data
        else:
            for step in flat_steps:
                step_key = getattr(step, "_internal_id", f"step_{len(results)}")
                step_result = await self._async_execute_single_step(
                    step,
                    step_key,
                    ctx,
                    named_outputs,
                    last_output,
                    execution_log,
                    errors,
                )
                results[step_key] = step_result
                last_output = step_result.data
                named_outputs[step_key] = step_result.data
                if not step_result.success and not step.continue_on_error:
                    break

        return last_output

    async def _async_execute_mixed(
        self,
        workflow: Workflow,
        ctx: ToolContext,
        results: Dict[str, ToolResult],
        execution_log: List[Dict],
        errors: List[ErrorInfo],
        named_outputs: Dict[str, Any],
    ):
        """异步混合执行（含并行组的线性流程）"""
        groups = self._group_by_parallel(workflow.steps)
        order_preserved = self._preserve_order_with_groups(workflow.steps)

        last_output = None
        for item in order_preserved:
            if item["type"] == "single":
                step = item["step"]
                step_key = getattr(step, "_internal_id", f"step_{len(results)}")
                step_result = await self._async_execute_single_step(
                    step,
                    step_key,
                    ctx,
                    named_outputs,
                    last_output,
                    execution_log,
                    errors,
                )
                results[step_key] = step_result
                last_output = step_result.data
                named_outputs[step_key] = step_result.data
                if not step_result.success and not step.continue_on_error:
                    break
            elif item["type"] == "group":
                group_steps = item["steps"]
                group_results = await self._async_execute_parallel(
                    group_steps,
                    ctx,
                    named_outputs,
                    last_output,
                    execution_log,
                    errors,
                )
                results.update(group_results)
                for sk, sr in group_results.items():
                    named_outputs[sk] = sr.data
                    last_output = sr.data

    async def _async_execute_parallel(
        self,
        steps: List[WorkflowStep],
        ctx: ToolContext,
        named_outputs: Dict[str, Any],
        last_output: Any,
        execution_log: List[Dict],
        errors: List[ErrorInfo],
    ) -> Dict[str, ToolResult]:
        """异步并发执行一组步骤"""
        semaphore = asyncio.Semaphore(self.max_concurrency)
        results: Dict[str, ToolResult] = {}

        async def _bounded_run(step: WorkflowStep) -> Tuple[str, ToolResult]:
            async with semaphore:
                step_key = getattr(step, "_internal_id", f"async_parallel_{id(step)}")
                result = await self._async_execute_single_step(
                    step,
                    step_key,
                    ctx,
                    named_outputs,
                    last_output,
                    execution_log,
                    errors,
                )
                return step_key, result

        tasks = [_bounded_run(s) for s in steps]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for i, outcome in enumerate(completed):
            step = steps[i]
            step_key = getattr(step, "_internal_id", f"async_parallel_{id(step)}")
            if isinstance(outcome, Exception):
                err_result = ToolResult.error_result(
                    f"异步并行步骤异常: {str(outcome)}",
                    code="ASYNC_PARALLEL_ERROR",
                )
                results[step_key] = err_result
                errors.append(
                    ErrorInfo(
                        code="ASYNC_PARALLEL_ERROR",
                        message=f"异步并行步骤 '{step.tool_name}' 异常: {str(outcome)}",
                        severity="error",
                    )
                )
            else:
                sk, sr = outcome
                results[sk] = sr

        return results

    # ── 单步执行核心 ──────────────────────────────────────

    def _execute_single_step(
        self,
        step: WorkflowStep,
        step_key: str,
        ctx: ToolContext,
        named_outputs: Dict[str, Any],
        last_output: Any,
        execution_log: List[Dict],
        errors: List[ErrorInfo],
    ) -> ToolResult:
        """执行单个工作流步骤（同步版本）"""
        step_start = time.time()

        log_entry = {
            "step_key": step_key,
            "tool_name": step.tool_name,
            "status": "running",
            "start_time": step_start,
        }
        execution_log.append(log_entry)

        if step.condition is not None:
            try:
                should_run = step.condition(dict(ctx.state))
            except Exception as e:
                logger.warning(f"[WorkflowEngine] 条件评估异常: {e}")
                should_run = False
            if not should_run:
                log_entry.update(
                    {
                        "status": "skipped",
                        "reason": "condition_evaluated_false",
                        "end_time": time.time(),
                        "elapsed_ms": round((time.time() - step_start) * 1000, 2),
                    }
                )
                skipped_result = ToolResult.success_result(
                    data=None,
                    skipped=True,
                    reason="condition_evaluated_false",
                )
                return skipped_result

        tool_class = self.registry.get(step.tool_name)
        if tool_class is None:
            err_msg = f"工具 '{step.tool_name}' 未在注册表中找到"
            logger.error(f"[WorkflowEngine] {err_msg}")
            errors.append(ErrorInfo(code="TOOL_NOT_FOUND", message=err_msg))
            log_entry.update(
                {
                    "status": "error",
                    "error": err_msg,
                    "end_time": time.time(),
                    "elapsed_ms": round((time.time() - step_start) * 1000, 2),
                }
            )
            return ToolResult.error_result(err_msg, code="TOOL_NOT_FOUND")

        resolved_args = self._resolve_args(step, named_outputs, last_output)

        timeout = step.timeout if step.timeout > 0 else self.default_timeout
        attempt = 0
        last_error = None
        result = None

        while attempt <= step.retry_count:
            attempt += 1
            try:
                tool_instance = tool_class()

                if timeout > 0 and timeout < float("inf"):
                    result = _run_with_timeout(
                        tool_instance.run_safe,
                        (ctx,),
                        resolved_args,
                        timeout,
                    )
                else:
                    result = tool_instance.run_safe(ctx, **resolved_args)

                result.metadata.setdefault("attempt", attempt)
                result.metadata.setdefault("step_key", step_key)
                break
            except _StepTimeoutError as e:
                last_error = e
                logger.warning(f"[WorkflowEngine] 步骤 '{step.tool_name}' 第 {attempt} 次尝试超时")
                if attempt <= step.retry_count:
                    time.sleep(step.retry_delay)
            except Exception as e:
                last_error = e
                logger.warning(f"[WorkflowEngine] 步骤 '{step.tool_name}' 第 {attempt} 次尝试异常: {e}")
                if attempt <= step.retry_count:
                    time.sleep(step.retry_delay)

        if result is None:
            err_msg = f"步骤 '{step.tool_name}' 执行失败 (已重试 {step.retry_count} 次): {last_error}"
            errors.append(
                ErrorInfo(
                    code="STEP_EXECUTION_FAILED",
                    message=err_msg,
                    severity="error",
                    details={"tool_name": step.tool_name, "attempts": attempt},
                )
            )
            log_entry.update(
                {
                    "status": "error",
                    "error": str(last_error),
                    "attempts": attempt,
                    "end_time": time.time(),
                    "elapsed_ms": round((time.time() - step_start) * 1000, 2),
                }
            )
            return ToolResult.error_result(err_msg, code="STEP_EXECUTION_FAILED")

        elapsed_ms = (time.time() - step_start) * 1000
        log_entry.update(
            {
                "status": "success" if result.success else "failed",
                "success": result.success,
                "attempts": attempt,
                "elapsed_ms": round(elapsed_ms, 2),
                "end_time": time.time(),
                "output_keys": (
                    list(result.data.keys()) if isinstance(result.data, dict) else type(result.data).__name__
                ),
            }
        )

        if not result.success:
            for err in result.errors:
                errors.append(err)

        logger.debug(
            f"[WorkflowEngine] 步骤 [{step_key}] '{step.tool_name}' "
            f"{'成功' if result.success else '失败'} "
            f"({elapsed_ms:.0f}ms, 尝试{attempt}次)"
        )

        return result

    async def _async_execute_single_step(
        self,
        step: WorkflowStep,
        step_key: str,
        ctx: ToolContext,
        named_outputs: Dict[str, Any],
        last_output: Any,
        execution_log: List[Dict],
        errors: List[ErrorInfo],
    ) -> ToolResult:
        """执行单个工作流步骤（异步版本）"""
        step_start = time.time()

        log_entry = {
            "step_key": step_key,
            "tool_name": step.tool_name,
            "status": "running",
            "start_time": step_start,
        }
        execution_log.append(log_entry)

        if step.condition is not None:
            try:
                should_run = step.condition(dict(ctx.state))
            except Exception as e:
                logger.warning(f"[WorkflowEngine] 条件评估异常: {e}")
                should_run = False
            if not should_run:
                log_entry.update(
                    {
                        "status": "skipped",
                        "reason": "condition_evaluated_false",
                        "end_time": time.time(),
                        "elapsed_ms": round((time.time() - step_start) * 1000, 2),
                    }
                )
                return ToolResult.success_result(
                    data=None,
                    skipped=True,
                    reason="condition_evaluated_false",
                )

        tool_class = self.registry.get(step.tool_name)
        if tool_class is None:
            err_msg = f"工具 '{step.tool_name}' 未在注册表中找到"
            errors.append(ErrorInfo(code="TOOL_NOT_FOUND", message=err_msg))
            log_entry.update(
                {
                    "status": "error",
                    "error": err_msg,
                    "end_time": time.time(),
                    "elapsed_ms": round((time.time() - step_start) * 1000, 2),
                }
            )
            return ToolResult.error_result(err_msg, code="TOOL_NOT_FOUND")

        resolved_args = self._resolve_args(step, named_outputs, last_output)
        timeout = step.timeout if step.timeout > 0 else self.default_timeout
        attempt = 0
        last_error = None
        result = None

        while attempt <= step.retry_count:
            attempt += 1
            try:
                tool_instance = tool_class()
                if hasattr(tool_instance, "execute_async"):
                    coro = tool_instance.execute_async(ctx, **resolved_args)
                    if timeout > 0 and timeout < float("inf"):
                        result = await _run_with_timeout_async(coro, timeout)
                    else:
                        result = await coro
                else:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        lambda: _run_with_timeout(
                            tool_instance.run_safe,
                            (ctx,),
                            resolved_args,
                            timeout,
                        ),
                    )
                result.metadata.setdefault("attempt", attempt)
                result.metadata.setdefault("step_key", step_key)
                break
            except _StepTimeoutError as e:
                last_error = e
                if attempt <= step.retry_count:
                    await asyncio.sleep(step.retry_delay)
            except Exception as e:
                last_error = e
                if attempt <= step.retry_count:
                    await asyncio.sleep(step.retry_delay)

        if result is None:
            err_msg = f"步骤 '{step.tool_name}' 执行失败: {last_error}"
            errors.append(
                ErrorInfo(
                    code="STEP_EXECUTION_FAILED",
                    message=err_msg,
                    severity="error",
                )
            )
            log_entry.update(
                {
                    "status": "error",
                    "error": str(last_error),
                    "attempts": attempt,
                    "end_time": time.time(),
                    "elapsed_ms": round((time.time() - step_start) * 1000, 2),
                }
            )
            return ToolResult.error_result(err_msg, code="STEP_EXECUTION_FAILED")

        elapsed_ms = (time.time() - step_start) * 1000
        log_entry.update(
            {
                "status": "success" if result.success else "failed",
                "success": result.success,
                "attempts": attempt,
                "elapsed_ms": round(elapsed_ms, 2),
                "end_time": time.time(),
            }
        )

        if not result.success:
            errors.extend(result.errors)

        return result

    # ── 参数解析与辅助方法 ────────────────────────────────

    def _resolve_args(
        self,
        step: WorkflowStep,
        named_outputs: Dict[str, Any],
        last_output: Any,
    ) -> Dict:
        """解析步骤参数，处理 $prev 和 $step_xxx 引用

        支持的引用语法:
        - $prev:           上一步的完整输出 (ToolResult.data)
        - $prev.data.key:  上一步输出中 data 的嵌套字段
        - $step_3:         命名为 step_3 的步骤输出
        - $step_3.data.X:  命名步骤输出的嵌套字段
        """
        resolved = dict(step.args)

        if step.input_from_step and step.input_from_step in named_outputs:
            source_output = named_outputs[step.input_from_step]
        else:
            source_output = last_output

        def _resolve_value(val):
            if isinstance(val, str):
                if val == "$prev":
                    return source_output
                if val.startswith("$prev."):
                    path = val[6:]
                    return self._get_nested(source_output, path)
                if val.startswith("$") and "." in val:
                    ref_name = val.split(".")[0]
                    ref_path = val[len(ref_name) + 1 :]
                    if ref_name in named_outputs:
                        return self._get_nested(named_outputs[ref_name], ref_path)
                    if ref_name == "$prev":
                        return self._get_nested(source_output, ref_path)
                if val.startswith("$") and val not in ("$prev",):
                    ref_name = val[1:]
                    if ref_name in named_outputs:
                        return named_outputs[ref_name]
                return val
            elif isinstance(val, dict):
                return {k: _resolve_value(v) for k, v in val.items()}
            elif isinstance(val, (list, tuple)):
                return type(val)(_resolve_value(v) for v in val)
            return val

        return {k: _resolve_value(v) for k, v in resolved.items()}

    @staticmethod
    def _get_nested(obj: Any, path: str) -> Any:
        """按点号路径从对象中提取嵌套值"""
        if obj is None:
            return None
        parts = path.split(".")
        current = obj
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    @staticmethod
    def _flatten_workflow(steps: List[WorkflowStep]) -> List[WorkflowStep]:
        """展开工作流步骤列表，将条件分支标记替换为实际选择的步骤"""
        flattened = []
        for step in steps:
            if getattr(step, "is_branch", False):
                cond_fn = step.args.get("__condition_ref__")
                if cond_fn is not None:
                    try:
                        use_true = cond_fn({})
                    except Exception:
                        use_true = True
                else:
                    use_true = True
                chosen = step.args.get("__true_steps__", []) if use_true else step.args.get("__false_steps__", [])
                for cs in chosen:
                    cs_copy = copy.deepcopy(cs)
                    flattened.append(cs_copy)
            else:
                flattened.append(step)
        return flattened

    @staticmethod
    def _group_by_parallel(steps: List[WorkflowStep]) -> Dict[str, List[WorkflowStep]]:
        """按 parallel_group 分组"""
        groups: Dict[str, List[WorkflowStep]] = {}
        for step in steps:
            if step.parallel_group:
                groups.setdefault(step.parallel_group, []).append(step)
        return groups

    @staticmethod
    def _preserve_order_with_groups(steps: List[WorkflowStep]) -> List[Dict]:
        """保持步骤原始顺序，将连续的并行步骤合并为组"""
        result = []
        current_group = None
        for step in steps:
            if step.parallel_group:
                if current_group is None or current_group["group_name"] != step.parallel_group:
                    if current_group is not None:
                        result.append(current_group)
                    current_group = {
                        "type": "group",
                        "group_name": step.parallel_group,
                        "steps": [step],
                    }
                else:
                    current_group["steps"].append(step)
            else:
                if current_group is not None:
                    result.append(current_group)
                    current_group = None
                result.append({"type": "single", "step": step})
        if current_group is not None:
            result.append(current_group)
        return result

    @staticmethod
    def _extract_last_output(results: Dict[str, ToolResult]) -> Any:
        """从结果字典中提取最后一步的输出"""
        if not results:
            return None
        last_key = list(results.keys())[-1]
        return results[last_key].data


# ── 内置工作流模板 ────────────────────────────────────────────


class BuiltInWorkflows:
    """预置工作流模板工厂

    提供常用场景的开箱即用工作流模板，
    可直接使用也可作为自定义工作流的起点。

    所有模板返回 Workflow 对象，可通过修改其 steps 属性进行定制。
    """

    @staticmethod
    def daily_analysis() -> Workflow:
        """每日分析流程

        流水线: 数据加载 → 特征工程 → 预测 → 权重分析 → 优化建议 → 报告汇总

        适用场景: 日常例行分析任务
        """
        wf = Workflow(
            name="daily_analysis",
            description="每日分析流程: 数据加载→特征→预测→权重分析→优化建议→报告",
        )
        wf.add_step(
            WorkflowStep(
                tool_name="data_loader",
                args={"path_or_data": "$config.data_path"},
                continue_on_error=False,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="feature_engineer",
                args={"raw_data": "$prev.data"},
                input_from_step=None,
                continue_on_error=False,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="predictor",
                args={"features": "$prev.data.X"},
                continue_on_error=False,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="weight_analyzer",
                args={},
                continue_on_error=True,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="optimization_advisor",
                args={"performance_data": "$prev.data"},
                continue_on_error=True,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="model_analyzer",
                args={"load_model": False},
                continue_on_error=True,
            )
        )
        return wf

    @staticmethod
    def model_training() -> Workflow:
        """模型训练流程

        流水线: 数据加载 → 特征工程 → 特征选择 → 模型诊断(加载/训练) → 保存验证

        适用场景: 模型重新训练与更新
        """
        wf = Workflow(
            name="model_training",
            description="模型训练流程: 数据→特征→选择→训练→评估→保存→验证",
        )
        wf.add_step(
            WorkflowStep(
                tool_name="data_loader",
                args={"path_or_data": "$config.training_data_path"},
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="feature_engineer",
                args={
                    "raw_data": "$prev.data",
                    "enable_selection": True,
                    "select_top": 80,
                },
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="feature_selector",
                args={
                    "X": "$prev.data.featured_dataframe",
                    "y": "$config.target_column",
                    "n_features": 60,
                },
                continue_on_error=True,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="model_analyzer",
                args={"load_model": True},
                retry_count=2,
                retry_delay=2.0,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="history_evaluator",
                args={
                    "predictions_history": "$config.recent_predictions",
                    "actual_results": "$config.recent_actuals",
                },
                continue_on_error=True,
                condition=lambda state: state.get("has_evaluation_data", False),
            )
        )
        return wf

    @staticmethod
    def evaluation() -> Workflow:
        """评估流程

        流水线: 历史数据加载 → 模型诊断 → 历史评估 → 权重分析 → 优化建议 → 评估报告

        适用场景: 定期模型效果评估
        """
        wf = Workflow(
            name="evaluation",
            description="评估流程: 历史→诊断→评估→权重分析→建议→报告",
        )
        wf.add_step(
            WorkflowStep(
                tool_name="model_analyzer",
                args={"load_model": True},
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="weight_analyzer",
                args={},
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="history_evaluator",
                args={
                    "predictions_history": "$config.predictions_history",
                    "actual_results": "$config.actual_results",
                },
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="optimization_advisor",
                args={},
            )
        )
        return wf

    @staticmethod
    def full_pipeline() -> Workflow:
        """完整自动化流水线

        包含全部阶段: 数据准备 → 特征处理 → 预测 → 评估 → 分析 → 建议 → 报告

        适用场景: 一键全流程自动化
        """
        wf = Workflow(
            name="full_pipeline",
            description="完整自动化流水线: 数据→特征→预测→评估→分析→建议→报告",
        )
        wf.add_step(
            WorkflowStep(
                tool_name="data_loader",
                args={"path_or_data": "$config.data_path"},
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="validation",
                args={
                    "data": "$prev.data",
                    "required_columns": ["period"],
                    "strict": False,
                },
                continue_on_error=True,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="feature_engineer",
                args={
                    "raw_data": "$prev.data",
                    "enable_selection": True,
                    "select_top": 100,
                },
            )
        )
        wf.add_parallel(
            WorkflowStep(
                tool_name="model_analyzer",
                args={"load_model": True},
                parallel_group=None,
            ),
            WorkflowStep(
                tool_name="weight_analyzer",
                args={},
                parallel_group=None,
            ),
        )
        wf.add_step(
            WorkflowStep(
                tool_name="predictor",
                args={"features": "$prev.data.X"},
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="optimization_advisor",
                args={},
                continue_on_error=True,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="logger",
                args={
                    "message": "完整流水线执行完成",
                    "level": "info",
                    "extra": {"workflow": "full_pipeline"},
                },
                continue_on_error=True,
            )
        )
        return wf

    @staticmethod
    def quick_predict() -> Workflow:
        """快速预测流程

        最精简路径: 加载模型 → 直接预测

        适用场景: 低延迟实时预测请求
        """
        wf = Workflow(
            name="quick_predict",
            description="快速预测流程: 模型加载→预测",
        )
        wf.add_step(
            WorkflowStep(
                tool_name="model_analyzer",
                args={"load_model": True},
                timeout=120.0,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="predictor",
                args={"features": "$input.features"},
                timeout=60.0,
            )
        )
        return wf

    @staticmethod
    def batch_prediction() -> Workflow:
        """批量预测流程

        流水线: 数据加载 → 特征工程 → 批量预测 → 结果汇总

        适用场景: 多期批量预测
        """
        wf = Workflow(
            name="batch_prediction",
            description="批量预测流程: 数据加载→特征→批量预测→汇总",
        )
        wf.add_step(
            WorkflowStep(
                tool_name="data_loader",
                args={"path_or_data": "$config.batch_data_path"},
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="feature_engineer",
                args={"raw_data": "$prev.data"},
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="batch_predictor",
                args={
                    "features_list": "$prev.data.X",
                    "top_k": "$config.top_k",
                },
                timeout=600.0,
            )
        )
        wf.add_step(
            WorkflowStep(
                tool_name="optimization_advisor",
                args={},
                continue_on_error=True,
            )
        )
        return wf

    @staticmethod
    def diagnostic_check() -> Workflow:
        """诊断检查流程

        并行执行多项诊断: 模型健康 + 权重状态 + 缓存统计

        适用场景: 系统健康巡检
        """
        wf = Workflow(
            name="diagnostic_check",
            description="诊断检查流程: 并行执行模型/权重/缓存诊断",
        )
        wf.add_parallel(
            WorkflowStep(tool_name="model_analyzer", args={"load_model": True}),
            WorkflowStep(tool_name="weight_analyzer", args={}),
            WorkflowStep(tool_name="cache", args={"operation": "stats"}),
        )
        wf.add_step(
            WorkflowStep(
                tool_name="logger",
                args={
                    "message": "诊断检查完成",
                    "level": "info",
                    "extra": {"workflow": "diagnostic_check"},
                },
            )
        )
        return wf

    @staticmethod
    def list_templates() -> Dict[str, Workflow]:
        """列出所有可用模板

        Returns:
            {模板名称: Workflow实例} 字典
        """
        templates = {}
        method_names = [
            "daily_analysis",
            "model_training",
            "evaluation",
            "full_pipeline",
            "quick_predict",
            "batch_prediction",
            "diagnostic_check",
        ]
        for name in method_names:
            method = getattr(BuiltInWorkflows, name, None)
            if callable(method):
                templates[name] = method()
        return templates

    @staticmethod
    def get_template(name: str) -> Optional[Workflow]:
        """按名称获取单个模板

        Args:
            name: 模板名称

        Returns:
            Workflow 实例，不存在则返回 None
        """
        method = getattr(BuiltInWorkflows, name, None)
        if callable(method):
            return method()
        available = list(BuiltInWorkflows.list_templates().keys())
        logger.warning(f"[BuiltInWorkflows] 未找到模板 '{name}'，" f"可用模板: {available}")
        return None
