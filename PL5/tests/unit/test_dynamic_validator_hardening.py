"""内存加固：动态特征验证器 + _get_best_feature_config 缓存优先降级 单元测试。"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.core.features import dynamic_validator as dv
from src.core.features.dynamic_validator import DynamicFeatureValidator


# ---------- 内存守卫 ----------
def test_memory_guard_triggers_when_low(monkeypatch):
    monkeypatch.setattr(dv, "_available_memory_mb", lambda: 500.0)
    assert dv._memory_guard_active() is True


def test_memory_guard_safe_when_high(monkeypatch):
    monkeypatch.setattr(dv, "_available_memory_mb", lambda: 5000.0)
    assert dv._memory_guard_active() is False


def test_memory_guard_safe_when_unavailable(monkeypatch):
    monkeypatch.setattr(dv, "_available_memory_mb", lambda: None)
    assert dv._memory_guard_active() is False


# ---------- 验证入口内存守卫降级 ----------
def test_validate_and_update_features_degrades_on_low_memory(monkeypatch):
    class FakeCollector:
        def update_data(self):
            import pandas as pd
            return pd.DataFrame({"period": [1, 2], "ge": [3, 4]})

    monkeypatch.setattr(dv, "_memory_guard_active", lambda: True)
    v = DynamicFeatureValidator()
    v.collector = FakeCollector()
    res = v.validate_and_update_features()
    assert res["success"] is False
    assert "内存守卫" in res["error"]
    assert "best_config" in res


# ---------- 组合数限制 ----------
def test_find_best_feature_combination_limits_combos(monkeypatch):
    import pandas as pd
    from datetime import datetime

    calls = {"n": 0}

    def fake_validate(self, df, config):
        calls["n"] += 1
        return {
            "name": config["name"], "accuracy": 0.3,
            "select_top": config["select_top"],
            "feature_selection_method": config["feature_selection_method"],
            "timestamp": datetime.now().isoformat(),
        }

    monkeypatch.setattr(DynamicFeatureValidator, "validate_feature_combination", fake_validate)
    monkeypatch.setattr(dv, "MAX_COMBINATIONS", 3)
    v = DynamicFeatureValidator()
    df = pd.DataFrame({"period": [1], "ge": [2]})
    v.find_best_feature_combination(df)
    # 全量 6 组合 → 应被截断到 MAX_COMBINATIONS=3
    assert calls["n"] <= 3


# ---------- 训练抽样 ----------
def test_validate_feature_combination_samples_training_data(monkeypatch):
    import pandas as pd

    seen = {}

    class FakeEngineer:
        def extract_all_features(self, df, select_top=None, feature_selection_method="rfe"):
            return df.copy()

    class FakePredictor:
        def __init__(self):
            self.trained_rows = None
        def fit(self, train_data, feature_cols):
            seen["rows"] = len(train_data)
        def predict(self, features=None, recent_original_data=None, **kw):
            return {}

    monkeypatch.setattr(dv, "MAX_VALIDATION_SAMPLES", 50)
    monkeypatch.setattr(dv, "EnhancedPL5Predictor", FakePredictor)
    v = DynamicFeatureValidator()
    v.engineer = FakeEngineer()
    n = 500
    df = pd.DataFrame({
        "period": list(range(n)),
        "date": ["2026-01-01"] * n,
        "full_number": ["12345"] * n,
        "wan": [1] * n, "qian": [2] * n, "bai": [3] * n, "shi": [4] * n, "ge": [5] * n,
        **{f"f{i}": [0.1] * n for i in range(10)},
    })
    v.validate_feature_combination(df, {"name": "t", "description": "test", "select_top": 5, "feature_selection_method": "rfe"})
    assert seen["rows"] == 50  # 抽样后训练行数受限


# ---------- _get_best_feature_config 缓存优先（内存紧张复用缓存） ----------
def test_get_best_feature_config_reuses_cache_when_pressure(tmp_path, monkeypatch):
    import src.app.auto_scheduler_v8 as mod
    from src.app.auto_scheduler_v8 import AutoSchedulerV8

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    cache = {
        "best_config": {"select_top": 100, "feature_selection_method": "rfe"},
        "last_updated": datetime.now().isoformat(),
    }
    (logs_dir / "best_feature_config.json").write_text(
        json.dumps(cache, ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(mod, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(mod, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(AutoSchedulerV8, "_memory_pressure", lambda self: True)

    scheduler = AutoSchedulerV8.__new__(AutoSchedulerV8)
    best = scheduler._get_best_feature_config(force_validate=True)
    assert best["select_top"] == 100  # 内存紧张时应复用缓存而非强制验证


def test_get_best_feature_config_validates_when_no_pressure(tmp_path, monkeypatch):
    import src.app.auto_scheduler_v8 as mod
    from src.app.auto_scheduler_v8 import AutoSchedulerV8

    logs_dir = tmp_path / "logs2"
    logs_dir.mkdir()
    cache = {
        "best_config": {"select_top": 100, "feature_selection_method": "rfe"},
        "last_updated": datetime.now().isoformat(),
    }
    (logs_dir / "best_feature_config.json").write_text(
        json.dumps(cache, ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(mod, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(mod, "MODELS_DIR", tmp_path / "models2")
    monkeypatch.setattr(AutoSchedulerV8, "_memory_pressure", lambda self: False)

    # 内存充足 + force_validate=True → 应执行真实验证（不读缓存）
    # DynamicFeatureValidator 在方法内部局部导入，直接 patch 其类方法即可拦截
    from src.core.features.dynamic_validator import DynamicFeatureValidator as DV

    def fake_validate_and_update(self):
        return {"success": True, "best_config": {"select_top": 150, "feature_selection_method": "rfe"}}
    monkeypatch.setattr(DV, "validate_and_update_features", fake_validate_and_update)

    scheduler = AutoSchedulerV8.__new__(AutoSchedulerV8)
    best = scheduler._get_best_feature_config(force_validate=True)
    assert best["select_top"] == 150  # 强制执行了验证
