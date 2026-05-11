"""
Prefect部署配置 V12.0
PL5智能分析系统工作流部署 - 多智能体时间协调版

任务周期:
- 启动时间: 22:00
- 结束时间: 第二天 20:30
- 时间协调: 多智能体智能分配

使用方法:
1. 启动Prefect服务器: prefect server start --host 0.0.0.0 --port 4200
2. 部署工作流: python prefect_deploy_v12.py deploy
3. 运行工作流: python prefect_deploy_v12.py run
"""

from prefect import flow
from prefect.client.schemas.schedules import CronSchedule
from datetime import datetime, timedelta
import os
import sys

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def deploy_all():
    """部署所有工作流 - Prefect 3.7版本"""
    print("=" * 80)
    print("PL5 Prefect工作流部署 V12.0")
    print("=" * 80)
    print("任务周期: 22:00 -> 次日 20:30")
    print("时间协调: 多智能体智能时间分配")
    print("=" * 80)

    from src.core.workflow.prefect_workflow_v12 import pl5_daily_workflow, pl5_quick_workflow

    print("\n部署日循环工作流...")
    daily_schedule = CronSchedule(
        cron="0 22 * * *",  # 每天 22:00
        timezone="Asia/Shanghai"
    )
    daily_deployment = pl5_daily_workflow.to_deployment(
        name="pl5-daily-v12",
        version="12.0",
        description="PL5日循环预测工作流 V12 - 每天22:00执行，多智能体时间协调",
        schedule=daily_schedule,
        tags=["pl5", "daily", "production", "v12", "distributed"],
        work_pool_name="pl5-pool",
        work_queue_name="pl5-queue",
    )
    daily_deployment.apply()
    print("✅ 日循环工作流部署成功!")

    print("\n部署快速预测工作流...")
    quick_deployment = pl5_quick_workflow.to_deployment(
        name="pl5-quick-v12",
        version="12.0",
        description="PL5快速预测工作流 V12 - 每小时执行",
        interval=3600,
        tags=["pl5", "quick", "production", "v12", "distributed"],
        work_pool_name="pl5-pool",
        work_queue_name="pl5-queue",
    )
    quick_deployment.apply()
    print("✅ 快速预测工作流部署成功!")

    print("\n" + "=" * 80)
    print("✅ 所有工作流部署完成!")
    print("=" * 80)


def run_pl5_daily():
    """手动运行日循环工作流"""
    print("\n" + "=" * 80)
    print("手动运行 PL5 日循环工作流 V12")
    print("=" * 80)

    from src.core.workflow.prefect_workflow_v12 import pl5_daily_workflow
    result = pl5_daily_workflow()

    print("\n✅ 日循环工作流执行完成!")
    print(f"执行时间: {result.get('execution_time', 0):.2f} 秒")
    print(f"数据记录: {result.get('data_result', {}).get('record_count', 0)} 条")

    return result


def run_pl5_quick():
    """手动运行快速预测工作流"""
    print("\n" + "=" * 80)
    print("手动运行 PL5 快速预测工作流 V12")
    print("=" * 80)

    from src.core.workflow.prefect_workflow_v12 import pl5_quick_workflow
    result = pl5_quick_workflow()

    print("\n✅ 快速预测工作流执行完成!")
    print(f"数据记录: {result.get('data_result', {}).get('record_count', 0)} 条")

    return result


def show_schedule():
    """显示智能调度表"""
    print("\n" + "=" * 80)
    print("PL5 智能任务调度表")
    print("=" * 80)
    print("任务周期: 22:00 -> 次日 20:30")
    print("时间协调: 多智能体智能时间分配")
    print("=" * 80)

    from src.core.workflow.prefect_workflow_v12 import get_time_coordinator

    try:
        coord = get_time_coordinator()
        schedule = coord.calculate_schedule()
        coord.print_schedule(schedule)
    except Exception as e:
        print(f"无法生成调度表: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
PL5 Prefect工作流部署工具 V12.0

用法:
    python prefect_deploy_v12.py deploy       - 部署所有工作流
    python prefect_deploy_v12.py deploy-daily - 部署日循环工作流
    python prefect_deploy_v12.py deploy-quick - 部署快速预测工作流
    python prefect_deploy_v12.py run           - 运行日循环工作流
    python prefect_deploy_v12.py run-quick     - 运行快速预测工作流
    python prefect_deploy_v12.py schedule      - 显示智能调度表
    python prefect_deploy_v12.py server        - 启动Prefect服务器

任务周期:
    - 启动: 22:00
    - 结束: 次日 20:30
    - 时间协调: 多智能体智能分配
""")

    elif sys.argv[1] == "deploy":
        deploy_all()

    elif sys.argv[1] == "deploy-daily":
        from src.core.workflow.prefect_workflow_v12 import pl5_daily_workflow
        daily_schedule = CronSchedule(
            cron="0 22 * * *",
            timezone="Asia/Shanghai"
        )
        daily_deployment = pl5_daily_workflow.to_deployment(
            name="pl5-daily-v12",
            version="12.0",
            schedule=daily_schedule,
            tags=["pl5", "daily", "production", "v12"],
            work_pool_name="pl5-pool",
            work_queue_name="pl5-queue",
        )
        daily_deployment.apply()
        print("✅ 日循环工作流部署成功!")

    elif sys.argv[1] == "deploy-quick":
        from src.core.workflow.prefect_workflow_v12 import pl5_quick_workflow
        quick_deployment = pl5_quick_workflow.to_deployment(
            name="pl5-quick-v12",
            version="12.0",
            interval=3600,
            tags=["pl5", "quick", "production", "v12"],
            work_pool_name="pl5-pool",
            work_queue_name="pl5-queue",
        )
        quick_deployment.apply()
        print("✅ 快速预测工作流部署成功!")

    elif sys.argv[1] == "run":
        run_pl5_daily()

    elif sys.argv[1] == "run-quick":
        run_pl5_quick()

    elif sys.argv[1] == "schedule":
        show_schedule()

    elif sys.argv[1] == "server":
        print("\n启动Prefect服务器...")
        print("访问 http://localhost:4200 查看Prefect UI")
        os.system("prefect server start")

    else:
        print(f"未知命令: {sys.argv[1]}")
        print("使用 'python prefect_deploy_v12.py' 查看帮助")
