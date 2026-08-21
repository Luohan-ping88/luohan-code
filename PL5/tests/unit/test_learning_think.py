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

def test_parameter_suggestion_produces_update_param():
    class FakeSLParams(FakeSL):
        def __init__(self):
            self.suggestion_history = [{
                "id": "SUG-PARAM1",
                "status": "pending",
                "category": "parameter_n_estimators",
                "priority": 2,
                "confidence_level": 0.7,
                "parameter": {"name": "n_estimators", "recommended_value": 150},
                "effect_estimation": {"improvement_range": [0.01, 0.04, 0.08]},
                "reasoning": "test rule",
            }]
        def generate_structured_suggestions(self):
            return []

    think = ThinkModule(self_learning=FakeSLParams(), feedback_analyzer=FakeFeedback(), llm=None)
    ctx = think.think()
    updates = [a for a in ctx.candidates if a.action_type == ActionType.UPDATE_PARAM.value]
    assert updates
    assert updates[0].suggestion_id == "SUG-PARAM1"
    assert updates[0].param_name == "n_estimators"
    assert updates[0].recommended_value == 150