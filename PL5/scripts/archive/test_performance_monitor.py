#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试性能监控模块的增强功能
"""

import time
from src.core.monitoring.performance_monitor import get_performance_monitor, start_performance_monitoring, stop_performance_monitoring

print("测试性能监控模块的增强功能")
print("=" * 60)

# 启动性能监控
print("1. 启动性能监控...")
start_performance_monitoring()

# 等待一段时间收集数据
print("2. 等待10秒收集性能数据...")
time.sleep(10)

# 获取性能监控器实例
monitor = get_performance_monitor()

# 测试性能摘要
print("3. 测试性能摘要...")
summary = monitor.get_performance_summary()
print(f"   样本数: {summary.get('sample_count', 0)}")
print(f"   CPU平均使用率: {summary.get('cpu', {}).get('avg', 0):.1f}%")
print(f"   内存平均使用率: {summary.get('memory', {}).get('avg', 0):.1f}%")
print(f"   磁盘平均使用率: {summary.get('disk', {}).get('avg', 0):.1f}%")
print(f"   基线: {summary.get('baseline', {})}")
print(f"   异常计数: {summary.get('anomaly_count', 0)}")

# 测试性能基线
print("4. 测试性能基线...")
print(f"   当前基线: {monitor.get_baseline()}")

# 尝试建立基线
print("5. 尝试建立基线...")
monitor.establish_baseline()
print(f"   建立后的基线: {monitor.get_baseline()}")

# 测试异常检测
print("6. 测试异常检测...")
anomalies = monitor.detect_anomalies()
print(f"   检测到的异常: {anomalies}")

# 测试异常历史
print("7. 测试异常历史...")
anomaly_history = monitor.get_anomaly_history()
print(f"   异常历史数量: {len(anomaly_history)}")

# 测试阈值设置
print("8. 测试阈值设置...")
print(f"   当前阈值: {monitor.thresholds}")
new_thresholds = {'cpu_percent': 75, 'memory_percent': 80, 'disk_percent': 85}
monitor.set_thresholds(new_thresholds)
print(f"   新阈值: {monitor.thresholds}")

# 测试历史数据
print("9. 测试历史数据...")
history = monitor.get_history(limit=5)
print(f"   历史数据数量: {len(history)}")
if history:
    print(f"   最新数据: {history[-1]['timestamp']}")

# 停止性能监控
print("10. 停止性能监控...")
stop_performance_monitoring()

print("=" * 60)
print("性能监控模块测试完成")