import pickle
import os

# 检查工作流状态文件
state_file = 'logs/workflow_state.pkl'
if os.path.exists(state_file):
    with open(state_file, 'rb') as f:
        state = pickle.load(f)
    
    print("=== 工作流状态检查 ===")
    print(f"状态: {state.get('workflow_status')}")
    print(f"当前任务: {state.get('current_task')}")

    print("\n=== 任务列表 ===")
    tasks = state.get('tasks', {})
    completed_count = 0
    for task_name, task_info in tasks.items():
        status = task_info.get('status')
        if status == 'completed':
            completed_count += 1
        
        print(f"\n--- {task_name} ---")
        print(f"  状态: {status}")
        
        if task_info.get('error'):
            print(f"  错误: {task_info.get('error')}")
        
        if task_info.get('last_executed'):
            print(f"  最后执行: {task_info.get('last_executed')}")
    
    total_count = len(tasks)
    print(f"\n任务进度: {completed_count}/{total_count}")
