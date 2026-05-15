# -*- coding: utf-8 -*-
"""调查 22:00 触发后为什么 22:01 就"完成"了
核心假设：run_full_pipeline() 被调用，但任务被快速跳过"""
import os, json
from datetime import datetime, timedelta

print("=" * 70)
print("日循环任务快速完成 - 根因调查")
print("=" * 70)

# 1. 检查昨天 22:00 左右的系统日志
print("\n[1] 搜索 2026-05-08 22:00 的日志:")
log_dir = "logs"
if os.path.exists(log_dir):
    for f in os.listdir(log_dir):
        if not f.endswith('.log'):
            continue
        fpath = os.path.join(log_dir, f)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        # 检查是否是昨天 22:00 左右的日志
        if mtime.date() == (datetime.now() - timedelta(days=1)).date():
            print(f"\n  >>> {f} (修改: {mtime.strftime('%H:%M')})")
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                    lines = fh.readlines()
                # 找 22: 附近的内容
                found = False
                for i, line in enumerate(lines):
                    if '22:' in line or '22 ' in line:
                        start = max(0, i-1)
                        end = min(len(lines), i+3)
                        if not found:
                            print(f"    找到 22:xx 附近日志:")
                            found = True
                        for l in lines[start:end]:
                            print(f"    {l.rstrip()[:120]}")
                if not found:
                    # 显示最后 10 行
                    print(f"    无 22:xx 记录，最后 5 行:")
                    for l in lines[-5:]:
                        print(f"    {l.rstrip()[:120]}")
            except Exception as e:
                print(f"    读取失败: {e}")
else:
    print("  logs 目录不存在")

# 2. 检查 scheduler_v8_status.json
print("\n[2] 调度器状态文件:")
status_file = "logs/scheduler_v8_status.json"
if os.path.exists(status_file):
    mtime = datetime.fromtimestamp(os.path.getmtime(status_file))
    print(f"  修改时间: {mtime.strftime('%m-%d %H:%M:%S')}")
    with open(status_file, 'r', encoding='utf-8') as f:
        status = json.load(f)
    print(f"  内容: {json.dumps(status, ensure_ascii=False)[:500]}")
else:
    print(f"  {status_file} 不存在")

# 3. 检查 task_history_v8 (任务执行历史)
print("\n[3] 任务执行历史:")
hist_file = "logs/task_history_v8.json"
if os.path.exists(hist_file):
    mtime = datetime.fromtimestamp(os.path.getmtime(hist_file))
    print(f"  修改时间: {mtime.strftime('%m-%d %H:%M:%S')}")
    with open(hist_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    print(f"  总记录数: {len(history)}")
    # 找昨天 22:00 左右的记录
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    yesterday_records = [r for r in history if yesterday in r.get('start_time', '')]
    print(f"  昨天记录数: {len(yesterday_records)}")
    for r in yesterday_records[:10]:
        start = r.get('start_time', 'N/A')
        end = r.get('end_time', 'N/A')
        status = r.get('status', 'N/A')
        duration = r.get('duration', 'N/A')
        name = r.get('task_name', 'N/A')
        print(f"    {name}: {status} | {start[11:16] if len(start)>11 else start} | {duration}s")
else:
    print(f"  {hist_file} 不存在")

# 4. 检查 workflow_state (orchestrator 状态)
print("\n[4] Workflow 状态:")
wf_file = "logs/workflow_state.pkl"
if os.path.exists(wf_file):
    import pickle
    mtime = datetime.fromtimestamp(os.path.getmtime(wf_file))
    print(f"  修改时间: {mtime.strftime('%m-%d %H:%M:%S')}")
    try:
        with open(wf_file, 'rb') as f:
            wf_state = pickle.load(f)
        print(f"  Workflow 状态: {wf_state.get('status', 'N/A')}")
        print(f"  当前周期: {wf_state.get('cycle_date', 'N/A')}")
        tasks_state = wf_state.get('tasks', {})
        print(f"  任务数: {len(tasks_state)}")
        for name, t in list(tasks_state.items())[:5]:
            print(f"    {name}: {t.get('status', 'N/A')}")
    except Exception as e:
        print(f"  读取失败: {e}")
else:
    print(f"  {wf_file} 不存在")

print("\n" + "=" * 70)
