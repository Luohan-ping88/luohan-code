#!/usr/bin/env python
"""检查任务执行历史"""
import sys
sys.path.insert(0, '.')

import pickle
from pathlib import Path

history_file = Path('logs/task_history_v8.pkl')
if history_file.exists():
    with open(history_file, 'rb') as f:
        history = pickle.load(f)
    print('=== 最近任务执行记录 ===')
    for record in history[-10:]:
        print(f"任务: {record['task_name']}")
        print(f"状态: {record['status']}")
        print(f"时间: {record['start_time']}")
        print(f"耗时: {record.get('duration', 0):.1f}秒")
        if record.get('error_message'):
            print(f"错误: {record['error_message'][:100]}")
        print()
else:
    print('任务历史文件不存在')
