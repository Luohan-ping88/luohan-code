"""工具注册表

管理和注册工具的核心组件。
"""

from typing import Dict, Type, List, Optional
from .base import BaseTool
from ..ai_types import ToolInfo, ToolCategory


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, Type[BaseTool]] = {}
        self._tools_by_category: Dict[ToolCategory, List[str]] = {}

    def register(self, tool_class: Type[BaseTool]) -> None:
        """注册工具

        Args:
            tool_class: 工具类
        """
        tool_name = tool_class.name
        if tool_name in self._tools:
            raise ValueError(f"Tool with name '{tool_name}' already registered")

        self._tools[tool_name] = tool_class

        # 按分类组织工具
        category = tool_class.category
        if category not in self._tools_by_category:
            self._tools_by_category[category] = []
        self._tools_by_category[category].append(tool_name)

    def unregister(self, tool_name: str) -> None:
        """注销工具

        Args:
            tool_name: 工具名称
        """
        if tool_name not in self._tools:
            raise ValueError(f"Tool with name '{tool_name}' not found")

        tool_class = self._tools[tool_name]
        category = tool_class.category

        del self._tools[tool_name]

        # 从分类中移除
        if category in self._tools_by_category:
            if tool_name in self._tools_by_category[category]:
                self._tools_by_category[category].remove(tool_name)

    def get_tool(self, tool_name: str) -> Type[BaseTool]:
        """获取工具类

        Args:
            tool_name: 工具名称

        Returns:
            工具类
        """
        if tool_name not in self._tools:
            raise ValueError(f"Tool with name '{tool_name}' not found")
        return self._tools[tool_name]

    def get_tool_instance(self, tool_name: str) -> BaseTool:
        """获取工具实例

        Args:
            tool_name: 工具名称

        Returns:
            工具实例
        """
        tool_class = self.get_tool(tool_name)
        return tool_class()

    def list_tools(self) -> List[str]:
        """列出所有工具名称

        Returns:
            工具名称列表
        """
        return list(self._tools.keys())

    def list_tools_by_category(self, category: ToolCategory) -> List[str]:
        """按分类列出工具

        Args:
            category: 工具分类

        Returns:
            工具名称列表
        """
        return self._tools_by_category.get(category, [])

    def get_tool_info(self, tool_name: str) -> ToolInfo:
        """获取工具信息

        Args:
            tool_name: 工具名称

        Returns:
            工具信息
        """
        tool_class = self.get_tool(tool_name)
        return tool_class.get_tool_class_info()

    def get_all_tool_info(self) -> List[ToolInfo]:
        """获取所有工具信息

        Returns:
            工具信息列表
        """
        return [tool_class.get_tool_class_info() for tool_class in self._tools.values()]


# 全局工具注册表实例
tool_registry = ToolRegistry()


# 工具注册装饰器
def register_tool(tool_class: Type[BaseTool]) -> Type[BaseTool]:
    """工具注册装饰器

    Args:
        tool_class: 工具类

    Returns:
        工具类
    """
    tool_registry.register(tool_class)
    return tool_class
