"""
端到端流水线快速验证脚本 V8.0
不做完整训练（耗时太长），而是：
1. 加载真实历史数据
2. 构建特征矩阵（前100条）
3. 用小批量数据训练 StackingEnsemble + HMM + EVM
4. 执行一次预测，验证输出格式
5. 验证 SelfLearning.record_evaluation() 可写入磁盘
"""
import sys, os, json, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "e2e_quick_v80.txt")
results = []

def step(label, fn):
    try:
        detail = fn()
        results.append(('PASS', label, detail or 'OK'))
        return True
    except Exception:
        results.append(('FAIL', label, traceback.format_exc().strip().split('\n')[-1]))
        return False

# ─── Step 1: 加载数据 ────────────────────────────────────────
import pandas as pd
import numpy as np

def s1():
    df = pd.read_csv(
        "data/processed/pl5_processed.csv",
        low_memory=False
    )
    # 存全局供后续使用
    globals()['_df'] = df
    return f'shape={df.shape}, cols={len(df.columns)}'
step('1. 加载历史数据', s1)

# ─── Step 2: 准备训练数据（取后200条） ───────────────────────
def s2():
    df = globals()['_df']
    pos_cols = ['wan', 'qian', 'bai', 'shi', 'ge']
    # 确认位置列存在
    missing = [c for c in pos_cols if c not in df.columns]
    if missing:
        raise ValueError(f"缺少位置列: {missing}")
    # 取后200条
    sub = df.tail(200).reset_index(drop=True)
    globals()['_sub'] = sub
    globals()['_pos_cols'] = pos_cols
    return f'sub.shape={sub.shape}'
step('2. 准备训练子集(后200条)', s2)

# ─── Step 3: 训练 HMM（万位） ────────────────────────────────
def s3():
    from src.core.models.predictor import HMMModel
    sub = globals()['_sub']
    m = HMMModel()
    m.fit(sub['wan'].values)
    p = m.predict_proba(int(sub['wan'].iloc[-1]))
    assert abs(p.sum() - 1.0) < 1e-6
    globals()['_hmm_wan'] = m
    return f'last_digit={int(sub["wan"].iloc[-1])}, top1={int(np.argmax(p))}'
step('3. HMM 训练(万位)', s3)

# ─── Step 4: 训练 ExtremeValueModel（万位） ─────────────────
def s4():
    from src.core.models.predictor import ExtremeValueModel
    sub = globals()['_sub']
    m = ExtremeValueModel()
    m.fit(sub['wan'].values)
    p = m.predict(sub['wan'].values)
    assert abs(p.sum() - 1.0) < 1e-6
    globals()['_evm_wan'] = m
    return f'omission={m.omission[:3].tolist()}'
step('4. EVM 训练(万位)', s4)

# ─── Step 5: 训练 BSTSModel（万位） ─────────────────────────
def s5():
    from src.core.models.predictor import BSTSModel
    sub = globals()['_sub']
    m = BSTSModel()
    m.fit(sub['wan'].values)
    p = m.predict(sub['wan'].values)
    assert abs(p.sum() - 1.0) < 1e-6
    globals()['_bsts_wan'] = m
    return f'top1={int(np.argmax(p))}'
step('5. BSTS 训练(万位)', s5)

