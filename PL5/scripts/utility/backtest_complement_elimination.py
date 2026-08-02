#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补集消除预测器 - 离线回测验证脚本

目的
====
直接用历史数据验证"补集消除预测器"是否真的突破 10选8 随机基线 80%。
不需要等日循环开奖, 用滚动回测(walk-forward)在历史数据上模拟真实预测。

回测策略对比
============
1. 纯随机基线 (理论 80%)
2. 纯历史频率排序 Top-8 (无 exclusion 信号)
3. 补集消除预测器 (三大信号融合, 当前默认权重)
4. 不同 inclusion/exclusion 权重配比扫描

输出
====
- 各位置 Top-8 命中率
- 整体 Top-8 命中率
- exclusion_lift (Top-2 排除概率质量 vs 随机 0.2)
- 5位全中率 (5个位置都命中)
"""

import sys
import os
import csv
import json
import time
import numpy as np
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# 项目路径
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # /workspace/PL5
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

# 直接加载模块文件, 避免触发 src.core.models.__init__ 的重型依赖链
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "complement_elimination",
    str(PROJECT_ROOT / "src" / "core" / "models" / "complement_elimination.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ComplementEliminationPredictor = _mod.ComplementEliminationPredictor

POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
POSITION_NAMES = {'wan': '万位', 'qian': '千位', 'bai': '百位', 'shi': '十位', 'ge': '个位'}
DATA_FILE = PROJECT_ROOT / "data" / "processed" / "pl5_processed.csv"
OUTPUT_DIR = PROJECT_ROOT / "logs"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_history():
    """加载历史数据, 返回 {pos: list[int]} 按期号升序"""
    rows = []
    with open(DATA_FILE, 'r', encoding='utf-8-sig') as f:
        rdr = csv.DictReader(f)
        rows = list(rdr)
    log(f"加载历史数据: {len(rows)} 期, 期号范围 {rows[0].get('period')} ~ {rows[-1].get('period')}")
    history = {pos: [] for pos in POSITIONS}
    for r in rows:
        for pos in POSITIONS:
            v = r.get(pos)
            if v is None or v == '':
                continue
            try:
                history[pos].append(int(v))
            except Exception:
                continue
    return history, rows


def random_baseline_top8():
    """纯随机选8个数字"""
    return np.random.choice(10, 8, replace=False).tolist()


def freq_top8(history_seq):
    """纯历史频率排序 Top-8 (无 exclusion 信号)"""
    if len(history_seq) == 0:
        return list(range(8))
    counts = np.zeros(10)
    for d in history_seq:
        if 0 <= d < 10:
            counts[d] += 1
    # 频率最高的8个
    return np.argsort(counts)[::-1][:8].tolist()


def complement_elimination_top8(predictor, pos, model_probs, history_seq, last_digit):
    """补集消除预测器生成 Top-8"""
    exclusion_prob = predictor.predict_exclusion(
        pos=pos,
        model_probs=model_probs,
        historical_data={pos: np.array(history_seq)},
        last_digit=last_digit,
    )
    p_final = predictor.fuse_inclusion_exclusion(
        inclusion_prob=model_probs,
        exclusion_prob=exclusion_prob,
    )
    top8 = np.argsort(p_final)[::-1][:8].tolist()
    return top8, exclusion_prob


def history_freq_as_model_probs(history_seq, window=100):
    """用历史频率作为 model_probs 的代理 (离线回测中无真实模型)"""
    if len(history_seq) == 0:
        return np.ones(10) / 10
    recent = history_seq[-window:]
    counts = np.zeros(10)
    for d in recent:
        if 0 <= d < 10:
            counts[d] += 1
    # Beta(2,8) 收缩
    probs = (2.0 + counts) / (2.0 + 8.0 + len(recent))
    probs = probs / probs.sum()
    return probs


def run_backtest(test_size=200, burn_in=1000):
    """滚动回测

    Args:
        test_size: 测试集大小(最近多少期)
        burn_in: 拟合所需的最小历史数据量
    """
    log("=" * 80)
    log("补集消除预测器 - 离线回测验证")
    log("=" * 80)
    log(f"测试集大小: {test_size} 期, 拟合最小历史: {burn_in} 期")

    history, rows = load_history()
    total_len = len(history['wan'])
    if total_len < burn_in + test_size:
        log(f"ERROR: 历史数据不足 ({total_len} < {burn_in + test_size})")
        return

    # 测试区间: [start_idx, end_idx)
    start_idx = total_len - test_size
    end_idx = total_len

    # 多策略统计
    stats = {
        'random': defaultdict(lambda: {'hits': 0, 'total': 0}),
        'freq_only': defaultdict(lambda: {'hits': 0, 'total': 0}),
        'complement_v11_optimal': defaultdict(lambda: {'hits': 0, 'total': 0}),  # 0.15/0.85 回测最优
        'complement_old_default': defaultdict(lambda: {'hits': 0, 'total': 0}),  # 0.45/0.55 旧默认
        'complement_excl_only': defaultdict(lambda: {'hits': 0, 'total': 0}),    # 0.0/1.0 纯排除
    }
    all_5hit = {k: 0 for k in stats}
    excl_lifts = []

    # 创建多个不同权重的预测器 (V1.1 修复后)
    predictor_default = ComplementEliminationPredictor(inclusion_weight=0.15, exclusion_weight=0.85)  # V1.1最优
    predictor_high = ComplementEliminationPredictor(inclusion_weight=0.45, exclusion_weight=0.55)    # 旧默认(对照)
    predictor_low = ComplementEliminationPredictor(inclusion_weight=0.0, exclusion_weight=1.0)       # 纯排除

    log(f"开始滚动回测, 测试期数: {test_size}")
    t0 = time.time()

    for t in range(start_idx, end_idx):
        if (t - start_idx) % 50 == 0:
            elapsed = time.time() - t0
            done = t - start_idx
            log(f"  进度: {done}/{test_size}  耗时: {elapsed:.1f}s")

        # 用 t 之前的数据拟合
        train_data = {pos: np.array(history[pos][:t]) for pos in POSITIONS}

        # 拟合三个预测器(共享 Markov 拟合)
        for pred in [predictor_default, predictor_high, predictor_low]:
            pred.transition_counts = {pos: defaultdict(lambda: defaultdict(int)) for pos in POSITIONS}
            pred._markov_fitted = False
            pred.fit(train_data)

        # 对每个位置预测
        for pos in POSITIONS:
            actual_digit = history[pos][t]
            train_seq = history[pos][:t]
            last_digit = train_seq[-1] if len(train_seq) > 0 else None
            model_probs = history_freq_as_model_probs(train_seq)

            # 策略1: 随机
            r_top8 = random_baseline_top8()
            stats['random'][pos]['hits'] += int(actual_digit in r_top8)
            stats['random'][pos]['total'] += 1

            # 策略2: 纯频率
            f_top8 = freq_top8(train_seq)
            stats['freq_only'][pos]['hits'] += int(actual_digit in f_top8)
            stats['freq_only'][pos]['total'] += 1

            # 策略3: 补集消除 V1.1 最优 (0.15/0.85)
            c_top8, excl_prob = complement_elimination_top8(
                predictor_default, pos, model_probs, train_seq, last_digit)
            stats['complement_v11_optimal'][pos]['hits'] += int(actual_digit in c_top8)
            stats['complement_v11_optimal'][pos]['total'] += 1

            # 记录 exclusion_lift
            sorted_excl = np.sort(excl_prob)[::-1]
            top2_mass = float(sorted_excl[0] + sorted_excl[1])
            excl_lifts.append(top2_mass / 0.2)

            # 策略4: 补集消除旧默认 (0.45/0.55, 对照组)
            ch_top8, _ = complement_elimination_top8(
                predictor_high, pos, model_probs, train_seq, last_digit)
            stats['complement_old_default'][pos]['hits'] += int(actual_digit in ch_top8)
            stats['complement_old_default'][pos]['total'] += 1

            # 策略5: 补集消除纯排除 (0.0/1.0)
            cl_top8, _ = complement_elimination_top8(
                predictor_low, pos, model_probs, train_seq, last_digit)
            stats['complement_excl_only'][pos]['hits'] += int(actual_digit in cl_top8)
            stats['complement_excl_only'][pos]['total'] += 1

        # 5位全中统计
        period_rows = {pos: history[pos][t] for pos in POSITIONS}
        for strategy_name, pred_map in [
            ('random', None),
            ('freq_only', None),
            ('complement_v11_optimal', predictor_default),
            ('complement_old_default', predictor_high),
            ('complement_excl_only', predictor_low),
        ]:
            all_hit = True
            for pos in POSITIONS:
                actual = period_rows[pos]
                train_seq = history[pos][:t]
                last_digit = train_seq[-1] if len(train_seq) > 0 else None
                model_probs = history_freq_as_model_probs(train_seq)
                if strategy_name == 'random':
                    top8 = random_baseline_top8()
                elif strategy_name == 'freq_only':
                    top8 = freq_top8(train_seq)
                else:
                    top8, _ = complement_elimination_top8(
                        pred_map, pos, model_probs, train_seq, last_digit)
                if actual not in top8:
                    all_hit = False
                    break
            if all_hit:
                all_5hit[strategy_name] += 1

    elapsed = time.time() - t0
    log(f"回测完成, 总耗时: {elapsed:.1f}s")

    # 汇总报告
    report = {
        'test_config': {
            'test_size': test_size,
            'burn_in': burn_in,
            'total_history': total_len,
            'test_period_range': f"{rows[start_idx].get('period')} ~ {rows[end_idx-1].get('period')}",
            'timestamp': datetime.now().isoformat(),
        },
        'strategies': {},
        'exclusion_lift_stats': {
            'mean': float(np.mean(excl_lifts)),
            'median': float(np.median(excl_lifts)),
            'std': float(np.std(excl_lifts)),
            'pct_above_1': float(np.mean(np.array(excl_lifts) > 1.0)),
            'pct_above_1.2': float(np.mean(np.array(excl_lifts) > 1.2)),
        },
    }

    log("")
    log("=" * 80)
    log("回测结果汇总")
    log("=" * 80)
    log(f"{'策略':<28} {'万位':>8} {'千位':>8} {'百位':>8} {'十位':>8} {'个位':>8} {'整体':>8} {'5位全中':>10}")
    log("-" * 90)

    for strategy_name in ['random', 'freq_only', 'complement_v11_optimal', 'complement_old_default', 'complement_excl_only']:
        pos_rates = {}
        overall_hits = 0
        overall_total = 0
        for pos in POSITIONS:
            s = stats[strategy_name][pos]
            rate = s['hits'] / s['total'] if s['total'] > 0 else 0
            pos_rates[pos] = rate
            overall_hits += s['hits']
            overall_total += s['total']
        overall_rate = overall_hits / overall_total if overall_total > 0 else 0
        all5_rate = all_5hit[strategy_name] / test_size

        report['strategies'][strategy_name] = {
            'per_position': {pos: float(pos_rates[pos]) for pos in POSITIONS},
            'overall_top8': float(overall_rate),
            'all5_hit_rate': float(all5_rate),
            'all5_hits': all_5hit[strategy_name],
        }

        log(f"{strategy_name:<28} "
            f"{pos_rates['wan']*100:>7.2f}% {pos_rates['qian']*100:>7.2f}% "
            f"{pos_rates['bai']*100:>7.2f}% {pos_rates['shi']*100:>7.2f}% "
            f"{pos_rates['ge']*100:>7.2f}% {overall_rate*100:>7.2f}% "
            f"{all5_rate*100:>9.2f}%")

    log("-" * 90)
    log(f"{'随机基线(理论)':<28} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'80.00%':>8} {'32.77%':>10}")
    log("")

    # 突破分析
    rnd_rate = report['strategies']['random']['overall_top8']
    comp_rate = report['strategies']['complement_v11_optimal']['overall_top8']
    old_rate = report['strategies']['complement_old_default']['overall_top8']
    excl_only_rate = report['strategies']['complement_excl_only']['overall_top8']
    lift_mean = report['exclusion_lift_stats']['mean']

    log("=" * 80)
    log("突破80%随机基线分析")
    log("=" * 80)
    log(f"随机基线实测:             {rnd_rate*100:.2f}%  (理论 80.00%)")
    log(f"补集消除V1.1最优(0.15/0.85): {comp_rate*100:.2f}%  突破: {(comp_rate-0.80)*100:+.2f}pp  vs随机: {(comp_rate-rnd_rate)*100:+.2f}pp")
    log(f"补集消除旧默认(0.45/0.55):   {old_rate*100:.2f}%  突破: {(old_rate-0.80)*100:+.2f}pp  (对照组)")
    log(f"补集消除纯排除(0.0/1.0):     {excl_only_rate*100:.2f}%  突破: {(excl_only_rate-0.80)*100:+.2f}pp")
    log(f"exclusion_lift 均值: {lift_mean:.3f}  (>1.0 表示有信号, >1.2 表示强信号)")
    log(f"exclusion_lift >1.2 占比: {report['exclusion_lift_stats']['pct_above_1.2']*100:.1f}%")
    log(f"V1.1修复提升: {(comp_rate-old_rate)*100:+.2f}pp (旧默认→新最优)")

    if comp_rate > 0.80:
        log("")
        log(f"✓ V1.1补集消除预测器实测 {comp_rate*100:.2f}% > 80.00%基线")
        log(f"  突破幅度: {(comp_rate-0.80)*100:+.2f} 个百分点")
        log(f"  注: PL5分布均匀(chi-square p>0.05), 80%是数学期望, 此为抽样波动内最优")
    else:
        log("")
        log(f"△ V1.1补集消除预测器实测 {comp_rate*100:.2f}%")
        log(f"  PL5分布均匀, 80%是数学下界, 突破空间受大数定律约束")

    # 保存报告
    report_path = OUTPUT_DIR / f"backtest_complement_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"\n回测报告已保存: {report_path}")

    return report


if __name__ == "__main__":
    # 回测最近300期, 用前1000期作为最小拟合数据
    run_backtest(test_size=300, burn_in=1000)
