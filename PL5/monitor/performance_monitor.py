#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5智能分析系统 - 性能监控模块
监控系统性能指标，包括CPU、内存、磁盘、网络等
"""

import os
import psutil
import time
import json
from datetime import datetime
from pathlib import Path

from src.core.utils import logger

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else Path('logs/performance')
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # 性能数据历史
        self.metrics_history = []
        self.max_history = 1000  # 最大历史记录数
        
        # 性能阈值
        self.thresholds = {
            'cpu_usage': 80,
            'memory_usage': 80,
            'disk_usage': 90,
            'network_sent': 10 * 1024 * 1024,  # 10MB/s
            'network_recv': 10 * 1024 * 1024   # 10MB/s
        }
        
        # 网络流量基线
        self.network_baseline = {
            'sent': 0,
            'recv': 0
        }
        self.last_network_check = time.time()
        
        # 初始化网络基线
        self._init_network_baseline()
    
    def _init_network_baseline(self):
        """初始化网络流量基线"""
        try:
            net_io = psutil.net_io_counters()
            self.network_baseline['sent'] = net_io.bytes_sent
            self.network_baseline['recv'] = net_io.bytes_recv
            self.last_network_check = time.time()
        except Exception as e:
            logger.warning(f"初始化网络基线失败: {e}")
    
    def get_metrics(self):
        """获取性能指标"""
        metrics = {}
        
        try:
            # CPU 使用率
            metrics['cpu_usage'] = psutil.cpu_percent(interval=1)
            
            # 内存使用
            memory = psutil.virtual_memory()
            metrics['memory_usage'] = memory.percent
            metrics['memory_used'] = memory.used
            metrics['memory_total'] = memory.total
            
            # 磁盘使用
            disk = psutil.disk_usage('/')
            metrics['disk_usage'] = disk.percent
            metrics['disk_used'] = disk.used
            metrics['disk_total'] = disk.total
            
            # 网络流量
            net_metrics = self._get_network_metrics()
            metrics.update(net_metrics)
            
            # 系统负载
            metrics['load_avg'] = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            # 进程数
            metrics['process_count'] = len(psutil.pids())
            
            # 时间戳
            metrics['timestamp'] = datetime.now().isoformat()
            
            # 保存到历史
            self._save_metrics(metrics)
            
        except Exception as e:
            logger.error(f"获取性能指标失败: {e}")
        
        return metrics
    
    def _get_network_metrics(self):
        """获取网络流量指标"""
        net_metrics = {
            'network_sent': 0,
            'network_recv': 0,
            'network_sent_rate': 0,
            'network_recv_rate': 0
        }
        
        try:
            net_io = psutil.net_io_counters()
            current_time = time.time()
            time_diff = current_time - self.last_network_check
            
            if time_diff > 0:
                # 计算速率
                net_metrics['network_sent'] = net_io.bytes_sent
                net_metrics['network_recv'] = net_io.bytes_recv
                net_metrics['network_sent_rate'] = (net_io.bytes_sent - self.network_baseline['sent']) / time_diff
                net_metrics['network_recv_rate'] = (net_io.bytes_recv - self.network_baseline['recv']) / time_diff
                
                # 更新基线
                self.network_baseline['sent'] = net_io.bytes_sent
                self.network_baseline['recv'] = net_io.bytes_recv
                self.last_network_check = current_time
                
        except Exception as e:
            logger.warning(f"获取网络指标失败: {e}")
        
        return net_metrics
    
    def _save_metrics(self, metrics):
        """保存性能指标"""
        try:
            # 添加到历史
            self.metrics_history.append(metrics)
            
            # 限制历史记录数
            if len(self.metrics_history) > self.max_history:
                self.metrics_history = self.metrics_history[-self.max_history:]
            
            # 每10次保存一次到文件
            if len(self.metrics_history) % 10 == 0:
                self._save_to_file()
                
        except Exception as e:
            logger.error(f"保存性能指标失败: {e}")
    
    def _save_to_file(self):
        """保存到文件"""
        try:
            date_str = datetime.now().strftime('%Y%m%d')
            metrics_file = self.data_dir / f'performance_{date_str}.jsonl'
            
            # 追加模式写入
            with open(metrics_file, 'a', encoding='utf-8') as f:
                for metric in self.metrics_history[-10:]:  # 只保存最近10条
                    f.write(json.dumps(metric, ensure_ascii=False) + '\n')
                    
        except Exception as e:
            logger.error(f"保存性能数据到文件失败: {e}")
    
    def get_summary(self, hours=24):
        """获取性能摘要"""
        summary = {
            'cpu': {
                'average': 0,
                'max': 0,
                'min': 100
            },
            'memory': {
                'average': 0,
                'max': 0,
                'min': 100
            },
            'disk': {
                'average': 0,
                'max': 0,
                'min': 100
            },
            'network': {
                'sent_avg': 0,
                'recv_avg': 0
            },
            'samples': 0
        }
        
        try:
            # 过滤指定时间范围内的数据
            cutoff_time = datetime.now().timestamp() - (hours * 3600)
            recent_metrics = []
            
            for metric in self.metrics_history:
                metric_time = datetime.fromisoformat(metric['timestamp']).timestamp()
                if metric_time >= cutoff_time:
                    recent_metrics.append(metric)
            
            if recent_metrics:
                # 计算CPU摘要
                cpu_values = [m.get('cpu_usage', 0) for m in recent_metrics]
                summary['cpu']['average'] = sum(cpu_values) / len(cpu_values)
                summary['cpu']['max'] = max(cpu_values)
                summary['cpu']['min'] = min(cpu_values)
                
                # 计算内存摘要
                memory_values = [m.get('memory_usage', 0) for m in recent_metrics]
                summary['memory']['average'] = sum(memory_values) / len(memory_values)
                summary['memory']['max'] = max(memory_values)
                summary['memory']['min'] = min(memory_values)
                
                # 计算磁盘摘要
                disk_values = [m.get('disk_usage', 0) for m in recent_metrics]
                summary['disk']['average'] = sum(disk_values) / len(disk_values)
                summary['disk']['max'] = max(disk_values)
                summary['disk']['min'] = min(disk_values)
                
                # 计算网络摘要
                sent_values = [m.get('network_sent_rate', 0) for m in recent_metrics]
                recv_values = [m.get('network_recv_rate', 0) for m in recent_metrics]
                summary['network']['sent_avg'] = sum(sent_values) / len(sent_values)
                summary['network']['recv_avg'] = sum(recv_values) / len(recv_values)
                
                summary['samples'] = len(recent_metrics)
                
        except Exception as e:
            logger.error(f"获取性能摘要失败: {e}")
        
        return summary
    
    def check_thresholds(self):
        """检查性能阈值"""
        alerts = []
        metrics = self.get_metrics()
        
        try:
            # 检查CPU
            cpu_usage = metrics.get('cpu_usage', 0)
            if cpu_usage > self.thresholds['cpu_usage']:
                alerts.append({
                    'level': 'WARNING',
                    'metric': 'cpu_usage',
                    'value': cpu_usage,
                    'threshold': self.thresholds['cpu_usage'],
                    'message': f"CPU使用率过高: {cpu_usage}%",
                    'timestamp': datetime.now().isoformat()
                })
            
            # 检查内存
            memory_usage = metrics.get('memory_usage', 0)
            if memory_usage > self.thresholds['memory_usage']:
                alerts.append({
                    'level': 'WARNING',
                    'metric': 'memory_usage',
                    'value': memory_usage,
                    'threshold': self.thresholds['memory_usage'],
                    'message': f"内存使用率过高: {memory_usage}%",
                    'timestamp': datetime.now().isoformat()
                })
            
            # 检查磁盘
            disk_usage = metrics.get('disk_usage', 0)
            if disk_usage > self.thresholds['disk_usage']:
                alerts.append({
                    'level': 'CRITICAL',
                    'metric': 'disk_usage',
                    'value': disk_usage,
                    'threshold': self.thresholds['disk_usage'],
                    'message': f"磁盘使用率过高: {disk_usage}%",
                    'timestamp': datetime.now().isoformat()
                })
            
            # 检查网络发送
            network_sent = metrics.get('network_sent_rate', 0)
            if network_sent > self.thresholds['network_sent']:
                alerts.append({
                    'level': 'WARNING',
                    'metric': 'network_sent',
                    'value': network_sent,
                    'threshold': self.thresholds['network_sent'],
                    'message': f"网络发送速率过高: {network_sent / 1024 / 1024:.2f}MB/s",
                    'timestamp': datetime.now().isoformat()
                })
            
            # 检查网络接收
            network_recv = metrics.get('network_recv_rate', 0)
            if network_recv > self.thresholds['network_recv']:
                alerts.append({
                    'level': 'WARNING',
                    'metric': 'network_recv',
                    'value': network_recv,
                    'threshold': self.thresholds['network_recv'],
                    'message': f"网络接收速率过高: {network_recv / 1024 / 1024:.2f}MB/s",
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"检查性能阈值失败: {e}")
        
        return alerts
    
    def get_top_processes(self, limit=5):
        """获取占用资源最多的进程"""
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    if proc_info['cpu_percent'] > 0 or proc_info['memory_percent'] > 0:
                        processes.append({
                            'pid': proc_info['pid'],
                            'name': proc_info['name'],
                            'cpu_percent': proc_info['cpu_percent'],
                            'memory_percent': proc_info['memory_percent']
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # 按CPU使用率排序
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            
        except Exception as e:
            logger.error(f"获取进程信息失败: {e}")
        
        return processes[:limit]
    
    def reset(self):
        """重置性能监控"""
        self.metrics_history = []
        self._init_network_baseline()
        logger.info("性能监控已重置")


if __name__ == "__main__":
    """测试性能监控"""
    monitor = PerformanceMonitor()
    
    print("性能监控测试")
    print("=" * 50)
    
    # 测试获取指标
    metrics = monitor.get_metrics()
    print("当前性能指标:")
    for key, value in metrics.items():
        if key != 'timestamp':
            print(f"{key}: {value}")
    
    # 测试阈值检查
    alerts = monitor.check_thresholds()
    print("\n性能告警:")
    for alert in alerts:
        print(f"{alert['level']}: {alert['message']}")
    
    # 测试获取摘要
    summary = monitor.get_summary()
    print("\n性能摘要:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    # 测试获取进程
    top_processes = monitor.get_top_processes()
    print("\n占用资源最多的进程:")
    for proc in top_processes:
        print(f"PID: {proc['pid']}, 名称: {proc['name']}, CPU: {proc['cpu_percent']}%, 内存: {proc['memory_percent']}%")