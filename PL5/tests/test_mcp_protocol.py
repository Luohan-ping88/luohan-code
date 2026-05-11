#!/usr/bin/env python
"""
MCP协议层测试脚本
"""

import asyncio
from src.core.mcp.tool_registry import mcp_registry


async def test_mcp_protocol():
    """测试MCP协议层"""
    print("开始测试MCP协议层...")

    # 1. 列出所有可用工具
    print("\n1. 列出所有可用工具:")
    tools = mcp_registry.list_tools()
    for tool in tools:
        print(f"  - {tool}")

    # 2. 获取工具模式
    print("\n2. 获取工具模式:")
    schema = mcp_registry.get_tool_schema()
    for tool_schema in schema.get("tools", []):
        print(f"  - {tool_schema['name']}: {tool_schema['description']}")

    # 3. 测试数据采集工具
    print("\n3. 测试数据采集工具:")
    result = await mcp_registry.execute_tool("collect_data", {})
    print(f"  结果: {result}")

    print("\nMCP协议层测试完成！")


if __name__ == "__main__":
    asyncio.run(test_mcp_protocol())
