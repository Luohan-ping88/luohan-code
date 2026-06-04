
#!/usr/bin/env python3
import os
import pickle
import sys
from datetime import datetime

os.chdir('/workspace/PL5')

print("=" * 80)
print("PL5 日循环任务状态检查")
print("=" * 80)
print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 1. 检查运行状态
print("1. 任务运行状态:")
try:
    import subprocess
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    running = False
    for line in result.stdout.split('\n'):
        if 'python main.py schedule' in line:
            print(f"   ✓ 日循环任务正在运行: {line.strip()}")
            running = True
    if not running:
        print("   ✗ 日循环任务未在运行")
except Exception as e:
    print(f"   检查失败: {e}")

print()

# 2. 检查工作流状态
print("2. 工作流状态:")
try:
    if os.path.exists('logs/workflow_state.pkl'):
        with open('logs/workflow_state.pkl', 'rb') as f:
            state = pickle.load(f)
        print(f"   ✓ 工作流状态存在")
        print(f"   状态: {state.get('workflow_status', 'N/A')}")
        print(f"   开始时间: {state.get('start_time', 'N/A')}")
        if 'end_time' in state and state['end_time']:
            print(f"   结束时间: {state.get('end_time')}")
        
        print()
        print("   各任务执行情况:")
        tasks = state.get('tasks', {})
        success_count = 0
        failed_count = 0
        pending_count = 0
        
        for task_name, task_info in tasks.items():
            status = task_info.get('status', 'N/A')
            if status == 'completed':
                success_count += 1
                status_icon = '✓'
            elif status == 'failed':
                failed_count += 1
                status_icon = '✗'
            else:
                pending_count += 1
                status_icon = '◯'
            
            error = task_info.get('error', 'N/A')
            print(f"     {status_icon} {task_name}: {status}")
            if error and error != 'N/A':
                print(f"       错误: {error}")
        
        print()
        print(f"   统计: ✓ {success_count} 成功, ✗ {failed_count} 失败, ◯ {pending_count} 待定")
    else:
        print("   ✗ 工作流状态不存在")
except Exception as e:
    print(f"   检查失败: {e}")

print()

# 3. 检查日志
print("3. 最新日志 (最后100行):")
print("-" * 80)
try:
    if os.path.exists('scheduler_full.log'):
        with open('scheduler_full.log', 'r') as f:
            lines = f.read().split('\n')
            for line in lines[-100:]:
                print(line)
    else:
        print("   日志文件不存在")
except Exception as e:
    print(f"   读取日志失败: {e}")
print("-" * 80)
print()
print("查看完整日志命令: tail -f /workspace/PL5/scheduler_full.log")
