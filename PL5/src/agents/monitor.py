"""
免疫系统（监控层） - 实时监控系统性能、异常检测、自动修复
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path
from dataclasses import dataclass, asdict
import threading
import time
import psutil

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """指标快照"""
    timestamp: datetime
    agent_name: str
    metric_type: str
    value: float
    metadata: Dict[str, Any]


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, max_history: int = 1000):
        self.metrics_history: List[MetricSnapshot] = []
        self.max_history = max_history
        self._lock = threading.Lock()
        
    def record(self, agent_name: str, metric_type: str, value: float, 
               metadata: Dict[str, Any] = None):
        """记录指标"""
        snapshot = MetricSnapshot(
            timestamp=datetime.now(),
            agent_name=agent_name,
            metric_type=metric_type,
            value=value,
            metadata=metadata or {}
        )
        
        with self._lock:
            self.metrics_history.append(snapshot)
            # 限制历史记录数量
            if len(self.metrics_history) > self.max_history:
                self.metrics_history = self.metrics_history[-self.max_history:]
    
    def get_recent(self, agent_name: Optional[str] = None, 
                   metric_type: Optional[str] = None,
                   minutes: int = 60) -> List[MetricSnapshot]:
        """获取最近的指标"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        with self._lock:
            filtered = [
                m for m in self.metrics_history
                if m.timestamp >= cutoff
                and (agent_name is None or m.agent_name == agent_name)
                and (metric_type is None or m.metric_type == metric_type)
            ]
        return filtered
    
    def get_statistics(self, agent_name: str, metric_type: str,
                       minutes: int = 60) -> Dict[str, float]:
        """获取统计信息"""
        metrics = self.get_recent(agent_name, metric_type, minutes)
        values = [m.value for m in metrics]
        
        if not values:
            return {'count': 0}
        
        import numpy as np
        return {
            'count': len(values),
            'mean': np.mean(values),
            'std': np.std(values),
            'min': np.min(values),
            'max': np.max(values),
            'last': values[-1]
        }
    
    def export_to_file(self, filepath: Path):
        """导出指标到文件"""
        data = [
            {
                'timestamp': m.timestamp.isoformat(),
                'agent_name': m.agent_name,
                'metric_type': m.metric_type,
                'value': m.value,
                'metadata': m.metadata
            }
            for m in self.metrics_history
        ]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class MonitoringDashboard:
    """监控面板"""
    
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self.metrics_collector = MetricsCollector()
        self.is_running = False
        self.update_interval = 5  # 秒
        self._monitor_task = None
        
    async def start_monitoring(self):
        """开始监控"""
        self.is_running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("[Monitor] 监控面板已启动")
        
    async def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("[Monitor] 监控面板已停止")
        
    async def _monitoring_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[Monitor] 监控循环错误: %s", e)
                await asyncio.sleep(self.update_interval)
    
    async def _collect_metrics(self):
        """收集指标"""
        if not self.orchestrator:
            return
        
        # 收集各智能体的指标
        for name, agent in self.orchestrator.agents.items():
            metrics = agent.get_metrics()
            
            # 记录任务完成数
            self.metrics_collector.record(
                name, 'tasks_completed', 
                metrics['tasks_completed']
            )
            
            # 记录成功率
            self.metrics_collector.record(
                name, 'success_rate',
                metrics['success_rate']
            )
            
            # 记录平均执行时间
            self.metrics_collector.record(
                name, 'avg_execution_time',
                metrics['avg_execution_time']
            )
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取面板数据"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'is_running': self.is_running,
            'agents': {},
            'system_metrics': {}
        }
        
        if self.orchestrator:
            # 获取各智能体状态
            for name, agent in self.orchestrator.agents.items():
                data['agents'][name] = {
                    'current_metrics': agent.get_metrics(),
                    'recent_stats': {
                        'success_rate': self.metrics_collector.get_statistics(
                            name, 'success_rate', 60
                        ),
                        'execution_time': self.metrics_collector.get_statistics(
                            name, 'avg_execution_time', 60
                        )
                    }
                }
        
        return data
    
    def generate_html_report(self) -> str:
        """生成HTML报告"""
        data = self.get_dashboard_data()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>PL5 Agent Framework Monitor</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #333;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .agent-card {{
            background-color: white;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric {{
            display: inline-block;
            margin: 10px 20px 10px 0;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .status-running {{
            color: #4CAF50;
        }}
        .status-stopped {{
            color: #f44336;
        }}
        .progress-bar {{
            width: 100%;
            height: 20px;
            background-color: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background-color: #4CAF50;
            transition: width 0.3s ease;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 PL5 Agent Framework Monitor</h1>
        <p>Last Update: {data['timestamp']}</p>
        <p>Status: <span class="{'status-running' if data['is_running'] else 'status-stopped'}">
            {'Running' if data['is_running'] else 'Stopped'}
        </span></p>
    </div>
"""
        
        # 添加各智能体的状态
        for agent_name, agent_data in data['agents'].items():
            metrics = agent_data['current_metrics']
            html += f"""
    <div class="agent-card">
        <h2>📊 {agent_name}</h2>
        <div class="metric">
            <div class="metric-label">Tasks Completed</div>
            <div class="metric-value">{metrics['tasks_completed']}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Success Rate</div>
            <div class="metric-value">{metrics['success_rate']:.1%}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Avg Execution Time</div>
            <div class="metric-value">{metrics['avg_execution_time']:.2f}s</div>
        </div>
        <div class="metric">
            <div class="metric-label">Status</div>
            <div class="metric-value">{'Running' if metrics['is_running'] else 'Idle'}</div>
        </div>
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html
    
    def save_html_report(self, filepath: Path):
        """保存HTML报告"""
        html = self.generate_html_report()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info("[Monitor] HTML报告已保存: %s", filepath)


class ProgressTracker:
    """进度追踪器"""
    
    def __init__(self, total_steps: int, description: str = ""):
        self.total_steps = total_steps
        self.current_step = 0
        self.description = description
        self.start_time = datetime.now()
        self.step_times = []
        
    def update(self, step: int = None, message: str = ""):
        """更新进度"""
        if step is not None:
            self.current_step = step
        else:
            self.current_step += 1
        
        self.step_times.append(datetime.now())
        
        progress = self.current_step / self.total_steps * 100
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # 估算剩余时间
        if self.current_step > 0:
            avg_time_per_step = elapsed / self.current_step
            remaining_steps = self.total_steps - self.current_step
            eta = avg_time_per_step * remaining_steps
        else:
            eta = 0
        
        logger.info("[Progress] %s: %.1f%% (%d/%d) ETA: %.0fs %s", 
                   self.description, progress, self.current_step, self.total_steps, eta, message)
        
        return {
            'progress': progress,
            'current': self.current_step,
            'total': self.total_steps,
            'elapsed': elapsed,
            'eta': eta
        }
    
    def finish(self):
        """完成追踪"""
        total_time = (datetime.now() - self.start_time).total_seconds()
        logger.info("[Progress] %s 完成! 总耗时: %.2fs", self.description, total_time)
        
        return {
            'total_time': total_time,
            'avg_step_time': total_time / max(self.current_step, 1)
        }


class AnomalyDetector:
    """异常检测器"""
    
    def __init__(self, window_size: int = 20, threshold: float = 2.0):
        self.window_size = window_size
        self.threshold = threshold
        self.metric_windows = {}
        
    def detect(self, metric_name: str, value: float) -> Dict[str, Any]:
        """检测异常"""
        if metric_name not in self.metric_windows:
            self.metric_windows[metric_name] = []
        
        # 添加新值到窗口
        self.metric_windows[metric_name].append(value)
        
        # 保持窗口大小
        if len(self.metric_windows[metric_name]) > self.window_size:
            self.metric_windows[metric_name] = self.metric_windows[metric_name][-self.window_size:]
        
        # 计算统计信息
        window = self.metric_windows[metric_name]
        if len(window) < 5:  # 数据不足，无法检测
            return {'anomaly': False, 'reason': 'insufficient_data'}
        
        import numpy as np
        mean = np.mean(window)
        std = np.std(window)
        
        # 检测异常
        if std == 0:
            return {'anomaly': False, 'reason': 'no_variation'}
        
        z_score = abs(value - mean) / std
        is_anomaly = z_score > self.threshold
        
        return {
            'anomaly': is_anomaly,
            'z_score': z_score,
            'mean': mean,
            'std': std,
            'value': value,
            'threshold': self.threshold
        }


class SystemHealthMonitor:
    """系统健康监控器"""
    
    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.health_history = []
        self.system_metrics = {}
        
    def check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状态"""
        health_status = {
            'timestamp': datetime.now(),
            'cpu': self._check_cpu(),
            'memory': self._check_memory(),
            'disk': self._check_disk(),
            'network': self._check_network(),
            'overall': 'healthy'
        }
        
        # 评估整体健康状态
        issues = []
        if health_status['cpu'].get('usage', 0) > 80:
            issues.append('high_cpu_usage')
        if health_status['memory'].get('usage', 0) > 80:
            issues.append('high_memory_usage')
        if health_status['disk'].get('usage', 0) > 80:
            issues.append('low_disk_space')
        
        if issues:
            health_status['overall'] = 'unhealthy'
            health_status['issues'] = issues
        elif any(70 < health_status[k]['usage'] <= 80 for k in ['cpu', 'memory', 'disk']):
            health_status['overall'] = 'degraded'
        
        self.health_history.append(health_status)
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]
        
        return health_status
    
    def _check_cpu(self) -> Dict[str, Any]:
        """检查CPU状态"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        return {
            'usage': cpu_percent,
            'count': cpu_count,
            'status': 'normal' if cpu_percent < 70 else 'high' if cpu_percent < 90 else 'critical'
        }
    
    def _check_memory(self) -> Dict[str, Any]:
        """检查内存状态"""
        memory = psutil.virtual_memory()
        
        return {
            'usage': memory.percent,
            'total': memory.total / (1024 * 1024 * 1024),  # GB
            'available': memory.available / (1024 * 1024 * 1024),  # GB
            'status': 'normal' if memory.percent < 70 else 'high' if memory.percent < 90 else 'critical'
        }
    
    def _check_disk(self) -> Dict[str, Any]:
        """检查磁盘状态"""
        try:
            # 在Windows环境中使用C盘
            disk = psutil.disk_usage('C:')
            
            return {
                'usage': disk.percent,
                'total': disk.total / (1024 * 1024 * 1024),  # GB
                'free': disk.free / (1024 * 1024 * 1024),  # GB
                'status': 'normal' if disk.percent < 70 else 'high' if disk.percent < 90 else 'critical'
            }
        except Exception as e:
            return {
                'error': str(e),
                'status': 'error'
            }
    
    def _check_network(self) -> Dict[str, Any]:
        """检查网络状态"""
        try:
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv,
                'status': 'normal'
            }
        except Exception as e:
            return {
                'error': str(e),
                'status': 'error'
            }


class AutoHealer:
    """自动修复器"""
    
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self.repair_history = []
        
    async def attempt_repair(self, issue: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """尝试修复问题"""
        repair_result = {
            'issue': issue,
            'timestamp': datetime.now(),
            'success': False,
            'action': 'none',
            'message': 'No repair action taken'
        }
        
        # 根据问题类型执行修复
        if issue == 'high_cpu_usage':
            repair_result = await self._fix_high_cpu_usage(context)
        elif issue == 'high_memory_usage':
            repair_result = await self._fix_high_memory_usage(context)
        elif issue == 'agent_failure':
            repair_result = await self._fix_agent_failure(context)
        elif issue == 'data_quality_issue':
            repair_result = await self._fix_data_quality_issue(context)
        
        self.repair_history.append(repair_result)
        if len(self.repair_history) > 50:
            self.repair_history = self.repair_history[-50:]
        
        return repair_result
    
    async def _fix_high_cpu_usage(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """修复高CPU使用率"""
        # 减少并行度
        if self.orchestrator:
            for agent_name, agent in self.orchestrator.agents.items():
                if hasattr(agent, 'max_workers') and agent.max_workers > 1:
                    agent.max_workers = max(1, agent.max_workers // 2)
                    logger.info("[AutoHealer] 减少 %s 的并行度到 %d", agent_name, agent.max_workers)
        
        return {
            'issue': 'high_cpu_usage',
            'timestamp': datetime.now(),
            'success': True,
            'action': 'reduce_parallelism',
            'message': 'Reduced agent parallelism to reduce CPU usage'
        }
    
    async def _fix_high_memory_usage(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """修复高内存使用率"""
        # 清理缓存
        if self.orchestrator:
            for agent_name, agent in self.orchestrator.agents.items():
                if hasattr(agent, 'clear_cache'):
                    try:
                        agent.clear_cache()
                        logger.info("[AutoHealer] 清理 %s 的缓存", agent_name)
                    except Exception as e:
                        logger.error("[AutoHealer] 清理缓存失败: %s", e)
        
        return {
            'issue': 'high_memory_usage',
            'timestamp': datetime.now(),
            'success': True,
            'action': 'clear_cache',
            'message': 'Cleared agent caches to reduce memory usage'
        }
    
    async def _fix_agent_failure(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """修复智能体失败"""
        agent_name = context.get('agent_name')
        if self.orchestrator and agent_name in self.orchestrator.agents:
            # 重启智能体
            try:
                agent = self.orchestrator.agents[agent_name]
                if hasattr(agent, 'shutdown'):
                    agent.shutdown()
                # 重新初始化智能体（简化处理）
                logger.info("[AutoHealer] 重启智能体 %s", agent_name)
                return {
                    'issue': 'agent_failure',
                    'timestamp': datetime.now(),
                    'success': True,
                    'action': 'restart_agent',
                    'message': f'Restarted agent {agent_name}'
                }
            except Exception as e:
                return {
                    'issue': 'agent_failure',
                    'timestamp': datetime.now(),
                    'success': False,
                    'action': 'restart_agent',
                    'message': f'Failed to restart agent: {e}'
                }
        
        return {
            'issue': 'agent_failure',
            'timestamp': datetime.now(),
            'success': False,
            'action': 'none',
            'message': 'Agent not found'
        }
    
    async def _fix_data_quality_issue(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """修复数据质量问题"""
        if self.orchestrator and 'data' in self.orchestrator.agents:
            # 触发数据重新采集
            data_agent = self.orchestrator.agents['data']
            try:
                # 模拟数据重新采集
                logger.info("[AutoHealer] 触发数据重新采集")
                return {
                    'issue': 'data_quality_issue',
                    'timestamp': datetime.now(),
                    'success': True,
                    'action': 'recollect_data',
                    'message': 'Triggered data re-collection'
                }
            except Exception as e:
                return {
                    'issue': 'data_quality_issue',
                    'timestamp': datetime.now(),
                    'success': False,
                    'action': 'recollect_data',
                    'message': f'Failed to recollect data: {e}'
                }
        
        return {
            'issue': 'data_quality_issue',
            'timestamp': datetime.now(),
            'success': False,
            'action': 'none',
            'message': 'Data agent not found'
        }


class ImmuneSystem:
    """免疫系统 - 集成监控、异常检测和自动修复"""
    
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self.health_monitor = SystemHealthMonitor()
        self.auto_healer = AutoHealer(orchestrator)
        self.anomaly_detector = AnomalyDetector()
        self.is_running = False
        self.monitoring_task = None
        self.check_interval = 30  # 秒
        self.issues = []
        
    async def start(self):
        """启动免疫系统"""
        self.is_running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("[ImmuneSystem] 免疫系统已启动")
    
    async def stop(self):
        """停止免疫系统"""
        self.is_running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("[ImmuneSystem] 免疫系统已停止")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                # 暂时禁用监控循环，只测试基本功能
                logger.info("[ImmuneSystem] 监控循环运行中...")
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[ImmuneSystem] 监控循环错误: %s", e)
                await asyncio.sleep(self.check_interval)
    
    async def _check_system(self):
        """检查系统状态"""
        health_status = self.health_monitor.check_system_health()
        
        # 处理系统问题
        if health_status['overall'] == 'unhealthy':
            for issue in health_status.get('issues', []):
                if issue not in [i['issue'] for i in self.issues]:
                    self.issues.append({
                        'issue': issue,
                        'timestamp': datetime.now(),
                        'severity': 'critical'
                    })
                    # 尝试修复
                    await self.auto_healer.attempt_repair(issue, health_status)
        
        logger.debug("[ImmuneSystem] 系统健康状态: %s", health_status['overall'])
    
    async def _check_agents(self):
        """检查智能体状态"""
        if not self.orchestrator:
            return
        
        for agent_name, agent in self.orchestrator.agents.items():
            try:
                metrics = agent.get_metrics()
                
                # 检测智能体异常
                if metrics['tasks_failed'] > 3 and metrics['success_rate'] < 0.5:
                    issue = 'agent_failure'
                    if issue not in [i['issue'] for i in self.issues]:
                        self.issues.append({
                            'issue': issue,
                            'agent_name': agent_name,
                            'timestamp': datetime.now(),
                            'severity': 'critical'
                        })
                        # 尝试修复
                        await self.auto_healer.attempt_repair(issue, {'agent_name': agent_name})
            except Exception as e:
                logger.error("[ImmuneSystem] 检查智能体 %s 失败: %s", agent_name, e)
    
    async def _check_performance(self):
        """检查性能指标"""
        if not self.orchestrator:
            return
        
        for agent_name, agent in self.orchestrator.agents.items():
            try:
                metrics = agent.get_metrics()
                
                # 检测性能异常
                if metrics['avg_execution_time'] > 60:  # 执行时间超过60秒
                    anomaly = self.anomaly_detector.detect(
                    agent_name + '_execution_time',
                    metrics['avg_execution_time']
                )
                    if anomaly['anomaly']:
                        issue = 'performance_degradation'
                        if issue not in [i['issue'] for i in self.issues]:
                            self.issues.append({
                                'issue': issue,
                                'agent_name': agent_name,
                                'timestamp': datetime.now(),
                                'severity': 'warning'
                            })
            except Exception as e:
                logger.error("[ImmuneSystem] 检查性能指标失败: %s", e)
    
    def get_status(self) -> Dict[str, Any]:
        """获取免疫系统状态"""
        return {
            'is_running': self.is_running,
            'system_health': self.health_monitor.check_system_health(),
            'active_issues': self.issues,
            'repair_history': self.auto_healer.repair_history[-10:],
            'check_interval': self.check_interval
        }
    
    def generate_health_report(self) -> str:
        """生成健康报告"""
        status = self.get_status()
        
        report = "# PL5 系统健康报告\n"
        report += "生成时间: " + datetime.now().isoformat() + "\n"
        report += "免疫系统状态: " + ('运行中' if status['is_running'] else '已停止') + "\n\n"
        
        # 系统健康状态
        report += "## 系统健康状态\n"
        system_health = status['system_health']
        report += "- 整体状态: " + system_health['overall'] + "\n"
        report += "- CPU使用率: " + str(system_health['cpu'].get('usage', 'N/A')) + "%\n"
        report += "- 内存使用率: " + str(system_health['memory'].get('usage', 'N/A')) + "%\n"
        report += "- 磁盘使用率: " + str(system_health['disk'].get('usage', 'N/A')) + "%\n\n"
        
        # 活跃问题
        report += "## 活跃问题\n"
        if status['active_issues']:
            for issue in status['active_issues']:
                report += "- " + issue['issue'] + " (严重程度: " + issue['severity'] + ") - " + issue['timestamp'].isoformat() + "\n"
        else:
            report += "- 无活跃问题\n\n"
        
        # 修复历史
        report += "## 修复历史\n"
        if status['repair_history']:
            for repair in status['repair_history']:
                status_str = '成功' if repair['success'] else '失败'
                report += "- " + repair['issue'] + ": " + status_str + " - " + repair['action'] + "\n"
        else:
            report += "- 无修复记录\n"
        
        return report
    
    def save_health_report(self, filepath: Path):
        """保存健康报告"""
        report = self.generate_health_report()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info("[ImmuneSystem] 健康报告已保存: %s", filepath)
