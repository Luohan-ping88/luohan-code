#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 故障恢复测试套件 V2.0
测试系统的故障检测和自动恢复能力

测试内容：
- 模拟故障场景
- 测试自动恢复能力
- 验证系统稳定性
- 测试备份恢复流程
"""

import os
import sys
import time
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.utils.error_handler import (
    ErrorLogger, RecoveryManager, error_logger, recovery_manager,
    retry_with_exponential_backoff, safe_execute, handle_errors, circuit_breaker,
    DataLoadError, ModelLoadError, NetworkError, ServiceUnavailableError,
    get_error_stats, get_recovery_stats, clear_error_history
)
from scripts.utility.auto_backup import BackupManager, BackupConfig
from scripts.utility.restore_backup import BackupRestorer


class TestErrorHandling(unittest.TestCase):
    """错误处理测试"""

    def setUp(self):
        """设置测试环境"""
        clear_error_history()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)

    def tearDown(self):
        """清理测试环境"""
        self.temp_dir.cleanup()

    def test_error_classification(self):
        """测试错误分类"""
        # 数据错误
        data_error = DataLoadError("无法加载数据", file_path="/path/to/data.csv")
        self.assertEqual(data_error.category.value, "data")
        self.assertIn("file_path", data_error.context)

        # 模型错误
        model_error = ModelLoadError("无法加载模型", model_path="/path/to/model.pkl")
        self.assertEqual(model_error.category.value, "model")
        self.assertIn("model_path", model_error.context)

        # 网络错误
        network_error = NetworkError("连接超时", url="http://example.com", status_code=500)
        self.assertEqual(network_error.category.value, "network")
        self.assertEqual(network_error.status_code, 500)

    def test_error_logging(self):
        """测试错误日志记录"""
        error = DataLoadError("测试错误")
        record = error_logger.log_error(error, operation="test_operation", component="test_component")

        self.assertIsNotNone(record)
        self.assertEqual(record.error_type, "DataLoadError")
        self.assertEqual(record.context.operation, "test_operation")
        self.assertEqual(record.context.component, "test_component")

    def test_error_stats(self):
        """测试错误统计"""
        clear_error_history()
        # 记录一些错误
        for i in range(5):
            error_logger.log_error(DataLoadError(f"数据错误 {i}"))
        for i in range(3):
            error_logger.log_error(ModelLoadError(f"模型错误 {i}"))

        stats = get_error_stats()

        self.assertEqual(stats["total_errors"], 8)
        # 检查错误类型统计（可能是 data:DataLoadError 或 DataLoadError）
        self.assertTrue(
            "data:DataLoadError" in stats["errors_by_type"] or
            "DataLoadError" in stats["errors_by_type"]
        )

    def test_retry_decorator(self):
        """测试重试装饰器"""
        attempt_count = 0

        @retry_with_exponential_backoff(max_retries=3, base_delay=0.1)
        def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("模拟失败")
            return "成功"

        result = flaky_function()
        self.assertEqual(result, "成功")
        self.assertEqual(attempt_count, 3)

    def test_retry_with_fallback(self):
        """测试带回退的重试"""
        # 使用唯一的操作名避免与其他测试冲突
        op_name = f"test_op_{id(self)}"
        # 先记录一个成功的结果
        recovery_manager.record_success(op_name, "last_good_result")

        @retry_with_exponential_backoff(max_retries=2, base_delay=0.1, operation_name=op_name)
        def always_fail():
            raise Exception("总是失败")

        # 应该返回上次成功的结果
        result = always_fail()
        self.assertEqual(result, "last_good_result")

    def test_safe_execute(self):
        """测试安全执行"""
        def failing_function():
            raise Exception("函数失败")

        result = safe_execute(failing_function, fallback_value="默认值")
        self.assertEqual(result, "默认值")

    def test_handle_errors_decorator(self):
        """测试错误处理装饰器"""
        @handle_errors(fallback_value="默认值")
        def failing_function():
            raise Exception("函数失败")

        result = failing_function()
        self.assertEqual(result, "默认值")

    def test_circuit_breaker(self):
        """测试熔断器"""
        call_count = 0

        @circuit_breaker(failure_threshold=3, recovery_timeout=0.1)
        def unstable_function(should_fail):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise Exception("失败")
            return "成功"

        # 前3次调用失败
        for i in range(3):
            with self.assertRaises(Exception):
                unstable_function(True)

        # 第4次应该触发熔断
        with self.assertRaises(ServiceUnavailableError):
            unstable_function(False)

        # 等待熔断器恢复
        time.sleep(0.2)

        # 现在应该可以成功
        result = unstable_function(False)
        self.assertEqual(result, "成功")


class TestBackupSystem(unittest.TestCase):
    """备份系统测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)
        self.original_cwd = os.getcwd()
        os.chdir(self.test_path)

        # 创建测试目录结构
        (self.test_path / "data").mkdir()
        (self.test_path / "models").mkdir()
        (self.test_path / "config").mkdir()

        # 创建测试文件
        (self.test_path / "data" / "test.csv").write_text("col1,col2\n1,2")
        (self.test_path / "models" / "model.pkl").write_text("model data")
        (self.test_path / "config" / "config.json").write_text('{"key": "value"}')

        # 初始化备份管理器
        config = BackupConfig(
            backup_dir=str(self.test_path / "backups"),
            daily_backup_dir=str(self.test_path / "backups" / "daily"),
            manual_backup_dir=str(self.test_path / "backups" / "manual"),
            compression_enabled=False  # 测试中禁用压缩以便检查
        )
        self.backup_manager = BackupManager(config)

    def tearDown(self):
        """清理测试环境"""
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_create_backup(self):
        """测试创建备份"""
        result = self.backup_manager.create_backup(backup_type="daily")

        self.assertEqual(result["status"], "success")
        self.assertIn("backup_id", result)
        self.assertIn("data", result["items"])
        self.assertIn("models", result["items"])

    def test_list_backups(self):
        """测试列出备份"""
        # 创建几个备份
        for i in range(3):
            self.backup_manager.create_backup(backup_type="daily")

        backups = self.backup_manager.list_backups()
        self.assertEqual(len(backups), 3)

    def test_restore_backup(self):
        """测试恢复备份"""
        # 创建备份
        result = self.backup_manager.create_backup(backup_type="daily")
        backup_id = result["backup_id"]

        # 修改原始文件
        (self.test_path / "data" / "test.csv").write_text("modified")

        # 恢复备份
        restore_result = self.backup_manager.restore_backup(backup_id)

        self.assertEqual(restore_result["status"], "success")

        # 验证文件已恢复
        content = (self.test_path / "data" / "test.csv").read_text()
        self.assertEqual(content, "col1,col2\n1,2")

    def test_backup_cleanup(self):
        """测试备份清理"""
        config = BackupConfig(
            backup_dir=str(self.test_path / "backups"),
            daily_backup_dir=str(self.test_path / "backups" / "daily"),
            manual_backup_dir=str(self.test_path / "backups" / "manual"),
            max_daily_backups=3,
            compression_enabled=False
        )
        manager = BackupManager(config)

        # 创建5个备份
        for i in range(5):
            manager.create_backup(backup_type="daily")

        backups = manager.list_backups("daily")
        self.assertLessEqual(len(backups), 3)

    def test_backup_integrity(self):
        """测试备份完整性验证"""
        result = self.backup_manager.create_backup(backup_type="daily")

        self.assertEqual(result.get("integrity_check"), "passed")

    def test_get_backup_stats(self):
        """测试获取备份统计"""
        # 创建几个备份
        self.backup_manager.create_backup(backup_type="daily")
        self.backup_manager.create_backup(backup_type="manual")

        stats = self.backup_manager.get_backup_stats()

        self.assertIn("daily_backups_count", stats)
        self.assertIn("manual_backups_count", stats)
        self.assertIn("total_size_bytes", stats)


