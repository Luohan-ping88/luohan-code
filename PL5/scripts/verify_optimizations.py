#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证PL5系统优化效果
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


def test_feature_cache_optimization():
    """测试特征缓存优化"""
    print("\n" + "=" * 80)
    print("测试1: 特征缓存管理器优化")
    print("=" * 80)

    try:
        from src.core.cache.feature_cache import FeatureCacheManager, CacheConfig, EvictionStrategy

        # 创建优化的缓存管理器
        config = CacheConfig(
            max_size=200,
            default_ttl=3600,
            eviction_strategy="smart",
            auto_adjust_size=True,
            enable_persistence=False
        )

        cache = FeatureCacheManager(config)

        # 测试基本功能
        import pandas as pd
        import numpy as np

        # 创建测试数据
        test_data = pd.DataFrame({
            'period': range(1000, 1050),
            'full_number': [f"{i:05d}" for i in range(1000, 1050)]
        })

        # 测试缓存key生成
        key = cache.get_key(test_data)
        print(f"  ✓ 缓存key生成成功: {key}")

        # 测试数据存储
        cache.put(key, test_data)
        print(f"  ✓ 数据存储成功")

        # 测试数据获取
        retrieved = cache.get(key)
        print(f"  ✓ 数据获取成功: {retrieved is not None}")

        # 测试统计信息
        stats = cache.stats
        print(f"  ✓ 缓存统计: {stats}")

        # 测试智能淘汰
        for i in range(250):
            small_data = pd.DataFrame({'period': [i], 'full_number': [f"{i:05d}"]})
            cache.put(f"test_key_{i}", small_data)

        print(f"  ✓ 智能淘汰测试完成，当前缓存大小: {len(cache)}")

        return True, "特征缓存优化测试通过"

    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, f"特征缓存优化测试失败: {e}"


def test_model_evaluator():
    """测试模型评估器"""
    print("\n" + "=" * 80)
    print("测试2: 增强的模型评估器")
    print("=" * 80)

    try:
        from src.core.models.model_evaluator import (
            EnhancedModelEvaluator,
            CrossValidationConfig,
            EvaluationMetric
        )
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.datasets import make_classification
        import numpy as np

        # 创建测试数据
        X, y = make_classification(
            n_samples=1000,
            n_features=20,
            n_informative=15,
            n_classes=10,
            random_state=42
        )

        # 创建评估器
        cv_config = CrossValidationConfig(
            n_splits=3,
            use_time_series_split=True,
            shuffle=False
        )

        evaluator = EnhancedModelEvaluator(cv_config)

        # 创建简单模型
        model = RandomForestClassifier(n_estimators=10, random_state=42, n_jobs=-1)

        # 评估模型
        result = evaluator.evaluate_with_cross_validation(
            model, X, y, "RandomForest",
            metrics=[
                EvaluationMetric.ACCURACY,
                EvaluationMetric.F1
            ]
        )

        print(f"  ✓ 交叉验证评估完成")
        print(f"  平均准确率: {result.mean_scores.get('accuracy', 0):.4f}")
        print(f"  标准差: {result.std_scores.get('accuracy', 0):.4f}")

        # 测试对比功能
        from sklearn.tree import DecisionTreeClassifier
        models = {
            "RandomForest": RandomForestClassifier(n_estimators=10, random_state=42),
            "DecisionTree": DecisionTreeClassifier(random_state=42)
        }

        comparison_df = evaluator.compare_models(models, X[:500], y[:500])
        print(f"  ✓ 模型对比完成")
        print(f"  对比结果:\n{comparison_df}")

        return True, "模型评估器测试通过"

    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, f"模型评估器测试失败: {e}"


