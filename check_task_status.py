
import pickle
import json
import os

print("=" * 80)
print("检查日循环任务状态")
print("=" * 80)

# 检查 task_history
task_history_path = "/workspace/PL5/logs/task_history_v8.pkl"
if os.path.exists(task_history_path):
    print(f"\n✅ 找到任务历史: {task_history_path}")
    try:
        with open(task_history_path, 'rb') as f:
            task_history = pickle.load(f)
        print(f"   数据类型: {type(task_history)}")
        if isinstance(task_history, list):
            print(f"   任务数量: {len(task_history)}")
            if task_history:
                print("\n   最新任务:")
                latest_task = task_history[-1]
                print(f"     {latest_task}")
                # 显示最近几个任务
                print("\n   最近 10 个任务:")
                for task in reversed(task_history[-10:]):
                    print(f"     - {task}")
    except Exception as e:
        print(f"   读取失败: {e}")
else:
    print(f"\n❌ 未找到任务历史: {task_history_path}")

# 检查 workflow_state
workflow_state_path = "/workspace/PL5/logs/workflow_state.pkl"
if os.path.exists(workflow_state_path):
    print(f"\n✅ 找到工作流状态: {workflow_state_path}")
    try:
        with open(workflow_state_path, 'rb') as f:
            workflow_state = pickle.load(f)
        print(f"   数据类型: {type(workflow_state)}")
        if isinstance(workflow_state, dict):
            print(f"   键: {list(workflow_state.keys())}")
            for key, value in workflow_state.items():
                print(f"   {key}: {value}")
    except Exception as e:
        print(f"   读取失败: {e}")
else:
    print(f"\n❌ 未找到工作流状态: {workflow_state_path}")

# 检查预测文件
predictions_dir = "/workspace/PL5/logs/predictions"
print(f"\n检查预测文件: {predictions_dir}")
if os.path.exists(predictions_dir):
    files = os.listdir(predictions_dir)
    print(f"   文件: {files}")
    for f in files:
        fpath = os.path.join(predictions_dir, f)
        mtime = os.path.getmtime(fpath)
        import time
        print(f"   - {f} (修改时间: {time.ctime(mtime)})")
else:
    print("   目录不存在")

print("\n" + "=" * 80)
