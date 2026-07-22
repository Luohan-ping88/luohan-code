"""内置工具"""

import subprocess
import os
import ast
import operator
from typing import Dict, Any, List

from .base import BaseTool
from ..ai_types import ToolResult, ToolCategory, ToolParameter


# 【安全修复】支持的安全二元运算符映射
_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

# 【安全修复】支持的安全一元运算符映射
_SAFE_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# 【安全修复】兼容 Python < 3.8 的 ast.Num（3.8+ 统一为 ast.Constant，3.12+ 已移除 ast.Num）
_AST_NUM = getattr(ast, 'Num', None)


def _safe_eval_arithmetic(expression: str):
    """【安全修复】基于 AST 的安全算术表达式求值

    替代危险的 eval()，仅允许数字常量与基本算术运算
    （+、-、*、/、%、**、// 及一元正负号），拒绝任何
    名称、属性访问、调用等可执行代码。

    Args:
        expression: 数学表达式字符串

    Returns:
        求值结果（int 或 float）

    Raises:
        ValueError: 表达式包含不支持的语法节点
        SyntaxError: 表达式语法错误
        ZeroDivisionError: 除零错误
    """
    node = ast.parse(expression, mode='eval')
    return _safe_eval_node(node.body)


def _safe_eval_node(node):
    """递归求值 AST 节点"""
    # 数字常量（Python 3.8+ 使用 ast.Constant）
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"仅支持数字常量，不支持: {type(node.value).__name__}")
    # 兼容 Python < 3.8 的 ast.Num
    if _AST_NUM is not None and isinstance(node, _AST_NUM):
        return node.n
    # 二元运算
    if isinstance(node, ast.BinOp):
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        op_type = type(node.op)
        if op_type in _SAFE_BINOPS:
            return _SAFE_BINOPS[op_type](left, right)
        raise ValueError(f"不支持的运算符: {op_type.__name__}")
    # 一元运算（正负号）
    if isinstance(node, ast.UnaryOp):
        operand = _safe_eval_node(node.operand)
        op_type = type(node.op)
        if op_type in _SAFE_UNARYOPS:
            return _SAFE_UNARYOPS[op_type](operand)
        raise ValueError(f"不支持的一元运算符: {op_type.__name__}")
    raise ValueError(f"不支持的表达式类型: {type(node).__name__}")


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
            
            # 计算结果（【安全修复】使用基于 AST 的安全求值替代危险的 eval()）
            result = _safe_eval_arithmetic(expression)
            
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
