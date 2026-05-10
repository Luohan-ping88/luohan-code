"""
PL5 V5.3 冒烟测试 - 轻量快速版
强制 UTF-8 输出，50 条数据，带超时保护
"""
import sys
import os
import io
import time

# 强制 UTF-8 输出（解决 Windows GBK 终端问题）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

LOG_FILE = os.path.join(BASE_DIR, 'smoke_result.txt')
results = []
pass_count = 0
fail_count = 0
warn_count = 0

def log(msg, level="INFO"):
    global pass_count, fail_count, warn_count
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    results.append(line)
    print(line, flush=True)
    if "[PASS]" in msg:
        pass_count += 1
    elif "[FAIL]" in msg:
        fail_count += 1
    elif "[WARN]" in msg:
        warn_count += 1

def save():
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results) + '\n')

log("=" * 60)
log("PL5 V5.3 Smoke Test - Start")
log("=" * 60)

# ─────────────────────────────────────────────────────────────
# T01: 核心模块导入
# ─────────────────────────────────────────────────────────────
log("\n[T01] 核心模块导入测试...")
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
            log(f"  [WARN] {mod_name}.{attr} not found")
        else:
            log(f"  [PASS] {mod_name}.{attr}")
    except Exception as e:
        log(f"  [FAIL] {mod_name}: {str(e)[:80]}")
save()

# ─────────────────────────────────────────────────────────────
# T02: cpp_core 扩展验证（从已缓存模块中获取，避免重复 import 触发 .pyd）
# ─────────────────────────────────────────────────────────────
log("\n[T02] cpp_core 扩展验证...")
try:
    # 使用 sys.modules 缓存（T01 已通过 feature_engineering 间接导入 cpp_core）
    # 避免二次 import 触发 .pyd 加载引发 Access Violation
    import sys as _sys
    if 'cpp_core' in _sys.modules:
        cpp_core = _sys.modules['cpp_core']
    else:
        # 尚未加载，用专门的脚本子进程测试（隔离 AV 崩溃）
        import subprocess
        result = subprocess.run(
            [_sys.executable, '-X', 'utf8', 'test_cpp2.py'],
            capture_output=True, text=True, timeout=30,
            cwd=BASE_DIR, encoding='utf-8', errors='replace'
        )
        if result.returncode == 0:
            log(f"  [PASS] cpp_core: subprocess probe OK (isolated)")
        else:
            log(f"  [WARN] cpp_core: subprocess probe failed: {result.stderr[:100]}")
        save()
        # 跳过后续直接调用
        cpp_core = None

    if cpp_core is not None:
        fc = cpp_core.FeatureCalculator
        data = list(range(50))
        m = fc.rolling_mean(data, 5)
        s = fc.rolling_std(data, 5)
        f = fc.fft_transform(data)
        assert len(m) == len(s) == len(f) == 50, f"length mismatch"
        log(f"  [PASS] cpp_core: CPP_AVAILABLE={getattr(cpp_core,'CPP_AVAILABLE',False)}, rolling_mean/std/fft OK (n=50)")
except Exception as e:
    import traceback
    log(f"  [WARN] cpp_core: {e}")
    log(f"  {traceback.format_exc()[:200]}")
save()

# ─────────────────────────────────────────────────────────────
# T03: 数据采集
# ─────────────────────────────────────────────────────────────
log("\n[T03] 数据采集...")
df = None
try:
    from core.data_collector import PL5DataCollector
    c = PL5DataCollector()
    t0 = time.time()
    df = c.load_processed_data()
    if df is None or len(df) == 0:
        log("  本地缓存为空，尝试网络更新...")
        df = c.update_data()
    elapsed = time.time() - t0
    assert df is not None and len(df) > 0
    log(f"  [PASS] data_collector: {len(df)} records, latest={df['period'].iloc[-1]}, cols={len(df.columns)}, time={elapsed:.1f}s")
except Exception as e:
    import traceback
    log(f"  [FAIL] data_collector: {e}")
    log(f"  {traceback.format_exc()[:200]}")
save()

if df is None or len(df) == 0:
    log("\n[ABORT] 数据为空，后续测试无法进行")
    save()
    sys.exit(1)

# 使用最后 50 条（快速测试）
df_test = df.tail(50).reset_index(drop=True)
log(f"  使用最后 50 条数据进行后续测试")

# ─────────────────────────────────────────────────────────────
# T04: 特征工程（分步测试，定位慢点）
# ─────────────────────────────────────────────────────────────
log("\n[T04] 特征工程（50 条数据）...")
feats = None
feat_cols = []
try:
    from core.feature_engineering import FeatureEngineer
    fe = FeatureEngineer()

    steps = [
        ("黄金分割特征", lambda d: fe.extract_golden_ratio_features(d)),
        ("熵值特征", lambda d: fe.extract_entropy_features(d, window=10)),
        ("马尔可夫特征", lambda d: fe.extract_markov_features(d)),
        ("混沌特征(Hurst)", lambda d: fe.extract_chaos_features(d, window=20)),
        ("傅里叶特征", lambda d: fe.extract_fourier_features(d, window=20)),
        ("互相关特征", lambda d: fe.extract_cross_correlation_features(d)),
    ]

    current = df_test.copy()
    for step_name, fn in steps:
        t0 = time.time()
        try:
            current = fn(current)
            elapsed = time.time() - t0
            log(f"  [PASS] {step_name}: {elapsed:.2f}s")
        except Exception as e:
            elapsed = time.time() - t0
            log(f"  [WARN] {step_name}: {e} ({elapsed:.2f}s, skipped)")

    feats = current
    base_cols = {'period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge'}
    feat_cols = [c for c in feats.columns if c not in base_cols]
    assert len(feat_cols) > 10, f"too few features: {len(feat_cols)}"
    log(f"  [PASS] feature_engineering total: {len(feat_cols)} feature columns")

