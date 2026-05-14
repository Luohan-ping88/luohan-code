"""对话Agent实现"""

from typing import Dict, List, Any, Optional

from .base import BaseAgent, AgentFactory
from ..ai_types import AgentType, ToolResult, ConversationMessage


class ConversationAgent(BaseAgent):
    """对话Agent

    专注于对话管理，支持多轮对话和上下文理解。
    """

    def run(
        self, task: str, context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """执行任务"""
        # 构建对话消息
        messages = [
            ConversationMessage(
                role="system",
                content="你是一个智能对话助手，擅长理解用户需求并提供专业的回答。",
            ),
            ConversationMessage(role="user", content=task),
        ]

        return self.chat(messages, context)

    def chat(
        self,
        messages: List[ConversationMessage],
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """对话模式"""
        try:
            # 构建LLM对话格式
            llm_messages = []
            for msg in messages:
                llm_messages.append({"role": msg.role, "content": msg.content})

            # 调用LLM进行对话
            response = self.llm.chat(llm_messages)

            # 构建回复消息
            reply = ConversationMessage(
                role="assistant", content=response.get("content", "")
            )

            return ToolResult(
                success=True,
                data={"reply": reply, "conversation": messages + [reply]},
                metadata={
                    "agent_type": self.agent_type.value,
                    "llm_model": self.llm.model_name,
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"对话执行失败: {str(e)}",
                metadata={"agent_type": self.agent_type.value},
            )

    def get_conversation_history(
        self, messages: List[ConversationMessage], max_history: int = 10
    ) -> List[ConversationMessage]:
        """获取对话历史

        Args:
            messages: 完整对话消息
            max_history: 最大历史消息数

        Returns:
            截断后的对话历史
        """
        if len(messages) <= max_history:
            return messages
        return messages[-max_history:]

    def format_conversation(self, messages: List[ConversationMessage]) -> str:
        """格式化对话为文本

        Args:
            messages: 对话消息列表

        Returns:
            格式化的对话文本
        """
        formatted = ""
        for msg in messages:
            if msg.role == "system":
                formatted += f"System: {msg.content}\n"
            elif msg.role == "user":
                formatted += f"User: {msg.content}\n"
            elif msg.role == "assistant":
                formatted += f"Assistant: {msg.content}\n"
        return formatted


# 注册到工厂
AgentFactory.register(AgentType.CONVERSATION, ConversationAgent)
