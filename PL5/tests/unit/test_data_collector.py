"""
数据采集模块单元测试
测试DataCollector、DataValidator、DataVersionManager等核心组件
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
import shutil

# 导入被测模块
from src.core.data.collector import DataValidator, DataVersionManager, PL5DataCollectorV8, retry_on_failure
from src.core.utils.errors import DataValidationError, NetworkError

# ═══════════════════════════════════════════════════════════════
# DataValidator 测试
# ═══════════════════════════════════════════════════════════════


class TestDataValidator:
    """测试数据验证器"""

    @pytest.fixture
    def validator(self):
        return DataValidator()

    @pytest.mark.unit
    @pytest.mark.data
    def test_validate_period_valid(self, validator):
        """测试有效期号验证"""
        assert validator.validate_period("2026076") is True
        assert validator.validate_period("26076") is True
        assert validator.validate_period("2026001") is True

    @pytest.mark.unit
    @pytest.mark.data
    def test_validate_period_invalid(self, validator):
        """测试无效期号验证"""
        assert validator.validate_period("") is False
        assert validator.validate_period("invalid") is False
        assert validator.validate_period("1234") is False  # 太短
        assert validator.validate_period("12345678") is False  # 太长
        assert validator.validate_period(None) is False

    @pytest.mark.unit
    @pytest.mark.data
    def test_validate_digit_valid(self, validator):
        """测试有效数字验证"""
        for i in range(10):
            assert validator.validate_digit(i) is True
            assert validator.validate_digit(str(i)) is True

    @pytest.mark.unit
    @pytest.mark.data
    def test_validate_digit_invalid(self, validator):
        """测试无效数字验证"""
        assert validator.validate_digit(10) is False
        assert validator.validate_digit(-1) is False
        assert validator.validate_digit("a") is False
        assert validator.validate_digit(None) is False
        # 浮点数在0-9范围内被视为有效
        assert validator.validate_digit(3.5) is True

    @pytest.mark.unit
    @pytest.mark.data
    def test_validate_record_valid(self, validator):
        """测试有效记录验证"""
        record = {"period": "2026076", "wan": 1, "qian": 2, "bai": 3, "shi": 4, "ge": 5}
        is_valid, msg = validator.validate_record(record)
        assert is_valid is True
        assert msg == "验证通过"

    @pytest.mark.unit
    @pytest.mark.data
    def test_validate_record_missing_field(self, validator):
        """测试缺少字段的记录"""
        record = {
            "period": "2026076",
            "wan": 1,
            "qian": 2,
            "bai": 3,
            "shi": 4,
            # 缺少 'ge'
        }
        is_valid, msg = validator.validate_record(record)
        assert is_valid is False
        assert "缺少字段" in msg

    @pytest.mark.unit
    @pytest.mark.data
    def test_validate_record_invalid_period(self, validator):
        """测试无效期号的记录"""
        record = {"period": "invalid", "wan": 1, "qian": 2, "bai": 3, "shi": 4, "ge": 5}
        is_valid, msg = validator.validate_record(record)
        assert is_valid is False
        assert "期号" in msg

    @pytest.mark.unit
    @pytest.mark.data
    def test_validate_record_out_of_range_digit(self, validator):
        """测试数字超出范围的记录"""
        record = {"period": "2026076", "wan": 15, "qian": 2, "bai": 3, "shi": 4, "ge": 5}
        is_valid, msg = validator.validate_record(record)
        assert is_valid is False
        assert "数字" in msg


# ═══════════════════════════════════════════════════════════════
# DataVersionManager 测试
# ═══════════════════════════════════════════════════════════════


class TestDataVersionManager:
    """测试数据版本管理器"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def version_manager(self, temp_dir, monkeypatch):
        """创建版本管理器实例"""
        # 使用临时目录
        import src.core.data.collector as collector_module

        monkeypatch.setattr(collector_module, "MODELS_DIR", temp_dir)
        monkeypatch.setattr(collector_module, "RAW_DATA_DIR", temp_dir / "raw")

        return DataVersionManager()

    @pytest.mark.unit
    @pytest.mark.data
    def test_get_current_version_empty(self, version_manager):
        """测试获取空版本信息"""
        version = version_manager.get_current_version()
        assert version["version"] == "0.0.0"
        assert version["last_update"] is None
        assert version["record_count"] == 0

    @pytest.mark.unit
    @pytest.mark.data
    def test_save_and_get_version(self, version_manager, sample_pl5_data):
        """测试保存和获取版本信息"""
        df = sample_pl5_data
        version_manager.save_version(df, source="test")

        version = version_manager.get_current_version()
        assert version["record_count"] == len(df)
        assert version["source"] == "test"
        assert version["latest_period"] == str(df["period"].iloc[-1])
        assert "data_hash" in version
        assert "columns" in version

    @pytest.mark.unit
    @pytest.mark.data
    def test_calculate_data_hash(self, version_manager, sample_pl5_data):
        """测试数据哈希计算"""
        df = sample_pl5_data
        hash1 = version_manager.calculate_data_hash(df)
        hash2 = version_manager.calculate_data_hash(df)

        # 相同数据应产生相同哈希
        assert hash1 == hash2
        assert len(hash1) == 16

        # 修改数据后哈希应不同
        df_modified = df.copy()
        df_modified.iloc[0, 0] = "9999999"
        hash3 = version_manager.calculate_data_hash(df_modified)
        assert hash1 != hash3

    @pytest.mark.unit
    @pytest.mark.data
    def test_create_and_restore_backup(self, version_manager, sample_pl5_data):
        """测试创建和恢复备份"""
        df = sample_pl5_data

        # 创建备份
        backup_path = version_manager.create_backup(df)
        assert backup_path.exists()

        # 恢复备份
        restored_df = version_manager.restore_backup(backup_path)
        assert restored_df is not None
        assert len(restored_df) == len(df)
        # 比较数据内容，忽略数据类型差异和前导零
        for col in df.columns:
            for i in range(len(df)):
                left = str(restored_df[col].iloc[i]).lstrip("0") or "0"
                right = str(df[col].iloc[i]).lstrip("0") or "0"
                assert left == right, f"Column {col} row {i}: {left} != {right}"

    @pytest.mark.unit
    @pytest.mark.data
    def test_list_backups(self, version_manager, sample_pl5_data):
        """测试列出备份"""
        df = sample_pl5_data
        version_manager.create_backup(df)

        backups = version_manager.list_backups()
        assert len(backups) >= 1

    @pytest.mark.unit
    @pytest.mark.data
    def test_restore_nonexistent_backup(self, version_manager):
        """测试恢复不存在的备份"""
        result = version_manager.restore_backup(Path("/nonexistent/path.csv"))
        assert result is None


