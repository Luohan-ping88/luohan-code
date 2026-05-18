"""增量学习模块 V2.0

实现增量学习和分层训练策略，提高模型训练效率和预测准确性。
增强功能：
1. 智能数据采样
2. 自适应训练策略
3. 性能监控
4. 早停机制
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from collections import deque
from sklearn.base import BaseEstimator, ClassifierMixin

from src.core.utils.logger import logger


class TrainingStrategy(Enum):
    """训练策略"""
    QUICK = "quick"       # 快速训练
    MEDIUM = "medium"     # 中等训练
    DEEP = "deep"         # 深度训练


@dataclass
class LearningMetrics:
    """学习指标"""
    timestamp: datetime
    accuracy: float
    loss: float
    samples_seen: int
    validation_score: Optional[float] = None


@dataclass
class AdaptiveConfig:
    """自适应配置"""
    min_update_interval_hours: float = 24.0
    performance_threshold: float = 0.85
    degradation_threshold: float = 0.05
    max_consecutive_failures: int = 3
    batch_size: int = 100
    max_memory_size: int = 1000
    use_sampling: bool = True
    sampling_ratio: float = 0.3


class EnhancedIncrementalLearningManager:
    """增强的增量学习管理器"""

    def __init__(self, config: Optional[AdaptiveConfig] = None):
        self.config = config or AdaptiveConfig()
        self.last_update_time: Optional[datetime] = None
        self.memory: Dict[str, Dict] = {}
        self.metrics_history: List[LearningMetrics] = []
        self.consecutive_failures = 0
        self.current_strategy = TrainingStrategy.QUICK
        self._init_memory()

    def _init_memory(self):
        """初始化内存"""
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        for pos in positions:
            self.memory[pos] = {
                'data': [],
                'target': [],
                'timestamps': []
            }

    def should_update(self) -> bool:
        """判断是否应该更新模型"""
        if self.last_update_time is None:
            return True

        current_time = datetime.now()
        time_diff = (current_time - self.last_update_time).total_seconds() / 3600

        # 检查性能是否下降
        if self._is_performance_degraded():
            logger.info("检测到性能下降，触发更新")
            return True

        return time_diff >= self.config.min_update_interval_hours

    def _is_performance_degraded(self) -> bool:
        """检查性能是否下降"""
        if len(self.metrics_history) < 10:
            return False

        recent_metrics = self.metrics_history[-10:]
        if not recent_metrics:
            return False

        avg_recent = np.mean([m.accuracy for m in recent_metrics])

        if len(self.metrics_history) >= 20:
            older_metrics = self.metrics_history[-20:-10]
            if older_metrics:
                avg_older = np.mean([m.accuracy for m in older_metrics])
                degradation = avg_older - avg_recent

                if degradation > self.config.degradation_threshold:
                    logger.warning(f"性能下降检测: {degradation:.4f}")
                    self.consecutive_failures += 1
                    return True

        return False

    def add_data(
        self,
        position: str,
        data: np.ndarray,
        target: np.ndarray,
        timestamp: Optional[datetime] = None
    ):
        """添加新数据到内存"""
        if timestamp is None:
            timestamp = datetime.now()

        if position not in self.memory:
            self._init_memory()
            self.memory[position] = {'data': [], 'target': [], 'timestamps': []}

        # 智能采样
        if self.config.use_sampling and len(data) > self.config.batch_size:
            indices = np.random.choice(
                len(data),
                size=int(len(data) * self.config.sampling_ratio),
                replace=False
            )
            data = data[indices]
            target = target[indices]

        self.memory[position]['data'].append(data)
        self.memory[position]['target'].append(target)
        self.memory[position]['timestamps'].append(timestamp)

        # 限制内存大小
        self._trim_memory(position)

    def _trim_memory(self, position: str):
        """修剪内存，保留最新数据"""
        if len(self.memory[position]['data']) > self.config.max_memory_size:
            # 保留最新的数据
            self.memory[position]['data'] = self.memory[position]['data'][-self.config.max_memory_size:]
            self.memory[position]['target'] = self.memory[position]['target'][-self.config.max_memory_size:]
            self.memory[position]['timestamps'] = self.memory[position]['timestamps'][-self.config.max_memory_size:]

    def get_batch(self, position: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """获取批量数据"""
        if position not in self.memory:
            return None

        data = self.memory[position]['data']
        target = self.memory[position]['target']

        if len(data) < self.config.batch_size:
            return None

        # 获取最近的批次
        batch_data = np.vstack(data[-self.config.batch_size:])
        batch_target = np.hstack(target[-self.config.batch_size:])

        return batch_data, batch_target

    def record_metrics(self, accuracy: float, loss: float, validation_score: Optional[float] = None):
        """记录学习指标"""
        metrics = LearningMetrics(
            timestamp=datetime.now(),
            accuracy=accuracy,
            loss=loss,
            samples_seen=sum(len(d) for d in self.memory.values()),
            validation_score=validation_score
        )

        self.metrics_history.append(metrics)

        # 只保留最近100条记录
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]

    def get_performance_trend(self) -> Dict[str, Any]:
        """获取性能趋势"""
        if not self.metrics_history:
            return {'trend': 'unknown', 'change': 0.0}

        recent = self.metrics_history[-5:]
        older = self.metrics_history[-10:-5] if len(self.metrics_history) >= 10 else recent

        avg_recent = np.mean([m.accuracy for m in recent])
        avg_older = np.mean([m.accuracy for m in older])

        change = avg_recent - avg_older

        if change > 0.02:
            trend = 'improving'
        elif change < -0.02:
            trend = 'degrading'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'change': change,
            'avg_recent': avg_recent,
            'avg_older': avg_older
        }

    def update_timestamp(self):
        """更新时间戳"""
        self.last_update_time = datetime.now()
        self.consecutive_failures = 0

    def clear_memory(self, position: Optional[str] = None):
        """清空内存"""
        if position is None:
            for pos in self.memory:
                self.memory[pos] = {'data': [], 'target': [], 'timestamps': []}
        elif position in self.memory:
            self.memory[position] = {'data': [], 'target': [], 'timestamps': []}

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_samples = sum(len(d) for pos_data in self.memory.values() for d in pos_data['data'])
        return {
            'total_samples': total_samples,
            'positions': {pos: len(self.memory[pos]['data']) for pos in self.memory},
            'metrics_count': len(self.metrics_history),
            'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
            'consecutive_failures': self.consecutive_failures,
            'performance_trend': self.get_performance_trend()
        }


class AdaptiveTrainingStrategyManager:
    """自适应训练策略管理器"""

    def __init__(self):
        self.last_deep_train_time: Optional[datetime] = None
        self.performance_history: deque = deque(maxlen=30)
        self.strategy_thresholds = {
            'deep': 7,   # 天数
            'medium': 3  # 天数
        }

    def get_optimal_strategy(self) -> TrainingStrategy:
        """获取最佳训练策略"""
        if self.last_deep_train_time is None:
            return TrainingStrategy.DEEP

        current_time = datetime.now()
        days_since_deep = (current_time - self.last_deep_train_time).days

        # 分析性能趋势
        if len(self.performance_history) >= 7:
            recent_avg = np.mean(list(self.performance_history)[-7:])
            older_avg = np.mean(list(self.performance_history)[-14:-7]) if len(self.performance_history) >= 14 else recent_avg

            # 如果性能持续下降，触发深度训练
            if recent_avg < older_avg - 0.05:
                logger.info("性能持续下降，触发深度训练")
                return TrainingStrategy.DEEP

        # 基于时间的策略选择
        if days_since_deep >= self.strategy_thresholds['deep']:
            return TrainingStrategy.DEEP
        elif days_since_deep >= self.strategy_thresholds['medium']:
            return TrainingStrategy.MEDIUM
        else:
            return TrainingStrategy.QUICK

    def record_performance(self, accuracy: float):
        """记录性能"""
        self.performance_history.append(accuracy)

    def get_training_parameters(self, strategy: TrainingStrategy) -> Dict[str, Any]:
        """获取训练参数"""
        base_params = {
            TrainingStrategy.DEEP: {
                "epochs": 100,
                "batch_size": 32,
                "learning_rate": 0.001,
                "n_layers": 4,
                "d_model": 64,
                "use_early_stopping": True,
                "patience": 10,
                "validation_split": 0.2
            },
            TrainingStrategy.MEDIUM: {
                "epochs": 50,
                "batch_size": 64,
                "learning_rate": 0.005,
                "n_layers": 3,
                "d_model": 48,
                "use_early_stopping": True,
                "patience": 5,
                "validation_split": 0.15
            },
            TrainingStrategy.QUICK: {
                "epochs": 20,
                "batch_size": 128,
                "learning_rate": 0.01,
                "n_layers": 2,
                "d_model": 32,
                "use_early_stopping": False,
                "patience": 3,
                "validation_split": 0.1
            }
        }

        return base_params.get(strategy, base_params[TrainingStrategy.QUICK])

    def update_deep_train_timestamp(self):
        """更新深度训练时间戳"""
        self.last_deep_train_time = datetime.now()


class IncrementalModelWrapper(BaseEstimator, ClassifierMixin):
    """增量模型包装器 V2.0"""

    def __init__(
        self,
        base_model: BaseEstimator,
        learning_rate: float = 0.1,
        update_threshold: float = 0.01,
        use_warm_start: bool = True
    ):
        self.base_model = base_model
        self.learning_rate = learning_rate
        self.update_threshold = update_threshold
        self.use_warm_start = use_warm_start
        self.is_fitted = False
        self.best_score = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "IncrementalModelWrapper":
        """拟合模型"""
        self.base_model.fit(X, y)
        self.is_fitted = True

        if hasattr(self.base_model, 'score'):
            self.best_score = self.base_model.score(X, y)

        return self

    def partial_fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        classes: Optional[np.ndarray] = None
    ) -> "IncrementalModelWrapper":
        """部分拟合模型"""
        if not self.is_fitted:
            if classes is not None:
                return self.fit(X, y)
            return self

        # 对于支持partial_fit的模型
        if hasattr(self.base_model, 'partial_fit'):
            try:
                if classes is not None:
                    self.base_model.partial_fit(X, y, classes=classes)
                else:
                    self.base_model.partial_fit(X, y)
            except Exception as e:
                logger.warning(f"partial_fit失败: {e}")
                # 回退到全量训练
                self.fit(X, y)
        else:
            # 对于不支持partial_fit的模型，使用增量采样训练
            if len(X) > 1000:
                # 随机采样一部分数据
                indices = np.random.choice(len(X), size=1000, replace=False)
                X_sample = X[indices]
                y_sample = y[indices]
                self.base_model.fit(X_sample, y_sample)
            else:
                self.base_model.fit(X, y)

        # 更新最佳分数
        if hasattr(self.base_model, 'score'):
            current_score = self.base_model.score(X, y)
            self.best_score = max(self.best_score, current_score)

        return self

    def should_update(self) -> bool:
        """判断是否应该更新"""
        if not self.is_fitted:
            return True

        if not hasattr(self.base_model, 'score'):
            return True

        return False

    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测"""
        return self.base_model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """预测概率"""
        if hasattr(self.base_model, 'predict_proba'):
            return self.base_model.predict_proba(X)

        # 如果模型不支持predict_proba，返回均匀分布
        n_classes = len(np.unique(self.base_model.classes_)) if hasattr(self.base_model, 'classes_') else 10
        return np.ones((len(X), n_classes)) / n_classes


