"""
数据流集成测试
测试模块间的数据传递和协作
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch

# 导入被测模块
from src.core.data.collector import PL5DataCollectorV8
from src.core.features.engineer import FeatureEngineerV9
from src.core.models.predictor import PL5Predictor


class TestDataFlowIntegration:
    """测试数据流集成"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)
    
    @pytest.fixture
    def sample_raw_data(self):
        """创建样本原始数据"""
        lines = []
        for i in range(100):
            period = 2026001 + i
            date = f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
            nums = [np.random.randint(0, 10) for _ in range(5)]
            lines.append(f"{period} {date} {' '.join(map(str, nums))} {''.join(map(str, nums))}")
        return '\n'.join(lines)
    
    @pytest.mark.integration
    @pytest.mark.data
    def test_collector_to_features_flow(self, temp_dir, sample_raw_data, monkeypatch):
        """测试数据采集到特征工程的完整流程"""
        # 配置临时目录
        import src.core.data.collector as collector_module
        import src.core.features.engineer as engineer_module
        
        monkeypatch.setattr(collector_module, 'RAW_DATA_DIR', temp_dir / 'raw')
        monkeypatch.setattr(collector_module, 'PROCESSED_DATA_DIR', temp_dir / 'processed')
        monkeypatch.setattr(collector_module, 'MODELS_DIR', temp_dir / 'models')
        monkeypatch.setattr(engineer_module, 'MODELS_DIR', temp_dir / 'models')
        monkeypatch.setattr(engineer_module, 'PROCESSED_DATA_DIR', temp_dir / 'processed')
        
        (temp_dir / 'raw').mkdir(exist_ok=True)
        (temp_dir / 'processed').mkdir(exist_ok=True)
        (temp_dir / 'models').mkdir(exist_ok=True)
        
        # 1. 数据采集
        collector = PL5DataCollectorV8()
        collector.raw_data_path.write_text(sample_raw_data, encoding='utf-8')
        
        raw_df = collector.load_local_data()
        assert raw_df is not None
        assert len(raw_df) == 100
        assert all(col in raw_df.columns for col in ['period', 'wan', 'qian', 'bai', 'shi', 'ge'])
        
        # 2. 特征工程
        engineer = FeatureEngineerV9(
            use_config=False,
            enable_parallel=False,
            cache_max_size=5
        )
        
        features_df = engineer.extract_all_features(
            raw_df,
            select_top=None,
            enable_scaler=False
        )
        
        assert features_df is not None
        assert len(features_df) == len(raw_df)
        # 应该生成更多特征列
        assert len(features_df.columns) > len(raw_df.columns)
        
        # 3. 验证数据完整性
        assert 'period' in features_df.columns
        assert all(pos in features_df.columns for pos in ['wan', 'qian', 'bai', 'shi', 'ge'])
    
    @pytest.mark.integration
    @pytest.mark.data
    def test_features_to_prediction_flow(self, temp_dir, monkeypatch):
        """测试特征工程到预测的完整流程"""
        # 配置临时目录
        import src.core.features.engineer as engineer_module
        import src.core.models.predictor as predictor_module
        
        monkeypatch.setattr(engineer_module, 'MODELS_DIR', temp_dir / 'models')
        monkeypatch.setattr(engineer_module, 'PROCESSED_DATA_DIR', temp_dir / 'processed')
        
        (temp_dir / 'models').mkdir(exist_ok=True)
        (temp_dir / 'processed').mkdir(exist_ok=True)
        
        # 1. 创建样本数据
        np.random.seed(42)
        n = 100
        raw_df = pd.DataFrame({
            'period': [f'2026{i:04d}' for i in range(n)],
            'wan': np.random.randint(0, 10, n),
            'qian': np.random.randint(0, 10, n),
            'bai': np.random.randint(0, 10, n),
            'shi': np.random.randint(0, 10, n),
            'ge': np.random.randint(0, 10, n)
        })
        
        # 2. 特征工程
        engineer = FeatureEngineerV9(
            use_config=False,
            enable_parallel=False,
            cache_max_size=5
        )
        
        features_df = engineer.extract_all_features(
            raw_df,
            select_top=50,  # 选择Top 50特征
            enable_scaler=True
        )
        
        # 3. 模型训练
        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir / 'models'
        
        feature_cols = [col for col in features_df.columns 
                       if col not in ['period', 'wan', 'qian', 'bai', 'shi', 'ge', 'full_number']]
        
        predictor.fit(features_df, feature_cols)
        
        assert predictor.is_trained is True
        assert len(predictor.feature_cols) > 0
        
        # 4. 预测
        test_features = features_df[feature_cols].iloc[-1].values
        recent_data = {
            'wan': raw_df['wan'].values[-10:],
            'qian': raw_df['qian'].values[-10:],
            'bai': raw_df['bai'].values[-10:],
            'shi': raw_df['shi'].values[-10:],
            'ge': raw_df['ge'].values[-10:]
        }
        
        prediction = predictor.predict(test_features, recent_data, top_k=5)
        
        assert prediction is not None
        assert len(prediction) == 5  # 5个位置
        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            assert pos in prediction
            assert 'top_k' in prediction[pos]
            assert 'probabilities' in prediction[pos]
    
    @pytest.mark.integration
    @pytest.mark.data
    def test_end_to_end_data_pipeline(self, temp_dir, sample_raw_data, monkeypatch):
        """测试端到端数据管道"""
        # 配置临时目录
        import src.core.data.collector as collector_module
        import src.core.features.engineer as engineer_module
        import src.core.models.predictor as predictor_module
        
        monkeypatch.setattr(collector_module, 'RAW_DATA_DIR', temp_dir / 'raw')
        monkeypatch.setattr(collector_module, 'PROCESSED_DATA_DIR', temp_dir / 'processed')
        monkeypatch.setattr(collector_module, 'MODELS_DIR', temp_dir / 'models')
        monkeypatch.setattr(engineer_module, 'MODELS_DIR', temp_dir / 'models')
        monkeypatch.setattr(engineer_module, 'PROCESSED_DATA_DIR', temp_dir / 'processed')
        
        (temp_dir / 'raw').mkdir(exist_ok=True)
        (temp_dir / 'processed').mkdir(exist_ok=True)
        (temp_dir / 'models').mkdir(exist_ok=True)
        
        # 完整流程：采集 -> 特征 -> 训练 -> 预测
        
        # 1. 数据采集
        collector = PL5DataCollectorV8()
        collector.raw_data_path.write_text(sample_raw_data, encoding='utf-8')
        raw_df = collector.load_local_data()
        
        # 2. 特征工程
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        features_df = engineer.extract_all_features(raw_df, select_top=30, enable_scaler=True)
        
        # 3. 模型训练
        predictor = PL5Predictor()
        predictor.MODELS_DIR = temp_dir / 'models'
        feature_cols = [col for col in features_df.columns 
                       if col not in ['period', 'wan', 'qian', 'bai', 'shi', 'ge', 'full_number']]
        predictor.fit(features_df, feature_cols)
        
        # 4. 预测
        test_features = features_df[feature_cols].iloc[-1].values
        recent_data = {pos: raw_df[pos].values[-10:] for pos in ['wan', 'qian', 'bai', 'shi', 'ge']}
        prediction = predictor.predict(test_features, recent_data, top_k=8)
        
        # 验证结果
        assert prediction is not None
        assert all(pos in prediction for pos in ['wan', 'qian', 'bai', 'shi', 'ge'])
        
        # 验证预测格式
        for pos, pred in prediction.items():
            assert len(pred['top_k']) == 8
            assert len(pred['probabilities']) == 8
            assert all(isinstance(x, int) for x in pred['top_k'])
            assert all(0 <= x <= 9 for x in pred['top_k'])
            assert all(isinstance(p, float) for p in pred['probabilities'])
            assert abs(sum(pred['probabilities']) - 1.0) < 0.01  # 概率和接近1
    
    @pytest.mark.integration
    @pytest.mark.data
    def test_data_version_consistency(self, temp_dir, sample_raw_data, monkeypatch):
        """测试数据版本一致性"""
        import src.core.data.collector as collector_module
        
        monkeypatch.setattr(collector_module, 'RAW_DATA_DIR', temp_dir / 'raw')
        monkeypatch.setattr(collector_module, 'MODELS_DIR', temp_dir / 'models')
        
        (temp_dir / 'raw').mkdir(exist_ok=True)
        (temp_dir / 'models').mkdir(exist_ok=True)
        
        collector = PL5DataCollectorV8()
        collector.raw_data_path.write_text(sample_raw_data, encoding='utf-8')
        
        # 加载数据并保存版本
        df1 = collector.load_local_data()
        collector.version_manager.save_version(df1, source='test')
        
        # 再次加载相同数据
        df2 = collector.load_local_data()
        
        # 验证数据一致性
        pd.testing.assert_frame_equal(df1, df2)
        
        # 验证版本信息
        version = collector.version_manager.get_current_version()
        assert version['record_count'] == len(df1)
        assert version['source'] == 'test'


