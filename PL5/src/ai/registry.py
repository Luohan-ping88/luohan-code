"""工具注册中心

管理所有工具的注册、发现和调用。
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
import threading

from .ai_types import ToolInfo, ToolCategory, ToolResult


class ToolRegistry:
    """工具注册中心单例"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tools = {}
                    cls._tools_by_category = {}
                    cls._tools_by_tag = {}
        return cls._instance

    def register(self, tool_info: ToolInfo, tool_function: Callable) -> None:
        """注册工具

        Args:
            tool_info: 工具信息
            tool_function: 工具执行函数
        """
        self._tools[tool_info.name] = {"info": tool_info, "function": tool_function}

        # 按分类索引
        if tool_info.category not in self._tools_by_category:
            self._tools_by_category[tool_info.category] = []
        self._tools_by_category[tool_info.category].append(tool_info.name)

        # 按标签索引
        for tag in tool_info.tags:
            if tag not in self._tools_by_tag:
                self._tools_by_tag[tag] = []
            self._tools_by_tag[tag].append(tool_info.name)

    def get_tool(self, name: str) -> Optional[Callable]:
        """获取工具函数

        Args:
            name: 工具名称

        Returns:
            工具执行函数，如果工具不存在返回None
        """
        tool_data = self._tools.get(name)
        if tool_data:
            return tool_data["function"]
        return None

    def get_tool_info(self, name: str) -> Optional[ToolInfo]:
        """获取工具信息

        Args:
            name: 工具名称

        Returns:
            工具信息，如果工具不存在返回None
        """
        tool_data = self._tools.get(name)
        if tool_data:
            return tool_data["info"]
        return None

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

    def search_tools(self, tags: List[str]) -> List[str]:
        """按标签搜索工具

        Args:
            tags: 标签列表

        Returns:
            工具名称列表
        """
        if not tags:
            return self.list_tools()

        # 找出包含所有标签的工具
        matched_tools = set()
        for tag in tags:
            tag_tools = set(self._tools_by_tag.get(tag, []))
            if not matched_tools:
                matched_tools = tag_tools
            else:
                matched_tools.intersection_update(tag_tools)

        return list(matched_tools)

    def execute_tool(self, name: str, parameters: Dict) -> ToolResult:
        """执行工具

        Args:
            name: 工具名称
            parameters: 工具参数

        Returns:
            工具执行结果
        """
        tool_function = self.get_tool(name)
        if not tool_function:
            return ToolResult(success=False, error=f"Tool '{name}' not found")

        try:
            result = tool_function(parameters)
            if not isinstance(result, ToolResult):
                return ToolResult(success=False, error=f"Tool '{name}' returned invalid result type")
            return result
        except Exception as e:
            return ToolResult(success=False, error=f"Tool '{name}' execution failed: {str(e)}")

    def get_stats(self) -> Dict:
        """获取注册表统计信息

        Returns:
            统计信息
        """
        stats = {"total_tools": len(self._tools), "tools_by_category": {}, "tools_by_tag": {}}

        for category, tools in self._tools_by_category.items():
            stats["tools_by_category"][category.value] = len(tools)

        for tag, tools in self._tools_by_tag.items():
            stats["tools_by_tag"][tag] = len(tools)

        return stats

    def clear(self) -> None:
        """清空注册表"""
        self._tools = {}
        self._tools_by_category = {}
        self._tools_by_tag = {}


def get_registry() -> ToolRegistry:
    """获取工具注册中心单例

    Returns:
        ToolRegistry实例
    """
    return ToolRegistry()


def reset_registry() -> None:
    """重置工具注册中心"""
    registry = ToolRegistry()
    registry.clear()


def register_tool(
    name: str, description: str, parameters: List, category: ToolCategory = ToolCategory.CUSTOM, tags: List[str] = None
) -> Callable:
    """工具注册装饰器

    Args:
        name: 工具名称
        description: 工具描述
        parameters: 参数列表
        category: 工具分类（支持字符串或ToolCategory枚举）
        tags: 标签列表

    Returns:
        装饰器函数
    """
    from .ai_types import ToolParameter

    if tags is None:
        tags = []

    # 转换category为ToolCategory枚举
    if isinstance(category, str):
        try:
            category = ToolCategory(category)
        except ValueError:
            category = ToolCategory.CUSTOM

    # 转换参数列表
    tool_parameters = []
    for param in parameters:
        if isinstance(param, ToolParameter):
            tool_parameters.append(param)
        else:
            # 支持字典格式
            tool_parameters.append(ToolParameter(**param))

    tool_info = ToolInfo(name=name, description=description, parameters=tool_parameters, category=category, tags=tags)

    def decorator(func):
        registry = get_registry()
        registry.register(tool_info, func)
        return func

    return decorator