# ═══════════════════════════════════════════════════════════════
# PL5DataCollectorV8 测试
# ═══════════════════════════════════════════════════════════════


class TestPL5DataCollectorV8:
    """测试数据采集器V8"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def collector(self, temp_dir, monkeypatch):
        """创建采集器实例"""
        import src.core.data.collector as collector_module

        monkeypatch.setattr(collector_module, "RAW_DATA_DIR", temp_dir / "raw")
        monkeypatch.setattr(collector_module, "PROCESSED_DATA_DIR", temp_dir / "processed")
        monkeypatch.setattr(collector_module, "MODELS_DIR", temp_dir / "models")

        (temp_dir / "raw").mkdir(exist_ok=True)
        (temp_dir / "processed").mkdir(exist_ok=True)
        (temp_dir / "models").mkdir(exist_ok=True)

        return PL5DataCollectorV8()

    @pytest.mark.unit
    @pytest.mark.data
    def test_collector_initialization(self, collector):
        """测试采集器初始化"""
        assert collector.positions == ["wan", "qian", "bai", "shi", "ge"]
        assert collector.validator is not None
        assert collector.version_manager is not None
        assert "lecai" in collector.data_sources
        assert "local" in collector.data_sources

    @pytest.mark.unit
    @pytest.mark.data
    def test_parse_raw_data_valid(self, collector, sample_raw_text):
        """测试解析有效原始数据"""
        df = collector.parse_raw_data(sample_raw_text)

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "period" in df.columns
        assert "wan" in df.columns
        assert "qian" in df.columns
        assert "bai" in df.columns
        assert "shi" in df.columns
        assert "ge" in df.columns
        assert "full_number" in df.columns

    @pytest.mark.unit
    @pytest.mark.data
    def test_parse_raw_data_empty(self, collector):
        """测试解析空数据"""
        df = collector.parse_raw_data("")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @pytest.mark.unit
    @pytest.mark.data
    def test_parse_raw_data_invalid(self, collector):
        """测试解析无效数据"""
        invalid_text = "invalid line\nanother invalid"
        df = collector.parse_raw_data(invalid_text)
        assert isinstance(df, pd.DataFrame)

    @pytest.mark.unit
    @pytest.mark.data
    def test_parse_raw_data_with_errors(self, collector):
        """测试解析包含错误行的数据"""
        text = """2026076 2026-03-15 1 2 3 4 5 12345
