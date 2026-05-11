"""
分布式智能体系统
提供多智能体协作、任务分发和协调能力
"""

from .protocol import (
    AgentCommunicationProtocol,
    AgentInfo,
    AgentCapability,
    AgentMessage,
    MessageType,
    MessagePriority,
    MessageQueue,
    AgentRegistry,
)

from .base_agent import (
    BaseAgent,
    CollaborativeAgent,
    MasterAgent,
    AgentState,
    AgentTask,
    TaskResult,
)

from .specialized_agents import (
    PredictionAgent,
    AnalysisAgent,
    DataCollectionAgent,
    EvaluationAgent,
    OrchestratorAgent,
)

__all__ = [
    "AgentCommunicationProtocol",
    "AgentInfo",
    "AgentCapability",
    "AgentMessage",
    "MessageType",
    "MessagePriority",
    "MessageQueue",
    "AgentRegistry",
    "BaseAgent",
    "CollaborativeAgent",
    "MasterAgent",
    "AgentState",
    "AgentTask",
    "TaskResult",
    "PredictionAgent",
    "AnalysisAgent",
    "DataCollectionAgent",
    "EvaluationAgent",
    "OrchestratorAgent",
]
