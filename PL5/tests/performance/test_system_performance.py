"""
系统性能测试
测试系统的性能指标和资源使用
"""

import pytest
import time
import psutil
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import asyncio
from functools import wraps

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.features.engineer import FeatureEngineer
from src.core.models import PL5Predictor
from src.core.data.validator import AdvancedDataValidator, ValidationLevel


def measure_performance(func):
    """性能测量装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss

        result = func(*args, **kwargs)

        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss

        execution_time = end_time - start_time
        memory_used = (end_memory - start_memory) / (1024 * 1024)  # MB

        return result, execution_time, memory_used

    return wrapper


def measure_performance_async(func):
    """异步性能测量装饰器"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss

        result = await func(*args, **kwargs)

        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss

        execution_time = end_time - start_time
        memory_used = (end_memory - start_memory) / (1024 * 1024)  # MB

        return result, execution_time, memory_used

    return wrapper


class TestFeatureEngineeringPerformance:
    """特征工程性能测试"""

    @pytest.fixture
    def generate_test_data(self):
        """生成测试数据"""

        def _generate(n_records):
            np.random.seed(42)

            data = pd.DataFrame(
                {
                    "period": [f"2026{str(i).zfill(3)}" for i in range(1001, 1001 + n_records)],
                    "wan": np.random.randint(0, 10, n_records),
                    "qian": np.random.randint(0, 10, n_records),
                    "bai": np.random.randint(0, 10, n_records),
                    "shi": np.random.randint(0, 10, n_records),
                    "ge": np.random.randint(0, 10, n_records),
                }
            )

            return data

        return _generate

    @pytest.mark.parametrize("n_records", [100, 500, 1000])
    def test_feature_engineering_speed(self, generate_test_data, n_records, benchmark):
        """测试特征工程速度"""
        data = generate_test_data(n_records)
        engineer = FeatureEngineer()

        # 使用pytest-benchmark进行基准测试
        def run_feature_engineering():
            return engineer.extract_all_features(data)

        result = benchmark(run_feature_engineering)

        # 验证结果
        assert result is not None
        assert len(result) == n_records
        assert len(result.columns) > len(data.columns)

    @pytest.mark.parametrize("n_records", [100, 500, 1000])
    def test_feature_engineering_memory(self, generate_test_data, n_records):
        """测试特征工程内存使用"""
        data = generate_test_data(n_records)
        engineer = FeatureEngineer()

        # 测量性能
        result, execution_time, memory_used = measure_performance(engineer.extract_all_features)(data)

        # 记录性能指标
        print(f"\n特征工程性能 (n={n_records}):")
        print(f"  执行时间: {execution_time:.3f}秒")
        print(f"  内存使用: {memory_used:.2f} MB")
        print(f"  特征数量: {len(result.columns)}")

        # 性能要求
        if n_records <= 500:
            assert execution_time < 10.0, f"特征工程太慢: {execution_time:.3f}秒"
            assert memory_used < 500.0, f"特征工程内存使用太高: {memory_used:.2f} MB"

    def test_feature_engineering_scalability(self, generate_test_data):
        """测试特征工程可扩展性"""
        sizes = [100, 200, 400, 800]
        times = []

        for size in sizes:
            data = generate_test_data(size)
            engineer = FeatureEngineer()

            start_time = time.time()
            engineer.extract_all_features(data)
            end_time = time.time()

            execution_time = end_time - start_time
            times.append(execution_time)

            print(f"  数据量 {size}: {execution_time:.3f}秒")

        # 检查是否近似线性增长
        ratios = [times[i] / times[0] for i in range(1, len(times))]
        size_ratios = [sizes[i] / sizes[0] for i in range(1, len(sizes))]

        # 允许一定的非线性（特征工程可能不是完全线性的）
        for i, (time_ratio, size_ratio) in enumerate(zip(ratios, size_ratios)):
            assert time_ratio <= size_ratio * 1.5, f"可扩展性不佳: {time_ratio:.2f}倍时间对应{size_ratio:.1f}倍数据"


