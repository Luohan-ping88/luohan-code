#!/usr/bin/env python
"""
V11先进特征工程简单测试脚本
不依赖V10特征工程和sklearn
"""

import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
import time
import json

sys.path.insert(0, str(Path(__file__).parent))

def generate_test_data(n_samples=300, n_positions=5):
    """生成测试数据"""
    np.random.seed(42)
    data = {
        'period': [f'2025{i:05d}' for i in range(1, n_samples + 1)],
        'wan': np.random.randint(0, 10, n_samples),
        'qian': np.random.randint(0, 10, n_samples),
        'bai': np.random.randint(0, 10, n_samples),
        'shi': np.random.randint(0, 10, n_samples),
        'ge': np.random.randint(0, 10, n_samples),
    }
    return pd.DataFrame(data)

def test_advanced_features():
    """测试高级特征模块"""
    print("\n" + "="*60)
    print("测试 1: AdvancedFeatureExtractor")
    print("="*60)
    
    try:
        from src.core.features.advanced_features import AdvancedFeatureEngineering
        
        df = generate_test_data(300)
        print(f"测试数据: {len(df)} 条")
        
        start = time.time()
        extractor = AdvancedFeatureEngineering(use_cpp=True)
        df_features = extractor.extract_all_features(df)
        elapsed = time.time() - start
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        feature_cols = [c for c in df_features.columns if c not in ['period'] + positions]
        
        print(f"✓ 高级特征提取成功")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  特征总数: {len(feature_cols)}")
        
        # 统计各类特征
        categories = {
            '多尺度时序': len([c for c in feature_cols if '_ms_' in c]),
            '频域特征': len([c for c in feature_cols if any(kw in c for kw in ['dominant_freq', 'spectral_entropy', 'low_freq', 'mid_freq', 'high_freq'])]),
            '位置关联': len([c for c in feature_cols if any(kw in c for kw in ['_corr', '_with_', 'sum_all', 'product_all', 'mean_all', 'std_all'])]),
            '统计检验': len([c for c in feature_cols if any(kw in c for kw in ['normality', 'ks_', 'runs_', 'anderson'])]),
            '信息论': len([c for c in feature_cols if any(kw in c for kw in ['entropy_', 'cond_entropy_', 'mutual_info_'])]),
            '混沌分形': len([c for c in feature_cols if any(kw in c for kw in ['hurst', 'lyapunov', 'corr_dim', 'approx_entropy', 'sample_entropy'])]),
            '跨期特征': len([c for c in feature_cols if any(kw in c for kw in ['lag_', 'diff_mean', 'momentum', 'acceleration'])]),
            '分布特征': len([c for c in feature_cols if any(kw in c for kw in ['digit_mode', 'gini_coeff', 'even_ratio', 'odd_ratio', 'small_ratio', 'large_ratio', 'prime_ratio'])])
        }
        
        print(f"\n特征分类统计:")
        for cat, count in categories.items():
            if count > 0:
                print(f"  {cat}: {count}")
        
        return True, {
            'success': True,
            'feature_count': len(feature_cols),
            'elapsed': elapsed,
            'categories': categories
        }
    except Exception as e:
        print(f"✗ 高级特征提取失败: {e}")
        import traceback
        traceback.print_exc()
        return False, {'success': False, 'error': str(e)}

def test_v11_engineer():
    """测试V11特征工程"""
    print("\n" + "="*60)
    print("测试 2: V11FeatureEngineer (高级模式)")
    print("="*60)
    
    try:
        from src.core.features.v11_engineer import V11FeatureEngineer
        
        df = generate_test_data(300)
        print(f"测试数据: {len(df)} 条")
        
        start = time.time()
        engineer = V11FeatureEngineer(mode='v11_advanced')
        
        # 模拟V11特征工程（绕过V10依赖）
        df_features = engineer.advanced_engineer.extract_all_features(df)
        elapsed = time.time() - start
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        feature_cols = [c for c in df_features.columns if c not in ['period'] + positions]
        
        print(f"✓ V11特征提取成功")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  特征总数: {len(feature_cols)}")
        
        return True, {
            'success': True,
            'mode': 'v11_advanced',
            'feature_count': len(feature_cols),
            'elapsed': elapsed
        }
    except Exception as e:
        print(f"✗ V11特征工程失败: {e}")
        import traceback
        traceback.print_exc()
        return False, {'success': False, 'error': str(e)}

