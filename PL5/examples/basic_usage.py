"""基本工具调用示例

展示如何使用AI工具系统的基本功能。
"""

from src.ai.registry import get_registry, register_tool
from src.ai.tools.builtin import SearchTool, CalculatorTool, FileTool
from src.ai.types import ToolParameter


# 注册内置工具
def register_builtin_tools():
    """注册内置工具"""
    # 注册搜索工具
    @register_tool(
        name="search",
        description="在互联网上搜索信息",
        parameters=[
            ToolParameter(
                name="query",
                type="str",
                description="搜索查询词",
                required=True
            ),
            ToolParameter(
                name="max_results",
                type="int",
                description="最大结果数量",
                required=False,
                default=5
            )
        ]
    )
    def search_tool(params):
        tool = SearchTool()
        return tool.execute(params)
    
    # 注册计算器工具
    @register_tool(
        name="calculator",
        description="执行数学计算",
        parameters=[
            ToolParameter(
                name="expression",
                type="str",
                description="数学表达式",
                required=True
            )
        ]
    )
    def calculator_tool(params):
        tool = CalculatorTool()
        return tool.execute(params)
    
    # 注册文件工具
    @register_tool(
        name="file",
        description="文件操作工具",
        parameters=[
            ToolParameter(
                name="action",
                type="str",
                description="操作类型: read, write, list",
                required=True
            ),
            ToolParameter(
                name="path",
                type="str",
                description="文件路径",
                required=True
            ),
            ToolParameter(
                name="content",
                type="str",
                description="文件内容（仅write操作需要）",
                required=False
            ),
            ToolParameter(
                name="max_lines",
                type="int",
                description="最大读取行数（仅read操作需要）",
                required=False,
                default=100
            )
        ]
    )
    def file_tool(params):
        tool = FileTool()
        return tool.execute(params)


# 示例1：使用计算器工具
def example_calculator():
    """使用计算器工具"""
    print("=== 示例1: 使用计算器工具 ===")
    registry = get_registry()
    
    # 执行计算
    result = registry.execute_tool(
        "calculator",
        {"expression": "123 + 456 * 2"}
    )
    
    print(f"计算结果: {result.data}")
    print(f"执行成功: {result.success}")
    print()


# 示例2：使用搜索工具
def example_search():
    """使用搜索工具"""
    print("=== 示例2: 使用搜索工具 ===")
    registry = get_registry()
    
    # 执行搜索
    result = registry.execute_tool(
        "search",
        {"query": "AI大模型工具系统", "max_results": 3}
    )
    
    print(f"搜索查询: {result.data['query']}")
    print(f"搜索结果: {result.data['results']}")
    print(f"结果数量: {result.data['total']}")
    print()


# 示例3：使用文件工具
def example_file():
    """使用文件工具"""
    print("=== 示例3: 使用文件工具 ===")
    registry = get_registry()
    
    # 写入文件
    write_result = registry.execute_tool(
        "file",
        {
            "action": "write",
            "path": "test.txt",
            "content": "Hello, AI工具系统!\n这是一个测试文件。"
        }
    )
    print(f"写入文件成功: {write_result.success}")
    
    # 读取文件
    read_result = registry.execute_tool(
        "file",
        {
            "action": "read",
            "path": "test.txt"
        }
    )
    print(f"读取文件成功: {read_result.success}")
    print(f"文件内容: {read_result.data['content']}")
    
    # 列出目录
    list_result = registry.execute_tool(
        "file",
        {
            "action": "list",
            "path": "."
        }
    )
    print(f"列出目录成功: {list_result.success}")
    print(f"目录内容: {list_result.data['files']}")
    print()


# 示例4：列出所有可用工具
def example_list_tools():
    """列出所有可用工具"""
    print("=== 示例4: 列出所有可用工具 ===")
    registry = get_registry()
    
    tools = registry.list_tools()
    print(f"可用工具数量: {len(tools)}")
    print("可用工具:")
    for tool_name in tools:
        tool_info = registry.get_tool_info(tool_name)
        print(f"  - {tool_name}: {tool_info.description}")
    print()


if __name__ == "__main__":
    # 注册内置工具
    register_builtin_tools()
    
    # 运行示例
    example_calculator()
    example_search()
    example_file()
    example_list_tools()
    
    print("基本工具调用示例完成！")
