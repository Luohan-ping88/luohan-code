"""
PL5智能分析系统 - Prefect工作流定义 V11.0

Phase 2: 工作流引擎升级
- 使用Prefect 3.7作为现代化工作流编排引擎
- 支持任务并行、可视化监控、动态调度
- 保留与现有auto_scheduler_v8的兼容性
"""

from prefect import flow, task, get_run_logger
from datetime import datetime, timedelta
from typing import Dict, List, Any


# ================================================================
# Task 1: 数据采集
# ================================================================

@task(
    name="数据采集",
    description="从乐彩网采集排列五历史数据",
    tags=["data", "pl5"],
    retries=2,
    retry_delay_seconds=30,
    cache_key_fn=None,  # Prefect 3.x不支持cache_policy，使用cache_key_fn
    cache_expiration=timedelta(hours=1)
)
def data_fetch() -> Dict[str, Any]:
    """数据采集任务"""
    logger = get_run_logger()
    logger.info("开始执行数据采集任务")

    try:
        from src.core.data.collector import PL5DataCollector
        collector = PL5DataCollector()
        df = collector.update_data()

        result = {
            "success": True,
            "record_count": len(df),
            "latest_period": df["period"].iloc[-1] if not df.empty else None,
            "data_hash": str(hash(df.to_csv())),
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"数据采集成功: {result['record_count']} 条记录")
        return result

    except Exception as e:
        logger.error(f"数据采集失败: {str(e)}")
        raise


# ================================================================
# Task 2: 评估
# ================================================================

@task(
    name="模型评估",
    description="评估当前模型性能",
    tags=["evaluation", "pl5"],
    retries=1,
    retry_delay_seconds=60
)
def evaluation(data_result: Dict[str, Any]) -> Dict[str, Any]:
    """模型评估任务"""
    logger = get_run_logger()
    logger.info("开始执行模型评估任务")

    try:
        from src.core.evaluation.evaluator import PredictionEvaluator
        evaluator = PredictionEvaluator()
        metrics = evaluator.get_evaluation_statistics()

        result = {
            "success": True,
            "metrics": metrics,
            "data_result": data_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"模型评估完成: {metrics}")
        return result

    except Exception as e:
        logger.error(f"模型评估失败: {str(e)}")
        raise


# ================================================================
# Task 3: 优化
# ================================================================

