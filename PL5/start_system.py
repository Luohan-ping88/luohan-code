#!/usr/bin/env python3
import psutil
import subprocess
import time
import os
import sys

# 将项目根目录加入 sys.path，复用 process_guardian 的严格匹配规则
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.utils.process_guardian import _is_pl5_process_strict


def _is_pl5_process_to_stop(cmdline):
    """
    判断进程是否为需要停止的 PL5 系统进程。

    采用与 process_guardian.py 一致的三重匹配规则
    （Python进程 + PL5标识符 + PL5路径/模块模式），
    避免误杀其他项目的 uvicorn / python 服务。
    额外补充识别 PL5 自身的 API 服务（uvicorn src.ai.api:app）。
    """
    if _is_pl5_process_strict(cmdline):
        return True
    if not cmdline:
        return False
    cmdline_str = ' '.join(cmdline).lower()
    # 规则1：必须是 Python 进程
    if 'python' not in cmdline_str:
        return False
    # PL5 API 服务：必须同时包含 uvicorn 与 src.ai.api 模块，才认定为 PL5 的 API 服务
    # （其他项目的 uvicorn 不会包含 src.ai.api，故不会被误杀）
    return 'uvicorn' in cmdline_str and 'src.ai.api' in cmdline_str


print("=== PL5 系统启动脚本 ===\n")

# 1. 停止现有进程
print("1. 停止现有PL5相关进程...")
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = proc.info.get('cmdline') or []
        if _is_pl5_process_to_stop(cmdline):
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
