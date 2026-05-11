"""Agent编排器实现"""

from typing import Dict, List, Any, Optional

from .base import BaseAgent, AgentFactory
from ..ai_types import AgentConfig, AgentType, ToolResult, ConversationMessage


class AgentOrchestrator:
    """Agent编排器

    管理多个Agent的协作，根据任务类型选择合适的Agent。
    """

    def __init__(self):
        """初始化Agent编排器"""
        self._agents: Dict[str, BaseAgent] = {}

    def register_agent(self, name: str, agent: BaseAgent) -> None:
        """注册Agent

        Args:
            name: Agent名称
            agent: Agent实例
        """
        self._agents[name] = agent

    def create_agent(self, name: str, config: AgentConfig) -> BaseAgent:
        """创建并注册Agent

        Args:
            name: Agent名称
            config: Agent配置

        Returns:
            创建的Agent实例
        """
        agent = AgentFactory.create(config)
        self.register_agent(name, agent)
        return agent

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取Agent

        Args:
            name: Agent名称

        Returns:
            Agent实例
        """
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        """列出所有注册的Agent

        Returns:
            Agent名称列表
        """
        return list(self._agents.keys())

    def remove_agent(self, name: str) -> bool:
        """移除Agent

        Args:
            name: Agent名称

        Returns:
            是否移除成功
        """
        if name in self._agents:
            del self._agents[name]
            return True
        return False

    def select_agent(self, task: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """选择合适的Agent

        Args:
            task: 任务描述
            context: 上下文信息

        Returns:
            选择的Agent名称
        """
        # 简单的任务类型判断
        task_lower = task.lower()

        # 检查是否有专门的Agent
        if "predict" in task_lower or "forecast" in task_lower:
            return "tool_agent"  # 工具Agent适合预测任务
        elif "chat" in task_lower or "talk" in task_lower or "discuss" in task_lower:
            return "conversation_agent"  # 对话Agent适合聊天任务
        elif "react" in task_lower or "plan" in task_lower:
            return "react_agent"  # ReAct Agent适合复杂任务

        # 默认使用工具Agent
        return "tool_agent" if "tool_agent" in self._agents else next(iter(self._agents.keys()), None)

    def run_task(
        self, task: str, context: Optional[Dict[str, Any]] = None, agent_name: Optional[str] = None
    ) -> ToolResult:
        """执行任务

        Args:
            task: 任务描述
            context: 上下文信息
            agent_name: 指定的Agent名称

        Returns:
            任务执行结果
        """
        # 选择Agent
        if agent_name is None:
            agent_name = self.select_agent(task, context)

        if agent_name is None:
            return ToolResult(success=False, error="没有可用的Agent")

        agent = self.get_agent(agent_name)
        if agent is None:
            return ToolResult(success=False, error=f"Agent {agent_name} 不存在")

        # 执行任务
        try:
            result = agent.run(task, context)
            result.metadata["agent_name"] = agent_name
            return result
        except Exception as e:
            return ToolResult(success=False, error=f"Agent执行失败: {str(e)}", metadata={"agent_name": agent_name})

    def run_chat(
        self,
        messages: List[ConversationMessage],
        context: Optional[Dict[str, Any]] = None,
        agent_name: Optional[str] = None,
    ) -> ToolResult:
        """执行对话

        Args:
            messages: 对话消息列表
            context: 上下文信息
            agent_name: 指定的Agent名称

        Returns:
            对话执行结果
        """
        # 选择对话Agent
        if agent_name is None:
            agent_name = (
                "conversation_agent" if "conversation_agent" in self._agents else self.select_agent("chat", context)
            )

        if agent_name is None:
            return ToolResult(success=False, error="没有可用的Agent")

        agent = self.get_agent(agent_name)
        if agent is None:
            return ToolResult(success=False, error=f"Agent {agent_name} 不存在")

        # 执行对话
        try:
            result = agent.chat(messages, context)
            result.metadata["agent_name"] = agent_name
            return result
        except Exception as e:
            return ToolResult(success=False, error=f"对话执行失败: {str(e)}", metadata={"agent_name": agent_name})

    def get_agent_info(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """获取Agent信息

        Args:
            agent_name: Agent名称

        Returns:
            Agent信息
        """
        agent = self.get_agent(agent_name)
        if agent:
            config = agent.get_config()
            return {
                "name": agent_name,
                "type": config.agent_type.value,
                "llm_model": config.llm_config.model_name,
                "max_steps": config.max_steps,
                "max_retries": config.max_retries,
            }
        return None

    def list_agent_info(self) -> List[Dict[str, Any]]:
        """列出所有Agent信息

        Returns:
            Agent信息列表
        """
        return [self.get_agent_info(name) for name in self._agents.keys() if self.get_agent_info(name)]