class TestBackupRestorer(unittest.TestCase):
    """备份恢复器测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)
        self.original_cwd = os.getcwd()
        os.chdir(self.test_path)

        # 创建备份目录结构
        (self.test_path / "backups" / "daily").mkdir(parents=True)

        # 创建一个测试备份
        backup_dir = self.test_path / "backups" / "daily" / "test_backup"
        backup_dir.mkdir()

        (backup_dir / "data").mkdir()
        (backup_dir / "data" / "test.csv").write_text("col1,col2\n1,2")

        info = {
            "backup_id": "test_backup",
            "backup_type": "daily",
            "timestamp": datetime.now().isoformat(),
            "items": {"data": {"status": "success"}},
            "status": "success"
        }
        (backup_dir / "backup_info.json").write_text(json.dumps(info))

        self.restorer = BackupRestorer(str(self.test_path / "backups"))

    def tearDown(self):
        """清理测试环境"""
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_list_available_backups(self):
        """测试列出可用备份"""
        backups = self.restorer.list_available_backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0]["backup_id"], "test_backup")

    def test_find_backup(self):
        """测试查找备份"""
        backup_path = self.restorer.find_backup("test_backup")
        self.assertIsNotNone(backup_path)
        self.assertTrue(backup_path.exists())

    def test_restore(self):
        """测试恢复"""
        # 创建目标目录
        (self.test_path / "target").mkdir()

        result = self.restorer.restore(
            backup_id="test_backup",
            target_dir=str(self.test_path / "target"),
            create_pre_backup=False
        )

        self.assertEqual(result["status"], "success")
        self.assertTrue((self.test_path / "target" / "data" / "test.csv").exists())

    def test_get_latest_backup(self):
        """测试获取最新备份"""
        latest = self.restorer.get_latest_backup()
        self.assertIsNotNone(latest)
        self.assertEqual(latest["backup_id"], "test_backup")


class TestFaultScenarios(unittest.TestCase):
    """故障场景测试"""

    def setUp(self):
        """设置测试环境"""
        clear_error_history()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)

    def tearDown(self):
        """清理测试环境"""
        self.temp_dir.cleanup()

    def test_data_corruption_recovery(self):
        """测试数据损坏恢复"""
        # 模拟数据损坏检测
        def check_data_integrity(data_path: Path) -> bool:
            """检查数据完整性"""
            if not data_path.exists():
                return False
            # 简单的完整性检查
            return data_path.stat().st_size > 0

        # 创建测试文件
        test_file = self.test_path / "data.csv"
        test_file.write_text("valid,data\n1,2")

        # 验证完整性检查通过
        self.assertTrue(check_data_integrity(test_file))

        # 模拟损坏（清空文件）
        test_file.write_text("")

        # 验证完整性检查失败
        self.assertFalse(check_data_integrity(test_file))

    def test_service_restart_simulation(self):
        """测试服务重启模拟"""
        service_state = {"running": True, "restart_count": 0}

        def simulate_service_crash():
            service_state["running"] = False
            raise Exception("服务崩溃")

        def restart_service():
            service_state["running"] = True
            service_state["restart_count"] += 1

        # 模拟服务崩溃和重启
        try:
            simulate_service_crash()
        except Exception:
            restart_service()

        self.assertTrue(service_state["running"])
        self.assertEqual(service_state["restart_count"], 1)

    def test_network_failure_recovery(self):
        """测试网络故障恢复"""
        network_state = {"connected": True, "retry_count": 0}

        @retry_with_exponential_backoff(max_retries=3, base_delay=0.1)
        def network_operation():
            network_state["retry_count"] += 1
            if network_state["retry_count"] < 3:
                network_state["connected"] = False
                raise NetworkError("连接失败")
            network_state["connected"] = True
            return "success"

        result = network_operation()
        self.assertEqual(result, "success")
        self.assertTrue(network_state["connected"])
        self.assertEqual(network_state["retry_count"], 3)

    def test_resource_exhaustion_handling(self):
        """测试资源耗尽处理"""
        resource_usage = {"memory": 50, "max_memory": 100}

        def check_resources():
            if resource_usage["memory"] > resource_usage["max_memory"] * 0.9:
                raise ResourceWarning("内存使用超过90%")
            return True

        # 正常情况
        self.assertTrue(check_resources())

        # 资源耗尽情况
        resource_usage["memory"] = 95
        with self.assertRaises(ResourceWarning):
            check_resources()


class TestSystemStability(unittest.TestCase):
    """系统稳定性测试"""

    def test_error_rate_monitoring(self):
        """测试错误率监控"""
        clear_error_history()

        # 模拟一段时间内的错误
        for i in range(10):
            if i < 7:  # 70%成功率
                error_logger.log_error(DataLoadError(f"错误 {i}"))

        stats = get_error_stats()
        error_rate = stats["total_errors"] / 10

        # 错误率应该小于阈值（比如80%）
        self.assertLess(error_rate, 0.8)

    def test_recovery_success_rate(self):
        """测试恢复成功率"""
        # 创建新的恢复管理器实例以避免受其他测试影响
        from src.core.utils.error_handler import RecoveryManager
        test_recovery_manager = RecoveryManager()

        # 记录一些成功的恢复
        for i in range(8):
            test_recovery_manager.record_recovery_attempt(True)

        # 记录一些失败的恢复
        for i in range(2):
            test_recovery_manager.record_recovery_attempt(False)

        stats = test_recovery_manager.get_recovery_stats()
        success_rate = stats["success_rate"]

        # 成功率应该大于80%
        self.assertGreaterEqual(success_rate, 0.8)

    def test_concurrent_error_handling(self):
        """测试并发错误处理"""
        import threading

        error_counts = {"success": 0, "failure": 0}
        lock = threading.Lock()

        def worker():
            try:
                if error_counts["success"] < 5:
                    with lock:
                        error_counts["success"] += 1
                    return "success"
                else:
                    raise Exception("模拟错误")
            except Exception as e:
                with lock:
                    error_counts["failure"] += 1
                error_logger.log_error(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有线程都完成了
        self.assertEqual(error_counts["success"] + error_counts["failure"], 10)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def setUp(self):
        """设置测试环境"""
        clear_error_history()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)
        self.original_cwd = os.getcwd()
        os.chdir(self.test_path)

        # 创建测试目录
        (self.test_path / "data").mkdir()
        (self.test_path / "models").mkdir()
        (self.test_path / "config").mkdir()

    def tearDown(self):
        """清理测试环境"""
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_full_recovery_workflow(self):
        """测试完整恢复工作流"""
        # 1. 创建备份
        config = BackupConfig(
            backup_dir=str(self.test_path / "backups"),
            daily_backup_dir=str(self.test_path / "backups" / "daily"),
            manual_backup_dir=str(self.test_path / "backups" / "manual"),
            compression_enabled=False
        )
        manager = BackupManager(config)

        # 创建测试数据
        (self.test_path / "data" / "important.csv").write_text("key,value\n1,test")

        # 创建备份
        backup_result = manager.create_backup(backup_type="daily")
        self.assertEqual(backup_result["status"], "success")
        backup_id = backup_result["backup_id"]

        # 2. 模拟数据损坏
        (self.test_path / "data" / "important.csv").write_text("corrupted")

        # 3. 使用恢复器恢复
        restorer = BackupRestorer(str(self.test_path / "backups"))
        restore_result = restorer.restore(backup_id=backup_id, create_pre_backup=True)

        self.assertEqual(restore_result["status"], "success")

        # 4. 验证数据已恢复
        content = (self.test_path / "data" / "important.csv").read_text()
        self.assertEqual(content, "key,value\n1,test")

    def test_error_handling_with_backup(self):
        """测试带备份的错误处理"""
        config = BackupConfig(
            backup_dir=str(self.test_path / "backups"),
            daily_backup_dir=str(self.test_path / "backups" / "daily"),
            manual_backup_dir=str(self.test_path / "backups" / "manual"),
            compression_enabled=False
        )
        manager = BackupManager(config)

        @handle_errors(fallback_value=None)
        def risky_operation_with_backup():
            # 先创建备份
            manager.create_backup(backup_type="manual", backup_name="pre_operation")
            # 然后执行可能失败的操作
            raise Exception("操作失败")

        result = risky_operation_with_backup()
        self.assertIsNone(result)

        # 验证备份已创建
        backups = manager.list_backups("manual")
        self.assertGreater(len(backups), 0)


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestBackupSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestBackupRestorer))
    suite.addTests(loader.loadTestsFromTestCase(TestFaultScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemStability))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 生成测试报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "success": result.wasSuccessful()
    }

    # 保存测试报告
    report_path = Path("logs/fault_recovery_test_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n测试报告已保存到: {report_path}")
    print(f"测试结果: {'通过' if result.wasSuccessful() else '失败'}")
    print(f"运行测试: {result.testsRun}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
