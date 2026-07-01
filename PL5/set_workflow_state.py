#!/usr/bin/env python3
"""设置工作流状态：标记前4个任务（data_fetch, evaluation, optimization, training）为已完成"""
import sys
import os
import json
import pickle
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

state = {
    "workflow_status": "idle",
    "tasks": {},
    "current_task": None,
    "start_time": datetime.now().isoformat(),
    "end_time": None,
    "updated_at": datetime.now().isoformat(),
    "cycle_date": datetime.now().date().isoformat(),
    "last_scheduled_time": None,
    "missed_tasks": []
}

task_order = [
    "data_fetch", "evaluation", "optimization", "training",
    "incremental_training", "first_prediction_verification",
    "second_prediction_verification", "third_prediction_verification",
    "deep_strategy_optimization", "prediction_preview",
    "final_prediction", "final_prediction_verification",
    "pre_sale_prediction", "send_report",
]

completed_tasks = {"data_fetch", "evaluation", "optimization", "training"}

for task in task_order:
    if task in completed_tasks:
        state["tasks"][task] = {
            "status": "completed",
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "result": "ok",
            "error": None,
            "retry_count": 0,
            "last_executed_time": datetime.now().isoformat(),
            "is_missed": False
        }
    else:
        state["tasks"][task] = {
            "status": "pending",
            "start_time": None,
            "end_time": None,
            "result": None,
            "error": None,
            "retry_count": 0,
            "last_executed_time": None,
            "is_missed": False
        }

os.makedirs("logs", exist_ok=True)

pkl_path = "logs/workflow_state.pkl"
json_path = "logs/workflow_state.json"

with open(pkl_path, "wb") as f:
    pickle.dump(state, f)
print(f"状态已保存: {pkl_path}")

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print(f"状态已保存: {json_path}")

print("\n已完成任务:", [t for t in task_order if t in completed_tasks])
print("待执行任务:", [t for t in task_order if t not in completed_tasks])
