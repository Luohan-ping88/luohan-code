"""
数据采集智能体 - 负责从数据源获取和处理排列五历史数据
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from .base_agent import BaseAgent, AgentTask, AgentResult

logger = logging.getLogger(__name__)


class DataAgent(BaseAgent):
    """
    数据采集智能体
    
    职责:
    - 从数据源获取最新开奖数据
    - 验证和清洗数据
    - 更新本地数据库
    - 监控数据质量
    """
    
    def __init__(self, max_workers: int = 4):
        super().__init__(name="DataAgent", max_workers=max_workers)
        self.data_source = "http://data.17500.cn/pl5_asc.txt"
        self.last_update = None
        self.quality_metrics = {
            'total_records': 0,
            'valid_records': 0,
            'error_records': 0,
            'last_quality_check': None
        }
        
    async def execute(self, task: AgentTask) -> AgentResult:
        """执行数据采集任务"""
        start_time = datetime.now()
        
        try:
            action = task.params.get('action', 'fetch')
            
            if action == 'fetch':
                result = await self.fetch_data(task.params)
            elif action == 'validate':
                result = await self.validate_data(task.params)
            elif action == 'update':
                result = await self.update_local_data(task.params)
            elif action == 'quality_check':
                result = await self.check_quality(task.params)
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
            logger.error(f"DataAgent执行失败: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                data={},
                execution_time=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )
    
    def validate(self, task: AgentTask) -> bool:
        """验证任务参数"""
        required_fields = ['action']
        return all(field in task.params for field in required_fields)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """获取智能体能力"""
        return {
            'name': self.name,
            'actions': ['fetch', 'validate', 'update', 'quality_check'],
            'data_source': self.data_source,
            'supported_formats': ['txt', 'csv', 'json'],
            'quality_metrics': self.quality_metrics
        }
    
    async def fetch_data(self, params: Dict) -> Dict[str, Any]:
        """从数据源获取数据"""
        try:
            from src.core.data import PL5DataCollectorV8
            
            collector = PL5DataCollectorV8()
            
            # 获取最新数据
            latest_data = collector.fetch_latest()
            
            self.last_update = datetime.now()
            self.quality_metrics['total_records'] += len(latest_data) if latest_data else 0
            
            return {
                'action': 'fetch',
                'status': 'success',
                'records': len(latest_data) if latest_data else 0,
                'timestamp': self.last_update.isoformat(),
                'data_preview': latest_data.tail(5).to_dict() if latest_data is not None and len(latest_data) > 0 else None
            }
            
        except Exception as e:
            logger.error(f"数据获取失败: {e}")
            return {
                'action': 'fetch',
                'status': 'error',
                'error': str(e)
            }
    
    async def validate_data(self, params: Dict) -> Dict[str, Any]:
        """验证数据质量"""
        try:
            from src.core.data import DataValidator, ValidationLevel
            
            validator = DataValidator(ValidationLevel.STANDARD)
            
            # 获取需要验证的数据
            data = params.get('data')
            if data is None:
                return {
                    'action': 'validate',
                    'status': 'error',
                    'error': 'No data provided'
                }
                
            result = validator.validate_dataset(data)
            
            self.quality_metrics['valid_records'] += result.summary.get('valid_records', 0)
            self.quality_metrics['error_records'] += len(result.issues)
            self.quality_metrics['last_quality_check'] = datetime.now().isoformat()
            
            return {
                'action': 'validate',
                'status': 'success',
                'is_valid': result.is_valid,
                'issues': result.issues,
                'summary': result.summary
            }
            
        except Exception as e:
            logger.error(f"数据验证失败: {e}")
            return {
                'action': 'validate',
                'status': 'error',
                'error': str(e)
            }
    
    async def update_local_data(self, params: Dict) -> Dict[str, Any]:
        """更新本地数据"""
        try:
            from src.core.data import PL5DataCollectorV8
            
            collector = PL5DataCollectorV8()
            
            # 保存新数据
            new_data = params.get('data')
            if new_data is not None:
                collector.save_data(new_data)
                
            return {
                'action': 'update',
                'status': 'success',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"数据更新失败: {e}")
            return {
                'action': 'update',
                'status': 'error',
                'error': str(e)
            }
    
    async def check_quality(self, params: Dict) -> Dict[str, Any]:
        """检查数据质量"""
        return {
            'action': 'quality_check',
            'status': 'success',
            'metrics': self.quality_metrics
        }
    
    def get_status(self) -> Dict[str, Any]:
        """获取智能体状态"""
        return {
            'name': self.name,
            'is_running': self.is_running,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'metrics': self.metrics,
            'quality_metrics': self.quality_metrics
        }
