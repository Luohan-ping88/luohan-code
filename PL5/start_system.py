#!/usr/bin/env python3
import psutil
import subprocess
import time
import os
import sys

print("=== PL5 系统启动脚本 ===\n")

# 1. 停止现有进程
print("1. 停止现有PL5相关进程...")
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = ' '.join(proc.info.get('cmdline') or [])
        if any(keyword in cmdline for keyword in ['auto_scheduler', 'uvicorn', 'src.ai.api']):
            proc.terminate()
            print(f"   已终止 PID={proc.info['pid']}")
    except:
        pass

time.sleep(2)
print("   完成\n")

os.chdir(r'e:\PL5')
python_exe = r'e:\PL5\venv\Scripts\python.exe'

# 2. 启动调度器（后台运行）
print("2. 启动调度器...")
scheduler_proc = subprocess.Popen(
    [python_exe, '-m', 'src.app.auto_scheduler_v8'],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
)
print(f"   调度器已启动 (后台)\n")

# 3. 启动API服务器
print("3. 启动API服务器...")
api_proc = subprocess.Popen(
    [python_exe, '-m', 'uvicorn', 'src.ai.api:app', '--host', '0.0.0.0', '--port', '8000'],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
)
print(f"   API服务器已启动 (后台)\n")

print("=== 系统启动完成 ===")
print("  - API服务: http://localhost:8000")
print("  - 仪表板: http://localhost:8000/dashboard")
print("  - 调度器: 运行中 (查看日志确认)")
