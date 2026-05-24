#!/usr/bin/env python
"""
系统性能监控脚本
在后台监控CPU、内存、磁盘使用情况
"""

import psutil
import time
import json
from datetime import datetime
from pathlib import Path

class SystemMonitor:
    def __init__(self, log_file='logs/system_monitor.json'):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.metrics = []

    def get_cpu_usage(self):
        """获取CPU使用率"""
        return psutil.cpu_percent(interval=1, percpu=False)

    def get_memory_usage(self):
        """获取内存使用情况"""
        mem = psutil.virtual_memory()
        return {
            'total': mem.total,
            'available': mem.available,
            'percent': mem.percent,
            'used': mem.used,
            'free': mem.free
        }

    def get_disk_usage(self, path='/'):
        """获取磁盘使用情况"""
        disk = psutil.disk_usage(path)
        return {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': disk.percent
        }

    def get_network_io(self):
        """获取网络IO统计"""
        net = psutil.net_io_counters()
        return {
            'bytes_sent': net.bytes_sent,
            'bytes_recv': net.bytes_recv,
            'packets_sent': net.packets_sent,
            'packets_recv': net.packets_recv
        }

    def collect_metrics(self):
        """收集当前指标"""
        timestamp = datetime.now().isoformat()
        metrics = {
            'timestamp': timestamp,
            'cpu_percent': self.get_cpu_usage(),
            'memory': self.get_memory_usage(),
            'disk': self.get_disk_usage('/'),
            'network': self.get_network_io()
        }
        self.metrics.append(metrics)
        return metrics

    def save_metrics(self):
        """保存指标到文件"""
        with open(self.log_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)

    def monitor(self, interval=60, duration=None):
        """执行监控"""
        start_time = time.time()
        iteration = 0

        print(f"开始系统监控 (每 {interval} 秒采样)...")

        while True:
            metrics = self.collect_metrics()
            iteration += 1

            print(f"[{metrics['timestamp']}] "
                  f"CPU: {metrics['cpu_percent']:.1f}% | "
                  f"内存: {metrics['memory']['percent']:.1f}% | "
                  f"磁盘: {metrics['disk']['percent']:.1f}%")

            # 检查是否超过指定时长
            if duration and (time.time() - start_time) >= duration:
                break

            time.sleep(interval)

        self.save_metrics()
        print(f"监控完成，共采集 {len(self.metrics)} 条记录")

if __name__ == '__main__':
    import sys

    monitor = SystemMonitor()

    if len(sys.argv) > 1:
        interval = int(sys.argv[1])
    else:
        interval = 60  # 默认60秒

    monitor.monitor(interval=interval)
