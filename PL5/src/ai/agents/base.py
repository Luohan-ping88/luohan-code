"""Agent层基础接口"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

from ..ai_types import AgentConfig, AgentType, ToolResult, ConversationMessage
from ..registry import get_registry
from ..models.base import LLMFactory


class BaseAgent(ABC):
    """Agent抽象基类"""

    def __init__(self, config: AgentConfig):
        """初始化Agent

        Args:
            config: Agent配置
        """
        self.config = config
        self.agent_type = config.agent_type
        self.llm = LLMFactory.create(config.llm_config)
        self.tool_registry = get_registry()
        self.max_steps = config.max_steps
        self.max_retries = config.max_retries
        self.timeout = config.timeout

    @abstractmethod
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

    @abstractmethod
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

    def get_available_tools(self) -> List[str]:
        """获取可用工具列表

        Returns:
            工具名称列表
        """
        return self.tool_registry.list_tools()

    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """获取工具信息

        Args:
            tool_name: 工具名称

        Returns:
            工具信息
        """
        tool_info = self.tool_registry.get_tool_info(tool_name)
        if tool_info:
            return {
                "name": tool_info.name,
                "description": tool_info.description,
                "parameters": [
                    {
                        "name": param.name,
                        "type": param.type,
                        "description": param.description,
                        "required": param.required,
                        "default": param.default,
                    }
                    for param in tool_info.parameters
                ],
            }
        return None

    def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> ToolResult:
        """执行工具

        Args:
            tool_name: 工具名称
            parameters: 工具参数

        Returns:
            工具执行结果
        """
        return self.tool_registry.execute_tool(tool_name, parameters)

    def get_config(self) -> AgentConfig:
        """获取配置

        Returns:
            Agent配置
        """
        return self.config

    def set_config(self, config: AgentConfig) -> None:
        """设置配置

        Args:
            config: Agent配置
        """
        self.config = config
        self.agent_type = config.agent_type
        self.llm = LLMFactory.create(config.llm_config)
        self.max_steps = config.max_steps
        self.max_retries = config.max_retries
        self.timeout = config.timeout


class AgentFactory:
    """Agent工厂类"""

    _agent_classes = {}

    @classmethod
    def register(cls, agent_type: AgentType, agent_class: type):
        """注册Agent类

        Args:
            agent_type: Agent类型
            agent_class: Agent类
        """
        cls._agent_classes[agent_type] = agent_class

    @classmethod
    def create(cls, config: AgentConfig) -> BaseAgent:
        """创建Agent实例

        Args:
            config: Agent配置

        Returns:
            Agent实例

        Raises:
            ValueError: 如果Agent类型不支持
        """
        agent_class = cls._agent_classes.get(config.agent_type)
        if not agent_class:
            raise ValueError(f"Unsupported agent type: {config.agent_type}")
        return agent_class(config)

    @classmethod
    def list_supported_agents(cls) -> List[AgentType]:
        """列出支持的Agent类型

        Returns:
            支持的Agent类型列表
        """
        return list(cls._agent_classes.keys())

    @classmethod
    def is_supported(cls, agent_type: AgentType) -> bool:
        """检查Agent类型是否支持

        Args:
            agent_type: Agent类型

        Returns:
            是否支持
        """
        return agent_type in cls._agent_classes