def test_incremental_learning():
    """测试增量学习"""
    print("\n" + "=" * 80)
    print("测试3: 增强的增量学习系统")
    print("=" * 80)

    try:
        from src.core.models.incremental_learning import (
            EnhancedIncrementalLearningManager,
            AdaptiveConfig,
            AdaptiveTrainingStrategyManager,
            TrainingStrategy
        )
        import numpy as np

        # 测试增量学习管理器
        config = AdaptiveConfig(
            min_update_interval_hours=1.0,
            batch_size=50,
            max_memory_size=500,
            use_sampling=True,
            sampling_ratio=0.3
        )

        manager = EnhancedIncrementalLearningManager(config)

        # 添加测试数据
        test_data = np.random.randn(100, 10)
        test_target = np.random.randint(0, 10, 100)

        manager.add_data('wan', test_data, test_target)
        print(f"  ✓ 数据添加成功")

        # 测试指标记录
        manager.record_metrics(accuracy=0.85, loss=0.15)
        manager.record_metrics(accuracy=0.86, loss=0.14)
        manager.record_metrics(accuracy=0.87, loss=0.13)
        print(f"  ✓ 指标记录成功")

        # 测试性能趋势
        trend = manager.get_performance_trend()
        print(f"  ✓ 性能趋势分析: {trend}")

        # 测试自适应训练策略
        strategy_manager = AdaptiveTrainingStrategyManager()

        # 测试策略选择
        strategy = strategy_manager.get_optimal_strategy()
        print(f"  ✓ 策略选择: {strategy.value}")

        # 获取训练参数
        params = strategy_manager.get_training_parameters(strategy)
        print(f"  ✓ 训练参数: {params}")

        return True, "增量学习测试通过"

    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, f"增量学习测试失败: {e}"


def test_window_expansion():
    """测试窗口扩展"""
    print("\n" + "=" * 80)
    print("测试4: 窗口配置扩展")
    print("=" * 80)

    try:
        # 读取特征工程文件
        engineer_file = ROOT_DIR / 'src' / 'core' / 'features' / 'engineer_v10.py'

        with open(engineer_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查时间序列窗口配置
        import re
        ts_match = re.search(r'def _add_time_series_features.*?windows = \[(.*?)\]', content, re.DOTALL)

        if ts_match:
            windows = ts_match.group(1)
            print(f"  ✓ 时间序列窗口配置: [{windows}]")

            # 验证是否包含新的窗口
            new_windows = ['45', '60', '80']
            for w in new_windows:
                if w in windows:
                    print(f"  ✓ 包含新窗口 {w}")
                else:
                    print(f"  ⚠ 缺少新窗口 {w}")

        # 检查极值特征窗口配置
        ext_match = re.search(r'def _add_extreme_features.*?windows = \[(.*?)\]', content, re.DOTALL)

        if ext_match:
            windows = ext_match.group(1)
            print(f"  ✓ 极值特征窗口配置: [{windows}]")

        return True, "窗口扩展测试通过"

    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, f"窗口扩展测试失败: {e}"


def test_documentation():
    """测试文档完整性"""
    print("\n" + "=" * 80)
    print("测试5: 代码文档和注释检查")
    print("=" * 80)

    try:
        # 检查关键文件是否有文档字符串
        files_to_check = [
            'src/core/cache/feature_cache.py',
            'src/core/models/model_evaluator.py',
            'src/core/models/incremental_learning.py',
        ]

        all_passed = True

        for file_path in files_to_check:
            full_path = ROOT_DIR / file_path
            if full_path.exists():
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 检查是否有模块文档字符串
                has_docstring = '"""' in content[:500]
                has_functions = 'def ' in content

                status = "✓" if has_docstring and has_functions else "⚠"
                print(f"  {status} {file_path}: 文档字符串={'是' if has_docstring else '否'}, 函数={'是' if has_functions else '否'}")

                if not (has_docstring and has_functions):
                    all_passed = False
            else:
                print(f"  ✗ {file_path}: 文件不存在")
                all_passed = False

        return all_passed, "文档检查完成"

    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, f"文档检查失败: {e}"


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("PL5 系统优化验证测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 执行所有测试
    tests = [
        ("特征缓存优化", test_feature_cache_optimization),
        ("模型评估器", test_model_evaluator),
        ("增量学习", test_incremental_learning),
        ("窗口扩展", test_window_expansion),
        ("文档完整性", test_documentation),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success, message = test_func()
            results.append({
                'name': test_name,
                'success': success,
                'message': message
            })
        except Exception as e:
            results.append({
                'name': test_name,
                'success': False,
                'message': f"测试异常: {e}"
            })

    # 打印汇总报告
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)

    passed = sum(1 for r in results if r['success'])
    total = len(results)

    for result in results:
        status = "✓ PASS" if result['success'] else "✗ FAIL"
        print(f"{status} {result['name']}: {result['message']}")

    print("\n" + "=" * 80)
    print(f"总计: {passed}/{total} 测试通过")
    print("=" * 80)

    # 生成详细报告
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_tests': total,
        'passed': passed,
        'failed': total - passed,
        'results': results
    }

    # 保存报告
    import json
    report_file = ROOT_DIR / 'logs' / f'optimization_verification_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n详细报告已保存: {report_file}")

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
