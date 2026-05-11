"""
数据验证模块单元测试
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from src.core.data.validator import (
    AdvancedDataValidator,
    DataCleaner,
    ValidationLevel,
    quick_validate,
    clean_and_validate,
)


class TestAdvancedDataValidator:
    """高级数据验证器测试"""

    def test_validate_valid_data(self, sample_pl5_data):
        """测试验证有效数据"""
        validator = AdvancedDataValidator(ValidationLevel.STANDARD)
        result = validator.validate_dataset(sample_pl5_data)

        assert result.is_valid is True
        assert result.summary["valid_records"] == 5
        assert result.summary["validity_rate"] == 1.0
        assert len(result.issues) == 0