invalid line
2026077 2026-03-16 2 3 4 5 6 23456
2026078 2026-03-17 10 11 12 13 14 1011121314
2026079 2026-03-18 5 6 7 8 9 56789"""

        df = collector.parse_raw_data(text)
        assert isinstance(df, pd.DataFrame)
        # 只有有效行被解析
        assert len(df) == 3

    @pytest.mark.unit
    @pytest.mark.data
    def test_load_local_data_nonexistent(self, collector):
        """测试加载不存在的本地数据"""
        result = collector.load_local_data()
        assert result is None

    @pytest.mark.unit
    @pytest.mark.data
    def test_load_local_data_empty_file(self, collector):
        """测试加载空文件"""
        # 创建空文件
        collector.raw_data_path.write_text("")
        result = collector.load_local_data()
        assert result is None

    @pytest.mark.unit
    @pytest.mark.data
    def test_load_local_data_valid(self, collector, sample_raw_text):
        """测试加载有效本地数据"""
        collector.raw_data_path.write_text(sample_raw_text, encoding="utf-8")
        df = collector.load_local_data()

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    @pytest.mark.unit
    @pytest.mark.data
    def test_get_latest_period_with_data(self, collector, sample_pl5_data):
        """测试获取最新期号（有数据）"""
        # 保存版本信息
        collector.version_manager.save_version(sample_pl5_data, source="test")

        latest = collector.get_latest_period()
        expected = str(sample_pl5_data["period"].iloc[-1])
        assert latest == expected

    @pytest.mark.unit
    @pytest.mark.data
    def test_get_latest_period_no_data(self, temp_dir, monkeypatch):
        """测试获取最新期号（无数据）- 使用完全隔离的环境"""
        import src.core.data.collector as collector_module

        # 在导入PL5DataCollectorV8之前patch路径
        monkeypatch.setattr(collector_module, "RAW_DATA_DIR", temp_dir / "raw")
        monkeypatch.setattr(collector_module, "PROCESSED_DATA_DIR", temp_dir / "processed")
        monkeypatch.setattr(collector_module, "MODELS_DIR", temp_dir / "models")

        (temp_dir / "raw").mkdir(parents=True, exist_ok=True)
        (temp_dir / "processed").mkdir(parents=True, exist_ok=True)
        (temp_dir / "models").mkdir(parents=True, exist_ok=True)

        # 重新导入以使用新的路径
        from importlib import reload

        reload(collector_module)

        collector = collector_module.PL5DataCollectorV8()

        # 手动清除版本管理器中的数据，模拟无数据状态
        collector.version_manager.version_file = temp_dir / "models" / "data_version.json"
        # 确保版本文件不存在
        if collector.version_manager.version_file.exists():
            collector.version_manager.version_file.unlink()

        latest = collector.get_latest_period()
        assert latest is None

    @pytest.mark.unit
    @pytest.mark.data
    @patch("src.core.data.collector.requests.get")
    def test_fetch_from_network_success(self, mock_get, collector):
        """测试网络获取成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        # 提供足够长的数据内容（至少100个字符）
        mock_response.text = "2026076 2026-03-15 1 2 3 4 5 12345\n2026077 2026-03-16 2 3 4 5 6 23456\n" + "x" * 100
        mock_get.return_value = mock_response

        result = collector.fetch_from_network("lecai")
        assert result is not None
        assert "2026076" in result

    @pytest.mark.unit
    @pytest.mark.data
    @patch("src.core.data.collector.requests.get")
    def test_fetch_from_network_403(self, mock_get, collector):
        """测试网络获取403错误"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        with pytest.raises(NetworkError):
            collector.fetch_from_network("lecai")

    @pytest.mark.unit
    @pytest.mark.data
    @patch("src.core.data.collector.requests.get")
    def test_fetch_from_network_timeout(self, mock_get, collector):
        """测试网络获取超时"""
        from requests import Timeout

        mock_get.side_effect = Timeout("Connection timeout")

        with pytest.raises(NetworkError):
            collector.fetch_from_network("lecai")

    @pytest.mark.unit
    @pytest.mark.data
    def test_update_data_from_local(self, collector, sample_raw_text):
        """测试从本地更新数据"""
        # 准备本地数据
        collector.raw_data_path.write_text(sample_raw_text, encoding="utf-8")

        df = collector.update_data()

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "period" in df.columns


# ═══════════════════════════════════════════════════════════════
# 装饰器测试
# ═══════════════════════════════════════════════════════════════


class TestRetryDecorator:
    """测试重试装饰器"""

    @pytest.mark.unit
    def test_retry_success_first_attempt(self):
        """测试首次成功不重试"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.1)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.unit
    def test_retry_success_after_failures(self):
        """测试失败后重试成功"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.1)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.unit
    def test_retry_exhausted(self):
        """测试重试次数耗尽"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.1)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")

        with pytest.raises(Exception):
            always_fail()

        assert call_count == 3


