"""
端到端测试 - 完整业务流程
测试从数据采集到预测输出的完整流程
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil
import json
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# 导入被测模块
from src.core.data.collector import PL5DataCollectorV8
from src.core.features.engineer import FeatureEngineerV9
from src.core.models.predictor import PL5Predictor


class TestFullPipeline:
    """测试完整业务流程"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def sample_historical_data(self):
        """创建样本历史数据"""
        np.random.seed(42)
        lines = []
        for i in range(300):
            period = 2026001 + i
            date = f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
            nums = [np.random.randint(0, 10) for _ in range(5)]
            lines.append(f"{period} {date} {' '.join(map(str, nums))} {''.join(map(str, nums))}")
        return "\n".join(lines)

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_complete_prediction_pipeline(self, temp_dir, sample_historical_data, monkeypatch):
        """测试完整预测流程"""
        # 配置临时目录
        import src.core.data.collector as collector_module
        import src.core.features.engineer as engineer_module
        import src.core.models.predictor as predictor_module

        monkeypatch.setattr(collector_module, "RAW_DATA_DIR", temp_dir / "raw")
        monkeypatch.setattr(collector_module, "PROCESSED_DATA_DIR", temp_dir / "processed")
        monkeypatch.setattr(collector_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "PROCESSED_DATA_DIR", temp_dir / "processed")

        (temp_dir / "raw").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)
        (temp_dir / "models").mkdir(exist_ok=True)

        pipeline_start = time.time()

        # Step 1: 数据采集
        print("Step 1: 数据采集...")
        collector = PL5DataCollectorV8()
        collector.raw_data_path.write_text(sample_historical_data, encoding="utf-8")

        raw_df = collector.load_local_data()
        assert raw_df is not None
        assert len(raw_df) == 300
        print(f"  ✓ 加载了 {len(raw_df)} 条历史数据")

        # Step 2: 数据版本管理
        print("Step 2: 数据版本管理...")
        collector.version_manager.save_version(raw_df, source="e2e_test")
        version = collector.version_manager.get_current_version()
        assert version["record_count"] == 300
        print(f"  ✓ 数据版本已保存: {version['version']}")

        # Step 3: 特征工程
        print("Step 3: 特征工程...")
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False, cache_max_size=10)

        features_df = engineer.extract_all_features(
            raw_df, select_top=80, feature_selection_method="rfe", enable_scaler=True
        )

        assert features_df is not None
        assert len(features_df) == len(raw_df)
        original_cols = len(raw_df.columns)
        feature_cols = len(features_df.columns)
        print(f"  ✓ 特征提取完成: {original_cols} -> {feature_cols} 列")

        # Step 4: 模型训练
        print("Step 4: 模型训练...")
        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir / "models"

        feature_columns = [
            col
            for col in features_df.columns
            if col not in ["period", "wan", "qian", "bai", "shi", "ge", "full_number"]
        ]

        predictor.fit(features_df, feature_columns)

        assert predictor.is_trained is True
        assert len(predictor.stacking) == 5
        print(f"  ✓ 模型训练完成")

        # Step 5: 保存模型
        print("Step 5: 保存模型...")
        predictor.save_models()

        model_files = list((temp_dir / "models").glob("*.joblib")) + list((temp_dir / "models").glob("*.pkl"))
        assert len(model_files) > 0
        print(f"  ✓ 模型已保存: {len(model_files)} 个文件")

        # Step 6: 加载模型
        print("Step 6: 加载模型...")
        new_predictor = PL5Predictor()
        new_predictor.MODELS_DIR = temp_dir / "models"
        success = new_predictor.load_models()

        assert success is True
        assert new_predictor.is_trained is True
        print(f"  ✓ 模型加载成功")

        # Step 7: 执行预测
        print("Step 7: 执行预测...")
        test_features = features_df[feature_columns].iloc[-1].values
        recent_data = {pos: raw_df[pos].values[-30:] for pos in ["wan", "qian", "bai", "shi", "ge"]}

        prediction = new_predictor.predict(test_features, recent_data, top_k=8)

        assert prediction is not None
        assert len(prediction) == 5
        print(f"  ✓ 预测完成")

        # Step 8: 验证预测结果
        print("Step 8: 验证预测结果...")
        for pos, pred in prediction.items():
            assert "top_k" in pred
            assert "probabilities" in pred
            assert len(pred["top_k"]) == 8
            assert len(pred["probabilities"]) == 8

            # 验证号码范围
            for num in pred["top_k"]:
                assert 0 <= num <= 9

            # 验证概率和
            prob_sum = sum(pred["probabilities"])
            assert abs(prob_sum - 1.0) < 0.01

        print(f"  ✓ 预测结果验证通过")

        pipeline_end = time.time()
        print(f"\n完整流程耗时: {pipeline_end - pipeline_start:.2f} 秒")

        # 输出预测结果
        print("\n预测结果:")
        for pos in ["wan", "qian", "bai", "shi", "ge"]:
            pred = prediction[pos]
            numbers = "-".join(map(str, pred["top_k"][:5]))
            print(f"  {pos}: {numbers}")

    @pytest.mark.e2e
    def test_model_persistence_workflow(self, temp_dir, monkeypatch):
        """测试模型持久化工作流"""
        import src.core.features.engineer as engineer_module
        import src.core.models.predictor as predictor_module

        monkeypatch.setattr(engineer_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "PROCESSED_DATA_DIR", temp_dir / "processed")

        (temp_dir / "models").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)

        # 创建训练数据
        np.random.seed(42)
        n = 100
        df = pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(n)],
                "feature_1": np.random.randn(n),
                "feature_2": np.random.randn(n),
                "wan": np.random.randint(0, 10, n),
                "qian": np.random.randint(0, 10, n),
                "bai": np.random.randint(0, 10, n),
                "shi": np.random.randint(0, 10, n),
                "ge": np.random.randint(0, 10, n),
            }
        )

        # 训练并保存
        predictor1 = PL5Predictor()
        predictor1.MODELS_DIR = temp_dir / "models"
        predictor1.fit(df, ["feature_1", "feature_2"])
        predictor1.save_models()

        # 创建新实例并加载
        predictor2 = PL5Predictor()
        predictor2.MODELS_DIR = temp_dir / "models"
        success = predictor2.load_models()

        assert success is True

        # 验证两个预测器输出一致
        features = np.array([0.5, -0.5])
        pred1 = predictor1.predict(features, top_k=5)
        pred2 = predictor2.predict(features, top_k=5)

        for pos in ["wan", "qian", "bai", "shi", "ge"]:
            assert pred1[pos]["top_k"] == pred2[pos]["top_k"]

    @pytest.mark.e2e
    def test_error_handling_pipeline(self, temp_dir, monkeypatch):
        """测试错误处理流程"""
        import src.core.data.collector as collector_module

        monkeypatch.setattr(collector_module, "RAW_DATA_DIR", temp_dir / "raw")
        monkeypatch.setattr(collector_module, "MODELS_DIR", temp_dir / "models")

        (temp_dir / "raw").mkdir(exist_ok=True)
        (temp_dir / "models").mkdir(exist_ok=True)

        collector = PL5DataCollectorV8()

        # 测试无效数据
        invalid_data = "invalid line\nanother invalid"
        collector.raw_data_path.write_text(invalid_data, encoding="utf-8")

        # 应该返回空DataFrame而不是崩溃
        result = collector.parse_raw_data(invalid_data)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

        # 测试空数据
        empty_result = collector.parse_raw_data("")
        assert isinstance(empty_result, pd.DataFrame)
        assert len(empty_result) == 0

    @pytest.mark.e2e
    def test_data_drift_detection_pipeline(self, temp_dir, monkeypatch):
        """测试数据漂移检测流程"""
        import src.core.features.engineer as engineer_module

        monkeypatch.setattr(engineer_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "PROCESSED_DATA_DIR", temp_dir / "processed")

        (temp_dir / "models").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)

        # 创建训练数据
        np.random.seed(42)
        n = 100
        train_df = pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(n)],
                "wan": np.random.randint(0, 10, n),
                "qian": np.random.randint(0, 10, n),
                "bai": np.random.randint(0, 10, n),
                "shi": np.random.randint(0, 10, n),
                "ge": np.random.randint(0, 10, n),
            }
        )

        # 特征工程并启用漂移检测
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)

        # 第一次提取（建立基线）
        features_train = engineer.extract_all_features(train_df, select_top=30, detect_drift=True)

        # 创建漂移数据
        drift_df = train_df.copy()
        drift_df["wan"] = drift_df["wan"] + 5  # 人为制造漂移

        # 第二次提取（检测漂移）
        features_drift = engineer.extract_all_features(drift_df, select_top=30, detect_drift=True)

        # 验证漂移检测器状态
        assert len(engineer.drift_detector.training_stats) > 0

    @pytest.mark.e2e
    @pytest.mark.performance
    def test_system_performance_requirements(self, temp_dir, monkeypatch):
        """测试系统性能要求"""
        import src.core.features.engineer as engineer_module
        import src.core.models.predictor as predictor_module

        monkeypatch.setattr(engineer_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "PROCESSED_DATA_DIR", temp_dir / "processed")

        (temp_dir / "models").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)

        # 创建中等规模数据
        np.random.seed(42)
        n = 200
        df = pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(n)],
                "wan": np.random.randint(0, 10, n),
                "qian": np.random.randint(0, 10, n),
                "bai": np.random.randint(0, 10, n),
                "shi": np.random.randint(0, 10, n),
                "ge": np.random.randint(0, 10, n),
            }
        )

        # 性能测试：特征提取
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)

        start = time.time()
        features_df = engineer.extract_all_features(df, select_top=50, enable_scaler=True)
        feature_time = time.time() - start

        assert feature_time < 30, f"特征提取耗时过长: {feature_time:.2f}s"

        # 性能测试：模型训练
        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir / "models"
        feature_cols = [
            col
            for col in features_df.columns
            if col not in ["period", "wan", "qian", "bai", "shi", "ge", "full_number"]
        ]

        start = time.time()
        predictor.fit(features_df, feature_cols)
        train_time = time.time() - start

        assert train_time < 60, f"模型训练耗时过长: {train_time:.2f}s"

        # 性能测试：预测
        test_features = features_df[feature_cols].iloc[-1].values

        start = time.time()
        for _ in range(10):
            predictor.predict(test_features, top_k=5)
        predict_time = time.time() - start

        assert predict_time < 5, f"预测耗时过长: {predict_time:.2f}s"

        print(f"\n性能测试结果:")
        print(f"  特征提取: {feature_time:.2f}s")
        print(f"  模型训练: {train_time:.2f}s")
        print(f"  10次预测: {predict_time:.2f}s")


