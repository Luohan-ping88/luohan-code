"""
工作流集成测试
测试完整业务流程和工作流
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# 导入被测模块
from src.core.data.collector import PL5DataCollectorV8
from src.core.features.engineer import FeatureEngineerV9
from src.core.models.predictor import PL5Predictor


class TestTrainingWorkflow:
    """测试训练工作流"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def sample_training_data(self):
        """创建样本训练数据"""
        np.random.seed(42)
        n = 200
        return pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(n)],
                "wan": np.random.randint(0, 10, n),
                "qian": np.random.randint(0, 10, n),
                "bai": np.random.randint(0, 10, n),
                "shi": np.random.randint(0, 10, n),
                "ge": np.random.randint(0, 10, n),
            }
        )

    @pytest.mark.integration
    @pytest.mark.slow
    def test_full_training_workflow(self, temp_dir, sample_training_data, monkeypatch):
        """测试完整训练工作流"""
        # 配置临时目录
        import src.core.features.engineer as engineer_module
        import src.core.models.predictor as predictor_module

        monkeypatch.setattr(engineer_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "PROCESSED_DATA_DIR", temp_dir / "processed")

        (temp_dir / "models").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)

        # 1. 数据准备
        raw_df = sample_training_data

        # 2. 特征工程
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False, cache_max_size=10)

        features_df = engineer.extract_all_features(
            raw_df, select_top=50, feature_selection_method="rfe", enable_scaler=True
        )

        # 3. 模型训练
        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir / "models"

        feature_cols = [
            col
            for col in features_df.columns
            if col not in ["period", "wan", "qian", "bai", "shi", "ge", "full_number"]
        ]

        predictor.fit(features_df, feature_cols)

        # 4. 验证训练结果
        assert predictor.is_trained is True
        assert len(predictor.stacking) == 5
        assert len(predictor.hmm_models) == 5
        assert len(predictor.bsts_models) == 5
        assert len(predictor.evm_models) == 5

        # 5. 保存模型
        predictor.save_models()

        # 验证模型文件存在
        model_files = list((temp_dir / "models").glob("*.joblib")) + list((temp_dir / "models").glob("*.pkl"))
        assert len(model_files) > 0

    @pytest.mark.integration
    def test_incremental_training_workflow(self, temp_dir, monkeypatch):
        """测试增量训练工作流"""
        import src.core.features.engineer as engineer_module
        import src.core.models.predictor as predictor_module

        monkeypatch.setattr(engineer_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "PROCESSED_DATA_DIR", temp_dir / "processed")

        (temp_dir / "models").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)

        # 第一批数据
        np.random.seed(42)
        df1 = pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(50)],
                "wan": np.random.randint(0, 10, 50),
                "qian": np.random.randint(0, 10, 50),
                "bai": np.random.randint(0, 10, 50),
                "shi": np.random.randint(0, 10, 50),
                "ge": np.random.randint(0, 10, 50),
            }
        )

        # 训练第一批
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        features_df1 = engineer.extract_all_features(df1, select_top=30, enable_scaler=True)

        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir / "models"
        feature_cols = [
            col
            for col in features_df1.columns
            if col not in ["period", "wan", "qian", "bai", "shi", "ge", "full_number"]
        ]
        predictor.fit(features_df1, feature_cols)
        predictor.save_models()

        # 第二批数据
        df2 = pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(50, 100)],
                "wan": np.random.randint(0, 10, 50),
                "qian": np.random.randint(0, 10, 50),
                "bai": np.random.randint(0, 10, 50),
                "shi": np.random.randint(0, 10, 50),
                "ge": np.random.randint(0, 10, 50),
            }
        )

        # 合并数据重新训练
        combined_df = pd.concat([df1, df2], ignore_index=True)
        features_combined = engineer.extract_all_features(combined_df, select_top=30, enable_scaler=True)

        # 使用相同的特征列
        predictor2 = PL5Predictor()
        predictor2.MODELS_DIR = temp_dir / "models"
        predictor2.fit(features_combined, feature_cols)

        assert predictor2.is_trained is True
        assert len(predictor2.feature_cols) == len(feature_cols)


