"""AI大模型工具系统

让智能体拥有"动手能力"，通过工具调用完成复杂任务。

核心架构：
- 模型层 (models): 大模型适配器
- 工具层 (tools): 标准化工具接口
- Agent层 (agents): 智能调度
- 记忆层 (memory): 历史记录

版本: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "PL5 Team"
__description__ = "AI大模型工具系统 - 让智能体拥有动手能力"

# 导出核心模块
from .registry import ToolRegistry, get_registry, reset_registry
from .models.base import BaseLLM, LLMFactory
from .tools.base import BaseTool
from .agents.base import BaseAgent, AgentFactory
from .memory.base import BaseMemory, MemoryManager
from .orchestrator import Workflow, WorkflowEngine, BuiltInWorkflows

__all__ = [
    # 核心组件
    "ToolRegistry",
    "get_registry",
    "reset_registry",
    "BaseLLM",
    "LLMFactory",
    "BaseTool",
    "BaseAgent",
    "AgentFactory",
    "BaseMemory",
    "MemoryManager",
    "Workflow",
    "WorkflowEngine",
    "BuiltInWorkflows",
    # 版本信息
    "__version__",
    "__author__",
    "__description__",
]