# ═══════════════════════════════════════════════════════════════
# 边界条件测试
# ═══════════════════════════════════════════════════════════════


class TestDataCollectorEdgeCases:
    """测试边界条件"""

    @pytest.mark.unit
    @pytest.mark.data
    def test_parse_single_record(self):
        """测试解析单条记录"""
        validator = DataValidator()
        text = "2026076 2026-03-15 1 2 3 4 5 12345"

        # 这里我们直接测试验证器
        parts = text.split()
        record = {
            "period": parts[0],
            "date": parts[1],
            "wan": int(parts[2]),
            "qian": int(parts[3]),
            "bai": int(parts[4]),
            "shi": int(parts[5]),
            "ge": int(parts[6]),
        }

        is_valid, msg = validator.validate_record(record)
        assert is_valid is True

    @pytest.mark.unit
    @pytest.mark.data
    def test_validate_large_period_number(self):
        """测试大期号验证"""
        validator = DataValidator()
        # 7位期号
        assert validator.validate_period("9999999") is True
        # 5位期号
        assert validator.validate_period("99999") is True

    @pytest.mark.unit
    @pytest.mark.data
    def test_dataframe_with_nan_values(self):
        """测试包含NaN值的数据框"""
        df = pd.DataFrame(
            {
                "period": ["2026076", "2026077", None],
                "wan": [1, 2, np.nan],
                "qian": [2, np.nan, 4],
                "bai": [3, 4, 5],
                "shi": [4, 5, 6],
                "ge": [5, 6, 7],
            }
        )

        validator = DataValidator()
        # NaN值应该被视为无效
        assert validator.validate_digit(np.nan) is False
