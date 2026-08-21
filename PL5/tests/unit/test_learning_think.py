import pytest
from src.core.learning_think import ThinkModule
from src.core.learning_decision import RankedAction, ActionType

class FakeSL:
    def evaluate_recent_performance(self):
        return {"accuracy": 0.12, "std": 0.07, "trend": "declining", "count": 5}
    def compute_comprehensive_score(self):
        return {"comprehensive_score": 0.2, "metrics_available": ["accuracy"]}
    def check_performance_alert(self):
        return {"alert_level": "urgent", "reasons": ["low"]}
    def should_trigger_retrain(self):
        return True, "urgent alert"
    def generate_structured_suggestions(self):
        return []
    def get_suggestion_statistics(self):
        return {"effect_sample_size": 0, "adoption_rate": 0, "avg_actual_effect": None, "positive_effect_rate": 0}

class FakeFeedback:
    def analyze_strategy_performance(self, window_size=20):
        return {"overall_analysis": {"top3_accuracy": 0.12}, "position_analysis": {}}
    def _identify_strategy_issues(self, position_analysis, overall_analysis):
        return []
    def _generate_improvement_suggestions(self, issues, position_analysis):
        return []

def test_urgent_produces_retrain_action():
    think = ThinkModule(self_learning=FakeSL(), feedback_analyzer=FakeFeedback(), llm=None)
    ctx = think.think()
    kinds = {a.action_type for a in ctx.candidates}
    assert ActionType.RETRAIN.value in kinds
    assert len(ctx.reasoning) > 0

def test_no_llm_no_crash():
    think = ThinkModule(self_learning=FakeSL(), feedback_analyzer=FakeFeedback(), llm=None)
    ctx = think.think()
    assert ctx.reasoning