# ─── Step 6: 训练 StackingEnsemble（万位，小批量）────────────
def s6():
    from src.core.models.predictor import StackingEnsemble
    sub = globals()['_sub']
    pos_cols = globals()['_pos_cols']

    # 过滤元数据列 + 位置列 + 数值列
    meta_cols = {'period', 'date', 'full_number', 'parse_line'}
    num_cols = [c for c in sub.columns
                if c not in pos_cols
                and c not in meta_cols
                and sub[c].dtype in [np.float64, np.int64, np.float32, np.int32]]

    # 如果特征不足，构造合成特征（基于数字统计）
    if len(num_cols) < 5:
        wan = sub['wan'].values.astype(int)
        digits = np.arange(10)
        # 每个数字的历史频率
        freq = np.array([np.sum(wan == d) / len(wan) for d in digits])
        # 每个数字的遗漏次数
        miss = np.zeros(10, dtype=float)
        for d in digits:
            idx = np.where(wan == d)[0]
            miss[d] = len(wan) - idx[-1] - 1 if len(idx) > 0 else len(wan)
        # 构造 DataFrame 特征（更新全局变量供 s7 使用）
        _sub = sub.copy()
        _sub['_freq'] = freq[wan]
        _sub['_miss_norm'] = miss[wan] / max(miss.max(), 1)
        _sub['_window_mean'] = pd.Series(wan).rolling(5, min_periods=1).mean().values
        _sub['_window_std'] = pd.Series(wan).rolling(5, min_periods=1).std().fillna(0).values
        num_cols = ['_freq', '_miss_norm', '_window_mean', '_window_std']
        sub = _sub
        globals()['_sub'] = _sub  # 更新全局变量！

    m = StackingEnsemble()
    m.fit_position_models(sub, num_cols)
    x_last = sub[num_cols].fillna(0).values[-1].astype(float)
    proba = m.predict_proba_position('wan', x_last)
    assert proba.shape == (10,), f'proba shape错误: {proba.shape}'
    assert abs(proba.sum() - 1.0) < 1e-6

    globals()['_stack_ens'] = m
    globals()['_num_cols'] = num_cols
    return f'features={len(num_cols)}, top1={int(np.argmax(proba))}'
step('6. StackingEnsemble 训练(万位)', s6)

# ─── Step 7: 贝叶斯融合预测 ─────────────────────────────────
def s7():
    from src.core.models.predictor import MODEL_WEIGHTS, _safe_proba, _top_k_from_proba
    
    sub = globals()['_sub']
    hmm = globals()['_hmm_wan']
    evm = globals()['_evm_wan']
    bsts = globals()['_bsts_wan']
    stack = globals()['_stack_ens']
    num_cols = globals()['_num_cols']
    
    x_last = sub[num_cols].fillna(0).values[-1]
    last_digit = int(sub['wan'].iloc[-1])
    
    p_hmm = hmm.predict_proba(last_digit)
    p_evm = evm.predict(sub['wan'].values)
    p_bsts = bsts.predict(sub['wan'].values)
    p_stack = stack.predict_proba_position('wan', x_last)
    
    w = MODEL_WEIGHTS
    # copula 权重分配给 hmm（copula 仅用于调整，不直接预测概率）
    copula_w = w['copula']
    p_fused = (w['stacking'] * p_stack + (w['hmm'] + copula_w) * p_hmm +
               w['bsts'] * p_bsts + w['evm'] * p_evm)
    p_fused /= p_fused.sum()
    
    top8 = _top_k_from_proba(p_fused, k=8)
    return f'top8={top8}'
step('7. 贝叶斯融合预测', s7)

# ─── Step 8: SelfLearning 写入测试 ───────────────────────────
def s8():
    from src.core.self_learning import SelfLearningSystem
    sl = SelfLearningSystem()
    before = len(sl.learning_history)
    sl.record_evaluation(0.52, {"test_run": True, "source": "e2e_quick_v80"})
    after = len(sl.learning_history)
    assert after == before + 1
    # 回滚（删掉刚才写的）
    sl.learning_history.pop()
    sl._save_history()
    return f'records before={before}, after record+rollback={len(sl.learning_history)}'
step('8. SelfLearning 写入+回滚', s8)

# ─── 输出 ────────────────────────────────────────────────────
pass_n = sum(1 for s,_,_ in results if s=='PASS')
fail_n = len(results) - pass_n

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('=' * 72 + '\n')
    f.write('PL5 V8.0 E2E Quick Validation\n')
    f.write('=' * 72 + '\n')
    for status, name, detail in results:
        icon = '[OK]' if status == 'PASS' else '[!!]'
        f.write(f'{icon} {status:4s} | {name:<38} | {detail}\n')
    f.write('=' * 72 + '\n')
    f.write(f'TOTAL: {pass_n} PASS / {fail_n} FAIL / {len(results)} steps\n')
    f.write('=' * 72 + '\n')

print(f'E2E Quick: {pass_n} PASS / {fail_n} FAIL')
print(f'Log: {OUT}')
sys.exit(0 if fail_n == 0 else 1)
