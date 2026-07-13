"""
PL5 V8.0 端到端冒烟测试脚本
测试系统核心功能是否正常运行
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
print("PL5 V8.0 - End-to-End Smoke Test")
print("=" * 60)
print()

# --- 1. 模块导入检查 ---
print("[MODULE IMPORTS]")
mods = [
    ('src.core.config', 'setup_logging'),
    ('src.core.data.collector', 'PL5DataCollectorV8'),
    ('src.core.features.engineer', 'FeatureEngineer'),
    ('src.core.models.predictor', 'PL5Predictor'),
    ('src.core.self_learning', 'SelfLearningSystem'),
    ('src.app.auto_scheduler', 'AutoScheduler'),
    ('monitor.perfect_monitor', 'PerfectSystemMonitor'),
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
    import cpp_core.pl5_core as cpp_core
    fc = cpp_core.FeatureCalculator
    data = list(range(50))
    means = fc.rolling_mean(data, 5)
    assert len(means) == 50, "rolling_mean length mismatch"
    stds  = fc.rolling_std(data, 5)
    assert len(stds)  == 50, "rolling_std length mismatch"
    fft   = fc.fft_transform(data)
    assert len(fft)   == 50, "fft_transform length mismatch"
    # 检查C++扩展是否成功加载
    cpp_available = hasattr(cpp_core, 'FeatureCalculator')
    return f"CPP_AVAILABLE={cpp_available}"
check("cpp_core.FeatureCalculator rolling_mean/std/fft", test_cpp)

print()

# --- 3. 数据采集 ---
print("[DATA COLLECTION]")
def test_data():
    from src.core.data.collector import PL5DataCollectorV8
    c = PL5DataCollectorV8()
    df = c.load_processed_data()
    if df is None or len(df) == 0:
        df = c.update_data()
    assert df is not None and len(df) > 0, "no data loaded"
    return f"{len(df)} records, latest={df['period'].iloc[-1]}"
check("PL5DataCollectorV8.load/update_data", test_data)

print()

# --- 4. 特征工程 ---
print("[FEATURE ENGINEERING]")
def test_fe():
    from src.core.data.collector import PL5DataCollectorV8
    from src.core.features.engineer import FeatureEngineer
    c = PL5DataCollectorV8()
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

# --- 5. 系统监控 ---
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
