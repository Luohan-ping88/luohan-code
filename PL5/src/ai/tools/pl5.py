"""PL5工具系统适配器

将现有的PL5工具系统集成到AI工具系统中。
"""

import sys
import os
from typing import Dict, Any, List, Optional

# 添加PL5工具系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from .base import BaseTool
from ..ai_types import ToolResult, ToolCategory, ToolParameter

# 尝试导入PL5工具系统
PL5_AVAILABLE = False
try:
    from tools.base import ToolRegistry as PL5ToolRegistry, BaseTool as PL5BaseTool, ToolContext

    PL5_AVAILABLE = True
except ImportError:
    pass


class PL5ToolAdapter(BaseTool):
    """PL5工具适配器

    将PL5现有的工具系统集成到AI工具系统中。
    """

    name = "pl5_tool"
    description = "调用PL5系统的工具"
    layer = "application"
    tags = ["pl5", "prediction"]
    input_schema = {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string", "description": "PL5工具名称", "example": "predict"},
            "parameters": {"type": "object", "description": "工具参数", "example": {}},
        },
        "required": ["tool_name", "parameters"],
    }

    def __init__(self):
        super().__init__()
        self.pl5_registry = None
        if PL5_AVAILABLE:
            self.pl5_registry = PL5ToolRegistry()

    def run(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行PL5工具

        Args:
            parameters: 工具参数

        Returns:
            工具执行结果
        """
        tool_name = parameters.get("tool_name")
        tool_params = parameters.get("parameters", {})

        if not PL5_AVAILABLE:
            return ToolResult(success=False, error="PL5 tool system is not available")

        try:
            # 获取PL5工具
            tool_class = self.pl5_registry.get(tool_name)
            if not tool_class:
                return ToolResult(success=False, error=f"PL5 tool '{tool_name}' not found")

            # 创建工具实例
            tool = tool_class()

            # 执行工具
            pl5_result = tool.run_safe(ToolContext(), **tool_params)

            # 转换结果格式
            result = ToolResult(success=pl5_result.success, data=pl5_result.data, metadata=pl5_result.metadata)

            return result
        except Exception as e:
            return ToolResult(success=False, error=f"PL5 tool execution failed: {str(e)}")

    def execute(self, ctx, **kwargs) -> ToolResult:
        """执行PL5工具

        Args:
            ctx: 工具执行上下文
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        return self.run(kwargs)

    def list_pl5_tools(self) -> List[str]:
        """列出所有可用的PL5工具

        Returns:
            PL5工具名称列表
        """
        if not PL5_AVAILABLE:
            return []

        try:
            return list(self.pl5_registry.list_all().keys())
        except Exception:
            return []

    def get_pl5_tool_info(self, tool_name: str) -> Optional[Dict]:
        """获取PL5工具信息

        Args:
            tool_name: 工具名称

        Returns:
            工具信息
        """
        if not PL5_AVAILABLE:
            return None

        try:
            tool_class = self.pl5_registry.get(tool_name)
            if not tool_class:
                return None

            tool = tool_class()
            return tool.get_info()
        except Exception:
            return None


def register_pl5_tools():
    """注册所有PL5工具到AI工具系统

    将PL5工具系统中的所有工具注册为AI工具系统的工具。
    """
    from ..registry import get_registry, register_tool

    if not PL5_AVAILABLE:
        return

    registry = get_registry()
    pl5_registry = PL5ToolRegistry()

    for tool_name, tool_class in pl5_registry.list_all().items():
        # 创建工具实例获取信息
        tool = tool_class()
        tool_info = tool.get_info()

        # 构建参数列表
        parameters = []
        if tool_info.get("input_schema"):
            schema = tool_info["input_schema"]
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            for param_name, param_schema in properties.items():
                param = ToolParameter(
                    name=param_name,
                    type=param_schema.get("type", "string"),
                    description=param_schema.get("description", ""),
                    required=param_name in required,
                    default=param_schema.get("default"),
                )
                parameters.append(param)
        else:
            # 默认参数
            parameters = [ToolParameter(name="params", type="dict", description="工具参数", required=True)]

        # 创建包装函数
        def create_wrapper(pl5_tool_name):
            def wrapper(parameters):
                adapter = PL5ToolAdapter()
                return adapter.run({"tool_name": pl5_tool_name, "parameters": parameters})

            return wrapper

        # 注册工具
        wrapper_func = create_wrapper(tool_name)
        register_tool(
            name=f"pl5_{tool_name}",
            description=tool_info.get("description", ""),
            parameters=parameters,
            category=ToolCategory.PL5,
            tags=tool_info.get("tags", []) + ["pl5"],
        )(wrapper_func)
