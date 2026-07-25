"""
自学习增强模块包 V1.0

整合模式识别、周期变化检测、数据分布漂移检测、自适应学习率管理、
策略自适应选择五大能力，为 SelfLearningSystem 提供持续进化的智能化基础。

子模块:
- pattern_recognizer: 高级模式识别（频率/连号/重复/位置关联/趋势/异常）
- cycle_detector: 周期变化检测（FFT/CUSUM/PELT/自相关）
- drift_detector: 数据分布漂移检测（PSI/KS/ADWIN）
- adaptive_lr_manager: 自适应学习率管理（性能反馈驱动）
- strategy_adaptive_selector: 策略自适应选择（动态切换/组合优化）
"""

from .pattern_recognizer import (
    PatternType,
    NumberCategory,
    TrendDirection,
    AnomalyLevel,
    FrequencyPattern,
    ConsecutivePattern,
    RepeatPattern,
    PositionCorrelation,
    TrendPattern,
    AnomalyPattern,
    PatternAnalysisResult,
    PatternRecognizer,
    get_pattern_recognizer,
    DEFAULT_POSITIONS as PATTERN_DEFAULT_POSITIONS,
    POSITION_LABELS,
)

from .cycle_detector import (
    CycleChangeType,
    ChangePointType,
    DetectionMethod,
    CycleInfo,
    CycleResult,
    ChangePoint,
    CycleChangeResult,
    FFTAnalyzer,
    AutocorrelationAnalyzer,
    CUSUMDetector,
    PELTDetector,
    CycleDetector,
    get_cycle_detector,
)

from .drift_detector import (
    DriftLevel,
    DriftType,
    DriftResult,
    DriftSummary,
    PSICalculator,
    KSTestDetector,
    ADWINDetector,
    DataDriftDetector,
    get_drift_detector,
)

from .adaptive_lr_manager import (
    TrainingPhase,
    AdjustmentAction,
    MetricRecord,
    CurveAnalysis,
    LRHistoryRecord,
    AdaptiveLRConfig,
    PositionState,
    AdaptiveLRManager,
    get_adaptive_lr_manager,
)

from .strategy_adaptive_selector import (
    SelectionMode,
    SwitchTrigger,
    StrategyPerformanceRecord,
    StrategyStats,
    SelectorConfig,
    StrategyAdaptiveSelector,
    get_strategy_selector,
    PRESET_STRATEGIES,
    POSITION_NAMES,
)

__all__ = [
    # 模式识别
    'PatternType',
    'NumberCategory',
    'TrendDirection',
    'AnomalyLevel',
    'FrequencyPattern',
    'ConsecutivePattern',
    'RepeatPattern',
    'PositionCorrelation',
    'TrendPattern',
    'AnomalyPattern',
    'PatternAnalysisResult',
    'PatternRecognizer',
    'get_pattern_recognizer',
    'PATTERN_DEFAULT_POSITIONS',
    'POSITION_LABELS',
    # 周期检测
    'CycleChangeType',
    'ChangePointType',
    'DetectionMethod',
    'CycleInfo',
    'CycleResult',
    'ChangePoint',
    'CycleChangeResult',
    'FFTAnalyzer',
    'AutocorrelationAnalyzer',
    'CUSUMDetector',
    'PELTDetector',
    'CycleDetector',
    'get_cycle_detector',
    # 漂移检测
    'DriftLevel',
    'DriftType',
    'DriftResult',
    'DriftSummary',
    'PSICalculator',
    'KSTestDetector',
    'ADWINDetector',
    'DataDriftDetector',
    'get_drift_detector',
    # 自适应学习率
    'TrainingPhase',
    'AdjustmentAction',
    'MetricRecord',
    'CurveAnalysis',
    'LRHistoryRecord',
    'AdaptiveLRConfig',
    'PositionState',
    'AdaptiveLRManager',
    'get_adaptive_lr_manager',
    # 策略自适应选择
    'SelectionMode',
    'SwitchTrigger',
    'StrategyPerformanceRecord',
    'StrategyStats',
    'SelectorConfig',
    'StrategyAdaptiveSelector',
    'get_strategy_selector',
    'PRESET_STRATEGIES',
    'POSITION_NAMES',
]