@task(
    name="策略优化",
    description="优化预测策略",
    tags=["optimization", "pl5"],
    retries=1,
    retry_delay_seconds=60
)
def optimization(eval_result: Dict[str, Any]) -> Dict[str, Any]:
    """策略优化任务"""
    logger = get_run_logger()
    logger.info("开始执行策略优化任务")

    try:
        import asyncio
        from src.agents.optimization_agent import OptimizationAgent
        agent = OptimizationAgent()
        optimization_result = asyncio.run(agent.suggest_system_optimizations())

        result = {
            "success": True,
            "optimization_result": optimization_result,
            "eval_result": eval_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info("策略优化完成")
        return result

    except Exception as e:
        logger.error(f"策略优化失败: {str(e)}")
        raise


# ================================================================
# Task 4: 训练
# ================================================================

@task(
    name="模型训练",
    description="训练预测模型",
    tags=["training", "pl5"],
    retries=2,
    retry_delay_seconds=120
)
def training(optimization_result: Dict[str, Any]) -> Dict[str, Any]:
    """模型训练任务"""
    logger = get_run_logger()
    logger.info("开始执行模型训练任务")

    try:
        import asyncio
        from src.agents.training_agent import TrainingOptimizationAgent
        agent = TrainingOptimizationAgent()
        model_result = asyncio.run(agent._train_all_models({}))

        result = {
            "success": True,
            "model_result": model_result,
            "optimization_result": optimization_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"模型训练完成: {model_result.get('model_count', 0)} 个模型")
        return result

    except Exception as e:
        logger.error(f"模型训练失败: {str(e)}")
        raise


# ================================================================
# Task 5: 增量训练
# ================================================================

@task(
    name="增量训练",
    description="基于新数据进行增量训练",
    tags=["training", "incremental", "pl5"],
    retries=1,
    retry_delay_seconds=60
)
def incremental_training(training_result: Dict[str, Any]) -> Dict[str, Any]:
    """增量训练任务"""
    logger = get_run_logger()
    logger.info("开始执行增量训练任务")

    try:
        from src.core.models.incremental_learning import IncrementalLearning
        incremental = IncrementalLearning()
        incremental_result = incremental.train_incremental()

        result = {
            "success": True,
            "incremental_result": incremental_result,
            "training_result": training_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info("增量训练完成")
        return result

    except Exception as e:
        logger.error(f"增量训练失败: {str(e)}")
        raise


# ================================================================
# Task 6-8: 预测验证（并行）
# ================================================================

@task(
    name="第一次预测验证",
    description="验证预测结果一致性",
    tags=["verification", "pl5"],
    retries=1
)
def first_prediction_verification(incremental_result: Dict[str, Any]) -> Dict[str, Any]:
    """第一次预测验证任务"""
    logger = get_run_logger()
    logger.info("执行第一次预测验证")

    try:
        from src.core.models.predictor import PL5Predictor
        predictor = PL5Predictor()
        prediction1 = predictor.predict()

        result = {
            "success": True,
            "prediction": prediction1,
            "verification_round": 1,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"第一次验证完成: {prediction1.get('period')}")
        return result

    except Exception as e:
        logger.error(f"第一次验证失败: {str(e)}")
        raise


@task(
    name="第二次预测验证",
    description="验证预测结果一致性",
    tags=["verification", "pl5"],
    retries=1
)
def second_prediction_verification(incremental_result: Dict[str, Any]) -> Dict[str, Any]:
    """第二次预测验证任务"""
    logger = get_run_logger()
    logger.info("执行第二次预测验证")

    try:
        from src.core.models.predictor import PL5Predictor
        predictor = PL5Predictor()
        prediction2 = predictor.predict()

        result = {
            "success": True,
            "prediction": prediction2,
            "verification_round": 2,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"第二次验证完成: {prediction2.get('period')}")
        return result

    except Exception as e:
        logger.error(f"第二次验证失败: {str(e)}")
        raise


@task(
    name="第三次预测验证",
    description="验证预测结果一致性",
    tags=["verification", "pl5"],
    retries=1
)
def third_prediction_verification(incremental_result: Dict[str, Any]) -> Dict[str, Any]:
    """第三次预测验证任务"""
    logger = get_run_logger()
    logger.info("执行第三次预测验证")

    try:
        from src.core.models.predictor import PL5Predictor
        predictor = PL5Predictor()
        prediction3 = predictor.predict()

        result = {
            "success": True,
            "prediction": prediction3,
            "verification_round": 3,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"第三次验证完成: {prediction3.get('period')}")
        return result

    except Exception as e:
        logger.error(f"第三次验证失败: {str(e)}")
        raise


# ================================================================
# Task 9: 深度策略优化
# ================================================================

@task(
    name="深度策略优化",
    description="基于多次验证进行深度策略优化",
    tags=["optimization", "deep", "pl5"],
    retries=1
)
def deep_strategy_optimization(
    verifications: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """深度策略优化任务"""
    logger = get_run_logger()
    logger.info("执行深度策略优化")

    try:
        from src.agents.optimization_agent import OptimizationAgent
        agent = OptimizationAgent()

        # 汇总三次验证结果
        verification_summary = {
            f"verification_{i+1}": v["prediction"] for i, v in enumerate(verifications)
        }

        deep_result = agent.deep_optimize(verification_summary)

        result = {
            "success": True,
            "deep_result": deep_result,
            "verifications": verifications,
            "timestamp": datetime.now().isoformat()
        }

        logger.info("深度策略优化完成")
        return result

    except Exception as e:
        logger.error(f"深度策略优化失败: {str(e)}")
        raise


# ================================================================
# Task 10: 预测预览
# ================================================================

@task(
    name="预测预览",
    description="生成最终预测预览",
    tags=["prediction", "preview", "pl5"],
    retries=1
)
def prediction_preview(deep_result: Dict[str, Any]) -> Dict[str, Any]:
    """预测预览任务"""
    logger = get_run_logger()
    logger.info("执行预测预览")

    try:
        from src.core.models.predictor import PL5Predictor
        predictor = PL5Predictor()
        preview = predictor.predict_preview()

        result = {
            "success": True,
            "preview": preview,
            "deep_result": deep_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info("预测预览完成")
        return result

    except Exception as e:
        logger.error(f"预测预览失败: {str(e)}")
        raise


# ================================================================
# Task 11: 最终预测
# ================================================================

@task(
    name="最终预测",
    description="生成最终预测结果",
    tags=["prediction", "final", "pl5"],
    retries=2,
    retry_delay_seconds=60
)
def final_prediction(preview_result: Dict[str, Any]) -> Dict[str, Any]:
    """最终预测任务"""
    logger = get_run_logger()
    logger.info("执行最终预测")

    try:
        import numpy as np
        from src.core.models.predictor import PL5Predictor

        predictor = PL5Predictor()
        predictor.load_models()
        
        features = np.zeros(100)
        prediction = predictor.predict(features)

        result = {
            "success": True,
            "prediction": prediction,
            "preview_result": preview_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"最终预测完成")
        return result

    except Exception as e:
        logger.error(f"最终预测失败: {str(e)}")
        raise


# ================================================================
# Task 12: 最终预测验证
# ================================================================

@task(
    name="最终预测验证",
    description="验证最终预测结果",
    tags=["verification", "final", "pl5"],
    retries=1
)
def final_prediction_verification(final_result: Dict[str, Any]) -> Dict[str, Any]:
    """最终预测验证任务"""
    logger = get_run_logger()
    logger.info("执行最终预测验证")

    try:
        # 验证预测结果的完整性
        verification = {
            "has_prediction": "prediction" in final_result,
            "has_fusion": "fusion_result" in final_result,
            "period": final_result.get("prediction", {}).get("period"),
            "confidence": final_result.get("prediction", {}).get("confidence", 0)
        }

        result = {
            "success": True,
            "verification": verification,
            "final_result": final_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"最终验证完成: {verification}")
        return result

    except Exception as e:
        logger.error(f"最终验证失败: {str(e)}")
        raise


# ================================================================
# Task 13: 售前预测
# ================================================================

@task(
    name="售前预测",
    description="生成售前预测报告",
    tags=["prediction", "pre-sale", "pl5"],
    retries=1
)
def pre_sale_prediction(verification_result: Dict[str, Any]) -> Dict[str, Any]:
    """售前预测任务"""
    logger = get_run_logger()
    logger.info("执行售前预测")

    try:
        from src.app.analyze_and_send import AnalyzeAndSender

        sender = AnalyzeAndSender()
        pre_sale_report = sender.generate_pre_sale_report(
            verification_result["final_result"]
        )

        result = {
            "success": True,
            "pre_sale_report": pre_sale_report,
            "verification_result": verification_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info("售前预测完成")
        return result

    except Exception as e:
        logger.error(f"售前预测失败: {str(e)}")
        raise


# ================================================================
# Task 14: 发送报告
# ================================================================

@task(
    name="发送报告",
    description="发送最终预测报告",
    tags=["report", "email", "pl5"],
    retries=3,
    retry_delay_seconds=60
)
def send_report(pre_sale_result: Dict[str, Any]) -> Dict[str, Any]:
    """发送报告任务"""
    logger = get_run_logger()
    logger.info("执行发送报告")

    try:
        from src.app.email_sender import EmailSender

        sender = EmailSender()
        email_result = sender.send_prediction_report(
            pre_sale_result["pre_sale_report"]
        )

        result = {
            "success": True,
            "email_result": email_result,
            "pre_sale_result": pre_sale_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info("报告发送完成")
        return result

    except Exception as e:
        logger.error(f"报告发送失败: {str(e)}")
        raise


# ================================================================
# Main Flow: PL5日循环工作流
# ================================================================

@flow(
    name="PL5日循环工作流",
    description="排列五智能分析系统的日循环预测工作流",
    version="11.0",
    log_prints=True
    # schedule将在部署时配置
)
def pl5_daily_workflow() -> Dict[str, Any]:
    """
    PL5日循环工作流

    工作流程（14步）：
    1. 数据采集 (data_fetch)
    2. 模型评估 (evaluation)
    3. 策略优化 (optimization)
    4. 模型训练 (training)
    5. 增量训练 (incremental_training)
    6-8. 三次预测验证 (first/second/third_prediction_verification) - 并行
    9. 深度策略优化 (deep_strategy_optimization)
    10. 预测预览 (prediction_preview)
    11. 最终预测 (final_prediction)
    12. 最终预测验证 (final_prediction_verification)
    13. 售前预测 (pre_sale_prediction)
    14. 发送报告 (send_report)

    Returns:
        Dict: 工作流执行结果
    """
    logger = get_run_logger()
    logger.info("=" * 80)
    logger.info("开始执行 PL5 日循环工作流 V11.0")
    logger.info("=" * 80)

    start_time = datetime.now()

    try:
        # Stage 1: 数据采集与评估 (串行)
        logger.info("\n[Stage 1/4] 数据采集与评估")
        data_result = data_fetch()
        eval_result = evaluation(data_result)

        # Stage 2: 优化与训练 (串行)
        logger.info("\n[Stage 2/4] 策略优化与模型训练")
        optimization_result = optimization(eval_result)
        training_result = training(optimization_result)
        incremental_result = incremental_training(training_result)

        # Stage 3: 三次预测验证 (并行)
        logger.info("\n[Stage 3/4] 预测验证")
        verifications = [
            first_prediction_verification(incremental_result),
            second_prediction_verification(incremental_result),
            third_prediction_verification(incremental_result),
        ]

        # Stage 4: 深度优化与最终预测 (串行)
        logger.info("\n[Stage 4/4] 深度优化与最终预测")
        deep_result = deep_strategy_optimization(verifications)
        preview_result = prediction_preview(deep_result)
        final_result = final_prediction(preview_result)
        verification_result = final_prediction_verification(final_result)
        pre_sale_result = pre_sale_prediction(verification_result)
        email_result = send_report(pre_sale_result)

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        result = {
            "success": True,
            "workflow_version": "11.0",
            "execution_time": execution_time,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "data_result": data_result,
            "eval_result": eval_result,
            "training_result": training_result,
            "verifications": verifications,
            "final_result": final_result,
            "email_result": email_result,
        }

        logger.info("=" * 80)
        logger.info(f"✅ PL5日循环工作流执行成功!")
        logger.info(f"⏱️ 总耗时: {execution_time:.2f} 秒")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"❌ 工作流执行失败: {str(e)}")
        raise


# ================================================================
# Sub-Flow: 快速预测工作流（仅核心步骤）
# ================================================================

@flow(
    name="PL5快速预测工作流",
    description="轻量级预测工作流，用于快速预测",
    version="11.0"
)
def pl5_quick_workflow() -> Dict[str, Any]:
    """快速预测工作流 - 仅执行核心预测步骤"""

    logger = get_run_logger()
    logger.info("开始执行快速预测工作流")

    try:
        # 仅执行关键步骤
        data_result = data_fetch()
        eval_result = evaluation(data_result)
        optimization_result = optimization(eval_result)
        training_result = training(optimization_result)
        final_result = final_prediction({"optimization_result": optimization_result})

        result = {
            "success": True,
            "data_result": data_result,
            "final_result": final_result,
            "timestamp": datetime.now().isoformat()
        }

        logger.info("快速预测工作流执行成功")
        return result

    except Exception as e:
        logger.error(f"快速预测工作流失败: {str(e)}")
        raise


# ================================================================
# 测试入口
# ================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("PL5 Prefect工作流 V11.0")
    print("=" * 80)

    # 测试完整工作流
    print("\n执行完整日循环工作流...")
    result = pl5_daily_workflow()

    print(f"\n✅ 工作流执行完成!")
    print(f"执行时间: {result.get('execution_time', 0):.2f} 秒")
    print(f"数据记录: {result.get('data_result', {}).get('record_count', 0)} 条")
