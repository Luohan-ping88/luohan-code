#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统可靠性和故障恢复测试
验证系统的可靠性和故障恢复能力
"""

import os
import sys
import time
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.backup.backup_manager import create_backup, restore_backup, list_backups, get_latest_backup
from src.core.recovery.failure_recovery import handle_failure, auto_retry
from src.core.monitoring.alerting import check_alerts
from src.core.monitoring.health_check import check_health, get_health_summary
from src.core.automation.scheduler import PL5AutomationScheduler


class TestSystemReliability(unittest.TestCase):
    """系统可靠性测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # 模拟必要的目录结构
        (self.test_dir / 'models').mkdir(exist_ok=True)
        (self.test_dir / 'data').mkdir(exist_ok=True)
        (self.test_dir / 'config').mkdir(exist_ok=True)
        (self.test_dir / 'logs').mkdir(exist_ok=True)
        
        # 创建测试文件
        with open(self.test_dir / 'models' / 'test_model.pkl', 'w') as f:
            f.write('test model')
        
        with open(self.test_dir / 'data' / 'test_data.csv', 'w') as f:
            f.write('period,value\n1,10\n2,20')
        
        # 保存原始工作目录
        self.original_cwd = os.getcwd()
        # 切换到测试目录
        os.chdir(self.test_dir)
    
    def tearDown(self):
        """清理测试环境"""
        # 切回原始工作目录
        os.chdir(self.original_cwd)
        # 清理临时目录
        self.temp_dir.cleanup()
    
    def test_backup_and_restore(self):
        """测试备份和恢复功能"""
        # 创建备份
        backup_result = create_backup('test_backup')
        self.assertEqual(backup_result['status'], 'success')
        
        # 验证备份创建成功
        backups = list_backups()
        self.assertGreater(len(backups), 0)
        
        # 获取最新备份
        latest_backup = get_latest_backup()
        self.assertIsNotNone(latest_backup)
        
        # 修改测试文件
        with open('models/test_model.pkl', 'w') as f:
            f.write('modified model')
        
        # 恢复备份
        restore_result = restore_backup(latest_backup['backup_id'])
        self.assertEqual(restore_result['status'], 'success')
        
        # 验证文件已恢复
        with open('models/test_model.pkl', 'r') as f:
            content = f.read()
        self.assertEqual(content, 'test model')
    
    def test_auto_retry(self):
        """测试自动重试机制"""
        # 模拟一个会失败的函数
        failure_count = 0
        
        def flaky_function():
            nonlocal failure_count
            failure_count += 1
            if failure_count < 3:
                raise Exception("模拟失败")
            return "成功"
        
        # 使用自动重试
        result = auto_retry(flaky_function)
        self.assertEqual(result, "成功")
        self.assertEqual(failure_count, 3)
    
    def test_failure_handling(self):
        """测试故障处理机制"""
        # 模拟一个故障
        try:
            handle_failure('data_collection_failure', Exception('测试故障'), {
                'collector': Mock()
            })
            # 测试应该通过，故障处理不应该抛出异常
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"故障处理失败: {str(e)}")
    
    def test_alerting(self):
        """测试告警机制"""
        # 模拟高CPU使用率
        metrics = {
            'system': {
                'cpu_percent': 95,
                'memory_percent': 80,
                'disk_percent': 70
            }
        }
        
        # 检查告警
        alerts = check_alerts(metrics)
        self.assertGreater(len(alerts), 0)
        
        # 验证告警级别
        critical_alerts = [alert for alert in alerts if alert.level == 'critical']
        self.assertGreater(len(critical_alerts), 0)
    
    def test_health_check(self):
        """测试健康检查功能"""
        # 执行健康检查
        health_result = check_health()
        self.assertIn('overall_status', health_result)
        
        # 获取健康状态摘要
        health_summary = get_health_summary()
        self.assertIn('status', health_summary)
    
    def test_scheduler_reliability(self):
        """测试调度器可靠性"""
        # 创建调度器实例
        scheduler = PL5AutomationScheduler()
        
        # 测试启动和停止
        scheduler.start()
        self.assertTrue(scheduler.is_running)
        
        # 等待一段时间，确保调度器正常运行
        time.sleep(1)
        
        # 测试停止
        scheduler.stop()
        self.assertFalse(scheduler.is_running)
    
    def test_system_integration(self):
        """测试系统集成"""
        # 测试完整的系统流程
        
        # 1. 创建备份
        backup_result = create_backup('integration_test')
        self.assertEqual(backup_result['status'], 'success')
        
        # 2. 执行健康检查
        health_result = check_health()
        self.assertIn('overall_status', health_result)
        
        # 3. 测试故障处理
        try:
            handle_failure('test_failure', Exception('集成测试故障'))
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"集成测试失败: {str(e)}")


class TestFaultRecovery(unittest.TestCase):
    """故障恢复测试"""
    
    def test_data_collection_failure_recovery(self):
        """测试数据采集故障恢复"""
        # 模拟数据采集器
        mock_collector = Mock()
        mock_collector.update_data.side_effect = [
            Exception("第一次失败"),
            Exception("第二次失败"),
            "成功数据"
        ]
        
        # 处理数据采集故障
        handle_failure('data_collection_failure', Exception('数据采集失败'), {
            'collector': mock_collector
        })
        
        # 验证数据采集器被调用了3次
        self.assertEqual(mock_collector.update_data.call_count, 3)
    
    def test_model_training_failure_recovery(self):
        """测试模型训练故障恢复"""
        # 首先创建一个备份
        backup_result = create_backup('model_backup')
        self.assertEqual(backup_result['status'], 'success')
        
        # 处理模型训练故障
        handle_failure('model_training_failure', Exception('模型训练失败'))
        # 测试应该通过，故障处理不应该抛出异常
        self.assertTrue(True)
    
    def test_system_crash_recovery(self):
        """测试系统崩溃恢复"""
        # 处理系统崩溃
        handle_failure('system_crash', Exception('系统崩溃'), {
            'test_context': '测试崩溃恢复'
        })
        # 测试应该通过，故障处理不应该抛出异常
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
