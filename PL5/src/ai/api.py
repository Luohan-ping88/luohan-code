"""API服务层

提供AI工具系统的RESTful API接口。
"""

from fastapi import FastAPI, HTTPException, Query, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional
import jwt
from datetime import datetime, timedelta
import time

from .registry import get_registry
from .orchestrator import WorkflowEngine, Workflow
from .ai_types import LLMConfig, LLMType, AgentConfig, AgentType
from .agents.base import AgentFactory
from .memory.base import MemoryManager
from .tools.pl5 import register_pl5_tools
from .security import get_permission_manager, SecurityConfig, get_scanner
from .performance import monitored, cached, get_load_balancer, get_auto_scaler
from .error_handling import handle_error, AIError
from .system_health import (
    start_health_monitoring,
    register_service,
    HealthCheckResult,
    ServiceStatus,
    get_system_status,
    get_system_metrics,
    run_diagnostics,
)

# JWT配置
import os
import secrets
import logging

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv(
    "JWT_SECRET", secrets.token_urlsafe(32)
)  # 从环境变量读取，默认生成安全密钥
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION = int(os.getenv("JWT_EXPIRATION", "3600"))  # 1小时

# 会话配置
SESSION_CONFIG = {
    "access_token_expiry": int(
        os.getenv("ACCESS_TOKEN_EXPIRY", "3600")
    ),  # 访问令牌过期时间（秒）
    "refresh_token_expiry": int(
        os.getenv("REFRESH_TOKEN_EXPIRY", "86400")
    ),  # 刷新令牌过期时间（秒）
    "session_timeout": int(
        os.getenv("SESSION_TIMEOUT", "1800")
    ),  # 会话超时时间（秒）
    "max_concurrent_sessions": int(
        os.getenv("MAX_CONCURRENT_SESSIONS", "5")
    ),  # 最大并发会话数
    "session_cleanup_interval": int(
        os.getenv("SESSION_CLEANUP_INTERVAL", "60")
    ),  # 会话清理间隔（秒）
}

# 创建FastAPI应用
app = FastAPI(
    title="AI工具系统API",
    description="让智能体拥有动手能力的API服务",
    version="1.0.0",
)

# 配置CORS - 从环境变量读取允许的域名
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", "https://your-domain.com"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# 初始化组件
workflow_engine = WorkflowEngine()
memory_manager = MemoryManager()
permission_manager = get_permission_manager()

# 注册PL5工具
register_pl5_tools()

# 安全方案
security = HTTPBearer()

# 导入用户管理器
from .users import get_user_manager

user_manager = get_user_manager()


# JWT工具函数
def create_access_token(data: Dict[str, Any]) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """验证令牌"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# 速率限制中间件
class RateLimitMiddleware:
    """速率限制中间件"""

    def __init__(self, app, config: dict = None):
        """初始化速率限制中间件

        Args:
            app: FastAPI应用
            config: 速率限制配置
        """
        self.app = app
        # 默认配置
        self.config = config or {
            "default": {"max_requests": 100, "window_seconds": 60},
            "strict": {"max_requests": 10, "window_seconds": 60},
            "api": {"max_requests": 50, "window_seconds": 60},
            "auth": {"max_requests": 5, "window_seconds": 60},
        }
        self.requests = {}
        self.blocked_ips = set()

    def _get_endpoint_category(self, path: str) -> str:
        """获取端点类别"""
        if path.startswith("/api/auth/"):
            return "auth"
        elif path.startswith("/api/"):
            return "api"
        elif path.startswith("/predict/") or path.startswith("/train/"):
            return "strict"
        return "default"

    def _get_limit_config(self, category: str) -> dict:
        """获取限制配置"""
        return self.config.get(category, self.config["default"])

    async def __call__(self, scope, receive, send):
        """处理请求"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from fastapi import Request
        from fastapi.responses import JSONResponse
        from fastapi import status as http_status

        request = Request(scope, receive=receive)
        client_ip = request.client.host if request.client else "127.0.0.1"

        # 检查是否被封禁
        if client_ip in self.blocked_ips:
            response = JSONResponse(
                status_code=http_status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "IP blocked due to repeated rate limit violations"
                },
            )
            await response(scope, receive, send)
            return

        now = time.time()
        path = scope.get("path", "")
        category = self._get_endpoint_category(path)
        limit_config = self._get_limit_config(category)
        max_requests = limit_config["max_requests"]
        window_seconds = limit_config["window_seconds"]

        # 初始化或清理请求记录
        if client_ip not in self.requests:
            self.requests[client_ip] = {}
        if category not in self.requests[client_ip]:
            self.requests[client_ip][category] = []

        # 清理过期记录
        self.requests[client_ip][category] = [
            t
            for t in self.requests[client_ip][category]
            if now - t < window_seconds
        ]

        # 检查请求数
        if len(self.requests[client_ip][category]) >= max_requests:
            # 记录违规次数
            if "violations" not in self.requests[client_ip]:
                self.requests[client_ip]["violations"] = 0
            self.requests[client_ip]["violations"] += 1

            # 如果违规超过5次，封禁IP
            if self.requests[client_ip]["violations"] >= 5:
                self.blocked_ips.add(client_ip)
                response = JSONResponse(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": "IP blocked due to repeated rate limit violations"
                    },
                )
            else:
                response = JSONResponse(
                    status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": f"Rate limit exceeded for {category} endpoints",
                        "retry_after": window_seconds,
                        "violations": self.requests[client_ip]["violations"],
                        "max_violations_before_block": 5,
                    },
                )
            await response(scope, receive, send)
            return

        # 记录请求
        self.requests[client_ip][category].append(now)

        # 处理请求
        await self.app(scope, receive, send)


# 添加速率限制中间件
rate_limit_config = {
    "default": {"max_requests": 100, "window_seconds": 60},
    "strict": {"max_requests": 10, "window_seconds": 60},  # 预测/训练端点
    "api": {"max_requests": 50, "window_seconds": 60},  # API端点
    "auth": {"max_requests": 5, "window_seconds": 60},  # 认证端点
}
app.add_middleware(RateLimitMiddleware, config=rate_limit_config)


# HTTPS强制重定向中间件
class HTTPSRedirectMiddleware:
    """HTTPS强制重定向中间件"""

    def __init__(self, app):
        self.app = app
        self.https_enabled = (
            os.getenv("HTTPS_ENABLED", "false").lower() == "true"
        )

    async def __call__(self, scope, receive, send):
        """处理请求"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 如果启用了HTTPS且请求是HTTP，重定向到HTTPS
        if self.https_enabled:
            from fastapi import Request
            from fastapi.responses import RedirectResponse
            from fastapi import status as http_status

            request = Request(scope, receive=receive)

            # 检查是否是HTTP请求
            if request.url.scheme == "http":
                # 构建HTTPS URL
                https_url = f"https://{request.url.hostname}{request.url.path}"
                if request.url.query:
                    https_url += f"?{request.url.query}"

                response = RedirectResponse(
                    url=https_url,
                    status_code=http_status.HTTP_301_MOVED_PERMANENTLY,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


# HSTS中间件
class HSTSMiddleware:
    """HTTP严格传输安全中间件"""

    def __init__(
        self, app, max_age: int = 31536000, include_subdomains: bool = True
    ):
        self.app = app
        self.hsts_header = f"max-age={max_age}"
        if include_subdomains:
            self.hsts_header += "; includeSubDomains"

    async def __call__(self, scope, receive, send):
        """处理请求"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 获取原始响应
        response_sent = False

        async def send_wrapper(message):
            nonlocal response_sent
            if message["type"] == "http.response.start" and not response_sent:
                headers = list(message.get("headers", []))
                headers.append(
                    (b"strict-transport-security", self.hsts_header.encode())
                )
                message["headers"] = headers
                response_sent = True
            await send(message)

        await self.app(scope, receive, send_wrapper)


