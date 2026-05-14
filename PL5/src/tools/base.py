"""
PL5 工具系统核心基础设施

定义工具系统的基类、接口、上下文对象和结果格式:
- ToolLayer: 工具分层枚举（基础设施/核心/应用层）
- ErrorInfo: 结构化错误信息
- ToolResult: 标准化执行结果（支持序列化）
- ToolContext: 工具执行上下文（配置/缓存/日志/指标/状态共享）
- BaseTool: 所有工具的抽象基类（execute/validate/async/info）
- ToolRegistry: 全局工具注册表
- register_tool: 装饰器式工具注册
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Tuple, get_type_hints
from dataclasses import dataclass, field
from enum import Enum
import time
import logging
import asyncio

logger = logging.getLogger(__name__)


# ── 枚举与数据结构 ──────────────────────────────────────────────


class ToolLayer(Enum):
    """工具分层 - 用于组织和管理不同层次的工具"""

    INFRASTRUCTURE = "infrastructure"
    CORE = "core"
    APPLICATION = "application"


@dataclass
class ErrorInfo:
    """结构化错误信息"""

    code: str
    message: str
    severity: str = "error"
    details: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
        }


@dataclass
class ToolResult:
    """标准化工具执行结果

    所有工具的 execute() 方法必须返回此类型，
    保证结果格式统一，便于上层编排和监控。
    """

    success: bool
    data: Any = None
    metadata: Dict = field(default_factory=dict)
    errors: List[ErrorInfo] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        """序列化为字典，用于日志记录、API响应或持久化"""
        return {
            "success": self.success,
            "data": self._serialize_data(self.data),
            "metadata": self.metadata,
            "errors": [e.to_dict() for e in self.errors],
            "timestamp": self.timestamp,
        }

    @staticmethod
    def _serialize_data(data: Any) -> Any:
        """递归序列化 data 字段中的非 JSON 兼容对象"""
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool)):
            return data
        if isinstance(data, dict):
            return {k: ToolResult._serialize_data(v) for k, v in data.items()}
        if isinstance(data, (list, tuple)):
            return [ToolResult._serialize_data(item) for item in data]
        if hasattr(data, "to_dict"):
            return data.to_dict()
        if hasattr(data, "__dict__"):
            return {
                k: ToolResult._serialize_data(v)
                for k, v in data.__dict__.items()
                if not k.startswith("_")
            }
        return str(data)

    @classmethod
    def success_result(cls, data=None, **meta) -> "ToolResult":
        """快速创建成功结果"""
        return cls(success=True, data=data, metadata=meta if meta else {})

    @classmethod
    def error_result(cls, message, code="TOOL_ERROR", **meta) -> "ToolResult":
        """快速创建错误结果"""
        return cls(
            success=False,
            errors=[ErrorInfo(code=code, message=message)],
            metadata=meta if meta else {},
        )

    def add_error(
        self,
        code: str,
        message: str,
        severity: str = "error",
        details: Optional[Dict] = None,
    ):
        """追加一条错误信息并标记失败"""
        self.errors.append(
            ErrorInfo(
                code=code,
                message=message,
                severity=severity,
                details=details,
            )
        )
        self.success = False
        return self

    def merge(self, other: "ToolResult") -> "ToolResult":
        """合并另一个 ToolResult 的错误和元数据"""
        self.errors.extend(other.errors)
        self.metadata.update(other.metadata)
        if not other.success:
            self.success = False
        return self


@dataclass
class ToolContext:
    """工具执行上下文

    在一次完整的预测流程中，所有工具共享同一个 Context 实例，
    通过 state 字典实现跨工具的状态传递。
    """

    config: Any = None
    cache: Optional[Dict] = None
    logger: Optional[logging.Logger] = None
    metrics: Optional[Dict] = None
    state: Dict = field(default_factory=dict)
    user_id: Optional[str] = None

    @property
    def log(self) -> logging.Logger:
        """获取可用 logger，回退到模块级默认 logger"""
        return self.logger or logger

    def get(self, key: str, default: Any = None) -> Any:
        """从共享状态中获取值"""
        return self.state.get(key, default)

    def set(self, key: str, value: Any):
        """设置共享状态值"""
        self.state[key] = value

    def record_metric(self, name: str, value: Any):
        """记录性能指标到 metrics 收集器"""
        if self.metrics is not None:
            self.metrics[name] = value

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """从 config 中安全获取嵌套配置值（兼容 ModelConfig 和 dict）"""
        if self.config is None:
            return default
        if hasattr(self.config, "get") and not isinstance(self.config, dict):
            return self.config.get(key, default)
        keys = key.split(".")
        current = self.config
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current

    def create_child(self, **overrides) -> "ToolContext":
        """创建子上下文，继承当前状态但可覆盖部分字段"""
        child_state = dict(self.state)
        child_cache = dict(self.cache) if self.cache else None
        child_metrics = dict(self.metrics) if self.metrics else None
        return ToolContext(
            config=overrides.get("config", self.config),
            cache=overrides.get("cache", child_cache),
            logger=overrides.get("logger", self.logger),
            metrics=overrides.get("metrics", child_metrics),
            state=child_state,
            user_id=overrides.get("user_id", self.user_id),
        )


# ── 全局工具注册表 ──────────────────────────────────────────────


class ToolRegistry:
    """全局工具注册表

    单例模式，通过 register_tool 装饰器自动注册，
    支持按名称、标签、层级查询已注册的工具。
    """

    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, Type["BaseTool"]] = {}

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(
        self, tool_class: Type["BaseTool"], name: Optional[str] = None
    ) -> Type["BaseTool"]:
        """注册一个工具类"""
        reg_name = name or getattr(tool_class, "name", None)
        if not reg_name:
            raise ValueError(f"工具类 {tool_class.__name__} 缺少 name 属性")
        self._tools[reg_name] = tool_class
        logger.debug(
            f"[ToolRegistry] 已注册工具: {reg_name} ({tool_class.__name__})"
        )
        return tool_class

    def get(self, name: str) -> Optional[Type["BaseTool"]]:
        """按名称获取工具类"""
        return self._tools.get(name)

    def create(self, name: str, **kwargs) -> Optional["BaseTool"]:
        """按名称创建工具实例"""
        tool_class = self.get(name)
        if tool_class is None:
            return None
        return tool_class(**kwargs)

    def list_all(self) -> Dict[str, Type["BaseTool"]]:
        """返回所有已注册工具的副本"""
        return dict(self._tools)

    def list_by_layer(self, layer: ToolLayer) -> Dict[str, Type["BaseTool"]]:
        """按层级筛选工具"""
        return {
            name: cls
            for name, cls in self._tools.items()
            if getattr(cls, "layer", ToolLayer.CORE) == layer
        }

    def list_by_tag(self, tag: str) -> Dict[str, Type["BaseTool"]]:
        """按标签筛选工具"""
        return {
            name: cls
            for name, cls in self._tools.items()
            if tag in getattr(cls, "tags", [])
        }

    def clear(self):
        """清空注册表（主要用于测试）"""
        self._tools.clear()

    @property
    def count(self) -> int:
        return len(self._tools)

    def list_ai_tools(self) -> Dict[str, Type["BaseTool"]]:
        """返回适合AI调用的工具"""
        return {
            k: v
            for k, v in self._tools.items()
            if hasattr(v, "ai_friendly_schema")
        }

    def get_ai_tool_info(self, tool_name: str) -> Optional[Dict]:
        """返回工具的AI友好信息"""
        tool_class = self.get(tool_name)
        if tool_class:
            tool_instance = tool_class()
            return {
                "name": tool_instance.name,
                "description": tool_instance.get_tool_description(),
                "schema": tool_instance.ai_friendly_schema,
                "examples": tool_instance.get_parameter_examples(),
            }
        return None

    def list_by_ability(self, ability: str) -> Dict[str, Type["BaseTool"]]:
        """按能力类别过滤工具"""
        return {
            name: cls
            for name, cls in self._tools.items()
            if ability in getattr(cls, "tags", [])
        }


_global_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """获取全局工具注册表单例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_registry():
    """重置全局注册表（测试用）"""
    global _global_registry
    if _global_registry is not None:
        _global_registry.clear()
    _global_registry = None


