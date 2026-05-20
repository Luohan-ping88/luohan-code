"""
优化模块综合测试脚本

测试各优化模块的功能:
1. AdaptiveFeatureSelector - 自适应特征选择
2. FeatureInteractionExtractor - 特征交互提取
3. ContextAwareWeightFusion - 上下文感知权重融合
4. EnhancedStackingEnsemble - 增强Stacking集成
5. TailAwareCopula - 尾部敏感Copula
"""

import numpy as np
import pandas as pd
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.features.adaptive_selector import AdaptiveFeatureSelector, OnlineImportanceTracker
from src.core.features.interaction_extractor import FeatureInteractionExtractor
from src.core.models.context_weight_fusion import ContextAwareWeightFusion, ThompsonSamplingOptimizer
from src.core.models.enhanced_stacking import EnhancedStackingEnsemble
from src.core.models.tail_aware_copula import TailAwareCopula, GaussianCopula, TCopula, GumbelCopula
from src.core.models.optimized_predictor import OptimizedPredictor


def generate_sample_data(n_samples: int = 500) -> pd.DataFrame:
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
    
    for i in range(1, 6):
        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            data[f'lag_{i}_{pos}'] = np.roll(data[pos], i)
    
    for w in [5, 10, 20]:
        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            data[f'rolling_mean_{w}_{pos}'] = pd.Series(data[pos]).rolling(w).mean().fillna(method='bfill').astype(int)
            data[f'rolling_std_{w}_{pos}'] = pd.Series(data[pos]).rolling(w).std().fillna(0)
    
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        data[f'{pos}_digit_freq'] = np.random.random(n_samples)
        data[f'fib_{pos}'] = np.random.randint(0, 20, n_samples)
        data[f'entropy_{pos}'] = np.random.random(n_samples)
    
    return pd.DataFrame(data)


def test_feature_selector():
    """测试自适应特征选择器"""
    print("\n" + "="*60)
    print("测试1: AdaptiveFeatureSelector")
    print("="*60)
    
    selector = AdaptiveFeatureSelector(
        decay_factor=0.95,
        min_importance=0.01,
        max_features_per_group=3,
        warmup_periods=5
    )
    
    selector.register_group('fibonacci', [f'fib_wan_{i}' for i in range(5)])
    selector.register_group('entropy', [f'entropy_wan_{i}' for i in range(3)])
    
    for period in range(10):
        importance = {
            f'fib_wan_{i}': np.random.random() * (1 if i < 3 else 0.5)
            for i in range(5)
        }
        importance.update({
            f'entropy_wan_{i}': np.random.random() * (1 if i < 2 else 0.3)
            for i in range(3)
        })
        selector.update(importance, period)
    
    selected = selector.get_selected_features(
        list(importance.keys()),
        min_count=5,
        max_count=10
    )
    
    ranking = selector.get_group_statistics()
    
    print(f"✓ 选中特征数量: {len(selected)}")
    print(f"✓ 特征组统计: {list(ranking.keys())}")
    
    return True


def test_interaction_extractor() -> bool:
    """测试特征交互提取器"""
    print("\n" + "="*60)
    print("测试2: FeatureInteractionExtractor")
    print("="*60)
    
    df = generate_sample_data(200)
    
    extractor = FeatureInteractionExtractor(
        enable_position_cross=True,
        enable_temporal_cross=True,
        enable_frequency_cross=True,
        max_interaction_features=30
    )
    
    result_df = extractor.extract_all(df, lag_windows=[1, 2, 3])
    
    interaction_cols = [c for c in result_df.columns if '_' in c and any(
        prefix in c for prefix in ['position_', 'temporal_', 'freq_', 'stat_']
    )]
    
    importance = extractor.get_feature_importance(result_df)
    
    print(f"✓ 提取交互特征数: {len(interaction_cols)}")
    print(f"✓ 样本交互特征: {interaction_cols[:5] if interaction_cols else 'None'}")
    print(f"✓ 特征重要性计算成功")
    
    return True


