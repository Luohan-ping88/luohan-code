"""增量学习模块

实现增量学习和分层训练策略，提高模型训练效率和预测准确性。
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from sklearn.base import BaseEstimator, ClassifierMixin

from src.core.utils.logger import logger


class IncrementalLearningManager:
    """增量学习管理器"""
    
    def __init__(self, 
                 min_update_interval: int = 24,  # 最小更新间隔（小时）
                 batch_size: int = 100,  # 批量大小
                 max_memory_size: int = 1000  # 最大内存大小
                 ):
        """初始化增量学习管理器
        
        Args:
            min_update_interval: 最小更新间隔（小时）
            batch_size: 批量大小
            max_memory_size: 最大内存大小
        """
        self.min_update_interval = min_update_interval
        self.batch_size = batch_size
        self.max_memory_size = max_memory_size
        self.last_update_time = None
        self.memory = {}
        
    def should_update(self) -> bool:
        """判断是否应该更新模型
        
        Returns:
            bool: 是否应该更新模型
        """
        if self.last_update_time is None:
            return True
        
        current_time = datetime.now()
        time_diff = (current_time - self.last_update_time).total_seconds() / 3600
        return time_diff >= self.min_update_interval
    
    def add_data(self, position: str, data: np.ndarray, target: np.ndarray):
        """添加新数据到内存
        
        Args:
            position: 位置
            data: 特征数据
            target: 目标数据
        """
        if position not in self.memory:
            self.memory[position] = {
                'data': [],
                'target': []
            }
        
        self.memory[position]['data'].append(data)
        self.memory[position]['target'].append(target)
        
        # 限制内存大小
        if len(self.memory[position]['data']) > self.max_memory_size:
            self.memory[position]['data'] = self.memory[position]['data'][-self.max_memory_size:]
            self.memory[position]['target'] = self.memory[position]['target'][-self.max_memory_size:]
    
    def get_batch(self, position: str) -> Optional[tuple]:
        """获取批量数据
        
        Args:
            position: 位置
            
        Returns:
            tuple: (data, target) 或 None
        """
        if position not in self.memory:
            return None
        
        data = self.memory[position]['data']
        target = self.memory[position]['target']
        
        if len(data) < self.batch_size:
            return None
        
        # 获取最近的批次
        batch_data = np.vstack(data[-self.batch_size:])
        batch_target = np.hstack(target[-self.batch_size:])
        
        return batch_data, batch_target
    
    def update_timestamp(self):
        """更新时间戳"""
        self.last_update_time = datetime.now()
    
    def clear_memory(self, position: Optional[str] = None):
        """清空内存
        
        Args:
            position: 位置，如果为None则清空所有内存
        """
        if position is None:
            self.memory = {}
        elif position in self.memory:
            self.memory[position] = {
                'data': [],
                'target': []
            }


class HierarchicalTrainingManager:
    """分层训练管理器"""
    
    def __init__(self, 
                 quick_train_hours: float = 0.5,  # 快速训练时间（小时）
                 medium_train_hours: float = 2.0,  # 中等训练时间（小时）
                 deep_train_hours: float = 5.0,  # 深度训练时间（小时）
                 deep_train_frequency: int = 7  # 深度训练频率（天）
                 ):
        """初始化分层训练管理器
        
        Args:
            quick_train_hours: 快速训练时间（小时）
            medium_train_hours: 中等训练时间（小时）
            deep_train_hours: 深度训练时间（小时）
            deep_train_frequency: 深度训练频率（天）
        """
        self.quick_train_hours = quick_train_hours
        self.medium_train_hours = medium_train_hours
        self.deep_train_hours = deep_train_hours
        self.deep_train_frequency = deep_train_frequency
        self.last_deep_train_time = None
        
    def get_training_strategy(self) -> str:
        """获取训练策略
        
        Returns:
            str: 训练策略 ("quick", "medium", "deep")
        """
        if self.last_deep_train_time is None:
            return "deep"
        
        current_time = datetime.now()
        days_since_deep = (current_time - self.last_deep_train_time).days
        
        if days_since_deep >= self.deep_train_frequency:
            return "deep"
        elif days_since_deep >= self.deep_train_frequency // 2:
            return "medium"
        else:
            return "quick"
    
    def get_training_parameters(self, strategy: str) -> Dict[str, Any]:
        """获取训练参数
        
        Args:
            strategy: 训练策略
            
        Returns:
            Dict: 训练参数
        """
        if strategy == "deep":
            return {
                "epochs": 100,
                "batch_size": 32,
                "learning_rate": 0.001,
                "n_layers": 4,
                "d_model": 64,
                "train_time": self.deep_train_hours
            }
        elif strategy == "medium":
            return {
                "epochs": 50,
                "batch_size": 64,
                "learning_rate": 0.005,
                "n_layers": 3,
                "d_model": 48,
                "train_time": self.medium_train_hours
            }
        else:  # quick
            return {
                "epochs": 20,
                "batch_size": 128,
                "learning_rate": 0.01,
                "n_layers": 2,
                "d_model": 32,
                "train_time": self.quick_train_hours
            }
    
    def update_deep_train_timestamp(self):
        """更新深度训练时间戳"""
        self.last_deep_train_time = datetime.now()
    
    def estimate_training_time(self, strategy: str) -> float:
        """估计训练时间
        
        Args:
            strategy: 训练策略
            
        Returns:
            float: 估计训练时间（小时）
        """
        params = self.get_training_parameters(strategy)
        return params["train_time"]


class IncrementalModelWrapper(BaseEstimator, ClassifierMixin):
    """增量模型包装器"""
    
    def __init__(self, base_model: BaseEstimator, 
                 learning_rate: float = 0.1, 
                 update_threshold: float = 0.01):
        """初始化增量模型包装器
        
        Args:
            base_model: 基础模型
            learning_rate: 学习率
            update_threshold: 更新阈值
        """
        self.base_model = base_model
        self.learning_rate = learning_rate
        self.update_threshold = update_threshold
        self.is_fitted = False
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> "IncrementalModelWrapper":
        """拟合模型
        
        Args:
            X: 特征数据
            y: 目标数据
            
        Returns:
            IncrementalModelWrapper: 自身
        """
        self.base_model.fit(X, y)
        self.is_fitted = True
        return self
    
    def partial_fit(self, X: np.ndarray, y: np.ndarray) -> "IncrementalModelWrapper":
        """部分拟合模型
        
        Args:
            X: 特征数据
            y: 目标数据
            
        Returns:
            IncrementalModelWrapper: 自身
        """
        if not self.is_fitted:
            return self.fit(X, y)
        
        # 对于支持partial_fit的模型
        if hasattr(self.base_model, 'partial_fit'):
            self.base_model.partial_fit(X, y)
        else:
            # 对于不支持partial_fit的模型，使用增量学习策略
            # 这里可以实现更复杂的增量学习逻辑
            pass
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测
        
        Args:
            X: 特征数据
            
        Returns:
            np.ndarray: 预测结果
        """
        return self.base_model.predict(X)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """预测概率
        
        Args:
            X: 特征数据
            
        Returns:
            np.ndarray: 预测概率
        """
        return self.base_model.predict_proba(X)


