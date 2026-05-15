#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化系统测试脚本
测试PL5预测系统的24/7自动化后台运行功能
"""

import time
import logging
from src.core.automation.manager import PL5AutomationManager
from src.core.utils import setup_logging

# 配置日志
setup_logging()
logger = logging.getLogger(__name__)

def test_automation_system():
    """测试自动化系统"""
    logger.info("=" * 80)
    logger.info("PL5预测系统 - 自动化系统测试")
    logger.info("=" * 80)
    
    # 初始化自动化管理器
    manager = PL5AutomationManager()
    
    # 启动自动化管理
    manager.start()
    
    logger.info("自动化系统已启动")
    
    # 测试获取系统状态
    status = manager.get_status()
    logger.info(f"系统状态: {status}")
    
    # 测试手动运行任务
    logger.info("\n测试手动运行数据采集任务...")
    result = manager.run_manually('data_collection')
    logger.info(f"数据采集任务执行结果: {result}")
    
    # 测试获取系统状态
    status = manager.get_status()
    logger.info(f"系统状态: {status}")
    
    # 停止自动化管理
    manager.stop()
    logger.info("自动化系统已停止")
    
    logger.info("=" * 80)
    logger.info("自动化系统测试完成")
    logger.info("=" * 80)

if __name__ == "__main__":
    test_automation_system()
