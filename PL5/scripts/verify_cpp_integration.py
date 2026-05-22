#!/usr/bin/env python3
"""
C++模块与FeatureEngineer集成测试
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("C++模块与FeatureEngineer集成测试")
print("=" * 80)

# 1. 测试C++模块
print("\n[1] C++模块状态:")
try:
    from cpp_core import CPP_AVAILABLE, FeatureCalculator
    print(f"  ✓ C++模块导入成功")
    print(f"  C++可用: {CPP_AVAILABLE}")
    
    if CPP_AVAILABLE:
        calc = FeatureCalculator()
        test_data = list(range(1000))
        result = calc.rolling_mean(test_data, 20)
        print(f"  ✓ rolling_mean 测试: {len(result)} 结果")
except Exception as e:
    print(f"  ✗ C++模块错误: {e}")

# 2. 测试FeatureEngineer
print("\n[2] FeatureEngineer状态:")
try:
    from src.core.features.engineer import FeatureEngineer
    
    # 创建实例（这会初始化cpp_available）
    print("  正在初始化FeatureEngineer...")
    fe = FeatureEngineer()
    
    # 检查C++属性
    if hasattr(fe, 'cpp_available'):
        print(f"  ✓ cpp_available 属性存在: {fe.cpp_available}")
    else:
        print(f"  ✗ cpp_available 属性不存在")
    
    if hasattr(fe, 'cpp_calc'):
        print(f"  ✓ cpp_calc 属性存在: {fe.cpp_calc is not None}")
    else:
        print(f"  ⚠ cpp_calc 属性不存在（可能C++未加载）")
    
    print(f"  ✓ FeatureEngineer 初始化完成")
    
except Exception as e:
    print(f"  ✗ FeatureEngineer 错误: {e}")
    import traceback
    traceback.print_exc()

# 3. 测试AdvancedFeatureEngineering
print("\n[3] AdvancedFeatureEngineering状态:")
try:
    from src.core.features.advanced_features import AdvancedFeatureEngineering
    
    afe = AdvancedFeatureEngineering()
    if hasattr(afe, 'cpp_available'):
        print(f"  ✓ cpp_available: {afe.cpp_available}")
    else:
        print(f"  ✗ cpp_available 属性不存在")
    
    print(f"  ✓ AdvancedFeatureEngineering 初始化完成")
    
except Exception as e:
    print(f"  ✗ AdvancedFeatureEngineering 错误: {e}")

# 4. 性能对比测试
print("\n[4] Python vs C++ 性能对比:")
try:
    import time
    import numpy as np
    
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
    
    # C++实现
    from cpp_core import FeatureCalculator
    cpp_calc = FeatureCalculator()
    
    # 测试数据
    test_size = 10000
    test_data = list(range(test_size))
    
    # Python性能
    start = time.time()
    python_result = python_rolling_mean(test_data, 100)
    python_time = (time.time() - start) * 1000
    
    # C++性能
    start = time.time()
    cpp_result = cpp_calc.rolling_mean(test_data, 100)
    cpp_time = (time.time() - start) * 1000
    
    # 加速比
    speedup = python_time / cpp_time if cpp_time > 0 else 0
    
    print(f"  数据量: {test_size} 元素")
    print(f"  窗口大小: 100")
    print(f"  Python耗时: {python_time:.2f} ms")
    print(f"  C++耗时: {cpp_time:.2f} ms")
    print(f"  加速比: {speedup:.1f}x")
    
    if speedup > 1:
        print(f"  ✓ C++加速有效！")
    else:
        print(f"  ⚠ C++未提供加速（数据量可能太小）")
        
except Exception as e:
    print(f"  ✗ 性能测试错误: {e}")

print("\n" + "=" * 80)
print("集成测试完成")
print("=" * 80)
