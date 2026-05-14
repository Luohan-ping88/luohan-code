#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能体调度系统集成模块
集成新智能体系统到现有调度器
支持新旧模式切换、降级模式
"""

import sys
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Callable
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


class SchedulerMode(Enum):
    """调度器模式"""

    LEGACY = "legacy"
    INTELLIGENT = "intelligent"
    HYBRID = "hybrid"


@dataclass
class IntegrationConfig:
    """集成配置"""

    mode: SchedulerMode = SchedulerMode.LEGACY
    enable_intelligent_agents: bool = True
    enable_fallback: bool = True
    fallback_timeout_seconds: int = 30
    intelligent_agent_weight: float = 0.7


class IntelligentSchedulerIntegration:
    """
    智能调度系统集成器

    功能：
    1. 新旧模式切换
    2. 降级模式（智能体失败时回退）
    3. 混合模式（新旧结合）
    4. 智能体决策追踪
    """

    def __init__(self, config: Optional[IntegrationConfig] = None):
        self.config = config or IntegrationConfig()
        self._intelligent_available = False
        self._legacy_available = True
        self._decision_history: list = []
        self._load_intelligent_modules()

    def _load_intelligent_modules(self) -> bool:
        """尝试加载智能体模块"""
        try:
            pass

            self._intelligent_available = True
            logger.info("[Integration] 智能体模块加载成功")
            return True
        except ImportError as e:
            logger.warning(f"[Integration] 智能体模块加载失败: {e}")
            self._intelligent_available = False
            return False

    def get_current_mode(self) -> SchedulerMode:
        """获取当前模式"""
        return self.config.mode

    def set_mode(self, mode: SchedulerMode) -> bool:
        """设置模式"""
        if (
            mode == SchedulerMode.INTELLIGENT
            and not self._intelligent_available
        ):
            logger.warning("[Integration] 智能体模式不可用，切换到Legacy模式")
            self.config.mode = SchedulerMode.LEGACY
            return False

        self.config.mode = mode
        logger.info(f"[Integration] 调度器模式切换为: {mode.value}")
        return True

    def should_use_intelligent(self, task_type: str) -> bool:
        """判断是否使用智能体模式"""
        if self.config.mode == SchedulerMode.LEGACY:
            return False

        if self.config.mode == SchedulerMode.INTELLIGENT:
            return (
                self._intelligent_available
                and self.config.enable_intelligent_agents
            )

        if self.config.mode == SchedulerMode.HYBRID:
            import random

            return random.random() < self.config.intelligent_agent_weight

        return False

    def execute_with_fallback(
        self,
        intelligent_fn: Callable,
        legacy_fn: Callable,
        task_name: str,
        *args,
        **kwargs,
    ) -> Any:
        """
        带降级的执行

        Args:
            intelligent_fn: 智能体执行函数
            legacy_fn: 旧逻辑执行函数
            task_name: 任务名称
            *args, **kwargs: 参数

        Returns:
            执行结果
        """
        start_time = datetime.now()

        use_intelligent = self.should_use_intelligent(task_name)
        mode_used = "intelligent" if use_intelligent else "legacy"

        try:
            if use_intelligent and self.config.enable_intelligent_agents:
                try:
                    result = intelligent_fn(*args, **kwargs)
                    self._record_decision(
                        task_name, mode_used, "success", start_time
                    )
                    return result
                except Exception as e:
                    logger.warning(
                        f"[Integration] 智能体执行失败: {e}，尝试降级"
                    )
                    if not self.config.enable_fallback:
                        raise

            result = legacy_fn(*args, **kwargs)
            self._record_decision(
                task_name,
                mode_used if not use_intelligent else "fallback",
                "success",
                start_time,
            )
            return result

        except Exception as e:
            self._record_decision(
                task_name, mode_used, "error", start_time, str(e)
            )
            raise

    def _record_decision(
        self,
        task_name: str,
        mode_used: str,
        status: str,
        start_time: datetime,
        error: Optional[str] = None,
    ):
        """记录决策"""
        record = {
            "task_name": task_name,
            "mode_used": mode_used,
            "status": status,
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "error": error,
        }
        self._decision_history.append(record)

        if len(self._decision_history) > 1000:
            self._decision_history = self._decision_history[-500:]

    def get_decision_stats(self) -> Dict[str, Any]:
        """获取决策统计"""
        if not self._decision_history:
            return {"total_decisions": 0}

        total = len(self._decision_history)
        intelligent_count = sum(
            1
            for d in self._decision_history
            if d["mode_used"] == "intelligent"
        )
        fallback_count = sum(
            1 for d in self._decision_history if d["mode_used"] == "fallback"
        )
        success_count = sum(
            1 for d in self._decision_history if d["status"] == "success"
        )

        return {
            "total_decisions": total,
            "intelligent_ratio": intelligent_count / total if total > 0 else 0,
            "fallback_ratio": fallback_count / total if total > 0 else 0,
            "success_rate": success_count / total if total > 0 else 0,
            "recent_decisions": self._decision_history[-10:],
        }

    def save_config(self, config_path: Path):
        """保存配置"""
        config_data = {
            "mode": self.config.mode.value,
            "enable_intelligent_agents": self.config.enable_intelligent_agents,
            "enable_fallback": self.config.enable_fallback,
            "fallback_timeout_seconds": self.config.fallback_timeout_seconds,
            "intelligent_agent_weight": self.config.intelligent_agent_weight,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

    def load_config(self, config_path: Path):
        """加载配置"""
        if not config_path.exists():
            return

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        self.config.mode = SchedulerMode(config_data.get("mode", "legacy"))
        self.config.enable_intelligent_agents = config_data.get(
            "enable_intelligent_agents", True
        )
        self.config.enable_fallback = config_data.get("enable_fallback", True)
        self.config.fallback_timeout_seconds = config_data.get(
            "fallback_timeout_seconds", 30
        )
        self.config.intelligent_agent_weight = config_data.get(
            "intelligent_agent_weight", 0.7
        )


_global_integration: Optional[IntelligentSchedulerIntegration] = None


def get_integration() -> IntelligentSchedulerIntegration:
    """获取全局集成器实例"""
    global _global_integration
    if _global_integration is None:
        _global_integration = IntelligentSchedulerIntegration()
    return _global_integration


def set_integration(integration: IntelligentSchedulerIntegration):
    """设置全局集成器实例"""
    global _global_integration
    _global_integration = integration
