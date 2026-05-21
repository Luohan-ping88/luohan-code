#!/usr/bin/env python
"""
V11先进特征工程集成测试脚本
测试V10和V11特征工程的功能
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

def test_v10_feature_engineer():
    """测试V10特征工程"""
    print("\n" + "="*60)
    print("测试 1: V10特征工程")
    print("="*60)
    
    try:
        from src.core.features.engineer import FeatureEngineer
        
        df = generate_test_data(300)
        print(f"测试数据: {len(df)} 条")
        
        start = time.time()
        engineer = FeatureEngineer()
        df_features = engineer.extract_all_features(df, select_top=None)
        elapsed = time.time() - start
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        feature_cols = [c for c in df_features.columns if c not in ['period', 'full_number'] + positions]
        
        print(f"✓ V10特征提取成功")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  特征总数: {len(feature_cols)}")
        print(f"  列名预览: {list(feature_cols)[:10]}")
        
        return True, {
            'success': True,
            'feature_count': len(feature_cols),
            'elapsed': elapsed
        }
    except Exception as e:
        print(f"✗ V10测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, {'success': False, 'error': str(e)}

def test_v11_feature_engineer():
    """测试V11特征工程"""
    print("\n" + "="*60)
    print("测试 2: V11特征工程 (v11_advanced模式)")
    print("="*60)
    
    try:
        from src.core.features.v11_engineer import V11FeatureEngineer
        
        df = generate_test_data(300)
        print(f"测试数据: {len(df)} 条")
        
        start = time.time()
        engineer = V11FeatureEngineer(mode='v11_advanced')
        df_features = engineer.extract_all_features(df, select_top=None)
        elapsed = time.time() - start
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        feature_cols = [c for c in df_features.columns if c not in ['period', 'full_number'] + positions]
        
        print(f"✓ V11特征提取成功")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  特征总数: {len(feature_cols)}")
        
        # 统计V11新增的高级特征
        v11_features = [c for c in feature_cols if any(kw in c for kw in 
            ['ms_', 'dominant_freq', 'spectral_entropy', '_corr_with', 
             'normality_stat', 'ks_stat', 'runs_stat', 
             'hurst', 'lyapunov', 'corr_dim', 'approx_entropy', 'sample_entropy',
             'momentum', 'acceleration', 'digit_mode', 'gini_coefficient',
             'even_ratio', 'odd_ratio', 'small_ratio', 'large_ratio', 'prime_ratio'])]
        
        print(f"  高级特征数: {len(v11_features)}")
        print(f"  高级特征示例: {v11_features[:15]}")
        
        return True, {
            'success': True,
            'mode': 'v11_advanced',
            'feature_count': len(feature_cols),
            'advanced_feature_count': len(v11_features),
            'elapsed': elapsed
        }
    except Exception as e:
        print(f"✗ V11测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, {'success': False, 'error': str(e)}

def test_comprehensive_extractor():
    """测试综合特征提取器"""
    print("\n" + "="*60)
    print("测试 3: 综合特征提取器")
    print("="*60)
    
    try:
        from src.core.features.comprehensive_features import ComprehensiveFeatureExtractor
        
        df = generate_test_data(300)
        
        extractor = ComprehensiveFeatureExtractor(
            enable_advanced=True,
            enable_deep=False,
            enable_cpp=True
        )
        
        start = time.time()
        df_features = extractor.extract_all(df, include_deep=False)
        elapsed = time.time() - start
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        feature_cols = [c for c in df_features.columns if c not in ['period', 'full_number'] + positions]
        
        print(f"✓ 综合特征提取成功")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  特征总数: {len(feature_cols)}")
        
        summary = extractor.get_feature_summary(df_features)
        print(f"  特征摘要: {summary}")
        
        return True, {
            'success': True,
            'feature_count': len(feature_cols),
            'elapsed': elapsed,
            'summary': summary
        }
    except Exception as e:
        print(f"✗ 综合特征提取器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, {'success': False, 'error': str(e)}

def test_advanced_features_import():
    """测试高级特征模块的导入"""
    print("\n" + "="*60)
    print("测试 4: 模块导入测试")
    print("="*60)
    
    tests = []
    
    # 测试1: V11特征工程
    try:
        from src.core.features import v11_engineer
        tests.append(('v11_engineer', True))
        print("✓ v11_engineer 导入成功")
    except:
        tests.append(('v11_engineer', False))
        print("✗ v11_engineer 导入失败")
    
    # 测试2: 先进特征
    try:
        from src.core.features import advanced_features
        tests.append(('advanced_features', True))
        print("✓ advanced_features 导入成功")
    except:
        tests.append(('advanced_features', False))
        print("✗ advanced_features 导入失败")
    
    # 测试3: 综合特征
    try:
        from src.core.features import comprehensive_features
        tests.append(('comprehensive_features', True))
        print("✓ comprehensive_features 导入成功")
    except:
        tests.append(('comprehensive_features', False))
        print("✗ comprehensive_features 导入失败")
    
    # 测试4: 深度学习特征（可选）
    try:
        from src.core.features import deep_features
        tests.append(('deep_features', True))
        print("✓ deep_features 导入成功")
    except Exception as e:
        tests.append(('deep_features', False))
        print(f"⚠ deep_features 导入失败 (PyTorch未安装): {e}")
    
    return all(t[1] for t in tests), dict(tests)

def print_report(results):
    """打印测试报告"""
    print("\n" + "="*60)
    print("集成测试报告")
    print("="*60)
    
    for name, (success, data) in results.items():
        status = "✓ 通过" if success else "✗ 失败"
        print(f"\n{name}: {status}")
        if success:
            for k, v in data.items():
                if k != 'success':
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
    print("PL5 V11先进特征工程集成测试")
    print("="*60)
    
    results = {}
    
    # 运行所有测试
    results['测试1: V10特征工程'] = test_v10_feature_engineer()
    results['测试2: V11特征工程'] = test_v11_feature_engineer()
    results['测试3: 综合特征提取器'] = test_comprehensive_extractor()
    results['测试4: 模块导入测试'] = test_advanced_features_import()
    
    # 打印报告
    print_report(results)
    
    # 保存报告
    report_path = Path('logs') / 'v11_integration_test_report.json'
    report_path.parent.mkdir(exist_ok=True)
    
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