class TestPredictionWorkflow:
    """测试预测工作流"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def trained_predictor(self, temp_dir, monkeypatch):
        """创建已训练的预测器"""
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
                "wan": np.random.randint(0, 10, n),
                "qian": np.random.randint(0, 10, n),
                "bai": np.random.randint(0, 10, n),
                "shi": np.random.randint(0, 10, n),
                "ge": np.random.randint(0, 10, n),
            }
        )

        # 特征工程
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        features_df = engineer.extract_all_features(df, select_top=30, enable_scaler=True)

        # 训练模型
        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir / "models"
        feature_cols = [
            col
            for col in features_df.columns
            if col not in ["period", "wan", "qian", "bai", "shi", "ge", "full_number"]
        ]
        predictor.fit(features_df, feature_cols)
        predictor.save_models()

        return predictor, df, feature_cols

    @pytest.mark.integration
    def test_daily_prediction_workflow(self, trained_predictor):
        """测试日常预测工作流"""
        predictor, training_df, feature_cols = trained_predictor

        # 获取最新特征
        latest_features = training_df[["wan", "qian", "bai", "shi", "ge"]].iloc[-1].values

        # 获取最近历史数据
        recent_data = {pos: training_df[pos].values[-20:] for pos in ["wan", "qian", "bai", "shi", "ge"]}

        # 执行预测
        prediction = predictor.predict(latest_features, recent_data, top_k=8)

        # 验证预测结果
        assert prediction is not None
        assert len(prediction) == 5

        for pos in ["wan", "qian", "bai", "shi", "ge"]:
            assert pos in prediction
            assert "top_k" in prediction[pos]
            assert "probabilities" in prediction[pos]
            assert len(prediction[pos]["top_k"]) == 8
            assert len(prediction[pos]["probabilities"]) == 8

            # 验证推荐号码在有效范围内
            for num in prediction[pos]["top_k"]:
                assert 0 <= num <= 9

            # 验证概率和接近1
            assert abs(sum(prediction[pos]["probabilities"]) - 1.0) < 0.01

    @pytest.mark.integration
    def test_batch_prediction_workflow(self, trained_predictor):
        """测试批量预测工作流"""
        predictor, training_df, feature_cols = trained_predictor

        # 对最后10期进行批量预测
        predictions = []
        for i in range(10):
            idx = -(i + 1)
            features = training_df[["wan", "qian", "bai", "shi", "ge"]].iloc[idx].values

            recent_data = {pos: training_df[pos].values[idx - 20 : idx] for pos in ["wan", "qian", "bai", "shi", "ge"]}

            pred = predictor.predict(features, recent_data, top_k=5)
            predictions.append(pred)

        # 验证所有预测
        assert len(predictions) == 10
        for pred in predictions:
            assert len(pred) == 5
            for pos in pred.values():
                assert len(pos["top_k"]) == 5


class TestDataUpdateWorkflow:
    """测试数据更新工作流"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.mark.integration
    def test_data_update_and_retrain_workflow(self, temp_dir, monkeypatch):
        """测试数据更新和重新训练工作流"""
        import src.core.data.collector as collector_module
        import src.core.features.engineer as engineer_module

        monkeypatch.setattr(collector_module, "RAW_DATA_DIR", temp_dir / "raw")
        monkeypatch.setattr(collector_module, "PROCESSED_DATA_DIR", temp_dir / "processed")
        monkeypatch.setattr(collector_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "MODELS_DIR", temp_dir / "models")
        monkeypatch.setattr(engineer_module, "PROCESSED_DATA_DIR", temp_dir / "processed")

        (temp_dir / "raw").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)
        (temp_dir / "models").mkdir(exist_ok=True)

        # 1. 初始数据
        initial_data = """2026001 2026-01-01 1 2 3 4 5 12345
2026002 2026-01-02 2 3 4 5 6 23456
2026003 2026-01-03 3 4 5 6 7 34567"""

        collector = PL5DataCollectorV8()
        collector.raw_data_path.write_text(initial_data, encoding="utf-8")

        df1 = collector.load_local_data()
        assert len(df1) == 3

        # 2. 更新数据
        updated_data = initial_data + "\n2026004 2026-01-04 4 5 6 7 8 45678"
        collector.raw_data_path.write_text(updated_data, encoding="utf-8")

        df2 = collector.load_local_data()
        assert len(df2) == 4

        # 3. 保存版本
        collector.version_manager.save_version(df2, source="update")

        version = collector.version_manager.get_current_version()
        assert version["record_count"] == 4
        assert version["latest_period"] == "2026004"


