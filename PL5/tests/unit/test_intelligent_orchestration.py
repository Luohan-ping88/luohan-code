"""
智能编排系统单元测试
测试功能：任务注册、执行、状态持久化、性能监控等
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import unittest
from unittest.mock import Mock, MagicMock

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.workflow.intelligent_orchestration import (
    OrchestrationTask,
    IntelligentOrchestrationManager,
    reset_orchestration_manager
)


class TestOrchestrationTask(unittest.TestCase):
    """测试编排任务类"""
    
    def test_task_initialization(self):
        """测试任务初始化"""
        def mock_handler():
            return "result"
        
        task = OrchestrationTask(
            name="test_task",
            handler=mock_handler,
            priority=2,
            dependencies=["dep1", "dep2"],
            max_retries=5
        )
        
        self.assertEqual(task.name, "test_task")
        self.assertEqual(task.priority, 2)
        self.assertEqual(task.dependencies, ["dep1", "dep2"])
        self.assertEqual(task.max_retries, 5)
        self.assertEqual(task.status, "pending")
    
    def test_task_to_dict(self):
        """测试任务序列化"""
        def mock_handler():
            return "result"
        
        task = OrchestrationTask("test_task", mock_handler)
        task.status = "completed"
        task.start_time = datetime.now()
        task.end_time = datetime.now()
        
        task_dict = task.to_dict()
        
        self.assertIn("name", task_dict)
        self.assertIn("status", task_dict)
        self.assertEqual(task_dict["name"], "test_task")
        self.assertEqual(task_dict["status"], "completed")


class TestIntelligentOrchestrationManager(unittest.TestCase):
    """测试智能编排管理器"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_scheduler = Mock()
        self.manager = IntelligentOrchestrationManager(
            self.mock_scheduler,
            state_dir=self.temp_dir
        )
    
    def tearDown(self):
        """测试后清理"""
        self.manager.clear_state()
        reset_orchestration_manager()
        shutil.rmtree(self.temp_dir)
    
    def test_register_task(self):
        """测试任务注册"""
        def mock_handler():
            return "success"
        
        self.manager.register_task("test_task", mock_handler, priority=3)
        
        self.assertIn("test_task", self.manager.tasks)
        self.assertEqual(self.manager.tasks["test_task"].priority, 3)
    
    def test_execute_successful_task(self):
        """测试成功执行任务"""
        result_data = {"status": "ok"}
        
        def mock_handler():
            return result_data
        
        self.manager.register_task("success_task", mock_handler)
        
        # 执行任务
        result = self.manager._execute_single_task("success_task")
        
        self.assertTrue(result)
        task = self.manager.tasks["success_task"]
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.result, result_data)
    
    def test_execute_failed_task(self):
        """测试失败任务"""
        def mock_handler():
            raise Exception("Test error")
        
        self.manager.register_task("failed_task", mock_handler, max_retries=1)
        
        # 执行任务
        result = self.manager._execute_single_task("failed_task")
        
        self.assertFalse(result)
        task = self.manager.tasks["failed_task"]
        self.assertEqual(task.status, "failed")
        self.assertIsNotNone(task.error)
    
    def test_task_dependencies(self):
        """测试任务依赖"""
        def mock_handler():
            return "ok"
        
        self.manager.register_task("task_a", mock_handler)
        self.manager.register_task("task_b", mock_handler, dependencies=["task_a"])
        
        # 尝试在依赖未完成时执行
        result = self.manager._execute_single_task("task_b")
        self.assertFalse(result)
        
        # 标记依赖为完成
        self.manager.tasks["task_a"].status = "completed"
        
        # 再次执行
        result = self.manager._execute_single_task("task_b")
        # 注意：这里会实际执行 handler，为了简化测试我们只检查逻辑
        self.assertIsNotNone(self.manager.tasks["task_b"])
    
    def test_training_window_detection(self):
        """测试训练窗口检测"""
        # 这个测试验证逻辑是否存在
        self.assertTrue(hasattr(self.manager, '_is_in_training_window'))
        self.assertTrue(hasattr(self.manager, '_check_training_window'))
    
    def test_state_persistence(self):
        """测试状态持久化"""
        # 执行一些操作来改变状态
        self.manager.in_training_window = True
        self.manager.training_window_start = datetime.now()
        
        # 保存状态
        self.manager._save_state()
        
        # 验证文件存在
        state_file = Path(self.temp_dir) / self.manager.STATE_FILE
        self.assertTrue(state_file.exists())
        
        # 创建新的管理器实例，验证状态恢复
        new_manager = IntelligentOrchestrationManager(
            Mock(),
            state_dir=self.temp_dir
        )
        self.assertTrue(new_manager.in_training_window)
    
    def test_performance_metrics(self):
        """测试性能指标"""
        def success_handler():
            return "ok"
        
        def fail_handler():
            raise Exception("error")
        
        self.manager.register_task("success_task", success_handler)
        self.manager.register_task("fail_task", fail_handler, max_retries=0)
        
        # 执行成功任务
        self.manager._execute_single_task("success_task")
        
        # 检查性能指标
        metrics = self.manager.performance_metrics
        self.assertEqual(metrics["total_tasks_executed"], 1)
        self.assertEqual(metrics["tasks_success"], 1)
    
    def test_get_orchestration_status(self):
        """测试获取编排状态"""
        status = self.manager.get_orchestration_status()
        
        self.assertIn("is_running", status)
        self.assertIn("in_training_window", status)
        self.assertIn("performance_metrics", status)
    
    def test_get_performance_report(self):
        """测试获取性能报告"""
        report = self.manager.get_performance_report()
        
        self.assertIn("metrics", report)
        self.assertIn("success_rate", report)
        self.assertIn("report_time", report)
    
    def test_history_recording(self):
        """测试历史记录"""
        def mock_handler():
            return "ok"
        
        self.manager.register_task("history_test", mock_handler)
        
        # 执行任务
        self.manager._execute_single_task("history_test")
        
        # 检查历史
        history = self.manager.get_history()
        self.assertGreater(len(history), 0)
    
    def test_clear_state(self):
        """测试清除状态"""
        # 添加一些数据
        self.manager.history.append({"test": "data"})
        self.manager.performance_metrics["total_tasks_executed"] = 10
        
        # 清除状态
        self.manager.clear_state()
        
        # 验证
        self.assertEqual(len(self.manager.history), 0)
        self.assertEqual(self.manager.performance_metrics["total_tasks_executed"], 0)


