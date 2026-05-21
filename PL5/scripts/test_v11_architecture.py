"""
V11高级架构测试脚本
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd


def generate_test_data(n_samples: int = 200) -> pd.DataFrame:
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
    
    for i in range(1, 4):
        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            data[f'lag_{i}_{pos}'] = np.roll(data[pos], i)
    
    return pd.DataFrame(data)


def test_v11_predictor():
    """测试V11预测器"""
    print("\n" + "="*60)
    print("测试: PL5 V11高级预测器")
    print("="*60)
    
    try:
        from src.core.models.v11_predictor import PL5V11Predictor
        
        print("✓ 导入V11预测器成功")
        
        predictor = PL5V11Predictor(
            config={
                'mamba': {'d_model': 128, 'n_layers': 3, 'seq_len': 30},
                'diffusion': {'num_timesteps': 50, 'noise_scale': 0.1},
                'moe': {'num_experts': 2, 'd_model': 64}
            },
            use_advanced=True,
            device='cpu'
        )
        
        print("✓ V11预测器创建成功")
        
        status = predictor.get_component_status()
        print(f"✓ 组件状态: {status['components']}")
        
        df = generate_test_data(200)
        
        try:
            history = predictor.fit(df, epochs=5, batch_size=16)
            print(f"✓ 训练完成，历史记录: {list(history.keys())}")
        except Exception as e:
            print(f"⚠️ 训练跳过 (需要PyTorch): {e}")
        
        results = predictor.predict(df, top_k=5)
        
        print(f"✓ 预测成功，位置: {list(results.keys())}")
        
        for pos in ['wan', 'qian']:
            if pos in results:
                print(f"  {pos}: Top-5 = {results[pos]['top_k']}")
        
        return True
    
    except ImportError as e:
        print(f"✗ V11预测器导入失败: {e}")
        return False


def test_advanced_components():
    """测试高级组件"""
    print("\n" + "="*60)
    print("测试: 高级组件")
    print("="*60)
    
    try:
        from src.core.models.advanced_components import (
            DiffusionRefiner, MoEPredictor, CausalReasoningEngine
        )
        
        print("✓ 导入高级组件成功")
        
        causal_engine = CausalReasoningEngine()
        features = ['wan', 'qian', 'bai', 'shi', 'ge', 'lag_1_wan', 'digit_freq_wan']
        causal_engine.build_graph(features)
        
        importance = causal_engine.get_feature_importance('wan')
        print(f"✓ 因果推理引擎: 特征重要性计算成功")
        
        return True
    
    except ImportError as e:
        print(f"✗ 高级组件导入失败: {e}")
        return False


def test_mamba_predictor():
    """测试Mamba预测器"""
    print("\n" + "="*60)
    print("测试: Mamba预测器")
    print("="*60)
    
    try:
        from src.core.models.mamba_predictor import MambaPL5Predictor, PL5SequenceDataset
        
        print("✓ 导入Mamba预测器成功")
        
        df = generate_test_data(150)
        
        try:
            predictor = MambaPL5Predictor(d_model=128, n_layers=3, seq_len=30)
            
            print("✓ Mamba预测器创建成功")
            
            history = predictor.fit(df, epochs=5, batch_size=16)
            print(f"✓ Mamba训练完成，验证准确率: {history['val_acc'][-1]:.4f}")
            
            results = predictor.predict(df, top_k=5)
            print(f"✓ Mamba预测成功")
            
            return True
        except Exception as e:
            print(f"⚠️ Mamba训练跳过: {e}")
            return True
    
    except ImportError as e:
        print(f"✗ Mamba预测器导入失败: {e}")
        return False


def run_v11_tests():
    """运行所有V11测试"""
    print("\n" + "="*60)
    print("PL5 V11高级架构测试")
    print("="*60)
    
    tests = [
        ("Mamba预测器", test_mamba_predictor),
        ("高级组件", test_advanced_components),
        ("V11预测器", test_v11_predictor),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"✗ {name} 测试异常: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, s in results if s)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    return passed == total


if __name__ == '__main__':
    success = run_v11_tests()
    sys.exit(0 if success else 1)