# 添加HTTPS重定向中间件（仅在生产环境启用）
app.add_middleware(HTTPSRedirectMiddleware)

# 添加HSTS中间件（有效期1年）
app.add_middleware(HSTSMiddleware, max_age=31536000, include_subdomains=True)


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    # 使用错误处理器处理异常
    ai_error = handle_error(exc, {"request_path": str(request.url)})

    # 处理HTTP异常
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_type": "http_error"},
        )

    # 处理AIError
    if isinstance(ai_error, AIError):
        # 根据错误类型设置状态码
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if ai_error.error_type in ["client_error", "validation_error"]:
            status_code = status.HTTP_400_BAD_REQUEST
        elif ai_error.error_type == "auth_error":
            status_code = status.HTTP_401_UNAUTHORIZED
        elif ai_error.error_type == "rate_limit_error":
            status_code = status.HTTP_429_TOO_MANY_REQUESTS

        return JSONResponse(
            status_code=status_code, content=ai_error.to_dict()
        )

    # 处理其他异常
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error_type": "unknown_error",
        },
    )


# 依赖项
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """获取当前用户"""
    token = credentials.credentials
    payload = verify_token(token)
    username = payload.get("sub")

    # 使用用户管理器验证用户
    user_info = user_manager.get_user_by_username(username)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": user_info["username"], "role": user_info["role"]}


@app.on_event("startup")
def startup_event():
    """启动事件"""
    print("AI工具系统API服务启动中...")
    # 注册内置工具
    from .tools.builtin import SearchTool, CalculatorTool, FileTool
    from .registry import register_tool

    # 注册搜索工具
    @register_tool(
        name="search",
        description="在互联网上搜索信息",
        parameters=[
            {
                "name": "query",
                "type": "str",
                "description": "搜索查询词",
                "required": True,
            },
            {
                "name": "max_results",
                "type": "int",
                "description": "最大结果数量",
                "required": False,
                "default": 5,
            },
        ],
        category="builtin",
    )
    def search_tool(params):
        tool = SearchTool()
        return tool.execute(params)

    # 注册计算器工具
    @register_tool(
        name="calculator",
        description="执行数学计算",
        parameters=[
            {
                "name": "expression",
                "type": "str",
                "description": "数学表达式",
                "required": True,
            }
        ],
        category="builtin",
    )
    def calculator_tool(params):
        tool = CalculatorTool()
        return tool.execute(params)

    # 注册文件工具
    @register_tool(
        name="file",
        description="文件操作工具",
        parameters=[
            {
                "name": "action",
                "type": "str",
                "description": "操作类型: read, write, list",
                "required": True,
            },
            {
                "name": "path",
                "type": "str",
                "description": "文件路径",
                "required": True,
            },
            {
                "name": "content",
                "type": "str",
                "description": "文件内容（仅write操作需要）",
                "required": False,
            },
            {
                "name": "max_lines",
                "type": "int",
                "description": "最大读取行数（仅read操作需要）",
                "required": False,
                "default": 100,
            },
        ],
        category="builtin",
    )
    def file_tool(params):
        tool = FileTool()
        return tool.execute(params)

    # 启动健康监控
    start_health_monitoring()

    # 注册API服务健康检查
    def api_health_check():
        try:
            # 检查注册表是否正常
            registry = get_registry()
            tool_count = len(registry.list_tools())

            # 检查工作流引擎是否正常
            workflow_count = len(workflow_engine.list_workflows())

            metrics = {
                "tool_count": tool_count,
                "workflow_count": workflow_count,
            }

            return HealthCheckResult(
                service="api",
                status=ServiceStatus.HEALTHY,
                message="API service is healthy",
                metrics=metrics,
            )
        except Exception as e:
            return HealthCheckResult(
                service="api",
                status=ServiceStatus.UNHEALTHY,
                message=f"API service health check failed: {str(e)}",
            )

    # 注册API服务健康检查
    register_service("api", api_health_check)

    print("AI工具系统API服务启动完成！")


# ── 根路由与健康检查 ──────────────────────────────────────────


