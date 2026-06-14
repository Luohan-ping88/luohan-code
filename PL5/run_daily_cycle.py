"""
日循环任务自动执行入口 V10.3+
按照既定的日循环流程，依次执行所有日常任务步骤
涵盖完整佐证链：数据获取 -> 评估 -> 策略优化 -> 深度训练
               -> 增量训练(早/中/下午) -> 多次佐证
               -> 深度策略优化 -> 预测预生成 -> 最终预测
               -> 最终预测验证 -> 售前预测 -> 发送报告
"""
import sys
import json
import time
import traceback
from datetime import datetime
from pathlib import Path

base_dir = Path(__file__).parent
sys.path.insert(0, str(base_dir))

from src.app.auto_scheduler_v8 import AutoSchedulerV8


def execute_daily_cycle():
    print("\n" + "=" * 80)
    print("       PL5 日循环任务自动执行  V10.3+")
    print("       执行时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 80)

    cycle_start = datetime.now()
    task_results = []
    completed_count = 0
    failed_count = 0
    skipped_count = 0
    errors = []

    # 1. 初始化调度器
    print("\n[步骤0] 初始化 AutoSchedulerV8 ...")
    init_start = datetime.now()
    try:
        scheduler = AutoSchedulerV8()
        init_duration = (datetime.now() - init_start).total_seconds()
        print(f"  ✓ 调度器初始化成功 (耗时 {init_duration:.1f}s)")
        print(f"  ✓ 注册任务数: {len(scheduler.custom_tasks)}")
        print(f"  ✓ 任务列表: {', '.join(scheduler.custom_tasks)}")
    except Exception as e:
        print(f"  ✗ 调度器初始化失败: {e}")
        traceback.print_exc()
        return _build_summary(cycle_start, [], 0, 0, 1, [f"调度器初始化失败: {e}"])

    # 2. 逐个执行日循环中的每个子任务
    print("\n" + "-" * 80)
    print("开始执行日循环完整流程")
    print("-" * 80)

    for idx, task_name in enumerate(scheduler.custom_tasks, start=1):
        task_start = datetime.now()
        print(f"\n[{idx}/{len(scheduler.custom_tasks)}] 正在执行: {task_name}")
        print(f"      开始时间: {task_start.strftime('%H:%M:%S')}")

        # 查找任务处理器
        display_name, handler = scheduler.task_map.get(task_name, (task_name, None))

        if handler is None:
            print(f"      ⚠ 未找到处理器，跳过")
            task_results.append({
                "index": idx,
                "task_name": task_name,
                "display_name": display_name,
                "status": "SKIPPED",
                "reason": "no_handler",
                "duration_sec": 0,
                "timestamp": task_start.isoformat(),
            })
            skipped_count += 1
            continue

        try:
            # 使用调度器的重试机制执行
            if task_name == 'data_fetch':
                result = scheduler.execute_with_retry(scheduler.task_fetch_data, 'data_fetch')
            elif task_name == 'evaluation':
                result = scheduler.execute_with_retry(scheduler.task_evaluate, 'evaluation')
                result = result is not None and isinstance(result, tuple)
            elif task_name == 'send_report':
                result = scheduler.execute_with_retry(scheduler.task_send_report, 'send_report')
            else:
                result = scheduler.execute_with_retry(handler, task_name)

            task_duration = (datetime.now() - task_start).total_seconds()

            if result or (result is None and task_name in ('optimization',)):
                status = "SUCCESS"
                completed_count += 1
                print(f"      ✓ 成功 (耗时 {task_duration:.1f}s)")
            else:
                status = "FAILED"
                failed_count += 1
                errors.append(f"{task_name}: 返回结果为 {result!r}")
                print(f"      ✗ 失败 (耗时 {task_duration:.1f}s)")

            task_results.append({
                "index": idx,
                "task_name": task_name,
                "display_name": display_name,
                "status": status,
                "duration_sec": round(task_duration, 2),
                "timestamp": task_start.isoformat(),
            })

        except Exception as e:
            task_duration = (datetime.now() - task_start).total_seconds()
            failed_count += 1
            err_msg = f"{task_name}: {type(e).__name__}: {str(e)}"
            errors.append(err_msg)
            print(f"      ✗ 异常: {type(e).__name__}: {str(e)} (耗时 {task_duration:.1f}s)")
            task_results.append({
                "index": idx,
                "task_name": task_name,
                "display_name": display_name,
                "status": "FAILED",
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_sec": round(task_duration, 2),
                "timestamp": task_start.isoformat(),
            })

    # 3. 保存任务历史
    total_duration = (datetime.now() - cycle_start).total_seconds()

    # 保存执行摘要
    summary = {
        "execution_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "total_duration_sec": round(total_duration, 2),
        "total_tasks": len(scheduler.custom_tasks),
        "completed": completed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "tasks": task_results,
        "errors": errors,
    }

    summary_path = base_dir / "logs" / "daily_cycle_summary.json"
    summary_path.parent.mkdir(exist_ok=True)
    try:
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n  ✓ 执行摘要已保存至: {summary_path}")
    except Exception as e:
        print(f"\n  ⚠  保存摘要失败: {e}")

    # 4. 打印最终摘要
    print("\n" + "=" * 80)
    print("                       日循环任务执行摘要")
    print("=" * 80)
    print(f"  执行时间: {summary['execution_time']}")
    print(f"  总耗时: {total_duration:.1f} 秒 ({total_duration/60:.1f} 分钟)")
    print(f"  任务总数: {len(scheduler.custom_tasks)}")
    print(f"  成功: {completed_count} | 失败: {failed_count} | 跳过: {skipped_count}")
    print("-" * 80)

    for r in task_results:
        icon = "✓" if r["status"] == "SUCCESS" else ("⊘" if r["status"] == "SKIPPED" else "✗")
        line = f"  {icon} [{r['index']:02d}] {r['task_name']:<28} {r['status']:<10}  {r['duration_sec']:.1f}s"
        if r.get("error"):
            line += f"  (错误: {r['error'][:60]})"
        print(line)

    if errors:
        print("-" * 80)
        print("  出现的问题:")
        for err in errors:
            print(f"    ! {err}")

    print("=" * 80)
    print(f"  执行结果: {'全部成功 ✓' if failed_count == 0 else f'存在失败任务 ({failed_count}) ✗'}")
    print("=" * 80)

    return summary


def _build_summary(cycle_start, task_results, completed, failed, skipped, errors):
    total_duration = (datetime.now() - cycle_start).total_seconds()
    summary = {
        "execution_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "total_duration_sec": round(total_duration, 2),
        "total_tasks": 0,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "tasks": task_results,
        "errors": errors,
    }
    print(f"\n  执行失败，总耗时 {total_duration:.1f}s")
    print(f"  错误: {'; '.join(errors)}")
    return summary


if __name__ == "__main__":
    try:
        summary = execute_daily_cycle()
        sys.exit(0 if summary["failed"] == 0 else 1)
    except KeyboardInterrupt:
        print("\n  ! 用户中断执行")
        sys.exit(130)
    except Exception as e:
        print(f"\n  ! 执行入口异常: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(2)