class TestModuleCommunication:
    """测试模块间通信"""
    
    @pytest.mark.integration
    def test_error_propagation(self):
        """测试错误传播"""
        from src.core.utils.errors import DataError, FeatureError
        
        # 模拟数据错误
        with pytest.raises(DataError):
            collector = PL5DataCollectorV8()
            # 尝试加载不存在的数据源
            collector.fetch_from_network('nonexistent_source')
    
    @pytest.mark.integration
    def test_data_format_compatibility(self):
        """测试数据格式兼容性"""
        # 创建不同格式的数据
        np.random.seed(42)
        
        # DataFrame格式
        df_format = pd.DataFrame({
            'period': ['2026001', '2026002'],
            'wan': [1, 2],
            'qian': [3, 4],
            'bai': [5, 6],
            'shi': [7, 8],
            'ge': [9, 0]
        })
        
        # 验证所有模块都能处理
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        result = engineer._add_golden_ratio_volatility_features(df_format)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(df_format)


class TestCachingIntegration:
    """测试缓存集成"""
    
    @pytest.mark.integration
    def test_feature_cache_integration(self):
        """测试特征缓存集成"""
        np.random.seed(42)
        n = 50
        df = pd.DataFrame({
            'period': [f'2026{i:04d}' for i in range(n)],
            'wan': np.random.randint(0, 10, n),
            'qian': np.random.randint(0, 10, n),
            'bai': np.random.randint(0, 10, n),
            'shi': np.random.randint(0, 10, n),
            'ge': np.random.randint(0, 10, n)
        })
        
        engineer = FeatureEngineerV9(
            use_config=False,
            enable_parallel=False,
            cache_max_size=10
        )
        
        # 第一次提取（缓存未命中）
        result1 = engineer.extract_all_features(df, select_top=None, enable_scaler=False)
        initial_hits = engineer.cache.stats['hits']
        
        # 第二次提取（应该命中缓存）
        result2 = engineer.extract_all_features(df, select_top=None, enable_scaler=False)
        
        # 验证缓存命中
        assert engineer.cache.stats['hits'] > initial_hits
        
        # 验证结果一致
        pd.testing.assert_frame_equal(result1, result2)
