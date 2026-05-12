"""
HMM参数优化模块
针对排列五0-9数字特征优化的HMM模型参数配置
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class HMMOptimizer:
    """
    HMM模型参数优化器
    
    针对排列五数据特点（5个位置，每个位置0-9共10个状态），
    自动优化HMM模型的参数配置。
    """
    
    # 排列五数据特点
    POSITION_COUNT = 5
    DIGIT_RANGE = 10  # 0-9
    SEQUENCE_LENGTH = 1000  # 建议最小序列长度
    
    # 优化后的参数范围
    OPTIMAL_PARAMS = {
        'n_states': {
            'min': 3,
            'max': 6,
            'default': 4,
            'recommended': 4,  # 对于10个数字，4个状态足够
        },
        'alpha': {  # Laplace平滑参数
            'min': 0.1,
            'max': 2.0,
            'default': 1.0,
            'recommended': 0.5,  # 稍微降低平滑，保留更多转移信息
        },
        'min_frequency': {
            'min': 50,
            'max': 200,
            'default': 100,
            'recommended': 50,  # 对于排列五，建议使用较短窗口
        }
    }
    
    def __init__(self):
        self.current_params = self.OPTIMAL_PARAMS.copy()
        self.performance_history: List[Dict] = []
        
    def analyze_data_characteristics(self, data: np.ndarray) -> Dict:
        """
        分析数据特点，返回建议的参数配置
        
        Args:
            data: 历史数据 shape=(n_samples, 5)
            
        Returns:
            参数建议字典
        """
        n_samples = len(data)
        
        # 分析1: 数据量评估
        if n_samples < self.SEQUENCE_LENGTH:
            logger.warning(f"数据量较少({n_samples})，建议使用更多平滑")
            self.current_params['alpha']['recommended'] = 1.0
        else:
            self.current_params['alpha']['recommended'] = 0.5
            
        # 分析2: 数字分布均匀性
        digit_counts = np.zeros(10)
        for pos in range(min(5, data.shape[1])):
            for val in data[:, pos]:
                if 0 <= val <= 9:
                    digit_counts[int(val)] += 1
                    
        digit_freq = digit_counts / digit_counts.sum()
        freq_std = digit_freq.std()
        
        # 分布越均匀，状态数可以越少
        if freq_std < 0.02:
            logger.info("数字分布非常均匀，建议增加状态数以捕获细微差异")
            self.current_params['n_states']['recommended'] = 5
        elif freq_std > 0.05:
            logger.info("数字分布有明显偏态，建议使用较少状态")
            self.current_params['n_states']['recommended'] = 3
            
        # 分析3: 序列转移模式
        transition_counts = self._analyze_transitions(data)
        
        return {
            'n_samples': n_samples,
            'digit_frequency_std': freq_std,
            'transition_sparsity': self._calculate_sparsity(transition_counts),
            'recommended_params': {
                k: v['recommended'] 
                for k, v in self.current_params.items()
            }
        }
    
    def _analyze_transitions(self, data: np.ndarray) -> Dict:
        """分析数字转移模式"""
        transitions = {}
        
        for pos in range(min(5, data.shape[1])):
            # 统计前后转移
            for i in range(len(data) - 1):
                curr = int(data[i, pos])
                next_val = int(data[i + 1, pos])
                
                key = (curr, next_val)
                transitions[key] = transitions.get(key, 0) + 1
                
        return transitions
    
    def _calculate_sparsity(self, transitions: Dict) -> float:
        """计算转移矩阵的稀疏度"""
        total_possible = 10 * 10  # 10x10
        observed = len(transitions)
        # 稀疏度 = 未出现的转移数 / 总转移数
        return 1.0 - (observed / total_possible)
    
    def get_optimal_params(self, data: Optional[np.ndarray] = None) -> Dict:
        """
        获取最优参数配置
        
        Args:
            data: 可选的历史数据
            
        Returns:
            最优参数字典
        """
        if data is not None:
            analysis = self.analyze_data_characteristics(data)
            logger.info(f"数据特点分析: {analysis}")
            
        return {
            'n_states': self.current_params['n_states']['recommended'],
            'alpha': self.current_params['alpha']['recommended'],
            'min_frequency': self.current_params['min_frequency']['recommended'],
        }
    
    def update_params(self, performance: float, direction: str = 'increase'):
        """
        根据性能反馈更新参数
        
        Args:
            performance: 预测准确率
            direction: 调整方向 ('increase' 或 'decrease')
        """
        self.performance_history.append({
            'performance': performance,
            'params': self.get_optimal_params(),
        })
        
        # 简单反馈调整
        alpha = self.current_params['alpha']['recommended']
        
        if direction == 'increase':
            # 性能提升，降低平滑
            alpha = max(
                self.OPTIMAL_PARAMS['alpha']['min'],
                alpha * 0.9
            )
        else:
            # 性能下降，增加平滑
            alpha = min(
                self.OPTIMAL_PARAMS['alpha']['max'],
                alpha * 1.1
            )
            
        self.current_params['alpha']['recommended'] = round(alpha, 2)
        logger.info(f"参数更新: alpha={alpha}")


class HMMBootstrap:
    """
    HMM模型自举集成
    
    使用多个不同参数的HMM模型进行集成预测，
    提高预测稳定性。
    """
    
    def __init__(self, n_models: int = 3):
        self.n_models = n_models
        self.models = []
        self.weights = []
        
    def create_ensemble(self, base_data: np.ndarray) -> List[Dict]:
        """
        创建HMM集成模型
        
        Args:
            base_data: 基础训练数据
            
        Returns:
            模型参数列表
        """
        optimizer = HMMOptimizer()
        optimal = optimizer.get_optimal_params(base_data)
        
        # 创建不同参数的模型
        param_sets = [
            {
                'n_states': optimal['n_states'],
                'alpha': optimal['alpha'] * 0.5,  # 低平滑
            },
            {
                'n_states': optimal['n_states'],
                'alpha': optimal['alpha'],  # 中等平滑
            },
            {
                'n_states': optimal['n_states'],
                'alpha': optimal['alpha'] * 2.0,  # 高平滑
            },
        ]
        
        self.models = param_sets
        # 权重：中等平滑权重最高
        self.weights = [0.3, 0.4, 0.3]
        
        return param_sets
    
    def predict_ensemble(self, predictions: List[np.ndarray]) -> np.ndarray:
        """
        集成预测
        
        Args:
            predictions: 各模型预测结果列表
            
        Returns:
            加权平均预测
        """
        if len(predictions) != len(self.weights):
            raise ValueError("预测数量与权重数量不匹配")
            
        result = np.zeros(10)
        for pred, weight in zip(predictions, self.weights):
            result += pred * weight
            
        return result


# 全局实例
_hmm_optimizer: Optional[HMMOptimizer] = None


def get_hmm_optimizer() -> HMMOptimizer:
    """获取HMM优化器全局实例"""
    global _hmm_optimizer
    if _hmm_optimizer is None:
        _hmm_optimizer = HMMOptimizer()
    return _hmm_optimizer
