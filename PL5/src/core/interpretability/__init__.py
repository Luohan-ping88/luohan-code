"""
模型可解释性模块包 V1.0

提供模型决策的可解释性分析能力，包括：
- 特征重要性分析（全局/局部/树模型）
- 决策路径追踪（集成模型决策链）
- 跨位置综合分析
- 人类可读的解释报告生成

子模块:
- model_interpreter: 模型解释器主入口
"""

from .model_interpreter import (
    InterpretationLevel,
    ContributionType,
    FeatureContribution,
    DecisionStep,
    PositionInterpretation,
    PredictionInterpretation,
    FeatureImportanceAnalyzer,
    DecisionPathTracer,
    CrossPositionAnalyzer,
    ModelInterpreter,
    get_model_interpreter,
)

__all__ = [
    'InterpretationLevel',
    'ContributionType',
    'FeatureContribution',
    'DecisionStep',
    'PositionInterpretation',
    'PredictionInterpretation',
    'FeatureImportanceAnalyzer',
    'DecisionPathTracer',
    'CrossPositionAnalyzer',
    'ModelInterpreter',
    'get_model_interpreter',
]
