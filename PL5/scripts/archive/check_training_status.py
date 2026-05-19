#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import psutil
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent

print("=" * 80)
print("PL5 训练进程状态检查")
print("=" * 80)

# 1. 检查Python进程
print("\n[1] 正在运行的 Python 进程:")
print("-" * 80)

for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'create_time']):
    try:
        if proc.info['name'] in ['pythonw.exe', 'python.exe']:
            cmdline = proc.info['cmdline']
            cmd_str = ' '.join(cmdline) if cmdline else 'N/A'
            
            # 识别进程类型
            process_type = "Unknown"
            if 'auto_scheduler_v8' in cmd_str:
                process_type = "主调度器 (Main Scheduler)"
            elif 'process_watchdog' in cmd_str:
                process_type = "看门狗 (Watchdog)"
            elif 'prevent_sleep' in cmd_str:
                process_type = "防睡眠 (Prevent Sleep)"
            
            # 计算运行时间
            create_time = datetime.fromtimestamp(proc.info['create_time'])
            runtime = datetime.now() - create_time
            
            # 内存使用
            memory_mb = proc.info['memory_info'].rss / 1024 / 1024
            
            print(f"  PID: {proc.info['pid']}")
            print(f"  类型: {process_type}")
            print(f"  启动时间: {create_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  运行时间: {runtime}")
            print(f"  内存使用: {memory_mb:.2f} MB")
            print(f"  命令行: {cmd_str[:100]}..." if len(cmd_str) > 100 else f"  命令行: {cmd_str}")
            print()
            
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        continue

# 2. 检查调度器状态
print("\n[2] 调度器状态:")
print("-" * 80)
scheduler_status_file = PROJECT_ROOT / "logs" / "scheduler_v8_status.json"
if scheduler_status_file.exists():
    with open(scheduler_status_file, 'r', encoding='utf-8') as f:
        status = json.load(f)
    print(json.dumps(status, indent=4, ensure_ascii=False))
else:
    print("调度器状态文件不存在")

# 3. 检查训练信息
print("\n[3] 训练信息:")
print("-" * 80)
training_info_file = PROJECT_ROOT / "logs" / "training_info.json"
if training_info_file.exists():
    with open(training_info_file, 'r', encoding='utf-8') as f:
        info = json.load(f)
    print(json.dumps(info, indent=4, ensure_ascii=False))
else:
    print("训练信息文件不存在")

# 4. 检查看门狗状态
print("\n[4] 看门狗状态:")
print("-" * 80)
watchdog_status_file = PROJECT_ROOT / "logs" / "watchdog_status.json"
if watchdog_status_file.exists():
    with open(watchdog_status_file, 'r', encoding='utf-8') as f:
        wd_status = json.load(f)
    print(json.dumps(wd_status, indent=4, ensure_ascii=False))
else:
    print("看门狗状态文件不存在")

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)