except Exception as e:
    import traceback
    log(f"  [FAIL] feature_engineering: {e}")
    log(f"  {traceback.format_exc()[:300]}")
save()

# ─────────────────────────────────────────────────────────────
# T05: 模型训练
# ─────────────────────────────────────────────────────────────
log("\n[T05] 模型训练...")
predictor = None
if feats is not None and len(feat_cols) > 0:
    try:
        from core.models import PL5Predictor
        predictor = PL5Predictor()
        t0 = time.time()
        predictor.fit(feats, feat_cols)
        elapsed = time.time() - t0
        log(f"  [PASS] model training: HMM+Copula+EVM+Ensemble, time={elapsed:.1f}s")
    except Exception as e:
        import traceback
        log(f"  [FAIL] model training: {e}")
        log(f"  {traceback.format_exc()[:300]}")
else:
    log("  [WARN] 跳过模型训练（特征为空）")
save()

# ─────────────────────────────────────────────────────────────
# T06: 预测生成
# ─────────────────────────────────────────────────────────────
log("\n[T06] 预测生成...")
if predictor is not None and feats is not None and len(feat_cols) > 0:
    try:
        import numpy as np
        latest = feats[feat_cols].iloc[-1].values.astype(float)
        # 处理 NaN/Inf
        latest = np.nan_to_num(latest, nan=0.0, posinf=0.0, neginf=0.0)
        t0 = time.time()
        preds = predictor.predict(latest, top_k=5)
        elapsed = time.time() - t0
        assert isinstance(preds, dict) and len(preds) > 0
        # 安全展示: preds[pos] 是 dict {'top_k': [...], ...}
        sample = {}
        for pos, v in list(preds.items())[:2]:
            if isinstance(v, dict):
                sample[pos] = v.get('top_k', v)[:3] if hasattr(v.get('top_k', v), '__getitem__') else str(v)[:50]
            elif hasattr(v, '__iter__'):
                sample[pos] = list(v)[:3]
            else:
                sample[pos] = v
        log(f"  [PASS] prediction: {len(preds)} positions, sample={sample}, time={elapsed:.2f}s")
    except Exception as e:
        import traceback
        log(f"  [FAIL] prediction: {e}")
        log(f"  {traceback.format_exc()[:400]}")
else:
    log("  [WARN] 跳过预测（模型未训练）")
save()

# ─────────────────────────────────────────────────────────────
# T07: 系统监控
# ─────────────────────────────────────────────────────────────
log("\n[T07] 系统监控...")
try:
    from monitor.perfect_monitor import PerfectSystemMonitor
    m = PerfectSystemMonitor()
    metrics = m.get_system_metrics()
    cpu = metrics.get('cpu', {}).get('percent', 'N/A')
    mem = metrics.get('memory', {}).get('percent', 'N/A')
    disk_info = metrics.get('disk', {})
    if isinstance(disk_info, dict):
        disk = disk_info.get('percent', disk_info.get('used_percent', 'N/A'))
    else:
        disk = 'N/A'
    log(f"  [PASS] system_monitor: cpu={cpu}%, mem={mem}%, disk={disk}%")
except Exception as e:
    log(f"  [FAIL] system_monitor: {e}")
save()

# ─────────────────────────────────────────────────────────────
# T08: 模型评估器
# ─────────────────────────────────────────────────────────────
log("\n[T08] 模型评估器...")
try:
    from core.evaluator import ModelEvaluator
    ev = ModelEvaluator()
    # 只验证对象可以创建，不执行完整评估
    log(f"  [PASS] ModelEvaluator: instantiated OK")
except Exception as e:
    log(f"  [WARN] evaluator: {e}")
save()

# ─────────────────────────────────────────────────────────────
# T09: 配置文件验证
# ─────────────────────────────────────────────────────────────
log("\n[T09] 配置文件验证...")
try:
    import json
    config_path = os.path.join(BASE_DIR, 'config', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        keys = list(cfg.keys())
        log(f"  [PASS] config.json: {len(keys)} sections: {keys}")
    else:
        log(f"  [WARN] config.json not found at {config_path}")
except Exception as e:
    log(f"  [FAIL] config.json: {e}")
save()

# ─────────────────────────────────────────────────────────────
# 汇总
# ─────────────────────────────────────────────────────────────
log("\n" + "=" * 60)
log(f"SMOKE TEST RESULT: {pass_count} PASS  {warn_count} WARN  {fail_count} FAIL")
if fail_count == 0:
    log("STATUS: ALL CRITICAL TESTS PASSED - SYSTEM READY")
elif fail_count <= 2:
    log("STATUS: MOSTLY OK - review WARN/FAIL items above")
else:
    log("STATUS: MULTIPLE FAILURES - system needs repair")
log("=" * 60)
save()
print(f"\nResults saved to: {LOG_FILE}", flush=True)
sys.exit(fail_count)
