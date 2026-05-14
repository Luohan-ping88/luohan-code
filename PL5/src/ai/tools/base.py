"""工具层基础接口"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

from ..ai_types import ToolInfo, ToolResult, ToolCategory


class BaseTool(ABC):
    """工具抽象基类"""

    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.CUSTOM
    tags: List[str] = []
    parameters: List = []
    version: str = "1.0.0"

    def __init__(self):
        """初始化工具"""
        # 转换参数列表为ToolParameter对象
        tool_parameters = []
        from ..ai_types import ToolParameter

        for param in self.parameters:
            if isinstance(param, dict):
                tool_parameters.append(ToolParameter(**param))
            else:
                tool_parameters.append(param)

        self.tool_info = ToolInfo(
            name=self.name,
            description=self.description,
            parameters=tool_parameters,
            category=self.category,
            tags=self.tags,
            version=self.version,
        )

    @abstractmethod
    def run(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行工具

        Args:
            parameters: 工具参数

        Returns:
            工具执行结果
        """

    def get_info(self) -> ToolInfo:
        """获取工具信息

        Returns:
            工具信息
        """
        return self.tool_info

    def validate_parameters(
        self, parameters: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """验证参数

        Args:
            parameters: 工具参数

        Returns:
            (是否有效, 错误信息)
        """
        # 检查必填参数
        for param in self.tool_info.parameters:
            if param.required and param.name not in parameters:
                return False, f"Missing required parameter: {param.name}"

        # 检查参数类型
        for param in self.tool_info.parameters:
            if param.name in parameters:
                value = parameters[param.name]
                if param.type == "str" and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                elif param.type == "int" and not isinstance(value, int):
                    return False, f"Parameter {param.name} must be an integer"
                elif param.type == "float" and not isinstance(
                    value, (int, float)
                ):
                    return False, f"Parameter {param.name} must be a number"
                elif param.type == "bool" and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"
                elif param.type == "list" and not isinstance(value, list):
                    return False, f"Parameter {param.name} must be a list"
                elif param.type == "dict" and not isinstance(value, dict):
                    return (
                        False,
                        f"Parameter {param.name} must be a dictionary",
                    )

        return True, None

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行工具（带参数验证）

        Args:
            parameters: 工具参数

        Returns:
            工具执行结果
        """
        # 验证参数
        valid, error = self.validate_parameters(parameters)
        if not valid:
            return ToolResult(success=False, error=error)

        # 执行工具
        try:
            return self.run(parameters)
        except Exception as e:
            return ToolResult(
                success=False, error=f"Tool execution failed: {str(e)}"
            )

    @classmethod
    def get_tool_class_info(cls) -> ToolInfo:
        """获取工具类信息

        Returns:
            工具信息
        """
        # 转换参数列表为ToolParameter对象
        tool_parameters = []
        from ..ai_types import ToolParameter

        for param in cls.parameters:
            if isinstance(param, dict):
                tool_parameters.append(ToolParameter(**param))
            else:
                tool_parameters.append(param)

        return ToolInfo(
            name=cls.name,
            description=cls.description,
            parameters=tool_parameters,
            category=cls.category,
            tags=cls.tags,
            version=cls.version,
        )