def test_weight_fusion():
    """测试上下文感知权重融合"""
    print("\n" + "="*60)
    print("测试3: ContextAwareWeightFusion")
    print("="*60)
    
    fusion = ContextAwareWeightFusion(
        context_dim=32,
        history_window=30,
        enable_online_update=True
    )
    
    weights = fusion.get_weights()
    print(f"✓ 初始权重: {weights}")
    
    predictions = {
        'stacking': np.random.dirichlet(np.ones(10)),
        'hmm': np.random.dirichlet(np.ones(10)),
        'copula': np.random.dirichlet(np.ones(10)),
    }
    
    fused = fusion.fuse_predictions(predictions, use_confidence_weighting=True)
    print(f"✓ 融合概率和: {fused.sum():.4f}")
    
    actual = {'wan': 3, 'qian': 7, 'bai': 1, 'shi': 5, 'ge': 9}
    pred_results = {
        'stacking': {'wan': [1, 2, 3, 4, 5]},
        'hmm': {'wan': [7, 8, 9, 0, 1]},
        'copula': {'wan': [2, 3, 4, 5, 6]},
    }
    
    fusion.update_with_feedback(pred_results, actual)
    summary = fusion.get_performance_summary()
    print(f"✓ 性能摘要 keys: {list(summary.keys())}")
    
    return True


def test_enhanced_stacking() -> bool:
    """测试增强Stacking集成"""
    print("\n" + "="*60)
    print("测试4: EnhancedStackingEnsemble")
    print("="*60)
    
    df = generate_sample_data(300)
    feature_cols = [
        c for c in df.columns
        if c not in ['period', 'wan', 'qian', 'bai', 'shi', 'ge']
    ]
    
    stacking = EnhancedStackingEnsemble(
        diversity_threshold=0.7,
        cv_folds=3,
        enable_calibration=True
    )
    
    stacking.fit(df, feature_cols)
    
    X_sample = df[feature_cols].fillna(0).iloc[-10:].values
    predictions = stacking.predict(X_sample)
    
    print(f"✓ 预测位置: {list(predictions.keys())}")
    print(f"✓ 各位置概率和: {[round(predictions[p].sum(), 2) for p in predictions]}")
    
    return True


def test_tail_copula():
    """测试尾部敏感Copula"""
    print("\n" + "="*60)
    print("测试5: TailAwareCopula")
    print("="*60)
    
    copula = TailAwareCopula(
        copula_types=['gaussian', 't', 'gumbel'],
        enable_tail_boost=True,
        tail_threshold=0.1
    )
    
    np.random.seed(42)
    data = np.random.uniform(0.2, 0.8, (200, 3))
    
    copula.fit(data)
    
    test_u = np.random.uniform(0.1, 0.9, (10, 3))
    pdf_vals = copula.pdf(test_u)
    
    tail_dep = copula.get_tail_dependence()
    
    marginals = {
        0: np.random.dirichlet(np.ones(10)),
        1: np.random.dirichlet(np.ones(10)),
        2: np.random.dirichlet(np.ones(10)),
    }
    
    joint_probs = copula.predict_joint_probability(marginals)
    
    print(f"✓ 混合权重: {dict(zip(copula.copulas.keys(), copula.mixture_weights))}")
    print(f"✓ 尾部依赖: {tail_dep}")
    print(f"✓ 联合概率和: {joint_probs.sum():.4f}")
    
    return True


def test_optimized_predictor():
    """测试优化预测器集成"""
    print("\n" + "="*60)
    print("测试6: OptimizedPredictor (综合测试)")
    print("="*60)
    
    df = generate_sample_data(300)
    feature_cols = [
        c for c in df.columns
        if c not in ['period', 'wan', 'qian', 'bai', 'shi', 'ge']
    ]
    
    predictor = OptimizedPredictor(
        enable_feature_optimization=True,
        enable_weight_optimization=True,
        enable_model_optimization=True,
        config={
            'decay_factor': 0.95,
            'context_dim': 32,
            'diversity_threshold': 0.7,
        }
    )
    
    predictor.fit(df, feature_cols, fit_stacking=True, fit_copula=True)
    
    results = predictor.predict(df, features=df[feature_cols].fillna(0).iloc[-1].values)
    
    summary = predictor.get_optimization_summary()
    
    print(f"✓ 预测位置: {list(results.keys())}")
    print(f"✓ 选中特征数: {summary['selected_features_count']}")
    print(f"✓ 模型权重: {summary.get('model_weights', {}).get('current_weights')}")
    
    for pos in ['wan', 'qian']:
        if pos in results:
            print(f"✓ {pos} Top-3: {results[pos]['top_k'][:3]}")
    
    return True


def run_all_tests() -> bool:
    """运行所有测试"""
    print("\n" + "="*60)
    print("PL5 优化模块综合测试")
    print("="*60)
    
    tests = [
        ("自适应特征选择", test_feature_selector),
        ("特征交互提取", test_interaction_extractor),
        ("上下文感知权重融合", test_weight_fusion),
        ("增强Stacking集成", test_enhanced_stacking),
        ("尾部敏感Copula", test_tail_copula),
        ("优化预测器集成", test_optimized_predictor),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
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
    success = run_all_tests()
    sys.exit(0 if success else 1)
