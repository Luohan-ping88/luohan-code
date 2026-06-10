"""
完整日循环任务执行器
按照既定流程依次执行所有日常任务
"""
import sys
import time
import json
import traceback
from pathlib import Path
from datetime import datetime

# 添加路径
base_dir = Path(__file__).parent
sys.path.insert(0, str(base_dir))
sys.path.insert(0, str(base_dir / "src"))

from src.app.auto_scheduler_v8 import AutoSchedulerV8

def format_duration(seconds):
    """格式化耗时显示"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}分{secs:.1f}秒"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}小时{mins}分{secs:.1f}秒"


def main():
    print("=" * 80)
    print("排列五智能分析系统 - 完整日循环任务执行")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 执行摘要记录
    cycle_start = datetime.now()
    summary = {
        "cycle_start": cycle_start.isoformat(),
        "total_tasks": 0,
        "completed_tasks": 0,
        "failed_tasks": 0,
        "skipped_tasks": 0,
        "task_details": [],
        "problems": [],
        "follow_up_items": []
    }

    try:
        print("\n[初始化] 正在启动调度器...")
        scheduler = AutoSchedulerV8()
        print("[初始化] 调度器启动完成 ✓")

        # 任务列表（完整日循环）
        task_chain = [
            "data_fetch",
            "evaluation",
            "optimization",
            "training",
            "incremental_training",
            "first_prediction_verification",
            "second_prediction_verification",
            "third_prediction_verification",
            "deep_strategy_optimization",
            "prediction_preview",
            "final_prediction",
            "final_prediction_verification",
            "pre_sale_prediction",
            "send_report",
        ]

        task_names_cn = {
            "data_fetch": "任务1: 数据获取",
            "evaluation": "任务2: 评估分析",
            "optimization": "任务3: 策略优化",
            "training": "任务4: 深度训练",
            "incremental_training": "任务5: 增量训练",
            "first_prediction_verification": "任务6: 首次预测验证",
            "second_prediction_verification": "任务7: 二次预测验证",
            "third_prediction_verification": "任务8: 三次预测验证",
            "deep_strategy_optimization": "任务9: 深度策略优化",
            "prediction_preview": "任务10: 预测预生成",
            "final_prediction": "任务11: 最终预测",
            "final_prediction_verification": "任务12: 最终预测验证",
            "pre_sale_prediction": "任务13: 售前最终预测",
            "send_report": "任务14: 发送报告",
        }

        summary["total_tasks"] = len(task_chain)
        print(f"\n[流程] 共 {len(task_chain)} 个任务将依次执行\n")

        # 依次执行每个任务
        for idx, task_name in enumerate(task_chain, 1):
            task_cn = task_names_cn.get(task_name, task_name)
            print(f"\n{'─' * 80}")
            print(f"[{idx}/{len(task_chain)}] {task_cn}")
            print(f"{'─' * 80}")

            task_start = datetime.now()
            success = False
            error_msg = None

            try:
                task_handler = scheduler._get_task_handler(task_name)
                if task_handler is None:
                    print(f"  ⚠ 任务 {task_name} 无处理器，跳过")
                    summary["skipped_tasks"] += 1
                    summary["task_details"].append({
                        "name": task_name,
                        "name_cn": task_cn,
                        "status": "SKIPPED",
                        "duration": 0,
                        "error": "无任务处理器"
                    })
                    continue

                if task_name == 'data_fetch':
                    result = scheduler.execute_with_retry(scheduler.task_fetch_data, 'data_fetch')
                    success = bool(result)
                elif task_name == 'evaluation':
                    result = scheduler.execute_with_retry(scheduler.task_evaluate, 'evaluation')
                    success = result is not None
                elif task_name == 'send_report':
                    result = scheduler.execute_with_retry(scheduler.task_send_report, 'send_report')
                    success = bool(result)
                else:
                    result = scheduler.execute_with_retry(task_handler, task_name)
                    success = bool(result) if result is not None else True

            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                print(f"  ✗ 异常: {error_msg}")
                summary["problems"].append(f"{task_cn}: {error_msg}")
                traceback.print_exc()

            task_end = datetime.now()
            duration = (task_end - task_start).total_seconds()

            if success:
                print(f"  ✓ 成功 - 耗时: {format_duration(duration)}")
                summary["completed_tasks"] += 1
                summary["task_details"].append({
                    "name": task_name,
                    "name_cn": task_cn,
                    "status": "SUCCESS",
                    "duration": round(duration, 2)
                })
            elif error_msg:
                print(f"  ✗ 失败 - 耗时: {format_duration(duration)}")
                summary["failed_tasks"] += 1
                summary["task_details"].append({
                    "name": task_name,
                    "name_cn": task_cn,
                    "status": "FAILED",
                    "duration": round(duration, 2),
                    "error": error_msg
                })
            else:
                print(f"  ✗ 未成功 - 耗时: {format_duration(duration)}")
                summary["failed_tasks"] += 1
                summary["task_details"].append({
                    "name": task_name,
                    "name_cn": task_cn,
                    "status": "FAILED",
                    "duration": round(duration, 2)
                })

    except Exception as e:
        print(f"\n[严重错误] 日循环启动失败: {e}")
        traceback.print_exc()
        summary["problems"].append(f"调度器初始化失败: {e}")

    cycle_end = datetime.now()
    total_duration = (cycle_end - cycle_start).total_seconds()
    summary["cycle_end"] = cycle_end.isoformat()
    summary["total_duration"] = round(total_duration, 2)

    # 生成后续跟进事项
    if summary["failed_tasks"] > 0:
        summary["follow_up_items"].append(
            f"有 {summary['failed_tasks']} 个任务执行失败，需要排查失败原因并重试"
        )
    if summary["skipped_tasks"] > 0:
        summary["follow_up_items"].append(
            f"有 {summary['skipped_tasks']} 个任务被跳过，需要检查任务处理器配置"
        )
    if total_duration > 1800:  # 超过30分钟
        summary["follow_up_items"].append(
            f"本次执行耗时较长（{format_duration(total_duration)}），建议评估性能瓶颈"
        )

    # 输出执行摘要
    print("\n" + "=" * 80)
    print("日循环任务执行摘要")
    print("=" * 80)
    print(f"开始时间: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"结束时间: {cycle_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {format_duration(total_duration)}")
    print(f"总任务数: {summary['total_tasks']}")
    print(f"成功: {summary['completed_tasks']}  失败: {summary['failed_tasks']}  跳过: {summary['skipped_tasks']}")
    print(f"成功率: {summary['completed_tasks']}/{summary['total_tasks']} "
          f"({(summary['completed_tasks']/summary['total_tasks']*100):.1f}%)")

    print("\n--- 各任务执行详情 ---")
    for detail in summary["task_details"]:
        icon = "✓" if detail["status"] == "SUCCESS" else \
               "⊘" if detail["status"] == "SKIPPED" else "✗"
        duration_str = format_duration(detail["duration"])
        extra = f" - {detail.get('error', '')}" if detail.get("error") else ""
        print(f"  {icon} {detail['name_cn']:20s} [{detail['status']:10s}] {duration_str}{extra}")

    if summary["problems"]:
        print("\n--- 出现的问题 ---")
        for prob in summary["problems"]:
            print(f"  ! {prob}")

    if summary["follow_up_items"]:
        print("\n--- 后续跟进事项 ---")
        for item in summary["follow_up_items"]:
            print(f"  → {item}")

    print("\n" + "=" * 80)

    # 保存摘要到文件
    summary_file = base_dir / "logs" / f"daily_cycle_summary_{cycle_start.strftime('%Y%m%d_%H%M%S')}.json"
    summary_file.parent.mkdir(exist_ok=True)
    try:
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n摘要已保存: {summary_file}")
    except Exception as e:
        print(f"\n保存摘要失败: {e}")

    print("日循环任务执行完成。")
    return summary


if __name__ == "__main__":
    main()
