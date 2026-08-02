#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 多窗口分布验证 - 检测周期分布逻辑

核心认知纠正
============
全局 chi-square 均匀(7678期) 只能证明"总体无偏",
不能否定"局部窗口存在周期性/聚集性偏离"。
大数定律把短期信号平均掉了, 但短期信号才是可预测性的来源。

本脚本验证:
1. 多窗口 chi-square: 哪些窗口下分布显著偏离均匀(p<0.05)?
2. 偏移幅度: 偏离窗口下, 数字频率 vs 期望频率的差距
3. 周期性检测: 数字出现频率的自相关(ACF)和FFT
4. 时间条件分布: 按期号模周期(7/30/100)分组, 检测条件偏移
5. 可预测性评估: 用"局部偏移数字"做Top-8, 是否超过80%?
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
    return history, rows


def chi_square_test(seq):
    if len(seq) < 10:
        return None, None
    counts = np.zeros(10)
    for d in seq:
        if 0 <= d < 10:
            counts[d] += 1
    expected = len(seq) / 10
    chi2, p = scipy_stats.chisquare(counts, [expected] * 10)
    return float(chi2), float(p)


def sliding_window_chi2(seq, window):
    """滑动窗口 chi-square, 返回每个窗口的p值序列"""
    p_values = []
    n_sig = 0
    for i in range(window, len(seq) + 1, max(1, window // 4)):
        sub = seq[i - window:i]
        _, p = chi_square_test(sub)
        if p is not None:
            p_values.append(p)
            if p < 0.05:
                n_sig += 1
    return p_values, n_sig


def autocorr_digit(seq, digit, max_lag=100):
    """单数字出现序列的自相关"""
    binary = np.array([1 if d == digit else 0 for d in seq])
    n = len(binary)
    if n < max_lag * 2:
        return []
    binary = binary - binary.mean()
    var = np.var(binary)
    if var < 1e-8:
        return []
    acf = []
    for lag in range(1, max_lag + 1):
        c = np.sum(binary[:n - lag] * binary[lag:]) / (n * var)
        acf.append(c)
    return acf


def fft_period(seq, digit):
    """FFT检测单数字出现序列的周期"""
    binary = np.array([1 if d == digit else 0 for d in seq])
    if len(binary) < 256:
        return []
    # 取最近1024期
    x = binary[-1024:]
    X = np.fft.rfft(x - x.mean())
    mag = np.abs(X)
    # 找top5周期(排除DC)
    mag[0] = 0
    top_idx = np.argsort(mag)[::-1][:5]
    periods = []
    for idx in top_idx:
        if mag[idx] > 0 and idx > 0:
            period = len(x) / idx
            periods.append((int(period), float(mag[idx])))
    return periods


def top8_by_local_window(seq, window, predict_window):
    """用最近window期的频率分布做Top-8 (局部偏移策略)
    
    逻辑: 在偏离均匀的局部窗口里, 高频数字 → 选入Top-8
    (如果窗口p<0.05, 说明局部有偏, 频率排序有信号)
    """
    if len(seq) < window:
        return list(range(8)), 1.0
    recent = seq[-window:]
    counts = np.zeros(10)
    for d in recent:
        if 0 <= d < 10:
            counts[d] += 1
    # 频率最高的8个
    return np.argsort(counts)[::-1][:8].tolist(), None


def run_analysis(test_size=300, burn_in=1000):
    log("=" * 80)
    log("PL5 多窗口分布验证 - 检测周期分布逻辑")
    log("=" * 80)

    history, rows = load_history()
    total = len(history['wan'])
    log(f"历史数据: {total} 期")

    # === 1. 多窗口 chi-square ===
    log("\n=== 1. 多窗口 chi-square 检验 ===")
    log("检测哪些窗口下分布显著偏离均匀(p<0.05)")
    log(f"{'位置':<6} {'窗口':<6} {'窗口数':<8} {'显著偏离数':<12} {'偏离比例':<10} {'p<0.05占比':<12}")
    log("-" * 70)

    windows = [10, 20, 30, 50, 100, 200, 500]
    window_deviation = {pos: {} for pos in POSITIONS}

    for pos in POSITIONS:
        seq = history[pos]
        for w in windows:
            p_vals, n_sig = sliding_window_chi2(seq, w)
            n_total = len(p_vals)
            ratio = n_sig / n_total if n_total > 0 else 0
            window_deviation[pos][w] = {'n_sig': n_sig, 'n_total': n_total, 'ratio': ratio,
                                         'p_values': p_vals}
            log(f"{pos:<6} {w:<6} {n_total:<8} {n_sig:<12} {ratio*100:>7.1f}%     "
                f"{'★★★' if ratio > 0.10 else ('★★' if ratio > 0.07 else ('★' if ratio > 0.05 else ''))}")
        log("")

    # === 2. 周期性检测: 自相关 ===
    log("=== 2. 数字出现序列的自相关(ACF)检测 ===")
    log("检测是否存在显著自相关(短期聚集/反聚集)")
    log(f"{'位置':<6} {'数字':<4} {'ACF@1':<10} {'ACF@2':<10} {'ACF@5':<10} {'ACF@10':<10} {'max_lag':<8} {'max_acf':<10}")
    log("-" * 70)

    acf_results = {}
    for pos in POSITIONS:
        acf_results[pos] = {}
        seq = history[pos]
        for d in range(10):
            acf = autocorr_digit(seq, d, max_lag=50)
            if not acf:
                continue
            # 显著性阈值: 1.96/sqrt(n)
            n = len(seq)
            sig_thresh = 1.96 / np.sqrt(n)
            # 找最大ACF的lag
            max_lag_idx = int(np.argmax(np.abs(acf))) + 1
            max_acf = float(acf[max_lag_idx - 1])
            significant = abs(max_acf) > sig_thresh
            acf_results[pos][d] = {
                'acf_1': float(acf[0]) if len(acf) > 0 else 0,
                'acf_2': float(acf[1]) if len(acf) > 1 else 0,
                'acf_5': float(acf[4]) if len(acf) > 4 else 0,
                'acf_10': float(acf[9]) if len(acf) > 9 else 0,
                'max_lag': max_lag_idx,
                'max_acf': max_acf,
                'significant': significant,
            }
            marker = " ★" if significant else ""
            log(f"{pos:<6} {d:<4} {acf[0]:>8.4f}  {acf[1] if len(acf)>1 else 0:>8.4f}  "
                f"{acf[4] if len(acf)>4 else 0:>8.4f}  {acf[9] if len(acf)>9 else 0:>8.4f}  "
                f"{max_lag_idx:<8} {max_acf:>8.4f}{marker}")
        log("")

    # === 3. FFT 周期检测 ===
    log("=== 3. FFT周期检测 ===")
    log("检测数字出现序列的主导周期")
    log(f"{'位置':<6} {'数字':<4} {'主导周期(top3)':<40}")
    log("-" * 70)
    fft_results = {}
    for pos in POSITIONS:
        fft_results[pos] = {}
        seq = history[pos]
        for d in range(10):
            periods = fft_period(seq, d)
            fft_results[pos][d] = periods
            if periods:
                top3 = periods[:3]
                p_str = ", ".join(f"T={p[0]}(mag={p[1]:.1f})" for p in top3)
                log(f"{pos:<6} {d:<4} {p_str}")
        log("")

    # === 4. 多窗口局部偏移策略回测 ===
    log("=== 4. 多窗口局部偏移策略回测 ===")
    log("用最近W期频率排序做Top-8, 测试哪个窗口最优")
    log(f"测试 {test_size} 期, burn_in={burn_in}")

    start_idx = total - test_size
    strategies = [(f'local_freq_w{w}', w) for w in [10, 20, 30, 50, 100, 200]]
    stats = {name: defaultdict(lambda: {'hits': 0, 'total': 0}) for name, _ in strategies}
    stats['random'] = defaultdict(lambda: {'hits': 0, 'total': 0})

    # 额外: 自适应窗口(检测偏离程度选窗口)
    stats['adaptive_window'] = defaultdict(lambda: {'hits': 0, 'total': 0})

    t0 = time.time()
    for t in range(start_idx, total):
        if (t - start_idx) % 100 == 0:
            log(f"  进度: {t-start_idx}/{test_size}  耗时: {time.time()-t0:.1f}s")
        for pos in POSITIONS:
            actual = history[pos][t]
            seq = history[pos][:t]
            # 随机
            r = np.random.choice(10, 8, replace=False)
            stats['random'][pos]['hits'] += int(actual in r); stats['random'][pos]['total'] += 1
            # 各窗口
            for name, w in strategies:
                top8, _ = top8_by_local_window(seq, w, None)
                stats[name][pos]['hits'] += int(actual in top8); stats[name][pos]['total'] += 1
            # 自适应: 选p值最小的窗口(偏离最大)的频率排序
            best_p = 1.0
            best_w = 50
            best_top8 = list(range(8))
            for w in [20, 50, 100, 200]:
                if len(seq) < w:
                    continue
                recent = seq[-w:]
                _, p = chi_square_test(recent)
                if p is not None and p < best_p:
                    best_p = p
                    best_w = w
                    counts = np.zeros(10)
                    for d in recent:
                        if 0 <= d < 10:
                            counts[d] += 1
                    best_top8 = np.argsort(counts)[::-1][:8].tolist()
            stats['adaptive_window'][pos]['hits'] += int(actual in best_top8)
            stats['adaptive_window'][pos]['total'] += 1

    log(f"\n回测完成, 耗时: {time.time()-t0:.1f}s")
    log("")
    log("=" * 90)
    log("多窗口局部偏移策略 Top-8 命中率")
    log("=" * 90)
    log(f"{'策略':<24} {'万位':>8} {'千位':>8} {'百位':>8} {'十位':>8} {'个位':>8} {'整体':>8} {'vs随机':>10}")
    log("-" * 90)

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
        diff = (r['overall'] - random_overall) * 100 if random_overall else 0
        marker = " ★" if r['overall'] > 0.80 else ""
        log(f"{name:<24} {r['per_pos']['wan']*100:>7.2f}% {r['per_pos']['qian']*100:>7.2f}% "
            f"{r['per_pos']['bai']*100:>7.2f}% {r['per_pos']['shi']*100:>7.2f}% "
            f"{r['per_pos']['ge']*100:>7.2f}% {r['overall']*100:>7.2f}% {diff:>+9.2f}pp{marker}")

    log("-" * 90)
    log(f"{'随机基线(理论)':<24} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8}")

    # === 5. 总结 ===
    log("\n" + "=" * 90)
    log("多窗口验证总结")
    log("=" * 90)
    # 统计显著偏离窗口的比例
    total_sig = 0
    total_windows = 0
    for pos in POSITIONS:
        for w in windows:
            d = window_deviation[pos][w]
            total_sig += d['n_sig']
            total_windows += d['n_total']
    overall_sig_ratio = total_sig / total_windows if total_windows > 0 else 0
    log(f"显著偏离窗口(p<0.05)占比: {overall_sig_ratio*100:.2f}% (期望5% under H0)")
    log(f"  → {'存在周期性偏离' if overall_sig_ratio > 0.07 else '接近H0,偏离弱'}")

    # ACF显著的数字数
    sig_acf_count = sum(1 for pos in POSITIONS for d in range(10)
                        if d in acf_results[pos] and acf_results[pos][d]['significant'])
    log(f"ACF显著的(数字,位置)组合: {sig_acf_count}/50")
    log(f"  → {'存在自相关信号' if sig_acf_count > 5 else '自相关信号弱'}")

    best_window_name = max([n for n in results if n != 'random' and n != 'adaptive_window'],
                           key=lambda x: results[x]['overall'], default=None)
    if best_window_name:
        log(f"最优局部窗口策略: {best_window_name} = {results[best_window_name]['overall']*100:.2f}%")
    log(f"自适应窗口策略: {results['adaptive_window']['overall']*100:.2f}%")

    # 保存
    report = {
        'timestamp': datetime.now().isoformat(),
        'window_deviation': {pos: {w: {'n_sig': window_deviation[pos][w]['n_sig'],
                                        'n_total': window_deviation[pos][w]['n_total'],
                                        'ratio': window_deviation[pos][w]['ratio']}
                                    for w in windows} for pos in POSITIONS},
        'acf_results': {pos: {str(d): acf_results[pos][d] for d in acf_results[pos]} for pos in POSITIONS},
        'fft_results': {pos: {str(d): fft_results[pos][d] for d in fft_results[pos]} for pos in POSITIONS},
        'strategy_results': {n: results[n] for n in results},
        'overall_sig_ratio': overall_sig_ratio,
        'sig_acf_count': sig_acf_count,
    }
    rp = OUTPUT_DIR / f"multi_window_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(rp, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    log(f"\n分析报告已保存: {rp}")
    return report


if __name__ == "__main__":
    run_analysis(test_size=300, burn_in=1000)
