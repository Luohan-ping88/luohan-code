import pytest
from src.core.learning_act import ActModule
from src.core.learning_decision import ActionType, RankedAction

class FakeSL:
    def apply_suggestion(self, suggestion_id=None, category=None, dry_run=False):
        if dry_run:
            return {"applied": True, "message": "dry"}
        return {"applied": True, "message": "applied", "params_updated": {"x": 1}}
    def record_suggestion_outcome(self, suggestion_id, status, actual_effect=None, notes=""):
        return True

class FakeEngine:
    def __init__(self):
        self.retrain_called = 0
    def trigger_retrain(self):
        self.retrain_called += 1

class FakeCollector:
    def __init__(self):
        self.updated = 0
    def update_data(self):
        self.updated += 1
        import pandas as pd
        return pd.DataFrame({"a": [1,2]})

def test_update_param_calls_apply():
    sl = FakeSL()
    engine = FakeEngine()
    act = ActModule(self_learning=sl, engine=engine)
    res = act.act(RankedAction(
        action_type=ActionType.UPDATE_PARAM.value, priority=1, confidence=0.8,
        estimated_improvement_mid=0.05, suggestion_id="SUG-ABC", name="x",
    ))
    assert res["executed"] is True

def test_retrain_triggers_engine():
    engine = FakeEngine()
    act = ActModule(self_learning=FakeSL(), engine=engine)
    act.act(RankedAction(
        action_type=ActionType.RETRAIN.value, priority=1, confidence=1.0,
        estimated_improvement_mid=0.2, name="retrain",
    ))
    assert engine.retrain_called == 1

def test_monitor_noop():
    act = ActModule(self_learning=FakeSL(), engine=FakeEngine())
    res = act.act(RankedAction(
        action_type=ActionType.MONITOR.value, priority=3, confidence=1.0,
        estimated_improvement_mid=0.0, name="monitor",
    ))
    assert res["executed"] is False