@app.get("/")
async def root():
    """根路由 - 系统信息"""
    from src import __version__

    return {
        "name": "PL5 排列五高阶数理分析预测系统",
        "version": __version__,
        "status": "running",
        "docs": "/docs",
        "api_prefix": "/api",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    from src import __version__

    return {
        "status": "healthy",
        "version": __version__,
        "timestamp": datetime.now().isoformat(),
        "uptime": "running",
    }


# ── 前端页面路由 ────────────────────────────────────────────


def get_frontend_dir():
    """获取前端目录路径"""
    import os

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(project_root, "frontend")


def get_models_dir():
    """获取模型目录路径"""
    import os

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(project_root, "models")


@app.get("/login")
async def login_page():
    """登录页面"""
    from fastapi.responses import FileResponse
    import os

    frontend_dir = get_frontend_dir()
    login_path = os.path.join(frontend_dir, "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path, media_type="text/html")
    return {"error": "Login page not found"}


@app.get("/dashboard")
async def dashboard_page():
    """仪表板页面"""
    from fastapi.responses import FileResponse
    import os

    frontend_dir = get_frontend_dir()
    dashboard_path = os.path.join(frontend_dir, "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    return {"error": "Dashboard page not found"}


# ── 认证相关接口 ────────────────────────────────────────────


@app.post("/api/auth/login")
async def login(username: str, password: str):
    """用户登录

    Args:
        username: 用户名
        password: 密码

    Returns:
        访问令牌
    """
    # 使用用户管理器验证密码
    success, user_info = user_manager.verify_password(username, password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"username": user_info["username"], "role": user_info["role"]},
    }


@app.get("/api/auth/me")
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取当前用户信息

    Args:
        current_user: 当前用户

    Returns:
        用户信息
    """
    return current_user


# ── 工具相关接口 ──────────────────────────────────────────────


@app.get("/api/tools")
@monitored(name="list_tools")
@cached(ttl=300)  # 5分钟缓存
async def list_tools():
    """列出所有可用工具"""
    registry = get_registry()
    tools = registry.list_tools()
    tool_infos = []

    for tool_name in tools:
        tool_info = registry.get_tool_info(tool_name)
        if tool_info:
            tool_infos.append(
                {
                    "name": tool_info.name,
                    "description": tool_info.description,
                    "category": tool_info.category.value,
                    "tags": tool_info.tags,
                    "parameters": [
                        {
                            "name": param.name,
                            "type": param.type,
                            "description": param.description,
                            "required": param.required,
                            "default": param.default,
                        }
                        for param in tool_info.parameters
                    ],
                }
            )

    return {"tools": tool_infos, "count": len(tool_infos)}


@app.post("/api/tools/{tool_name}/execute")
@monitored(name="execute_tool")
async def execute_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """执行工具"""
    # 检查权限
    if not permission_manager.has_permission(current_user["role"], tool_name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    registry = get_registry()
    result = registry.execute_tool(tool_name, parameters)

    return {
        "tool": tool_name,
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "metadata": result.metadata,
    }


# ── Agent相关接口 ─────────────────────────────────────────────


@app.post("/api/agents/create")
def create_agent(
    config: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """创建Agent"""
    try:
        # 构建LLM配置
        llm_config = LLMConfig(
            model_type=LLMType(config.get("model_type", "local")),
            model_name=config.get("model_name", "gpt-3.5-turbo"),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 1000),
            timeout=config.get("timeout", 30),
            streaming=config.get("streaming", False),
        )

        # 构建Agent配置
        agent_config = AgentConfig(
            agent_type=AgentType(config.get("agent_type", "react")),
            llm_config=llm_config,
            max_steps=config.get("max_steps", 10),
            max_retries=config.get("max_retries", 3),
            timeout=config.get("timeout", 300),
        )

        # 创建Agent
        agent = AgentFactory.create(agent_config)

        return {
            "success": True,
            "agent_type": agent.agent_type.value,
            "model_type": agent.llm.model_type.value,
            "model_name": agent.llm.model_name,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/agents/run")
async def run_agent(
    task: str,
    context: Optional[Dict[str, Any]] = None,
    agent_config: Optional[Dict[str, Any]] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """运行Agent"""
    try:
        # 构建默认配置
        if not agent_config:
            agent_config = {
                "agent_type": "react",
                "model_type": "local",
                "model_name": "gpt-3.5-turbo",
            }

        # 创建Agent
        llm_config = LLMConfig(
            model_type=LLMType(agent_config.get("model_type", "local")),
            model_name=agent_config.get("model_name", "gpt-3.5-turbo"),
            api_key=agent_config.get("api_key"),
            base_url=agent_config.get("base_url"),
            temperature=agent_config.get("temperature", 0.7),
            max_tokens=agent_config.get("max_tokens", 1000),
            timeout=agent_config.get("timeout", 30),
            streaming=agent_config.get("streaming", False),
        )

        agent_config_obj = AgentConfig(
            agent_type=AgentType(agent_config.get("agent_type", "react")),
            llm_config=llm_config,
            max_steps=agent_config.get("max_steps", 10),
            max_retries=agent_config.get("max_retries", 3),
            timeout=agent_config.get("timeout", 300),
        )

        agent = AgentFactory.create(agent_config_obj)

        # 运行Agent
        result = agent.run(task, context)

        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "metadata": result.metadata,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── 工作流相关接口 ────────────────────────────────────────────


@app.post("/api/workflows/create")
def create_workflow(
    workflow_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """创建工作流"""
    try:
        from .ai_types import WorkflowStep

        # 构建工作流步骤
        steps = []
        for step_data in workflow_data.get("steps", []):
            step = WorkflowStep(
                name=step_data["name"],
                tool_name=step_data["tool_name"],
                parameters=step_data.get("parameters", {}),
                condition_expr=step_data.get("condition_expr"),
                retry_count=step_data.get("retry_count", 0),
                retry_delay=step_data.get("retry_delay", 1.0),
                parallel_group=step_data.get("parallel_group"),
            )
            steps.append(step)

        # 创建工作流
        workflow = Workflow(
            name=workflow_data["name"],
            description=workflow_data.get("description", ""),
            steps=steps,
            variables=workflow_data.get("variables", {}),
        )

        return {
            "success": True,
            "workflow_id": workflow.execution_id,
            "name": workflow.name,
            "steps": len(workflow.steps),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/workflows/run")
@monitored(name="run_workflow")
async def run_workflow(
    workflow_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """运行工作流"""
    try:
        from .ai_types import WorkflowStep

        # 构建工作流步骤
        steps = []
        for step_data in workflow_data.get("steps", []):
            step = WorkflowStep(
                name=step_data["name"],
                tool_name=step_data["tool_name"],
                parameters=step_data.get("parameters", {}),
                condition_expr=step_data.get("condition_expr"),
                retry_count=step_data.get("retry_count", 0),
                retry_delay=step_data.get("retry_delay", 1.0),
                parallel_group=step_data.get("parallel_group"),
            )
            steps.append(step)

        # 创建工作流
        workflow = Workflow(
            name=workflow_data["name"],
            description=workflow_data.get("description", ""),
            steps=steps,
            variables=workflow_data.get("variables", {}),
        )

        # 运行工作流
        result = await workflow_engine.run_workflow(workflow)

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/workflows/running")
def list_running_workflows(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """列出运行中的工作流"""
    workflows = workflow_engine.list_running_workflows()
    return {"workflows": workflows, "count": len(workflows)}


@app.get("/api/workflows/list")
def list_workflows(
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """列出工作流"""
    from .ai_types import WorkflowStatus

    workflow_status = WorkflowStatus(status) if status else None
    workflows = workflow_engine.list_workflows(workflow_status)
    return {"workflows": workflows, "count": len(workflows)}


@app.post("/api/workflows/{execution_id}/resume")
async def resume_workflow(
    execution_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """恢复工作流"""
    try:
        result = await workflow_engine.resume_workflow(execution_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/workflows/{execution_id}")
def delete_workflow(
    execution_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """删除工作流"""
    success = workflow_engine.delete_workflow(execution_id)
    return {"success": success}


# ── 记忆相关接口 ──────────────────────────────────────────────


@app.post("/api/memory/create")
def create_memory(
    memory_config: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """创建记忆"""
    try:
        from .ai_types import MemoryConfig, MemoryType
        from .memory.conversation import ConversationMemory
        from .memory.execution import ExecutionMemory

        # 构建记忆配置
        config = MemoryConfig(
            memory_type=MemoryType(
                memory_config.get("memory_type", "conversation")
            ),
            max_size=memory_config.get("max_size", 1000),
            ttl=memory_config.get("ttl"),
            embedding_dim=memory_config.get("embedding_dim", 1536),
        )

        # 创建记忆实例
        if config.memory_type == MemoryType.CONVERSATION:
            memory = ConversationMemory(config)
        elif config.memory_type == MemoryType.EXECUTION:
            memory = ExecutionMemory(config)
        else:
            raise ValueError(f"Unsupported memory type: {config.memory_type}")

        # 添加到管理器
        memory_name = memory_config.get(
            "name", f"memory_{config.memory_type.value}"
        )
        memory_manager.add_memory(memory_name, memory)

        return {
            "success": True,
            "memory_name": memory_name,
            "memory_type": config.memory_type.value,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/memory/{memory_name}/add")
def add_memory_item(
    memory_name: str,
    item: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """添加记忆项"""
    memory = memory_manager.get_memory(memory_name)
    if not memory:
        raise HTTPException(
            status_code=404, detail=f"Memory '{memory_name}' not found"
        )

    try:
        from .ai_types import ConversationMessage

        # 根据记忆类型添加不同的项
        if hasattr(memory, "add_user_message"):
            # 对话记忆
            if "content" in item:
                memory.add_user_message(item["content"])
            elif "role" in item and "content" in item:
                message = ConversationMessage(
                    role=item["role"], content=item["content"]
                )
                memory.add(message)
        elif hasattr(memory, "add_execution_record"):
            # 执行记忆
            if "tool_name" in item and "parameters" in item:
                memory.add_execution_record(
                    tool_name=item["tool_name"],
                    parameters=item["parameters"],
                    result=item.get("result"),
                    execution_time=item.get("execution_time", 0.0),
                )

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/memory/{memory_name}/get")
def get_memory_items(
    memory_name: str,
    limit: int = Query(10, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取记忆项"""
    memory = memory_manager.get_memory(memory_name)
    if not memory:
        raise HTTPException(
            status_code=404, detail=f"Memory '{memory_name}' not found"
        )

    items = memory.get_all()
    if hasattr(memory, "get_last_n_messages"):
        items = memory.get_last_n_messages(limit)
    elif hasattr(memory, "get_last_n_records"):
        items = memory.get_last_n_records(limit)

    # 转换为可序列化的格式
    serialized_items = []
    for item in items:
        if hasattr(item, "to_dict"):
            serialized_items.append(item.to_dict())
        elif hasattr(item, "__dict__"):
            serialized_items.append(
                {
                    k: v
                    for k, v in item.__dict__.items()
                    if not k.startswith("_")
                }
            )
        else:
            serialized_items.append(str(item))

    return {"items": serialized_items, "count": len(serialized_items)}


# ── 工作流模板相关接口 ────────────────────────────────────────


@app.post("/api/workflow-templates/save")
def save_workflow_template(
    template_name: str,
    workflow_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """保存工作流模板"""
    try:
        from .ai_types import WorkflowStep

        # 构建工作流步骤
        steps = []
        for step_data in workflow_data.get("steps", []):
            step = WorkflowStep(
                name=step_data["name"],
                tool_name=step_data["tool_name"],
                parameters=step_data.get("parameters", {}),
                condition_expr=step_data.get("condition_expr"),
                retry_count=step_data.get("retry_count", 0),
                retry_delay=step_data.get("retry_delay", 1.0),
                parallel_group=step_data.get("parallel_group"),
            )
            steps.append(step)

        # 创建工作流
        workflow = Workflow(
            name=workflow_data["name"],
            description=workflow_data.get("description", ""),
            steps=steps,
            variables=workflow_data.get("variables", {}),
        )

        # 保存模板
        success = workflow_engine.save_template(template_name, workflow)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/workflow-templates/list")
def list_workflow_templates(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """列出工作流模板"""
    templates = workflow_engine.list_templates()
    return {"templates": templates, "count": len(templates)}


@app.post("/api/workflow-templates/{template_name}/load")
def load_workflow_template(
    template_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """加载工作流模板"""
    workflow = workflow_engine.load_template(template_name)
    if not workflow:
        raise HTTPException(
            status_code=404, detail=f"Template '{template_name}' not found"
        )

    return {"success": True, "workflow": workflow.to_dict()}


@app.delete("/api/workflow-templates/{template_name}")
def delete_workflow_template(
    template_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """删除工作流模板"""
    success = workflow_engine.delete_template(template_name)
    return {"success": success}


# ── 系统相关接口 ──────────────────────────────────────────────


@app.get("/api/system/stats")
def get_system_stats(current_user: Dict[str, Any] = Depends(get_current_user)):
    """获取系统统计信息"""
    registry = get_registry()

    return {
        "tools": {
            "total": len(registry.list_tools()),
            "stats": registry.get_stats(),
        },
        "workflows": {
            "running": len(workflow_engine.list_running_workflows())
        },
        "memory": memory_manager.get_stats(),
    }


# WebSocket管理器
class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        """初始化连接管理器"""
        self.active_connections: Dict[str, WebSocket] = {}
        self.training_subscribers: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """连接WebSocket"""
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        """断开WebSocket连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.training_subscribers:
            del self.training_subscribers[client_id]

    async def send_personal_message(
        self, message: Dict[str, Any], client_id: str
    ):
        """发送个人消息"""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息"""
        for connection in self.active_connections.values():
            await connection.send_json(message)

    async def broadcast_training_update(self, message: Dict[str, Any]):
        """广播训练状态更新"""
        for connection in self.training_subscribers.values():
            try:
                await connection.send_json(message)
            except Exception:
                pass


# 训练状态管理器
class TrainingStatusManager:
    """训练状态管理器 - 与实际调度器联动"""

    def __init__(self):
        self._running = False
        self._last_status = {}
        self._monitor_task = None

    def get_current_status(self) -> Dict[str, Any]:
        """获取当前训练状态"""
        from pathlib import Path
        import json

        status_file = Path("logs/data/scheduler_v8_status.json")

        if status_file.exists():
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "current_task": "空闲",
            "learning_progress": 0,
            "last_run": None,
            "next_run": None,
            "is_running": self._running,
        }

    def get_detailed_status(self) -> Dict[str, Any]:
        """获取详细训练状态"""
        from pathlib import Path
        from datetime import datetime

        status = self.get_current_status()
        status_file = Path("logs/data/scheduler_v8_status.json")

        log_path = Path("logs/app.log")
        if not log_path.exists():
            log_path = Path("logs/latest.log")

        training_steps = {
            "data_fetch": {
                "step": "数据采集",
                "status": "pending",
                "time": None,
                "desc": "等待定时采集",
            },
            "feature_engineering": {
                "step": "特征提取",
                "status": "pending",
                "time": None,
                "desc": "等待特征提取",
            },
            "training": {
                "step": "模型训练",
                "status": "pending",
                "time": None,
                "desc": "等待模型训练",
            },
            "prediction": {
                "step": "生成预测",
                "status": "pending",
                "time": None,
                "desc": "等待生成预测",
            },
        }

        current_task = status.get("current_task", "")
        progress = status.get("learning_progress", 0)

        if progress >= 100:
            if "采集" in current_task:
                training_steps["data_fetch"] = {
                    "step": "数据采集",
                    "status": "completed",
                    "time": status.get("last_run", ""),
                    "desc": "已完成",
                }
            if "特征" in current_task or "采集" in current_task:
                training_steps["feature_engineering"] = {
                    "step": "特征提取",
                    "status": "completed",
                    "time": status.get("last_run", ""),
                    "desc": "已完成",
                }
            if (
                "训练" in current_task
                or "特征" in current_task
                or "采集" in current_task
            ):
                training_steps["training"] = {
                    "step": "模型训练",
                    "status": "completed",
                    "time": status.get("last_run", ""),
                    "desc": "已完成",
                }
            training_steps["prediction"] = {
                "step": "生成预测",
                "status": "completed",
                "time": status.get("last_run", ""),
                "desc": "已完成",
            }
        elif progress > 0:
            if "采集" in current_task:
                training_steps["data_fetch"] = {
                    "step": "数据采集",
                    "status": "completed",
                    "time": status.get("last_run", ""),
                    "desc": "已完成",
                }
                training_steps["feature_engineering"] = {
                    "step": "特征提取",
                    "status": "running",
                    "time": "进行中",
                    "desc": f"进行中 ({progress}%)",
                }
            elif "特征" in current_task:
                training_steps["data_fetch"] = {
                    "step": "数据采集",
                    "status": "completed",
                    "time": status.get("last_run", ""),
                    "desc": "已完成",
                }
                training_steps["feature_engineering"] = {
                    "step": "特征提取",
                    "status": "running",
                    "time": "进行中",
                    "desc": f"进行中 ({progress}%)",
                }
            elif "训练" in current_task:
                training_steps["data_fetch"] = {
                    "step": "数据采集",
                    "status": "completed",
                    "time": status.get("last_run", ""),
                    "desc": "已完成",
                }
                training_steps["feature_engineering"] = {
                    "step": "特征提取",
                    "status": "completed",
                    "time": status.get("last_run", ""),
                    "desc": "已完成",
                }
                training_steps["training"] = {
                    "step": "模型训练",
                    "status": "running",
                    "time": "进行中",
                    "desc": f"进行中 ({progress}%)",
                }

        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for line in reversed(lines[-2000:]):
                    line_lower = line.lower()
                    if "数据采集" in line and "完成" in line:
                        training_steps["data_fetch"] = {
                            "step": "数据采集",
                            "status": "completed",
                            "time": self._extract_time(line),
                            "desc": "最新数据已入库",
                        }
                        break
                    elif "特征" in line and "完成" in line:
                        training_steps["feature_engineering"] = {
                            "step": "特征提取",
                            "status": "completed",
                            "time": self._extract_time(line),
                            "desc": "特征工程完成",
                        }
                        break
                    elif "训练" in line and "完成" in line:
                        training_steps["training"] = {
                            "step": "模型训练",
                            "status": "completed",
                            "time": self._extract_time(line),
                            "desc": "模型训练完成",
                        }
                        break
                    elif "预测" in line and ("完成" in line or "生成" in line):
                        training_steps["prediction"] = {
                            "step": "生成预测",
                            "status": "completed",
                            "time": self._extract_time(line),
                            "desc": "预测已生成",
                        }
                        break
            except Exception:
                pass

        return {
            "scheduler_status": status,
            "training_steps": training_steps,
            "last_updated": datetime.now().isoformat(),
        }

    def _extract_time(self, line: str) -> str:
        """从日志行提取时间"""
        import re

        match = re.search(r"(\d{2}:\d{2}:\d{2}|\d{2}:\d{2})", line)
        return match.group(1) if match else "未知"

    def has_status_changed(self) -> bool:
        """检查状态是否有变化"""
        current = self.get_current_status()
        changed = current != self._last_status
        self._last_status = current
        return changed


# 创建全局实例
training_manager = TrainingStatusManager()
manager = ConnectionManager()


# WebSocket端点
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket端点"""
    await manager.connect(websocket, client_id)
    training_subscribed = False

    try:
        await manager.send_personal_message(
            {
                "type": "connected",
                "client_id": client_id,
                "message": "已连接到训练监控系统",
            },
            client_id,
        )

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await manager.send_personal_message(
                    {"type": "pong"}, client_id
                )

            elif data.get("type") == "subscribe_training":
                manager.training_subscribers[client_id] = websocket
                training_subscribed = True
                status = training_manager.get_detailed_status()
                await manager.send_personal_message(
                    {"type": "training_status", "data": status}, client_id
                )
                logger.info(f"[WebSocket] 客户端 {client_id} 订阅了训练状态")

            elif data.get("type") == "unsubscribe_training":
                if client_id in manager.training_subscribers:
                    del manager.training_subscribers[client_id]
                training_subscribed = False

            elif data.get("type") == "get_training_status":
                status = training_manager.get_detailed_status()
                await manager.send_personal_message(
                    {"type": "training_status", "data": status}, client_id
                )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        if training_subscribed:
            logger.info(
                f"[WebSocket] 客户端 {client_id} 断开连接，已取消训练状态订阅"
            )


async def broadcast_training_update():
    """广播训练状态更新到所有订阅者"""
    try:
        status = training_manager.get_detailed_status()
        await manager.broadcast_training_update(
            {"type": "training_status_update", "data": status}
        )
    except Exception as e:
        logger.error(f"广播训练状态失败: {e}")


# 训练状态轮询任务
_training_polling_active = False


async def start_training_polling():
    """启动训练状态轮询"""
    global _training_polling_active
    _training_polling_active = True

    async def poll():
        while _training_polling_active:
            try:
                if training_manager.has_status_changed():
                    await broadcast_training_update()
            except Exception:
                pass
            await asyncio.sleep(5)

    import asyncio

    asyncio.create_task(poll())


# 工作流状态更新函数
def send_workflow_update(workflow_id: str, status: str, data: Dict[str, Any]):
    """发送工作流状态更新"""
    import asyncio

    message = {
        "type": "workflow_update",
        "workflow_id": workflow_id,
        "status": status,
        "data": data,
    }
    asyncio.create_task(manager.broadcast(message))


# ── 安全相关接口 ──────────────────────────────────────────────


@app.get("/api/security/config")
async def get_security_config(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取安全配置"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    config = {
        "MAX_STRING_LENGTH": SecurityConfig.MAX_STRING_LENGTH,
        "MAX_LIST_LENGTH": SecurityConfig.MAX_LIST_LENGTH,
        "MAX_DICT_DEPTH": SecurityConfig.MAX_DICT_DEPTH,
        "MAX_REQUESTS_PER_MINUTE": SecurityConfig.MAX_REQUESTS_PER_MINUTE,
        "MAX_REQUESTS_PER_HOUR": SecurityConfig.MAX_REQUESTS_PER_HOUR,
        "PASSWORD_MIN_LENGTH": SecurityConfig.PASSWORD_MIN_LENGTH,
        "PASSWORD_REQUIRE_UPPERCASE": SecurityConfig.PASSWORD_REQUIRE_UPPERCASE,
        "PASSWORD_REQUIRE_LOWERCASE": SecurityConfig.PASSWORD_REQUIRE_LOWERCASE,
        "PASSWORD_REQUIRE_DIGIT": SecurityConfig.PASSWORD_REQUIRE_DIGIT,
        "PASSWORD_REQUIRE_SPECIAL": SecurityConfig.PASSWORD_REQUIRE_SPECIAL,
        "PASSWORD_EXPIRATION_DAYS": SecurityConfig.PASSWORD_EXPIRATION_DAYS,
        "PASSWORD_HISTORY_SIZE": SecurityConfig.PASSWORD_HISTORY_SIZE,
        "SESSION_TIMEOUT": SecurityConfig.SESSION_TIMEOUT,
        "SESSION_MAX_INACTIVE_INTERVAL": SecurityConfig.SESSION_MAX_INACTIVE_INTERVAL,
        "TOKEN_EXPIRATION": SecurityConfig.TOKEN_EXPIRATION,
        "REFRESH_TOKEN_EXPIRATION": SecurityConfig.REFRESH_TOKEN_EXPIRATION,
        "ENABLE_CORS": SecurityConfig.ENABLE_CORS,
        "ENABLE_RATE_LIMITING": SecurityConfig.ENABLE_RATE_LIMITING,
        "ENABLE_XSS_PROTECTION": SecurityConfig.ENABLE_XSS_PROTECTION,
        "ENABLE_CSRF_PROTECTION": SecurityConfig.ENABLE_CSRF_PROTECTION,
        "ENABLE_CONTENT_SECURITY_POLICY": SecurityConfig.ENABLE_CONTENT_SECURITY_POLICY,
        "LOG_SECURITY_EVENTS": SecurityConfig.LOG_SECURITY_EVENTS,
        "LOG_AUDIT_EVENTS": SecurityConfig.LOG_AUDIT_EVENTS,
        "LOG_ERRORS": SecurityConfig.LOG_ERRORS,
        "ENCRYPT_SENSITIVE_DATA": SecurityConfig.ENCRYPT_SENSITIVE_DATA,
        "DATA_RETENTION_DAYS": SecurityConfig.DATA_RETENTION_DAYS,
    }

    return {"config": config}


@app.post("/api/security/config")
async def update_security_config(
    config_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """更新安全配置"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    # 更新配置
    for key, value in config_data.items():
        if hasattr(SecurityConfig, key):
            setattr(SecurityConfig, key, value)

    # 保存配置到文件
    SecurityConfig.save_to_file("./security_config.json")

    return {"success": True, "message": "Security config updated"}


@app.post("/api/security/scan")
async def run_security_scan(
    input_data: Optional[Any] = None,
    config: Optional[Dict[str, Any]] = None,
    directory: str = ".",
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """运行安全扫描"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    scanner = get_scanner()
    vulnerabilities = scanner.run_full_scan(input_data, config, directory)
    report = scanner.generate_report()

    return {"report": report}


@app.get("/api/security/vulnerabilities")
async def get_vulnerabilities(
    severity: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取漏洞列表"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    scanner = get_scanner()
    vulnerabilities = scanner.get_vulnerabilities(severity)

    return {"vulnerabilities": vulnerabilities, "count": len(vulnerabilities)}


# ── 性能相关接口 ──────────────────────────────────────────────


@app.get("/api/performance/load-balancer/services")
async def list_load_balancer_services(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """列出负载均衡器服务"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    lb = get_load_balancer()
    services = lb.list_services()

    return {"services": services, "count": len(services)}


@app.post("/api/performance/load-balancer/services")
async def register_service(
    service_id: str,
    service_url: str,
    weight: int = 1,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """注册服务到负载均衡器"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    lb = get_load_balancer()
    lb.register_service(service_id, service_url, weight)

    return {"success": True, "message": "Service registered"}


@app.delete("/api/performance/load-balancer/services/{service_id}")
async def unregister_service(
    service_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """从负载均衡器注销服务"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    lb = get_load_balancer()
    lb.unregister_service(service_id)

    return {"success": True, "message": "Service unregistered"}


@app.get("/api/performance/auto-scaler/instances")
async def list_auto_scaler_instances(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """列出自动扩展器实例"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    scaler = get_auto_scaler()
    instances = scaler.list_instances()

    return {"instances": instances, "count": len(instances)}


@app.post("/api/performance/auto-scaler/scale")
async def scale_auto_scaler(
    cpu_usage: float,
    memory_usage: float,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """执行自动扩展决策"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    scaler = get_auto_scaler()
    decision = scaler.scale(cpu_usage, memory_usage)

    return {"decision": decision}


@app.get("/api/health")
def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "AI工具系统API"}


# ── 系统健康相关接口 ────────────────────────────────────────


@app.get("/api/system/health")
async def get_system_health(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取系统健康状态"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    system_status = get_system_status()
    metrics = get_system_metrics()

    return {"system_status": system_status.value, "metrics": metrics}


@app.get("/api/system/diagnostics")
async def run_system_diagnostics(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """运行系统诊断"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    diagnostics = run_diagnostics()
    return {"diagnostics": diagnostics}


@app.get("/api/system/metrics")
async def get_system_metrics_api(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取系统指标"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    metrics = get_system_metrics()
    return {"metrics": metrics}


# ── PL5 训练数据接口 ───────────────────────────────────────────


@app.get("/api/pl5/stats")
async def get_pl5_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取PL5系统训练统计数据"""
    try:
        from src.core.data.collector import PL5DataCollector
        from pathlib import Path

        collector = PL5DataCollector()

        latest_period = collector.get_latest_period()
        next_period = str(int(latest_period) + 1) if latest_period else "未知"

        df = collector.load_processed_data()
        total_records = len(df) if df is not None else 0

        model_dir = Path("models")
        model_count = (
            len(list(model_dir.glob("*.pkl"))) if model_dir.exists() else 0
        )

        eval_reports = (
            list(Path("results").glob("eval_report_*.json"))
            if Path("results").exists()
            else []
        )
        eval_reports.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        accuracy = 0.0
        hit_rate = 0.0
        if eval_reports:
            import json

            with open(eval_reports[0], "r", encoding="utf-8") as f:
                eval_data = json.load(f)
                summary = eval_data.get("summary", {})
                accuracy = summary.get("overall_accuracy", 0.0) * 100
                hit_rate = summary.get("full_match_rate", 0.0) * 100

        return {
            "accuracy": round(accuracy, 1),
            "hit_rate": round(hit_rate, 1),
            "model_count": model_count,
            "latest_period": latest_period,
            "next_period": next_period,
            "total_records": total_records,
        }
    except Exception as e:
        logger.error(f"获取PL5统计数据失败: {e}")
        return {
            "accuracy": 0.0,
            "hit_rate": 0.0,
            "model_count": 0,
            "latest_period": "未知",
            "next_period": "未知",
            "total_records": 0,
            "error": str(e),
        }


@app.get("/api/pl5/prediction")
async def get_pl5_prediction(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取PL5最新预测结果 - 使用智能多特征组合融合系统 V11 (优化缓存版)"""
    try:
        from src.core.models.multi_feature_fusion import (
            MultiFeatureFusionPredictor,
        )
        from src.core.data.collector import PL5DataCollector
        from src.core.features.engineer_v10 import (
            FeatureEngineerV10 as FeatureEngineer,
        )

        collector = PL5DataCollector()
        data = collector.load_processed_data()

        if data is None or len(data) == 0:
            raise ValueError("No data available")

        engineer = FeatureEngineer()
        df_features = engineer.extract_all_features(data, select_top=0)

        non_feature_cols = [
            "period",
            "full_number",
            "wan",
            "qian",
            "bai",
            "shi",
            "ge",
            "date",
        ]
        feature_cols = [
            col for col in df_features.columns if col not in non_feature_cols
        ]

        logger.info(
            f"[预测API] 使用智能多特征融合预测，特征数: {len(feature_cols)}"
        )

        mff_predictor = MultiFeatureFusionPredictor(max_combinations=5)
        cache_file = os.path.join(
            get_models_dir(), "multi_feature_fusion_cache.joblib"
        )
        cache_loaded = mff_predictor.load_model(cache_file)
        cache_valid = mff_predictor.is_cache_valid(
            data_periods=len(data), max_age_hours=24
        )

        if cache_loaded and cache_valid:
            logger.info("[预测API] 使用缓存模型进行快速预测")
        else:
            logger.info("[预测API] 缓存无效，重新训练模型")
            mff_predictor.fit(df_features, feature_cols, recent_periods=500)

        mff_results = mff_predictor.predict(df_features, top_k=8)

        predictions = {}
        fusion_details = {}
        for pos, result in mff_results.items():
            predictions[pos] = {"top_k": result.get("top_k", [])}
            fusion_details[pos] = result.get("combination_details", {})

        summary = mff_predictor.get_intelligent_summary()

        logger.info(
            f"[预测API] 多特征融合完成: {summary['n_combinations']} 个特征组合"
        )

        return {
            "success": True,
            "prediction_method": "multi_feature_fusion",
            "n_feature_combinations": summary["n_combinations"],
            "feature_combinations": summary["combinations"],
            "predictions": predictions,
            "cache_info": mff_predictor._cache_info,
        }
    except Exception as e:
        logger.error(f"获取PL5预测失败: {e}")
        import traceback

        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "predictions": {
                "wan": {"top_k": [0, 1, 2, 3, 4, 5, 6, 7]},
                "qian": {"top_k": [1, 2, 3, 4, 5, 6, 7, 8]},
                "bai": {"top_k": [2, 3, 4, 5, 6, 7, 8, 9]},
                "shi": {"top_k": [3, 4, 5, 6, 7, 8, 9, 0]},
                "ge": {"top_k": [4, 5, 6, 7, 8, 9, 0, 1]},
            },
        }


@app.get("/api/pl5/training-status")
async def get_pl5_training_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取PL5训练状态 - 完整日循环任务时间周期"""
    try:
        from src.core.data.collector import PL5DataCollector
        from pathlib import Path
        import json

        collector = PL5DataCollector()
        latest_period = collector.get_latest_period()

        status = training_manager.get_detailed_status()
        scheduler_status = status.get("scheduler_status", {})

        scheduler_config_file = Path("config/scheduler_config_v8.json")
        daily_cycle_tasks = []
        if scheduler_config_file.exists():
            with open(scheduler_config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                daily_cycle_tasks = [
                    {
                        "time": config.get("data_fetch_time", "22:15"),
                        "name": "数据采集",
                        "desc": "自动获取开奖数据",
                    },
                    {
                        "time": config.get("evaluation_time", "22:15"),
                        "name": "评估预测",
                        "desc": "评估预测逻辑与命中情况",
                    },
                    {
                        "time": config.get("optimization_start", "22:45"),
                        "name": "策略优化",
                        "desc": "推理逻辑策略优化学习",
                    },
                    {
                        "time": config.get("training_start", "00:30"),
                        "name": "深度训练",
                        "desc": "开始深度训练模型",
                    },
                    {
                        "time": config.get(
                            "incremental_training_morning", "08:00"
                        ),
                        "name": "增量训练(上午)",
                        "desc": "首次佐证前增量学习",
                    },
                    {
                        "time": config.get(
                            "first_prediction_verification", "10:00"
                        ),
                        "name": "佐证1",
                        "desc": "首次预测验证",
                    },
                    {
                        "time": config.get(
                            "incremental_training_noon", "12:00"
                        ),
                        "name": "增量训练(中午)",
                        "desc": "二次佐证前增量学习",
                    },
                    {
                        "time": config.get(
                            "second_prediction_verification", "13:00"
                        ),
                        "name": "佐证2",
                        "desc": "二次预测验证",
                    },
                    {
                        "time": config.get(
                            "incremental_training_afternoon", "14:00"
                        ),
                        "name": "增量训练(下午)",
                        "desc": "三次佐证前增量学习",
                    },
                    {
                        "time": config.get(
                            "third_prediction_verification", "15:00"
                        ),
                        "name": "佐证3",
                        "desc": "三次预测验证",
                    },
                    {
                        "time": config.get(
                            "deep_strategy_optimization", "16:00"
                        ),
                        "name": "深度策略优化",
                        "desc": "深度策略优化（四次佐证）",
                    },
                    {
                        "time": config.get("prediction_preview", "17:00"),
                        "name": "预测预生成",
                        "desc": "预测结果预生成（五次佐证）",
                    },
                    {
                        "time": config.get("final_prediction_time", "18:00"),
                        "name": "最终预测",
                        "desc": "生成最终预测结果",
                    },
                    {
                        "time": config.get(
                            "final_prediction_verification_time", "19:00"
                        ),
                        "name": "佐证6",
                        "desc": "验证最终预测结果",
                    },
                    {
                        "time": config.get(
                            "pre_sale_prediction_time", "20:00"
                        ),
                        "name": "售前预测",
                        "desc": "售前最终预测",
                    },
                    {
                        "time": config.get("email_send_time", "20:15"),
                        "name": "发送报告",
                        "desc": "发送训练报告和预测到邮箱",
                    },
                ]

        current_task = scheduler_status.get("current_task", "空闲")
        current_task_lower = current_task.lower()

        def get_task_status(task_name: str, desc: str) -> dict:
            task_name_lower = task_name.lower()
            if any(
                keyword in current_task_lower for keyword in ["空闲", "idle"]
            ):
                return {
                    "time": "",
                    "name": task_name,
                    "desc": desc,
                    "status": "pending",
                }

            if "采集" in task_name and (
                "data" in current_task_lower or "fetch" in current_task_lower
            ):
                return {
                    "time": "",
                    "name": task_name,
                    "desc": desc,
                    "status": "running",
                }
            if "评估" in task_name and "evaluate" in current_task_lower:
                return {
                    "time": "",
                    "name": task_name,
                    "desc": desc,
                    "status": "running",
                }
            if "优化" in task_name and "optim" in current_task_lower:
                return {
                    "time": "",
                    "name": task_name,
                    "desc": desc,
                    "status": "running",
                }
            if "训练" in task_name and (
                "train" in current_task_lower
                or "incremental" in current_task_lower
            ):
                return {
                    "time": "",
                    "name": task_name,
                    "desc": desc,
                    "status": "running",
                }
            if "佐证" in task_name or "验证" in task_name:
                if (
                    "verification" in current_task_lower
                    or "佐证" in current_task_lower
                    or "验证" in current_task_lower
                ):
                    return {
                        "time": "",
                        "name": task_name,
                        "desc": desc,
                        "status": "running",
                    }
            if "预测" in task_name and (
                "prediction" in current_task_lower
                or "predict" in current_task_lower
            ):
                return {
                    "time": "",
                    "name": task_name,
                    "desc": desc,
                    "status": "running",
                }
            if "报告" in task_name and "report" in current_task_lower:
                return {
                    "time": "",
                    "name": task_name,
                    "desc": desc,
                    "status": "running",
                }

            return {
                "time": "",
                "name": task_name,
                "desc": desc,
                "status": "pending",
            }

        training_status = [
            get_task_status(t["name"], t["desc"]) for t in daily_cycle_tasks
        ]

        return {
            "latest_period": latest_period,
            "next_period": (
                str(int(latest_period) + 1)
                if latest_period and latest_period.isdigit()
                else "未知"
            ),
            "daily_cycle": {
                "enabled": (
                    config.get("enabled", True)
                    if scheduler_config_file.exists()
                    else True
                ),
                "data_fetch_time": (
                    config.get("data_fetch_time", "22:15")
                    if scheduler_config_file.exists()
                    else "22:15"
                ),
                "training_deadline": (
                    config.get("training_deadline", "17:00")
                    if scheduler_config_file.exists()
                    else "17:00"
                ),
                "final_prediction_time": (
                    config.get("final_prediction_time", "18:00")
                    if scheduler_config_file.exists()
                    else "18:00"
                ),
            },
            "training_status": training_status,
            "training_steps_count": len(daily_cycle_tasks),
            "last_run": scheduler_status.get("last_run"),
            "next_run": scheduler_status.get("next_run"),
            "current_task": current_task,
            "learning_progress": scheduler_status.get("learning_progress", 0),
            "last_updated": status.get("last_updated"),
        }
    except Exception as e:
        logger.error(f"获取训练状态失败: {e}")
        import traceback

        traceback.print_exc()
        return {
            "latest_period": "未知",
            "next_period": "未知",
            "daily_cycle": {
                "enabled": True,
                "data_fetch_time": "22:15",
                "training_deadline": "17:00",
                "final_prediction_time": "18:00",
            },
            "training_status": [],
            "training_steps_count": 0,
            "error": str(e),
        }


@app.get("/api/pl5/daily-cycle-timeline")
async def get_pl5_daily_cycle_timeline(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取日循环任务时间线 - 完整可视化时间周期"""
    try:
        from pathlib import Path
        import json
        from datetime import datetime, time

        scheduler_config_file = Path("config/scheduler_config_v8.json")
        if not scheduler_config_file.exists():
            return {
                "success": False,
                "error": "配置文件不存在",
                "timeline": [],
            }

        with open(scheduler_config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        timeline = [
            {
                "id": 1,
                "time": config.get("data_fetch_time", "22:15"),
                "name": "数据采集",
                "type": "fetch",
                "desc": "自动获取开奖数据",
            },
            {
                "id": 2,
                "time": config.get("evaluation_time", "22:15"),
                "name": "评估预测",
                "type": "evaluate",
                "desc": "评估预测逻辑与命中情况",
            },
            {
                "id": 3,
                "time": config.get("optimization_start", "22:45"),
                "name": "策略优化",
                "type": "optimize",
                "desc": "推理逻辑策略优化学习",
            },
            {
                "id": 4,
                "time": config.get("training_start", "00:30"),
                "name": "深度训练",
                "type": "train",
                "desc": "开始深度训练模型",
                "critical": True,
            },
            {
                "id": 5,
                "time": config.get("incremental_training_morning", "08:00"),
                "name": "增量训练(上午)",
                "type": "incremental",
                "desc": "首次佐证前增量学习",
            },
            {
                "id": 6,
                "time": config.get("first_prediction_verification", "10:00"),
                "name": "佐证1",
                "type": "verify",
                "desc": "首次预测验证",
            },
            {
                "id": 7,
                "time": config.get("incremental_training_noon", "12:00"),
                "name": "增量训练(中午)",
                "type": "incremental",
                "desc": "二次佐证前增量学习",
            },
            {
                "id": 8,
                "time": config.get("second_prediction_verification", "13:00"),
                "name": "佐证2",
                "type": "verify",
                "desc": "二次预测验证",
            },
            {
                "id": 9,
                "time": config.get("incremental_training_afternoon", "14:00"),
                "name": "增量训练(下午)",
                "type": "incremental",
                "desc": "三次佐证前增量学习",
            },
            {
                "id": 10,
                "time": config.get("third_prediction_verification", "15:00"),
                "name": "佐证3",
                "type": "verify",
                "desc": "三次预测验证",
            },
            {
                "id": 11,
                "time": config.get("deep_strategy_optimization", "16:00"),
                "name": "深度策略优化",
                "type": "optimize",
                "desc": "深度策略优化（四次佐证）",
            },
            {
                "id": 12,
                "time": config.get("prediction_preview", "17:00"),
                "name": "预测预生成",
                "type": "predict",
                "desc": "预测结果预生成（五次佐证）",
            },
            {
                "id": 13,
                "time": config.get("final_prediction_time", "18:00"),
                "name": "最终预测",
                "type": "predict",
                "desc": "生成最终预测结果",
                "critical": True,
            },
            {
                "id": 14,
                "time": config.get(
                    "final_prediction_verification_time", "19:00"
                ),
                "name": "佐证6",
                "type": "verify",
                "desc": "验证最终预测结果",
            },
            {
                "id": 15,
                "time": config.get("pre_sale_prediction_time", "20:00"),
                "name": "售前预测",
                "type": "predict",
                "desc": "售前最终预测",
                "critical": True,
            },
            {
                "id": 16,
                "time": config.get("email_send_time", "20:15"),
                "name": "发送报告",
                "type": "report",
                "desc": "发送训练报告和预测到邮箱",
            },
        ]

        current_time = datetime.now().time()
        for task in timeline:
            task_hour, task_minute = map(int, task["time"].split(":"))
            task_time = time(task_hour, task_minute)
            task["passed"] = current_time > task_time

        return {
            "success": True,
            "enabled": config.get("enabled", True),
            "last_completed_period": config.get("last_completed_period"),
            "monitoring_enabled": config.get("monitoring_enabled", True),
            "training_deadline": config.get("training_deadline", "17:00"),
            "timeline": timeline,
            "total_tasks": len(timeline),
        }
    except Exception as e:
        logger.error(f"获取日循环时间线失败: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e), "timeline": []}


@app.get("/api/pl5/models")
async def get_pl5_models(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """获取PL5模型列表"""
    try:
        from pathlib import Path

        model_dir = Path("models")
        models = []

        if model_dir.exists():
            for model_file in sorted(model_dir.glob("*.pkl")):
                stat = model_file.stat()
                size_mb = stat.st_size / (1024 * 1024)
                models.append(
                    {
                        "name": model_file.stem,
                        "size_mb": round(size_mb, 2),
                        "updated": datetime.fromtimestamp(
                            stat.st_mtime
                        ).strftime("%Y-%m-%d %H:%M"),
                        "status": "ready",
                    }
                )

        return {"models": models}
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return {"models": [], "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
