import pickle

# 读取工作流状态文件
try:
    with open('logs/workflow_state.pkl', 'rb') as f:
        state = pickle.load(f)
    
    print('=== 工作流状态检查 ===')
    print('Workflow status:', state.get('workflow_status'))
    print('Current task:', state.get('current_task'))
    print()
    print('=== 任务状态 ===')
    
    tasks = state.get('tasks', {})
    completed_count = 0
    total_count = len(tasks)
    
    for task_name, task_info in tasks.items():
        status = task_info.get('status')
        print(f'  {task_name}: {status}')
        if status == 'completed':
            completed_count += 1
            last_executed = task_info.get('last_executed_time')
            if last_executed:
                print(f'    完成时间: {last_executed}')
    
    print()
    print(f'完成任务: {completed_count}/{total_count}')
    
except Exception as e:
    print('读取工作流状态失败:', e)
    import traceback
    traceback.print_exc()