class TestErrorRecoveryWorkflow:
    """测试错误恢复工作流"""

    @pytest.mark.integration
    def test_model_fallback_workflow(self, temp_dir, monkeypatch):
        """测试模型回退工作流"""
        import src.core.models.predictor as predictor_module

        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir

        # 尝试加载不存在的模型
        success = predictor.load_models()
        assert success is False

        # 未训练时预测应返回均匀分布
        result = predictor.predict(np.array([1, 2, 3, 4, 5]), top_k=5)

        for pos in result.values():
            assert len(pos["top_k"]) == 5
            # 均匀分布概率
            assert np.allclose(pos["probabilities"], [0.2] * 5)

    @pytest.mark.integration
    def test_data_corruption_recovery(self, temp_dir, monkeypatch):
        """测试数据损坏恢复"""
        import src.core.data.collector as collector_module

        monkeypatch.setattr(collector_module, "RAW_DATA_DIR", temp_dir / "raw")
        monkeypatch.setattr(collector_module, "MODELS_DIR", temp_dir / "models")

        (temp_dir / "raw").mkdir(exist_ok=True)
        (temp_dir / "models").mkdir(exist_ok=True)
        (temp_dir / "raw" / "backups").mkdir(exist_ok=True)

        collector = PL5DataCollectorV8()

        # 创建有效数据并备份
        valid_data = """2026001 2026-01-01 1 2 3 4 5 12345
2026002 2026-01-02 2 3 4 5 6 23456"""
        collector.raw_data_path.write_text(valid_data, encoding="utf-8")

        df = collector.load_local_data()
        collector.version_manager.create_backup(df)

        # 模拟数据损坏
        collector.raw_data_path.write_text("corrupted data", encoding="utf-8")

        # 尝试从备份恢复
        backups = collector.version_manager.list_backups()
        if backups:
            restored_df = collector.version_manager.restore_backup(backups[0])
            assert restored_df is not None
            assert len(restored_df) == 2


class TestPerformanceWorkflow:
    """测试性能工作流"""

    @pytest.mark.integration
    @pytest.mark.performance
    def test_feature_extraction_performance(self):
        """测试特征提取性能"""
        import time

        # 创建大数据集
        np.random.seed(42)
        n = 500
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

        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)

        start_time = time.time()
        result = engineer.extract_all_features(df, select_top=50, enable_scaler=False)
        elapsed = time.time() - start_time

        # 验证性能（应该在合理时间内完成）
        assert elapsed < 60  # 60秒内完成
        assert len(result) == len(df)

    @pytest.mark.integration
    @pytest.mark.performance
    def test_prediction_performance(self):
        """测试预测性能"""
        import time

        # 创建小模型
        np.random.seed(42)
        n = 50
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

        predictor = PL5Predictor()
        predictor.fit(df, ["feature_1"])

        # 批量预测性能测试
        start_time = time.time()
        for _ in range(10):
            predictor.predict(np.array([0.5]), top_k=5)
        elapsed = time.time() - start_time

        # 验证性能
        assert elapsed < 10  # 10次预测应在10秒内完成