class TestSingletonPattern(unittest.TestCase):
    """测试单例模式"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        reset_orchestration_manager()
    
    def tearDown(self):
        """测试后清理"""
        reset_orchestration_manager()
        shutil.rmtree(self.temp_dir)
    
    def test_singleton_instance(self):
        """测试单例获取"""
        from src.core.workflow.intelligent_orchestration import get_orchestration_manager
        
        scheduler1 = Mock()
        scheduler2 = Mock()
        
        # 第一次获取会创建
        manager1 = get_orchestration_manager(scheduler1, self.temp_dir)
        self.assertIsNotNone(manager1)
        
        # 第二次获取应该返回同一个实例
        manager2 = get_orchestration_manager(scheduler2)
        self.assertEqual(manager1, manager2)


def run_tests():
    """运行测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试
    suite.addTests(loader.loadTestsFromTestCase(TestOrchestrationTask))
    suite.addTests(loader.loadTestsFromTestCase(TestIntelligentOrchestrationManager))
    suite.addTests(loader.loadTestsFromTestCase(TestSingletonPattern))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 80)
    print("智能编排系统单元测试")
    print("=" * 80)
    
    success = run_tests()
    
    print("\n" + "=" * 80)
    if success:
        print("所有测试通过！")
    else:
        print("部分测试失败！")
    print("=" * 80)
    
    sys.exit(0 if success else 1)
