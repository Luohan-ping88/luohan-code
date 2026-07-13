"""
PL5 工具系统 - 全面验证脚本 (V10.0)
"""

import sys
import time
import traceback
import asyncio

SEPARATOR = "=" * 70
print(SEPARATOR)
print("  PL5 工具系统 - 全面验证报告 (V10.0)")
print(f"  Python: {sys.version.split()[0]}")
print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(SEPARATOR)
print()

results = {"pass": 0, "fail": 0, "warn": 0}
errors_log = []


def check(name, condition, detail=""):
    if condition:
        results["pass"] += 1
        print(f"  [PASS] {name}")
        if detail:
            print(f"         {detail}")
    else:
        results["fail"] += 1
        print(f"  [FAIL] {name}")
        if detail:
            print(f"         {detail}")


def warn(name, detail=""):
    results["warn"] += 1
    print(f"  [WARN] {name}")
    if detail:
        print(f"         {detail}")


# ── 1. 模块导入验证 ────────────────────────────────
print("▶ 阶段 1: 模块导入验证")
print("-" * 50)

try:
    from src.tools.base import (
        ToolLayer, ErrorInfo, ToolResult, ToolContext,
        BaseTool, ToolRegistry, register_tool, get_registry, reset_registry,
    )
    check("base 模块导入", True)
except Exception as e:
    check("base 模块导入", False, str(e))
    errors_log.append(("base import", str(e)))

try:
    from src.tools.infrastructure import (
        DataLoaderTool, CacheTool, ConfigTool, LoggerTool, ValidationTool,
    )
    check("infrastructure 模块导入", True, f"包含 5 个工具类")
except Exception as e:
    check("infrastructure 模块导入", False, str(e))
    errors_log.append(("infra import", str(e)))

try:
    from src.tools.core_tools import (
        PredictorTool, BatchPredictorTool, FeatureEngineerTool,
        FeatureSelectorTool, ModelAnalyzerTool, WeightAnalyzerTool,
        HistoryEvaluatorTool, OptimizationAdvisorTool,
    )
    check("core_tools 模块导入", True, f"包含 8 个工具类")
except Exception as e:
    check("core_tools 模块导入", False, str(e))
    errors_log.append(("core import", str(e)))

try:
    from src.tools.application_tools import (
        DailyReportTool, QuickPredictTool, BacktestTool,
        ComparisonTool, AlertTool, ExportTool,
    )
    check("application_tools 模块导入", True, f"包含 6 个工具类")
except Exception as e:
    check("application_tools 模块导入", False, str(e))
    errors_log.append(("app import", str(e)))

try:
    from src.tools.orchestrator import (
        WorkflowStep, Workflow, WorkflowResult,
        WorkflowEngine, BuiltInWorkflows,
    )
    check("orchestrator 模块导入", True, "含引擎 + 7模板")
except Exception as e:
    check("orchestrator 模块导入", False, str(e))
    errors_log.append(("orchestrator import", str(e)))

try:
    from src.tools.async_support import (
        AsyncToolMixin, AsyncPredictorMixin,
        ConcurrencyManager, AsyncBatchExecutor,
        BatchExecutionConfig, BatchStopError,
        create_default_concurrency_manager, create_batch_executor,
    )
    check("async_support 模块导入", True, f"含 8 个导出项")
except Exception as e:
    check("async_support 模块导入", False, str(e))
    errors_log.append(("async_support import", str(e)))

try:
    from src.tools.api_layer import (
        get_api_status, LightweightAPIRouter,
        ToolRequest, ToolResponse, BatchRequest, WorkflowRequest,
    )
    status = get_api_status()
    mode_str = "full" if status["full_api_ready"] else "lightweight"
    check("api_layer 模块导入", True,
          f"mode={mode_str}, fastapi={status['fastapi_available']}")
except Exception as e:
    check("api_layer 模块导入", False, str(e))
    errors_log.append(("api_layer import", str(e)))

try:
    from src.tools import __version__
    check("__init__.py 版本导出", True, f"version={__version__}")
except Exception as e:
    check("__init__.py 版本导出", False, str(e))

print()

# ── 2. ToolRegistry 注册验证 ─────────────────────────
print("▶ 阶段 2: ToolRegistry 注册验证")
print("-" * 50)

