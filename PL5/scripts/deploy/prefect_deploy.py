"""
Prefect部署配置 V11.0
PL5智能分析系统工作流部署

使用方法：
1. 启动Prefect服务器: prefect server start --host 0.0.0.0 --port 4200
2. 部署工作流: python prefect_deploy.py deploy
3. 运行工作流: python prefect_deploy.py run
"""

from prefect import flow
from prefect.client.schemas.schedules import CronSchedule
from prefect.client.orchestration import get_client
from datetime import datetime, timedelta
import os


async def ensure_work_pool(pool_name: str):
    """确保工作池存在"""
    async with get_client() as client:
        try:
            await client.read_work_pool(pool_name)
            print(f"工作池 '{pool_name}' 已存在")
        except Exception as e:
            print(f"工作池 '{pool_name}' 不存在，尝试创建...")
            try:
                await client.create_work_pool(
                    name=pool_name,
                    description="PL5智能分析系统工作池"
                )
                print(f"✅ 工作池 '{pool_name}' 创建成功!")
            except Exception as create_err:
                print(f"创建工作池失败: {create_err}")


def deploy_all():
    """部署所有工作流 - Prefect 3.7版本"""
    print("=" * 80)
    print("PL5 Prefect工作流部署 V11.0")
    print("=" * 80)

    import asyncio
    asyncio.run(ensure_work_pool("pl5-pool"))

    from src.core.workflow.prefect_workflow_v11 import pl5_daily_workflow, pl5_quick_workflow

    print("\n部署日循环工作流...")
    daily_schedule = CronSchedule(cron="15 22 * * *", timezone="Asia/Shanghai")
    daily_deployment = pl5_daily_workflow.to_deployment(
        name="pl5-daily-v11",
        version="11.0",
        description="PL5日循环预测工作流 - 每天22:15执行",
        schedule=daily_schedule,
        tags=["pl5", "daily", "production", "v11"],
        work_pool_name="pl5-pool",
        work_queue_name="pl5-queue",
    )
    daily_deployment.apply()
    print("✅ 日循环工作流部署成功!")

    print("\n部署快速预测工作流...")
    quick_deployment = pl5_quick_workflow.to_deployment(
        name="pl5-quick-v11",
        version="11.0",
        description="PL5快速预测工作流 - 每小时执行",
        interval=3600,
        tags=["pl5", "quick", "production", "v11"],
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
    print("手动运行 PL5 日循环工作流")
    print("=" * 80)

    from src.core.workflow.prefect_workflow_v11 import pl5_daily_workflow
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
        deploy_all()

    elif sys.argv[1] == "deploy-daily":
        import asyncio
        asyncio.run(ensure_work_pool("pl5-pool"))
        
        from src.core.workflow.prefect_workflow_v11 import pl5_daily_workflow
        daily_schedule = CronSchedule(cron="15 22 * * *", timezone="Asia/Shanghai")
        daily_deployment = pl5_daily_workflow.to_deployment(
            name="pl5-daily-v11",
            version="11.0",
            schedule=daily_schedule,
            tags=["pl5", "daily", "production", "v11"],
            work_pool_name="pl5-pool",
            work_queue_name="pl5-queue",
        )
        daily_deployment.apply()
        print("✅ 日循环工作流部署成功!")

    elif sys.argv[1] == "deploy-quick":
        import asyncio
        asyncio.run(ensure_work_pool("pl5-pool"))
        
        from src.core.workflow.prefect_workflow_v11 import pl5_quick_workflow
        quick_deployment = pl5_quick_workflow.to_deployment(
            name="pl5-quick-v11",
            version="11.0",
            interval=3600,
            tags=["pl5", "quick", "production", "v11"],
            work_pool_name="pl5-pool",
            work_queue_name="pl5-queue",
        )
        quick_deployment.apply()
        print("✅ 快速预测工作流部署成功!")

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