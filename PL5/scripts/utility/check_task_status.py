import json
state = json.load(open('e:/PL5/logs/workflow_state.json', encoding='utf-8'))
for task_name, task in state['tasks'].items():
    print(f'{task_name:45s} status={task["status"]:12s} last_exec={task.get("last_executed_time", "从未")}')
print()
print(f'current_task: {state["current_task"]}')
print(f'workflow_status: {state["workflow_status"]}')
