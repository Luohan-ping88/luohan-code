import sys
sys.path.insert(0, '.')
print("Testing cpp_core import...")
try:
    import cpp_core
    print(f"cpp_core imported OK, CPP_AVAILABLE={cpp_core.CPP_AVAILABLE}")
    fc = cpp_core.FeatureCalculator
    data = list(range(20))
    m = fc.rolling_mean(data, 5)
    print(f"rolling_mean OK, len={len(m)}, last={m[-1]:.2f}")
    s = fc.rolling_std(data, 5)
    print(f"rolling_std OK, len={len(s)}")
    print("ALL OK")
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
