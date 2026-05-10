"""
PL5 工具系统 - 统一工具基础设施 (V10.0)

模块结构:
- base:              核心基类、结果格式、上下文、注册表
- infrastructure:    Layer 1 - 基础设施工具（数据加载/缓存/配置/日志/验证）
- core_tools:        Layer 2 - 核心能力工具（预测/特征/诊断/评估/优化）
- application_tools:  Layer 3 - 应用层工具（报告/快速预测/回测/对比/告警/导出）
- orchestrator:      工作流编排引擎与内置模板
- async_support:     异步与并发支持（AsyncToolMixin/ConcurrencyManager/BatchExecutor）
- api_layer:         REST API 服务层（FastAPI 模式 / 轻量级降级模式）
"""

from .base import (
    ToolLayer,
    ErrorInfo,
    ToolResult,
    ToolContext,
    BaseTool,
    ToolRegistry,
    register_tool,
    get_registry,
    reset_registry,
)

# 导入各层工具模块以确保注册
from . import infrastructure
from . import core_tools
from . import application_tools
from . import orchestrator
from . import async_support
from . import api_layer

__all__ = [
    "ToolLayer",
    "ErrorInfo",
    "ToolResult",
    "ToolContext",
    "BaseTool",
    "ToolRegistry",
    "register_tool",
    "get_registry",
    "reset_registry",
    "infrastructure",
    "core_tools",
    "application_tools",
    "orchestrator",
    "async_support",
    "api_layer",
]

__version__ = "V10.0"
