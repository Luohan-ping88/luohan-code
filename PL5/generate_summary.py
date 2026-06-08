#!/usr/bin/env python3
import json
import datetime
import os


def load_task_history():
    task_history_path = "logs/task_history_v8.json"
    if os.path.exists(task_history_path):
        with open(task_history_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_scheduler_status():
    status_path = "logs/scheduler_v8_status.json"
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_system_log():
    log_path = "logs/system.log"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            return f.readlines()[-500:]  # Last 500 lines
    return []


def generate_summary():
    print("=" * 80)
    print("PL5 日循环任务执行摘要")
    print("=" * 80)
    print(f"生成时间: {datetime.datetime.now().isoformat()}")
    print()
    
    # 1. Scheduler status
    status = load_scheduler_status()
    print("【调度器状态】")
    if status:
        print(f"  最后运行: {status.get('last_run', '未知')}")
        print(f"  当前任务: {status.get('current_task', '无')}")
        print(f"  学习进度: {status.get('learning_progress', '0')}%")
        print(f"  最后成功: {status.get('last_successful_run', '无')}")
    print()
    
    # 2. Task history summary
    history = load_task_history()
    print("【任务历史摘要】")
    if history:
        # Find latest tasks
        latest_start = max(task.get("start_time", "") for task in history if task.get("start_time"))
        
        # Filter tasks from last run
        latest_tasks = []
        for task in reversed(history):
            task_time = task.get("start_time", "")
            if task_time and task_time >= latest_start.split("T")[0]:
                latest_tasks.append(task)
        
        # Reverse to get chronological order
        latest_tasks = list(reversed(latest_tasks))
        
        # Group by task name and status
        status_counts = {}
        task_stats = {}
        
        for task in latest_tasks:
            name = task.get("task_name", "未知")
            status = task.get("status", "未知")
            
            if name not in task_stats:
                task_stats[name] = {"success": 0, "failed": 0, "total": 0}
            
            task_stats[name]["total"] += 1
            if status == "SUCCESS":
                task_stats[name]["success"] += 1
            elif status == "FAILED":
                task_stats[name]["failed"] += 1
        
        # Display
        print(f"  历史总任务数: {len(history)}")
        print(f"  最新运行任务数: {len(latest_tasks)}")
        print()
        print("  各任务统计:")
        for name, stats in task_stats.items():
            print(f"    {name}:")
            print(f"      成功: {stats['success']}")
            print(f"      失败: {stats['failed']}")
            print(f"      总计: {stats['total']}")
        
        # Display latest task details
        print()
        print("  最新任务详情:")
        for task in latest_tasks[-10:]:  # Last 10
            print()
            print(f"    任务: {task.get('task_name')}")
            print(f"      状态: {task.get('status')}")
            print(f"      开始: {task.get('start_time')}")
            print(f"      结束: {task.get('end_time')}")
            print(f"      耗时: {task.get('duration', 0):.2f}秒")
            if task.get("error_message"):
                print(f"      错误: {task.get('error_message')}")
    else:
        print("  无任务历史记录")
    print()
    
    # 3. Recent logs summary
    print("【最近日志摘要】")
    logs = load_system_log()
    error_count = 0
    warning_count = 0
    info_count = 0
    
    for line in logs:
        if "ERROR" in line:
            error_count += 1
        elif "WARNING" in line:
            warning_count += 1
        elif "INFO" in line:
            info_count += 1
    
    print(f"  错误: {error_count}")
    print(f"  警告: {warning_count}")
    print(f"  信息: {info_count}")
    
    # Find unique errors
    print()
    print("  关键错误信息:")
    error_lines = [line.strip() for line in logs if "ERROR" in line]
    for error in error_lines[-10:]:
        print(f"    {error}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)) if __file__ else ".")
    generate_summary()
