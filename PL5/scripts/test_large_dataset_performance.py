#!/usr/bin/env python3
"""
大数据集性能测试 - 验证C++加速效果
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("大数据集性能测试")
print("=" * 80)

# 导入模块
from cpp_core import FeatureCalculator, CPP_AVAILABLE

if not CPP_AVAILABLE:
    print("❌ C++模块未加载")
    sys.exit(1)

print(f"\n✅ C++模块已加载: {CPP_AVAILABLE}")

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

# 测试配置
test_configs = [
    (10000, 100, "10K元素"),
    (50000, 100, "50K元素"),
    (100000, 100, "100K元素"),
    (500000, 100, "500K元素"),
    (1000000, 100, "1M元素"),
]

calc = FeatureCalculator()

print("\n性能对比测试")
print("-" * 80)
print(f"{'数据规模':<15} {'窗口':<8} {'Python(ms)':<15} {'C++(ms)':<15} {'加速比':<10}")
print("-" * 80)

results = []

for size, window, label in test_configs:
    # 生成测试数据
    test_data = list(range(size))
    
    # Python rolling_mean
    start = time.time()
    python_result = python_rolling_mean(test_data, window)
    python_time = (time.time() - start) * 1000
    
    # C++ rolling_mean
    start = time.time()
    cpp_result = calc.rolling_mean(test_data, window)
    cpp_time = (time.time() - start) * 1000
    
    # 验证结果一致性
    assert len(python_result) == len(cpp_result), "结果长度不一致"
    
    # 计算加速比
    speedup = python_time / cpp_time if cpp_time > 0 else 0
    
    results.append({
        'size': size,
        'window': window,
        'python_time': python_time,
        'cpp_time': cpp_time,
        'speedup': speedup
    })
    
    print(f"{label:<15} {window:<8} {python_time:>12.2f}ms {cpp_time:>12.2f}ms {speedup:>8.1f}x")

print("-" * 80)

# 测试其他功能
print("\n\n其他C++加速功能测试")
print("-" * 80)

test_data = list(range(100000))

# rolling_std
start = time.time()
python_std = python_rolling_std(test_data, 50)
python_std_time = (time.time() - start) * 1000

start = time.time()
cpp_std = calc.rolling_std(test_data, 50)
cpp_std_time = (time.time() - start) * 1000

print(f"rolling_std (100K): Python {python_std_time:.2f}ms vs C++ {cpp_std_time:.2f}ms")
print(f"  加速比: {python_std_time/cpp_std_time:.1f}x")

# rolling_frequency
start = time.time()
cpp_freq = calc.rolling_frequency(test_data, 50, 10)
cpp_freq_time = (time.time() - start) * 1000

print(f"rolling_frequency (100K): C++ {cpp_freq_time:.2f}ms")

# calculate_hurst
start = time.time()
cpp_hurst = calc.calculate_hurst(test_data[:10000])
cpp_hurst_time = (time.time() - start) * 1000

print(f"calculate_hurst (10K): C++ {cpp_hurst_time:.2f}ms (Hurst指数: {cpp_hurst:.4f})")

# calculate_lyapunov
start = time.time()
cpp_lyap = calc.calculate_lyapunov(test_data[:10000])
cpp_lyap_time = (time.time() - start) * 1000

print(f"calculate_lyapunov (10K): C++ {cpp_lyap_time:.2f}ms (Lyapunov指数: {cpp_lyap:.4f})")

# fft_transform
start = time.time()
cpp_fft = calc.fft_transform(test_data[:10000])
cpp_fft_time = (time.time() - start) * 1000

print(f"fft_transform (10K): C++ {cpp_fft_time:.2f}ms")

print("-" * 80)

# 总结
print("\n\n性能测试总结")
print("=" * 80)

avg_speedup = sum(r['speedup'] for r in results) / len(results)
max_speedup = max(r['speedup'] for r in results)
min_speedup = min(r['speedup'] for r in results)

print(f"平均加速比: {avg_speedup:.1f}x")
print(f"最大加速比: {max_speedup:.1f}x")
print(f"最小加速比: {min_speedup:.1f}x")

print(f"\n优化效果:")
print(f"✅ 小数据集 (10K): {results[0]['speedup']:.1f}x 加速")
print(f"✅ 中数据集 (100K): {results[2]['speedup']:.1f}x 加速")
print(f"✅ 大数据集 (1M): {results[4]['speedup']:.1f}x 加速")

if avg_speedup >= 10:
    print("\n🎉 C++加速效果显著，平均加速比超过10倍！")
elif avg_speedup >= 5:
    print("\n✅ C++加速效果良好，平均加速比超过5倍！")
else:
    print("\n⚠️ C++加速效果有限，建议检查实现")

print("=" * 80)
