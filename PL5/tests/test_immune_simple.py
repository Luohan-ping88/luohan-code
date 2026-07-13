"""
简化的免疫系统测试
"""

import asyncio
import logging
from agent_framework.monitor import ImmuneSystem

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_immune_system():
    """测试免疫系统功能"""
    logger.info("开始测试免疫系统")
    
    # 初始化免疫系统（不传入orchestrator）
    immune_system = ImmuneSystem()
    
    try:
        # 启动免疫系统
        await immune_system.start()
        logger.info("免疫系统已启动")
        
        # 等待5秒
        logger.info("等待5秒...")
        await asyncio.sleep(5)
        
        # 获取系统健康状态
        health_status = immune_system.health_monitor.check_system_health()
        logger.info("系统健康状态: %s", health_status)
        
        # 停止免疫系统
        await immune_system.stop()
        logger.info("免疫系统已停止")
        
        logger.info("免疫系统测试完成")
        
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(test_immune_system())