registry = get_registry()
all_tools = registry.list_all()
check("注册表非空", len(all_tools) > 0, f"共 {len(all_tools)} 个工具")

expected_min = 19
check(f"工具数量 >= {expected_min}", len(all_tools) >= expected_min,
      f"实际: {len(all_tools)} 个")

infra_tools = registry.list_by_layer(ToolLayer.INFRASTRUCTURE)
check(f"基础设施层工具", len(infra_tools) >= 4,
      f"{len(infra_tools)} 个: {list(infra_tools.keys())}")

core_tools_reg = registry.list_by_layer(ToolLayer.CORE)
check(f"核心层工具", len(core_tools_reg) >= 7,
      f"{len(core_tools_reg)} 个: {list(core_tools_reg.keys())}")

app_tools = registry.list_by_layer(ToolLayer.APPLICATION)
check(f"应用层工具", len(app_tools) >= 5,
      f"{len(app_tools)} 个: {list(app_tools.keys())}")

all_names = sorted(all_tools.keys())
check("完整工具列表", True, ", ".join(all_names))

print()

# ── 3. 实例化验证 ─────────────────────────────────
print("▶ 阶段 3: 工具实例化验证")
print("-" * 50)

tool_classes_to_test = [
    ("DataLoaderTool", DataLoaderTool),
    ("CacheTool", CacheTool),
    ("ConfigTool", ConfigTool),
    ("LoggerTool", LoggerTool),
    ("ValidationTool", ValidationTool),
    ("PredictorTool", PredictorTool),
    ("BatchPredictorTool", BatchPredictorTool),
    ("FeatureEngineerTool", FeatureEngineerTool),
    ("FeatureSelectorTool", FeatureSelectorTool),
    ("ModelAnalyzerTool", ModelAnalyzerTool),
    ("WeightAnalyzerTool", WeightAnalyzerTool),
    ("HistoryEvaluatorTool", HistoryEvaluatorTool),
    ("OptimizationAdvisorTool", OptimizationAdvisorTool),
    ("DailyReportTool", DailyReportTool),
    ("QuickPredictTool", QuickPredictTool),
    ("BacktestTool", BacktestTool),
    ("ComparisonTool", ComparisonTool),
    ("AlertTool", AlertTool),
    ("ExportTool", ExportTool),
]

for name, cls in tool_classes_to_test:
    try:
        instance = cls()
        has_name = bool(getattr(instance, "name", None))
        has_execute = callable(getattr(instance, "execute", None))
        has_run_safe = callable(getattr(instance, "run_safe", None))
        has_get_info = callable(getattr(instance, "get_info", None))

        ok = has_name and has_execute and has_run_safe and has_get_info
        check(f"实例化 {name}", ok,
              f"name={instance.name!r}, execute={has_execute}, run_safe={has_run_safe}")
    except Exception as e:
        check(f"实例化 {name}", False, str(e))
        errors_log.append((f"instantiate {name}", str(e)))

print()

# ── 4. 基础组件功能验证 ────────────────────────────
print("▶ 阶段 4: 基础组件功能验证")
print("-" * 50)

ctx = ToolContext(metrics={})
check("ToolContext 创建", ctx is not None)
ctx.set("test_key", "test_value")
check("ToolContext.set/get", ctx.get("test_key") == "test_value")
ctx.record_metric("metric_test", 42)
check("ToolContext.record_metric", ctx.metrics.get("metric_test") == 42)

result_success = ToolResult.success_result(data={"x": 1}, test_meta="ok")
check("ToolResult.success_result", result_success.success is True)
check("ToolResult.to_dict 序列化", isinstance(result_success.to_dict(), dict))

result_error = ToolResult.error_result("test error", code="TEST_CODE")
check("ToolResult.error_result", result_error.success is False)
check("ToolResult.error 追加", len(result_error.errors) > 0)

child_ctx = ctx.create_child()
check("ToolContext.create_child", child_ctx.get("test_key") == "test_value")

info = ErrorInfo(code="TEST", message="test msg")
check("ErrorInfo.to_dict", info.to_dict()["code"] == "TEST")

print()

