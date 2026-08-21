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

class FakeSLAlert(FakeSL):
    def check_performance_alert(self):
        return {"alert_level": "warning", "reasons": ["declining trend"]}

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


def _make_engine(tmp_path):
    mem = tmp_path / "mem.json"
    engine = LearningLoopEngine(
        memory_path=mem, self_learning=FakeSLAlert(), engine=FakeEngine(),
    )
    return engine, mem


def test_effects_pending_after_first_run(tmp_path):
    engine, _ = _make_engine(tmp_path)
    engine.run_once({"period": "p1", "current_accuracy": 0.30})
    effects = engine.memory.get("effects")
    assert len(effects) == 1
    assert effects[0]["delta_accuracy"] is None
    assert effects[0]["baseline_accuracy"] == 0.30
    assert effects[0]["recorded_at"] is None


def test_effects_backfill_real_delta(tmp_path):
    engine, _ = _make_engine(tmp_path)
    engine.run_once({"period": "p1", "current_accuracy": 0.30})
    engine.run_once({"period": "p2", "current_accuracy": 0.38})
    effects = engine.memory.get("effects")
    assert effects[0]["delta_accuracy"] == pytest.approx(0.08, abs=1e-6)
    assert effects[0]["recorded_at"] is not None


def test_avg_effect_gain_is_real(tmp_path):
    engine, _ = _make_engine(tmp_path)
    engine.run_once({"period": "p1", "current_accuracy": 0.30})
    engine.run_once({"period": "p2", "current_accuracy": 0.38})
    meta = engine.memory.data.get("meta", {})
    assert meta.get("avg_effect_gain") == pytest.approx(0.08, abs=1e-6)