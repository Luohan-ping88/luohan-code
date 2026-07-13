# -*- coding: utf-8 -*-
"""在 auto_scheduler_v8.py 中搜索 run / run_full_pipeline / setup_schedule 方法"""
import re

with open("src/app/auto_scheduler_v8.py", "r", encoding="utf-8") as f:
    content = f.read()

print("=" * 70)
print("搜索关键方法")
print("=" * 70)

# 找所有 def 
methods = re.findall(r'^\s*def (\w+)\s*\(', content, re.MULTILINE)
print(f"\n所有方法 ({len(methods)} 个):")
for m in methods:
    print(f"  - {m}")

# 找 run / run_full_pipeline / run_once 相关
print(f"\n[run 相关方法]:")
for m in methods:
    if 'run' in m.lower():
        print(f"  - {m}")

# 找 run() 方法内容
print(f"\n[run() 方法内容]:")
lines = content.split('\n')
in_run = False
run_lines = []
for i, line in enumerate(lines):
    if line.strip().startswith('def run('):
        in_run = True
    elif in_run and line.strip().startswith('def '):
        break
    if in_run:
        run_lines.append(line)

for l in run_lines[:80]:  # 前80行
    print(l)

# 找 setup_schedule 内容
print(f"\n[setup_schedule() 内容]:")
in_setup = False
setup_lines = []
for i, line in enumerate(lines):
    if line.strip().startswith('def setup_schedule('):
        in_setup = True
    elif in_setup and line.strip().startswith('def '):
        break
    if in_setup:
        setup_lines.append(line)

for l in setup_lines[:100]:  # 前100行
    print(l)

print("\n" + "=" * 70)