# ── 注册装饰器 ──────────────────────────────────────────────────


def register_tool(name: str = None, tags: List[str] = None):
    """装饰器：自动将工具类注册到 ToolRegistry

    用法::

        @register_tool(tags=["prediction", "core"])
        class MyPredictor(BaseTool):
            name = "my_predictor"
            ...

    Args:
        name: 覆盖工具类的 name 属性作为注册名（可选）
        tags: 附加标签列表（会合并到类的 tags 中）
    """

    def decorator(cls: Type[BaseTool]) -> Type[BaseTool]:
        if tags is not None:
            existing_tags = list(getattr(cls, "tags", []))
            merged_tags = list(set(existing_tags + tags))
            cls.tags = merged_tags
        registry = get_registry()
        return registry.register(cls, name=name)

    return decorator


# ── 抽象基类 ────────────────────────────────────────────────────


class BaseTool(ABC):
    """所有工具的抽象基类

    子类必须实现 execute() 方法。
    可选覆写 validate() 以提供输入参数校验。

    类属性说明:
        name:         工具唯一标识名
        description:  工具功能描述
        layer:        所属分层 (ToolLayer)
        tags:         分类标签列表
        input_schema: 输入参数 JSON Schema（用于验证和文档生成）
        output_schema:输出参数 JSON Schema
    """

    name: str = ""
    description: str = ""
    layer: ToolLayer = ToolLayer.CORE
    tags: List[str] = []
    input_schema: Optional[Dict] = None
    output_schema: Optional[Dict] = None

    @abstractmethod
    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        """执行工具主逻辑

        Args:
            ctx:   共享执行上下文
            **kwargs: 工具特定参数

        Returns:
            ToolResult 标准化结果
        """

    def validate(self, **kwargs) -> Tuple[bool, List[ErrorInfo]]:
        """验证输入参数

        默认实现基于 input_schema 进行基本校验：
        - 检查 required 字段是否存在
        - 检查字段类型是否匹配 type 约束

        子类可覆写以添加业务级验证逻辑。

        Returns:
            (是否有效, 错误列表)
        """
        if self.input_schema is None:
            return True, []

        schema = self.input_schema
        errors: List[ErrorInfo] = []
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for req_field in required:
            if req_field not in kwargs or kwargs[req_field] is None:
                errors.append(
                    ErrorInfo(
                        code="VALIDATION_REQUIRED",
                        message=f"缺少必填参数: '{req_field}'",
                        severity="error",
                    )
                )

        for key, value in kwargs.items():
            if key in properties:
                prop_def = properties[key]
                expected_type = prop_def.get("type")
                if expected_type and value is not None:
                    type_map = {
                        "string": str,
                        "integer": int,
                        "number": (int, float),
                        "boolean": bool,
                        "array": (list, tuple),
                        "object": dict,
                        "null": type(None),
                    }
                    allowed_types = type_map.get(expected_type)
                    if allowed_types and not isinstance(value, allowed_types):
                        errors.append(
                            ErrorInfo(
                                code="VALIDATION_TYPE",
                                message=(
                                    f"参数 '{key}' 类型不匹配: "
                                    f"期望 {expected_type}, 实际 {type(value).__name__}"
                                ),
                                severity="warning",
                            )
                        )

        return len(errors) == 0, errors

    async def execute_async(self, ctx: ToolContext, **kwargs) -> ToolResult:
        """异步执行（默认使用线程池包装同步 execute）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.execute(ctx, **kwargs)
        )

    def get_info(self) -> Dict:
        """返回工具信息描述，用于发现和文档生成"""
        hints = {}
        try:
            hints = get_type_hints(type(self).execute)
        except Exception:
            pass

        return {
            "name": self.name,
            "description": self.description,
            "layer": (
                self.layer.value
                if isinstance(self.layer, ToolLayer)
                else str(self.layer)
            ),
            "tags": list(self.tags),
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "class_name": self.__class__.__name__,
            "module": self.__module__,
        }

    def get_tool_description(self) -> str:
        """返回适合大模型理解的工具描述"""
        return self.description

    def get_parameter_examples(self) -> Dict[str, Any]:
        """提供参数示例"""
        examples = {}
        if self.input_schema and "properties" in self.input_schema:
            for param_name, param_schema in self.input_schema[
                "properties"
            ].items():
                if "example" in param_schema:
                    examples[param_name] = param_schema["example"]
        return examples

    @property
    def ai_friendly_schema(self) -> Dict:
        """返回大模型友好的schema"""
        schema = {
            "name": self.name,
            "description": self.description,
            "parameters": {},
        }
        if self.input_schema and "properties" in self.input_schema:
            for param_name, param_schema in self.input_schema[
                "properties"
            ].items():
                schema["parameters"][param_name] = {
                    "type": param_schema.get("type", "string"),
                    "description": param_schema.get("description", ""),
                    "required": param_name
                    in self.input_schema.get("required", []),
                }
                if "example" in param_schema:
                    schema["parameters"][param_name]["example"] = param_schema[
                        "example"
                    ]
        return schema

    def run_safe(self, ctx: ToolContext, **kwargs) -> ToolResult:
        """安全执行：先 validate 再 execute，自动捕获异常"""
        valid, validation_errors = self.validate(**kwargs)
        if not valid:
            result = ToolResult.error_result(
                "输入参数验证失败",
                code="VALIDATION_FAILED",
            )
            result.errors.extend(validation_errors)
            return result

        try:
            start_time = time.time()
            result = self.execute(ctx, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000
            result.metadata.setdefault("execution_ms", round(elapsed_ms, 2))
            result.metadata.setdefault("tool_name", self.name)
            ctx.record_metric(f"{self.name}.execution_ms", elapsed_ms)
            return result
        except Exception as e:
            ctx.log.exception(f"[{self.name}] 执行异常: {e}")
            return ToolResult.error_result(
                f"工具执行异常: {str(e)}",
                code="EXECUTION_ERROR",
                exception_type=type(e).__name__,
            )
