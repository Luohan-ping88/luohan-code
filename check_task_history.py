
import pickle
import os
from datetime import datetime

os.chdir('/workspace/PL5')

print("=== 检查任务历史 ===")
task_history_path = 'logs/task_history_v8.pkl'
if os.path.exists(task_history_path):
    with open(task_history_path, 'rb') as f:
        task_history = pickle.load(f)
    print(f"✓ 任务历史已加载，共 {len(task_history)} 条记录")
    print("\n=== 最近 30 条记录 ===")
    for i, record in enumerate(task_history[-30:], 1):
        print(f"{i}. {record}")
else:
    print("✗ 任务历史文件不存在")

print("\n=== 检查工作流状态 ===")
workflow_state_path = 'logs/workflow_state.pkl'
if os.path.exists(workflow_state_path):
    with open(workflow_state_path, 'rb') as f:
        workflow_state = pickle.load(f)
    print("✓ 工作流状态已加载")
    for k, v in workflow_state.items():
        print(f"  {k}: {v}")
else:
    print("✗ 工作流状态文件不存在")
