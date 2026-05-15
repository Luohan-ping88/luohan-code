#!/usr/bin/env python3
"""
测试反馈学习模块
"""

import logging
from src.core.feedback_learning import FeedbackLearningSystem

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_feedback_learning():
    """测试反馈学习系统"""
    logger.info("开始测试反馈学习模块...")
    
    try:
        # 创建反馈学习系统
        feedback_system = FeedbackLearningSystem()
        
        # 测试从反馈中学习
        logger.info("\n测试1: 从反馈中学习")
        learning_report = feedback_system.learn_from_feedback()
        
        # 测试8码优化
        logger.info("\n测试2: 8码命中率优化")
        eight_code_report = feedback_system.optimize_strategy_for_8code()
        
        logger.info("\n反馈学习模块测试完成！")
        
        # 打印测试结果
        logger.info("\n=== 测试结果 ===")
        logger.info(f"学习报告包含高优先级建议: {len(learning_report.get('high_priority_suggestions', []))}")
        logger.info(f"学习报告包含中优先级建议: {len(learning_report.get('medium_priority_suggestions', []))}")
        
        eight_code_issues = eight_code_report.get('eight_code_issues', [])
        eight_code_suggestions = eight_code_report.get('eight_code_suggestions', [])
        
        logger.info(f"8码优化报告包含问题: {len(eight_code_issues)}")
        logger.info(f"8码优化报告包含建议: {len(eight_code_suggestions)}")
        
        # 打印8码相关的建议
        if eight_code_suggestions:
            logger.info("\n=== 8码优化建议 ===")
            for i, suggestion in enumerate(eight_code_suggestions, 1):
                logger.info(f"{i}. {suggestion.get('title')}")
                logger.info(f"   描述: {suggestion.get('description')}")
                action_items = suggestion.get('action_items', [])
                if action_items:
                    logger.info("   行动项:")
                    for item in action_items:
                        logger.info(f"     - {item}")
                logger.info("")
        
        return True
        
    except Exception as e:
        logger.error(f"测试反馈学习模块失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_feedback_learning()
