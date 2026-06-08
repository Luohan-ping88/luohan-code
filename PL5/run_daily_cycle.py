#!/usr/bin/env python
"""
自动运行完整的日循环任务脚本
生成详细的执行摘要
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.app.auto_scheduler_v8 import AutoSchedulerV8
from src.core.utils.logger import logger


def main():
    """主函数 - 运行完整日循环并生成摘要"""
    print("=" * 80)
    print("PL5 日循环任务自动执行脚本")
    print("=" * 80)
    
    # 记录开始时间
    overall_start_time = datetime.now()
    summary_data = {
        "execution_date": overall_start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "tasks": [],
        "overall_result": None,
        "total_duration_seconds": 0.0
    }
    
    try:
        # 初始化调度器
        print("正在初始化自动调度器...")
        scheduler = AutoSchedulerV8()
        print("调度器初始化成功!")
        
        # 运行完整流程
        print("\n开始执行完整的日循环任务...")
        success = scheduler.run_full_pipeline()
        
        # 计算总耗时
        overall_end_time = datetime.now()
        total_duration = (overall_end_time - overall_start_time).total_seconds()
        summary_data["total_duration_seconds"] = round(total_duration, 2)
        summary_data["overall_result"] = "SUCCESS" if success else "FAILED"
        
        # 收集任务历史
        print("\n正在收集任务执行历史...")
        task_history = scheduler.history_manager.get_task_history(limit=20)
        
        # 构建任务摘要
        for task in task_history:
            summary_data["tasks"].append({
                "task_name": task.get("task_name"),
                "status": task.get("status"),
                "start_time": task.get("start_time"),
                "end_time": task.get("end_time"),
                "duration_seconds": round(task.get("duration", 0), 2) if task.get("duration") else 0,
                "error_message": task.get("error_message")
            })
        
        # 保存摘要
        summary_path = Path("logs") / f"daily_cycle_summary_{overall_start_time.strftime('%Y%m%d_%H%M%S')}.json"
        summary_path.parent.mkdir(exist_ok=True)
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        
        # 打印摘要
        print("\n" + "=" * 80)
        print("日循环任务执行摘要")
        print("=" * 80)
        print(f"执行时间: {summary_data['execution_date']}")
        print(f"总耗时: {total_duration:.2f} 秒")
        print(f"总体结果: {summary_data['overall_result']}")
        print(f"\n任务详细信息:")
        
        success_count = 0
        failed_count = 0
        for task in summary_data["tasks"]:
            status_icon = "✓" if task["status"] == "SUCCESS" else "✗"
            print(f"  {status_icon} {task['task_name']:40s} - {task['status']:10s} ({task['duration_seconds']:.2f}s)")
            if task["status"] == "SUCCESS":
                success_count += 1
            elif task["status"] == "FAILED":
                failed_count += 1
                if task["error_message"]:
                    print(f"      错误: {task['error_message']}")
        
        print(f"\n统计:")
        print(f"  成功: {success_count}")
        print(f"  失败: {failed_count}")
        print(f"  摘要已保存至: {summary_path}")
        print("=" * 80)
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
