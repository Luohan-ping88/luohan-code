#!/usr/bin/env python3
"""
查看定时任务进度
"""

import sys
from pathlib import Path
import pickle
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.app.auto_scheduler_v8 import AutoSchedulerV8
from src.core.workflow.orchestrator import TaskStatus, WorkflowStatus


def load_workflow_state():
    """加载工作流状态"""
    state_file = Path("logs/workflow_state.pkl")
    if not state_file.exists():
        return None
    
    try:
        with open(state_file, "rb") as f:
            state = pickle.load(f)
        return state
    except Exception as e:
        print(f"加载工作流状态失败: {e}")
        return None


def load_scheduler_status():
    """加载调度器状态"""
    status_file = Path("logs/scheduler_v8_status.json")
    if not status_file.exists():
        return None
    
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"加载调度器状态失败: {e}")
        return None


def format_timedelta(td):
    """格式化时间差"""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}小时{minutes}分{seconds}秒"


def main():
    print("=" * 80)
    print("PL5 V10.0 定时任务进度查看")
    print("=" * 80)
    
    now = datetime.now()
    print(f"\n当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 工作流状态
    print("\n" + "-" * 80)
    print("1. 工作流状态")
    print("-" * 80)
    
    workflow_state = load_workflow_state()
    if workflow_state:
        print(f"  工作流状态: {workflow_state.get('workflow_status')}")
        print(f"  当前任务: {workflow_state.get('current_task')}")
        print(f"  更新时间: {workflow_state.get('updated_at')}")
        
        tasks = workflow_state.get("tasks", {})
        print("\n  任务详情:")
        
        task_order = ["data_fetch", "evaluation", "optimization", "training", "send_report"]
        for task_name in task_order:
            task = tasks.get(task_name, {})
            status = task.get("status", "unknown")
            status_icon = "✅" if status == "completed" else "🔄" if status == "in_progress" else "⏳" if status == "pending" else "❌"
            
            print(f"\n  {status_icon} {task_name}")
            print(f"     状态: {status}")
            
            if task.get("start_time"):
                print(f"     开始: {task['start_time']}")
            
            if task.get("end_time"):
                print(f"     结束: {task['end_time']}")
                
                start_dt = datetime.fromisoformat(task["start_time"])
                end_dt = datetime.fromisoformat(task["end_time"])
                duration = end_dt - start_dt
                print(f"     耗时: {format_timedelta(duration)}")
            
            if task.get("result"):
                print(f"     结果: {task['result']}")
            
            if task.get("error"):
                print(f"     错误: {task['error']}")
    else:
        print("  工作流状态文件不存在")
    
    # 2. 调度器状态
    print("\n" + "-" * 80)
    print("2. 调度器状态")
    print("-" * 80)
    
    scheduler_status = load_scheduler_status()
    if scheduler_status:
        for key, value in scheduler_status.items():
            print(f"  {key}: {value}")
    else:
        print("  调度器状态文件不存在")
    
    # 3. 定时任务配置
    print("\n" + "-" * 80)
    print("3. 定时任务配置")
    print("-" * 80)
    
    scheduler = AutoSchedulerV8()
    print(f"  数据获取: {scheduler.config.get('data_fetch_time')}")
    print(f"  评估分析: {scheduler.config.get('evaluation_time')}")
    print(f"  策略优化: {scheduler.config.get('optimization_start')}")
    print(f"  深度学习: {scheduler.config.get('training_start')}")
    print(f"  发送报告: {scheduler.config.get('email_send_time')}")
    
    # 4. 智能时间调度
    print("\n" + "-" * 80)
    print("4. 智能时间调度")
    print("-" * 80)
    
    if scheduler.time_scheduler:
        summary = scheduler.time_scheduler.get_schedule_summary()
        print(f"  策略: {summary['strategy']}")
        print(f"  距离开奖: {summary['time_to_draw']}")
        print(f"  延迟邮件: {'是' if summary['should_delay_email'] else '否'}")
        if summary['new_email_time']:
            print(f"  新邮件时间: {summary['new_email_time']}")
        print(f"  可执行任务: {summary['executable_tasks']}")
    else:
        print("  智能时间调度器未初始化")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
