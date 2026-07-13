"""
智能体性能监控系统
实时监控智能体框架的性能指标、资源使用和任务状态
"""

import asyncio
import json
import sys
import time
import psutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
import numpy as np

# 确保项目根目录在 sys.path 中
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import setup_logging, BASE_DIR, LOGS_DIR

# agent_framework 是可选依赖（src/agents/orchestrator.py 实现了同等功能）
# 若未安装则使用占位对象，避免整个 monitor 包因此无法加载
try:
    from agent_framework import AgentOrchestrator
except ImportError:
    try:
        # 尝试从 src.agents 加载
        import importlib
        _mod = importlib.import_module("src.agents.orchestrator")
        AgentOrchestrator = getattr(_mod, "AgentOrchestrator", None)
    except Exception:
        AgentOrchestrator = None  # 完全不可用时置 None

logger = setup_logging(__name__)


class AgentPerformanceMonitor:
    """智能体性能监控器"""
    
    def __init__(self, update_interval=5):
        self.update_interval = update_interval
        self.running = False
        self.performance_metrics = deque(maxlen=1000)  # 存储性能指标
        self.task_history = deque(maxlen=500)  # 存储任务历史
        self.agent_status = {}
        self.orchestrator = None
        
    def start(self):
        """启动监控"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("智能体性能监控已启动")
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        logger.info("智能体性能监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                metrics = self.collect_performance_metrics()
                self.performance_metrics.append(metrics)
                
                # 检查智能体状态
                if self.orchestrator:
                    agent_status = self.get_agent_status()
                    self.agent_status = agent_status
                
                # 保存到文件（每10次记录一次）
                if len(self.performance_metrics) % 10 == 0:
                    self.save_metrics()
                
            except Exception as e:
                logger.error(f"监控数据收集失败: {e}")
            
            time.sleep(self.update_interval)
    
    def collect_performance_metrics(self):
        """收集性能指标"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'system': self._get_system_metrics(),
            'agents': self._get_agent_metrics(),
            'tasks': self._get_task_metrics(),
            'performance': self._get_performance_summary()
        }
        return metrics
    
    def _get_system_metrics(self):
        """获取系统指标"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(BASE_DIR))
            
            return {
                'cpu_percent': cpu_percent,
                'cpu_count': psutil.cpu_count(),
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024**3),
                'process_count': len(list(psutil.process_iter(['name']))),
                'uptime': time.time() - psutil.boot_time()
            }
        except Exception as e:
            logger.error(f"获取系统指标失败: {e}")
            return {}
    
    def _get_agent_metrics(self):
        """获取智能体指标"""
        if not self.orchestrator:
            return {}
        
        try:
            agents = {}
            for name, agent in self.orchestrator.agents.items():
                agents[name] = {
                    'is_running': agent.is_running if hasattr(agent, 'is_running') else True,
                    'tasks_completed': agent.tasks_completed if hasattr(agent, 'tasks_completed') else 0,
                    'tasks_failed': agent.tasks_failed if hasattr(agent, 'tasks_failed') else 0,
                    'success_rate': agent.success_rate if hasattr(agent, 'success_rate') else 1.0,
                    'active_tasks': agent.active_tasks if hasattr(agent, 'active_tasks') else 0,
                    'queue_size': agent.queue_size if hasattr(agent, 'queue_size') else 0
                }
            return agents
        except Exception as e:
            logger.error(f"获取智能体指标失败: {e}")
            return {}
    
    def _get_task_metrics(self):
        """获取任务指标"""
        try:
            # 从最近的任务历史中获取指标
            recent_tasks = list(self.task_history)[-50:] if self.task_history else []
            
            if not recent_tasks:
                return {}
            
            durations = [t.get('duration', 0) for t in recent_tasks if 'duration' in t]
            success_tasks = [t for t in recent_tasks if t.get('success', False)]
            failed_tasks = [t for t in recent_tasks if not t.get('success', True)]
            
            return {
                'total_tasks': len(recent_tasks),
                'success_tasks': len(success_tasks),
                'failed_tasks': len(failed_tasks),
                'success_rate': len(success_tasks) / len(recent_tasks) if recent_tasks else 0,
                'avg_duration': np.mean(durations) if durations else 0,
                'max_duration': max(durations) if durations else 0,
                'min_duration': min(durations) if durations else 0
            }
        except Exception as e:
            logger.error(f"获取任务指标失败: {e}")
            return {}
    
    def _get_performance_summary(self):
        """获取性能摘要"""
        try:
            if not self.performance_metrics:
                return {}
            
            # 分析最近10个数据点
            recent_metrics = list(self.performance_metrics)[-10:]
            
            cpu_values = [m['system'].get('cpu_percent', 0) for m in recent_metrics if 'system' in m]
            memory_values = [m['system'].get('memory_percent', 0) for m in recent_metrics if 'system' in m]
            
            return {
                'avg_cpu': np.mean(cpu_values) if cpu_values else 0,
                'max_cpu': max(cpu_values) if cpu_values else 0,
                'avg_memory': np.mean(memory_values) if memory_values else 0,
                'max_memory': max(memory_values) if memory_values else 0,
                'data_points': len(recent_metrics)
            }
        except Exception as e:
            logger.error(f"获取性能摘要失败: {e}")
            return {}
    
    def get_agent_status(self):
        """获取智能体状态"""
        if not self.orchestrator:
            return {}
        
        try:
            return self.orchestrator.get_status()
        except Exception as e:
            logger.error(f"获取智能体状态失败: {e}")
            return {}
    
    def record_task(self, task_info):
        """记录任务执行信息"""
        task_info['timestamp'] = datetime.now().isoformat()
        self.task_history.append(task_info)
    
    def save_metrics(self):
        """保存指标到文件"""
        try:
            metrics_file = LOGS_DIR / 'agent_performance.json'
            metrics_data = {
                'timestamp': datetime.now().isoformat(),
                'performance_metrics': list(self.performance_metrics)[-100:],  # 最近100个点
                'task_summary': self._get_task_metrics(),
                'agent_status': self.agent_status
            }
            
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.debug(f"性能指标已保存到: {metrics_file}")
        except Exception as e:
            logger.error(f"保存性能指标失败: {e}")
    
    def get_performance_report(self):
        """获取性能报告"""
        try:
            task_metrics = self._get_task_metrics()
            performance_summary = self._get_performance_summary()
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'system_status': self._get_system_metrics(),
                'performance_summary': performance_summary,
                'task_metrics': task_metrics,
                'agent_count': len(self.agent_status.get('agents', {})),
                'recommendations': self._generate_recommendations(task_metrics, performance_summary)
            }
            
            return report
        except Exception as e:
            logger.error(f"生成性能报告失败: {e}")
            return {}
    
    def _generate_recommendations(self, task_metrics, performance_summary):
        """生成优化建议"""
        recommendations = []
        
        # CPU使用率建议
        avg_cpu = performance_summary.get('avg_cpu', 0)
        if avg_cpu > 80:
            recommendations.append("CPU使用率过高，考虑增加工作线程或优化算法")
        elif avg_cpu < 30:
            recommendations.append("CPU使用率较低，可以增加并行任务数量")
        
        # 内存使用建议
        avg_memory = performance_summary.get('avg_memory', 0)
        if avg_memory > 80:
            recommendations.append("内存使用率过高，考虑优化内存使用或增加物理内存")
        
        # 任务成功率建议
        success_rate = task_metrics.get('success_rate', 1)
        if success_rate < 0.8:
            recommendations.append(f"任务成功率较低 ({success_rate:.1%})，建议检查任务逻辑和错误处理")
        
        # 任务执行时间建议
        avg_duration = task_metrics.get('avg_duration', 0)
        if avg_duration > 60:  # 超过60秒
            recommendations.append(f"平均任务执行时间较长 ({avg_duration:.1f}秒)，建议优化算法或增加并行度")
        
        return recommendations
    
    def connect_orchestrator(self, orchestrator: AgentOrchestrator):
        """连接智能体编排器"""
        self.orchestrator = orchestrator
        logger.info(f"已连接到智能体编排器，智能体数量: {len(orchestrator.agents)}")


class AgentPerformanceDashboard:
    """智能体性能仪表盘（控制台版本）"""
    
    def __init__(self, monitor: AgentPerformanceMonitor):
        self.monitor = monitor
        self.running = False
    
    def start(self):
        """启动仪表盘"""
        self.running = True
        self.dashboard_thread = threading.Thread(target=self._dashboard_loop, daemon=True)
        self.dashboard_thread.start()
        logger.info("智能体性能仪表盘已启动")
    
    def stop(self):
        """停止仪表盘"""
        self.running = False
        if self.dashboard_thread:
            self.dashboard_thread.join(timeout=2)
        logger.info("智能体性能仪表盘已停止")
    
    def _dashboard_loop(self):
        """仪表盘循环"""
        while self.running:
            try:
                self.clear_screen()
                self.display_header()
                self.display_system_metrics()
                self.display_agent_status()
                self.display_task_metrics()
                self.display_performance_summary()
                self.display_recommendations()
                self.display_footer()
                
            except Exception as e:
                logger.error(f"仪表盘显示失败: {e}")
            
            time.sleep(5)  # 5秒更新一次
    
    def clear_screen(self):
        """清屏"""
        print("\033c", end="")  # 清除屏幕
    
    def display_header(self):
        """显示头部信息"""
        print("=" * 100)
        print("PL5 智能体性能监控仪表板".center(100))
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(100))
        print("=" * 100)
        print()
    
    def display_system_metrics(self):
        """显示系统指标"""
        print("📊 系统资源使用")
        print("-" * 50)
        
        try:
            if self.monitor.performance_metrics:
                latest_metrics = self.monitor.performance_metrics[-1]
                system = latest_metrics.get('system', {})
                
                cpu_percent = system.get('cpu_percent', 0)
                memory_percent = system.get('memory_percent', 0)
                disk_percent = system.get('disk_percent', 0)
                
                # CPU进度条
                cpu_bar = self._create_progress_bar(cpu_percent, 50)
                print(f"CPU使用率: {cpu_percent:6.1f}% {cpu_bar}")
                
                # 内存进度条
                memory_bar = self._create_progress_bar(memory_percent, 50)
                print(f"内存使用率: {memory_percent:5.1f}% {memory_bar}")
                
                # 磁盘进度条
                disk_bar = self._create_progress_bar(disk_percent, 50)
                print(f"磁盘使用率: {disk_percent:5.1f}% {disk_bar}")
                
                # 其他信息
                cpu_count = system.get('cpu_count', 0)
                memory_used = system.get('memory_used_gb', 0)
                disk_free = system.get('disk_free_gb', 0)
                
                print(f"CPU核心数: {cpu_count} | 内存使用: {memory_used:.1f} GB | 磁盘剩余: {disk_free:.1f} GB")
        except Exception as e:
            print(f"系统指标获取失败: {e}")
        
        print()
    
    def display_agent_status(self):
        """显示智能体状态"""
        print("🤖 智能体状态")
        print("-" * 50)
        
        try:
            agent_status = self.monitor.agent_status
            agents = agent_status.get('agents', {})
            
            if not agents:
                print("暂无智能体状态信息")
                print()
                return
            
            for name, status in agents.items():
                is_running = status.get('is_running', False)
                tasks_completed = status.get('tasks_completed', 0)
                success_rate = status.get('success_rate', 0)
                active_tasks = status.get('active_tasks', 0)
                
                status_icon = "🟢" if is_running else "🔴"
                success_color = "\033[92m" if success_rate > 0.8 else "\033[93m" if success_rate > 0.6 else "\033[91m"
                reset_color = "\033[0m"
                
                print(f"{status_icon} {name:20} | 运行中: {'是' if is_running else '否':5} | "
                      f"完成任务: {tasks_completed:4d} | "
                      f"成功率: {success_color}{success_rate:6.1%}{reset_color} | "
                      f"活跃任务: {active_tasks:2d}")
        except Exception as e:
            print(f"智能体状态获取失败: {e}")
        
        print()
    
    def display_task_metrics(self):
        """显示任务指标"""
        print("📋 任务执行指标")
        print("-" * 50)
        
        try:
            task_metrics = self.monitor._get_task_metrics()
            
            if not task_metrics:
                print("暂无任务执行数据")
                print()
                return
            
            total_tasks = task_metrics.get('total_tasks', 0)
            success_tasks = task_metrics.get('success_tasks', 0)
            failed_tasks = task_metrics.get('failed_tasks', 0)
            success_rate = task_metrics.get('success_rate', 0)
            avg_duration = task_metrics.get('avg_duration', 0)
            
            # 成功率颜色
            if success_rate > 0.8:
                success_color = "\033[92m"  # 绿色
            elif success_rate > 0.6:
                success_color = "\033[93m"  # 黄色
            else:
                success_color = "\033[91m"  # 红色
            reset_color = "\033[0m"
            
            print(f"总任务数: {total_tasks:6d} | 成功: {success_tasks:6d} | 失败: {failed_tasks:6d}")
            print(f"成功率: {success_color}{success_rate:8.2%}{reset_color} | 平均耗时: {avg_duration:8.2f}秒")
            
            # 任务进度条
            if total_tasks > 0:
                success_bar = self._create_progress_bar(success_rate * 100, 50)
                print(f"成功比例: {success_bar}")
        except Exception as e:
            print(f"任务指标获取失败: {e}")
        
        print()
    
    def display_performance_summary(self):
        """显示性能摘要"""
        print("⚡ 性能摘要")
        print("-" * 50)
        
        try:
            performance_summary = self.monitor._get_performance_summary()
            
            if not performance_summary:
                print("暂无性能摘要数据")
                print()
                return
            
            avg_cpu = performance_summary.get('avg_cpu', 0)
            max_cpu = performance_summary.get('max_cpu', 0)
            avg_memory = performance_summary.get('avg_memory', 0)
            max_memory = performance_summary.get('max_memory', 0)
            data_points = performance_summary.get('data_points', 0)
            
            # CPU使用率评价
            cpu_status = "🟢 正常" if avg_cpu < 70 else "🟡 警告" if avg_cpu < 85 else "🔴 危险"
            memory_status = "🟢 正常" if avg_memory < 70 else "🟡 警告" if avg_memory < 85 else "🔴 危险"
            
            print(f"CPU使用率: 平均 {avg_cpu:5.1f}% | 峰值 {max_cpu:5.1f}% | 状态: {cpu_status}")
            print(f"内存使用率: 平均 {avg_memory:4.1f}% | 峰值 {max_memory:4.1f}% | 状态: {memory_status}")
            print(f"数据点数: {data_points}")
        except Exception as e:
            print(f"性能摘要获取失败: {e}")
        
        print()
    
    def display_recommendations(self):
        """显示优化建议"""
        print("💡 优化建议")
        print("-" * 50)
        
        try:
            report = self.monitor.get_performance_report()
            recommendations = report.get('recommendations', [])
            
            if not recommendations:
                print("系统运行良好，暂无优化建议")
            else:
                for i, rec in enumerate(recommendations, 1):
                    print(f"{i}. {rec}")
        except Exception as e:
            print(f"优化建议获取失败: {e}")
        
        print()
    
    def display_footer(self):
        """显示页脚"""
        print("=" * 100)
        print("按 Ctrl+C 退出监控 | 数据每5秒更新一次 | PL5 智能体优化版 V8.0")
        print("=" * 100)
    
    def _create_progress_bar(self, percentage, width=50):
        """创建进度条"""
        filled = int(width * percentage / 100)
        empty = width - filled
        
        # 根据百分比选择颜色
        if percentage < 50:
            color = "\033[92m"  # 绿色
        elif percentage < 80:
            color = "\033[93m"  # 黄色
        else:
            color = "\033[91m"  # 红色
        
        reset = "\033[0m"
        
        bar = f"{color}{'█' * filled}{reset}{'░' * empty}"
        return bar


def main():
    """主函数"""
    print("启动智能体性能监控系统...")
    
    # 创建监控器
    monitor = AgentPerformanceMonitor(update_interval=5)
    monitor.start()
    
    # 创建仪表盘
    dashboard = AgentPerformanceDashboard(monitor)
    dashboard.start()
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止监控系统...")
    finally:
        dashboard.stop()
        monitor.stop()
        print("监控系统已停止")


if __name__ == "__main__":
    main()