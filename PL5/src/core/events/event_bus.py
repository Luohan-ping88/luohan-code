"""事件总线模块
用于系统内部组件间的松耦合通信，消除循环依赖
"""

import asyncio
import logging
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型枚举"""
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_STEP_STARTED = "workflow.step.started"
    WORKFLOW_STEP_COMPLETED = "workflow.step.completed"
    TRAINING_STARTED = "training.started"
    TRAINING_COMPLETED = "training.completed"
    TRAINING_FAILED = "training.failed"
    PREDICTION_STARTED = "prediction.started"
    PREDICTION_COMPLETED = "prediction.completed"
    PREDICTION_FAILED = "prediction.failed"
    MODEL_LOADED = "model.loaded"
    MODEL_SAVED = "model.saved"
    DATA_FETCHED = "data.fetched"
    FEATURE_EXTRACTED = "feature.extracted"
    EVALUATION_STARTED = "evaluation.started"
    EVALUATION_COMPLETED = "evaluation.completed"
    ALERT_TRIGGERED = "alert.triggered"
    SYSTEM_ERROR = "system.error"
    HEALTH_CHECK_PASSED = "health_check.passed"
    HEALTH_CHECK_FAILED = "health_check.failed"


@dataclass
class Event:
    """事件数据类"""
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "unknown"
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id
        }


class EventHandler:
    """事件处理器基类"""

    def __init__(self, event_types: List[str]):
        self.event_types = event_types
        self.enabled = True

    async def handle(self, event: Event) -> None:
        """处理事件"""
        if self.enabled:
            await self._process(event)

    async def _process(self, event: Event) -> None:
        """实际处理逻辑，由子类实现"""
        raise NotImplementedError


class EventBus:
    """事件总线 - 单例模式"""

    _instance: Optional['EventBus'] = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._handlers: Dict[str, List[Callable]] = {}
        self._event_classes: Dict[str, type] = {}
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        self._async_handlers: Dict[str, List[Callable]] = {}
        self._initialized = True

        logger.info("[EventBus] 事件总线初始化完成")

    def register_event_class(self, event_type: str, event_class: type) -> None:
        """注册事件类"""
        self._event_classes[event_type] = event_class

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件（同步处理器）

        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"[EventBus] 订阅同步事件: {event_type}")

    def subscribe_async(self, event_type: str, handler: Callable) -> None:
        """订阅事件（异步处理器）

        Args:
            event_type: 事件类型
            handler: 异步事件处理函数
        """
        if event_type not in self._async_handlers:
            self._async_handlers[event_type] = []
        if handler not in self._async_handlers[event_type]:
            self._async_handlers[event_type].append(handler)
            logger.debug(f"[EventBus] 订阅异步事件: {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"[EventBus] 取消订阅同步事件: {event_type}")

        if event_type in self._async_handlers and handler in self._async_handlers[event_type]:
            self._async_handlers[event_type].remove(handler)
            logger.debug(f"[EventBus] 取消订阅异步事件: {event_type}")

    def publish(self, event: Event) -> None:
        """发布事件（同步）

        Args:
            event: 事件对象
        """
        try:
            self._add_to_history(event)

            # 调用同步处理器
            handlers = self._handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"[EventBus] 同步事件处理错误 {event.event_type}: {e}")

            logger.debug(f"[EventBus] 发布同步事件: {event.event_type}")

        except Exception as e:
            logger.error(f"[EventBus] 发布事件失败: {e}")

    async def publish_async(self, event: Event) -> None:
        """发布事件（异步）

        Args:
            event: 事件对象
        """
        try:
            self._add_to_history(event)

            # 调用异步处理器
            async_handlers = self._async_handlers.get(event.event_type, [])
            for handler in async_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"[EventBus] 异步事件处理错误 {event.event_type}: {e}")

            logger.debug(f"[EventBus] 发布异步事件: {event.event_type}")

        except Exception as e:
            logger.error(f"[EventBus] 异步发布事件失败: {e}")

    def _add_to_history(self, event: Event) -> None:
        """添加事件到历史记录"""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]

    def get_history(self, event_type: Optional[str] = None,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   limit: int = 100) -> List[Event]:
        """获取事件历史

        Args:
            event_type: 事件类型过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            事件列表
        """
        events = self._event_history

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        return events[-limit:]

    def clear_history(self) -> None:
        """清空事件历史"""
        self._event_history.clear()
        logger.info("[EventBus] 事件历史已清空")

    def get_statistics(self) -> Dict[str, Any]:
        """获取事件统计信息"""
        event_counts = {}
        for event in self._event_history:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

        return {
            "total_events": len(self._event_history),
            "event_counts": event_counts,
            "subscribed_sync_handlers": sum(len(h) for h in self._handlers.values()),
            "subscribed_async_handlers": sum(len(h) for h in self._async_handlers.values()),
            "registered_event_types": len(self._event_classes)
        }

    def reset(self) -> None:
        """重置事件总线"""
        self._handlers.clear()
        self._async_handlers.clear()
        self._event_history.clear()
        logger.info("[EventBus] 事件总线已重置")


# 全局事件总线实例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def publish_event(event_type: str, data: Dict[str, Any] = None,
                 source: str = "unknown",
                 correlation_id: Optional[str] = None) -> None:
    """发布事件的快捷函数

    Args:
        event_type: 事件类型
        data: 事件数据
        source: 事件来源
        correlation_id: 关联ID
    """
    event = Event(
        event_type=event_type,
        data=data or {},
        source=source,
        correlation_id=correlation_id
    )
    get_event_bus().publish(event)


async def publish_event_async(event_type: str, data: Dict[str, Any] = None,
                              source: str = "unknown",
                              correlation_id: Optional[str] = None) -> None:
    """异步发布事件的快捷函数

    Args:
        event_type: 事件类型
        data: 事件数据
        source: 事件来源
        correlation_id: 关联ID
    """
    event = Event(
        event_type=event_type,
        data=data or {},
        source=source,
        correlation_id=correlation_id
    )
    await get_event_bus().publish_async(event)