# ── 5. 异步支持组件验证 ────────────────────────────
print("▶ 阶段 5: 异步与并发支持验证")
print("-" * 50)


async def _test_async_components():
    checks_done = []

    cm = ConcurrencyManager(max_workers=4)
    stats = cm.get_stats()
    checks_done.append((
        "ConcurrencyManager 创建",
        stats["max_workers"] == 4 and stats["initialized"] is False,
        f"max_workers={stats['max_workers']}"
    ))

    await cm.acquire(priority=1)
    checks_done.append(("ConcurrencyManager.acquire", True))
    await cm.release()
    checks_done.append(("ConcurrencyManager.release", True))

    async def dummy_coro():
        await asyncio.sleep(0.01)
        return "done"

    result = await cm.run_with_limit(dummy_coro(), priority=2)
    checks_done.append(("ConcurrencyManager.run_with_limit", result == "done"))

    stats_after = cm.get_stats()
    checks_done.append((
        "ConcurrencyManager.get_stats",
        stats_after["total_submitted"] == 1 and stats_after["completed"] == 1,
        f"submitted={stats_after['total_submitted']}, completed={stats_after['completed']}"
    ))

    batch_cfg = BatchExecutionConfig(max_concurrency=2, timeout_per_tool=5.0)
    executor = AsyncBatchExecutor(concurrency_manager=cm, config=batch_cfg)
    checks_done.append(("AsyncBatchExecutor 创建", executor is not None))

    factory_cm = create_default_concurrency_manager(max_workers=8)
    checks_done.append(("create_default_concurrency_manager", factory_cm.max_workers == 8))

    factory_exec = create_batch_executor(max_concurrency=6)
    checks_done.append(("create_batch_executor", factory_exec.config.max_concurrency == 6))

    return checks_done


async_checks = asyncio.run(_test_async_components())
for item in async_checks:
    if len(item) == 3:
        name, ok, detail = item
    else:
        name, ok = item
        detail = ""
    check(name, ok, detail or "")


class DummyAsyncTool(AsyncToolMixin, BaseTool):
    name = "dummy_async"
    description = "dummy async tool for testing"

    async def execute_async_core(self, ctx, **kwargs):
        await asyncio.sleep(0.01)
        return ToolResult.success_result(data={"async": True})

    def execute(self, ctx, **kwargs):
        return ToolResult.success_result(data={"sync": True})


try:
    dummy = DummyAsyncTool()
    check("AsyncToolMixin 继承", hasattr(dummy, "execute_async_core"))
    check("AsyncToolMixin.execute_async_core 可调用", callable(dummy.execute_async_core))

    result_async = asyncio.run(dummy.execute_async_core(ctx))
    check("AsyncToolMixin 执行结果", result_async.success, f"data={result_async.data}")
except Exception as e:
    check("AsyncToolMixin 测试", False, str(e))
    errors_log.append(("AsyncToolMixin test", str(e)))

print()

# ── 6. 编排引擎验证 ────────────────────────────────
print("▶ 阶段 6: 编排引擎验证")
print("-" * 50)

templates = BuiltInWorkflows.list_templates()
check("BuiltInWorkflows 模板数", len(templates) == 7,
      f"实际 {len(templates)} 个: {list(templates.keys())}")

template_names = ["daily_analysis", "model_training", "evaluation",
                   "full_pipeline", "quick_predict", "batch_prediction", "diagnostic_check"]
for tname in template_names:
    wf = BuiltInWorkflows.get_template(tname)
    check(f"模板 {tname}", wf is not None, f"steps={len(wf.steps)}, desc={wf.description[:40]}")

step = WorkflowStep(tool_name="logger", args={"message": "test"})
check("WorkflowStep 创建", step.tool_name == "logger")

wf = Workflow("test_wf", "test workflow")
wf.add_step(step)
check("Workflow 创建与 add_step", len(wf.steps) == 1)
wf_dict = wf.to_dict()
check("Workflow.to_dict", "steps" in wf_dict and len(wf_dict["steps"]) == 1)

engine = WorkflowEngine(registry=registry)
check("WorkflowEngine 创建", engine is not None)
check("WorkflowEngine.max_concurrency", engine.max_concurrency == 4)

