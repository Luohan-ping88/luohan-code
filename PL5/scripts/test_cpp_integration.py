"""
C++优化模块验证测试
测试特征工程模块与C++加速的集成
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

def generate_sample_data(n_samples=200):
    """生成测试数据"""
    np.random.seed(42)
    data = {
        'period': [f'2026{i:05d}' for i in range(1, n_samples + 1)],
        'wan': np.random.randint(0, 10, n_samples),
        'qian': np.random.randint(0, 10, n_samples),
        'bai': np.random.randint(0, 10, n_samples),
        'shi': np.random.randint(0, 10, n_samples),
        'ge': np.random.randint(0, 10, n_samples),
    }
    return pd.DataFrame(data)

def test_cpp_core_basic():
    """测试C++核心模块基本功能"""
    print("\n" + "="*60)
    print("测试1: C++核心模块基本功能")
    print("="*60)
    
    try:
        from cpp_core import FeatureCalculator, CPP_AVAILABLE
        if CPP_AVAILABLE:
            print("✅ C++模块加载状态: 启用")
        else:
            print("⚠️ C++模块加载状态: 未启用，使用Python回退")
        
        data = list(range(100))
        
        print("\n测试1. 基础统计计算:")
        mean = FeatureCalculator.calculate_mean(data)
        std = FeatureCalculator.calculate_std(data)
        max_val = FeatureCalculator.calculate_max(data)
        min_val = FeatureCalculator.calculate_min(data)
        print(f"   mean={mean:.2f}, std={std:.2f}, max={max_val}, min={min_val}")
        
        print("\n测试2. 滚动计算:")
        means = FeatureCalculator.rolling_mean(data, 20)
        stds = FeatureCalculator.rolling_std(data, 20)
        print(f"   滚动均值数量: {len(means)}, 前5个值: {means[:5]}")
        
        print("\n测试3. 频率统计:")
        freq = FeatureCalculator.rolling_frequency(data, 20, 10)
        print(f"   频率矩阵维度: {len(freq)} x {len(freq[0]) if freq else 0}")
        
        print("\n测试4. 高级特征:")
        hurst = FeatureCalculator.calculate_hurst(data)
        lyapunov = FeatureCalculator.calculate_lyapunov(data)
        fft_vals = FeatureCalculator.fft_transform(data)
        print(f"   Hurst指数: {hurst:.4f}, Lyapunov指数: {lyapunov:.4f}")
        print(f"   FFT长度: {len(fft_vals)}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_feature_engineering_cpp_integration():
    """测试特征工程模块与C++的集成"""
    print("\n" + "="*60)
    print("测试2: 特征工程模块C++集成")
    print("="*60)
    
    try:
        from src.core.features.engineer import FeatureEngineering
        df = generate_sample_data(200)
        
        fe = FeatureEngineering(use_cache=False)
        print(f"✅ 特征工程初始化成功")
        print(f"   C++加速器状态: {fe.cpp_available}")
        
        start_time = time.time()
        features = fe.extract_features(df)
        elapsed = time.time() - start_time
        
        print(f"\n✅ 特征提取完成，耗时: {elapsed:.2f}秒")
        print(f"   提取的特征数量: {len(features.columns)}")
        print(f"   提取的特征: {list(features.columns)}")
        
        important_features = [c for c in features.columns if any(keyword in c for keyword in ['_mean_', '_std_', '_entropy_', '_hurst'])]
        print(f"\n   与C++相关的特征: {len(important_features)}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    results = []
    
    results.append(("C++核心模块测试", test_cpp_core_basic()))
    results.append(("特征工程集成测试", test_feature_engineering_cpp_integration()))
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status}: {name}")
    
    all_passed = all(passed for _, passed in results)
    print(f"\n总体结果: {'✅ 全部通过' if all_passed else '❌ 有测试失败'}")
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
