"""ReAct Agent实现"""

import json
from typing import Dict, List, Any, Optional

from .base import BaseAgent
from ..ai_types import ToolResult, ConversationMessage


class ReactAgent(BaseAgent):
    """ReAct模式的Agent

    结合推理(Reasoning)和行动(Action)的Agent实现。
    按照Think → Act → Observe的循环进行工作。
    """

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> ToolResult:
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

            # 构建系统提示
            system_prompt = self._build_system_prompt(available_tools)

            # 构建用户提示
            user_prompt = f"Task: {task}\nContext: {json.dumps(current_context, ensure_ascii=False)}"

            # 执行ReAct循环
            for step in range(self.max_steps):
                # 构建完整提示
                prompt = system_prompt + "\n" + user_prompt

                # 生成思考和行动
                response = self.llm.generate(prompt)

                # 解析响应
                thought, action, action_input = self._parse_response(response)

                # 记录步骤
                steps.append({"step": step + 1, "thought": thought, "action": action, "action_input": action_input})

                # 检查是否完成
                if action == "finish":
                    return ToolResult(success=True, data={"task": task, "result": action_input, "steps": steps})

                # 执行工具
                if action in available_tools:
                    result = self.execute_tool(action, action_input)

                    # 记录观察结果
                    steps[-1]["observation"] = {"success": result.success, "data": result.data, "error": result.error}

                    # 更新用户提示
                    user_prompt += f"\n\nThought: {thought}\nAction: {action}\nAction Input: {json.dumps(action_input, ensure_ascii=False)}\nObservation: {json.dumps(steps[-1]['observation'], ensure_ascii=False)}"
                else:
                    # 工具不存在
                    user_prompt += f"\n\nThought: {thought}\nAction: {action}\nAction Input: {json.dumps(action_input, ensure_ascii=False)}\nObservation: Tool '{action}' not found"

            # 达到最大步骤数
            return ToolResult(success=False, error="Max steps reached", data={"steps": steps})

        except Exception as e:
            return ToolResult(success=False, error=f"Agent execution failed: {str(e)}")

    def chat(self, messages: List[ConversationMessage], context: Optional[Dict[str, Any]] = None) -> ToolResult:
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
            return ToolResult(success=False, error=f"Chat execution failed: {str(e)}")

    def _build_system_prompt(self, available_tools: List[str]) -> str:
        """构建系统提示

        Args:
            available_tools: 可用工具列表

        Returns:
            系统提示字符串
        """
        tool_descriptions = []
        for tool_name in available_tools:
            tool_info = self.get_tool_info(tool_name)
            if tool_info:
                tool_descriptions.append(f"- {tool_name}: {tool_info['description']}")

        tools_str = "\n".join(tool_descriptions)

        return f"""你是一个ReAct模式的AI助手，需要通过思考和行动来完成任务。

可用工具：
{tools_str}

请按照以下格式进行思考和行动：

Thought: [你的思考过程]
Action: [工具名称或finish]
Action Input: [工具参数（JSON格式）或最终答案]

如果任务完成，请使用finish动作返回最终结果。

示例：

Task: 计算123 + 456

Thought: 我需要使用计算器工具来计算123 + 456
Action: calculator
Action Input: {"expression": "123 + 456"}

Observation: {"success": true, "data": {"expression": "123 + 456", "result": 579}, "error": null}

Thought: 计算完成，结果是579
Action: finish
Action Input: 579"""

    def _parse_response(self, response: str) -> tuple[str, str, Dict[str, Any]]:
        """解析LLM响应

        Args:
            response: LLM生成的响应

        Returns:
            (思考, 行动, 行动输入)
        """
        lines = response.strip().split("\n")
        thought = ""
        action = ""
        action_input = {}

        for line in lines:
            line = line.strip()
            if line.startswith("Thought:"):
                thought = line[8:].strip()
            elif line.startswith("Action:"):
                action = line[7:].strip()
            elif line.startswith("Action Input:"):
                input_str = line[13:].strip()
                try:
                    action_input = json.loads(input_str)
                except json.JSONDecodeError:
                    # 如果不是JSON格式，作为字符串处理
                    action_input = input_str

        return thought, action, action_input


# 注册到Agent工厂
from .base import AgentFactory
from ..ai_types import AgentType

AgentFactory.register(AgentType.REACT, ReactAgent)
