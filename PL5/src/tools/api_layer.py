"""
PL5 API 服务层

将工具系统暴露为 REST API 端点，支持两种模式:
1. FastAPI 模式 (推荐): 完整的 OpenAPI 文档、请求验证、异步支持
2. 轻量级模式: 基于 http.server 的基础 REST 接口（FastAPI 不可用时降级）

自动检测环境:
- 如果 fastapi 和 uvicorn 可用 → 使用完整 FastAPI 模式
- 否则 → 创建占位模块说明如何集成
"""

import json
import time
import logging
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

_FASTAPI_AVAILABLE = False
_PYDANTIC_AVAILABLE = False
_UVICORN_AVAILABLE = False

try:
    from fastapi import FastAPI, HTTPException, Query, Body
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    _FASTAPI_AVAILABLE = True
except ImportError:
    pass

try:
    import pydantic
    from pydantic import BaseModel, Field
    _PYDANTIC_AVAILABLE = True
except ImportError:
    pass

try:
    import uvicorn
    _UVICORN_AVAILABLE = True
except ImportError:
    pass


# ================================================================
# 通用数据模型（无论 FastAPI 是否可用都定义）
# ================================================================


class ToolRequest:
    """工具请求数据结构"""

    def __init__(self, kwargs: Optional[Dict] = None):
        self.kwargs = kwargs or {}

    def to_dict(self) -> Dict:
        return self.kwargs


class ToolResponse:
    """工具响应数据结构"""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        errors: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None,
        tool_name: str = "",
        elapsed_ms: float = 0.0,
    ):
        self.success = success
        self.data = data
        self.errors = errors or []
        self.metadata = metadata or {}
        self.tool_name = tool_name
        self.elapsed_ms = round(elapsed_ms, 2)

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "errors": self.errors,
            "metadata": self.metadata,
            "tool_name": self.tool_name,
            "elapsed_ms": self.elapsed_ms,
        }


class BatchRequest:
    """批量执行请求"""

    def __init__(self, calls: Optional[List[Dict]] = None):
        self.calls = calls or []


class WorkflowRequest:
    """工作流执行请求"""

    def __init__(
        self,
        template_name: str = "",
        config: Optional[Dict] = None,
        input_data: Optional[Dict] = None,
    ):
        self.template_name = template_name
        self.config = config or {}
        self.input_data = input_data or {}


# ================================================================
# Pydantic 模型（仅当 Pydantic 可用时使用）
# ================================================================


if _PYDANTIC_AVAILABLE:

    class ToolRequestModel(BaseModel):
        """Pydantic 工具请求模型"""
        kwargs: Dict[str, Any] = Field(default_factory=dict)

    class ToolResponseModel(BaseModel):
        """Pydantic 工具响应模型"""
        success: bool
        data: Any = None
        errors: List[Dict] = Field(default_factory=list)
        metadata: Dict = Field(default_factory=dict)
        tool_name: str = ""
        elapsed_ms: float = 0.0

    class BatchRequestModel(BaseModel):
        """Pydantic 批量请求模型"""
        calls: List[Dict[str, Any]] = Field(default_factory=list)

    class WorkflowRequestModel(BaseModel):
        """Pydantic 工作流请求模型"""
        template_name: str = ""
        config: Dict[str, Any] = Field(default_factory=dict)
        input_data: Dict[str, Any] = Field(default_factory=dict)

    class HealthResponse(BaseModel):
        """健康检查响应"""
        status: str
        version: str
        tools_count: int
        uptime_seconds: float
        fastapi_mode: bool


# ================================================================
# FastAPI 模式实现
# ================================================================


