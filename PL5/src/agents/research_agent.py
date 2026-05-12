"""
研究智能体 - 负责数据分析、策略研究和性能分析
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import numpy as np

from .base_agent import BaseAgent, AgentTask, AgentResult

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """
    研究智能体
    
    职责:
    - 分析历史数据规律
    - 研究号码分布特征
    - 分析模型性能
    - 生成研究报告
    """
    
    def __init__(self, max_workers: int = 4):
        super().__init__(name="ResearchAgent", max_workers=max_workers)
        self.analysis_cache: Dict[str, Any] = {}
        self.research_topics = [
            'frequency_analysis',
            'pattern_detection',
            'correlation_analysis',
            'trend_analysis',
            'model_performance'
        ]
        
    async def execute(self, task: AgentTask) -> AgentResult:
        """执行研究任务"""
        start_time = datetime.now()
        
        try:
            action = task.params.get('action', 'analyze')
            
            if action == 'analyze':
                result = await self.analyze_data(task.params)
            elif action == 'pattern':
                result = await self.detect_patterns(task.params)
            elif action == 'correlation':
                result = await self.analyze_correlation(task.params)
            elif action == 'trend':
                result = await self.analyze_trends(task.params)
            elif action == 'report':
                result = await self.generate_report(task.params)
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
            logger.error(f"ResearchAgent执行失败: {e}")
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
            'actions': ['analyze', 'pattern', 'correlation', 'trend', 'report'],
            'research_topics': self.research_topics,
            'analysis_cache_size': len(self.analysis_cache)
        }
    
    async def analyze_data(self, params: Dict) -> Dict[str, Any]:
        """分析数据"""
        try:
            from src.core.data import PL5DataCollectorV8
            
            collector = PL5DataCollectorV8()
            data = collector.load_processed_data()
            
            if data is None or len(data) < 100:
                return {
                    'action': 'analyze',
                    'status': 'error',
                    'error': 'Insufficient data'
                }
            
            analysis_results = {}
            
            # 1. 基础统计
            for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
                if col in data.columns:
                    values = data[col].values
                    analysis_results[col] = {
                        'mean': float(np.mean(values)),
                        'std': float(np.std(values)),
                        'min': int(np.min(values)),
                        'max': int(np.max(values)),
                        'median': float(np.median(values))
                    }
            
            # 2. 频率分布
            for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
                if col in data.columns:
                    values = data[col].values
                    freq = {}
                    for digit in range(10):
                        freq[digit] = int(np.sum(values == digit))
                    analysis_results[f'{col}_frequency'] = freq
                    
            # 3. 奇偶分布
            odd_ratio = {}
            for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
                if col in data.columns:
                    values = data[col].values
                    odd_count = np.sum(values % 2 == 1)
                    odd_ratio[col] = float(odd_count / len(values))
            analysis_results['odd_ratio'] = odd_ratio
            
            # 4. 大小分布
            large_ratio = {}
            for col in ['wan', 'qian', 'bai', 'shi', 'ge']:
                if col in data.columns:
                    values = data[col].values
                    large_count = np.sum(values >= 5)
                    large_ratio[col] = float(large_count / len(values))
            analysis_results['large_ratio'] = large_ratio
            
            self.analysis_cache['latest_analysis'] = analysis_results
            
            return {
                'action': 'analyze',
                'status': 'success',
                'data_points': len(data),
                'results': analysis_results
            }
            
        except Exception as e:
            logger.error(f"数据分析失败: {e}")
            return {
                'action': 'analyze',
                'status': 'error',
                'error': str(e)
            }
    
    async def detect_patterns(self, params: Dict) -> Dict[str, Any]:
        """检测号码模式"""
        try:
            from src.core.data import PL5DataCollectorV8
            from src.core.features import HotColdAnalyzer, NumberPatternAnalyzer
            
            collector = PL5DataCollectorV8()
            data = collector.load_processed_data()
            
            if data is None or len(data) < 50:
                return {
                    'action': 'pattern',
                    'status': 'error',
                    'error': 'Insufficient data'
                }
            
            positions = ['wan', 'qian', 'bai', 'shi', 'ge']
            
            # 冷热分析
            hot_cold = HotColdAnalyzer()
            freq_dict = hot_cold.analyze_frequency(data, positions, 50)
            
            # 形态分析
            pattern_analyzer = NumberPatternAnalyzer()
            morphology = pattern_analyzer.compute_morphology_features(data, positions)
            
            # 检测到的模式
            patterns = {}
            
            # 热号模式
            for pos in positions:
                hot_ids = hot_cold.identify_hot_cold(freq_dict[pos])['hot']
                if len(hot_ids) > 0:
                    patterns[f'{pos}_hot_numbers'] = list(hot_ids)
                    
            # 连号模式
            consecutive_count = 0
            for i in range(len(positions) - 1):
                col = f'consecutive_{positions[i]}_{positions[i+1]}'
                if col in morphology.columns:
                    consecutive_count += int(morphology[col].sum())
            patterns['consecutive_count'] = consecutive_count
            
            # 重号模式
            repeat_count = 0
            if 'total_repeat' in morphology.columns:
                repeat_count = int(morphology['total_repeat'].sum())
            patterns['repeat_count'] = repeat_count
            
            return {
                'action': 'pattern',
                'status': 'success',
                'patterns': patterns,
                'data_range': f'{len(data)} records'
            }
            
        except Exception as e:
            logger.error(f"模式检测失败: {e}")
            return {
                'action': 'pattern',
                'status': 'error',
                'error': str(e)
            }
    
    async def analyze_correlation(self, params: Dict) -> Dict[str, Any]:
        """分析位置间相关性"""
        try:
            from src.core.data import PL5DataCollectorV8
            
            collector = PL5DataCollectorV8()
            data = collector.load_processed_data()
            
            if data is None or len(data) < 100:
                return {
                    'action': 'correlation',
                    'status': 'error',
                    'error': 'Insufficient data'
                }
            
            positions = ['wan', 'qian', 'bai', 'shi', 'ge']
            
            # 计算位置间相关系数
            correlations = {}
            for i, pos1 in enumerate(positions):
                for j, pos2 in enumerate(positions):
                    if i >= j:
                        continue
                        
                    corr = np.corrcoef(data[pos1].values, data[pos2].values)[0, 1]
                    correlations[f'{pos1}_{pos2}'] = float(corr) if not np.isnan(corr) else 0.0
                    
            # 计算同期冷热一致性
            from src.core.features import HotColdAnalyzer
            hot_cold = HotColdAnalyzer()
            hot_features = hot_cold.compute_position_correlation(data, positions)
            
            return {
                'action': 'correlation',
                'status': 'success',
                'correlations': correlations,
                'hot_cold_consistency': {
                    'avg_hot_count': float(hot_features['all_pos_hot_count'].mean()),
                    'avg_cold_count': float(hot_features['all_pos_cold_count'].mean())
                }
            }
            
        except Exception as e:
            logger.error(f"相关性分析失败: {e}")
            return {
                'action': 'correlation',
                'status': 'error',
                'error': str(e)
            }
    
    async def analyze_trends(self, params: Dict) -> Dict[str, Any]:
        """分析趋势"""
        try:
            from src.core.data import PL5DataCollectorV8
            
            collector = PL5DataCollectorV8()
            data = collector.load_processed_data()
            
            if data is None or len(data) < 100:
                return {
                    'action': 'trend',
                    'status': 'error',
                    'error': 'Insufficient data'
                }
            
            positions = ['wan', 'qian', 'bai', 'shi', 'ge']
            windows = [10, 20, 50]
            
            trends = {}
            for pos in positions:
                trends[pos] = {}
                values = data[pos].values
                
                for window in windows:
                    if len(values) >= window:
                        recent = values[-window:]
                        older = values[-2*window:-window] if len(values) >= 2*window else values[:-window]
                        
                        recent_mean = np.mean(recent)
                        older_mean = np.mean(older)
                        
                        # 趋势：上升/下降/平稳
                        change = recent_mean - older_mean
                        if change > 0.5:
                            trend = 'up'
                        elif change < -0.5:
                            trend = 'down'
                        else:
                            trend = 'stable'
                            
                        trends[pos][f'w{window}'] = {
                            'trend': trend,
                            'change': float(change),
                            'recent_mean': float(recent_mean),
                            'older_mean': float(older_mean)
                        }
                        
            return {
                'action': 'trend',
                'status': 'success',
                'trends': trends
            }
            
        except Exception as e:
            logger.error(f"趋势分析失败: {e}")
            return {
                'action': 'trend',
                'status': 'error',
                'error': str(e)
            }
    
    async def generate_report(self, params: Dict) -> Dict[str, Any]:
        """生成研究报告"""
        try:
            report_type = params.get('report_type', 'comprehensive')
            
            # 执行各项分析
            analysis = await self.analyze_data({})
            patterns = await self.detect_patterns({})
            correlations = await self.analyze_correlation({})
            trends = await self.analyze_trends({})
            
            report = {
                'title': f'排列五数据分析报告 - {datetime.now().strftime("%Y-%m-%d")}',
                'type': report_type,
                'timestamp': datetime.now().isoformat(),
                'analysis_results': analysis.get('results', {}),
                'patterns': patterns.get('patterns', {}),
                'correlations': correlations.get('correlations', {}),
                'trends': trends.get('trends', {}),
                'summary': self._generate_summary(analysis, patterns, trends)
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
    
    def _generate_summary(self, analysis: Dict, patterns: Dict, trends: Dict) -> str:
        """生成分析摘要"""
        summary_parts = []
        
        # 频率摘要
        if 'wan_frequency' in analysis.get('results', {}):
            wan_freq = analysis['results']['wan_frequency']
            hot_digit = max(wan_freq.items(), key=lambda x: x[1])
            summary_parts.append(f"万位最热号码: {hot_digit[0]} (出现{hot_digit[1]}次)")
            
        # 趋势摘要
        if trends.get('trends'):
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                if pos in trends['trends'] and 'w50' in trends['trends'][pos]:
                    trend_info = trends['trends'][pos]['w50']
                    summary_parts.append(f"{pos}位趋势: {trend_info['trend']}")
                    
        return "; ".join(summary_parts)
    
    def get_status(self) -> Dict[str, Any]:
        """获取智能体状态"""
        return {
            'name': self.name,
            'is_running': self.is_running,
            'cache_size': len(self.analysis_cache),
            'metrics': self.metrics
        }
