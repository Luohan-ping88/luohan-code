"""
Prefect部署配置 V11.0
PL5智能分析系统工作流部署

使用方法：
1. 初始化Prefect后端: prefect backend server
2. 启动Prefect服务器: prefect server start
3. 部署工作流: python prefect_deploy.py deploy
4. 运行工作流: python prefect_deploy.py run
"""

from prefect.deployments import Deployment, run_deployment
from prefect.server.schemas.schedules import CronSchedule, IntervalSchedule
from prefect.orion.schemas.schedules import CronSchedule as OrionCronSchedule
from datetime import datetime, timedelta
import os


def deploy_pl5_daily_workflow():
    """部署PL5日循环工作流"""

    print("=" * 80)
    print("PL5 Prefect工作流部署 V11.0")
    print("=" * 80)

    # 导入工作流
    from src.core.workflow.prefect_workflow_v11 import pl5_daily_workflow

    # 创建日循环部署（每天22:15执行）
    daily_deployment = Deployment.build_from_flow(
        flow=pl5_daily_workflow,
        name="pl5-daily-v11",
        version="11.0",
        description="PL5日循环预测工作流 - 每天22:15执行",
        schedule=CronSchedule(
            cron="15 22 * * *",  # 每天22:15
            timezone="Asia/Shanghai"
        ),
        tags=["pl5", "daily", "production", "v11"],
        work_queue_name="pl5-queue",
        storage=None,  # 使用本地存储
    )

    print("\n部署日循环工作流...")
    daily_deployment.apply()
    print("✅ 日循环工作流部署成功!")

    return daily_deployment


def deploy_pl5_quick_workflow():
    """部署PL5快速预测工作流"""

    print("\n" + "=" * 80)
    print("部署快速预测工作流")
    print("=" * 80)

    # 导入工作流
    from src.core.workflow.prefect_workflow_v11 import pl5_quick_workflow

    # 创建快速预测部署（每小时执行一次）
    quick_deployment = Deployment.build_from_flow(
        flow=pl5_quick_workflow,
        name="pl5-quick-v11",
        version="11.0",
        description="PL5快速预测工作流 - 每小时执行",
        schedule=IntervalSchedule(
            interval=timedelta(hours=1),
            anchor_date=datetime.now()
        ),
        tags=["pl5", "quick", "production", "v11"],
        work_queue_name="pl5-queue",
        storage=None,
    )

    print("\n部署快速预测工作流...")
    quick_deployment.apply()
    print("✅ 快速预测工作流部署成功!")

    return quick_deployment


def run_pl5_daily():
    """手动运行日循环工作流"""

    print("\n" + "=" * 80)
    print("手动运行 PL5 日循环工作流")
    print("=" * 80)

    from src.core.workflow.prefect_workflow_v11 import pl5_daily_workflow

    # 同步运行
    result = pl5_daily_workflow()

    print("\n✅ 日循环工作流执行完成!")
    print(f"执行时间: {result.get('execution_time', 0):.2f} 秒")
    print(f"数据记录: {result.get('data_result', {}).get('record_count', 0)} 条")

    return result


def run_pl5_quick():
    """手动运行快速预测工作流"""

    print("\n" + "=" * 80)
    print("手动运行 PL5 快速预测工作流")
    print("=" * 80)

    from src.core.workflow.prefect_workflow_v11 import pl5_quick_workflow

    # 同步运行
    result = pl5_quick_workflow()

    print("\n✅ 快速预测工作流执行完成!")
    print(f"数据记录: {result.get('data_result', {}).get('record_count', 0)} 条")

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("""
PL5 Prefect工作流部署工具 V11.0
用法:
    python prefect_deploy.py deploy    - 部署所有工作流
    python prefect_deploy.py deploy-daily  - 部署日循环工作流
    python prefect_deploy.py deploy-quick - 部署快速预测工作流
    python prefect_deploy.py run       - 运行日循环工作流
    python prefect_deploy.py run-quick - 运行快速预测工作流
    python prefect_deploy.py server    - 启动Prefect服务器
        """)

    elif sys.argv[1] == "deploy":
        deploy_pl5_daily_workflow()
        deploy_pl5_quick_workflow()
        print("\n" + "=" * 80)
        print("✅ 所有工作流部署完成!")
        print("=" * 80)

    elif sys.argv[1] == "deploy-daily":
        deploy_pl5_daily_workflow()

    elif sys.argv[1] == "deploy-quick":
        deploy_pl5_quick_workflow()

    elif sys.argv[1] == "run":
        run_pl5_daily()

    elif sys.argv[1] == "run-quick":
        run_pl5_quick()

    elif sys.argv[1] == "server":
        print("\n启动Prefect服务器...")
        print("访问 http://localhost:4200 查看Prefect UI")
        os.system("prefect server start")

    else:
        print(f"未知命令: {sys.argv[1]}")
        print("使用 'python prefect_deploy.py' 查看帮助")
