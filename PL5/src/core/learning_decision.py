"""统一动作判定模型 (Task 2).

提供一个统一的入口，对外部候选动作进行分类、过滤与排序，
最终输出一个按优先级排好的动作序列供上层执行。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ActionType(Enum):
    """候选动作类型。"""

    UPDATE_PARAM = "update_param"
    RETRAIN = "retrain"
    FIX_DATA = "fix_data"
    MONITOR = "monitor"


@dataclass
class RankedAction:
    """带排序信息的候选动作。"""

    action_type: str
    priority: int
    confidence: float
    estimated_improvement_mid: float
    name: str = ""
    param_name: Optional[str] = None
    recommended_value: Optional[float] = None
    suggestion_id: Optional[str] = None
    reasoning: str = ""


# 各动作类型对应的置信度阈值
_CONFIDENCE_THRESHOLD = {
    ActionType.UPDATE_PARAM.value: 0.55,
    ActionType.FIX_DATA.value: 0.70,
}


class DecisionModule:
    """统一动作判定模型。

    - classify: 判断某类型动作在当前置信度下是否通过。
    - decide:   对候选动作先过滤（classify），再排序。
    - select_actions: 对外暴露的决定入口，等价于 decide。
    """

    def classify(self, action_type: str, confidence: float) -> bool:
        if action_type == ActionType.RETRAIN.value:
            return True
        if action_type == ActionType.MONITOR.value:
            return True
        if action_type == ActionType.UPDATE_PARAM.value:
            return confidence >= _CONFIDENCE_THRESHOLD[action_type]
        if action_type == ActionType.FIX_DATA.value:
            return confidence >= _CONFIDENCE_THRESHOLD[action_type]
        return False

    def decide(self, candidates: List[RankedAction]) -> List[RankedAction]:
        passed = [
            c for c in candidates
            if self.classify(c.action_type, c.confidence)
        ]

        def _sort_key(c: RankedAction):
            retrain_order = 0 if c.action_type == ActionType.RETRAIN.value else 1
            return (
                retrain_order,
                -c.priority,
                -c.confidence,
                -c.estimated_improvement_mid,
            )

        return sorted(passed, key=_sort_key)

    def select_actions(self, candidates: List[RankedAction]) -> List[RankedAction]:
        return self.decide(candidates)