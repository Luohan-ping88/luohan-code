import pickle
from datetime import datetime

# 读取工作流状态文件
try:
    with open('logs/workflow_state.pkl', 'rb') as f:
        state = pickle.load(f)
    
    print('=== 修复工作流状态 ===')
    
    # 重置当前任务
    state['current_task'] = None
    
    # 重置所有 pending 任务的状态为 pending，确保它们可以被执行
    tasks = state.get('tasks', {})
    
    # 检查哪些任务应该被执行
    print('当前任务状态:')
    for task_name, task_info in tasks.items():
        status = task_info.get('status')
        print(f'  {task_name}: {status}')
        
        # 确保任务依赖链中，如果前面的任务已经完成，但后面的没有完成，重置后面的
        # 这里的策略是：如果任务是 pending 或 failed，并且前置任务已经完成，那么重置为 pending
        if status in ['pending', 'failed']:
            task_info['status'] = 'pending'
            task_info['is_missed'] = True
            print(f'  重置 {task_name} 为 missed 状态')
    
    # 保存状态
    with open('logs/workflow_state.pkl', 'wb') as f:
        pickle.dump(state, f)
    
    print('\n工作流状态已修复并保存')
    
except Exception as e:
    print('修复工作流状态失败:', e)
    import traceback
    traceback.print_exc()