wr = WorkflowResult(success=True, results={}, total_time_ms=100.5)
check("WorkflowResult 创建", wr.success and wr.step_count == 0)
check("WorkflowResult.to_dict", isinstance(wr.to_dict(), dict))

print()

# ── 7. API 层验证 ──────────────────────────────────
print("▶ 阶段 7: API 层验证")
print("-" * 50)

api_status = get_api_status()
check("API 状态获取", api_status is not None)
check("API fastapi 检测", "fastapi_available" in api_status)
check("API pydantic 检测", "pydantic_available" in api_status)

router = LightweightAPIRouter()
routes = router.list_routes()
check("LightweightAPIRouter 路由", len(routes) > 0, f"{len(routes)} 条路由")

health_resp = router.handle_request("/health", "GET")
check("LightweightAPI /health", health_resp.get("status") == "ok")

tools_resp = router.handle_request("/tools", "GET")
check("LightweightAPI /tools", "count" in tools_resp)

req = ToolRequest(kwargs={"message": "hello"})
check("ToolRequest 创建", req.kwargs == {"message": "hello"})

resp = ToolResponse(success=True, data={"key": "val"})
check("ToolResponse 创建", resp.success and resp.data == {"key": "val"})
resp_dict = resp.to_dict()
check("ToolResponse.to_dict", "elapsed_ms" in resp_dict)

br = BatchRequest(calls=[{"tool_name": "logger"}])
check("BatchRequest 创建", len(br.calls) == 1)

wfr = WorkflowRequest(template_name="quick_predict")
check("WorkflowRequest 创建", wfr.template_name == "quick_predict")

if api_status["fastapi_available"]:
    warn("FastAPI 完整模式可用", "可使用 create_fastapi_app() 和 run_api_server()")
else:
    hint = api_status.get("install_hint", "N/A")
    warn("FastAPI 不可用，使用轻量级模式", f"安装提示: {hint}")

print()

# ── 8. 端到端快速预测模板测试 ─────────────────────
print("▶ 阶段 8: 端到端工作流测试（quick_predict 模板）")
print("-" * 50)

try:
    quick_wf = BuiltInWorkflows.quick_predict()
    check("quick_predict 模板加载", quick_wf is not None)
    step_names = [s.tool_name for s in quick_wf.steps]
    check("quick_predict 步骤数", len(quick_wf.steps) == 2, f"步骤: {step_names}")

    steps_info = []
    for s in quick_wf.steps:
        sd = s.to_dict()
        steps_info.append(sd)
    check("quick_predict 步骤序列化", all("tool_name" in si for si in steps_info))

    diag_wf = BuiltInWorkflows.diagnostic_check()
    check("diagnostic_check 并行组", any(s.parallel_group for s in diag_wf.steps))

    full_wf = BuiltInWorkflows.full_pipeline()
    check("full_pipeline 步骤数", len(full_wf.steps) >= 6, f"实际 {len(full_wf.steps)} 步")

    batch_wf = BuiltInWorkflows.batch_prediction()
    check("batch_prediction 超时配置",
          any(s.timeout > 100 for s in batch_wf.steps))

except Exception as e:
    check("端到端工作流测试", False, traceback.format_exc()[-200:])
    errors_log.append(("e2e workflow", str(e)))

print()

# ── 最终汇总 ───────────────────────────────────────
print(SEPARATOR)
print(f"  验证结果汇总")
print(SEPARATOR)
total = results["pass"] + results["fail"] + results["warn"]
print(f"  总检测项:   {total}")
print(f"  通过 (PASS): {results['pass']}")
print(f"  失败 (FAIL): {results['fail']}")
print(f"  警告 (WARN): {results['warn']}")
rate = results["pass"] / max(total, 1) * 100
print(f"  通过率:     {rate:.1f}%")

if errors_log:
    print(f"\n  错误详情 ({len(errors_log)} 条):")
    for src, err in errors_log:
        print(f"    - [{src}] {err[:120]}")

if results["fail"] == 0:
    overall = "[OK] 全部通过"
elif results["fail"] < 3:
    overall = "[!!] 有少量失败项"
else:
    overall = "[XX] 存在问题"

print(f"\n  总体状态: {overall}")
print(SEPARATOR)
