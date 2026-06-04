
#!/usr/bin/env python3
import os
import sys
import time
import subprocess
from pathlib import Path

# 切换到 PL5 目录
os.chdir('/workspace/PL5')
print("=== 彻底重置工作流和日志 ===")

# 删除旧状态和日志
for f in [
    'logs/workflow_state.pkl',
    'scheduler_full.log',
    'scheduler.log',
    'crash.log',
    'performance.log'
]:
    if os.path.exists(f):
        os.remove(f)
        print(f"已删除: {f}")

# 检查当前运行的任务
print("\n当前运行中的 Python 任务:")
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
for line in result.stdout.split('\n'):
    if 'python' in line.lower() and 'grep' not in line:
        print(line)

# 启动完整日循环
print("\n=== 启动完整日循环 ===")
log_path = 'scheduler_full.log'
cmd = ['python', 'main.py', 'schedule', '--once']

with open(log_path, 'w') as log_file:
    process = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)

print(f"完整日循环已启动，PID: {process.pid}")
print(f"日志文件: /workspace/PL5/{log_path}")

# 等待一段时间查看日志
print("\n=== 等待 30 秒... ===")
time.sleep(30)

print("\n=== 初始运行日志 ===")
if os.path.exists(log_path):
    with open(log_path, 'r') as f:
        lines = f.read().split('\n')
        for line in lines[-300:]:
            print(line)
else:
    print("日志文件不存在")

print("\n=== 任务仍在后台运行 ===")
print(f"使用以下命令查看完整日志: tail -f /workspace/PL5/{log_path}")
print(f"使用以下命令检查运行状态: ps aux | grep python")
