import pytest
from src.core.learning_loop import LearningLoopEngine

class FakeSL:
    def __init__(self):
        self.evals = [{"timestamp": "t1", "accuracy": 0.3}]
    def evaluate_recent_performance(self):
        return {"accuracy": 0.3, "std": 0.03, "trend": "stable", "count": 5}
    def compute_comprehensive_score(self):
        return {"comprehensive_score": 0.5, "metrics_available": ["accuracy"]}
    def check_performance_alert(self):
        return {"alert_level": "normal", "reasons": ["ok"]}
    def should_trigger_retrain(self):
        return False, "ok"
    def generate_structured_suggestions(self):
        return []
    def get_suggestion_statistics(self):
        return {"effect_sample_size": 0, "adoption_rate": 0, "avg_actual_effect": None, "positive_effect_rate": 0}
    def apply_suggestion(self, **kw):
        return {"applied": True, "message": "applied", "params_updated": {}}
    def record_suggestion_outcome(self, **kw):
        return True

class FakeEngine:
    def trigger_retrain(self):
        pass

def test_run_once_idempotent(tmp_path):
    mem = tmp_path / "mem.json"
    engine = LearningLoopEngine(
        memory_path=mem, self_learning=FakeSL(), engine=FakeEngine(),
    )
    out1 = engine.run_once({"period": "2026223"})
    out2 = engine.run_once({"period": "2026223"})
    assert len(engine.memory.get("actions")) == len(out1["actions"])
    assert out2["skipped"] is True

def test_run_once_different_period(tmp_path):
    mem = tmp_path / "mem.json"
    engine = LearningLoopEngine(
        memory_path=mem, self_learning=FakeSL(), engine=FakeEngine(),
    )
    out1 = engine.run_once({"period": "2026223"})
    out3 = engine.run_once({"period": "2026224"})
    assert out3["skipped"] is False