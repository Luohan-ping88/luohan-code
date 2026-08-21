import pytest
from src.core.learning_decision import RankedAction, DecisionModule, ActionType

def _sug(priority, confidence, improvement, param=None):
    return RankedAction(
        action_type=ActionType.UPDATE_PARAM.value,
        priority=priority, confidence=confidence,
        estimated_improvement_mid=improvement,
        name=param or ("param_%s" % priority),
    )

def test_retrain_always_first():
    dm = DecisionModule()
    cands = [
        _sug(1, 0.9, 0.05),
        _sug(3, 0.9, 0.1),
        RankedAction(action_type=ActionType.RETRAIN.value, priority=1, confidence=1.0, estimated_improvement_mid=0.2, name="retrain"),
    ]
    ranked = dm.decide(cands)
    assert ranked[0].action_type == ActionType.RETRAIN.value

def test_update_param_confidence_threshold():
    dm = DecisionModule()
    cands = [_sug(1, 0.40, 0.05)]  # 0.40 < 0.55 → 被过滤
    actions = dm.select_actions(cands)
    assert actions == []