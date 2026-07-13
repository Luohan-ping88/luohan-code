# -*- coding: utf-8 -*-
"""提取 run_full_pipeline 方法内容"""
import re

with open("src/app/auto_scheduler_v8.py", "r", encoding="utf-8") as f:
    content = f.read()

lines = content.split('\n')
in_method = False
method_lines = []
for i, line in enumerate(lines):
    if line.strip().startswith('def run_full_pipeline('):
        in_method = True
        continue
    if in_method and line.strip().startswith('def '):
        break
    if in_method:
        method_lines.append(line)

print("=" * 70)
print("run_full_pipeline() 方法内容")
print("=" * 70)
for l in method_lines:
    print(l)

# 也找 _execute_catchup_tasks
print("\n" + "=" * 70)
print("_execute_catchup_tasks() 方法内容（前50行）")
in_method = False
method_lines = []
for i, line in enumerate(lines):
    if line.strip().startswith('def _execute_catchup_tasks('):
        in_method = True
        continue
    if in_method and line.strip().startswith('def '):
        break
    if in_method:
        method_lines.append(line)

for l in method_lines[:50]:
    print(l)

# 找 check_intelligent_scheduling
print("\n" + "=" * 70)
print("check_intelligent_scheduling() 方法内容（前50行）")
in_method = False
method_lines = []
for i, line in enumerate(lines):
    if line.strip().startswith('def check_intelligent_scheduling('):
        in_method = True
        continue
    if in_method and line.strip().startswith('def '):
        break
    if in_method:
        method_lines.append(line)

for l in method_lines[:60]:
    print(l)
