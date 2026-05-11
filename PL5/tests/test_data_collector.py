"""
数据采集模块单元测试
"""

import unittest
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_collector import PL5DataCollector, DataValidator, DataVersionManager, retry_on_failure


class TestDataValidator(unittest.TestCase):
    """测试数据验证器"""

    def setUp(self):
        self.validator = DataValidator()

    def test_validate_period_valid(self):
        """测试有效期号验证"""
        self.assertTrue(self.validator.validate_period("2026076"))
        self.assertTrue(self.validator.validate_period("26076"))

    def test_validate_period_invalid(self):
        """测试无效期号验证"""
        self.assertFalse(self.validator.validate_period(""))
        self.assertFalse(self.validator.validate_period("abc"))
        self.assertFalse(self.validator.validate_period("12345678"))

    def test_validate_digit_valid(self):
        """测试有效数字验证"""
        for i in range(10):
            self.assertTrue(self.validator.validate_digit(i))
            self.assertTrue(self.validator.validate_digit(str(i)))

    def test_validate_digit_invalid(self):
        """测试无效数字验证"""
        self.assertFalse(self.validator.validate_digit(10))
        self.assertFalse(self.validator.validate_digit(-1))
        self.assertFalse(self.validator.validate_digit("a"))

    def test_validate_record_valid(self):
        """测试有效记录验证"""
        record = {"period": "2026076", "wan": 1, "qian": 2, "bai": 3, "shi": 4, "ge": 5}
        is_valid, msg = self.validator.validate_record(record)
        self.assertTrue(is_valid)
        self.assertEqual(msg, "验证通过")

    def test_validate_record_missing_field(self):
        """测试缺少字段的记录"""
        record = {"period": "2026076", "wan": 1}
        is_valid, msg = self.validator.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIn("缺少字段", msg)


class TestDataVersionManager(unittest.TestCase):
    """测试数据版本管理器"""

    def setUp(self):
        self.version_manager = DataVersionManager()
        # 创建测试数据
        self.test_df = pd.DataFrame(
            {
                "period": ["2026001", "2026002", "2026003"],
                "wan": [1, 2, 3],
                "qian": [4, 5, 6],
                "bai": [7, 8, 9],
                "shi": [0, 1, 2],
                "ge": [3, 4, 5],
            }
        )

    def test_get_current_version(self):
        """测试获取当前版本"""
        version = self.version_manager.get_current_version()
        self.assertIsInstance(version, dict)
        self.assertIn("version", version)

    def test_calculate_data_hash(self):
        """测试数据哈希计算"""
        hash1 = self.version_manager.calculate_data_hash(self.test_df)
        hash2 = self.version_manager.calculate_data_hash(self.test_df)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 16)

    def test_save_and_get_version(self):
        """测试保存和获取版本"""
        self.version_manager.save_version(self.test_df, "test")
        version = self.version_manager.get_current_version()
        self.assertEqual(version["record_count"], 3)
        self.assertEqual(version["source"], "test")


class TestRetryOnFailure(unittest.TestCase):
    """测试重试装饰器"""

    def test_retry_success(self):
        """测试成功不重试"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.1)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)

    def test_retry_failure(self):
        """测试失败重试"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.1)
        def fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")

        with self.assertRaises(ValueError):
            fail_func()

        self.assertEqual(call_count, 3)


class TestPL5DataCollector(unittest.TestCase):
    """测试数据采集器"""

    def setUp(self):
        self.collector = PL5DataCollector()

    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.collector)
        self.assertIsNotNone(self.collector.validator)
        self.assertIsNotNone(self.collector.version_manager)

    def test_parse_raw_data_empty(self):
        """测试解析空数据"""
        df = self.collector.parse_raw_data("")
        self.assertTrue(df.empty)

    def test_parse_raw_data_invalid(self):
        """测试解析无效数据"""
        df = self.collector.parse_raw_data("invalid data")
        self.assertTrue(df.empty)


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestDataValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestDataVersionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestRetryOnFailure))
    suite.addTests(loader.loadTestsFromTestCase(TestPL5DataCollector))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
