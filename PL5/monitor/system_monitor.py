"""
系统监控工具
实时查看系统运行状态
"""

import os
import sys
import time
import psutil
import json
from datetime import datetime
from pathlib import Path
import logging

# 将项目根目录加入路径（monitor/ 是根目录的子目录）
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.core.config import setup_logging, BASE_DIR, LOGS_DIR, MODELS_DIR

logger = setup_logging(__name__)


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self):
        self.project_dir = BASE_DIR  # 正确指向项目根目录
        
    def check_system_status(self):
        """检查系统状态"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'system_running': False,
            'python_processes': [],
            'data_status': {},
            'log_status': {},
            'last_run': None,
            'next_run': None
        }
        
        # 检查Python进程
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] in ('python.exe', 'python'):
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if 'PL5' in cmdline or 'pl5' in cmdline or 'auto_scheduler' in cmdline:
                        status['python_processes'].append({
                            'pid': proc.info['pid'],
                            'cmdline': cmdline[:100]
                        })
                        status['system_running'] = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # 检查数据状态
        data_file = self.project_dir / 'data' / 'processed' / 'pl5_processed.csv'
        if data_file.exists():
            status['data_status'] = {
                'exists': True,
                'size_mb': round(data_file.stat().st_size / 1024 / 1024, 2),
                'last_modified': datetime.fromtimestamp(data_file.stat().st_mtime).isoformat()
            }
        
        # 检查日志状态
        log_file = LOGS_DIR / 'pl5_system.log'
        if log_file.exists():
            status['log_status'] = {
                'exists': True,
                'size_kb': round(log_file.stat().st_size / 1024, 2),
                'last_modified': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
            }
        
        # 检查学习历史
        history_file = MODELS_DIR / 'learning_history.json'
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    evaluations = data.get('evaluations', [])
                    if evaluations:
                        status['last_run'] = evaluations[-1].get('timestamp')
                        status['evaluation_count'] = len(evaluations)
                        status['avg_accuracy'] = sum(e.get('accuracy', 0) for e in evaluations) / len(evaluations)
            except Exception:
                pass
        
        return status
    
    def display_status(self):
        """显示系统状态"""
        status = self.check_system_status()
        
        print("=" * 70)
        print("排列五智能自动化分析系统 - 状态监控")
        print("=" * 70)
        print(f"检查时间: {status['timestamp']}")
        print()
        
        # 系统运行状态
        print("【系统运行状态】")
        if status['system_running']:
            print(f"  ✅ 系统正在运行")
            print(f"  📊 Python进程数: {len(status['python_processes'])}")
            for proc in status['python_processes']:
                print(f"     - PID {proc['pid']}: {proc['cmdline'][:50]}...")
        else:
            print(f"  ❌ 系统未运行")
            print(f"  💡 启动命令: 双击 '启动完整系统.bat'")
        print()
        
        # 数据状态
        print("【数据状态】")
        if status['data_status'].get('exists'):
            print(f"  ✅ 数据文件存在")
            print(f"  📁 大小: {status['data_status']['size_mb']} MB")
            print(f"  🕐 最后更新: {status['data_status']['last_modified'][:19]}")
        else:
            print(f"  ❌ 数据文件不存在")
        print()
        
        # 日志状态
        print("【日志状态】")
        if status['log_status'].get('exists'):
            print(f"  ✅ 日志文件存在")
            print(f"  📁 大小: {status['log_status']['size_kb']} KB")
            print(f"  🕐 最后更新: {status['log_status']['last_modified'][:19]}")
        else:
            print(f"  ❌ 日志文件不存在")
        print()
        
        # 运行历史
        print("【运行历史】")
        if status.get('evaluation_count'):
            print(f"  📈 评估记录数: {status['evaluation_count']} 条")
            print(f"  🎯 平均准确率: {status.get('avg_accuracy', 0):.2%}")
            if status.get('last_run'):
                print(f"  🕐 最后运行: {status['last_run'][:19]}")
        else:
            print(f"  📭 暂无运行记录")
        print()
        
        # 系统资源
        print("【系统资源】")
        print(f"  CPU使用率: {psutil.cpu_percent()}%")
        print(f"  内存使用率: {psutil.virtual_memory().percent}%")
        # 兼容 Windows（使用项目所在盘符）和 Linux/macOS
        _disk_path = str(self.project_dir.anchor)
        print(f"  磁盘使用率: {psutil.disk_usage(_disk_path).percent}%")
        print()
        
        print("=" * 70)
        print("监控完成")
        print("=" * 70)
    
    def watch_logs(self, lines=20):
        """查看日志 — V6.0: 统一使用 LOGS_DIR / pl5_system.log"""
        log_file = LOGS_DIR / 'pl5_system.log'
        if not log_file.exists():
            print("❌ 日志文件不存在")
            return
        
        print("=" * 70)
        print(f"最近 {lines} 行日志")
        print("=" * 70)
        print()
        
        # 读取最后N行
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:]
            for line in last_lines:
                print(line.rstrip())
        
        print()
        print("=" * 70)
    
    def real_time_monitor(self, interval=5):
        """实时监控"""
        print("=" * 70)
        print("实时监控系统 (按 Ctrl+C 停止)")
        print("=" * 70)
        print()
        
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                self.display_status()
                print(f"\n刷新间隔: {interval}秒 | 按 Ctrl+C 停止")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n监控已停止")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='系统监控工具')
    parser.add_argument('--status', action='store_true', help='显示当前状态')
    parser.add_argument('--logs', type=int, default=20, help='查看最近N行日志')
    parser.add_argument('--watch', action='store_true', help='实时监控模式')
    parser.add_argument('--interval', type=int, default=5, help='刷新间隔（秒）')
    
    args = parser.parse_args()
    
    monitor = SystemMonitor()
    
    if args.watch:
        monitor.real_time_monitor(args.interval)
    elif args.logs:
        monitor.watch_logs(args.logs)
    else:
        monitor.display_status()


if __name__ == "__main__":
    main()
