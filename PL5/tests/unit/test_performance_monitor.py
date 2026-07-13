"""性能监控模块测试

测试PL5性能监控系统的功能和可靠性。
"""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.monitoring.performance_monitor import (
    PerformanceMonitor, PerformanceTracker,
    get_performance_monitor, get_performance_tracker,
    start_performance_monitoring, stop_performance_monitoring,
    track_performance
)


class TestPerformanceMonitor:
    """测试PerformanceMonitor类"""
    
    def test_initialization(self):
        """测试性能监控器初始化"""
        monitor = PerformanceMonitor(log_interval=10)
        assert monitor.log_interval == 10
        assert monitor.is_running is False
        assert monitor.monitor_thread is None
        assert len(monitor.performance_history) == 0
    
    def test_start_stop(self):
        """测试启动和停止性能监控"""
        monitor = PerformanceMonitor(log_interval=0.1)
        monitor.start()
        assert monitor.is_running is True
        assert monitor.monitor_thread is not None
        
        # 等待一下让监控线程运行
        time.sleep(0.2)
        
        monitor.stop()
        assert monitor.is_running is False
    
    def test_collect_metrics(self):
        """测试收集性能指标"""
        monitor = PerformanceMonitor()
        metrics = monitor.collect_metrics()
        
        assert 'timestamp' in metrics
        assert 'system' in metrics
        assert 'process' in metrics
        
        system_metrics = metrics['system']
        assert 'cpu_percent' in system_metrics
        assert 'memory_percent' in system_metrics
        assert 'disk_percent' in system_metrics
        
        process_metrics = metrics['process']
        assert 'cpu_percent' in process_metrics
        assert 'memory_mb' in process_metrics
        assert 'threads' in process_metrics
    
    def test_establish_baseline(self):
        """测试建立性能基线"""
        monitor = PerformanceMonitor()
        
        # 模拟性能历史数据
        for _ in range(30):
            metrics = monitor.collect_metrics()
            monitor.performance_history.append(metrics)
        
        monitor.establish_baseline()
        assert 'cpu_percent' in monitor.baseline_metrics
        assert 'memory_percent' in monitor.baseline_metrics
        assert 'disk_percent' in monitor.baseline_metrics
    
    def test_update_baseline(self):
        """测试更新性能基线"""
        monitor = PerformanceMonitor()
        
        # 模拟性能历史数据
        for _ in range(60):
            metrics = monitor.collect_metrics()
            monitor.performance_history.append(metrics)
        
        monitor.establish_baseline()
        initial_baseline = monitor.baseline_metrics.copy()
        
        # 再次添加一些数据
        for _ in range(10):
            metrics = monitor.collect_metrics()
            monitor.performance_history.append(metrics)
        
        monitor.update_baseline()
        updated_baseline = monitor.baseline_metrics
        
        # 基线应该有变化
        assert initial_baseline != updated_baseline
    
    def test_detect_anomalies(self):
        """测试检测性能异常"""
        monitor = PerformanceMonitor()
        
        # 模拟正常性能数据
        for _ in range(20):
            metrics = monitor.collect_metrics()
            # 确保CPU使用率正常
            if 'system' in metrics:
                metrics['system']['cpu_percent'] = 30
                metrics['system']['memory_percent'] = 40
                metrics['system']['disk_percent'] = 50
            monitor.performance_history.append(metrics)
        
        # 建立基线
        monitor.establish_baseline()
        
        # 模拟异常数据
        anomaly_metrics = monitor.collect_metrics()
        if 'system' in anomaly_metrics:
            anomaly_metrics['system']['cpu_percent'] = 90  # 超过阈值
            anomaly_metrics['system']['memory_percent'] = 95  # 超过阈值
            anomaly_metrics['system']['disk_percent'] = 95  # 超过阈值
        monitor.performance_history.append(anomaly_metrics)
        
        # 检测异常
        anomalies = monitor.detect_anomalies()
        assert len(anomalies) > 0
    
    def test_get_performance_summary(self):
        """测试获取性能摘要"""
        monitor = PerformanceMonitor()
        
        # 添加一些性能数据
        for _ in range(10):
            metrics = monitor.collect_metrics()
            monitor.performance_history.append(metrics)
        
        summary = monitor.get_performance_summary()
        assert 'sample_count' in summary
        assert 'cpu' in summary
        assert 'memory' in summary
        assert 'disk' in summary
        assert summary['sample_count'] == 10
    
    def test_set_thresholds(self):
        """测试设置性能告警阈值"""
        monitor = PerformanceMonitor()
        new_thresholds = {
            'cpu_percent': 70,
            'memory_percent': 80,
            'disk_percent': 85
        }
        monitor.set_thresholds(new_thresholds)
        assert monitor.thresholds['cpu_percent'] == 70
        assert monitor.thresholds['memory_percent'] == 80
        assert monitor.thresholds['disk_percent'] == 85
    
    def test_alert_configuration(self):
        """测试告警配置"""
        monitor = PerformanceMonitor()
        
        # 测试设置告警配置
        new_config = {
            'enabled': True,
            'email': {
                'enabled': True,
                'smtp_server': 'smtp.test.com',
                'smtp_port': 587,
                'username': 'test',
                'password': 'testpass',
                'from_email': 'alerts@test.com',
                'to_emails': ['admin@test.com']
            }
        }
        monitor.set_alert_config(new_config)
        assert monitor.alert_config['enabled'] is True
        assert monitor.alert_config['email']['enabled'] is True
        assert monitor.alert_config['email']['smtp_server'] == 'smtp.test.com'
    
    def test_alert_callback(self):
        """测试告警回调"""
        monitor = PerformanceMonitor()
        callback_called = False
        
        def test_callback(alert):
            nonlocal callback_called
            callback_called = True
        
        monitor.add_alert_callback(test_callback)
        assert len(monitor.alert_config['callbacks']) == 1
        
        # 触发一个告警
        test_alert = {
            'type': 'test_alert',
            'timestamp': time.time()
        }
        monitor.trigger_alert(test_alert)
        assert callback_called is True
    
    def test_get_alert_history(self):
        """测试获取告警历史"""
        monitor = PerformanceMonitor()
        
        # 添加一些告警
        for i in range(5):
            alert = {
                'type': f'test_alert_{i}',
                'timestamp': time.time() + i
            }
            monitor.trigger_alert(alert)
        
        alert_history = monitor.get_alert_history(limit=3)
        assert len(alert_history) == 3
    
    def test_clear_alert_history(self):
        """测试清空告警历史"""
        monitor = PerformanceMonitor()
        
        # 添加一些告警
        for i in range(5):
            alert = {
                'type': f'test_alert_{i}',
                'timestamp': time.time() + i
            }
            monitor.trigger_alert(alert)
        
        assert len(monitor.alert_history) == 5
        monitor.clear_alert_history()
        assert len(monitor.alert_history) == 0


