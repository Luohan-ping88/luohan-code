"""
模型模块 V10.0 - 6模型融合架构
优化项：
1. 并行模型训练
2. 多级缓存集成
3. 预测结果缓存
4. Mamba选择性状态空间模型
5. iTransformer变量维度注意力
6. 贝叶斯不确定性量化
"""

from .predictor_v9 import (
    PL5PredictorV9,
    HMMModel,
    CopulaModel,
    BSTSModel,
    ExtremeValueModel,
    StackingEnsemble,
    MODEL_WEIGHTS,
)

PL5Predictor = PL5PredictorV9

__all__ = [
    "PL5PredictorV9",
    "PL5Predictor",
    "HMMModel",
    "CopulaModel",
    "BSTSModel",
    "ExtremeValueModel",
    "StackingEnsemble",
    "MODEL_WEIGHTS",
]
