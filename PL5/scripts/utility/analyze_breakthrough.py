#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 突破80%随机基线 - 深度分析与策略发现

核心问题
========
回测发现补集消除预测器(78.73%) < 随机基线(80.33%)。
根因: exclusion 信号 = inclusion 信号的反转, 融合后无效。
本脚本验证:
1. PL5 数字分布是否真均匀 (chi-square)
2. 反频率策略 (选频率最低的8个) 是否有效
3. anti-persistence (排除最近出现过的) 是否有效
4. 冷号补涨效应是否存在
5. Markov 条件概率是否有信号
6. 综合最优策略
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
    rows = []
    with open(DATA_FILE, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    history = {pos: [] for pos in POSITIONS}
    for r in rows:
        for pos in POSITIONS:
            v = r.get(pos)
            if v is None or v == '':
                continue
            try:
                history[pos].append(int(v))
            except Exception:
                pass
    return history, rows


def random_top8(seq=None):
    return np.random.choice(10, 8, replace=False).tolist()


def freq_high_top8(seq):
    """选频率最高的8个 (排除频率最低的2个)"""
    if not seq:
        return list(range(8))
    counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            counts[d] += 1
    return np.argsort(counts)[::-1][:8].tolist()


def freq_low_top8(seq):
    """选频率最低的8个 (排除频率最高的2个) - 反频率策略"""
    if not seq:
        return list(range(8))
    counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            counts[d] += 1
    return np.argsort(counts)[:8].tolist()


def recent_freq_high_top8(seq, window=50):
    """最近window期频率最高"""
    if not seq:
        return list(range(8))
    recent = seq[-window:]
    counts = np.zeros(10)
    for d in recent:
        if 0 <= d < 10:
            counts[d] += 1
    return np.argsort(counts)[::-1][:8].tolist()


def recent_freq_low_top8(seq, window=50):
    """最近window期频率最低 - 短期反频率"""
    if not seq:
        return list(range(8))
    recent = seq[-window:]
    counts = np.zeros(10)
    for d in recent:
        if 0 <= d < 10:
            counts[d] += 1
    return np.argsort(counts)[:8].tolist()


def anti_persistence_top8(seq, window=5):
    """anti-persistence: 排除最近window期出现过的数字"""
    if not seq:
        return list(range(8))
    recent = seq[-window:]
    appeared = set(recent)
    # 优先选未出现过的, 不足8个再用出现过的补
    not_appeared = [d for d in range(10) if d not in appeared]
    appeared_list = [d for d in range(10) if d in appeared]
    # 未出现的优先, 但要选8个
    candidates = not_appeared + appeared_list
    return candidates[:8]


def cold_number_top8(seq, window=30):
    """冷号策略: 排除最近window期出现次数最多的(冷号补涨假说)"""
    if not seq:
        return list(range(8))
    recent = seq[-window:]
    counts = np.zeros(10)
    for d in recent:
        if 0 <= d < 10:
            counts[d] += 1
    # 出现次数最少的8个(冷号)
    return np.argsort(counts)[:8].tolist()


def gap_based_top8(seq, window=100):
    """间隔策略: 排除"最近刚出现"的(间隔最大的优先)"""
    if not seq:
        return list(range(8))
    recent = seq[-window:]
    # 计算每个数字最后一次出现的距离(越大表示越久没出现)
    gaps = np.zeros(10)
    for d in range(10):
        gap = window
        for i in range(len(recent) - 1, -1, -1):
            if recent[i] == d:
                gap = len(recent) - 1 - i
                break
        gaps[d] = gap
    # 间隔最大的8个(最久没出现的优先 = 冷号)
    return np.argsort(gaps)[::-1][:8].tolist()


def markov_conditional_top8(seq, last_digit, transition_counts):
    """Markov条件概率: 基于上一期数字, 选下一期出现概率最高的8个"""
    if last_digit is None or last_digit not in transition_counts:
        return list(range(8))
    counts = transition_counts[last_digit]
    total = sum(counts.values())
    if total == 0:
        return list(range(8))
    arr = np.zeros(10)
    for d, c in counts.items():
        if 0 <= d < 10:
            arr[d] = c
    return np.argsort(arr)[::-1][:8].tolist()


def markov_anti_top8(seq, last_digit, transition_counts):
    """Markov反向: 基于上一期, 排除下一期出现概率最高的(anti)"""
    if last_digit is None or last_digit not in transition_counts:
        return list(range(8))
    counts = transition_counts[last_digit]
    total = sum(counts.values())
    if total == 0:
        return list(range(8))
    arr = np.zeros(10)
    for d, c in counts.items():
        if 0 <= d < 10:
            arr[d] = c
    # 出现概率最低的8个
    return np.argsort(arr)[:8].tolist()


def combined_strategy_top8(seq, last_digit, transition_counts):
    """综合策略: 多信号投票
    - 反频率(长期): 冷号补涨
    - anti-persistence(短期): 排除最近出现的
    - Markov条件: 基于上一期
    投票: 每个策略选出8个, 累计票数, 取top8
    """
    votes = np.zeros(10)
    s1 = freq_low_top8(seq)
    for d in s1:
        votes[d] += 1
    s2 = anti_persistence_top8(seq, window=5)
    for d in s2:
        votes[d] += 1
    s3 = cold_number_top8(seq, window=30)
    for d in s3:
        votes[d] += 1
    s4 = markov_anti_top8(seq, last_digit, transition_counts)
    for d in s4:
        votes[d] += 1
    return np.argsort(votes)[::-1][:8].tolist()


def chi_square_uniformity(seq):
    """卡方均匀性检验"""
    if len(seq) < 10:
        return None, None
    counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            counts[d] += 1
    expected = len(seq) / 10
    chi2, p = scipy_stats.chisquare(counts, [expected] * 10)
    return float(chi2), float(p)


def run_analysis(test_size=300, burn_in=1000):
    log("=" * 80)
    log("PL5 突破80%随机基线 - 深度分析")
    log("=" * 80)

    history, rows = load_history()
    total_len = len(history['wan'])
    start_idx = total_len - test_size
    end_idx = total_len

    # === 1. 分布均匀性检验 ===
    log("\n=== 1. PL5 数字分布均匀性检验 (chi-square) ===")
    log(f"{'位置':<8} {'卡方':<12} {'p值':<12} {'是否均匀':<10} {'最频繁数字':<12} {'最罕见数字':<12}")
    for pos in POSITIONS:
        seq = history[pos]
        chi2, p = chi_square_uniformity(seq)
        counts = Counter(seq)
        most = counts.most_common(1)[0]
        least = min(counts.items(), key=lambda x: x[1])
        uniform = "是" if p > 0.05 else "否(有偏差)"
        log(f"{pos:<8} {chi2:<12.3f} {p:<12.4f} {uniform:<10} {most[0]}({most[1]}):<12 {least[0]}({least[1]}):<12")

    # === 2. 多策略回测 ===
    log(f"\n=== 2. 多策略回测 (测试 {test_size} 期) ===")
    strategies = [
        ('random', random_top8),
        ('freq_high', freq_high_top8),
        ('freq_low', freq_low_top8),
        ('recent_freq_high_w50', lambda s: recent_freq_high_top8(s, 50)),
        ('recent_freq_low_w50', lambda s: recent_freq_low_top8(s, 50)),
        ('anti_persist_w5', lambda s: anti_persistence_top8(s, 5)),
        ('anti_persist_w3', lambda s: anti_persistence_top8(s, 3)),
        ('cold_w30', lambda s: cold_number_top8(s, 30)),
        ('cold_w50', lambda s: cold_number_top8(s, 50)),
        ('gap_w100', lambda s: gap_based_top8(s, 100)),
        ('gap_w50', lambda s: gap_based_top8(s, 50)),
    ]
    # Markov 和 combined 需要特殊处理
    stats = {name: defaultdict(lambda: {'hits': 0, 'total': 0}) for name, _ in strategies}
    stats['markov_cond'] = defaultdict(lambda: {'hits': 0, 'total': 0})
    stats['markov_anti'] = defaultdict(lambda: {'hits': 0, 'total': 0})
    stats['combined'] = defaultdict(lambda: {'hits': 0, 'total': 0})

    t0 = time.time()
    for t in range(start_idx, end_idx):
        if (t - start_idx) % 100 == 0:
            log(f"  进度: {t-start_idx}/{test_size}  耗时: {time.time()-t0:.1f}s")

        # 构建 Markov 转移计数(用 t 之前数据) - 三层嵌套
        trans = {pos: defaultdict(lambda: defaultdict(int)) for pos in POSITIONS}
        for pos in POSITIONS:
            seq_p = history[pos][:t]
            for i in range(len(seq_p) - 1):
                trans[pos][seq_p[i]][seq_p[i+1]] += 1

        for pos in POSITIONS:
            actual = history[pos][t]
            seq = history[pos][:t]
            last_d = seq[-1] if seq else None

            for name, func in strategies:
                top8 = func(seq)
                stats[name][pos]['hits'] += int(actual in top8)
                stats[name][pos]['total'] += 1

            # Markov 条件
            mc_top8 = markov_conditional_top8(seq, last_d, trans[pos])
            stats['markov_cond'][pos]['hits'] += int(actual in mc_top8)
            stats['markov_cond'][pos]['total'] += 1

            # Markov 反向
            ma_top8 = markov_anti_top8(seq, last_d, trans[pos])
            stats['markov_anti'][pos]['hits'] += int(actual in ma_top8)
            stats['markov_anti'][pos]['total'] += 1

            # 综合
            cb_top8 = combined_strategy_top8(seq, last_d, trans[pos])
            stats['combined'][pos]['hits'] += int(actual in cb_top8)
            stats['combined'][pos]['total'] += 1

    # 汇总
    log(f"\n回测完成, 耗时: {time.time()-t0:.1f}s")
    log("")
    log("=" * 100)
    log("多策略 Top-8 命中率对比")
    log("=" * 100)
    log(f"{'策略':<24} {'万位':>8} {'千位':>8} {'百位':>8} {'十位':>8} {'个位':>8} {'整体':>8} {'vs随机':>10}")
    log("-" * 100)

    results = {}
    random_overall = None
    for name in list(stats.keys()):
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

    # 按整体命中率排序输出
    for name in sorted(results.keys(), key=lambda x: results[x]['overall'], reverse=True):
        r = results[name]
        diff = (r['overall'] - random_overall) * 100 if random_overall else 0
        marker = " ★" if r['overall'] > 0.80 else ""
        log(f"{name:<24} {r['per_pos']['wan']*100:>7.2f}% {r['per_pos']['qian']*100:>7.2f}% "
            f"{r['per_pos']['bai']*100:>7.2f}% {r['per_pos']['shi']*100:>7.2f}% "
            f"{r['per_pos']['ge']*100:>7.2f}% {r['overall']*100:>7.2f}% {diff:>+9.2f}pp{marker}")

    log("-" * 100)
    log(f"{'随机基线(理论)':<24} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8}")

    # === 3. 突破策略分析 ===
    log("\n" + "=" * 100)
    log("突破80%随机基线 - 最优策略分析")
    log("=" * 100)
    best_name = max(results.keys(), key=lambda x: results[x]['overall'])
    best = results[best_name]
    log(f"最优策略: {best_name}")
    log(f"  整体命中率: {best['overall']*100:.2f}%")
    log(f"  vs 随机基线: {(best['overall']-random_overall)*100:+.2f} 个百分点")
    log(f"  vs 80%理论: {(best['overall']-0.80)*100:+.2f} 个百分点")
    breakthrough = [n for n in results if results[n]['overall'] > 0.80]
    if breakthrough:
        log(f"\n突破80%的策略: {breakthrough}")
        for n in breakthrough:
            log(f"  {n}: {results[n]['overall']*100:.2f}%")
    else:
        log(f"\n所有策略均未突破80% (最高: {best_name} = {best['overall']*100:.2f}%)")
        log("结论: PL5数字分布接近均匀, 单一统计策略难以稳定突破80%")
        log("需要模型层特征(Stacking/HMM等)提供额外判别力")

    # 保存
    report = {
        'timestamp': datetime.now().isoformat(),
        'test_config': {'test_size': test_size, 'burn_in': burn_in, 'total_history': total_len},
        'uniformity': {pos: {'chi2': chi_square_uniformity(history[pos])[0],
                             'p_value': chi_square_uniformity(history[pos])[1]}
                       for pos in POSITIONS},
        'strategy_results': {n: {'overall': results[n]['overall'],
                                 'per_position': results[n]['per_pos']}
                             for n in results},
        'best_strategy': best_name,
        'best_overall': best['overall'],
        'random_overall': random_overall,
        'breakthrough_strategies': breakthrough,
    }
    rp = OUTPUT_DIR / f"breakthrough_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(rp, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"\n分析报告已保存: {rp}")
    return report


if __name__ == "__main__":
    run_analysis(test_size=300, burn_in=1000)