# 全局增量学习管理器实例
incremental_learning_manager = IncrementalLearningManager()
hierarchical_training_manager = HierarchicalTrainingManager()


def get_incremental_learning_manager() -> IncrementalLearningManager:
    """获取增量学习管理器实例
    
    Returns:
        IncrementalLearningManager: 增量学习管理器实例
    """
    return incremental_learning_manager


def get_hierarchical_training_manager() -> HierarchicalTrainingManager:
    """获取分层训练管理器实例
    
    Returns:
        HierarchicalTrainingManager: 分层训练管理器实例
    """
    return hierarchical_training_manager


def should_perform_incremental_update() -> bool:
    """判断是否应该执行增量更新
    
    Returns:
        bool: 是否应该执行增量更新
    """
    return incremental_learning_manager.should_update()


def get_training_strategy() -> str:
    """获取当前训练策略
    
    Returns:
        str: 训练策略
    """
    return hierarchical_training_manager.get_training_strategy()


def get_training_parameters() -> Dict[str, Any]:
    """获取当前训练参数
    
    Returns:
        Dict: 训练参数
    """
    strategy = get_training_strategy()
    return hierarchical_training_manager.get_training_parameters(strategy)


def update_training_timestamp(strategy: str):
    """更新训练时间戳
    
    Args:
        strategy: 训练策略
    """
    if strategy == "deep":
        hierarchical_training_manager.update_deep_train_timestamp()
    incremental_learning_manager.update_timestamp()
