"""
混合策略优化框架模块
策略库管理、评估、选择、融合和演化
"""

from .library import (
    PolicyStatus,
    PolicyMetadata,
    PolicyLibrary,
    get_global_library,
)

from .evaluator import (
    MetricType,
    EvaluationResult,
    PolicyRank,
    ParallelEvaluator,
)

from .selector import (
    SelectionStrategy,
    ContextFeatures,
    PolicyMatch,
    ContextFeatureExtractor,
    ContextAwareSelector,
)

from .fusion import (
    FusionStrategy,
    FusionResult,
    PolicyFuser,
)

from .evolution import (
    SelectionMethod,
    MutationMethod,
    CrossoverMethod,
    Individual,
    EvolutionResult,
    GeneticAlgorithm,
)

__all__ = [
    # library
    "PolicyStatus",
    "PolicyMetadata",
    "PolicyLibrary",
    "get_global_library",
    # evaluator
    "MetricType",
    "EvaluationResult",
    "PolicyRank",
    "ParallelEvaluator",
    # selector
    "SelectionStrategy",
    "ContextFeatures",
    "PolicyMatch",
    "ContextFeatureExtractor",
    "ContextAwareSelector",
    # fusion
    "FusionStrategy",
    "FusionResult",
    "PolicyFuser",
    # evolution
    "SelectionMethod",
    "MutationMethod",
    "CrossoverMethod",
    "Individual",
    "EvolutionResult",
    "GeneticAlgorithm",
]
