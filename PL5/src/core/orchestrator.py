"""
PL5 统一架构编排器
整合智能体框架与传统架构，实现统一的系统架构
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Protocol
from datetime import datetime

from src.core.utils import logger, log_execution_time, log_exception
from src.core.config import MODELS_DIR, LOGS_DIR


class DataCollectorProtocol(Protocol):
    """数据采集器接口"""

    def update_data(self) -> Any:
        """更新数据并返回DataFrame"""
        ...


class FeatureEngineerProtocol(Protocol):
    """特征工程接口"""

    def extract_all_features(self, data: Any) -> Any:
        """提取所有特征"""
        ...

    def prewarm_cache(self, data: Any) -> None:
        """预热缓存"""
        ...


class PredictorProtocol(Protocol):
    """预测器接口"""

    def fit(self, data: Any, feature_cols: List[str]) -> Any:
        """训练模型"""
        ...

    def predict(
        self,
        features: Any,
        recent_original_data: Optional[Dict[str, Any]] = None,
        top_k: int = 8,
    ) -> Dict[str, Any]:
        """预测"""
        ...

    def save_models(self) -> None:
        """保存模型"""
        ...

    def load_models(self) -> bool:
        """加载模型"""
        ...

    @property
    def is_trained(self) -> bool:
        """模型是否已训练"""
        ...


class EmailSenderProtocol(Protocol):
    """邮件发送接口"""

    def send_email(self, report: Dict[str, Any]) -> bool:
        """发送邮件"""
        ...


class EvaluatorProtocol(Protocol):
    """评估器接口"""

    def evaluate_predictions(
        self, actual: Dict[str, Any], predictions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """评估预测结果"""
        ...

    def get_evaluation_statistics(self) -> Dict[str, Any]:
        """获取评估统计信息"""
        ...


class SelfLearningProtocol(Protocol):
    """自学习系统接口"""

    def record_evaluation(
        self, accuracy: float, evaluation_data: Dict[str, Any]
    ) -> None:
        """记录评估结果"""
        ...

    def generate_optimization_suggestions(self) -> List[str]:
        """生成优化建议"""
        ...

    def should_trigger_retrain(self) -> tuple[bool, str]:
        """是否触发重训练"""
        ...


class PL5Orchestrator:
    """
    PL5 统一架构编排器

    职责：
    1. 整合智能体框架与传统架构
    2. 协调系统各个组件的工作流程
    3. 实现统一的训练和预测流程
    4. 提供系统状态监控和管理
    """

    def __init__(self, components: Optional[Dict[str, Any]] = None):
        self.is_running = False
        self.execution_history = []

        # 使用依赖注入，允许外部提供组件
        if components:
            self.components = components
        else:
            # 默认组件初始化
            from src.core.data.collector import PL5DataCollector
            from src.core.features.engineer import FeatureEngineer
            from src.core.models.enhanced_predictor import EnhancedPL5Predictor
            from src.core.email.sender import EmailSender
            from src.core.evaluation.evaluator import PredictionEvaluator
            from src.core.self_learning import SelfLearningSystem

            self.components = {
                "data_collector": PL5DataCollector(),
                "feature_engineer": FeatureEngineer(),
                "predictor": EnhancedPL5Predictor(),
                "email_sender": EmailSender(),
                "evaluator": PredictionEvaluator(),
                "self_learning": SelfLearningSystem(),
            }

        logger.info("[Orchestrator] 统一架构编排器初始化完成")

    @log_execution_time("orchestrator_train")
    @log_exception("orchestrator_train")  # type: ignore[arg-type]
    async def execute_training_pipeline(
        self, params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        执行训练流程

        流程：
        1. 数据采集与处理
        2. 特征工程
        3. 模型训练
        4. 模型评估
        5. 报告生成
        """
        start_time = datetime.now()
        self.is_running = True

        try:
            logger.info("=" * 80)
            logger.info("[Orchestrator] 开始执行训练流程")
            logger.info("=" * 80)

            results = {}

            # 1. 数据采集与处理
            logger.info("\n[Stage 1/5] 数据采集与处理")
            stage1_result = await self._stage_data_processing(params)
            results["data_processing"] = stage1_result

            if not stage1_result.get("success"):
                raise Exception("数据处理阶段失败")

            # 2. 特征工程
            logger.info("\n[Stage 2/5] 特征工程")
            stage2_result = await self._stage_feature_engineering(
                stage1_result
            )
            results["feature_engineering"] = stage2_result

            if not stage2_result.get("success"):
                raise Exception("特征工程阶段失败")

            # 3. 模型训练
            logger.info("\n[Stage 3/5] 模型训练")
            stage3_result = await self._stage_model_training(stage2_result)
            results["model_training"] = stage3_result

            if not stage3_result.get("success"):
                raise Exception("模型训练阶段失败")

            # 4. 模型评估
            logger.info("\n[Stage 4/5] 模型评估")
            stage4_result = await self._stage_model_evaluation(
                stage3_result, stage2_result
            )
            results["model_evaluation"] = stage4_result

            # 5. 报告生成
            logger.info("\n[Stage 5/5] 报告生成")
            stage5_result = await self._stage_report_generation(results)
            results["report_generation"] = stage5_result

            execution_time = (datetime.now() - start_time).total_seconds()

            logger.info("=" * 80)
            logger.info(
                f"[Orchestrator] 训练流程执行完成，总耗时: {execution_time:.2f}s"
            )
            logger.info("=" * 80)

            return {
                "success": True,
                "execution_time": execution_time,
                "results": results,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[Orchestrator] 训练流程执行失败: {str(e)}")

            return {
                "success": False,
                "execution_time": execution_time,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        finally:
            self.is_running = False

    async def _stage_data_processing(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """阶段1: 数据采集与处理"""
        try:
            collector = self.components["data_collector"]
            df = collector.update_data()

            logger.info(f"数据采集完成，记录数: {len(df)}")

            return {
                "success": True,
                "data": df,
                "record_count": len(df),
                "latest_period": int(df["period"].max()),
            }
        except Exception as e:
            logger.error("数据采集失败", exception=e)
            return {"success": False, "error": str(e)}

    async def _stage_feature_engineering(
        self, prev_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """阶段2: 特征工程"""
        try:
            engineer = self.components["feature_engineer"]
            df = prev_result["data"]
            df_features = engineer.extract_all_features(df)

            feature_cols = [
                c
                for c in df_features.columns
                if c
                not in [
                    "period",
                    "date",
                    "full_number",
                    "parse_line",
                    "wan",
                    "qian",
                    "bai",
                    "shi",
                    "ge",
                ]
            ]

            logger.info(f"特征工程完成，特征数: {len(feature_cols)}")

            return {
                "success": True,
                "features": df_features,
                "feature_cols": feature_cols,
                "feature_count": len(feature_cols),
            }
        except Exception as e:
            logger.error("特征工程失败", exception=e)
            return {"success": False, "error": str(e)}

    async def _stage_model_training(
        self, prev_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """阶段3: 模型训练"""
        try:
            predictor = self.components["predictor"]
            df_features = prev_result["features"]
            feature_cols = prev_result["feature_cols"]

            predictor.fit(df_features, feature_cols)
            predictor.save_models()

            logger.info("模型训练完成并保存")

            return {
                "success": True,
                "models": "saved",
                "positions_trained": ["wan", "qian", "bai", "shi", "ge"],
            }
        except Exception as e:
            logger.error("模型训练失败", exception=e)
            return {"success": False, "error": str(e)}

    async def _stage_model_evaluation(
        self, train_result: Dict[str, Any], feature_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """阶段4: 模型评估"""
        try:
            predictor = self.components["predictor"]
            evaluator = self.components["evaluator"]
            df_features = feature_result["features"]
            feature_cols = feature_result["feature_cols"]

            # 简单评估：使用最近100条数据进行测试
            test_data = df_features.tail(100)
            X_test = test_data[feature_cols].values
            y_test = test_data[["wan", "qian", "bai", "shi", "ge"]].values

            # 评估逻辑
            correct_count = 0
            total_count = len(test_data)
            evaluations = []

            for i in range(total_count):
                features = X_test[i]
                actual = y_test[i]
                predictions = predictor.predict(features)

                # 构建实际号码字典
                actual_dict = {
                    "wan": actual[0],
                    "qian": actual[1],
                    "bai": actual[2],
                    "shi": actual[3],
                    "ge": actual[4],
                }

                # 使用评估器评估预测结果
                evaluation = evaluator.evaluate_predictions(
                    actual_dict, predictions
                )
                evaluations.append(evaluation)

                # 简单评估：检查每个位置的预测是否正确
                for j, pos in enumerate(["wan", "qian", "bai", "shi", "ge"]):
                    if actual[j] in predictions[pos]["top_k"][:3]:
                        correct_count += 1

            accuracy = correct_count / (total_count * 5)  # 5个位置

            # 计算评估统计信息
            evaluation_stats = evaluator.get_evaluation_statistics()

            # 使用自学习系统记录评估结果并生成优化建议
            self_learning = self.components["self_learning"]
            self_learning.record_evaluation(
                accuracy,
                {
                    "hit_rate": correct_count / (total_count * 5),
                    "confidence": 0.7,  # 假设默认置信度
                    "evaluation_stats": evaluation_stats,
                },
            )

            # 生成优化建议
            optimization_suggestions = (
                self_learning.generate_optimization_suggestions()
            )
            logger.info("生成优化建议:")
            for suggestion in optimization_suggestions[:5]:  # 只打印前5条建议
                logger.info(f"  - {suggestion}")

            # 检查是否需要重训练
            should_retrain, reason = self_learning.should_trigger_retrain()
            if should_retrain:
                logger.warning(f"建议触发重训练: {reason}")

            logger.info(f"模型评估完成，准确率: {accuracy:.4f}")
            logger.info(f"评估统计信息: {evaluation_stats}")

            return {
                "success": True,
                "evaluation": {
                    "overall_accuracy": accuracy,
                    "total_predictions": total_count * 5,
                    "correct_predictions": correct_count,
                    "evaluation_stats": evaluation_stats,
                    "evaluation_count": len(evaluations),
                    "optimization_suggestions": optimization_suggestions,
                    "should_retrain": should_retrain,
                    "retrain_reason": reason,
                },
            }
        except Exception as e:
            logger.error("模型评估失败", exception=e)
            return {"success": False, "error": str(e)}

    async def _stage_report_generation(
        self, all_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """阶段5: 报告生成"""
        try:
            # 生成详细的训练报告
            report = {
                "timestamp": datetime.now().isoformat(),
                "data_processing": all_results.get("data_processing", {}),
                "feature_engineering": all_results.get(
                    "feature_engineering", {}
                ),
                "model_training": all_results.get("model_training", {}),
                "model_evaluation": all_results.get("model_evaluation", {}),
                "analysis": {
                    "summary": "PL5 预测模型训练报告",
                    "performance_metrics": {
                        "overall_accuracy": all_results.get(
                            "model_evaluation", {}
                        )
                        .get("evaluation", {})
                        .get("overall_accuracy", 0.0),
                        "total_predictions": all_results.get(
                            "model_evaluation", {}
                        )
                        .get("evaluation", {})
                        .get("total_predictions", 0),
                        "correct_predictions": all_results.get(
                            "model_evaluation", {}
                        )
                        .get("evaluation", {})
                        .get("correct_predictions", 0),
                    },
                    "feature_analysis": {
                        "total_features": all_results.get(
                            "feature_engineering", {}
                        ).get("feature_count", 0),
                        "feature_selection_method": "RFE (Recursive Feature Elimination)",
                    },
                    "data_analysis": {
                        "record_count": all_results.get(
                            "data_processing", {}
                        ).get("record_count", 0),
                        "latest_period": all_results.get(
                            "data_processing", {}
                        ).get("latest_period", 0),
                    },
                },
            }

            # 生成预测示例
            try:
                # 加载最新数据
                collector = self.components["data_collector"]
                df = collector.update_data()

                # 【修复D1延伸】与 execute_prediction_pipeline 保持一致：
                # 尝试读取 best_feature_config.json，但最终用 predictor.feature_cols 对齐
                best_config_path = (
                    Path(MODELS_DIR) / "best_feature_config.json"
                )
                best_select_top = None
                if best_config_path.exists():
                    try:
                        with open(
                            best_config_path, "r", encoding="utf-8"
                        ) as f:
                            cfg_data = json.load(f)
                        best_select_top = cfg_data.get("best_config", {}).get(
                            "select_top"
                        )
                        if best_select_top is not None:
                            logger.info(
                                f"[_stage_report_generation] 使用动态验证最佳配置: select_top={best_select_top}"
                            )
                    except Exception:
                        pass

                # 提取特征（与 execute_prediction_pipeline 一致：select_top=None）
                engineer = self.components["feature_engineer"]
                df_features = engineer.extract_all_features(
                    df, select_top=None
                )
                all_feature_cols = [
                    c
                    for c in df_features.columns
                    if c
                    not in [
                        "period",
                        "date",
                        "full_number",
                        "parse_line",
                        "wan",
                        "qian",
                        "bai",
                        "shi",
                        "ge",
                    ]
                ]

                # 模型推理
                predictor = self.components["predictor"]
                # 加载训练好的模型
                load_result = predictor.load_models()
                if load_result:
                    # 【修复ISSUE-3】与 execute_prediction_pipeline 一致：使用模型训练时的 feature_cols
                    if (
                        predictor.feature_cols
                        and len(predictor.feature_cols) > 0
                    ):
                        missing = [
                            c
                            for c in predictor.feature_cols
                            if c not in df_features.columns
                        ]
                        if missing:
                            logger.warning(
                                f"[_stage_report_generation] 模型特征列中有 {len(missing)} 个缺失，将用0填充"
                            )
                            for col in missing:
                                df_features[col] = 0.0
                        feature_cols = predictor.feature_cols
                    else:
                        feature_cols = all_feature_cols
                    latest_features = df_features[feature_cols].iloc[-1].values
                    # 【修复ISSUE-1】确保传入 ndarray 而非 pandas Series（避免 iloc[-1] KeyError 陷阱）
                    recent_original_data = {
                        pos: df[pos].values
                        for pos in ["wan", "qian", "bai", "shi", "ge"]
                    }

                    # 生成8个预测号码
                    predictions_8 = predictor.predict(
                        latest_features,
                        recent_original_data=recent_original_data,
                        top_k=8,
                    )
                    # 生成5个预测号码
                    predictions_5 = predictor.predict(
                        latest_features,
                        recent_original_data=recent_original_data,
                        top_k=5,
                    )
                    # 生成3个预测号码
                    predictions_3 = predictor.predict(
                        latest_features,
                        recent_original_data=recent_original_data,
                        top_k=3,
                    )

                    next_period = int(df["period"].max()) + 1
                    report["predictions"] = {
                        "next_period": next_period,
                        "top_8": predictions_8,
                        "top_5": predictions_5,
                        "top_3": predictions_3,
                    }
            except Exception as e:
                logger.warning(f"生成预测示例失败: {str(e)}")

            # 发送邮件
            email_sender = self.components["email_sender"]
            email_sent = email_sender.send_email(report)
            if email_sent:
                logger.info("训练报告已发送到用户邮箱")
            else:
                logger.warning("训练报告邮件发送失败")

            logger.info("训练报告生成完成")

            return {
                "success": True,
                "report": report,
                "email_sent": email_sent,
            }
        except Exception as e:
            logger.error("报告生成失败", exception=e)
            return {"success": False, "error": str(e)}

    @log_execution_time("orchestrator_predict")
    @log_exception("orchestrator_predict")  # type: ignore[arg-type]
    async def execute_prediction_pipeline(
        self, latest_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行预测流程

        流程：
        1. 加载最新数据
        2. 特征提取
        3. 模型推理
        4. 结果后处理
        5. 生成预测报告
        """
        start_time = datetime.now()

        try:
            logger.info("[Orchestrator] 开始执行预测流程")

            # 1. 加载最新数据
            collector = self.components["data_collector"]
            df = collector.update_data()

            # 2. 特征提取
            # 【关键修复D1】读取 DynamicFeatureValidator 验证的最佳特征配置
            # 确保训练时发现的最佳特征组被实际应用到生产预测
            # 优先读取 logs 目录，其次 models 目录，保持与训练流程一致
            best_select_top = None  # 默认：全量特征（与历史行为一致）
            cfg_data = None
            for config_dir in [LOGS_DIR, MODELS_DIR]:
                best_config_path = (
                    Path(config_dir) / "best_feature_config.json"
                )
                if best_config_path.exists():
                    try:
                        with open(
                            best_config_path, "r", encoding="utf-8"
                        ) as f:
                            cfg_data = json.load(f)
                        logger.info(
                            f"[Orchestrator] 从 {config_dir.name}/best_feature_config.json 读取配置"
                        )
                        break
                    except Exception as cfg_err:
                        logger.warning(
                            f"[Orchestrator] 读取 {config_dir.name}/best_feature_config.json 失败: {cfg_err}"
                        )

            if cfg_data is not None:
                try:
                    # 兼容两种格式：直接配置或嵌套在 best_config 中
                    if "best_config" in cfg_data:
                        best_select_top = cfg_data["best_config"].get(
                            "select_top"
                        )
                    else:
                        best_select_top = cfg_data.get("select_top")
                    if best_select_top is not None:
                        logger.info(
                            f"[Orchestrator] 读取到动态验证最佳配置: select_top={best_select_top}，将用于生产预测"
                        )
                    else:
                        logger.info(
                            "[Orchestrator] 动态验证最佳配置中 select_top=None（已验证全量特征最优），使用全量特征"
                        )
                except Exception as cfg_err:
                    logger.warning(
                        f"[Orchestrator] 解析 best_feature_config.json 失败（非致命）: {cfg_err}，使用默认行为"
                    )

            # predict 时不限制 select_top（提取全量），再用 predictor.feature_cols 精确对齐训练特征
            engineer = self.components["feature_engineer"]
            df_features = engineer.extract_all_features(df, select_top=None)
            all_feature_cols = [
                c
                for c in df_features.columns
                if c
                not in [
                    "period",
                    "date",
                    "full_number",
                    "parse_line",
                    "wan",
                    "qian",
                    "bai",
                    "shi",
                    "ge",
                ]
            ]

            # 3. 模型推理 - 【关键修复】先加载模型，优先使用训练时保存的 feature_cols
            predictor = self.components["predictor"]
            load_result = predictor.load_models()
            logger.info(
                f"[Orchestrator] 模型加载结果: {load_result}, is_trained={predictor.is_trained}"
            )
            if not load_result:
                logger.warning(
                    "[Orchestrator] 模型文件加载失败，使用RFE选择的特征"
                )
                feature_cols = all_feature_cols
            else:
                # 【核心修复】使用模型训练时保存的 feature_cols，避免 RFE 漂移
                if predictor.feature_cols and len(predictor.feature_cols) > 0:
                    # 检查模型特征列是否都存在于当前 df_features 中
                    missing = [
                        c
                        for c in predictor.feature_cols
                        if c not in df_features.columns
                    ]
                    if missing:
                        # 【关键修复】不能回退到 RFE 选择（全量特征数不匹配），
                        # 必须用模型期望的精确特征集，哪怕有少量缺失也填充 0
                        logger.warning(
                            f"[Orchestrator] 模型特征列中有 {len(missing)} 个缺失，将用0填充: {missing[:5]}"
                        )
                        # 用模型存储的 feature_cols 作为最终选择（缺失部分自动补0）
                        feature_cols = predictor.feature_cols
                    else:
                        feature_cols = predictor.feature_cols
                        logger.info(
                            f"[Orchestrator] 使用模型训练时的 {len(feature_cols)} 个特征列（特征漂移已修复）"
                        )
                else:
                    logger.warning(
                        "[Orchestrator] 模型无 feature_cols 记录，使用RFE选择的特征"
                    )
                    feature_cols = all_feature_cols

            # 4. 使用确定的 feature_cols 提取特征（缺失列自动填0）
            missing_cols = [
                c for c in feature_cols if c not in df_features.columns
            ]
            if missing_cols:
                logger.warning(
                    f"[Orchestrator] 特征提取: {len(missing_cols)} 列缺失，自动填充0: {missing_cols[:3]}"
                )
                for col in missing_cols:
                    df_features[col] = 0.0
            latest_features = df_features[feature_cols].iloc[-1].values
            # 【修复ISSUE-1】确保传入 ndarray 而非 pandas Series（避免 iloc[-1] KeyError 陷阱）
            recent_original_data = {
                pos: df[pos].values
                for pos in ["wan", "qian", "bai", "shi", "ge"]
            }
            predictions = predictor.predict(
                latest_features,
                recent_original_data=recent_original_data,
                top_k=8,
            )

            # 4. 结果后处理
            # 这里可以添加结果后处理逻辑

            # 5. 生成预测报告
            next_period = int(df["period"].max()) + 1
            report = {
                "next_period": next_period,
                "predictions": predictions,
                "timestamp": datetime.now().isoformat(),
            }

            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"预测流程执行完成，耗时: {execution_time:.2f}s")

            return {
                "success": True,
                "predictions": predictions,
                "next_period": next_period,
                "report": report,
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            import traceback

            err_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(
                f"预测流程执行失败: {err_msg}\n{traceback.format_exc()}"
            )

            return {
                "success": False,
                "error": err_msg,
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }

    def get_status(self) -> Dict[str, Any]:
        """获取编排器状态"""
        return {
            "is_running": self.is_running,
            "components": {
                "data_collector": "initialized",
                "feature_engineer": "initialized",
                "predictor": "initialized",
            },
            "execution_history": len(self.execution_history),
        }

    def shutdown(self):
        """关闭编排器"""
        logger.info("[Orchestrator] 正在关闭编排器...")
        # 清理资源
        self.is_running = False
        logger.info("[Orchestrator] 编排器已关闭")
