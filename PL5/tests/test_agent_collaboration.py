"""
测试Agent协作机制
"""

import asyncio
import logging
from agent_framework.orchestrator import AgentOrchestrator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_collaborative_decision():
    """测试协同决策功能"""
    logger.info("开始测试Agent协作机制")
    
    # 初始化编排器
    orchestrator = AgentOrchestrator()
    
    try:
        # 测试特征选择决策
        logger.info("\n1. 测试特征选择协同决策")
        feature_context = {
            'data': 'sample_data',
            'feature_cols': ['feature1', 'feature2', 'feature3', 'feature4', 'feature5']
        }
        
        feature_decision = await orchestrator.collaborative_decision('feature_selection', feature_context)
        logger.info(f"特征选择决策结果: {feature_decision}")
        
        # 测试模型选择决策
        logger.info("\n2. 测试模型选择协同决策")
        model_context = {
            'features': 'sample_features',
            'target': 'wan'
        }
        
        model_decision = await orchestrator.collaborative_decision('model_choice', model_context)
        logger.info(f"模型选择决策结果: {model_decision}")
        
        # 测试预测策略决策
        logger.info("\n3. 测试预测策略协同决策")
        strategy_context = {
            'performance': {'overall_accuracy': 0.25},
            'patterns': {'anomaly_detection': {'anomalies_detected': False}}
        }
        
        strategy_decision = await orchestrator.collaborative_decision('prediction_strategy', strategy_context)
        logger.info(f"预测策略决策结果: {strategy_decision}")
        
        # 测试系统优化任务
        logger.info("\n4. 测试系统优化任务")
        optimization_params = {
            'features': 'sample_features',
            'feature_cols': ['feature1', 'feature2', 'feature3']
        }
        
        optimization_result = await orchestrator._execute_collaborative_task('optimize_system', optimization_params)
        logger.info(f"系统优化结果: {optimization_result}")
        
        # 测试预测改进任务
        logger.info("\n5. 测试预测改进任务")
        prediction_params = {
            'data': 'sample_data',
            'feature_cols': ['feature1', 'feature2', 'feature3']
        }
        
        prediction_result = await orchestrator._execute_collaborative_task('improve_prediction', prediction_params)
        logger.info(f"预测改进结果: {prediction_result}")
        
        # 获取协作状态
        logger.info("\n6. 获取协作状态")
        collaboration_status = orchestrator.get_collaboration_status()
        logger.info(f"协作状态: {collaboration_status}")
        
        logger.info("\nAgent协作机制测试完成")
        
    finally:
        # 关闭编排器
        orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(test_collaborative_decision())
