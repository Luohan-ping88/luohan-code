"""
训练智能体 - 负责模型训练、优化和版本管理
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import time

from .base_agent import BaseAgent, AgentTask, AgentResult

logger = logging.getLogger(__name__)


class TrainingAgent(BaseAgent):
    """
    训练智能体
    
    职责:
    - 执行模型训练
    - 管理训练配置
    - 追踪训练进度
    - 保存训练结果
    """
    
    def __init__(self, max_workers: int = 4):
        super().__init__(name="TrainingAgent", max_workers=max_workers)
        self.training_config = {
            'model_type': 'stacking',
            'iterations': 100,
            'learning_rate': 0.05,
            'early_stopping_rounds': 10
        }
        self.training_history: List[Dict] = []
        self.current_training = None
        
    async def execute(self, task: AgentTask) -> AgentResult:
        """执行训练任务"""
        start_time = datetime.now()
        
        try:
            action = task.params.get('action', 'train')
            
            if action == 'train':
                result = await self.train_model(task.params)
            elif action == 'incremental':
                result = await self.incremental_train(task.params)
            elif action == 'validate_config':
                result = await self.validate_config(task.params)
            elif action == 'get_status':
                result = self.get_training_status(task.params)
            elif action == 'abort':
                result = await self.abort_training(task.params)
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
            logger.error(f"TrainingAgent执行失败: {e}")
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
            'actions': ['train', 'incremental', 'validate_config', 'get_status', 'abort'],
            'supported_models': ['stacking', 'hmm', 'bsts', 'evm', 'copula'],
            'training_config': self.training_config
        }
    
    async def train_model(self, params: Dict) -> Dict[str, Any]:
        """执行模型训练"""
        try:
            from src.core.models.predictor import PL5Predictor
            
            self.is_running = True
            self.current_training = {
                'start_time': datetime.now(),
                'model_type': params.get('model_type', 'stacking'),
                'status': 'training'
            }
            
            # 获取配置
            model_type = params.get('model_type', 'stacking')
            
            # 初始化预测器
            predictor = PL5Predictor()
            
            # 加载数据
            from src.core.data import PL5DataCollectorV8
            collector = PL5DataCollectorV8()
            data = collector.load_processed_data()
            
            if data is None or len(data) < 100:
                return {
                    'action': 'train',
                    'status': 'error',
                    'error': 'Insufficient training data'
                }
            
            # 提取特征和标签
            from src.core.features import FeatureEngineer
            fe = FeatureEngineer()
            
            features = fe.extract_features(data)
            labels = data[['wan', 'qian', 'bai', 'shi', 'ge']].values
            
            # 执行训练
            start_time = time.time()
            predictor.fit(features, labels)
            training_time = time.time() - start_time
            
            # 保存模型
            model_path = predictor.save_models()
            
            # 记录训练历史
            training_record = {
                'timestamp': datetime.now().isoformat(),
                'model_type': model_type,
                'training_time': training_time,
                'data_size': len(data),
                'feature_count': features.shape[1],
                'status': 'success',
                'model_path': model_path
            }
            self.training_history.append(training_record)
            
            self.is_running = False
            self.current_training = None
            
            return {
                'action': 'train',
                'status': 'success',
                'training_time': training_time,
                'model_path': model_path,
                'metrics': training_record
            }
            
        except Exception as e:
            logger.error(f"模型训练失败: {e}")
            self.is_running = False
            self.current_training = None
            return {
                'action': 'train',
                'status': 'error',
                'error': str(e)
            }
    
    async def incremental_train(self, params: Dict) -> Dict[str, Any]:
        """执行增量训练"""
        try:
            from src.core.models.predictor import PL5Predictor
            
            # 加载现有模型
            predictor = PL5Predictor()
            
            # 获取新数据
            from src.core.data import PL5DataCollectorV8
            collector = PL5DataCollectorV8()
            new_data = collector.fetch_latest()
            
            if new_data is None or len(new_data) < 10:
                return {
                    'action': 'incremental',
                    'status': 'skipped',
                    'reason': 'No new data available'
                }
            
            # 提取特征
            from src.core.features import FeatureEngineer
            fe = FeatureEngineor()
            features = fe.extract_features(new_data)
            labels = new_data[['wan', 'qian', 'bai', 'shi', 'ge']].values
            
            # 增量训练
            start_time = time.time()
            predictor.increment_fit(features, labels)
            training_time = time.time() - start_time
            
            # 保存更新后的模型
            model_path = predictor.save_models()
            
            return {
                'action': 'incremental',
                'status': 'success',
                'training_time': training_time,
                'new_records': len(new_data),
                'model_path': model_path
            }
            
        except Exception as e:
            logger.error(f"增量训练失败: {e}")
            return {
                'action': 'incremental',
                'status': 'error',
                'error': str(e)
            }
    
    async def validate_config(self, params: Dict) -> Dict[str, Any]:
        """验证训练配置"""
        config = params.get('config', self.training_config)
        
        errors = []
        warnings = []
        
        # 检查必要参数
        if 'model_type' not in config:
            errors.append('Missing required parameter: model_type')
        
        if 'iterations' in config:
            if config['iterations'] < 10:
                warnings.append('iterations too low, may underfit')
            elif config['iterations'] > 1000:
                warnings.append('iterations too high, may overfit')
                
        if 'learning_rate' in config:
            if config['learning_rate'] < 0.001:
                warnings.append('learning_rate too low')
            elif config['learning_rate'] > 0.5:
                warnings.append('learning_rate too high')
                
        return {
            'action': 'validate_config',
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'suggested_config': config
        }
    
    def get_training_status(self, params: Dict) -> Dict[str, Any]:
        """获取训练状态"""
        return {
            'action': 'get_status',
            'is_running': self.is_running,
            'current_training': self.current_training,
            'training_history': self.training_history[-10:],  # 最近10次
            'total_trainings': len(self.training_history)
        }
    
    async def abort_training(self, params: Dict) -> Dict[str, Any]:
        """中止训练"""
        if not self.is_running:
            return {
                'action': 'abort',
                'status': 'skipped',
                'reason': 'No training in progress'
            }
            
        self.is_running = False
        self.current_training = None
        
        return {
            'action': 'abort',
            'status': 'success'
        }
    
    def get_status(self) -> Dict[str, Any]:
        """获取智能体状态"""
        return {
            'name': self.name,
            'is_running': self.is_running,
            'current_training': self.current_training,
            'training_history_count': len(self.training_history),
            'metrics': self.metrics
        }