class TestModelTrainingPerformance:
    """模型训练性能测试"""

    @pytest.fixture
    def generate_training_data(self):
        """生成训练数据"""

        def _generate(n_samples, n_features):
            np.random.seed(42)

            # 创建特征数据
            features = pd.DataFrame(
                np.random.randn(n_samples, n_features), columns=[f"feature_{i}" for i in range(n_features)]
            )

            # 添加目标变量
            positions = ["wan", "qian", "bai", "shi", "ge"]
            for pos in positions:
                features[pos] = np.random.randint(0, 10, n_samples)

            features["period"] = [f"2026{str(i).zfill(3)}" for i in range(1001, 1001 + n_samples)]

            return features

        return _generate

    @pytest.mark.parametrize("n_samples,n_features", [(100, 50), (500, 100), (1000, 200)])
    def test_model_training_speed(self, generate_training_data, n_samples, n_features, benchmark):
        """测试模型训练速度"""
        features = generate_training_data(n_samples, n_features)
        feature_cols = [col for col in features.columns if col not in ["period", "wan", "qian", "bai", "shi", "ge"]]

        predictor = PL5Predictor()

        # 使用pytest-benchmark进行基准测试
        def run_model_training():
            predictor.fit(features, feature_cols)
            return predictor

        result = benchmark(run_model_training)

        # 验证结果
        assert result is not None
        assert result.ensemble_models is not None

    @pytest.mark.parametrize("n_samples,n_features", [(100, 50), (500, 100)])
    def test_model_training_memory(self, generate_training_data, n_samples, n_features):
        """测试模型训练内存使用"""
        features = generate_training_data(n_samples, n_features)
        feature_cols = [col for col in features.columns if col not in ["period", "wan", "qian", "bai", "shi", "ge"]]

        predictor = PL5Predictor()

        # 测量性能
        result, execution_time, memory_used = measure_performance(predictor.fit)(features, feature_cols)

        # 记录性能指标
        print(f"\n模型训练性能 (n={n_samples}, features={n_features}):")
        print(f"  执行时间: {execution_time:.3f}秒")
        print(f"  内存使用: {memory_used:.2f} MB")

        # 性能要求
        if n_samples <= 500:
            assert execution_time < 30.0, f"模型训练太慢: {execution_time:.3f}秒"
            assert memory_used < 1000.0, f"模型训练内存使用太高: {memory_used:.2f} MB"

    def test_model_prediction_speed(self, generate_training_data):
        """测试模型预测速度"""
        # 准备数据
        features = generate_training_data(500, 100)
        feature_cols = [col for col in features.columns if col not in ["period", "wan", "qian", "bai", "shi", "ge"]]

        # 训练模型
        predictor = PL5Predictor()
        predictor.fit(features, feature_cols)

        # 测试预测速度
        test_features = features[feature_cols].iloc[-10:].values  # 最后10条数据

        start_time = time.time()
        predictions = []

        for i in range(10):  # 预测10次
            pred = predictor.predict(test_features[i], top_k=3)
            predictions.append(pred)

        end_time = time.time()
        avg_prediction_time = (end_time - start_time) / 10

        print(f"\n模型预测性能:")
        print(f"  平均预测时间: {avg_prediction_time:.4f}秒")
        print(f"  预测速度: {1/avg_prediction_time:.1f} 预测/秒")

        # 性能要求：单次预测应该很快
        assert avg_prediction_time < 0.1, f"模型预测太慢: {avg_prediction_time:.4f}秒"


class TestDataValidationPerformance:
    """数据验证性能测试"""

    @pytest.fixture
    def generate_validation_data(self):
        """生成验证数据"""

        def _generate(n_records, error_rate=0.0):
            np.random.seed(42)

            data = pd.DataFrame(
                {
                    "period": [f"2026{str(i).zfill(3)}" for i in range(1001, 1001 + n_records)],
                    "wan": np.random.randint(0, 10, n_records),
                    "qian": np.random.randint(0, 10, n_records),
                    "bai": np.random.randint(0, 10, n_records),
                    "shi": np.random.randint(0, 10, n_records),
                    "ge": np.random.randint(0, 10, n_records),
                }
            )

            # 添加一些错误（如果指定了错误率）
            if error_rate > 0:
                n_errors = int(n_records * error_rate)
                error_indices = np.random.choice(n_records, n_errors, replace=False)

                for idx in error_indices:
                    # 随机选择一个字段设置为无效值
                    field = np.random.choice(["wan", "qian", "bai", "shi", "ge"])
                    data.loc[idx, field] = np.random.choice([-1, 10, "invalid"])

            return data

        return _generate

    @pytest.mark.parametrize(
        "n_records,validation_level", [(1000, "standard"), (5000, "standard"), (1000, "strict"), (1000, "complete")]
    )
    def test_data_validation_speed(self, generate_validation_data, n_records, validation_level):
        """测试数据验证速度"""
        data = generate_validation_data(n_records, error_rate=0.05)

        # 根据验证级别创建验证器
        level_map = {
            "standard": ValidationLevel.STANDARD,
            "strict": ValidationLevel.STRICT,
            "complete": ValidationLevel.COMPLETE,
        }

        validator = AdvancedDataValidator(level_map[validation_level])

        # 测量性能
        result, execution_time, memory_used = measure_performance(validator.validate_dataset)(data)

        # 记录性能指标
        print(f"\n数据验证性能 (n={n_records}, level={validation_level}):")
        print(f"  执行时间: {execution_time:.3f}秒")
        print(f"  内存使用: {memory_used:.2f} MB")
        print(f"  验证结果: {'有效' if result.is_valid else '无效'}")
        print(f"  问题数量: {len(result.issues)}")

        # 性能要求
        throughput = n_records / execution_time
        print(f"  吞吐量: {throughput:.1f} 记录/秒")

        if n_records <= 5000:
            assert execution_time < 5.0, f"数据验证太慢: {execution_time:.3f}秒"
            assert throughput > 100, f"数据验证吞吐量太低: {throughput:.1f} 记录/秒"

    def test_validation_level_comparison(self, generate_validation_data):
        """测试不同验证级别的性能比较"""
        data = generate_validation_data(1000, error_rate=0.1)

        levels = [
            ("basic", ValidationLevel.BASIC),
            ("standard", ValidationLevel.STANDARD),
            ("strict", ValidationLevel.STRICT),
            ("complete", ValidationLevel.COMPLETE),
        ]

        results = {}

        for level_name, level in levels:
            validator = AdvancedDataValidator(level)

            start_time = time.time()
            result = validator.validate_dataset(data)
            end_time = time.time()

            execution_time = end_time - start_time
            results[level_name] = {"time": execution_time, "issues": len(result.issues), "is_valid": result.is_valid}

            print(f"  {level_name}: {execution_time:.3f}秒, {len(result.issues)}个问题")

        # 验证级别越高，时间应该越长（通常）
        assert results["complete"]["time"] >= results["basic"]["time"], "验证级别与时间不符"

        # 严格级别应该发现更多问题
        if results["standard"]["issues"] > 0:
            assert results["strict"]["issues"] >= results["standard"]["issues"], "严格级别应该发现更多问题"


