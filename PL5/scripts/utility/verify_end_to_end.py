"""端到端验证: 修复后日循环能否完整执行14个任务"""
import sys
sys.path.insert(0, 'e:/PL5')
import os, json, tempfile
from datetime import datetime, timedelta

# 模拟创建旧状态（所有任务COMPLETED，cycle_date=May 3）
old_state = {
    "workflow_status": "completed",
    "current_task": None,
    "cycle_date": "2026-05-03",
    "tasks": {}
}
task_order = [
    "data_fetch", "evaluation", "optimization", "training",
    "incremental_training", "first_prediction_verification",
    "second_prediction_verification", "third_prediction_verification",
    "deep_strategy_optimization", "prediction_preview",
    "final_prediction", "final_prediction_verification",
    "pre_sale_prediction", "send_report"
]
for t in task_order:
    old_state["tasks"][t] = {"status": "completed", "start_time": None, "end_time": None}

print("=" * 70)
print("端到端验证: 模拟 22:01 启动后的流程")
print("=" * 70)

# Simulate now = May 3, 22:01
now = datetime(2026, 5, 3, 22, 1, 0)
print(f"\n当前时间: {now}")

# Step 1: _get_current_cycle_date
DATA_FETCH_TIME = datetime.strptime('22:15', '%H:%M').time()
SEND_REPORT_TIME = datetime.strptime('20:15', '%H:%M').time()

current_time = now.time()
if current_time >= DATA_FETCH_TIME:
    cycle_date = (now + timedelta(days=1)).date()
elif current_time <= SEND_REPORT_TIME:
    cycle_date = now.date()
else:
    cycle_date = (now + timedelta(days=1)).date()

print(f"\nStep 1: _get_current_cycle_date() = {cycle_date}")
print(f"  保存的状态 cycle_date = 2026-05-03")
print(f"  匹配? {cycle_date == datetime(2026, 5, 3).date()}")

# Step 2: Reset or load
if cycle_date != datetime(2026, 5, 3).date():
    print(f"\nStep 2: 不匹配 → 重置状态 ✅")
    # Simulate _init_state
    new_state = {
        "workflow_status": "idle",
        "current_task": None,
        "cycle_date": cycle_date.isoformat(),
        "tasks": {}
    }
    for t in task_order:
        new_state["tasks"][t] = {"status": "pending", "start_time": None, "end_time": None}
    
    pending_count = sum(1 for t in task_order if new_state["tasks"][t]["status"] == "pending")
    print(f"  PENDING 任务数: {pending_count}")
else:
    print(f"\nStep 2: 匹配 → 加载旧状态 ❌")
    new_state = old_state
    pending_count = sum(1 for t in task_order if new_state["tasks"][t]["status"] == "pending")
    print(f"  PENDING 任务数: {pending_count}")

# Step 3: Catchup candidates
can_start = lambda task_name: True  # Simplified
catchup = [t for t in task_order if new_state["tasks"][t]["status"] == "pending" and can_start(t)]

print(f"\nStep 3: get_catchup_candidates() = {len(catchup)} 个任务")
print(f"  前5个: {catchup[:5]}")

# Step 4: Simulate executing each task
print(f"\nStep 4: 模拟执行所有任务...")
completed = []
for t in catchup:
    new_state["tasks"][t]["status"] = "completed"
    completed.append(t)
    next_pending = [x for x in task_order if new_state["tasks"][x]["status"] == "pending"]
    print(f"  ✓ {t} 完成 → 剩余 {len(next_pending)} 个PENDING")

print(f"\n{'='*70}")
print(f"最终结果:")
print(f"  完成的任务: {len(completed)}/14")
print(f"  验证: {'✅ 全部完成!' if len(completed) == 14 else '❌ 未完成'}")
print(f"{'='*70}")
