"""
V8.0 冒烟测试 - 修复版 (清除字节码缓存)
"""
import sys, os

# 强制禁用 pyc 缓存
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 清除已导入的模块缓存
import importlib
for mod_name in list(sys.modules.keys()):
    if 'src.core' in mod_name or 'core.' in mod_name:
        del sys.modules[mod_name]

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "smoke_v80.txt")

lines = []
results = []

def chk(label, fn):
    try:
        detail = fn()
        results.append(('PASS', label, detail or 'OK'))
    except Exception as e:
        results.append(('FAIL', label, str(e)[:200]))

def t1():
    from core.config import BASE_DIR, setup_logging, LOGS_DIR, DATA_DIR, MODELS_DIR
    return f'BASE_DIR={BASE_DIR.name}'
chk('1. core.config', t1)

def t2():
    from core.utils import logger, log_execution_time, log_exception
    return 'logger/decorator OK'
chk('2. core.utils', t2)

def t3():
    from src.core.models.predictor import PL5Predictor, HMMModel, StackingEnsemble, MODEL_WEIGHTS
    w_sum = sum(MODEL_WEIGHTS.values())
    return f'weights_sum={w_sum:.3f}'
chk('3. predictor+MODEL_WEIGHTS', t3)

def t4():
    from src.core.models.predictor import HMMModel
    import numpy as np
    np.random.seed(42)
    data = np.random.randint(0, 10, 200)
    m = HMMModel(); m.fit(data)
    proba = m.predict_proba(7)
    s = abs(proba.sum() - 1.0)
    return f'proba_sum_err={s:.2e}'
chk('4. HMM fit+predict', t4)

def t5():
    from src.core.self_learning import SelfLearningSystem
    sl = SelfLearningSystem()
    r = sl.evaluate_recent_performance()
    return f'records={r["total_records"]}, acc={r["recent_performance"]["accuracy"]:.4f}'
chk('5. SelfLearning', t5)

def t6():
    from src.core.self_learning import SelfLearningSystem
    sl = SelfLearningSystem()
    should, reason = sl.should_trigger_retrain()
    sug = sl.generate_optimization_suggestions()
    return f'retrain={should}, suggestions={len(sug)}'
chk('6. SelfLearning retrain', t6)

def t7():
    from src.core.orchestrator import PL5Orchestrator
    return 'OK'
chk('7. orchestrator', t7)

def t8():
    from src.core.data.config import RAW_DATA_DIR, PROCESSED_DATA_DIR
    raw = (RAW_DATA_DIR / 'pl5_history.txt').exists()
    proc = (PROCESSED_DATA_DIR / 'pl5_processed.csv').exists()
    return f'raw={raw}, processed={proc}'
chk('8. data paths', t8)

def t9():
    from src.core.features import FeatureEngineer
    return f'FeatureEngineer={FeatureEngineer.__name__}'
chk('9. FeatureEngineer', t9)

def t10():
    import sys as _sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in _sys.path:
        _sys.path.insert(0, root)
    from monitor.system_monitor import SystemMonitor
    return 'OK'
chk('10. SystemMonitor', t10)

def t11():
    import asyncio
    from src.core.utils.logger import log_execution_time
    @log_execution_time('test')
    async def async_fn(x):
        return x * 2
    print("DEBUG: Is coroutine:", asyncio.iscoroutinefunction(async_fn))
    result = asyncio.run(async_fn(21))
    assert result == 42
    return f'async result={result}'
chk('11. async decorator', t11)

def t12():
    from src.core.data import DataLoader
    return f'DataLoader={DataLoader.__name__}'
chk('12. DataLoader', t12)

# Write results
pass_n = sum(1 for s,_,_ in results if s=='PASS')
fail_n = len(results) - pass_n

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('=' * 72 + '\n')
    f.write('PL5 V8.0 Smoke Test (clean)\n')
    f.write('=' * 72 + '\n')
    for status, name, detail in results:
        icon = '[OK]' if status == 'PASS' else '[!!]'
        f.write(f'{icon} {status:4s} | {name:<30} | {detail}\n')
    f.write('=' * 72 + '\n')
    f.write(f'TOTAL: {pass_n} PASS / {fail_n} FAIL / {len(results)} items\n')
    f.write('=' * 72 + '\n')

print(f'Results written to: {OUT}')
print(f'TOTAL: {pass_n} PASS / {fail_n} FAIL / {len(results)} items')
sys.exit(0 if fail_n == 0 else 1)
