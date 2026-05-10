# -*- coding: utf-8 -*-
import os
import json
from datetime import datetime, timedelta

print("=" * 70)
print("日循环执行情况调查")
print("=" * 70)

# 1. 检查最近的日志文件
log_dir = "logs"
if os.path.exists(log_dir):
    logs = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
    print(f"\n[1] 最近日志文件 (共 {len(logs)} 个):")
    for f in logs[-15:]:
        fpath = os.path.join(log_dir, f)
        size = os.path.getsize(fpath)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        print(f"  {f:40s} | {size/1024:7.1f}KB | {mtime.strftime('%m-%d %H:%M')}")

# 2. 检查昨晚 22:00 左右的日志内容
print(f"\n[2] 查找昨晚 22:00 前后的日志:")
target_date = "2026-05-08"
for f in os.listdir(log_dir):
    if not f.endswith('.log'):
        continue
    fpath = os.path.join(log_dir, f)
    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
    if mtime.strftime('%Y-%m-%d') == target_date:
        print(f"\n  >>> 检查: {f} (修改时间: {mtime.strftime('%H:%M:%S')})")
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            # 找 22: 附近的内容
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '22:' in line or '22 :' in line:
                    start = max(0, i-2)
                    end = min(len(lines), i+5)
                    print(f"    行 {i+1}: {line.strip()[:100]}")
        except Exception as e:
            print(f"    读取失败: {e}")

# 3. 检查调度器状态文件
print(f"\n[3] 调度器状态文件:")
status_files = [
    "models/scheduler_state.json",
    "models/auto_scheduler_state.json",
    "data/scheduler_status.json",
]
for sf in status_files:
    if os.path.exists(sf):
        mtime = datetime.fromtimestamp(os.path.getmtime(sf))
        print(f"  {sf} | 修改: {mtime.strftime('%m-%d %H:%M')}")
        try:
            with open(sf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"    内容摘要: {json.dumps(data, ensure_ascii=False)[:200]}")
        except Exception as e:
            print(f"    读取失败: {e}")
    else:
        print(f"  {sf} | 不存在")

# 4. 检查 auto_scheduler 是否在运行
print(f"\n[4] 进程检查:")
import subprocess
try:
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'], 
                        capture_output=True, text=True, shell=True)
    lines = result.stdout.strip().split('\n')
    py_processes = [l for l in lines if 'python' in l.lower()]
    print(f"  Python 进程数: {len(py_processes)}")
    for p in py_processes[:5]:
        print(f"    {p[:100]}")
except Exception as e:
    print(f"  检查失败: {e}")

# 5. 检查 suggestion_history 的生成时间
print(f"\n[5] suggestion_history.json 分析:")
hist_file = "models/suggestion_history.json"
if os.path.exists(hist_file):
    mtime = datetime.fromtimestamp(os.path.getmtime(hist_file))
    print(f"  修改时间: {mtime.strftime('%m-%d %H:%M:%S')}")
    with open(hist_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    timestamps = [r.get('timestamp', '') for r in data if r.get('timestamp')]
    if timestamps:
        print(f"  最早记录: {min(timestamps)}")
        print(f"  最晚记录: {max(timestamps)}")

print("\n" + "=" * 70)
