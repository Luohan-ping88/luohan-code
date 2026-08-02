#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 条件概率预测器 - 利用时序依赖信号改变号码筛选逻辑

核心论点
========
ACF信号虽弱(0.02~0.04), 但"只要存在, 就足以改变号码筛选逻辑"。
Top-8预测不需要解释大量方差, 只需在排序边界(第8/第9名)做出正确区分。

本脚本直接实证: 把ACF/周期/Markov条件概率接入Top-8筛选, 回测是否提升。

策略对比
========
1. 条件概率排序: P(digit | last_digit) - 利用1阶Markov
2. 条件概率偏离: P(digit|last) - P(digit) 的偏离度作为信号
3. 多阶Markov: P(digit | last_2, last_1)
4. 周期条件: P(digit | period % T)
5. ACF加权: 用各数字ACF@1作为频率排序的调整项
6. 条件贝叶斯: 用条件概率修正边际频率的贝叶斯估计
7. 综合最优: 多信号融合
"""

import sys, os, csv, json, time
import numpy as np
from collections import defaultdict, Counter
from pathlib import Path
from datetime import datetime
from scipy import stats as scipy_stats

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
DATA_FILE = PROJECT_ROOT / "data" / "processed" / "pl5_processed.csv"
OUTPUT_DIR = PROJECT_ROOT / "logs"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_history():
    rows = list(csv.DictReader(open(DATA_FILE, 'r', encoding='utf-8-sig')))
    history = {pos: [int(r[pos]) for r in rows if r.get(pos) not in (None, '')] for pos in POSITIONS}
    periods = [r.get('period') for r in rows]
    return history, periods


def random_top8(seq=None, last=None, last2=None, period_idx=None, ctx=None):
    return np.random.choice(10, 8, replace=False).tolist()


def marginal_freq_top8(seq):
    """边际频率排序"""
    if not seq:
        return list(range(8))
    counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            counts[d] += 1
    return np.argsort(counts)[::-1][:8].tolist()


def markov_cond_top8(seq, last, trans_counts):
    """1阶Markov条件概率: P(digit|last) 排序"""
    if last is None or last not in trans_counts or not trans_counts[last]:
        return marginal_freq_top8(seq)
    counts = np.zeros(10)
    total = 0
    for d, c in trans_counts[last].items():
        if 0 <= d < 10:
            counts[d] = c
            total += c
    if total == 0:
        return marginal_freq_top8(seq)
    return np.argsort(counts)[::-1][:8].tolist()


def markov_deviation_top8(seq, last, trans_counts, alpha=5.0):
    """条件概率偏离: P(d|last) - P(d) 的偏离度
    只在条件概率显著偏离边际时才改变选择。
    用贝叶斯收缩: posterior = (alpha*marginal + cond_counts) / (alpha + total_cond)
    alpha越大越保守(偏向边际), 越小越激进(偏向条件)
    """
    if last is None or last not in trans_counts or not trans_counts[last]:
        return marginal_freq_top8(seq)
    # 边际频率
    marg_counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            marg_counts[d] += 1
    marg_total = marg_counts.sum()
    if marg_total == 0:
        return list(range(8))
    marg_p = marg_counts / marg_total
    # 条件频率
    cond_counts = np.zeros(10)
    cond_total = 0
    for d, c in trans_counts[last].items():
        if 0 <= d < 10:
            cond_counts[d] = c
            cond_total += c
    if cond_total == 0:
        return marginal_freq_top8(seq)
    cond_p = cond_counts / cond_total
    # 贝叶斯收缩: 在边际和条件之间加权
    # alpha是边际的伪计数权重
    shrunk_p = (alpha * marg_p + cond_counts) / (alpha + cond_total)
    return np.argsort(shrunk_p)[::-1][:8].tolist()


def markov_2nd_order_top8(seq, last2, last1, trans2_counts):
    """2阶Markov: P(digit | last2, last1)"""
    key = (last2, last1)
    if last2 is None or last1 is None or key not in trans2_counts or not trans2_counts[key]:
        # 回退到1阶
        return marginal_freq_top8(seq)
    counts = np.zeros(10)
    total = 0
    for d, c in trans2_counts[key].items():
        if 0 <= d < 10:
            counts[d] = c
            total += c
    if total == 0:
        return marginal_freq_top8(seq)
    # 贝叶斯收缩避免过拟合
    marg_counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            marg_counts[d] += 1
    marg_total = marg_counts.sum()
    marg_p = marg_counts / marg_total if marg_total > 0 else np.ones(10)/10
    alpha = 10.0  # 2阶更稀疏, 用更大alpha
    shrunk_p = (alpha * marg_p + counts) / (alpha + total)
    return np.argsort(shrunk_p)[::-1][:8].tolist()


def period_conditional_top8(seq, period_idx, period_T, period_counts):
    """周期条件: P(digit | period % T)"""
    bucket = period_idx % period_T
    if bucket not in period_counts or not period_counts[bucket]:
        return marginal_freq_top8(seq)
    counts = np.zeros(10)
    total = 0
    for d, c in period_counts[bucket].items():
        if 0 <= d < 10:
            counts[d] = c
            total += c
    if total == 0:
        return marginal_freq_top8(seq)
    # 贝叶斯收缩
    marg_counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            marg_counts[d] += 1
    marg_total = marg_counts.sum()
    marg_p = marg_counts / marg_total if marg_total > 0 else np.ones(10)/10
    alpha = 8.0
    shrunk_p = (alpha * marg_p + counts) / (alpha + total)
    return np.argsort(shrunk_p)[::-1][:8].tolist()


def acf_weighted_freq_top8(seq, acf_lag1, gamma=5.0):
    """ACF加权频率排序
    用各数字的ACF@1作为边际频率的调整项:
    - ACF@1 > 0 (聚集): 该数字近期出现 → 提升排序
    - ACF@1 < 0 (反聚集): 该数字近期出现 → 降低排序
    score = freq + gamma * acf * recent_appearance
    """
    if not seq:
        return list(range(8))
    # 边际频率
    counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            counts[d] += 1
    marg_p = counts / counts.sum()
    # 最近是否出现(last 3期)
    recent_3 = seq[-3:] if len(seq) >= 3 else seq
    recent_appear = np.zeros(10)
    for d in recent_3:
        if 0 <= d < 10:
            recent_appear[d] = 1.0
    # ACF调整: acf_lag1是各数字的ACF@1
    if acf_lag1 is None or len(acf_lag1) != 10:
        return np.argsort(marg_p)[::-1][:8].tolist()
    # 调整: 聚集数字(acf>0)近期出现→提升; 反聚集(acf<0)近期出现→降低
    adjustment = gamma * np.array(acf_lag1) * recent_appear
    score = marg_p + adjustment
    return np.argsort(score)[::-1][:8].tolist()


def combined_conditional_top8(seq, last, last2, period_idx, ctx):
    """综合条件策略: 多信号贝叶斯融合
    融合: 边际频率 + 1阶Markov + 周期条件 + ACF调整
    每个信号用贝叶斯收缩避免过拟合
    """
    if not seq:
        return list(range(8))
    # 边际
    marg_counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            marg_counts[d] += 1
    marg_total = marg_counts.sum()
    if marg_total == 0:
        return list(range(8))
    marg_p = marg_counts / marg_total
    
    # 1阶Markov条件
    trans_counts = ctx['trans1']
    cond_p_markov = marg_p.copy()
    if last is not None and last in trans_counts and trans_counts[last]:
        cond_counts = np.zeros(10)
        ct = 0
        for d, c in trans_counts[last].items():
            if 0 <= d < 10:
                cond_counts[d] = c
                ct += c
        if ct > 0:
            alpha_m = 6.0
            cond_p_markov = (alpha_m * marg_p + cond_counts) / (alpha_m + ct)
    
    # 周期条件
    period_counts = ctx['period']
    cond_p_period = marg_p.copy()
    bucket = period_idx % ctx['period_T']
    if bucket in period_counts and period_counts[bucket]:
        pc = np.zeros(10)
        pt = 0
        for d, c in period_counts[bucket].items():
            if 0 <= d < 10:
                pc[d] = c
                pt += c
        if pt > 0:
            alpha_p = 10.0
            cond_p_period = (alpha_p * marg_p + pc) / (alpha_p + pt)
    
    # ACF调整
    acf_lag1 = ctx.get('acf1', np.zeros(10))
    recent_3 = seq[-3:] if len(seq) >= 3 else seq
    recent_appear = np.zeros(10)
    for d in recent_3:
        if 0 <= d < 10:
            recent_appear[d] = 1.0
    acf_adjust = 0.05 * np.array(acf_lag1) * recent_appear  # 小幅度调整
    
    # 融合: Markov和周期加权平均, 再加ACF调整
    fused = 0.5 * cond_p_markov + 0.3 * cond_p_period + 0.2 * marg_p + acf_adjust
    return np.argsort(fused)[::-1][:8].tolist()


def run_analysis(test_size=300, burn_in=1000):
    log("=" * 90)
    log("PL5 条件概率预测器 - 利用时序依赖改变筛选逻辑")
    log("=" * 90)
    log("论点: ACF信号虽弱, 但只要存在就足以改变边界决策, 提升Top-8")

    history, periods = load_history()
    total = len(history['wan'])
    log(f"历史: {total} 期")

    # 预计算每个位置的ACF@1(用全部历史)
    log("\n预计算各位置ACF@1...")
    acf_all = {}
    for pos in POSITIONS:
        seq = history[pos]
        acf_all[pos] = np.zeros(10)
        for d in range(10):
            binary = np.array([1 if x == d else 0 for x in seq])
            n = len(binary)
            if n < 100:
                continue
            binary = binary - binary.mean()
            var = np.var(binary)
            if var < 1e-8:
                continue
            acf_all[pos][d] = float(np.sum(binary[:-1] * binary[1:]) / (n * var))
        log(f"  {pos}: ACF@1范围 [{acf_all[pos].min():.4f}, {acf_all[pos].max():.4f}], "
            f"正数个数={int((acf_all[pos] > 0).sum())}, 负数个数={int((acf_all[pos] < 0).sum())}")

    start_idx = total - test_size
    # 策略
    strategies = {
        'random': random_top8,
        'marginal_freq': lambda s, l, l2, p, c: marginal_freq_top8(s),
        'markov_1st': lambda s, l, l2, p, c: markov_cond_top8(s, l, c['trans1']),
        'markov_deviation_a6': lambda s, l, l2, p, c: markov_deviation_top8(s, l, c['trans1'], 6.0),
        'markov_deviation_a3': lambda s, l, l2, p, c: markov_deviation_top8(s, l, c['trans1'], 3.0),
        'markov_deviation_a1': lambda s, l, l2, p, c: markov_deviation_top8(s, l, c['trans1'], 1.0),
        'markov_2nd': lambda s, l, l2, p, c: markov_2nd_order_top8(s, l2, l, c['trans2']),
        'period_T7': lambda s, l, l2, p, c: period_conditional_top8(s, p, 7, c['period7']),
        'period_T14': lambda s, l, l2, p, c: period_conditional_top8(s, p, 14, c['period14']),
        'acf_weighted_g5': lambda s, l, l2, p, c: acf_weighted_freq_top8(s, c['acf1'], 5.0),
        'acf_weighted_g10': lambda s, l, l2, p, c: acf_weighted_freq_top8(s, c['acf1'], 10.0),
        'combined': lambda s, l, l2, p, c: combined_conditional_top8(s, l, l2, p, c),
    }
    stats = {name: defaultdict(lambda: {'hits': 0, 'total': 0}) for name in strategies}

    log(f"\n开始滚动回测, 测试 {test_size} 期")
    t0 = time.time()
    for t in range(start_idx, total):
        if (t - start_idx) % 100 == 0:
            log(f"  进度: {t-start_idx}/{test_size}  耗时: {time.time()-t0:.1f}s")
        # 构建上下文
        for pos in POSITIONS:
            seq_p = history[pos][:t]
            # 1阶转移
            trans1 = defaultdict(lambda: defaultdict(int))
            for i in range(len(seq_p) - 1):
                trans1[seq_p[i]][seq_p[i+1]] += 1
            # 2阶转移
            trans2 = defaultdict(lambda: defaultdict(int))
            for i in range(len(seq_p) - 2):
                trans2[(seq_p[i], seq_p[i+1])][seq_p[i+2]] += 1
            # 周期条件(period_idx用历史索引)
            period7 = defaultdict(lambda: defaultdict(int))
            period14 = defaultdict(lambda: defaultdict(int))
            for i in range(len(seq_p)):
                period7[i % 7][seq_p[i]] += 1
                period14[i % 14][seq_p[i]] += 1
            ctx = {
                'trans1': trans1, 'trans2': trans2,
                'period7': period7, 'period14': period14,
                'period_T': 7, 'period': period7,
                'acf1': acf_all[pos],
            }
            actual = history[pos][t]
            seq = history[pos][:t]
            last = seq[-1] if seq else None
            last2 = seq[-2] if len(seq) >= 2 else None
            period_idx = t
            for name, func in strategies.items():
                top8 = func(seq, last, last2, period_idx, ctx)
                stats[name][pos]['hits'] += int(actual in top8)
                stats[name][pos]['total'] += 1

    log(f"\n回测完成, 耗时: {time.time()-t0:.1f}s")
    log("")
    log("=" * 95)
    log("条件概率策略 Top-8 命中率对比")
    log("=" * 95)
    log(f"{'策略':<24} {'万位':>8} {'千位':>8} {'百位':>8} {'十位':>8} {'个位':>8} {'整体':>8} {'vs随机':>10} {'vs80%':>10}")
    log("-" * 95)

    results = {}
    random_overall = None
    for name in stats:
        pos_rates = {}
        oh, ot = 0, 0
        for pos in POSITIONS:
            s = stats[name][pos]
            r = s['hits']/s['total'] if s['total'] > 0 else 0
            pos_rates[pos] = r
            oh += s['hits']; ot += s['total']
        overall = oh/ot if ot > 0 else 0
        results[name] = {'per_pos': pos_rates, 'overall': overall}
        if name == 'random':
            random_overall = overall

    for name in sorted(results.keys(), key=lambda x: results[x]['overall'], reverse=True):
        r = results[name]
        diff_rnd = (r['overall'] - random_overall) * 100 if random_overall else 0
        diff_80 = (r['overall'] - 0.80) * 100
        marker = " ★突破80" if r['overall'] > 0.80 else ""
        log(f"{name:<24} {r['per_pos']['wan']*100:>7.2f}% {r['per_pos']['qian']*100:>7.2f}% "
            f"{r['per_pos']['bai']*100:>7.2f}% {r['per_pos']['shi']*100:>7.2f}% "
            f"{r['per_pos']['ge']*100:>7.2f}% {r['overall']*100:>7.2f}% {diff_rnd:>+9.2f}pp {diff_80:>+9.2f}pp{marker}")

    log("-" * 95)
    log(f"{'随机基线(理论)':<24} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8}")

    # 分析: 条件信号是否真的改变了选择?
    log("\n" + "=" * 95)
    log("信号有效性分析")
    log("=" * 95)
    log(f"随机实测: {random_overall*100:.2f}%")
    breakthrough = [(n, results[n]['overall']) for n in results if results[n]['overall'] > 0.80]
    if breakthrough:
        log(f"\n突破80%的策略:")
        for n, r in sorted(breakthrough, key=lambda x: -x[1]):
            log(f"  {n}: {r*100:.2f}%  (vs随机 {(r-random_overall)*100:+.2f}pp, vs80% {(r-0.80)*100:+.2f}pp)")
    else:
        log(f"\n所有策略未突破80%")
    
    best_name = max(results.keys(), key=lambda x: results[x]['overall'])
    best = results[best_name]
    log(f"\n最优策略: {best_name} = {best['overall']*100:.2f}%")
    log(f"  vs 随机: {(best['overall']-random_overall)*100:+.2f}pp")
    log(f"  vs 80%: {(best['overall']-0.80)*100:+.2f}pp")
    
    # 关键问题: 条件信号是否改变了选择(对比边际频率)?
    log(f"\n关键对比(条件信号 vs 边际频率):")
    marg_rate = results['marginal_freq']['overall']
    for n in ['markov_1st', 'markov_deviation_a6', 'markov_deviation_a3', 'markov_deviation_a1',
              'markov_2nd', 'acf_weighted_g5', 'acf_weighted_g10', 'combined']:
        if n in results:
            r = results[n]['overall']
            log(f"  {n}: {r*100:.2f}%  vs边际 {(r-marg_rate)*100:+.2f}pp")

    report = {
        'timestamp': datetime.now().isoformat(),
        'acf_all': {pos: acf_all[pos].tolist() for pos in POSITIONS},
        'strategy_results': {n: results[n] for n in results},
        'best_strategy': best_name,
        'best_overall': best['overall'],
        'random_overall': random_overall,
        'breakthrough_strategies': breakthrough,
    }
    rp = OUTPUT_DIR / f"conditional_predictor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(rp, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    log(f"\n报告已保存: {rp}")
    return report


if __name__ == "__main__":
    run_analysis(test_size=300, burn_in=1000)
