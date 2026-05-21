"""
先进特征工程测试脚本
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import time


def generate_test_data(n_samples=300):
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


def test_advanced_features():
    """测试先进特征"""
    print("\n" + "="*70)
    print("测试1: 先进特征工程")
    print("="*70)
    
    try:
        from src.core.features.advanced_features import AdvancedFeatureEngineering
        
        df = generate_test_data(300)
        
        extractor = AdvancedFeatureEngineering(use_cpp=True)
        
        start_time = time.time()
        features = extractor.extract_all_features(df)
        elapsed = time.time() - start_time
        
        print(f"✅ 先进特征提取成功")
        print(f"   耗时: {elapsed:.2f}秒")
        print(f"   特征数量: {len(features.columns)}")
        
        categories = {
            '多尺度时序': len([c for c in features.columns if '_ms_' in c]),
            '频域特征': len([c for c in features.columns if any(x in c for x in ['_freq_', '_spectral_'])]),
            '位置关联': len([c for c in features.columns if '_corr' in c or '_sum_' in c or '_product_' in c]),
            '统计检验': len([c for c in features.columns if any(x in c for x in ['_normality_', '_ks_', '_runs_', '_anderson_'])]),
            '信息论': len([c for c in features.columns if '_entropy' in c or '_cond_entropy' in c or '_mutual_info' in c]),
            '混沌分形': len([c for c in features.columns if any(x in c for x in ['_hurst', '_lyapunov', '_corr_dim', '_approx_entropy', '_sample_entropy'])]),
            '跨期特征': len([c for c in features.columns if any(x in c for x in ['_lag_', '_diff_', 'momentum', 'acceleration'])]),
            '分布特征': len([c for c in features.columns if any(x in c for x in ['_digit_', '_even_', '_odd_', '_small_', '_large_', '_prime_'])]),
        }
        
        print("\n   特征分布:")
        for cat, count in categories.items():
            print(f"   - {cat}: {count}")
        
        return True
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_comprehensive_features():
    """测试综合特征"""
    print("\n" + "="*70)
    print("测试2: 综合特征工程")
    print("="*70)
    
    try:
        from src.core.features.comprehensive_features import ComprehensiveFeatureExtractor
        
        df = generate_test_data(300)
        
        extractor = ComprehensiveFeatureExtractor(
            enable_advanced=True,
            enable_deep=False,
            enable_cpp=True
        )
        
        start_time = time.time()
        features = extractor.extract_all(df, include_deep=False)
        elapsed = time.time() - start_time
        
        print(f"✅ 综合特征提取成功")
        print(f"   耗时: {elapsed:.2f}秒")
        print(f"   特征数量: {len(features.columns)}")
        
        summary = extractor.get_feature_summary(features)
        print(f"\n   特征摘要:")
        print(f"   - 总特征数: {summary['total_features']}")
        print(f"   - 位置特征: {summary['position_features']}")
        print(f"   - 先进特征: {summary['advanced_features']}")
        
        return True
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_deep_features():
    """测试深度学习特征"""
    print("\n" + "="*70)
    print("测试3: 深度学习特征")
    print("="*70)
    
    try:
        from src.core.features.deep_features import DeepFeatureExtractor
        import torch
        
        print(f"PyTorch版本: {torch.__version__}")
        print(f"CUDA可用: {torch.cuda.is_available()}")
        
        df = generate_test_data(200)
        
        extractor = DeepFeatureExtractor(device='cpu')
        extractor.initialize()
        
        features = extractor.extract_features(df, sequence_length=50)
        
        print(f"✅ 深度学习特征提取成功")
        print(f"   特征数量: {len(features.columns)}")
        
        deep_cols = [c for c in features.columns if any(x in c for x in ['_ae_feat_', '_conv_feat_', '_attn_feat_'])]
        print(f"   深度特征数: {len(deep_cols)}")
        
        return True
    
    except ImportError:
        print("⚠️ PyTorch未安装，跳过深度学习特征测试")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("PL5先进特征工程测试")
    print("="*70)
    
    results = []
    
    results.append(("先进特征工程", test_advanced_features()))
    results.append(("综合特征工程", test_comprehensive_features()))
    results.append(("深度学习特征", test_deep_features()))
    
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