class TestSystemResourceUsage:
    """系统资源使用测试"""

    def test_cpu_usage_during_processing(self, generate_training_data):
        """测试处理期间的CPU使用"""
        import threading
        import queue

        # 准备数据
        features = generate_training_data(200, 50)
        feature_cols = [col for col in features.columns if col not in ["period", "wan", "qian", "bai", "shi", "ge"]]

        cpu_readings = []

        def monitor_cpu(stop_event, readings_queue):
            """监控CPU使用率"""
            while not stop_event.is_set():
                cpu_percent = psutil.cpu_percent(interval=0.1)
                readings_queue.put(cpu_percent)
                time.sleep(0.1)

        # 启动监控线程
        stop_event = threading.Event()
        readings_queue = queue.Queue()
        monitor_thread = threading.Thread(target=monitor_cpu, args=(stop_event, readings_queue))
        monitor_thread.start()

        # 执行处理任务
        predictor = PL5Predictor()
        predictor.fit(features, feature_cols)

        # 停止监控
        stop_event.set()
        monitor_thread.join()

        # 收集CPU读数
        while not readings_queue.empty():
            cpu_readings.append(readings_queue.get())

        # 分析CPU使用
        if cpu_readings:
            avg_cpu = np.mean(cpu_readings)
            max_cpu = np.max(cpu_readings)

            print(f"\nCPU使用监控:")
            print(f"  平均CPU使用: {avg_cpu:.1f}%")
            print(f"  最大CPU使用: {max_cpu:.1f}%")
            print(f"  读数数量: {len(cpu_readings)}")

            # CPU使用应该合理
            assert avg_cpu < 90.0, f"平均CPU使用过高: {avg_cpu:.1f}%"
            assert max_cpu < 100.0, f"最大CPU使用过高: {max_cpu:.1f}%"

    def test_memory_usage_stability(self, generate_training_data):
        """测试内存使用稳定性"""
        # 准备数据
        features = generate_training_data(300, 80)
        feature_cols = [col for col in features.columns if col not in ["period", "wan", "qian", "bai", "shi", "ge"]]

        # 记录初始内存
        initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)  # MB

        # 执行多个处理任务
        memory_readings = [initial_memory]

        for i in range(3):
            predictor = PL5Predictor()
            predictor.fit(features, feature_cols)

            current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            memory_readings.append(current_memory)

            print(f"  迭代 {i+1}: 内存使用 {current_memory:.1f} MB")

        # 检查内存泄漏
        memory_diff = memory_readings[-1] - memory_readings[0]

        print(f"\n内存稳定性测试:")
        print(f"  初始内存: {memory_readings[0]:.1f} MB")
        print(f"  最终内存: {memory_readings[-1]:.1f} MB")
        print(f"  内存增长: {memory_diff:.1f} MB")

        # 内存增长应该有限
        assert memory_diff < 500.0, f"可能的内存泄漏: 增长 {memory_diff:.1f} MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
