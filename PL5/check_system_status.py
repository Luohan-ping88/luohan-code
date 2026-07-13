import psutil
import os
import json
import pickle
import glob
from datetime import datetime

PL5_PATHS = ['\\PL5\\', '/PL5/', 'e:\\PL5', 'E:\\PL5']
PL5_IDS = ['auto_scheduler_v8', 'process_watchdog', 'prevent_sleep', 'pl5_intelligent_system', 'start_sentinel', 'launch_simple', 'src.app.auto_scheduler_v8']

def check_module_mode(cmdline_str):
    if not cmdline_str:
        return False
    cmdline_lower = cmdline_str.lower()
    return 'src.app.auto_scheduler_v8' in cmdline_lower and 'python' in cmdline_lower

def is_pl5(cmdline_str, proc_name):
    if not cmdline_str:
        return False
    cmdline_str_lower = cmdline_str.lower()
    is_python = 'python' in proc_name.lower() if proc_name else False
    if not is_python:
        return False
    has_id = any(pid in cmdline_str_lower for pid in PL5_IDS)
    if not has_id:
        return False
    has_path = any(p.lower() in cmdline_str_lower for p in PL5_PATHS)
    has_module_mode = check_module_mode(cmdline_str_lower)
    return has_path or has_module_mode

def check_processes():
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'memory_info']):
        try:
            info = p.info
            if info['cmdline']:
                cmdline = ' '.join(info['cmdline'])
                if is_pl5(cmdline, info['name']):
                    processes.append(p)
        except:
            pass
    return processes

def main():
    print('=' * 80)
    print('PL5系统运行状态检查')
    print('=' * 80)
    print()
    
    # 检查进程
    processes = check_processes()
    if processes:
        print(f'✅ 发现 {len(processes)} 个PL5进程在运行:')
        print()
        for i, p in enumerate(processes, 1):
            info = p.info
            cmdline = ' '.join(info['cmdline'])
            create_time = datetime.fromtimestamp(info['create_time'])
            mem = info['memory_info'].rss / 1024 / 1024 if info['memory_info'] else 0
            print(f'[{i}] PID: {info["pid"]}')
            print(f'    名称: {info["name"]}')
            print(f'    启动时间: {create_time.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'    内存: {mem:.1f} MB')
            print(f'    命令: {cmdline[:120]}...' if len(cmdline) > 120 else f'    命令: {cmdline}')
            print()
    else:
        print('❌ 未发现PL5进程在运行')
        print()
    
    print('=' * 80)
    print('系统状态文件检查')
    print('=' * 80)
    print()
    
    # 检查调度器状态
    status_file = 'logs/scheduler_v8_status.json'
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            print('✅ 调度器状态文件存在:')
            print(f'    最后更新: {status.get("last_update", "N/A")}')
            print(f'    当前状态: {status.get("status", "N/A")}')
            print(f'    当前任务: {status.get("current_task", "N/A")}')
            print()
        except Exception as e:
            print(f'❌ 读取状态文件失败: {e}')
            print()
    else:
        print('⚠️ 调度器状态文件不存在')
        print()
    
    # 检查工作流状态
    workflow_file = 'logs/workflow_state.pkl'
    if os.path.exists(workflow_file):
        try:
            with open(workflow_file, 'rb') as f:
                workflow = pickle.load(f)
            print('✅ 工作流状态文件存在:')
            print(f'    当前状态: {workflow.get("state", "N/A")}')
            if 'tasks' in workflow:
                tasks = workflow['tasks']
                done_tasks = [t for t in tasks if tasks[t].get('status') == 'completed']
                print(f'    已完成任务: {len(done_tasks)} / {len(tasks)}')
                print(f'    任务详情:')
                for task_id in sorted(tasks.keys()):
                    task = tasks[task_id]
                    status = task.get('status', 'unknown')
                    status_icon = '✅' if status == 'completed' else '🔄' if status == 'running' else '⏳'
                    print(f'        {status_icon} {task_id}: {status}')
            print()
        except Exception as e:
            print(f'❌ 读取工作流文件失败: {e}')
            print()
    else:
        print('⚠️ 工作流状态文件不存在')
        print()
    
    print('=' * 80)
    print('日志目录检查')
    print('=' * 80)
    print()
    
    log_dir = 'logs'
    if os.path.exists(log_dir):
        files = os.listdir(log_dir)
        print(f'✅ logs目录存在，包含 {len(files)} 个文件:')
        for f in sorted(files):
            file_path = os.path.join(log_dir, f)
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path) / 1024
                print(f'    {f} ({size:.1f} KB)')
        print()
        
        # 查找最新的日志文件
        log_files = glob.glob(os.path.join(log_dir, '*.log'))
        if log_files:
            latest_log = max(log_files, key=os.path.getctime)
            print(f'最新日志文件: {os.path.basename(latest_log)}')
            print()
            try:
                with open(latest_log, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        print('最后30行:')
                        for line in lines[-30:]:
                            print(f'  {line.rstrip()}')
                print()
            except Exception as e:
                print(f'  读取失败: {e}')
                print()
    else:
        print('⚠️ logs目录不存在')
        print()
    
    print('=' * 80)
    print('检查完成')
    print('=' * 80)

if __name__ == '__main__':
    main()
