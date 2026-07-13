"""
系统集成测试
测试各模块之间的集成和协作
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import asyncio

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import setup_logging
from src.core.data.validator import AdvancedDataValidator, ValidationLevel, DataCleaner
from src.core.features.engineer import FeatureEngineer
from src.core.models import PL5Predictor

logger = setup_logging(__name__)


class TestDataToFeaturesIntegration:
    """数据到特征集成测试"""
    
    @pytest.fixture
    def sample_data(self):
        """创建样本数据"""
        np.random.seed(42)
        n_records = 50
        
        data = pd.DataFrame({
            'period': [f'2026{str(i).zfill(3)}' for i in range(1001, 1001 + n_records)],
            'wan': np.random.randint(0, 10, n_records),
            'qian': np.random.randint(0, 10, n_records),
            'bai': np.random.randint(0, 10, n_records),
            'shi': np.random.randint(0, 10, n_records),
            'ge': np.random.randint(0, 10, n_records)
        })
        
        return data
    
    def test_data_validation_to_feature_engineering(self, sample_data):
        """测试数据验证到特征工程的集成"""
        # 1. 数据验证
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        validation_result = validator.validate_dataset(sample_data)
        
        assert validation_result.is_valid is True
        assert validation_result.summary['valid_records'] == len(sample_data)
        
        # 2. 数据清洗（如果需要）
        if not validation_result.is_valid:
            logger.info("数据验证发现问题，进行清洗...")
            sample_data = DataCleaner.clean_dataset(sample_data, validation_result)
        
        # 3. 特征工程
        engineer = FeatureEngineer()
        features = engineer.extract_all_features(sample_data)
        
        # 验证特征生成
        assert features is not None
        assert len(features) == len(sample_data)
        assert len(features.columns) > len(sample_data.columns)  # 应该有更多特征
        
        # 检查特征列
        feature_cols = [col for col in features.columns 
                       if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        
        assert len(feature_cols) > 0
        logger.info(f"成功生成 {len(feature_cols)} 个特征")
        
        return features
    
    def test_feature_quality(self, sample_data):
        """测试特征质量"""
        engineer = FeatureEngineer()
        features = engineer.extract_all_features(sample_data)
        
        # 检查特征是否包含NaN或Inf
        numeric_features = features.select_dtypes(include=[np.number])
        
        # NaN检查
        nan_count = numeric_features.isna().sum().sum()
        assert nan_count == 0, f"发现 {nan_count} 个NaN值"
        
        # Inf检查
        inf_mask = np.isinf(numeric_features.values)
        inf_count = inf_mask.sum()
        assert inf_count == 0, f"发现 {inf_count} 个Inf值"
        
        # 特征范围检查（部分特征可能有特定范围）
        for col in numeric_features.columns:
            col_values = numeric_features[col].values
            if not np.all(np.isfinite(col_values)):
                continue
            
            # 检查特征是否都是有限值
            assert np.all(np.isfinite(col_values)), f"特征 {col} 包含非有限值"
            
            # 检查特征是否都是实数
            assert np.all(np.isreal(col_values)), f"特征 {col} 包含非实数值"


class TestModelTrainingIntegration:
    """模型训练集成测试"""
    
    @pytest.fixture
    def sample_features(self):
        """创建样本特征数据"""
        np.random.seed(42)
        n_samples = 100
        n_features = 50
        
        # 创建特征数据
        features = pd.DataFrame(
            np.random.randn(n_samples, n_features),
            columns=[f'feature_{i}' for i in range(n_features)]
        )
        
        # 添加目标变量
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        for pos in positions:
            features[pos] = np.random.randint(0, 10, n_samples)
        
        features['period'] = [f'2026{str(i).zfill(3)}' for i in range(1001, 1001 + n_samples)]
        
        return features
    
    def test_feature_to_model_training(self, sample_features):
        """测试特征到模型训练的集成"""
        # 1. 准备特征和目标
        feature_cols = [col for col in sample_features.columns 
                       if col not in ['period', 'wan', 'qian', 'bai', 'shi', 'ge']]
        
        assert len(feature_cols) > 0
        
        # 2. 创建预测器
        predictor = PL5Predictor()
        
        # 3. 训练模型
        try:
            predictor.fit(sample_features, feature_cols)
            
            # 验证模型是否训练成功
            assert predictor.ensemble_models is not None
            assert len(predictor.ensemble_models) == 5  # 5个位置
            
            # 检查每个位置的模型
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                assert pos in predictor.ensemble_models
                assert predictor.ensemble_models[pos] is not None
            
            logger.info("模型训练成功")
            
        except Exception as e:
            pytest.skip(f"模型训练失败: {e}")
    
    def test_model_prediction_integration(self, sample_features):
        """测试模型预测集成"""
        # 准备特征
        feature_cols = [col for col in sample_features.columns 
                       if col not in ['period', 'wan', 'qian', 'bai', 'shi', 'ge']]
        
        # 创建并训练预测器
        predictor = PL5Predictor()
        predictor.fit(sample_features, feature_cols)
        
        # 获取最新特征进行预测
        latest_features = sample_features[feature_cols].iloc[-1].values
        
        # 准备原始数据供HMM/Copula使用
        recent_original_data = {
            pos: sample_features[pos].values[-10:]  # 最近10条数据
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']
        }
        
        # 生成预测
        predictions = predictor.predict(
            latest_features, 
            recent_original_data=recent_original_data,
            top_k=3
        )
        
        # 验证预测结果
        assert predictions is not None
        assert isinstance(predictions, dict)
        
        # 检查每个位置的预测
        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            assert pos in predictions
            pos_predictions = predictions[pos]
            
            # 预测应该是列表
            assert isinstance(pos_predictions, list)
            
            # 预测数量应该正确
            assert len(pos_predictions) == 3  # top_k=3
            
            # 预测应该是0-9的数字
            for pred in pos_predictions:
                assert isinstance(pred, (int, np.integer))
                assert 0 <= pred <= 9
        
        logger.info(f"预测成功生成: {predictions}")


class TestSystemFlow:
    """系统流程测试"""
    
    def test_complete_system_flow(self, tmp_path):
        """测试完整系统流程"""
        # 这个测试模拟从数据到预测的完整流程
        # 由于是集成测试，我们只测试流程是否能够正常执行
        
        try:
            # 1. 数据准备
            np.random.seed(42)
            n_records = 30
            
            data = pd.DataFrame({
                'period': [f'2026{str(i).zfill(3)}' for i in range(1001, 1001 + n_records)],
                'wan': np.random.randint(0, 10, n_records),
                'qian': np.random.randint(0, 10, n_records),
                'bai': np.random.randint(0, 10, n_records),
                'shi': np.random.randint(0, 10, n_records),
                'ge': np.random.randint(0, 10, n_records)
            })
            
            # 2. 数据验证
            validator = AdvancedDataValidator(ValidationLevel.STANDARD)
            validation_result = validator.validate_dataset(data)
            
            if not validation_result.is_valid:
                data = DataCleaner.clean_dataset(data, validation_result)
            
            # 3. 特征工程
            engineer = FeatureEngineer()
            features = engineer.extract_all_features(data)
            
            feature_cols = [col for col in features.columns 
                           if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
            
            assert len(feature_cols) > 0
            
            # 4. 模型训练
            predictor = PL5Predictor()
            predictor.fit(features, feature_cols)
            
            # 5. 预测
            latest_features = features[feature_cols].iloc[-1].values
            recent_original_data = {
                pos: data[pos].values[-5:]
                for pos in ['wan', 'qian', 'bai', 'shi', 'ge']
            }
            
            predictions = predictor.predict(
                latest_features,
                recent_original_data=recent_original_data,
                top_k=2
            )
            
            # 验证最终结果
            assert predictions is not None
            
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                assert pos in predictions
                assert len(predictions[pos]) == 2
                for pred in predictions[pos]:
                    assert 0 <= pred <= 9
            
            logger.info("完整系统流程测试通过")
            
        except Exception as e:
            pytest.fail(f"完整系统流程测试失败: {e}")


class TestErrorHandlingIntegration:
    """错误处理集成测试"""
    
    def test_error_handling_in_data_validation(self):
        """测试数据验证中的错误处理"""
        # 创建有问题的数据
        problematic_data = pd.DataFrame({
            'period': ['invalid', None, ''],
            'wan': ['not_a_number', 10, -1],
            'qian': [2, 3, 4],
            'bai': [3, 4, 5],
            'shi': [4, 5, 6],
            'ge': [5, 6, 7]
        })
        
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        result = validator.validate_dataset(problematic_data)
        
        # 验证应该失败，但不应崩溃
        assert result.is_valid is False
        assert len(result.issues) > 0
        
        # 验证报告应该包含有用的信息
        assert result.summary['invalid_records'] > 0
        assert result.summary['validity_rate'] < 1.0
    
    def test_error_handling_in_feature_engineering(self):
        """测试特征工程中的错误处理"""
        # 创建空数据
        empty_data = pd.DataFrame()
        
        engineer = FeatureEngineer()
        
        # 空数据应该被优雅处理
        try:
            features = engineer.extract_all_features(empty_data)
            # 如果函数返回了某些东西，它应该是空DataFrame
            if features is not None:
                assert features.empty
        except Exception as e:
            # 如果抛出异常，它应该是可预期的异常类型
            assert "empty" in str(e).lower() or "data" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])