"""AI工具系统核心类型定义

定义系统中使用的基础类型、数据结构和常量。
"""

from typing import Dict, List, Any, Optional, Callable, TypeVar, Generic, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

T = TypeVar('T')


class ToolCategory(Enum):
    BUILTIN = "builtin"
    PL5 = "pl5"
    API = "api"
    CUSTOM = "custom"


class LLMType(Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    LOCAL = "local"
    HUGGINGFACE = "huggingface"
    OTHER = "other"


class AgentType(Enum):
    REACT = "react"
    TOOL_CALLING = "tool_calling"
    CONVERSATION = "conversation"
    MULTI_STEP = "multi_step"


class MemoryType(Enum):
    CONVERSATION = "conversation"
    EXECUTION = "execution"
    LONG_TERM = "long_term"
    VECTOR = "vector"


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    example: Optional[Any] = None


@dataclass
class ToolInfo:
    name: str
    description: str
    parameters: List[ToolParameter]
    category: ToolCategory = ToolCategory.CUSTOM
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LLMConfig:
    model_type: LLMType
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout: int = 30
    streaming: bool = False


@dataclass
class AgentConfig:
    agent_type: AgentType
    llm_config: LLMConfig
    max_steps: int = 10
    max_retries: int = 3
    timeout: int = 300


@dataclass
class MemoryConfig:
    memory_type: MemoryType
    max_size: int = 1000
    ttl: Optional[int] = None
    embedding_dim: int = 1536
    storage_path: Optional[str] = None


@dataclass
class WorkflowStep:
    name: str
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    condition_expr: Optional[str] = None
    retry_count: int = 0
    retry_delay: float = 1.0
    parallel_group: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "condition_expr": self.condition_expr,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "parallel_group": self.parallel_group
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowStep':
        step = cls(
            name=data["name"],
            tool_name=data["tool_name"],
            parameters=data.get("parameters", {}),
            condition_expr=data.get("condition_expr"),
            retry_count=data.get("retry_count", 0),
            retry_delay=data.get("retry_delay", 1.0),
            parallel_group=data.get("parallel_group")
        )
        if step.condition_expr:
            step.condition = cls._compile_condition(step.condition_expr)
        return step

    @staticmethod
    def _compile_condition(expr: str) -> Callable[[Dict[str, Any]], bool]:
        def condition(variables: Dict[str, Any]) -> bool:
            try:
                return bool(eval(expr, {}, variables))
            except Exception:
                return False
        return condition


@dataclass
class ConversationMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_call_id: Optional[str] = None
    tool_result: Optional[ToolResult] = None


@dataclass
class ExecutionRecord:
    tool_name: str
    parameters: Dict[str, Any]
    result: ToolResult
    timestamp: datetime = field(default_factory=datetime.now)
    execution_time: float = 0.0


ToolFunction = Callable[[Dict[str, Any]], ToolResult]
ToolDecorator = Callable[[ToolFunction], ToolFunction]
JSON = Dict[str, Any]
Vector = List[float]
Embedding = Vector
