import json
with open('e:/PL5/logs/workflow_state.json', 'r', encoding='utf-8') as f:
    state = json.load(f)
pending = [t for t, v in state.get('tasks', {}).items() if v.get('status') == 'pending']
completed = [t for t, v in state.get('tasks', {}).items() if v.get('status') == 'completed']
in_progress = [t for t, v in state.get('tasks', {}).items() if v.get('status') == 'in_progress']
print(f"cycle_date: {state.get('cycle_date')}")
print(f"workflow_status: {state.get('workflow_status')}")
print(f"PENDING: {len(pending)} - {pending}")
print(f"COMPLETED: {len(completed)} - {completed}")
print(f"IN_PROGRESS: {in_progress}")
print(f"current_task: {state.get('current_task')}")