class TestBusinessScenarios:
    """测试业务场景"""

    @pytest.mark.e2e
    def test_daily_operation_scenario(self, temp_dir, monkeypatch):
        """测试日常运营场景"""
        import src.core.data.collector as collector_module
        import src.core.features.engineer as engineer_module
        import src.core.models.predictor as predictor_module

        monkeypatch.setattr(collector_module, "RAW_DATA_DIR", temp_dir / "raw")
        monkeypatch.setattr(collector_module, "PROCESSED_DATA_DIR", temp_dir / "processed")
        monkeypatch.setattr(collector_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "PROCESSED_DATA_DIR", temp_dir / "processed")

        (temp_dir / "raw").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)
        (temp_dir / "models").mkdir(exist_ok=True)

        # 模拟日常运营：检查数据 -> 更新模型 -> 生成预测

        # 1. 检查最新数据
        collector = PL5DataCollectorV8()

        # 模拟历史数据
        historical_data = """2026300 2026-10-27 1 2 3 4 5 12345
2026301 2026-10-28 2 3 4 5 6 23456
2026302 2026-10-29 3 4 5 6 7 34567"""
        collector.raw_data_path.write_text(historical_data, encoding="utf-8")

        latest_period = collector.get_latest_period()
        assert latest_period == "2026302"

        # 2. 加载数据
        df = collector.load_local_data()

        # 3. 特征工程
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        features_df = engineer.extract_all_features(df, select_top=20, enable_scaler=False)

        # 4. 快速训练（使用少量数据）
        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir / "models"
        feature_cols = [
            col
            for col in features_df.columns
            if col not in ["period", "wan", "qian", "bai", "shi", "ge", "full_number"]
        ]
        predictor.fit(features_df, feature_cols)

        # 5. 生成预测
        test_features = features_df[feature_cols].iloc[-1].values
        recent_data = {pos: df[pos].values for pos in ["wan", "qian", "bai", "shi", "ge"]}

        prediction = predictor.predict(test_features, recent_data, top_k=5)

        # 验证预测结果格式
        assert prediction is not None
        for pos in ["wan", "qian", "bai", "shi", "ge"]:
            assert len(prediction[pos]["top_k"]) == 5

    @pytest.mark.e2e
    def test_model_deployment_scenario(self, temp_dir, monkeypatch):
        """测试模型部署场景"""
        import src.core.features.engineer as engineer_module
        import src.core.models.predictor as predictor_module

        monkeypatch.setattr(engineer_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "PROCESSED_DATA_DIR", temp_dir / "processed")

        (temp_dir / "models").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)

        # 模拟模型部署流程

        # 1. 训练新模型
        np.random.seed(42)
        n = 150
        df = pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(n)],
                "feature_1": np.random.randn(n),
                "wan": np.random.randint(0, 10, n),
                "qian": np.random.randint(0, 10, n),
                "bai": np.random.randint(0, 10, n),
                "shi": np.random.randint(0, 10, n),
                "ge": np.random.randint(0, 10, n),
            }
        )

        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        features_df = engineer.extract_all_features(df, select_top=30, enable_scaler=True)

        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir / "models"
        feature_cols = [
            col
            for col in features_df.columns
            if col not in ["period", "wan", "qian", "bai", "shi", "ge", "full_number"]
        ]
        predictor.fit(features_df, feature_cols)

        # 2. 保存模型
        predictor.save_models()

        # 3. 验证模型文件
        model_files = list((temp_dir / "models").glob("*"))
        assert len(model_files) > 0

        # 4. 加载验证
        new_predictor = PL5Predictor()
        new_predictor.MODELS_DIR = temp_dir / "models"
        assert new_predictor.load_models() is True

        # 5. 测试预测
        test_features = features_df[feature_cols].iloc[-1].values
        prediction = new_predictor.predict(test_features, top_k=5)

        assert prediction is not None
        print(f"\n部署验证成功，模型可以正常预测")
