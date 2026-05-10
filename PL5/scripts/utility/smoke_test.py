"""
PL5 V5.3 端到端冒烟测试脚本
"""
import sys
import os
import traceback

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, '.')

PASS = 0
FAIL = 0
WARN = 0

def check(label, fn):
    global PASS, FAIL
    try:
        result = fn()
        print(f"[PASS] {label}" + (f" -> {result}" if result is not None else ""))
        PASS += 1
        return True
    except Exception as e:
        print(f"[FAIL] {label}")
        print(f"       {e}")
        FAIL += 1
        return False

print("=" * 60)
print("PL5 V5.3 - End-to-End Smoke Test")
print("=" * 60)
print()

# --- 1. 模块导入检查 ---
print("[MODULE IMPORTS]")
mods = [
    ('core.config',              'setup_logging'),
    ('core.data_collector',      'PL5DataCollector'),
    ('core.feature_engineering', 'FeatureEngineer'),
    ('core.models',              'PL5Predictor'),
    ('core.self_learning',       'SelfLearningSystem'),
    ('app.auto_scheduler',       'AutoScheduler'),
    ('monitor.perfect_monitor',  'PerfectSystemMonitor'),
]
for mod, attr in mods:
    def _f(m=mod, a=attr):
        import importlib
        x = importlib.import_module(m)
        getattr(x, a)
    check(f"import {mod}.{attr}", _f)

print()

# --- 2. C++ 扩展 ---
print("[CPP CORE]")
def test_cpp():
    import cpp_core
    fc = cpp_core.FeatureCalculator
    data = list(range(50))
    means = fc.rolling_mean(data, 5)
    assert len(means) == 50, "rolling_mean length mismatch"
    stds  = fc.rolling_std(data, 5)
    assert len(stds)  == 50, "rolling_std length mismatch"
    fft   = fc.fft_transform(data)
    assert len(fft)   == 50, "fft_transform length mismatch"
    return f"CPP_AVAILABLE={cpp_core.CPP_AVAILABLE}"
check("cpp_core.FeatureCalculator rolling_mean/std/fft", test_cpp)

print()

# --- 3. 数据采集 ---
print("[DATA COLLECTION]")
def test_data():
    from core.data_collector import PL5DataCollector
    c = PL5DataCollector()
    df = c.load_processed_data()
    if df is None or len(df) == 0:
        df = c.update_data()
    assert df is not None and len(df) > 0, "no data loaded"
    return f"{len(df)} records, latest={df['period'].iloc[-1]}"
check("PL5DataCollector.load/update_data", test_data)

print()

# --- 4. 特征工程 ---
print("[FEATURE ENGINEERING]")
def test_fe():
    from core.data_collector import PL5DataCollector
    from core.feature_engineering import FeatureEngineer
    c = PL5DataCollector()
    df = c.load_processed_data()
    if df is None:
        df = c.update_data()
    # 只取最近 200 条加速测试
    df = df.tail(200).reset_index(drop=True)
    fe = FeatureEngineer()
    features = fe.extract_all_features(df)
    feat_cols = [col for col in features.columns
                 if col not in ['period','full_number','wan','qian','bai','shi','ge']]
    assert len(feat_cols) > 10, f"too few features: {len(feat_cols)}"
    return f"{len(feat_cols)} features extracted"
check("FeatureEngineer.extract_all_features (200 records)", test_fe)

print()

# --- 5. 模型训练（快速小样本）---
print("[MODEL TRAINING]")
def test_train():
    from core.data_collector import PL5DataCollector
    from core.feature_engineering import FeatureEngineer
    from core.models import PL5Predictor
    c = PL5DataCollector()
    df = c.load_processed_data()
    if df is None:
        df = c.update_data()
    df = df.tail(300).reset_index(drop=True)
    fe = FeatureEngineer()
    features = fe.extract_all_features(df)
    feat_cols = [col for col in features.columns
                 if col not in ['period','full_number','wan','qian','bai','shi','ge']]
    predictor = PL5Predictor()
    predictor.fit(features, feat_cols)
    return "model trained OK"
check("PL5Predictor.fit (300 records)", test_train)

print()

# --- 6. 预测生成 ---
print("[PREDICTION]")
def test_predict():
    from core.data_collector import PL5DataCollector
    from core.feature_engineering import FeatureEngineer
    from core.models import PL5Predictor
    c = PL5DataCollector()
    df = c.load_processed_data()
    df = df.tail(300).reset_index(drop=True)
    fe = FeatureEngineer()
    features = fe.extract_all_features(df)
    feat_cols = [col for col in features.columns
                 if col not in ['period','full_number','wan','qian','bai','shi','ge']]
    predictor = PL5Predictor()
    predictor.fit(features, feat_cols)
    latest = features[feat_cols].iloc[-1].values
    preds = predictor.predict(latest, top_k=5)
    assert isinstance(preds, dict), "predictions should be dict"
    assert len(preds) == 5, f"expect 5 positions, got {len(preds)}"
    return str({k: v[:3] for k, v in preds.items()})
check("PL5Predictor.predict (top_k=5)", test_predict)

print()

# --- 7. 系统监控 ---
print("[SYSTEM MONITOR]")
def test_monitor():
    from monitor.perfect_monitor import PerfectSystemMonitor
    m = PerfectSystemMonitor()
    metrics = m.get_system_metrics()
    assert 'cpu' in metrics, "no cpu metrics"
    assert 'memory' in metrics, "no memory metrics"
    assert 'disk' in metrics, "no disk metrics"
    return f"cpu={metrics['cpu']['percent']}% mem={metrics['memory']['percent']}%"
check("PerfectSystemMonitor.get_system_metrics", test_monitor)

print()

# --- 8. AutoScheduler 实例化 ---
print("[SCHEDULER]")
def test_scheduler():
    from app.auto_scheduler import AutoScheduler
    s = AutoScheduler()
    assert s.config is not None
    return "scheduler config loaded"
check("AutoScheduler instantiation", test_scheduler)

print()

# --- 汇总 ---
total = PASS + FAIL
print("=" * 60)
print(f"SMOKE TEST SUMMARY: {PASS}/{total} PASS  |  {FAIL} FAIL")
print("=" * 60)
if FAIL == 0:
    print("All tests PASSED - system is ready for deployment!")
else:
    print(f"WARNING: {FAIL} test(s) failed - please check above output")

sys.exit(FAIL)
