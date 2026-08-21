"""执行阶段 ActModule (Task 4).

接收上一步排序好的 RankedAction，按其类型执行动作：
- UPDATE_PARAM: 调用 self_learning.apply_suggestion 应用参数更新。
- RETRAIN:     触发 engine.trigger_retrain 重训练。
- FIX_DATA:    调用 collector.update_data 修复数据。
- MONITOR/其他: 视为 no-op。

所有异常均被捕获降级，绝不向上抛出。
"""
from typing import Any, Dict, Optional

from src.core.learning_decision import ActionType, RankedAction


class ActModule:
    """执行阶段动作执行模块。

    属性:
        self_learning: 提供 apply_suggestion / record_suggestion_outcome 的自学习模块。
        engine:        提供 trigger_retrain 的训练引擎。
        collector:     提供 update_data 的数据收集器。
    """

    def __init__(self, self_learning=None, engine=None, collector=None) -> None:
        self.self_learning = self_learning
        self.engine = engine
        self.collector = collector

    def act(self, action: RankedAction) -> Dict[str, Any]:
        """执行单个动作，返回 {"action_type", "executed", "message"} 等结果。"""
        try:
            return self._act(action)
        except Exception as exc:  # noqa: BLE001 绝不向上抛
            return {
                "action_type": action.action_type,
                "executed": False,
                "message": f"skipped:{exc}",
            }

    def _act(self, action: RankedAction) -> Dict[str, Any]:
        action_type = action.action_type

        if action_type == ActionType.UPDATE_PARAM.value:
            return self._execute_update_param(action)
        if action_type == ActionType.RETRAIN.value:
            return self._execute_retrain()
        if action_type == ActionType.FIX_DATA.value:
            return self._execute_fix_data()

        return {
            "action_type": action_type,
            "executed": False,
            "message": "no-op",
        }

    def _execute_update_param(self, action: RankedAction) -> Dict[str, Any]:
        if self.self_learning is None:
            return {
                "action_type": action.action_type,
                "executed": False,
                "message": "no self_learning module",
            }
        if not action.suggestion_id:
            return {
                "action_type": action.action_type,
                "executed": False,
                "message": "empty suggestion_id",
            }
        result = self.self_learning.apply_suggestion(
            suggestion_id=action.suggestion_id
        )
        result_map: Dict[str, Any] = {
            "action_type": action.action_type,
            "executed": bool(result.get("applied")),
            "message": result.get("message", "applied"),
        }
        params_updated = result.get("params_updated")
        if params_updated:
            result_map["params_updated"] = params_updated
        return result_map

    def _execute_retrain(self) -> Dict[str, Any]:
        if self.engine is None:
            return {
                "action_type": ActionType.RETRAIN.value,
                "executed": False,
                "message": "no engine",
            }
        self.engine.trigger_retrain()
        return {
            "action_type": ActionType.RETRAIN.value,
            "executed": True,
            "message": "retrain triggered",
        }

    def _execute_fix_data(self) -> Dict[str, Any]:
        if self.collector is None:
            return {
                "action_type": ActionType.FIX_DATA.value,
                "executed": False,
                "message": "no collector",
            }
        result = self.collector.update_data()
        executed = bool(result) and not getattr(result, "empty", False)
        return {
            "action_type": ActionType.FIX_DATA.value,
            "executed": executed,
            "message": "data updated" if executed else "no data updated",
        }