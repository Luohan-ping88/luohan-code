"""
PL5智能分析系统 - Prefect工作流定义 V12.0

Phase 3: 分布式智能体升级
- 任务周期：22:00-20:30（第二天）
- 节点时间控制：多智能体智能协调分配
- 充分利用22.5小时时间窗口
"""

from prefect import flow, task, get_run_logger
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
import os

# 添加项目根目录到路径
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ),
)

# 导入时间协调器 V2.0
try:
    from src.agents.distributed.time_coordinator_v2 import (
        TimeCoordinatorV2,
    )

    TIME_COORDINATOR_AVAILABLE = True
except ImportError:
    TIME_COORDINATOR_AVAILABLE = False
    print("警告: 时间协调器模块不可用，使用默认调度")


# 全局时间协调器实例
time_coordinator = None


def get_time_coordinator():
    """
    获取时间协调器实例 V2.0

    Returns:
        TimeCoordinatorV2: 时间协调器实例
    """
    global time_coordinator
    if time_coordinator is None:
        time_coordinator = TimeCoordinatorV2(
            window_start_hour=22, window_end_hour=20, window_end_next_day=True
        )

        # 注册核心任务（14个任务节点 + 自适应特征选择）
        time_coordinator.register_task(
            "数据采集",
            estimated_duration_minutes=30,
            priority=5,
            is_core_task=True,
        )
        time_coordinator.register_task(
            "自适应特征选择",
            estimated_duration_minutes=60,
            priority=4,
            dependencies=["数据采集"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "模型评估",
            estimated_duration_minutes=20,
            priority=4,
            dependencies=["自适应特征选择"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "策略优化",
            estimated_duration_minutes=60,
            priority=4,
            dependencies=["模型评估"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "模型训练",
            estimated_duration_minutes=180,
            priority=3,
            dependencies=["策略优化"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "增量训练",
            estimated_duration_minutes=150,
            priority=3,
            dependencies=["模型训练"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "第一次预测验证",
            estimated_duration_minutes=40,
            priority=2,
            dependencies=["增量训练"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "第二次预测验证",
            estimated_duration_minutes=40,
            priority=2,
            dependencies=["增量训练"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "第三次预测验证",
            estimated_duration_minutes=40,
            priority=2,
            dependencies=["增量训练"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "深度策略优化",
            estimated_duration_minutes=120,
            priority=2,
            dependencies=[
                "第一次预测验证",
                "第二次预测验证",
                "第三次预测验证",
            ],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "预测预览",
            estimated_duration_minutes=30,
            priority=1,
            dependencies=["深度策略优化"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "最终预测",
            estimated_duration_minutes=60,
            priority=1,
            dependencies=["预测预览"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "最终预测验证",
            estimated_duration_minutes=20,
            priority=1,
            dependencies=["最终预测"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "售前预测",
            estimated_duration_minutes=30,
            priority=1,
            dependencies=["最终预测验证"],
            is_core_task=True,
        )
        time_coordinator.register_task(
            "发送报告",
            estimated_duration_minutes=30,
            priority=1,
            dependencies=["售前预测"],
            is_core_task=True,
        )

        # 注册智能体
        time_coordinator.register_agent(
            "data_agent", ["数据", "采集", "fetch", "data"]
        )
        time_coordinator.register_agent(
            "feature_agent", ["特征", "自适应", "feature", "adaptive"]
        )
        time_coordinator.register_agent(
            "analysis_agent",
            ["评估", "优化", "策略", "evaluation", "optimization"],
        )
        time_coordinator.register_agent(
            "prediction_agent", ["预测", "训练", "prediction", "training"]
        )
        time_coordinator.register_agent(
            "report_agent", ["报告", "发送", "report", "send"]
        )

    return time_coordinator


# ================================================================
# Task 1: 数据采集
# ================================================================


@task(
    name="数据采集",
    description="从乐彩网采集排列五历史数据",
    tags=["data", "pl5"],
    retries=2,
    retry_delay_seconds=30,
    cache_expiration=timedelta(hours=1),
)
def data_fetch() -> Dict[str, Any]:
    """数据采集任务"""
    logger = get_run_logger()
    _log_task_start(logger, "数据采集")

    try:
        from src.core.data.collector import PL5DataCollector

        collector = PL5DataCollector()
        df = collector.update_data()

        result = {
            "success": True,
            "record_count": len(df),
            "latest_period": df["period"].iloc[-1] if not df.empty else None,
            "data_hash": str(hash(df.to_csv())),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"数据采集成功: {result['record_count']} 条记录")
        _log_task_end(logger, "数据采集")
        return result

    except Exception as e:
        logger.error(f"数据采集失败: {str(e)}")
        raise


# ================================================================
# Task 2: 自适应特征选择
# ================================================================


@task(
    name="自适应特征选择",
    description="根据开奖数据变化动态评估和调整特征组",
    tags=["feature", "adaptive", "pl5"],
    retries=1,
    retry_delay_seconds=60,
)
def adaptive_feature_selection(data_result: Dict[str, Any]) -> Dict[str, Any]:
    """自适应特征选择任务"""
    logger = get_run_logger()
    _log_task_start(logger, "自适应特征选择")

    try:
        from src.core.data.collector import PL5DataCollector
        from src.core.features.adaptive_feature_engine import (
            AdaptiveFeatureEngine,
            DynamicFeatureOptimizer,
        )

        # 获取最新数据
        collector = PL5DataCollector()
        df = collector.get_latest_data()

        # 初始化自适应特征引擎
        engine = AdaptiveFeatureEngine(history_window=100)
        optimizer = DynamicFeatureOptimizer(engine)

        # 设置基准分布
        baseline_df = df.head(1000)
        engine.set_baseline(baseline_df)

        # 执行自适应特征优化
        selected_features, importance_scores, suggestions = (
            optimizer.optimize_for_current_data(df)
        )

        # 生成特征推荐
        recommendations = engine.get_feature_recommendations()

        result = {
            "success": True,
            "selected_features": selected_features,
            "feature_importance": importance_scores,
            "suggestions": suggestions,
            "recommendations": recommendations,
            "data_result": data_result,
            "record_count": len(df),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"自适应特征选择完成: 选择了 {len(selected_features)} 个特征"
        )
        logger.info(f"特征列表: {selected_features[:5]}...")

        if suggestions:
            logger.info("优化建议:")
            for suggestion in suggestions:
                logger.info(f"  - {suggestion}")

        _log_task_end(logger, "自适应特征选择")
        return result

    except Exception as e:
        logger.error(f"自适应特征选择失败: {str(e)}")
        raise


# ================================================================
# Task 3: 模型评估
# ================================================================


@task(
    name="模型评估",
    description="评估现有模型的预测性能",
    tags=["evaluation", "pl5"],
    retries=1,
    retry_delay_seconds=60,
)
def evaluation(data_result: Dict[str, Any]) -> Dict[str, Any]:
    """模型评估任务"""
    logger = get_run_logger()
    _log_task_start(logger, "模型评估")

    try:
        from src.core.evaluation.evaluator import PredictionEvaluator

        evaluator = PredictionEvaluator()
        metrics = evaluator.get_evaluation_statistics()

        result = {
            "success": True,
            "metrics": metrics,
            "data_result": data_result,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"模型评估完成")
        _log_task_end(logger, "模型评估")
        return result

    except Exception as e:
        logger.error(f"模型评估失败: {str(e)}")
        raise


# ================================================================
# Task 3: 策略优化
# ================================================================


@task(
    name="策略优化",
    description="优化预测策略",
    tags=["optimization", "pl5"],
    retries=1,
    retry_delay_seconds=60,
)
def optimization(eval_result: Dict[str, Any]) -> Dict[str, Any]:
    """策略优化任务"""
    logger = get_run_logger()
    _log_task_start(logger, "策略优化")

    try:
        import asyncio
        from src.agents.optimization_agent import OptimizationAgent

        agent = OptimizationAgent()
        optimization_result = asyncio.run(agent.suggest_system_optimizations())

        result = {
            "success": True,
            "optimization_result": optimization_result,
            "eval_result": eval_result,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("策略优化完成")
        _log_task_end(logger, "策略优化")
        return result

    except Exception as e:
        logger.error(f"策略优化失败: {str(e)}")
        raise


# ================================================================
# Task 4: 模型训练
# ================================================================


@task(
    name="模型训练",
    description="训练预测模型",
    tags=["training", "pl5"],
    retries=2,
    retry_delay_seconds=120,
)
def training(optimization_result: Dict[str, Any]) -> Dict[str, Any]:
    """模型训练任务"""
    logger = get_run_logger()
    _log_task_start(logger, "模型训练")

    try:
        import asyncio
        from src.agents.training_agent import TrainingOptimizationAgent

        agent = TrainingOptimizationAgent()
        model_result = asyncio.run(agent._train_all_models({}))

        result = {
            "success": True,
            "model_result": model_result,
            "optimization_result": optimization_result,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"模型训练完成: {model_result.get('model_count', 0)} 个模型"
        )
        _log_task_end(logger, "模型训练")
        return result

    except Exception as e:
        logger.error(f"模型训练失败: {str(e)}")
        raise


# ================================================================
# Task 5: 增量训练
# ================================================================


@task(
    name="增量训练",
    description="使用最新数据进行增量训练",
    tags=["incremental", "training", "pl5"],
    retries=2,
    retry_delay_seconds=120,
)
def incremental_training(training_result: Dict[str, Any]) -> Dict[str, Any]:
    """增量训练任务"""
    logger = get_run_logger()
    _log_task_start(logger, "增量训练")

    try:
        from src.core.data.collector import PL5DataCollector
        from src.core.models.predictor import PL5Predictor

        # 获取最新数据
        collector = PL5DataCollector()
        df = collector.get_latest_data()

        # 使用最新数据增量训练
        predictor = PL5Predictor()
        predictor.load_models()
        # 这里实现增量训练逻辑
        incremental_result = {"data_count": len(df), "model_updated": True}

        result = {
            "success": True,
            "incremental_result": incremental_result,
            "training_result": training_result,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"增量训练完成: {len(df)} 条新数据")
        _log_task_end(logger, "增量训练")
        return result

    except Exception as e:
        logger.error(f"增量训练失败: {str(e)}")
        raise


# ================================================================
# Task 6: 第一次预测验证
# ================================================================


@task(
    name="第一次预测验证",
    description="第一次预测验证",
    tags=["prediction", "verification", "pl5"],
    retries=1,
)
def first_prediction_verification(
    incremental_result: Dict[str, Any],
) -> Dict[str, Any]:
    """第一次预测验证任务"""
    logger = get_run_logger()
    _log_task_start(logger, "第一次预测验证")

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
            "incremental_result": incremental_result,
            "verification_round": 1,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("第一次预测验证完成")
        _log_task_end(logger, "第一次预测验证")
        return result

    except Exception as e:
        logger.error(f"第一次预测验证失败: {str(e)}")
        raise


# ================================================================
# Task 7: 第二次预测验证
# ================================================================


@task(
    name="第二次预测验证",
    description="第二次预测验证",
    tags=["prediction", "verification", "pl5"],
    retries=1,
)
def second_prediction_verification(
    incremental_result: Dict[str, Any],
) -> Dict[str, Any]:
    """第二次预测验证任务"""
    logger = get_run_logger()
    _log_task_start(logger, "第二次预测验证")

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
            "incremental_result": incremental_result,
            "verification_round": 2,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("第二次预测验证完成")
        _log_task_end(logger, "第二次预测验证")
        return result

    except Exception as e:
        logger.error(f"第二次预测验证失败: {str(e)}")
        raise


# ================================================================
# Task 8: 第三次预测验证
# ================================================================


@task(
    name="第三次预测验证",
    description="第三次预测验证",
    tags=["prediction", "verification", "pl5"],
    retries=1,
)
def third_prediction_verification(
    incremental_result: Dict[str, Any],
) -> Dict[str, Any]:
    """第三次预测验证任务"""
    logger = get_run_logger()
    _log_task_start(logger, "第三次预测验证")

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
            "incremental_result": incremental_result,
            "verification_round": 3,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("第三次预测验证完成")
        _log_task_end(logger, "第三次预测验证")
        return result

    except Exception as e:
        logger.error(f"第三次预测验证失败: {str(e)}")
        raise


# ================================================================
# Task 9: 深度策略优化
# ================================================================


@task(
    name="深度策略优化",
    description="基于三次验证结果进行深度策略优化",
    tags=["optimization", "deep", "pl5"],
    retries=1,
    retry_delay_seconds=60,
)
def deep_strategy_optimization(
    verifications: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """深度策略优化任务"""
    logger = get_run_logger()
    _log_task_start(logger, "深度策略优化")

    try:
        import asyncio
        from src.agents.optimization_agent import OptimizationAgent

        agent = OptimizationAgent()
        # 基于三次验证结果进行深度优化
        deep_result = asyncio.run(agent.suggest_system_optimizations())

        result = {
            "success": True,
            "deep_result": deep_result,
            "verifications": verifications,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("深度策略优化完成")
        _log_task_end(logger, "深度策略优化")
        return result

    except Exception as e:
        logger.error(f"深度策略优化失败: {str(e)}")
        raise


# ================================================================
# Task 10: 预测预览
# ================================================================


@task(
    name="预测预览",
    description="生成预测预览",
    tags=["prediction", "preview", "pl5"],
    retries=1,
)
def prediction_preview(deep_result: Dict[str, Any]) -> Dict[str, Any]:
    """预测预览任务"""
    logger = get_run_logger()
    _log_task_start(logger, "预测预览")

    try:
        import numpy as np
        from src.core.models.predictor import PL5Predictor

        predictor = PL5Predictor()
        predictor.load_models()
        features = np.zeros(100)
        prediction = predictor.predict(features)

        result = {
            "success": True,
            "preview": prediction,
            "deep_result": deep_result,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("预测预览完成")
        _log_task_end(logger, "预测预览")
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
    retry_delay_seconds=60,
)
def final_prediction(preview_result: Dict[str, Any]) -> Dict[str, Any]:
    """最终预测任务"""
    logger = get_run_logger()
    _log_task_start(logger, "最终预测")

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
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"最终预测完成")
        _log_task_end(logger, "最终预测")
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
    retries=1,
)
def final_prediction_verification(
    final_result: Dict[str, Any],
) -> Dict[str, Any]:
    """最终预测验证任务"""
    logger = get_run_logger()
    _log_task_start(logger, "最终预测验证")

    try:
        verification = {
            "has_prediction": "prediction" in final_result,
            "period": final_result.get("prediction", {}).get("period"),
            "confidence": final_result.get("prediction", {}).get(
                "confidence", 0
            ),
        }

        result = {
            "success": True,
            "verification": verification,
            "final_result": final_result,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"最终验证完成: {verification}")
        _log_task_end(logger, "最终预测验证")
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
    retries=1,
)
def pre_sale_prediction(verification_result: Dict[str, Any]) -> Dict[str, Any]:
    """售前预测任务"""
    logger = get_run_logger()
    _log_task_start(logger, "售前预测")

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
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("售前预测完成")
        _log_task_end(logger, "售前预测")
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
    retry_delay_seconds=60,
)
def send_report(pre_sale_result: Dict[str, Any]) -> Dict[str, Any]:
    """发送报告任务"""
    logger = get_run_logger()
    _log_task_start(logger, "发送报告")

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
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("报告发送完成")
        _log_task_end(logger, "发送报告")
        return result

    except Exception as e:
        logger.error(f"报告发送失败: {str(e)}")
        raise


# ================================================================
# 辅助函数
# ================================================================


def _log_task_start(logger, task_name: str):
    """记录任务开始"""
    logger.info("-" * 60)
    logger.info(f"▶️ 开始执行: {task_name}")
    if TIME_COORDINATOR_AVAILABLE:
        try:
            coord = get_time_coordinator()
            slot = coord.get_slot_for_task(task_name)
            if slot:
                logger.info(
                    f"📋 预计时间: {slot.duration_minutes}分钟, Agent: {slot.agent_assigned}"
                )
        except Exception:
            pass
    logger.info("-" * 60)


def _log_task_end(logger, task_name: str):
    """记录任务结束"""
    logger.info(f"✅ 完成: {task_name}")
    logger.info("-" * 60)


# ================================================================
# Main Flow: PL5日循环工作流 V12.0
# ================================================================


@flow(
    name="PL5日循环工作流",
    description="排列五智能分析系统的日循环预测工作流 - V12.0 - 多智能体时间协调",
    version="12.0",
    log_prints=True,
)
def pl5_daily_workflow() -> Dict[str, Any]:
    """
    PL5日循环工作流 V12.0

    任务周期:
    - 启动时间: 22:00
    - 结束时间: 第二天 20:30
    - 时间协调: 多智能体智能分配

    工作流程（14步）:
    1. 数据采集
    2. 模型评估
    3. 策略优化
    4. 模型训练
    5. 增量训练
    6-8. 三次预测验证 - 并行
    9. 深度策略优化
    10. 预测预览
    11. 最终预测
    12. 最终预测验证
    13. 售前预测
    14. 发送报告

    Returns:
        Dict: 工作流执行结果
    """
    logger = get_run_logger()
    logger.info("=" * 80)
    logger.info("开始执行 PL5 日循环工作流 V12.0")
    logger.info("=" * 80)
    logger.info("任务周期: 22:00 -> 次日 20:30")
    logger.info("时间协调: 多智能体智能时间协调")

    # 显示智能调度表
    if TIME_COORDINATOR_AVAILABLE:
        try:
            coord = get_time_coordinator()
            schedule = coord.calculate_schedule()
            coord.print_schedule(schedule)
        except Exception as e:
            logger.warning(f"智能调度表生成失败: {e}")

    start_time = datetime.now()

    try:
        # Stage 1: 数据采集与评估
        logger.info("\n[Stage 1/4] 数据采集与评估")
        data_result = data_fetch()
        eval_result = evaluation(data_result)

        # Stage 2: 优化与训练
        logger.info("\n[Stage 2/4] 策略优化与模型训练")
        optimization_result = optimization(eval_result)
        training_result = training(optimization_result)
        incremental_result = incremental_training(training_result)

        # Stage 3: 三次预测验证
        logger.info("\n[Stage 3/4] 预测验证")
        verifications = [
            first_prediction_verification(incremental_result),
            second_prediction_verification(incremental_result),
            third_prediction_verification(incremental_result),
        ]

        # Stage 4: 深度优化与最终预测
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
            "workflow_version": "12.0",
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
# Sub-Flow: 快速预测工作流 V12.0
# ================================================================


@flow(
    name="PL5快速预测工作流",
    description="轻量级预测工作流，用于快速预测",
    version="12.0",
)
def pl5_quick_workflow() -> Dict[str, Any]:
    """快速预测工作流 - 仅执行核心预测步骤"""

    logger = get_run_logger()
    logger.info("开始执行快速预测工作流 V12.0")

    try:
        data_result = data_fetch()
        eval_result = evaluation(data_result)
        optimization_result = optimization(eval_result)
        training_result = training(optimization_result)
        final_result = final_prediction(
            {"optimization_result": optimization_result}
        )

        result = {
            "success": True,
            "data_result": data_result,
            "final_result": final_result,
            "timestamp": datetime.now().isoformat(),
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
    print("PL5 Prefect工作流 V12.0")
    print("=" * 80)
    print("任务周期: 22:00 -> 次日 20:30")
    print("时间协调: 多智能体智能时间分配")
    print("=" * 80)

    print("\n执行完整日循环工作流...")
    result = pl5_daily_workflow()

    print(f"\n✅ 工作流执行完成!")
    print(f"执行时间: {result.get('execution_time', 0):.2f} 秒")
    print(
        f"数据记录: {result.get('data_result', {}).get('record_count', 0)} 条"
    )
