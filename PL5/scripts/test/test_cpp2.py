import sys, os
sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

results = []

def out(msg):
    results.append(msg)
    print(msg, flush=True)

out("=== cpp_core 诊断测试 ===")

# Step 1: 测试 pl5_core.py 直接导入
out("\n[Step1] 测试 cpp_core.pl5_core 直接导入...")
try:
    import cpp_core.pl5_core as pl5
    out(f"  OK: pl5_core 导入成功")
    fc = pl5.FeatureCalculator
    out(f"  OK: FeatureCalculator = {fc}")
except Exception as e:
    import traceback
    out(f"  FAIL: {e}")
    out(traceback.format_exc())

# Step 2: 测试 cpp_core 包导入
out("\n[Step2] 测试 import cpp_core (包导入)...")
try:
    import cpp_core
    out(f"  OK: cpp_core 导入成功, CPP_AVAILABLE={cpp_core.CPP_AVAILABLE}")
except Exception as e:
    import traceback
    out(f"  FAIL: {e}")
    out(traceback.format_exc())

# Step 3: 测试 FeatureCalculator 功能
out("\n[Step3] 测试 FeatureCalculator 功能...")
try:
    data = list(range(50))
    m = cpp_core.FeatureCalculator.rolling_mean(data, 5)
    s = cpp_core.FeatureCalculator.rolling_std(data, 5)
    f = cpp_core.FeatureCalculator.fft_transform(data)
    out(f"  OK: rolling_mean len={len(m)}, rolling_std len={len(s)}, fft len={len(f)}")
    out(f"  Sample mean[10:15]: {m[10:15]}")
except Exception as e:
    import traceback
    out(f"  FAIL: {e}")
    out(traceback.format_exc())

out("\n=== 诊断完成 ===")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_cpp2_result.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
