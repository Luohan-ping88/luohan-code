"""
测试免疫系统功能
"""

import asyncio
import logging
import time
from src.agents.orchestrator import AgentOrchestrator

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


async def test_immune_system():
    """测试免疫系统功能"""
    logger.info("开始测试免疫系统")

    # 初始化编排器
    orchestrator = AgentOrchestrator()

    try:
        # 检查免疫系统是否初始化
        if orchestrator.immune_system:
            logger.info("免疫系统已初始化")
        else:
            logger.error("免疫系统初始化失败")
            return

        # 启动免疫系统
        await orchestrator.immune_system.start()
        logger.info("免疫系统已启动")

        # 等待一段时间，让免疫系统运行
        logger.info("等待30秒，让免疫系统运行...")
        await asyncio.sleep(30)

        # 获取免疫系统状态
        immune_status = orchestrator.immune_system.get_status()
        logger.info(f"免疫系统状态: {immune_status}")

        # 生成健康报告
        health_report = orchestrator.immune_system.generate_health_report()
        logger.info("\n健康报告:")
        logger.info(health_report)

        # 保存健康报告
        from pathlib import Path

        report_path = Path("results") / f'health_report_{time.strftime("%Y%m%d_%H%M%S")}.md'
        report_path.parent.mkdir(exist_ok=True)
        orchestrator.immune_system.save_health_report(report_path)
        logger.info(f"健康报告已保存到: {report_path}")

        # 停止免疫系统
        await orchestrator.immune_system.stop()
        logger.info("免疫系统已停止")

        logger.info("免疫系统测试完成")

    finally:
        # 关闭编排器
        orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(test_immune_system())
