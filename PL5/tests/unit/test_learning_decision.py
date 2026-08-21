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


def test_adaptive_threshold_positive_gain_lowers_gate():
    # 历史效果增益为正 → 降低门槛，0.50 应能通过（默认门槛 0.55）
    dm = DecisionModule(avg_effect_gain=0.4)
    cands = [_sug(1, 0.50, 0.05)]
    assert dm.select_actions(cands) != []


def test_adaptive_threshold_negative_gain_raises_gate():
    # 历史效果增益为负 → 提高门槛，0.60 应被过滤（默认门槛 0.55）
    dm = DecisionModule(avg_effect_gain=-0.4)
    cands = [_sug(1, 0.60, 0.05)]
    assert dm.select_actions(cands) == []


def test_set_avg_effect_gain_updates_gate():
    dm = DecisionModule()
    cands = [_sug(1, 0.50, 0.05)]
    # 默认门槛 0.55 → 0.50 被过滤
    assert dm.select_actions(cands) == []
    dm.set_avg_effect_gain(0.4)  # 门槛降为 0.45 → 0.50 通过
    assert dm.select_actions(list(cands)) != []