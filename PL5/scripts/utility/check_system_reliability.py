#!/usr/bin/env python
"""
系统可靠性检查工具
功能：
1. 检查进程状态（auto_scheduler_v8 是否运行）
2. 读取并显示任务历史
3. 检查配置一致性（guardian_config.json）
4. 提供清晰易读的输出格式
"""
import sys
sys.path.insert(0, '.')
import psutil
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
def print_header(title: str):
    """打印标题头"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)
def print_section(title: str):
    """打印章节标题"""
    print(f"\n【{title}】")
    print("-" * 50)
def check_process_status() -> Dict[str, Any]:
    """检查进程状态（auto_scheduler_v8 是否运行）"""
    result = {
        "running": False,
        "processes": [],
        "message": ""
    } 
    print_section("进程状态检查")
    pl5_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cpu_percent', 'memory_info']):
        try:
            if proc.info['name'] == 'python.exe':
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if 'auto_scheduler_v8' in cmdline or 'auto_scheduler' in cmdline:
                    process_info = {
                        'pid': proc.info['pid'],
                        'cmdline': cmdline,
                        'start_time': datetime.fromtimestamp(proc.info['create_time']).strftime('%Y-%m-%d %H:%M:%S'),
                        'cpu_percent': proc.info['cpu_percent'],
                        'memory_mb': proc.info['memory_info'].rss / (1024 * 1024) if proc.info['memory_info'] else 0
                    }
                    pl5_processes.append(process_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if pl5_processes:
        result["running"] = True
        result["processes"] = pl5_processes
        print(f"  ✅ 发现 {len(pl5_processes)} 个 auto_scheduler_v8 进程")
        for i, proc in enumerate(pl5_processes, 1):
            print(f"    [{i}] PID: {proc['pid']}")
            print(f"        启动时间: {proc['start_time']}")
            print(f"        内存使用: {proc['memory_mb']:.1f} MB")
            print(f"        命令行: {proc['cmdline'][:60]}...")
    else:
        result["message"] = "未发现 auto_scheduler_v8 进程"
        print("  ❌ 未发现 auto_scheduler_v8 进程")
    
    return result
def read_task_history(limit: int = 10) -> Dict[str, Any]:
    """读取并显示任务历史"""
    result = {
        "exists": False,
        "history": [],
        "message": ""
    }   
    print_section("任务执行历史")  
    history_file = Path('logs/task_history_v8.pkl')
    if history_file.exists():
        result["exists"] = True
        try:
            with open(history_file, 'rb') as f:
                history = pickle.load(f)        
            result["history"] = history[-limit:] if history else []         
            if history:
                print(f"  ✅ 任务历史文件存在，共 {len(history)} 条记录")
                print(f"  最近 {min(limit, len(history))} 条记录:")
                print()
                for i, record in enumerate(reversed(result["history"]), 1):
                    status_icon = "✓" if record['status'] == 'SUCCESS' else "✗"
                    task_name = record['task_name']
                    start_time = record['start_time'][:19] if isinstance(record['start_time'], str) else str(record['start_time'])
                    duration = record.get('duration', 0)
                    
                    print(f"  [{i}] {status_icon} {task_name}")
                    print(f"      状态: {record['status']}")
                    print(f"      时间: {start_time}")
                    print(f"      耗时: {duration:.1f}秒")
                    
                    if record.get('error_message'):
                        error_msg = record['error_message']
                        if len(error_msg) > 100:
                            error_msg = error_msg[:100] + "..."
                        print(f"      错误: {error_msg}")
                    print()
            else:
                print("  ⚠️ 任务历史文件存在但为空")
        except Exception as e:
            result["message"] = f"读取任务历史失败: {e}"
            print(f"  ❌ 读取任务历史失败: {e}")
    else:
        result["message"] = "任务历史文件不存在"
        print("  ❌ 任务历史文件不存在")
    
    return result


def check_config_consistency() -> Dict[str, Any]:
    """检查配置一致性（guardian_config.json）"""
    result = {
        "exists": False,
        "config": {},
        "issues": [],
        "message": ""
    }
    
    print_section("配置一致性检查")
    
    config_file = Path('config/guardian_config.json')
    if config_file.exists():
        result["exists"] = True
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            result["config"] = config
            
            print(f"  ✅ guardian_config.json 存在")
            print()
            
            required_fields = ['enabled', 'check_interval', 'max_restarts', 'restart_window', 'main_script']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                result["issues"].append(f"缺少必需字段: {', '.join(missing_fields)}")
                print(f"  ❌ 缺少必需字段: {', '.join(missing_fields)}")
            else:
                print(f"  ✅ 所有必需字段都存在")
            
            print()
            print("  当前配置:")
            print(f"    - 守护进程启用: {config.get('enabled')}")
            print(f"    - 检查间隔: {config.get('check_interval')}秒")
            print(f"    - 最大重启次数: {config.get('max_restarts')}")
            print(f"    - 重启窗口: {config.get('restart_window')}秒")
            print(f"    - 主脚本: {config.get('main_script')}")
            
            health_check = config.get('health_check', {})
            if health_check:
                print(f"    - 健康检查启用: {health_check.get('enabled')}")
                print(f"    - CPU阈值: {health_check.get('cpu_threshold')}%")
                print(f"    - 内存阈值: {health_check.get('memory_threshold')}%")
                print(f"    - 磁盘阈值: {health_check.get('disk_threshold')}%")
            
            scheduled_tasks = config.get('scheduled_tasks', {})
            if scheduled_tasks and scheduled_tasks.get('enabled'):
                tasks = scheduled_tasks.get('tasks', [])
                print(f"    - 定时任务: {len(tasks)}个")
                for task in tasks:
                    if task.get('enabled'):
                        print(f"      * {task.get('name')}: {task.get('time')}")
            
            if not result["issues"]:
                print()
                print("  ✅ 配置一致性检查通过")
            else:
                print()
                print(f"  ❌ 发现 {len(result['issues'])} 个问题")
                
        except json.JSONDecodeError as e:
            result["issues"].append(f"JSON格式错误: {e}")
            print(f"  ❌ JSON格式错误: {e}")
        except Exception as e:
            result["issues"].append(f"读取配置失败: {e}")
            print(f"  ❌ 读取配置失败: {e}")
    else:
        result["message"] = "guardian_config.json 不存在"
        print(f"  ❌ guardian_config.json 不存在")
    
    return result


def print_summary(process_result: Dict, history_result: Dict, config_result: Dict):
    """打印总结报告"""
    print_header("系统可靠性总结")
    
    overall_status = "健康"
    issues = []
    
    if not process_result["running"]:
        overall_status = "警告"
        issues.append("auto_scheduler_v8 进程未运行")
    
    if not history_result["exists"]:
        overall_status = "警告"
        issues.append("任务历史文件不存在")
    
    if config_result["issues"]:
        overall_status = "错误"
        issues.extend(config_result["issues"])
    
    status_color = "✅" if overall_status == "健康" else "⚠️" if overall_status == "警告" else "❌"
    
    print(f"\n  系统状态: {status_color} {overall_status}")
    print()
    
    if issues:
        print("  发现的问题:")
        for i, issue in enumerate(issues, 1):
            print(f"    {i}. {issue}")
        print()
    else:
        print("  ✅ 未发现问题")
        print()
    
    print("="*80)


def main():
    """主函数"""
    print_header("PL5 系统可靠性检查工具")
    print(f"  检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    process_result = check_process_status()
    history_result = read_task_history(limit=10)
    config_result = check_config_consistency()
    
    print_summary(process_result, history_result, config_result)
    
    return 0 if not any([
        not process_result["running"],
        config_result["issues"]
    ]) else 1


if __name__ == "__main__":
    sys.exit(main())
