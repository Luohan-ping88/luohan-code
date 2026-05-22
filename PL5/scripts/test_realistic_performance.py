#!/usr/bin/env python3
"""
真实场景性能测试 - 使用随机数据
"""

import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("真实场景性能测试 - 随机数据")
print("=" * 80)

from cpp_core import FeatureCalculator, CPP_AVAILABLE

if not CPP_AVAILABLE:
    print("❌ C++模块未加载")
    sys.exit(1)

print(f"✅ C++模块已加载: {CPP_AVAILABLE}\n")

# Python实现
def python_rolling_mean(data, window):
    n = len(data)
    result = []
    running_sum = 0
    for i in range(n):
        running_sum += data[i]
        if i >= window:
            running_sum -= data[i - window]
            result.append(running_sum / window)
        else:
            result.append(running_sum / (i + 1))
    return result

def python_rolling_std(data, window):
    import math
    n = len(data)
    result = []
    sum_x = 0.0
    sum_x2 = 0.0
    for i in range(n):
        sum_x  += data[i]
        sum_x2 += data[i] * data[i]
        if i >= window:
            sum_x  -= data[i - window]
            sum_x2 -= data[i - window] * data[i - window]
            count = window
        else:
            count = i + 1
        if count < 2:
            result.append(0.0)
        else:
            mean = sum_x / count
            variance = max(0.0, sum_x2 / count - mean * mean)
            result.append(math.sqrt(variance))
    return result

# 生成随机测试数据（模拟真实场景）
random.seed(42)
test_sizes = [10000, 50000, 100000, 500000]
window = 20

print(f"测试配置: 窗口大小 = {window}, 随机数据\n")

calc = FeatureCalculator()

print("=" * 80)
print(f"{'数据规模':<12} {'功能':<20} {'Python(ms)':<15} {'C++(ms)':<15} {'加速比':<10}")
print("=" * 80)

results = []

for size in test_sizes:
    # 生成随机数据
    data = [random.randint(0, 9) for _ in range(size)]
    label = f"{size//1000}K"
    
    # 测试 rolling_mean
    start = time.time()
    p_result = python_rolling_mean(data, window)
    p_time = (time.time() - start) * 1000
    
    start = time.time()
    c_result = calc.rolling_mean(data, window)
    c_time = (time.time() - start) * 1000
    
    speedup = p_time / c_time if c_time > 0 else 0
    print(f"{label:<12} {'rolling_mean':<20} {p_time:>12.2f}ms {c_time:>12.2f}ms {speedup:>8.1f}x")
    
    results.append(('rolling_mean', size, p_time, c_time, speedup))
    
    # 测试 rolling_std
    start = time.time()
    p_std = python_rolling_std(data, window)
    p_std_time = (time.time() - start) * 1000
    
    start = time.time()
    c_std = calc.rolling_std(data, window)
    c_std_time = (time.time() - start) * 1000
    
    speedup = p_std_time / c_std_time if c_std_time > 0 else 0
    print(f"{label:<12} {'rolling_std':<20} {p_std_time:>12.2f}ms {c_std_time:>12.2f}ms {speedup:>8.1f}x")
    
    results.append(('rolling_std', size, p_std_time, c_std_time, speedup))
    
    # 测试 rolling_frequency
    start = time.time()
    c_freq = calc.rolling_frequency(data, window, 10)
    c_freq_time = (time.time() - start) * 1000
    
    print(f"{label:<12} {'rolling_frequency':<20} {'N/A':>12} {c_freq_time:>12.2f}ms {'N/A':>8}")

print("=" * 80)

# 总结
print("\n\n性能总结")
print("=" * 80)

# 计算各类功能的平均加速比
mean_speedups = {}
for name, size, p, c, s in results:
    if name not in mean_speedups:
        mean_speedups[name] = []
    mean_speedups[name].append(s)

print("\n功能加速比:")
for name, speedups in mean_speedups.items():
    avg = sum(speedups) / len(speedups)
    max_s = max(speedups)
    print(f"  {name:<20}: 平均 {avg:.1f}x, 最大 {max_s:.1f}x")

overall_avg = sum(s for _, _, _, _, s in results) / len(results)
print(f"\n整体平均加速比: {overall_avg:.1f}x")

if overall_avg >= 10:
    print("🎉 C++加速效果显著！")
elif overall_avg >= 5:
    print("✅ C++加速效果良好！")
elif overall_avg >= 3:
    print("⚡ C++加速有效")
else:
    print("⚠️ C++加速效果有限")

print("=" * 80)
