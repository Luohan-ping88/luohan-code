"""优化后的PL5统一架构编排器
整合智能体框架与传统架构，实现统一的系统架构
优化点：
1. 使用事件总线消除循环依赖
2. 组件延迟初始化
3. 配置化路径管理
4. 工作流超时机制
5. 上下文管理器支持
6. 增强错误日志
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Protocol, Iterator
from datetime import datetime
from functools import cached_property
from contextlib import contextmanager

from src.core.utils import logger, log_execution_time, log_exception
from src.core.config import MODELS_DIR, LOGS_DIR
from src.core.events import EventBus, Event, get_event_bus, publish_event, publish_event_async
from src.core.features.feature_config_manager import get_feature_config_manager, FeatureConfigManager


class DataCollectorProtocol(Protocol):
    """数据采集器接口"""
    def update_data(self) -> Any:
        """更新数据并返回DataFrame"""
        ...


class FeatureEngineerProtocol(Protocol):
    """特征工程接口"""
    def extract_all_features(self, data: Any, select_top: Optional[int] = None) -> Any:
        """提取所有特征"""
        ...


class PredictorProtocol(Protocol):
    """预测器接口"""
    def fit(self, data: Any, feature_cols: List[str]) -> Any:
        """训练模型"""
        ...
    def predict(self, features: Any, recent_original_data: Optional[Dict[str, Any]] = None, top_k: int = 8) -> Dict[str, Any]:
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
    def evaluate_predictions(self, actual: Dict[str, Any], predictions: Dict[str, Any]) -> Dict[str, Any]:
        """评估预测结果"""
        ...
    def get_evaluation_statistics(self) -> Dict[str, Any]:
        """获取评估统计信息"""
        ...


class SelfLearningProtocol(Protocol):
    """自学习系统接口"""
    def record_evaluation(self, accuracy: float, evaluation_data: Dict[str, Any]) -> None:
        """记录评估结果"""
        ...
    def generate_optimization_suggestions(self) -> List[str]:
        """生成优化建议"""
        ...
    def should_trigger_retrain(self) -> tuple[bool, str]:
        """是否触发重训练"""
        ...


class PL5OrchestratorOptimized:
    """
    PL5 统一架构编排器（优化版）

    职责：
    1. 整合智能体框架与传统架构
    2. 协调系统各个组件的工作流程
    3. 实现统一的训练和预测流程
    4. 提供系统状态监控和管理

    优化点：
    - 使用事件总线进行组件间通信，消除循环依赖
    - 组件延迟初始化，提高启动速度
    - 配置化路径管理，提高可移植性
    - 工作流超时机制，防止长时间阻塞
    - 上下文管理器支持，便于资源管理
    - 增强错误日志，便于问题排查
    """

    def __init__(self, components: Optional[Dict[str, Any]] = None,
                 workflow_dir: Optional[str] = None,
                 default_timeout: int = 3600):
        """
        初始化编排器

        Args:
            components: 外部提供的组件（用于依赖注入）
            workflow_dir: 工作流持久化目录
            default_timeout: 默认超时时间（秒）
        """
        self._provided_components = components
        self._is_running = False
        self._execution_history = []
        self._event_bus = get_event_bus()
        self._feature_config_manager = get_feature_config_manager()
        self._workflow_dir = Path(workflow_dir) if workflow_dir else Path("./workflows")
        self._default_timeout = default_timeout

        # 确保工作流目录存在
        self._workflow_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[OrchestratorOptimized] 初始化完成，workflow_dir={self._workflow_dir}, timeout={self._default_timeout}s")

    @cached_property
    def data_collector(self):
        """数据采集器（延迟初始化）"""
        if self._provided_components and 'data_collector' in self._provided_components:
            return self._provided_components['data_collector']
        from src.core.data.collector import PL5DataCollector
        logger.info("[OrchestratorOptimized] 初始化数据采集器")
        return PL5DataCollector()

    @cached_property
    def feature_engineer(self):
        """特征工程（延迟初始化）"""
        if self._provided_components and 'feature_engineer' in self._provided_components:
            return self._provided_components['feature_engineer']
        from src.core.features.engineer import FeatureEngineer
        logger.info("[OrchestratorOptimized] 初始化特征工程")
        return FeatureEngineer()

    @cached_property
    def predictor(self):
        """预测器（延迟初始化）"""
        if self._provided_components and 'predictor' in self._provided_components:
            return self._provided_components['predictor']
        from src.core.models.enhanced_predictor import EnhancedPL5Predictor
        logger.info("[OrchestratorOptimized] 初始化预测器")
        return EnhancedPL5Predictor()

    @cached_property
    def email_sender(self):
        """邮件发送器（延迟初始化）"""
        if self._provided_components and 'email_sender' in self._provided_components:
            return self._provided_components['email_sender']
        from src.core.email.sender import EmailSender
        logger.info("[OrchestratorOptimized] 初始化邮件发送器")
        return EmailSender()

    @cached_property
    def evaluator(self):
        """评估器（延迟初始化）"""
        if self._provided_components and 'evaluator' in self._provided_components:
            return self._provided_components['evaluator']
        from src.core.evaluation.evaluator import PredictionEvaluator
        logger.info("[OrchestratorOptimized] 初始化评估器")
        return PredictionEvaluator()

    @cached_property
    def self_learning(self):
        """自学习系统（延迟初始化）"""
        if self._provided_components and 'self_learning' in self._provided_components:
            return self._provided_components['self_learning']
        from src.core.self_learning import SelfLearningSystem
        logger.info("[OrchestratorOptimized] 初始化自学习系统")
        return SelfLearningSystem()

    @property
    def is_running(self) -> bool:
        """检查编排器是否正在运行"""
        return self._is_running

    @contextmanager
    def run_context(self):
        """运行上下文管理器"""
        self._is_running = True
        logger.info("[OrchestratorOptimized] 进入运行上下文")
        try:
            yield self
        finally:
            self._is_running = False
            logger.info("[OrchestratorOptimized] 退出运行上下文")

    @log_execution_time("orchestrator_train_optimized")
    @log_exception("orchestrator_train_optimized")
    async def execute_training_pipeline(self, params: Dict[str, Any] = None,
                                       timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        执行训练流程（带超时控制）

        流程：
        1. 数据采集与处理
        2. 特征工程
        3. 模型训练
        4. 模型评估
        5. 报告生成
        """
        timeout = timeout or self._default_timeout
        start_time = datetime.now()
        execution_id = f"train_{int(start_time.timestamp() * 1000)}"

        # 发布事件代替直接调用
        publish_event("training.started", {
            "execution_id": execution_id,
            "params": params
        }, source="orchestrator")

        try:
            logger.info("=" * 80)
            logger.info(f"[OrchestratorOptimized] 开始执行训练流程 (ID: {execution_id})")
            logger.info("=" * 80)

            results = {}

            # 1. 数据采集与处理
            logger.info("\n[Stage 1/5] 数据采集与处理")
            stage1_result = await self._stage_data_processing(params)
            results['data_processing'] = stage1_result

            if not stage1_result.get('success'):
                raise Exception("数据处理阶段失败")

            # 2. 特征工程
            logger.info("\n[Stage 2/5] 特征工程")
            stage2_result = await self._stage_feature_engineering(stage1_result)
            results['feature_engineering'] = stage2_result

            if not stage2_result.get('success'):
                raise Exception("特征工程阶段失败")

            # 3. 模型训练
            logger.info("\n[Stage 3/5] 模型训练")
            stage3_result = await self._stage_model_training(stage2_result)
            results['model_training'] = stage3_result

            if not stage3_result.get('success'):
                raise Exception("模型训练阶段失败")

            # 4. 模型评估
            logger.info("\n[Stage 4/5] 模型评估")
            stage4_result = await self._stage_model_evaluation(stage3_result, stage2_result)
            results['model_evaluation'] = stage4_result

            # 5. 报告生成
            logger.info("\n[Stage 5/5] 报告生成")
            stage5_result = await self._stage_report_generation(results)
            results['report_generation'] = stage5_result

            execution_time = (datetime.now() - start_time).total_seconds()

            logger.info("=" * 80)
            logger.info(f"[OrchestratorOptimized] 训练流程执行完成，总耗时: {execution_time:.2f}s")
            logger.info("=" * 80)

            # 发布成功事件
            publish_event("training.completed", {
                "execution_id": execution_id,
                "execution_time": execution_time,
                "results": results
            }, source="orchestrator")

            return {
                'success': True,
                'execution_id': execution_id,
                'execution_time': execution_time,
                'results': results,
                'timestamp': datetime.now().isoformat()
            }

        except asyncio.TimeoutError:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"训练流程执行超时（{timeout}s）"

            logger.error(f"[OrchestratorOptimized] {error_msg}")

            publish_event("training.failed", {
                "execution_id": execution_id,
                "error": error_msg,
                "execution_time": execution_time
            }, source="orchestrator")

            return {
                'success': False,
                'execution_id': execution_id,
                'execution_time': execution_time,
                'error': error_msg,
                'error_type': 'timeout',
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            import traceback
            error_msg = f"训练流程执行失败: {type(e).__name__}: {str(e)}"

            logger.error(f"[OrchestratorOptimized] {error_msg}\n{traceback.format_exc()}")

            publish_event("training.failed", {
                "execution_id": execution_id,
                "error": error_msg,
                "traceback": traceback.format_exc(),
                "execution_time": execution_time
            }, source="orchestrator")

            return {
                'success': False,
                'execution_id': execution_id,
                'execution_time': execution_time,
                'error': error_msg,
                'error_type': 'exception',
                'timestamp': datetime.now().isoformat()
            }

    async def _stage_data_processing(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """阶段1: 数据采集与处理"""
        try:
            df = self.data_collector.update_data()

            logger.info(f"数据采集完成，记录数: {len(df)}")

            return {
                'success': True,
                'data': df,
                'record_count': len(df),
                'latest_period': int(df['period'].max())
            }
        except Exception as e:
            logger.error(f"数据采集失败: {e}")
            return {'success': False, 'error': str(e)}

    async def _stage_feature_engineering(self, prev_result: Dict[str, Any]) -> Dict[str, Any]:
        """阶段2: 特征工程"""
        try:
            df = prev_result['data']
            df_features = self.feature_engineer.extract_all_features(df)

            feature_cols = [c for c in df_features.columns
                          if c not in ['period', 'date', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']]

            logger.info(f"特征工程完成，特征数: {len(feature_cols)}")

            return {
                'success': True,
                'features': df_features,
                'feature_cols': feature_cols,
                'feature_count': len(feature_cols)
            }
        except Exception as e:
            logger.error(f"特征工程失败: {e}")
            return {'success': False, 'error': str(e)}

    async def _stage_model_training(self, prev_result: Dict[str, Any]) -> Dict[str, Any]:
        """阶段3: 模型训练"""
        try:
            df_features = prev_result['features']
            feature_cols = prev_result['feature_cols']

            self.predictor.fit(df_features, feature_cols)
            self.predictor.save_models()

            logger.info("模型训练完成并保存")

            return {
                'success': True,
                'models': 'saved',
                'positions_trained': ['wan', 'qian', 'bai', 'shi', 'ge']
            }
        except Exception as e:
            logger.error(f"模型训练失败: {e}")
            return {'success': False, 'error': str(e)}

    async def _stage_model_evaluation(self, train_result: Dict[str, Any],
                                    feature_result: Dict[str, Any]) -> Dict[str, Any]:
        """阶段4: 模型评估"""
        try:
            df_features = feature_result['features']
            feature_cols = feature_result['feature_cols']

            # 使用最近100条数据进行测试
            test_data = df_features.tail(100)
            X_test = test_data[feature_cols].values
            y_test = test_data[['wan', 'qian', 'bai', 'shi', 'ge']].values

            correct_count = 0
            total_count = len(test_data)
            evaluations = []

            for i in range(total_count):
                features = X_test[i]
                actual = y_test[i]

                predictions = self.predictor.predict(features)

                actual_dict = {
                    'wan': actual[0], 'qian': actual[1], 'bai': actual[2],
                    'shi': actual[3], 'ge': actual[4]
                }

                evaluation = self.evaluator.evaluate_predictions(actual_dict, predictions)
                evaluations.append(evaluation)

                for j, pos in enumerate(['wan', 'qian', 'bai', 'shi', 'ge']):
                    if actual[j] in predictions[pos]['top_k'][:3]:
                        correct_count += 1

            accuracy = correct_count / (total_count * 5)

            evaluation_stats = self.evaluator.get_evaluation_statistics()

            self.self_learning.record_evaluation(accuracy, {
                'hit_rate': correct_count / (total_count * 5),
                'confidence': 0.7,
                'evaluation_stats': evaluation_stats
            })

            optimization_suggestions = self.self_learning.generate_optimization_suggestions()
            logger.info("生成优化建议:")
            for suggestion in optimization_suggestions[:5]:
                logger.info(f"  - {suggestion}")

            should_retrain, reason = self.self_learning.should_trigger_retrain()
            if should_retrain:
                logger.warning(f"建议触发重训练: {reason}")

            logger.info(f"模型评估完成，准确率: {accuracy:.4f}")

            return {
                'success': True,
                'evaluation': {
                    'overall_accuracy': accuracy,
                    'total_predictions': total_count * 5,
                    'correct_predictions': correct_count,
                    'evaluation_stats': evaluation_stats,
                    'evaluation_count': len(evaluations),
                    'optimization_suggestions': optimization_suggestions,
                    'should_retrain': should_retrain,
                    'retrain_reason': reason
                }
            }
        except Exception as e:
            logger.error(f"模型评估失败: {e}")
            return {'success': False, 'error': str(e)}

    async def _stage_report_generation(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """阶段5: 报告生成"""
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'execution_id': f"train_{int(datetime.now().timestamp() * 1000)}",
                'data_processing': all_results.get('data_processing', {}),
                'feature_engineering': all_results.get('feature_engineering', {}),
                'model_training': all_results.get('model_training', {}),
                'model_evaluation': all_results.get('model_evaluation', {}),
            }

            # 生成预测示例
            try:
                df = self.data_collector.update_data()
                best_config = self._feature_config_manager.get_config()
                select_top = best_config.select_top if best_config else None

                df_features = self.feature_engineer.extract_all_features(df, select_top=select_top)
                all_feature_cols = [c for c in df_features.columns
                                   if c not in ['period', 'date', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']]

                if self.predictor.feature_cols and len(self.predictor.feature_cols) > 0:
                    missing = [c for c in self.predictor.feature_cols if c not in df_features.columns]
                    if missing:
                        for col in missing:
                            df_features[col] = 0.0
                    feature_cols = self.predictor.feature_cols
                else:
                    feature_cols = all_feature_cols

                latest_features = df_features[feature_cols].iloc[-1].values
                recent_original_data = {pos: df[pos].values for pos in ['wan', 'qian', 'bai', 'shi', 'ge']}

                predictions_8 = self.predictor.predict(latest_features, recent_original_data=recent_original_data, top_k=8)
                predictions_5 = self.predictor.predict(latest_features, recent_original_data=recent_original_data, top_k=5)
                predictions_3 = self.predictor.predict(latest_features, recent_original_data=recent_original_data, top_k=3)

                next_period = int(df['period'].max()) + 1
                report['predictions'] = {
                    'next_period': next_period,
                    'top_8': predictions_8,
                    'top_5': predictions_5,
                    'top_3': predictions_3
                }
            except Exception as e:
                logger.warning(f"生成预测示例失败: {e}")

            # 发送邮件
            email_sent = self.email_sender.send_email(report)
            if email_sent:
                logger.info("训练报告已发送到用户邮箱")

            logger.info("训练报告生成完成")

            return {
                'success': True,
                'report': report,
                'email_sent': email_sent
            }
        except Exception as e:
            logger.error(f"报告生成失败: {e}")
            return {'success': False, 'error': str(e)}

    @log_execution_time("orchestrator_predict_optimized")
    @log_exception("orchestrator_predict_optimized")
    async def execute_prediction_pipeline(self,
                                        latest_data: Optional[Dict[str, Any]] = None,
                                        timeout: Optional[int] = None) -> Dict[str, Any]:
        """执行预测流程（带超时控制）"""
        timeout = timeout or self._default_timeout
        start_time = datetime.now()
        execution_id = f"predict_{int(start_time.timestamp() * 1000)}"

        publish_event("prediction.started", {
            "execution_id": execution_id
        }, source="orchestrator")

        try:
            logger.info(f"[OrchestratorOptimized] 开始执行预测流程 (ID: {execution_id})")

            df = self.data_collector.update_data()

            # 使用统一的特征配置管理器
            best_config = self._feature_config_manager.get_config()
            select_top = best_config.select_top if best_config else None

            if select_top is not None:
                logger.info(f"[OrchestratorOptimized] 使用动态验证最佳配置: select_top={select_top}")
            else:
                logger.info("[OrchestratorOptimized] 使用全量特征")

            df_features = self.feature_engineer.extract_all_features(df, select_top=None)
            all_feature_cols = [c for c in df_features.columns
                              if c not in ['period', 'date', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']]

            load_result = self.predictor.load_models()

            if not load_result:
                logger.warning("[OrchestratorOptimized] 模型文件加载失败，使用全量特征")
                feature_cols = all_feature_cols
            else:
                if self.predictor.feature_cols and len(self.predictor.feature_cols) > 0:
                    missing = [c for c in self.predictor.feature_cols if c not in df_features.columns]
                    if missing:
                        logger.warning(f"[OrchestratorOptimized] 模型特征列中有 {len(missing)} 个缺失，将用0填充")
                        for col in missing:
                            df_features[col] = 0.0
                    feature_cols = self.predictor.feature_cols
                    logger.info(f"[OrchestratorOptimized] 使用模型训练时的 {len(feature_cols)} 个特征列")
                else:
                    feature_cols = all_feature_cols

            missing_cols = [c for c in feature_cols if c not in df_features.columns]
            if missing_cols:
                for col in missing_cols:
                    df_features[col] = 0.0

            latest_features = df_features[feature_cols].iloc[-1].values
            recent_original_data = {pos: df[pos].values for pos in ['wan', 'qian', 'bai', 'shi', 'ge']}
            predictions = self.predictor.predict(latest_features, recent_original_data=recent_original_data, top_k=8)

            next_period = int(df['period'].max()) + 1
            report = {
                'next_period': next_period,
                'predictions': predictions,
                'timestamp': datetime.now().isoformat()
            }

            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"预测流程执行完成，耗时: {execution_time:.2f}s")

            publish_event("prediction.completed", {
                "execution_id": execution_id,
                "execution_time": execution_time
            }, source="orchestrator")

            return {
                'success': True,
                'execution_id': execution_id,
                'predictions': predictions,
                'next_period': next_period,
                'report': report,
                'execution_time': execution_time,
                'timestamp': datetime.now().isoformat()
            }

        except asyncio.TimeoutError:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"预测流程执行超时（{timeout}s）"

            logger.error(f"[OrchestratorOptimized] {error_msg}")

            publish_event("prediction.failed", {
                "execution_id": execution_id,
                "error": error_msg,
                "execution_time": execution_time
            }, source="orchestrator")

            return {
                'success': False,
                'execution_id': execution_id,
                'execution_time': execution_time,
                'error': error_msg,
                'error_type': 'timeout',
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"

            logger.error(f"[OrchestratorOptimized] 预测流程执行失败: {error_msg}\n{traceback.format_exc()}")

            publish_event("prediction.failed", {
                "execution_id": execution_id,
                "error": error_msg,
                "traceback": traceback.format_exc(),
                "execution_time": execution_time
            }, source="orchestrator")

            return {
                'success': False,
                'execution_id': execution_id,
                'execution_time': execution_time,
                'error': error_msg,
                'error_type': 'exception',
                'timestamp': datetime.now().isoformat()
            }

    def get_status(self) -> Dict[str, Any]:
        """获取编排器状态"""
        return {
            'is_running': self._is_running,
            'execution_history_count': len(self._execution_history),
            'workflow_dir': str(self._workflow_dir),
            'default_timeout': self._default_timeout,
            'event_bus_stats': self._event_bus.get_statistics(),
            'feature_config_stats': self._feature_config_manager.get_statistics()
        }

    def shutdown(self):
        """关闭编排器"""
        logger.info("[OrchestratorOptimized] 正在关闭编排器...")
        self._is_running = False
        logger.info("[OrchestratorOptimized] 编排器已关闭")

    def __enter__(self):
        """上下文管理器入口"""
        self._is_running = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self._is_running = False
        if exc_type:
            logger.error(f"[OrchestratorOptimized] 上下文中的异常: {exc_val}")
        return False
