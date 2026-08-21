"""复盘闭环 ReviewEngine 单元测试 (Task: §6)。"""
from pathlib import Path
import pytest

from src.core.retrospective import ReviewEngine

TMP = Path(__file__).parent / "_test_retrospective_memory.json"


@pytest.fixture(autouse=True)
def clean():
    if TMP.exists():
        TMP.unlink()
    yield
    if TMP.exists():
        TMP.unlink()


def _sample_state(**over):
    state = {
        "volatility": 0.12,
        "hot_ratio": 0.5,
        "span_mean": 30.0,
        "sum_mean": 120.0,
        "feature_discrimination": 0.4,
        "psi_drift": 0.1,
        "top1_rate": 0.2,
        "top3_rate": 0.3,
        "top8_rate": 0.6,
    }
    state.update(over)
    return state


def test_build_state_vector_returns_numeric_dict():
    engine = ReviewEngine()
    state = engine.build_state_vector(
        recent_preds=[{"top_k": [1, 2, 3]}],
        actual_opens=[[1, 2, 3]],
        feature_stats={"span_mean": 30.0, "sum_mean": 120.0},
        switcher_status={"top1_rate": 0.2},
    )
    assert isinstance(state, dict)
    assert "top1_rate" in state
    assert all(isinstance(v, (int, float)) for v in state.values())


def test_attribute_discrepancy_detects_factor():
    engine = ReviewEngine()
    att = engine.attribute_discrepancy(
        pred_topk=[1, 2, 3, 4], actual=[9, 8, 7, 6],
        ctx={"strategy": "stacking_dominant"},
    )
    assert isinstance(att, list)
    # 归因至少应输出一个可调域
    assert len(att) > 0
    assert all("domain" in a for a in att)


def test_attribute_discrepancy_hit_produces_no_action():
    engine = ReviewEngine()
    att = engine.attribute_discrepancy(
        pred_topk=[1, 2, 3, 4], actual=[1, 2, 3, 4],
        ctx={"strategy": "stacking_dominant"},
    )
    # 全命中时无差分，不应强推调整
    assert not any(a.get("strength", 0) > 0 for a in att)


def test_match_state_finds_similar_experience():
    engine = ReviewEngine()
    experiences = [
        {
            "state": _sample_state(volatility=0.11, span_mean=29.0),
            "actions": [{"domain": "hyperparam", "value": "max_depth=6"}],
            "delta_accuracy": 0.05,
        },
        {
            "state": _sample_state(volatility=0.9, span_mean=90.0),
            "actions": [{"domain": "strategy", "value": "hmm_dominant"}],
            "delta_accuracy": -0.02,
        },
    ]
    matches = engine.match_state(_sample_state(volatility=0.12, span_mean=30.0), experiences, top_k=1)
    assert matches
    # 应优先命中波动率与跨度更接近的那条有效经验
    assert matches[0]["delta_accuracy"] > 0


def test_propose_adjustments_combines_attribution_and_match():
    engine = ReviewEngine()
    att = [{"domain": "hyperparam", "strength": 0.6, "reason": "top3 偏低"}]
    matches = [
        {"state": _sample_state(), "actions": [{"domain": "hyperparam", "value": "max_depth=6"}],
         "delta_accuracy": 0.05},
    ]
    adj = engine.propose_adjustments(_sample_state(), att, matches)
    assert isinstance(adj, list)
    assert all("domain" in a for a in adj)


def test_record_and_reload_experience():
    engine = ReviewEngine(memory_path=TMP)
    engine.record_experience(
        state=_sample_state(),
        actions=[{"domain": "hyperparam", "value": "max_depth=6"}],
        outcome_delta=0.05,
        period="2026221",
    )
    engine2 = ReviewEngine(memory_path=TMP)
    exps = engine2.memory.get("experiences")
    assert len(exps) == 1
    assert exps[0]["delta_accuracy"] == 0.05
    assert exps[0]["period"] == "2026221"