def test_module_imports():
    """测试模块导入"""
    print("\n" + "="*60)
    print("测试 3: 新模块导入")
    print("="*60)
    
    tests = []
    
    try:
        from src.core.features.advanced_features import AdvancedFeatureEngineering
        tests.append(('advanced_features', True))
        print("✓ advanced_features 导入成功")
    except Exception as e:
        tests.append(('advanced_features', False))
        print(f"✗ advanced_features 导入失败: {e}")
    
    try:
        from src.core.features.v11_engineer import V11FeatureEngineer
        tests.append(('v11_engineer', True))
        print("✓ v11_engineer 导入成功")
    except Exception as e:
        tests.append(('v11_engineer', False))
        print(f"✗ v11_engineer 导入失败: {e}")
    
    try:
        from src.core.features.comprehensive_features import ComprehensiveFeatureExtractor
        tests.append(('comprehensive_features', True))
        print("✓ comprehensive_features 导入成功")
    except Exception as e:
        tests.append(('comprehensive_features', False))
        print(f"✗ comprehensive_features 导入失败: {e}")
    
    try:
        from src.core.features.deep_features import DeepFeatureExtractor
        tests.append(('deep_features', True))
        print("✓ deep_features 导入成功")
    except Exception as e:
        tests.append(('deep_features', False))
        print(f"⚠ deep_features 导入失败 (PyTorch未安装): {e}")
    
    success_count = sum(1 for _, s in tests if s)
    print(f"\n导入成功: {success_count}/{len(tests)}")
    
    return all(t[1] for t in tests), dict(tests)

def test_cpp_acceleration():
    """测试C++加速"""
    print("\n" + "="*60)
    print("测试 4: C++加速模块")
    print("="*60)
    
    try:
        from cpp_core import FeatureCalculator, CPP_AVAILABLE
        
        print(f"C++模块可用: {CPP_AVAILABLE}")
        
        if CPP_AVAILABLE:
            data = list(range(100))
            
            start = time.time()
            means = FeatureCalculator.rolling_mean(data, 20)
            elapsed = time.time() - start
            
            print(f"✓ C++功能正常")
            print(f"  滚动均值: {len(means)} 条结果")
            print(f"  前5个结果: {means[:5]}")
            print(f"  耗时: {elapsed:.4f}s")
            
            return True, {
                'success': True,
                'cpp_available': True,
                'elapsed': elapsed
            }
        else:
            print("⚠ C++模块未编译，使用Python回退")
            return True, {
                'success': True,
                'cpp_available': False
            }
    except Exception as e:
        print(f"✗ C++模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, {'success': False, 'error': str(e)}

def print_report(results):
    """打印测试报告"""
    print("\n" + "="*60)
    print("V11先进特征工程 - 集成测试报告")
    print("="*60)
    
    for name, (success, data) in results.items():
        status = "✓ 通过" if success else "✗ 失败"
        print(f"\n{name}: {status}")
        if success:
            for k, v in data.items():
                if k != 'success':
                    if isinstance(v, dict):
                        print(f"  {k}:")
                        for sk, sv in v.items():
                            print(f"    {sk}: {sv}")
                    else:
                        print(f"  {k}: {v}")
        else:
            print(f"  错误: {data.get('error', '未知错误')}")
    
    print("\n" + "="*60)
    total = len(results)
    passed = sum(1 for s, d in results.values() if s)
    print(f"总测试: {total}, 通过: {passed}, 失败: {total - passed}")
    print("="*60)

def main():
    """主函数"""
    print("PL5 V11先进特征工程 - 快速集成测试")
    print("="*60)
    
    results = {}
    
    results['测试1: 高级特征提取'] = test_advanced_features()
    results['测试2: V11特征工程'] = test_v11_engineer()
    results['测试3: 模块导入'] = test_module_imports()
    results['测试4: C++加速模块'] = test_cpp_acceleration()
    
    print_report(results)
    
    # 保存报告
    (Path('logs')).mkdir(exist_ok=True)
    report_path = Path('logs') / 'v11_quick_test_report.json'
    
    report_data = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'results': {name: data for name, (s, data) in results.items()}
    }
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n测试报告已保存到: {report_path}")
    
    return 0 if all(s for s, d in results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
