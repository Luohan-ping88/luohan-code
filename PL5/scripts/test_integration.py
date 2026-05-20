"""
优化模块集成测试
测试优化模块与现有系统的集成
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple


def test_integration_basic() -> bool:
    """基础集成测试"""
    print("\n" + "="*60)
    print("测试1: 基础集成")
    print("="*60)

    try:
        from src.core.models.optimization_integration import (
            OptimizationIntegrationMixin,
            OptimizedEnhancedPredictorAdapter
        )

        print("✓ 导入成功: OptimizationIntegrationMixin")
        print("✓ 导入成功: OptimizedEnhancedPredictorAdapter")

        mixin = OptimizationIntegrationMixin()
        mixin._opt_config = {}
        mixin._optimization_enabled = True
        mixin._init_feature_optimization()
        mixin._init_weight_optimization()
        mixin._init_model_optimization()

        print("✓ 混入类初始化成功")

        return True

    except Exception as e:
        print(f"✗ 基础集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_adapter_pattern():
    """适配器模式测试"""
    print("\n" + "="*60)
    print("测试2: 适配器模式")
    print("="*60)

    try:
        from src.core.models.optimization_integration import OptimizedEnhancedPredictorAdapter

        class MockPredictor:
            def __init__(self):
                self.is_trained = True

            def fit(self, df, feature_cols, **kwargs):
                print(f"  Mock fit called with {len(feature_cols)} features")
                return self

            def predict(self, features, recent_data, top_k, **kwargs):
                return {
                    pos: {
                        'top_k': list(range(top_k)),
                        'probabilities': [0.1] * top_k,
                        'uncertainty': 0.5
                    }
                    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']
                }

            def update_with_feedback(self, predictions, actual):
                print("  Mock update_with_feedback called")

        mock_predictor = MockPredictor()

        adapter = OptimizedEnhancedPredictorAdapter(
            mock_predictor,
            config={
                'optimization': {
                    'feature_selection': {'enabled': True},
                    'fusion_strategy': {'enabled': True},
                    'ensemble': {'enabled': True}
                }
            }
        )

        print("✓ 适配器创建成功")

        adapter.base_predictor.is_trained = True
        result = adapter.predict(np.random.randn(50), top_k=5)
        print(f"✓ 预测成功，返回位置: {list(result.keys())}")

        return True

    except Exception as e:
        print(f"✗ 适配器模式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_optimization():
    """特征优化测试"""
    print("\n" + "="*60)
    print("测试3: 特征优化")
    print("="*60)

    try:
        from src.core.models.optimization_integration import OptimizationIntegrationMixin

        mixin = OptimizationIntegrationMixin()
        mixin._opt_config = {
            'optimization': {
                'feature_selection': {
                    'enabled': True,
                    'decay_factor': 0.95,
                    'min_importance': 0.01,
                    'max_features_per_group': 3,
                    'warmup_periods': 5,
                    'min_select': 10,
                    'max_select': 50
                },
                'feature_interaction': {
                    'enable_position_cross': True,
                    'enable_temporal_cross': True,
                    'enable_frequency_cross': True,
                    'max_interaction_features': 20,
                    'lag_windows': [1, 2]
                }
            }
        }
        mixin._optimization_enabled = True
        mixin._init_feature_optimization()

        print("✓ 特征优化模块初始化成功")

        df = generate_mock_data(100)
        feature_cols = [f'feat_{i}' for i in range(10)]

        df_enhanced, selected = mixin.optimize_features(df, feature_cols)
        print(f"✓ 特征优化完成: {len(feature_cols)} -> {len(selected)}")

        return True

    except Exception as e:
        print(f"✗ 特征优化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_weight_fusion():
    """权重融合测试"""
    print("\n" + "="*60)
    print("测试4: 权重融合")
    print("="*60)

    try:
        from src.core.models.optimization_integration import OptimizationIntegrationMixin

        mixin = OptimizationIntegrationMixin()
        mixin._opt_config = {
            'optimization': {
                'fusion_strategy': {
                    'enabled': True,
                    'context_dim': 32,
                    'history_window': 30,
                    'confidence_temperature': 1.0
                }
            }
        }
        mixin._optimization_enabled = True
        mixin._init_weight_optimization()

        print("✓ 权重融合模块初始化成功")

        predictions = {
            'stacking': np.random.dirichlet(np.ones(10)),
            'hmm': np.random.dirichlet(np.ones(10)),
            'copula': np.random.dirichlet(np.ones(10)),
            'bayesian': np.random.dirichlet(np.ones(10)),
            'mamba': np.random.dirichlet(np.ones(10)),
        }

        fused = mixin.weight_fusion.fuse_predictions(predictions)
        print(f"✓ 融合完成: 概率和 = {fused.sum():.4f}")

        summary = mixin.weight_fusion.get_performance_summary()
        print(f"✓ 性能摘要 keys: {list(summary.keys())}")

        return True

    except Exception as e:
        print(f"✗ 权重融合测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feedback_update():
    """反馈更新测试"""
    print("\n" + "="*60)
    print("测试5: 反馈更新")
    print("="*60)

    try:
        from src.core.models.optimization_integration import OptimizationIntegrationMixin

        mixin = OptimizationIntegrationMixin()
        mixin._opt_config = {
            'optimization': {
                'feature_selection': {'enabled': True},
                'fusion_strategy': {'enabled': True}
            }
        }
        mixin._optimization_enabled = True
        mixin._init_feature_optimization()
        mixin._init_weight_optimization()
        mixin._is_optimized_fitted = True

        predictions = {
            'wan': [1, 2, 3, 4, 5],
            'qian': [6, 7, 8, 9, 0],
            'bai': [1, 2, 3, 4, 5],
            'shi': [6, 7, 8, 9, 0],
            'ge': [1, 2, 3, 4, 5]
        }
        actual = {
            'wan': 2,
            'qian': 8,
            'bai': 3,
            'shi': 7,
            'ge': 4
        }

        mixin.update_optimization_with_feedback(predictions, actual)
        print("✓ 反馈更新成功")

        summary = mixin.get_optimization_summary()
        print(f"✓ 摘要生成成功: {summary.get('is_fitted', False)}")

        return True

    except Exception as e:
        print(f"✗ 反馈更新测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_save_load() -> bool:
    """状态保存/加载测试"""
    print("\n" + "="*60)
    print("测试6: 状态保存/加载")
    print("="*60)

    try:
        from src.core.models.optimization_integration import OptimizationIntegrationMixin
        import tempfile
        import os

        mixin = OptimizationIntegrationMixin()
        mixin._opt_config = {
            'optimization': {
                'feature_selection': {'enabled': True},
                'fusion_strategy': {'enabled': True}
            }
        }
        mixin._optimization_enabled = True
        mixin._init_feature_optimization()
        mixin._init_weight_optimization()
        mixin._selected_features = [f'feat_{i}' for i in range(20)]
        mixin._interaction_features = [f'inter_{i}' for i in range(10)]
        mixin._is_optimized_fitted = True

        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            temp_path = Path(f.name)

        try:
            mixin.save_optimization_state(temp_path)
            print(f"✓ 状态保存成功: {temp_path}")

            mixin2 = OptimizationIntegrationMixin()
            mixin2._opt_config = mixin._opt_config
            mixin2._optimization_enabled = True
            mixin2._init_feature_optimization()
            mixin2._init_weight_optimization()

            mixin2.load_optimization_state(temp_path)
            print(f"✓ 状态加载成功")
            print(f"  加载的特征数: {len(mixin2._selected_features)}")

        finally:
            if temp_path.exists():
                os.unlink(temp_path)

        return True

    except Exception as e:
        print(f"✗ 状态保存/加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_mock_data(n_samples: int) -> pd.DataFrame:
    """生成模拟数据"""
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

    for w in [5, 10]:
        for pos in ['wan', 'qian', 'bai']:
            data[f'rolling_mean_{w}_{pos}'] = (
                pd.Series(data[pos]).rolling(w).mean().fillna(method='bfill').astype(int)
            )

    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        data[f'feat_{pos}_1'] = np.random.random(n_samples)
        data[f'feat_{pos}_2'] = np.random.random(n_samples)

    return pd.DataFrame(data)


def run_integration_tests() -> bool:
    """运行所有集成测试"""
    print("\n" + "="*60)
    print("PL5 优化模块集成测试")
    print("="*60)

    tests = [
        ("基础集成", test_integration_basic),
        ("适配器模式", test_adapter_pattern),
        ("特征优化", test_feature_optimization),
        ("权重融合", test_weight_fusion),
        ("反馈更新", test_feedback_update),
        ("状态保存/加载", test_state_save_load),
    ]

    results = []

    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"✗ 测试异常: {e}")
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
    success = run_integration_tests()
    sys.exit(0 if success else 1)