class TestPerformanceTracker:
    """测试PerformanceTracker类"""
    
    def test_initialization(self):
        """测试性能跟踪器初始化"""
        tracker = PerformanceTracker()
        assert tracker.timings == {}
    
    def test_track_decorator(self):
        """测试性能跟踪装饰器"""
        tracker = PerformanceTracker()
        
        @tracker.track
        def test_function():
            time.sleep(0.1)
            return "test"
        
        result = test_function()
        assert result == "test"
        assert "test_function" in tracker.timings
        assert len(tracker.timings["test_function"]) == 1
    
    def test_get_function_stats(self):
        """测试获取函数执行统计信息"""
        tracker = PerformanceTracker()
        
        @tracker.track
        def test_function():
            time.sleep(0.05)
            return "test"
        
        # 调用函数多次
        for _ in range(5):
            test_function()
        
        stats = tracker.get_function_stats("test_function")
        assert stats['calls'] == 5
        assert stats['avg_execution_time'] > 0
        assert stats['max_execution_time'] > 0
        assert stats['min_execution_time'] > 0
    
    def test_get_all_stats(self):
        """测试获取所有函数的统计信息"""
        tracker = PerformanceTracker()
        
        @tracker.track
        def function1():
            time.sleep(0.01)
            return "test1"
        
        @tracker.track
        def function2():
            time.sleep(0.02)
            return "test2"
        
        function1()
        function2()
        
        all_stats = tracker.get_all_stats()
        assert "function1" in all_stats
        assert "function2" in all_stats


class TestGlobalFunctions:
    """测试全局函数"""
    
    def test_get_performance_monitor(self):
        """测试获取全局性能监控器"""
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()
        assert monitor1 is monitor2  # 应该返回同一个实例
    
    def test_get_performance_tracker(self):
        """测试获取全局性能跟踪器"""
        tracker1 = get_performance_tracker()
        tracker2 = get_performance_tracker()
        assert tracker1 is tracker2  # 应该返回同一个实例
    
    def test_start_stop_monitoring(self):
        """测试启动和停止全局性能监控"""
        start_performance_monitoring()
        monitor = get_performance_monitor()
        assert monitor.is_running is True
        
        stop_performance_monitoring()
        assert monitor.is_running is False
    
    def test_track_performance_decorator(self):
        """测试track_performance装饰器"""
        @track_performance
        def decorated_function():
            time.sleep(0.01)
            return "test"
        
        result = decorated_function()
        assert result == "test"


if __name__ == "__main__":
    pytest.main([__file__])
