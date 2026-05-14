"""ToolCalling Agent实现"""

import json
from typing import Dict, List, Any, Optional

from .base import BaseAgent
from ..ai_types import ToolResult, ConversationMessage


class ToolCallingAgent(BaseAgent):
    """工具调用专用Agent

    专注于工具调用的Agent实现，更适合结构化的工具使用场景。
    """

    def run(
        self, task: str, context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """执行任务

        Args:
            task: 任务描述
            context: 上下文信息

        Returns:
            任务执行结果
        """
        try:
            # 初始化状态
            steps = []
            current_context = context or {}
            available_tools = self.get_available_tools()

            # 构建工具信息
            tools_info = []
            for tool_name in available_tools:
                tool_info = self.get_tool_info(tool_name)
                if tool_info:
                    tools_info.append(tool_info)

            # 构建系统提示
            system_prompt = self._build_system_prompt(tools_info)

            # 构建用户提示
            user_prompt = f"Task: {task}\nContext: {json.dumps(current_context, ensure_ascii=False)}"

            # 生成工具调用计划
            response = self.llm.generate(system_prompt + "\n" + user_prompt)

            # 解析工具调用计划
            tool_calls = self._parse_tool_calls(response)

            # 执行工具调用
            results = []
            for i, tool_call in enumerate(tool_calls):
                tool_name = tool_call.get("tool")
                parameters = tool_call.get("params", {})

                if not tool_name:
                    continue

                # 执行工具
                result = self.execute_tool(tool_name, parameters)

                # 记录结果
                results.append(
                    {
                        "tool": tool_name,
                        "params": parameters,
                        "result": {
                            "success": result.success,
                            "data": result.data,
                            "error": result.error,
                        },
                    }
                )

                # 记录步骤
                steps.append(
                    {
                        "step": i + 1,
                        "tool": tool_name,
                        "params": parameters,
                        "result": result,
                    }
                )

            # 生成最终答案
            final_prompt = f"""根据以下工具执行结果，总结完成的任务：

Task: {task}

Tool Execution Results:
{json.dumps(results, ensure_ascii=False, indent=2)}

请提供简洁明了的总结。"""

            final_answer = self.llm.generate(final_prompt)

            return ToolResult(
                success=True,
                data={
                    "task": task,
                    "results": results,
                    "answer": final_answer,
                    "steps": steps,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False, error=f"Agent execution failed: {str(e)}"
            )

    def chat(
        self,
        messages: List[ConversationMessage],
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """对话模式

        Args:
            messages: 对话消息列表
            context: 上下文信息

        Returns:
            对话结果
        """
        try:
            # 提取最新的用户消息作为任务
            if not messages:
                return ToolResult(success=False, error="No messages provided")

            # 找到最后一条用户消息
            user_message = None
            for msg in reversed(messages):
                if msg.role == "user":
                    user_message = msg
                    break

            if not user_message:
                return ToolResult(success=False, error="No user message found")

            # 执行任务
            return self.run(user_message.content, context)

        except Exception as e:
            return ToolResult(
                success=False, error=f"Chat execution failed: {str(e)}"
            )

    def _build_system_prompt(self, tools_info: List[Dict]) -> str:
        """构建系统提示

        Args:
            tools_info: 工具信息列表

        Returns:
            系统提示字符串
        """
        tools_str = json.dumps(tools_info, ensure_ascii=False, indent=2)

        return f"""你是一个工具调用专家，需要根据用户的任务选择合适的工具并生成工具调用计划。

可用工具：
{tools_str}

请根据用户的任务，生成一个工具调用计划。计划应该是一个JSON数组，每个元素包含：
- tool: 工具名称
- params: 工具参数（JSON对象）

示例：

Task: 计算123 + 456，然后搜索相关信息

[
  {
    "tool": "calculator",
    "params": {"expression": "123 + 456"}
  },
  {
    "tool": "search",
    "params": {"query": "123 + 456 数学运算", "max_results": 3}
  }
]

请只返回JSON数组，不要包含其他内容。"""

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """解析工具调用计划

        Args:
            response: LLM生成的响应

        Returns:
            工具调用计划列表
        """
        try:
            # 提取JSON部分
            if "[" in response and "]" in response:
                json_str = response[
                    response.find("[") : response.rfind("]") + 1
                ]
                return json.loads(json_str)
            else:
                # 尝试直接解析
                return json.loads(response)
        except json.JSONDecodeError:
            # 如果解析失败，返回空列表
            return []


# 注册到Agent工厂
from .base import AgentFactory
from ..ai_types import AgentType

AgentFactory.register(AgentType.TOOL_CALLING, ToolCallingAgent)
