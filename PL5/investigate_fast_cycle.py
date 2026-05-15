# -*- coding: utf-8 -*-
"""
调查 22:00 日循环为什么 1 分钟"完成"
核心问题：
1. auto_scheduler_v8.py 是否有 22:00 的任务注册？
2. 任务是否真的执行了，还是快速跳过？
3. 22:01 时系统状态是什么？
"""
import sys, os, json
sys.path.insert(0, "e:/PL5")

print("=" * 70)
print("日循环任务调度逻辑调查")
print("=" * 70)

# 1. 检查 auto_scheduler_v8.py 的任务注册
print("\n[1] auto_scheduler_v8.py 任务注册检查:")
try:
    with open("src/app/auto_scheduler_v8.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 找任务注册
    import re
    task_defs = re.findall(r'def (task_\w+)', content)
    print(f"  任务函数: {task_defs}")

    # 找调度时间
    time_patterns = re.findall(r'["\'](\d{2}:\d{2})["\']\s*:', content)
    print(f"  注册的时间点: {sorted(set(time_patterns))}")

    # 找 setup_schedule 或调度表
    if "setup_schedule" in content:
        print("  setup_schedule: 存在")
        # 提取 setup_schedule 内容
        import ast
        # 简单提取
        lines = content.split('\n')
        in_setup = False
        setup_lines = []
        for line in lines:
            if 'def setup_schedule' in line:
                in_setup = True
                continue
            if in_setup and line.strip().startswith('def '):
                break
            if in_setup:
                setup_lines.append(line)
        print("  setup_schedule 内容:")
        for l in setup_lines[:40]:
            if l.strip():
                print(f"    {l}")
    else:
        print("  setup_schedule: 不存在（可能在其他文件）")

except Exception as e:
    print(f"  读取失败: {e}")

# 2. 检查 scheduler_config.json
print("\n[2] scheduler_config.json 检查:")
cfg_path = "config/scheduler_config.json"
if os.path.exists(cfg_path):
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    print(f"  配置内容: {json.dumps(cfg, ensure_ascii=False)[:500]}")
else:
    print(f"  文件不存在: {cfg_path}")

# 3. 检查 main.py 的调度启动逻辑
print("\n[3] main.py 调度启动检查:")
try:
    with open("main.py", "r", encoding="utf-8") as f:
        main_content = f.read()
    if "auto_scheduler" in main_content:
        lines = main_content.split('\n')
        for i, line in enumerate(lines):
            if 'auto_scheduler' in line or 'schedule' in line.lower():
                print(f"  L{i+1}: {line.strip()[:100]}")
except Exception as e:
    print(f"  读取失败: {e}")

# 4. 检查系统昨日是否有训练
print("\n[4] 训练活动检查:")
model_path = "models/enhanded_predictor_v10.pkl"
if os.path.exists(model_path):
    import datetime
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(model_path))
    print(f"  模型最后修改: {mtime.strftime('%m-%d %H:%M:%S')}")
    print(f"  距现在: {(datetime.datetime.now() - mtime).total_seconds()/3600:.1f} 小时")

# 检查训练日志
log_dir = "logs"
if os.path.exists(log_dir):
    for f in os.listdir(log_dir):
        if 'train' in f.lower() or 'learn' in f.lower():
            fpath = os.path.join(log_dir, f)
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
            if '2026-05-08' in str(mtime) or '2026-05-09' in str(mtime):
                print(f"  训练相关日志: {f} | {mtime.strftime('%H:%M')}")

# 5. 检查 data_version.json 确认数据是否更新
print("\n[5] 数据版本检查:")
dv_path = "models/data_version.json"
if os.path.exists(dv_path):
    with open(dv_path, "r", encoding="utf-8") as f:
        dv = json.load(f)
    print(f"  latest_period: {dv.get('latest_period')}")
    print(f"  last_update: {dv.get('last_update', 'N/A')}")
    print(f"  record_count: {dv.get('record_count')}")

print("\n" + "=" * 70)
