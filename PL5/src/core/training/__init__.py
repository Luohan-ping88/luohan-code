"""
训练模块 - V11
包含深度训练、增量训练和预测链路聚合功能。
"""
from src.core.training.deep_training_manager import (
    DeepTrainingManager,
    StrategyCombination
)
from src.core.training.incremental_training_manager import (
    IncrementalTrainingManager,
    StrategyDefect,
    AdjustmentProposal
)
from src.core.training.prediction_aggregator import (
    PredictionAggregator,
    PredictionEvidence,
    AggregatedPrediction
)
from src.core.training.daily_cycle_orchestrator import (
    DailyCycleOrchestrator,
    DailyCyclePhase,
    DailyCycleStatus
)

__all__ = [
    'DeepTrainingManager',
    'StrategyCombination',
    'IncrementalTrainingManager',
    'StrategyDefect',
    'AdjustmentProposal',
    'PredictionAggregator',
    'PredictionEvidence',
    'AggregatedPrediction',
    'DailyCycleOrchestrator',
    'DailyCyclePhase',
    'DailyCycleStatus'
]
