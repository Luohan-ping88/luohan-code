"""
数据验证模块单元测试
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from src.core.data.validator import (
    DataValidator,
    DataValidationError
)


class TestAdvancedDataValidator:
    """高级数据验证器测试"""
    
    def test_validate_valid_data(self, sample_pl5_data):
        """测试验证有效数据"""
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        result = validator.validate_dataset(sample_pl5_data)
        
        assert result.is_valid is True
        assert result.summary['valid_records'] == 5
        assert result.summary['validity_rate'] == 1.0
        assert len(result.issues) == 0
    
    def test_validate_invalid_data(self, sample_invalid_data):
        """测试验证无效数据"""
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        result = validator.validate_dataset(sample_invalid_data)
        
        assert result.is_valid is False
        assert result.summary['invalid_records'] > 0
        assert result.summary['validity_rate'] < 1.0
        assert len(result.issues) > 0
    
    def test_validate_duplicate_data(self, sample_duplicate_data):
        """测试验证重复数据"""
        validator = AdvancedDataValidator(ValidationLevel.STRICT)
        result = validator.validate_dataset(sample_duplicate_data)
        
        # 应该检测到重复问题
        issue_types = [issue['type'] for issue in result.issues]
        assert 'duplicates' in str(issue_types)
    
    def test_different_validation_levels(self, sample_pl5_data):
        """测试不同验证级别"""
        # BASIC级别
        validator_basic = AdvancedDataValidator(ValidationLevel.BASIC)
        result_basic = validator_basic.validate_dataset(sample_pl5_data)
        
        # COMPLETE级别
        validator_complete = AdvancedDataValidator(ValidationLevel.COMPLETE)
        result_complete = validator_complete.validate_dataset(sample_pl5_data)
        
        # COMPLETE级别应该进行更多检查
        assert result_basic.is_valid is True
        assert result_complete.is_valid is True
    
    def test_validate_empty_data(self):
        """测试验证空数据"""
        empty_data = pd.DataFrame()
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        result = validator.validate_dataset(empty_data)
        
        assert result.is_valid is False
        assert 'missing_values' in str([issue['type'] for issue in result.issues])
    
    def test_generate_validation_report(self, sample_pl5_data, tmp_path):
        """测试生成验证报告"""
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        result = validator.validate_dataset(sample_pl5_data)
        
        report_path = tmp_path / "validation_report.json"
        report_json = validator.generate_validation_report(result, report_path)
        
        assert report_path.exists()
        assert 'validation_result' in report_json
        assert 'summary' in report_json
        assert 'issues' in report_json
    
    def test_calculate_data_hash(self, sample_pl5_data):
        """测试计算数据哈希"""
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        result = validator.validate_dataset(sample_pl5_data)
        
        assert result.data_hash != "no_hash"
        assert result.data_hash != "error"
        assert len(result.data_hash) == 16  # MD5哈希的前16个字符


class TestDataCleaner:
    """数据清洗器测试"""
    
    def test_clean_valid_data(self, sample_pl5_data):
        """测试清洗有效数据"""
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        validation_result = validator.validate_dataset(sample_pl5_data)
        
        cleaned_data = DataCleaner.clean_dataset(sample_pl5_data, validation_result)
        
        assert cleaned_data.shape == sample_pl5_data.shape
        assert cleaned_data.equals(sample_pl5_data)
    
    def test_clean_invalid_data(self, sample_invalid_data):
        """测试清洗无效数据"""
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        validation_result = validator.validate_dataset(sample_invalid_data)
        
        cleaned_data = DataCleaner.clean_dataset(sample_invalid_data, validation_result)
        
        # 清洗后数据应该更有效
        assert cleaned_data.shape[0] <= sample_invalid_data.shape[0]
        
        # 检查无效值是否被修复
        if 'wan' in cleaned_data.columns:
            assert cleaned_data['wan'].between(0, 9).all()
    
    def test_remove_duplicates(self, sample_duplicate_data):
        """测试移除重复数据"""
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        validation_result = validator.validate_dataset(sample_duplicate_data)
        
        cleaned_data = DataCleaner.clean_dataset(sample_duplicate_data, validation_result)
        
        # 重复记录应该被移除
        assert cleaned_data['period'].nunique() == cleaned_data.shape[0]
        assert cleaned_data.shape[0] < sample_duplicate_data.shape[0]
    
    def test_fix_invalid_values(self):
        """测试修复无效值"""
        invalid_data = pd.DataFrame({
            'period': ['2026071', '2026072'],
            'wan': ['invalid', 10],  # 字符串和超出范围的值
            'qian': [2, 3],
            'bai': [3, 4],
            'shi': [4, 5],
            'ge': [5, 6]
        })
        
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        validation_result = validator.validate_dataset(invalid_data)
        
        cleaned_data = DataCleaner.clean_dataset(invalid_data, validation_result)
        
        # 检查无效值是否被修复
        assert cleaned_data['wan'].dtype in [np.int32, np.int64]
        assert cleaned_data['wan'].between(0, 9).all()
    
    def test_ensure_types(self):
        """测试确保数据类型"""
        mixed_type_data = pd.DataFrame({
            'period': [2026071, 2026072],  # 整数类型
            'wan': ['1', '2'],  # 字符串类型
            'qian': [2.0, 3.0],  # 浮点类型
            'bai': [3, 4],
            'shi': [4, 5],
            'ge': [5, 6]
        })
        
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        validation_result = validator.validate_dataset(mixed_type_data)
        
        cleaned_data = DataCleaner.clean_dataset(mixed_type_data, validation_result)
        
        # 检查数据类型是否被正确转换
        assert cleaned_data['period'].dtype == object or cleaned_data['period'].dtype.name == 'object'
        assert cleaned_data['wan'].dtype in [np.int32, np.int64]
        assert cleaned_data['qian'].dtype in [np.int32, np.int64]


class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_quick_validate(self, sample_pl5_data):
        """测试快速验证"""
        is_valid, message = quick_validate(sample_pl5_data)
        
        assert is_valid is True
        assert "数据验证通过" in message
    
    def test_quick_validate_invalid(self, sample_invalid_data):
        """测试快速验证无效数据"""
        is_valid, message = quick_validate(sample_invalid_data)
        
        assert is_valid is False
        assert "数据验证失败" in message
    
    def test_clean_and_validate_valid(self, sample_pl5_data):
        """测试清洗并验证有效数据"""
        cleaned_data, result = clean_and_validate(sample_pl5_data)
        
        assert cleaned_data.shape == sample_pl5_data.shape
        assert result.is_valid is True
    
    def test_clean_and_validate_invalid(self, sample_invalid_data):
        """测试清洗并验证无效数据"""
        cleaned_data, result = clean_and_validate(sample_invalid_data)
        
        # 清洗后的数据应该更有效
        assert cleaned_data.shape[0] <= sample_invalid_data.shape[0]
        
        # 重新验证应该通过或至少问题更少
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        new_result = validator.validate_dataset(cleaned_data)
        
        # 清洗后的数据应该问题更少
        assert len(new_result.issues) <= len(result.issues)


class TestValidationLevel:
    """验证级别测试"""
    
    def test_validation_level_enum(self):
        """测试验证级别枚举"""
        assert ValidationLevel.BASIC.value == "basic"
        assert ValidationLevel.STANDARD.value == "standard"
        assert ValidationLevel.STRICT.value == "strict"
        assert ValidationLevel.COMPLETE.value == "complete"
    
    def test_validation_level_comparison(self):
        """测试验证级别比较"""
        levels = [ValidationLevel.BASIC, ValidationLevel.STANDARD, 
                  ValidationLevel.STRICT, ValidationLevel.COMPLETE]
        
        # 验证级别应该有顺序
        for i in range(len(levels) - 1):
            assert levels[i].value != levels[i + 1].value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])