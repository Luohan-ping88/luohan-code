"""内置工具"""

import subprocess
import os
from typing import Dict, Any, List

from .base import BaseTool
from ..ai_types import ToolResult, ToolCategory, ToolParameter


class SearchTool(BaseTool):
    """搜索工具
    
    使用系统命令进行简单搜索，实际应用中可以集成更强大的搜索引擎。
    """
    name = "search"
    description = "在互联网上搜索信息"
    category = ToolCategory.BUILTIN
    tags = ["search", "web"]
    parameters = [
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
    
    def run(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行搜索"""
        query = parameters.get("query")
        max_results = parameters.get("max_results", 5)
        
        try:
            # 这里使用一个简单的模拟实现
            # 实际应用中可以集成Google Search API或其他搜索引擎
            results = [
                f"搜索结果 {i+1}: 关于 '{query}' 的信息"
                for i in range(max_results)
            ]
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "total": len(results)
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"搜索失败: {str(e)}"
            )


class CalculatorTool(BaseTool):
    """计算工具
    
    执行数学计算。
    """
    name = "calculator"
    description = "执行数学计算"
    category = ToolCategory.BUILTIN
    tags = ["calculator", "math"]
    parameters = [
        ToolParameter(
            name="expression",
            type="str",
            description="数学表达式",
            required=True
        )
    ]
    
    def run(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行计算"""
        expression = parameters.get("expression")
        
        try:
            # 安全的计算方式
            # 只允许基本的数学运算
            allowed_chars = "0123456789.+-*/() "
            for char in expression:
                if char not in allowed_chars:
                    return ToolResult(
                        success=False,
                        error="表达式包含不允许的字符"
                    )
            
            # 计算结果
            result = eval(expression)
            
            return ToolResult(
                success=True,
                data={
                    "expression": expression,
                    "result": result
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"计算失败: {str(e)}"
            )


class FileTool(BaseTool):
    """文件工具
    
    处理文件操作，如读取、写入文件。
    """
    name = "file"
    description = "文件操作工具"
    category = ToolCategory.BUILTIN
    tags = ["file", "io"]
    parameters = [
        ToolParameter(
            name="action",
            type="str",
            description="操作类型: read, write, list",
            required=True,
            enum=["read", "write", "list"]
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
    
    def run(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行文件操作"""
        action = parameters.get("action")
        path = parameters.get("path")
        content = parameters.get("content")
        max_lines = parameters.get("max_lines", 100)
        
        try:
            if action == "read":
                # 读取文件
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:max_lines]
                    file_content = ''.join(lines)
                
                return ToolResult(
                    success=True,
                    data={
                        "path": path,
                        "content": file_content,
                        "lines": len(lines)
                    }
                )
            
            elif action == "write":
                # 写入文件
                if content is None:
                    return ToolResult(
                        success=False,
                        error="Write operation requires content parameter"
                    )
                
                # 确保目录存在
                os.makedirs(os.path.dirname(path), exist_ok=True)
                
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                return ToolResult(
                    success=True,
                    data={
                        "path": path,
                        "written": True
                    }
                )
            
            elif action == "list":
                # 列出目录内容
                if os.path.isdir(path):
                    files = os.listdir(path)
                    return ToolResult(
                        success=True,
                        data={
                            "path": path,
                            "files": files,
                            "count": len(files)
                        }
                    )
                else:
                    return ToolResult(
                        success=False,
                        error="Path is not a directory"
                    )
            
            else:
                return ToolResult(
                    success=False,
                    error="Invalid action. Must be one of: read, write, list"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"文件操作失败: {str(e)}"
            )
