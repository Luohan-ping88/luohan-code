"""计算工具实现"""

from typing import Dict, Any, List
import math
import statistics

from .base import BaseTool
from .registry import register_tool
from ..ai_types import ToolResult, ToolCategory


@register_tool
class CalculatorTool(BaseTool):
    """计算工具

    支持数学计算和数据处理。
    """

    name = "calculator"
    description = "执行数学计算和数据处理"
    category = ToolCategory.BUILTIN
    tags = ["calculator", "math"]
    parameters = [
        {"name": "expression", "type": "str", "description": "数学表达式", "required": False, "example": "2 + 2 * 3"},
        {"name": "data", "type": "list", "description": "数据数组", "required": False, "example": [1, 2, 3, 4, 5]},
        {
            "name": "operation",
            "type": "str",
            "description": "操作类型",
            "required": True,
            "enum": ["evaluate", "sum", "mean", "median", "mode", "std", "var", "min", "max"],
            "example": "evaluate",
        },
    ]

    def run(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行计算

        Args:
            parameters: 工具参数

        Returns:
            计算结果
        """
        operation = parameters.get("operation")
        expression = parameters.get("expression")
        data = parameters.get("data")

        try:
            if operation == "evaluate":
                result = self._evaluate_expression(expression)
            elif operation == "sum":
                result = self._calculate_sum(data)
            elif operation == "mean":
                result = self._calculate_mean(data)
            elif operation == "median":
                result = self._calculate_median(data)
            elif operation == "mode":
                result = self._calculate_mode(data)
            elif operation == "std":
                result = self._calculate_std(data)
            elif operation == "var":
                result = self._calculate_var(data)
            elif operation == "min":
                result = self._calculate_min(data)
            elif operation == "max":
                result = self._calculate_max(data)
            else:
                return ToolResult(success=False, error=f"不支持的操作: {operation}")

            return ToolResult(success=True, data={"result": result, "operation": operation})
        except Exception as e:
            return ToolResult(success=False, error=f"计算执行失败: {str(e)}")

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行计算

        Args:
            parameters: 工具参数

        Returns:
            计算结果
        """
        return super().execute(parameters)

    def _evaluate_expression(self, expression: str) -> float:
        """计算数学表达式

        Args:
            expression: 数学表达式

        Returns:
            计算结果
        """
        # 安全计算数学表达式
        # 限制可用的函数和变量
        allowed_globals = {
            "math": math,
            "abs": abs,
            "pow": pow,
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "exp": math.exp,
        }

        try:
            result = eval(expression, allowed_globals, {})
            return float(result)
        except Exception as e:
            raise ValueError(f"无效的数学表达式: {str(e)}")

    def _calculate_sum(self, data: List[float]) -> float:
        """计算总和

        Args:
            data: 数据数组

        Returns:
            总和
        """
        if not data:
            raise ValueError("数据数组为空")
        return sum(data)

    def _calculate_mean(self, data: List[float]) -> float:
        """计算均值

        Args:
            data: 数据数组

        Returns:
            均值
        """
        if not data:
            raise ValueError("数据数组为空")
        return statistics.mean(data)

    def _calculate_median(self, data: List[float]) -> float:
        """计算中位数

        Args:
            data: 数据数组

        Returns:
            中位数
        """
        if not data:
            raise ValueError("数据数组为空")
        return statistics.median(data)

    def _calculate_mode(self, data: List[float]) -> List[float]:
        """计算众数

        Args:
            data: 数据数组

        Returns:
            众数列表
        """
        if not data:
            raise ValueError("数据数组为空")
        try:
            mode = statistics.mode(data)
            return [mode]
        except statistics.StatisticsError:
            # 处理多众数情况
            from collections import Counter

            counts = Counter(data)
            max_count = max(counts.values())
            return [k for k, v in counts.items() if v == max_count]

    def _calculate_std(self, data: List[float]) -> float:
        """计算标准差

        Args:
            data: 数据数组

        Returns:
            标准差
        """
        if not data:
            raise ValueError("数据数组为空")
        return statistics.stdev(data)

    def _calculate_var(self, data: List[float]) -> float:
        """计算方差

        Args:
            data: 数据数组

        Returns:
            方差
        """
        if not data:
            raise ValueError("数据数组为空")
        return statistics.variance(data)

    def _calculate_min(self, data: List[float]) -> float:
        """计算最小值

        Args:
            data: 数据数组

        Returns:
            最小值
        """
        if not data:
            raise ValueError("数据数组为空")
        return min(data)

    def _calculate_max(self, data: List[float]) -> float:
        """计算最大值

        Args:
            data: 数据数组

        Returns:
            最大值
        """
        if not data:
            raise ValueError("数据数组为空")
        return max(data)
