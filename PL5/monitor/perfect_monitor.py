"""
排列五完美系统监控中心
实时监控系统运行状态、性能指标和健康状况
"""

import os
import sys
import time
import psutil
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque

# 确保项目根目录在 sys.path 中
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import setup_logging, BASE_DIR, LOGS_DIR, MODELS_DIR
from .agent_monitor import AgentPerformanceMonitor, AgentPerformanceDashboard

logger = setup_logging(__name__)


class PerfectSystemMonitor:
    """完美系统监控中心"""
    
    def __init__(self):
        self.project_dir = BASE_DIR            # ✅ 正确指向项目根目录
        self.running = False
        self.metrics_history = deque(maxlen=1000)
        self.alert_thresholds = {
            'cpu_percent': 90,
            'memory_percent': 85,
            'disk_percent': 90,
            'process_count': 50
        }
        self.alerts = []
        
    def get_system_metrics(self):
        """获取系统指标"""
        # 磁盘信息：psutil.disk_usage 在某些 Windows 版本上有 bad format char 问题
        # 主方案：shutil.disk_usage（标准库，无此 bug）
        import shutil as _shutil
        try:
            _disk_path = str(self.project_dir)
            total, used, free = _shutil.disk_usage(_disk_path)
            disk_info = {
                'total': total,
                'used': used,
                'free': free,
                'percent': round(used / total * 100, 1) if total > 0 else 0.0
            }
        except Exception:
            try:
                total, used, free = _shutil.disk_usage('.')
                disk_info = {
                    'total': total,
                    'used': used,
                    'free': free,
                    'percent': round(used / total * 100, 1) if total > 0 else 0.0
                }
            except Exception:
                disk_info = {'total': 0, 'used': 0, 'free': 0, 'percent': 0.0}

        metrics = {
            'timestamp': datetime.now().isoformat(),
            'cpu': {
                'percent': psutil.cpu_percent(interval=1),
                'count': psutil.cpu_count(),
                'freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {}
            },
            'memory': psutil.virtual_memory()._asdict(),
            'disk': disk_info,
            'network': psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {},
            'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }
        return metrics
    
    def get_process_info(self):
        """获取进程信息"""
        pl5_processes = []
        python_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent', 'create_time']):
            try:
                pinfo = proc.info
                # 兼容 Windows(python.exe) 和 Linux(python/python3)
                if pinfo['name'] in ('python.exe', 'python', 'python3'):
                    cmdline = ' '.join(pinfo['cmdline']) if pinfo['cmdline'] else ''
                    python_processes.append({
                        'pid': pinfo['pid'],
                        'cmdline': cmdline[:100],
                        'cpu': pinfo['cpu_percent'],
                        'memory': pinfo['memory_percent']
                    })
                    
                    if any(keyword in cmdline.lower() for keyword in ['pl5', 'auto_scheduler', 'prevent_sleep']):
                        pl5_processes.append({
                            'pid': pinfo['pid'],
                            'cmdline': cmdline[:80],
                            'cpu': round(pinfo['cpu_percent'] or 0, 2),
                            'memory': round(pinfo['memory_percent'] or 0, 2),
                            'start_time': datetime.fromtimestamp(pinfo['create_time']).isoformat()
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return {
            'pl5_processes': pl5_processes,
            'total_python': len(python_processes),
            'system_total': len(list(psutil.process_iter()))
        }
    
    def get_data_health(self):
        """检查数据健康状态"""
        health = {
            'raw_data': {'exists': False, 'records': 0},
            'processed_data': {'exists': False, 'records': 0},
            'models': {'exists': False, 'count': 0},
            'learning_history': {'exists': False, 'evaluations': 0}
        }
        
        # 原始数据
        raw_file = self.project_dir / 'data' / 'raw' / 'pl5_history.txt'
        if raw_file.exists():
            health['raw_data']['exists'] = True
            health['raw_data']['size_mb'] = round(raw_file.stat().st_size / 1024 / 1024, 2)
        
        # 处理后的数据
        processed_file = self.project_dir / 'data' / 'processed' / 'pl5_processed.csv'
        if processed_file.exists():
            health['processed_data']['exists'] = True
            health['processed_data']['size_mb'] = round(processed_file.stat().st_size / 1024 / 1024, 2)
            try:
                import pandas as pd
                df = pd.read_csv(processed_file)
                health['processed_data']['records'] = len(df)
                health['processed_data']['features'] = len(df.columns)
            except Exception:
                pass
        
        # 模型文件（使用统一的 MODELS_DIR）
        if MODELS_DIR.exists():
            model_files = list(MODELS_DIR.glob('*.pkl')) + list(MODELS_DIR.glob('*.json'))
            health['models']['exists'] = len(model_files) > 0
            health['models']['count'] = len(model_files)
        
        # 学习历史
        history_file = MODELS_DIR / 'learning_history.json'
        if history_file.exists():
            health['learning_history']['exists'] = True
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    health['learning_history']['evaluations'] = len(data.get('evaluations', []))
            except Exception:
                pass
        
        return health
    
    def get_schedule_status(self):
        """获取调度状态"""
        status = {
            'next_tasks': [],
            'last_execution': None,
            'system_uptime': None
        }
        
        # 检查日志文件获取最后执行时间（使用统一的 LOGS_DIR）
        log_file = LOGS_DIR / 'pl5_system.log'
        if log_file.exists():
            try:
                mtime = log_file.stat().st_mtime
                status['last_execution'] = datetime.fromtimestamp(mtime).isoformat()
            except Exception:
                pass
        
        # 计算系统运行时间
        process_info = self.get_process_info()
        if process_info['pl5_processes']:
            oldest_process = min(process_info['pl5_processes'], 
                               key=lambda x: x.get('start_time', datetime.now().isoformat()))
            start_time = datetime.fromisoformat(oldest_process['start_time'])
            uptime = datetime.now() - start_time
            status['system_uptime'] = str(uptime).split('.')[0]
        
        return status
    
    def check_alerts(self, metrics, processes):
        """检查告警条件"""
        new_alerts = []
        
        # CPU告警
        if metrics['cpu']['percent'] > self.alert_thresholds['cpu_percent']:
            new_alerts.append({
                'level': 'WARNING',
                'message': f"CPU使用率过高: {metrics['cpu']['percent']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # 内存告警
        if metrics['memory']['percent'] > self.alert_thresholds['memory_percent']:
            new_alerts.append({
                'level': 'WARNING',
                'message': f"内存使用率过高: {metrics['memory']['percent']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # 磁盘告警
        if metrics['disk']['percent'] > self.alert_thresholds['disk_percent']:
            new_alerts.append({
                'level': 'WARNING',
                'message': f"磁盘使用率过高: {metrics['disk']['percent']}%",
                'timestamp': datetime.now().isoformat()
            })
        
        # 进程告警
        if processes['total_python'] > self.alert_thresholds['process_count']:
            new_alerts.append({
                'level': 'WARNING',
                'message': f"Python进程数过多: {processes['total_python']}",
                'timestamp': datetime.now().isoformat()
            })
        
        # 检查PL5系统是否运行
        if not processes['pl5_processes']:
            new_alerts.append({
                'level': 'CRITICAL',
                'message': "PL5系统未运行！",
                'timestamp': datetime.now().isoformat()
            })
        
        self.alerts.extend(new_alerts)
        # 只保留最近100条告警
        self.alerts = self.alerts[-100:]
        
        return new_alerts
    
    def display_dashboard(self):
        """显示监控仪表盘"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        metrics = self.get_system_metrics()
        processes = self.get_process_info()
        data_health = self.get_data_health()
        schedule_status = self.get_schedule_status()
        new_alerts = self.check_alerts(metrics, processes)
        
        # 保存历史
        self.metrics_history.append({
            'timestamp': metrics['timestamp'],
            'cpu': metrics['cpu']['percent'],
            'memory': metrics['memory']['percent']
        })
        
        # 标题
        print("╔" + "═" * 98 + "╗")
        print("║" + "排列五完美智能分析系统 - 实时监控中心".center(94) + "║")
        print("║" + f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(94) + "║")
        print("╚" + "═" * 98 + "╝")
        print()
        
        # 系统状态概览
        print("┌─ 系统状态概览 ".ljust(50, "─") + "┬─ 资源使用 ".ljust(49, "─") + "┐")
        
        # PL5进程状态
        if processes['pl5_processes']:
            status_str = f"✅ 运行中 ({len(processes['pl5_processes'])} 个进程)"
        else:
            status_str = "❌ 未运行"
        print(f"│ 系统状态: {status_str:<37} │ CPU: {metrics['cpu']['percent']:>5.1f}% {'█' * int(metrics['cpu']['percent']/5):<14} │")
        
        # 运行时间
        uptime = schedule_status.get('system_uptime', 'N/A')
        mem_used = metrics['memory']['percent']
        print(f"│ 运行时间: {uptime:<37} │ 内存: {mem_used:>5.1f}% {'█' * int(mem_used/5):<14} │")
        
        # 最后执行
        last_exec = schedule_status.get('last_execution', 'N/A')
        if last_exec != 'N/A':
            last_exec = last_exec[11:19]
        disk_used = metrics['disk']['percent']
        print(f"│ 最后执行: {last_exec:<37} │ 磁盘: {disk_used:>5.1f}% {'█' * int(disk_used/5):<14} │")
        print("└" + "─" * 49 + "┴" + "─" * 48 + "┘")
        print()
        
        # PL5进程详情
        if processes['pl5_processes']:
            print("┌─ PL5系统进程 ".ljust(100, "─") + "┐")
            print(f"│ {'PID':<10} {'CPU%':<8} {'内存%':<8} {'启动时间':<20} {'命令':<45} │")
            print("├" + "─" * 99 + "┤")
            for proc in processes['pl5_processes'][:5]:
                start = proc.get('start_time', 'N/A')
                if start != 'N/A':
                    start = start[11:19]
                cmd = proc['cmdline'][:40] if len(proc['cmdline']) > 40 else proc['cmdline']
                print(f"│ {proc['pid']:<10} {proc['cpu']:<8.1f} {proc['memory']:<8.1f} {start:<20} {cmd:<45} │")
            print("└" + "─" * 99 + "┘")
            print()
        
        # 数据健康状态
        print("┌─ 数据健康状态 ".ljust(100, "─") + "┐")
        
        raw_status = "✅" if data_health['raw_data']['exists'] else "❌"
        raw_size = f"{data_health['raw_data'].get('size_mb', 0)} MB"
        print(f"│ 原始数据: {raw_status} {raw_size:<15}", end="")
        
        proc_status = "✅" if data_health['processed_data']['exists'] else "❌"
        proc_info = f"{data_health['processed_data'].get('records', 0)} 条"
        print(f"处理数据: {proc_status} {proc_info:<15}", end="")
        
        model_status = "✅" if data_health['models']['exists'] else "❌"
        model_info = f"{data_health['models']['count']} 个模型"
        print(f"模型文件: {model_status} {model_info:<15} │")
        
        history_status = "✅" if data_health['learning_history']['exists'] else "❌"
        history_info = f"{data_health['learning_history']['evaluations']} 条评估"
        print(f"│ 学习历史: {history_status} {history_info:<93} │")
        
        print("└" + "─" * 99 + "┘")
        print()
        
        # 告警信息
        if self.alerts:
            print("┌─ 告警信息 ".ljust(100, "─") + "┐")
            for alert in self.alerts[-5:]:
                level_icon = "🔴" if alert['level'] == 'CRITICAL' else "🟡"
                msg = f"{level_icon} [{alert['timestamp'][11:19]}] {alert['message']}"
                print(f"│ {msg:<97} │")
            print("└" + "─" * 99 + "┘")
            print()
        
        # 操作提示
        print("─" * 100)
        print(" 按 Ctrl+C 停止监控 | 系统每5秒自动刷新 | 完美系统为您保驾护航 ")
        print("─" * 100)
    
    def save_status_report(self):
        """保存状态报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'metrics': self.get_system_metrics(),
            'processes': self.get_process_info(),
            'data_health': self.get_data_health(),
            'schedule_status': self.get_schedule_status(),
            'alerts': self.alerts[-10:]
        }
        
        report_file = LOGS_DIR / 'system_status.json'
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        return report
    
    def run(self, interval=5):
        """运行监控"""
        self.running = True
        logger.info("完美系统监控中心已启动")
        
        try:
            while self.running:
                self.display_dashboard()
                self.save_status_report()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.running = False
            print("\n\n监控中心已停止")
            logger.info("完美系统监控中心已停止")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='完美系统监控中心')
    parser.add_argument('--interval', type=int, default=5, help='刷新间隔（秒）')
    parser.add_argument('--report', action='store_true', help='生成状态报告')
    
    args = parser.parse_args()
    
    monitor = PerfectSystemMonitor()
    
    if args.report:
        report = monitor.save_status_report()
        print("状态报告已保存到 logs/system_status.json")
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        monitor.run(args.interval)


if __name__ == "__main__":
    main()
