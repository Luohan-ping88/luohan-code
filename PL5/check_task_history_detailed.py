#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pickle
from pathlib import Path

history_file = Path("logs/task_history_v8.pkl")

if history_file.exists():
    with open(history_file, 'rb') as f:
        data = pickle.load(f)
    
    print(f"总任务数: {len(data)}")
    print("=" * 100)
    
    if data:
        print("最近15个任务详情:")
        print("=" * 100)
        
        for i, r in enumerate(data[-15:], 1):
            print(f"\n[{i}] 任务: {r['task_name']}")
            print(f"    状态: {r['status']}")
            print(f"    开始: {r.get('start_time', 'N/A')}")
            print(f"    结束: {r.get('end_time', 'N/A')}")
            if 'error' in r and r['error']:
                print(f"    错误: {r['error'][:200]}")
else:
    print("任务历史文件不存在")
