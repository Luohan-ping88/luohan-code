"""
评估智能体 - 负责模型评估、预测验证和性能报告
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import numpy as np

from .base_agent import BaseAgent, AgentTask, AgentResult

logger = logging.getLogger(__name__)


class EvaluationAgent(BaseAgent):
    """
    评估智能体
    
    职责:
    - 评估模型预测性能
    - 验证预测结果
    - 生成性能报告
    - 追踪预测准确率
    """
    
    def __init__(self, max_workers: int = 4):
        super().__init__(name="EvaluationAgent", max_workers=max_workers)
        self.evaluation_history: List[Dict] = []
        self.prediction_tracker: Dict[str, List] = {}
        self.current_evaluation = None
        
    async def execute(self, task: AgentTask) -> AgentResult:
        """执行评估任务"""
        start_time = datetime.now()
        
        try:
            action = task.params.get('action', 'evaluate')
            
            if action == 'evaluate':
                result = await self.evaluate_predictions(task.params)
            elif action == 'verify':
                result = await self.verify_predictions(task.params)
            elif action == 'backtest':
                result = await self.backtest_model(task.params)
            elif action == 'report':
                result = await self.generate_performance_report(task.params)
            elif action == 'track':
                result = await self.track_prediction(task.params)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    success=False,
                    data={'error': f'Unknown action: {action}'},
                    execution_time=(datetime.now() - start_time).total_seconds(),
                    error_message=f'Unknown action: {action}'
                )
                
            return AgentResult(
                task_id=task.task_id,
                success=True,
                data=result,
                execution_time=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            logger.error(f"EvaluationAgent执行失败: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                data={},
                execution_time=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )
    
    def validate(self, task: AgentTask) -> bool:
        """验证任务参数"""
        return True
    
    def get_capabilities(self) -> Dict[str, Any]:
        """获取智能体能力"""
        return {
            'name': self.name,
            'actions': ['evaluate', 'verify', 'backtest', 'report', 'track'],
            'metrics': ['accuracy', 'precision', 'recall', 'f1'],
            'evaluation_history_count': len(self.evaluation_history)
        }
    
    async def evaluate_predictions(self, params: Dict) -> Dict[str, Any]:
        """评估预测结果"""
        try:
            from src.core.models.predictor import PL5Predictor
            from src.core.models.model_evaluator import ModelEvaluator
            from src.core.data import PL5DataCollectorV8
            
            self.is_running = True
            self.current_evaluation = {
                'start_time': datetime.now(),
                'action': 'evaluate',
                'status': 'running'
            }
            
            # 加载数据
            collector = PL5DataCollectorV8()
            data = collector.load_processed_data()
            
            if data is None or len(data) < 100:
                return {
                    'action': 'evaluate',
                    'status': 'error',
                    'error': 'Insufficient data'
                }
            
            # 初始化评估器
            evaluator = ModelEvaluator()
            
            # 加载预测器
            predictor = PL5Predictor()
            
            # 执行评估
            from src.core.features import FeatureEngineer
            fe = FeatureEngineer()
            features = fe.extract_features(data)
            labels = data[['wan', 'qian', 'bai', 'shi', 'ge']].values
            
            # 评估结果
            eval_result = evaluator.evaluate(predictor, features, labels)
            
            # 计算详细指标
            metrics = self._calculate_detailed_metrics(eval_result, labels)
            
            # 记录评估历史
            eval_record = {
                'timestamp': datetime.now().isoformat(),
                'data_size': len(data),
                'metrics': metrics,
                'status': 'success'
            }
            self.evaluation_history.append(eval_record)
            
            self.is_running = False
            self.current_evaluation = None
            
            return {
                'action': 'evaluate',
                'status': 'success',
                'evaluation': eval_result,
                'detailed_metrics': metrics
            }
            
        except Exception as e:
            logger.error(f"评估失败: {e}")
            self.is_running = False
            self.current_evaluation = None
            return {
                'action': 'evaluate',
                'status': 'error',
                'error': str(e)
            }
    
    async def verify_predictions(self, params: Dict) -> Dict[str, Any]:
        """验证预测结果"""
        try:
            from src.core.models.predictor import PL5Predictor
            from src.core.data import PL5DataCollectorV8
            
            # 获取预测和实际结果
            predictions = params.get('predictions')
            actuals = params.get('actuals')
            
            if predictions is None or actuals is None:
                return {
                    'action': 'verify',
                    'status': 'error',
                    'error': 'Missing predictions or actuals'
                }
            
            # 计算验证结果
            predictions = np.array(predictions)
            actuals = np.array(actuals)
            
            # 位置级准确率
            position_accuracy = {}
            for i, pos in enumerate(['wan', 'qian', 'bai', 'shi', 'ge']):
                if i < predictions.shape[1] and i < actuals.shape[1]:
                    correct = np.sum(predictions[:, i] == actuals[:, i])
                    acc = correct / len(predictions)
                    position_accuracy[pos] = float(acc)
            
            # 完全匹配数
            exact_matches = np.sum(np.all(predictions == actuals, axis=1))
            exact_match_rate = exact_matches / len(predictions)
            
            # 至少对一个位置
            partial_match = np.sum(np.any(predictions == actuals, axis=1))
            partial_match_rate = partial_match / len(predictions)
            
            verification_result = {
                'total_predictions': len(predictions),
                'position_accuracy': position_accuracy,
                'exact_match_rate': float(exact_match_rate),
                'partial_match_rate': float(partial_match_rate),
                'exact_matches': int(exact_matches)
            }
            
            return {
                'action': 'verify',
                'status': 'success',
                'verification': verification_result
            }
            
        except Exception as e:
            logger.error(f"验证失败: {e}")
            return {
                'action': 'verify',
                'status': 'error',
                'error': str(e)
            }
    
    async def backtest_model(self, params: Dict) -> Dict[str, Any]:
        """回测模型性能"""
        try:
            from src.core.models.predictor import PL5Predictor
            from src.core.data import PL5DataCollectorV8
            from src.core.features import FeatureEngineer
            
            # 获取回测配置
            window_size = params.get('window_size', 100)
            step_size = params.get('step_size', 10)
            
            # 加载数据
            collector = PL5DataCollectorV8()
            data = collector.load_processed_data()
            
            if data is None or len(data) < window_size * 2:
                return {
                    'action': 'backtest',
                    'status': 'error',
                    'error': 'Insufficient data for backtesting'
                }
            
            fe = FeatureEngineer()
            features = fe.extract_features(data)
            labels = data[['wan', 'qian', 'bai', 'shi', 'ge']].values
            
            # 执行回测
            backtest_results = []
            predictor = PL5Predictor()
            
            for i in range(0, len(data) - window_size, step_size):
                train_end = i + window_size
                test_start = train_end
                test_end = min(test_start + step_size, len(data))
                
                if test_end <= test_start:
                    continue
                    
                # 训练
                train_features = features[i:train_end]
                train_labels = labels[i:train_end]
                predictor.fit(train_features, train_labels)
                
                # 测试
                test_features = features[test_start:test_end]
                test_labels = labels[test_start:test_end]
                
                # 预测
                preds = predictor.predict(test_features)
                
                # 计算准确率
                correct = np.sum(np.all(preds == test_labels, axis=1))
                acc = correct / len(test_labels)
                
                backtest_results.append({
                    'train_range': f'{i}:{train_end}',
                    'test_range': f'{test_start}:{test_end}',
                    'accuracy': float(acc)
                })
            
            # 汇总结果
            if backtest_results:
                accuracies = [r['accuracy'] for r in backtest_results]
                summary = {
                    'mean_accuracy': float(np.mean(accuracies)),
                    'std_accuracy': float(np.std(accuracies)),
                    'min_accuracy': float(np.min(accuracies)),
                    'max_accuracy': float(np.max(accuracies)),
                    'total_tests': len(backtest_results)
                }
            else:
                summary = {
                    'mean_accuracy': 0.0,
                    'total_tests': 0
                }
                
            return {
                'action': 'backtest',
                'status': 'success',
                'summary': summary,
                'detailed_results': backtest_results[-20:]  # 最近20个
            }
            
        except Exception as e:
            logger.error(f"回测失败: {e}")
            return {
                'action': 'backtest',
                'status': 'error',
                'error': str(e)
            }
    
    async def generate_performance_report(self, params: Dict) -> Dict[str, Any]:
        """生成性能报告"""
        try:
            report_type = params.get('report_type', 'comprehensive')
            
            # 收集评估历史
            recent_evals = self.evaluation_history[-10:]
            
            # 计算性能趋势
            if recent_evals:
                all_metrics = [e['metrics'] for e in recent_evals]
                
                # 计算趋势
                if len(all_metrics) >= 2:
                    first_acc = all_metrics[0].get('overall_accuracy', 0)
                    last_acc = all_metrics[-1].get('overall_accuracy', 0)
                    trend = 'improving' if last_acc > first_acc else 'declining' if last_acc < first_acc else 'stable'
                else:
                    trend = 'insufficient_data'
            else:
                all_metrics = []
                trend = 'no_evaluation_history'
            
            report = {
                'title': f'排列五模型性能报告 - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                'type': report_type,
                'timestamp': datetime.now().isoformat(),
                'total_evaluations': len(self.evaluation_history),
                'recent_evaluations': len(recent_evals),
                'performance_trend': trend,
                'metrics_summary': self._summarize_metrics(all_metrics),
                'recommendations': self._generate_recommendations(recent_evals)
            }
            
            return {
                'action': 'report',
                'status': 'success',
                'report': report
            }
            
        except Exception as e:
            logger.error(f"报告生成失败: {e}")
            return {
                'action': 'report',
                'status': 'error',
                'error': str(e)
            }
    
    async def track_prediction(self, params: Dict) -> Dict[str, Any]:
        """追踪预测"""
        prediction_id = params.get('prediction_id', str(datetime.now().timestamp()))
        prediction = params.get('prediction')
        
        if prediction is not None:
            if prediction_id not in self.prediction_tracker:
                self.prediction_tracker[prediction_id] = []
            self.prediction_tracker[prediction_id].append({
                'timestamp': datetime.now().isoformat(),
                'prediction': prediction,
                'verified': False
            })
            
        return {
            'action': 'track',
            'status': 'success',
            'prediction_id': prediction_id,
            'tracked_count': len(self.prediction_tracker.get(prediction_id, []))
        }
    
    def _calculate_detailed_metrics(self, eval_result: Dict, labels: np.ndarray) -> Dict[str, Any]:
        """计算详细指标"""
        metrics = {}
        
        if isinstance(eval_result, dict):
            metrics.update(eval_result)
            
        # 添加额外统计
        metrics['sample_size'] = len(labels)
        metrics['timestamp'] = datetime.now().isoformat()
        
        return metrics
    
    def _summarize_metrics(self, metrics_list: List[Dict]) -> Dict[str, Any]:
        """汇总指标"""
        if not metrics_list:
            return {}
            
        summary = {}
        
        for key in ['overall_accuracy', 'position_accuracy']:
            values = [m.get(key, 0) for m in metrics_list if key in m]
            if values:
                summary[key] = {
                    'mean': float(np.mean(values)),
                    'std': float(np.std(values)),
                    'latest': values[-1] if values else 0
                }
                
        return summary
    
    def _generate_recommendations(self, evaluations: List[Dict]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if not evaluations:
            recommendations.append("建议先完成模型训练后再进行评估")
            return recommendations
            
        recent_metrics = evaluations[-1]['metrics'] if evaluations else {}
        acc = recent_metrics.get('overall_accuracy', 0)
        
        if acc < 0.01:
            recommendations.append("准确率较低，建议增加训练数据量")
            recommendations.append("考虑调整模型超参数")
        elif acc < 0.05:
            recommendations.append("准确率一般，建议尝试集成学习")
        else:
            recommendations.append("准确率表现良好，继续监控")
            
        return recommendations
    
    def get_status(self) -> Dict[str, Any]:
        """获取智能体状态"""
        return {
            'name': self.name,
            'is_running': self.is_running,
            'evaluation_history_count': len(self.evaluation_history),
            'tracked_predictions': len(self.prediction_tracker),
            'metrics': self.metrics
        }