# 全局实例
incremental_learning_manager = EnhancedIncrementalLearningManager()
training_strategy_manager = AdaptiveTrainingStrategyManager()


def get_incremental_learning_manager() -> EnhancedIncrementalLearningManager:
    """获取增量学习管理器实例"""
    return incremental_learning_manager


def get_training_strategy_manager() -> AdaptiveTrainingStrategyManager:
    """获取训练策略管理器实例"""
    return training_strategy_manager


def should_perform_incremental_update() -> bool:
    """判断是否应该执行增量更新"""
    return incremental_learning_manager.should_update()


def get_current_training_strategy() -> TrainingStrategy:
    """获取当前训练策略"""
    return training_strategy_manager.get_optimal_strategy()


def get_current_training_parameters() -> Dict[str, Any]:
    """获取当前训练参数"""
    strategy = get_current_training_strategy()
    return training_strategy_manager.get_training_parameters(strategy)


def update_training_timestamp(strategy: TrainingStrategy):
    """更新训练时间戳"""
    if strategy == TrainingStrategy.DEEP:
        training_strategy_manager.update_deep_train_timestamp()
    incremental_learning_manager.update_timestamp()


def record_training_performance(accuracy: float):
    """记录训练性能"""
    incremental_learning_manager.record_metrics(accuracy, 0.0)
    training_strategy_manager.record_performance(accuracy)