if _FASTAPI_AVAILABLE and _PYDANTIC_AVAILABLE:

    _start_time = time.time()

    app = FastAPI(
        title="PL5 Tools API",
        description="PL5 排列五预测系统 - 工具服务 REST API",
        version="V10.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _get_registry():
        from .base import get_registry
        return get_registry()

    def _create_context():
        from .base import ToolContext
        return ToolContext()

    @app.get("/", tags=["root"])
    async def root():
        return {
            "service": "PL5 Tools API",
            "version": "V10.0",
            "docs": "/docs",
            "status": "running",
        }

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health_check():
        registry = _get_registry()
        return HealthResponse(
            status="healthy",
            version="V10.0",
            tools_count=registry.count,
            uptime_seconds=round(time.time() - _start_time, 2),
            fastapi_mode=True,
        )

    @app.get("/tools", tags=["tools"])
    async def list_tools():
        registry = _get_registry()
        tools_info = []
        for name, cls in registry.list_all().items():
            try:
                instance = cls()
                info = instance.get_info()
                tools_info.append(info)
            except Exception as e:
                tools_info.append({
                    "name": name,
                    "error": str(e),
                    "class_name": cls.__name__,
                })
        return {"count": len(tools_info), "tools": tools_info}

    @app.get("/tools/{tool_name}", tags=["tools"])
    async def get_tool_info(tool_name: str):
        registry = _get_registry()
        cls = registry.get(tool_name)
        if cls is None:
            raise HTTPException(status_code=404, detail=f"工具 '{tool_name}' 未注册")
        instance = cls()
        return instance.get_info()

    @app.post(
        "/tools/{tool_name}/execute",
        response_model=ToolResponseModel,
        tags=["execution"]
    )
    async def execute_tool(tool_name: str, request: ToolRequestModel = Body(...)):
        registry = _get_registry()
        cls = registry.get(tool_name)
        if cls is None:
            raise HTTPException(status_code=404, detail=f"工具 '{tool_name}' 未注册")

        ctx = _create_context()
        start = time.time()

        try:
            tool_instance = cls()
            result = tool_instance.run_safe(ctx, **request.kwargs)
            elapsed = (time.time() - start) * 1000

            return ToolResponseModel(
                success=result.success,
                data=result.data,
                errors=[e.to_dict() for e in result.errors],
                metadata=result.metadata,
                tool_name=tool_name,
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return ToolResponseModel(
                success=False,
                errors=[{"code": "EXECUTION_ERROR", "message": str(e)}],
                tool_name=tool_name,
                elapsed_ms=elapsed,
            )

    @app.post("/batch/execute", tags=["execution"])
    async def execute_batch(request: BatchRequestModel = Body(...)):
        registry = _get_registry()
        ctx = _create_context()
        start = time.time()
        results = []

        for call in request.calls:
            tool_name = call.get("tool_name", "")
            args = call.get("kwargs", {})
            cls = registry.get(tool_name)

            if cls is None:
                results.append(ToolResponseModel(
                    success=False,
                    errors=[{"code": "TOOL_NOT_FOUND", "message": f"工具 '{tool_name}' 未注册"}],
                    tool_name=tool_name,
                ).to_dict())
                continue

            try:
                tool_instance = cls()
                result = tool_instance.run_safe(ctx, **args)
                results.append(ToolResponseModel(
                    success=result.success,
                    data=result.data,
                    errors=[e.to_dict() for e in result.errors],
                    metadata=result.metadata,
                    tool_name=tool_name,
                ).to_dict())
            except Exception as e:
                results.append(ToolResponseModel(
                    success=False,
                    errors=[{"code": "EXECUTION_ERROR", "message": str(e)}],
                    tool_name=tool_name,
                ).to_dict())

        elapsed = (time.time() - start) * 1000
        return {
            "total_calls": len(request.calls),
            "success_count": sum(1 for r in results if r.get("success")),
            "results": results,
            "elapsed_ms": round(elapsed, 2),
        }

    @app.post("/workflow/run", tags=["workflow"])
    async def run_workflow(request: WorkflowRequestModel = Body(...)):
        from .orchestrator import BuiltInWorkflows, WorkflowEngine

        template = BuiltInWorkflows.get_template(request.template_name)
        if template is None:
            raise HTTPException(
                status_code=404,
                detail=f"模板 '{request.template_name}' 不存在"
            )

        ctx = _create_context()
        if request.input_data:
            for k, v in request.input_data.items():
                ctx.set(k, v)

        engine = WorkflowEngine()
        start = time.time()

        try:
            wf_result = await engine.execute_async(template, ctx)
            elapsed = (time.time() - start) * 1000
            return {
                "success": wf_result.success,
                "template": request.template_name,
                "step_count": wf_result.step_count,
                "error_count": wf_result.error_count,
                "total_time_ms": round(elapsed, 2),
                "results": {
                    k: v.to_dict() for k, v in wf_result.results.items()
                },
                "final_output": wf_result.final_output,
                "errors": [e.to_dict() for e in wf_result.errors],
            }
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return {
                "success": False,
                "template": request.template_name,
                "error": str(e),
                "elapsed_ms": round(elapsed, 2),
            }

    @app.get("/workflows/templates", tags=["workflow"])
    async def list_workflow_templates():
        from .orchestrator import BuiltInWorkflows
        templates = BuiltInWorkflows.list_templates()
        return {
            "templates": [
                {"name": name, "description": wf.description}
                for name, wf in templates.items()
            ]
        }

    @app.get("/registry/stats", tags=["system"])
    async def registry_stats():
        from .base import get_registry, ToolLayer
        registry = get_registry()
        return {
            "total_tools": registry.count,
            "by_layer": {
                "infrastructure": len(registry.list_by_layer(ToolLayer.INFRASTRUCTURE)),
                "core": len(registry.list_by_layer(ToolLayer.CORE)),
                "application": len(registry.list_by_layer(ToolLayer.APPLICATION)),
            },
            "tool_names": list(registry.list_all().keys()),
        }


def create_fastapi_app() -> 'FastAPI':
    """创建并返回 FastAPI 应用实例

    Returns:
        配置好的 FastAPI app 对象

    Raises:
        RuntimeError: 当 FastAPI 不可用时
    """
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI 不可用。请安装: pip install fastapi uvicorn pydantic\n"
            "或使用轻量级 API 模式。"
        )
    return app


def run_api_server(host: str = "0.0.0.0", port: int = 8000, **kwargs):
    """启动 API 服务器

    Args:
        host: 监听地址
        port: 监听端口
        **kwargs: 额外的 uvicorn 参数
    """
    if not (_FASTAPI_AVAILABLE and _UVICORN_AVAILABLE):
        logger.warning(
            "[API Layer] FastAPI/Uvicorn 不可用，无法启动服务器。\n"
            "安装命令: pip install fastapi uvicorn pydantic"
        )
        print("=" * 60)
        print("  PL5 API 服务层 - 轻量级模式")
        print("=" * 60)
        print(f"\n  FastAPI 可用: {_FASTAPI_AVAILABLE}")
        print(f"  Pydantic 可用: {_PYDANTIC_AVAILABLE}")
        print(f"  Uvicorn 可用: {_UVICORN_AVAILABLE}")
        print("\n  要启用完整的 REST API 服务，请运行:")
        print("    pip install fastapi uvicorn pydantic")
        print("\n  然后重新导入此模块即可使用完整功能。")
        print("=" * 60)
        return

    uvicorn.run(app, host=host, port=port, **kwargs)


# ================================================================
# 轻量级模式：当 FastAPI 不可用时提供的基础能力说明
# ================================================================


class LightweightAPIRouter:
    """轻量级 API 路由器（FastAPI 不可用时的降级方案）

    提供基于标准库的简单路由映射和请求处理逻辑，
    可用于集成到自定义的 Web 框架中。
    """

    def __init__(self):
        self._routes: Dict[str, callable] = {}
        self._setup_routes()

    def _setup_routes(self):
        from .base import get_registry

        registry = get_registry()

        def handle_list_tools(params=None):
            tools = []
            for name, cls in registry.list_all().items():
                try:
                    inst = cls()
                    tools.append(inst.get_info())
                except Exception:
                    tools.append({"name": name})
            return {"count": len(tools), "tools": tools}

        def handle_health(params=None):
            return {
                "status": "ok",
                "mode": "lightweight",
                "tools_count": registry.count,
            }

        def handle_execute(params=None):
            if not params:
                return {"error": "缺少参数"}
            tool_name = params.get("tool_name")
            if not tool_name:
                return {"error": "缺少 tool_name"}
            cls = registry.get(tool_name)
            if cls is None:
                return {"error": f"工具 '{tool_name}' 未注册"}

            from .base import ToolContext
            ctx = ToolContext()
            kwargs = {k: v for k, v in params.items() if k != "tool_name"}

            try:
                inst = cls()
                result = inst.run_safe(ctx, **kwargs)
                return result.to_dict()
            except Exception as e:
                return {"success": False, "error": str(e)}

        self._routes = {
            "GET /health": handle_health,
            "GET /tools": handle_list_tools,
            "POST /tools/{tool_name}/execute": handle_execute,
        }

    def route(self, path: str, method: str = "GET") -> Optional[callable]:
        """获取路由处理器

        Args:
            path:   路径（如 '/tools'）
            method: HTTP 方法

        Returns:
            处理函数或 None
        """
        key = f"{method} {path}"
        return self._routes.get(key)

    def list_routes(self) -> List[Dict]:
        """列出所有已注册路由"""
        return [{"path": k.split(" ", 1)[1], "method": k.split(" ")[0]}
                for k in self._routes.keys()]

    def handle_request(self, path: str, method: str, params: Optional[Dict] = None) -> Dict:
        """处理一个模拟请求

        Args:
            path:   请求路径
            method: HTTP 方法
            params: 请求参数

        Returns:
            响应字典
        """
        handler = self.route(path, method)
        if handler is None:
            return {"error": f"未找到路由: {method} {path}", "status": 404}
        return handler(params)


def get_api_status() -> Dict:
    """获取 API 层的状态信息

    Returns:
        包含各依赖可用性的状态字典
    """
    return {
        "fastapi_available": _FASTAPI_AVAILABLE,
        "pydantic_available": _PYDANTIC_AVAILABLE,
        "uvicorn_available": _UVICORN_AVAILABLE,
        "full_api_ready": _FASTAPI_AVAILABLE and _PYDANTIC_AVAILABLE and _UVICORN_AVAILABLE,
        "lightweight_mode": not (_FASTAPI_AVAILABLE and _PYDANTIC_AVAILABLE),
        "install_hint": (
            "pip install fastapi uvicorn pydantic"
            if not (_FASTAPI_AVAILABLE and _UVICORN_AVAILABLE)
            else None
        ),
    }


__all__ = [
    "get_api_status",
    "create_fastapi_app",
    "run_api_server",
    "LightweightAPIRouter",
    "ToolRequest",
    "ToolResponse",
    "BatchRequest",
    "WorkflowRequest",
]
