import pickle
import json

# 读取工作流状态文件
try:
    with open('logs/workflow_state.pkl', 'rb') as f:
        state = pickle.load(f)
    
    print('=== 工作流状态检查 ===')
    print('Workflow status:', state.get('workflow_status'))
    print('Current task:', state.get('current_task'))
    print('Missed tasks:', state.get('missed_tasks', []))
    
    print('\n=== 任务状态 ===')
    tasks = state.get('tasks', {})
    for task_name, task_info in tasks.items():
        status = task_info.get('status')
        is_missed = task_info.get('is_missed', False)
        last_executed = task_info.get('last_executed_time', 'N/A')
        print(f'  {task_name}: status={status}, is_missed={is_missed}, last_executed={last_executed}')
    
    print('\n=== 任务顺序 ===')
    # 检查是否有 task_order
    if hasattr(state, 'task_order'):
        print('Task order:', state.task_order)
    elif 'task_order' in state:
        print('Task order:', state['task_order'])
    else:
        print('Task order: Not found')
        
except Exception as e:
    print('Error reading workflow state:', e)
    import traceback
    traceback.print_exc()