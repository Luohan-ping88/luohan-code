"""
测试完整的 T01+T02 组合场景
模拟 run_smoke.py 的实际执行顺序
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

results = []
def out(msg):
    results.append(msg)
    print(msg, flush=True)

out("=== Full Import Test (T01+T02 sequence) ===")

# T01: 全部模块导入
out("\n[T01] 模拟 run_smoke.py T01 导入...")
import_tests = [
    ("core.config", "setup_logging"),
    ("core.data_collector", "PL5DataCollector"),
    ("core.feature_engineering", "FeatureEngineer"),
    ("core.models", "PL5Predictor"),
    ("core.evaluator", "ModelEvaluator"),
    ("monitor.perfect_monitor", "PerfectSystemMonitor"),
    ("app.auto_scheduler", "AutoScheduler"),
    ("app.email_sender", "EmailSender"),
]
for mod_name, attr in import_tests:
    try:
        mod = __import__(mod_name, fromlist=[attr])
        obj = getattr(mod, attr, None)
        if obj is None:
            out(f"  [WARN] {mod_name}.{attr} not found")
        else:
            out(f"  [PASS] {mod_name}.{attr}")
    except Exception as e:
        import traceback
        out(f"  [FAIL] {mod_name}: {e}")
        out(traceback.format_exc()[:300])

# 检查 sys.modules
out(f"\n  sys.modules has 'cpp_core': {'cpp_core' in sys.modules}")

# T02: cpp_core 验证
out("\n[T02] 模拟 run_smoke.py T02 cpp_core 验证...")
try:
    import cpp_core
    out(f"  OK: import cpp_core CPP_AVAILABLE={cpp_core.CPP_AVAILABLE}")
    fc = cpp_core.FeatureCalculator
    data = list(range(50))
    m = fc.rolling_mean(data, 5)
    s = fc.rolling_std(data, 5)
    f = fc.fft_transform(data)
    out(f"  OK: rolling_mean/std/fft len={len(m)}/{len(s)}/{len(f)}")
    out(f"  [PASS] T02 OK")
except Exception as e:
    import traceback
    out(f"  [WARN] {e}")
    out(traceback.format_exc()[:300])

out("\n=== Full Import Test DONE ===")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_full_import_result.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
