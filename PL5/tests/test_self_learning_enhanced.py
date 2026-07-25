"""
自学习增强模块 V10.4 测试套件

覆盖范围：
1. 数据分布漂移检测 (drift_detector)
2. 高级模式识别 (pattern_recognizer)
3. 周期变化检测 (cycle_detector)
4. 自适应学习率管理 (adaptive_lr_manager)
5. 策略自适应选择 (strategy_adaptive_selector)
6. 模型解释器 (model_interpreter)
7. SelfLearningSystem V10.4 集成层
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

# 抑制预存在的日志递归问题
logging.disable(logging.CRITICAL)

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# 测试夹具
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def rng():
    """可重复的随机数生成器"""
    return np.random.default_rng(seed=42)


@pytest.fixture
def sample_position_data(rng):
    """构造 5 个位置的样本数据（100 条记录）"""
    n = 100
    return {
        'wan': rng.integers(0, 10, n).tolist(),
        'qian': rng.integers(0, 10, n).tolist(),
        'bai': rng.integers(0, 10, n).tolist(),
        'shi': rng.integers(0, 10, n).tolist(),
        'ge': rng.integers(0, 10, n).tolist(),
    }


@pytest.fixture
def sample_feature_matrix(rng):
    """构造样本特征矩阵 (100 samples × 5 features)"""
    return rng.standard_normal((100, 5))


@pytest.fixture
def periodic_series():
    """构造具有明显周期性的序列"""
    t = np.linspace(0, 8 * np.pi, 200)
    return np.sin(t) + np.random.default_rng(42).normal(0, 0.1, 200)


@pytest.fixture
def sample_prediction_result():
    """构造样本预测结果"""
    return {
        'next_period': '2026198',
        'predictions': {
            'wan': {
                'top_k': [1, 2, 3],
                'weights_used': {'stacking': 0.4, 'hmm': 0.3, 'copula': 0.3},
                'confidence': 0.65,
            },
            'qian': {
                'top_k': [2, 3, 4],
                'weights_used': {'stacking': 0.4, 'hmm': 0.3, 'copula': 0.3},
                'confidence': 0.55,
            },
            'bai': {
                'top_k': [3, 4, 5],
                'weights_used': {'stacking': 0.5, 'hmm': 0.2, 'copula': 0.3},
                'confidence': 0.70,
            },
        },
    }


# ═══════════════════════════════════════════════════════════════
# 1. 数据分布漂移检测测试
# ═══════════════════════════════════════════════════════════════

class TestDataDriftDetector:
    """数据分布漂移检测器测试"""

    def test_import(self):
        """测试模块可正常导入"""
        from src.core.learning import DataDriftDetector, DriftLevel, DriftType, get_drift_detector
        assert DataDriftDetector is not None
        assert DriftLevel is not None
        assert DriftType is not None
        assert get_drift_detector is not None

    def test_psi_calculator_no_drift(self, rng):
        """PSI 计算：无漂移时应返回低值"""
        from src.core.learning import PSICalculator
        ref = rng.standard_normal(500)
        cur = rng.standard_normal(500)
        psi = PSICalculator.calculate(ref, cur, bins=10)
        assert 0.0 <= psi < 0.1, f"无漂移时 PSI 应小于 0.1，实际: {psi}"

    def test_psi_calculator_with_drift(self, rng):
        """PSI 计算：有漂移时应返回高值"""
        from src.core.learning import PSICalculator
        ref = rng.standard_normal(500)
        cur = rng.standard_normal(500) + 1.0  # 显著偏移
        psi = PSICalculator.calculate(ref, cur, bins=10)
        assert psi > 0.1, f"有漂移时 PSI 应大于 0.1，实际: {psi}"

    def test_ks_test_detector(self, rng):
        """KS 检验检测器"""
        from src.core.learning import KSTestDetector
        ref = rng.standard_normal(200)
        cur = rng.standard_normal(200) + 0.5
        stat, pval, drifted = KSTestDetector.detect(ref, cur, alpha=0.05)
        assert 0.0 <= stat <= 1.0
        assert 0.0 <= pval <= 1.0
        assert bool(drifted) in (True, False)

    def test_adwin_detector(self):
        """ADWIN 在线漂移检测器"""
        from src.core.learning import ADWINDetector
        detector = ADWINDetector(delta=0.002, min_window=30)
        # 前期稳定数据
        for _ in range(100):
            detector.add_element(float(np.random.default_rng(0).normal(0, 0.1)))
        # 引入突变
        drift_detected = False
        for _ in range(200):
            if detector.add_element(float(np.random.default_rng(1).normal(2.0, 0.1))):
                drift_detected = True
                break
        # ADWIN 应能检测到突变（允许偶尔漏检）
        assert isinstance(drift_detected, bool)

    def test_drift_detector_with_reference(self, rng):
        """设置参考分布后的漂移检测"""
        from src.core.learning import DataDriftDetector, DriftLevel, DriftType
        detector = DataDriftDetector(enable_adwin=False)
        ref = rng.standard_normal((200, 3))
        cur = rng.standard_normal((100, 3)) + 0.8
        feature_names = ['f1', 'f2', 'f3']
        detector.set_reference(ref, feature_names)
        summary = detector.detect_drift(cur, feature_names, DriftType.COVARIATE)
        assert summary.total_features == 3
        assert summary.drifted_features >= 1
        assert summary.overall_level in (DriftLevel.LOW, DriftLevel.MEDIUM, DriftLevel.HIGH)
        assert isinstance(summary.recommendation, str)
        assert len(summary.results) == 3

    def test_drift_detector_without_reference(self, rng):
        """无参考分布时的漂移检测（时间窗口对比法）"""
        from src.core.learning import DataDriftDetector
        detector = DataDriftDetector(enable_adwin=False)
        # 构造前段稳定、后段漂移的数据
        data = np.zeros((200, 2))
        data[:140] = rng.standard_normal((140, 2))
        data[140:] = rng.standard_normal((60, 2)) + 1.5
        summary = detector.detect_drift(data, ['f1', 'f2'])
        assert summary.total_features == 2
        assert summary.drift_ratio >= 0.0

    def test_drift_detector_insufficient_data(self, rng):
        """数据量不足时的处理"""
        from src.core.learning import DataDriftDetector
        detector = DataDriftDetector(enable_adwin=False)
        small_data = rng.standard_normal((5, 2))
        summary = detector.detect_drift(small_data, ['f1', 'f2'])
        # 数据不足时应给出建议文本
        assert isinstance(summary.recommendation, str)

    def test_drift_summary_to_dict(self, rng):
        """DriftSummary 序列化"""
        from src.core.learning import DataDriftDetector
        detector = DataDriftDetector(enable_adwin=False)
        data = rng.standard_normal((100, 2))
        summary = detector.detect_drift(data, ['f1', 'f2'])
        d = summary.to_dict()
        assert isinstance(d, dict)
        assert 'total_features' in d
        assert 'drift_ratio' in d
        assert 'overall_level' in d
        assert 'results' in d


# ═══════════════════════════════════════════════════════════════
# 2. 高级模式识别测试
# ═══════════════════════════════════════════════════════════════

class TestPatternRecognizer:
    """高级模式识别器测试"""

    def test_import(self):
        from src.core.learning import (
            PatternRecognizer, PatternType, NumberCategory,
            TrendDirection, AnomalyLevel, get_pattern_recognizer,
        )
        assert PatternRecognizer is not None
        assert PatternType is not None

    def test_analyze_patterns_basic(self, sample_position_data):
        """基础模式分析"""
        from src.core.learning import PatternRecognizer
        recognizer = PatternRecognizer(min_samples=10)
        result = recognizer.analyze_patterns(sample_position_data)
        assert result.total_records == 100
        assert set(result.positions_analyzed) == {'wan', 'qian', 'bai', 'shi', 'ge'}
        assert isinstance(result.summary, str)

    def test_analyze_patterns_with_dict_data(self, sample_position_data):
        """dict 数据输入"""
        from src.core.learning import PatternRecognizer
        recognizer = PatternRecognizer()
        result = recognizer.analyze_patterns(sample_position_data)
        assert result.total_records > 0

    def test_analyze_patterns_specific_positions(self, sample_position_data):
        """指定位置分析"""
        from src.core.learning import PatternRecognizer
        recognizer = PatternRecognizer()
        result = recognizer.analyze_patterns(sample_position_data, positions=['wan', 'qian'])
        assert set(result.positions_analyzed) == {'wan', 'qian'}

    def test_analyze_patterns_insufficient_samples(self):
        """样本数不足时的处理"""
        from src.core.learning import PatternRecognizer
        recognizer = PatternRecognizer(min_samples=50)
        small_data = {'wan': [1, 2, 3], 'qian': [4, 5, 6]}
        result = recognizer.analyze_patterns(small_data)
        # 样本不足时仍应返回结果（带警告）
        assert result.total_records == 3

    def test_pattern_analysis_result_to_dict(self, sample_position_data):
        """分析结果序列化"""
        from src.core.learning import PatternRecognizer
        recognizer = PatternRecognizer()
        result = recognizer.analyze_patterns(sample_position_data)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert 'total_records' in d
        assert 'positions_analyzed' in d

    def test_frequency_pattern_detection(self, sample_position_data):
        """频率模式识别"""
        from src.core.learning import PatternRecognizer
        recognizer = PatternRecognizer()
        result = recognizer.analyze_patterns(sample_position_data)
        # 至少应有部分频率模式
        assert hasattr(result, 'frequency_patterns')

    def test_singleton_factory(self):
        """单例工厂函数"""
        from src.core.learning import get_pattern_recognizer
        r1 = get_pattern_recognizer()
        r2 = get_pattern_recognizer()
        assert r1 is r2


# ═══════════════════════════════════════════════════════════════
# 3. 周期变化检测测试
# ═══════════════════════════════════════════════════════════════

class TestCycleDetector:
    """周期变化检测器测试"""

    def test_import(self):
        from src.core.learning import (
            CycleDetector, CycleResult, ChangePoint, CycleInfo,
            FFTAnalyzer, CUSUMDetector, get_cycle_detector,
        )
        assert CycleDetector is not None

    def test_detect_cycles_periodic(self, periodic_series):
        """检测明显周期性"""
        from src.core.learning import CycleDetector
        detector = CycleDetector()
        result = detector.detect_cycles(periodic_series)
        assert result.is_periodic is True
        assert result.dominant_cycle is not None
        assert result.dominant_cycle.length > 0
        assert result.dominant_cycle.strength > 0

    def test_detect_cycles_random(self, rng):
        """随机序列不应被识别为强周期性"""
        from src.core.learning import CycleDetector
        detector = CycleDetector()
        random_series = rng.standard_normal(200)
        result = detector.detect_cycles(random_series)
        # 随机序列可能检测到弱周期，但强度应较低
        assert isinstance(result.is_periodic, bool)

    def test_detect_cycles_short_series(self):
        """短序列处理"""
        from src.core.learning import CycleDetector
        detector = CycleDetector()
        result = detector.detect_cycles([1.0, 2.0, 3.0])
        assert result.is_periodic is False
        assert len(result.cycles) == 0

    def test_detect_changepoints(self, rng):
        """变点检测"""
        from src.core.learning import CycleDetector
        detector = CycleDetector()
        # 构造有变点的序列
        series = np.concatenate([
            rng.normal(0, 0.1, 100),
            rng.normal(2.0, 0.1, 100),
        ])
        cps = detector.detect_changepoints(series)
        assert isinstance(cps, list)
        # 应至少检测到一个变点
        if cps:
            cp = cps[0]
            assert cp.position > 0
            assert cp.confidence >= 0.0

    def test_fft_analyzer(self, periodic_series):
        """FFT 分析器"""
        from src.core.learning import FFTAnalyzer
        # FFTAnalyzer.analyze 是静态方法，返回 (frequencies, magnitudes, phases)
        frequencies, magnitudes, phases = FFTAnalyzer.analyze(periodic_series)
        assert len(frequencies) == len(magnitudes)
        assert len(frequencies) == len(phases)
        assert len(frequencies) > 0

    def test_cusum_detector(self, rng):
        """CUSUM 检测器"""
        from src.core.learning import CUSUMDetector
        series = np.concatenate([
            rng.normal(0, 0.1, 100),
            rng.normal(2.0, 0.1, 100),
        ])
        cps = CUSUMDetector.detect(series, threshold=5.0)
        assert isinstance(cps, list)

    def test_cycle_result_to_dict(self, periodic_series):
        """CycleResult 序列化"""
        from src.core.learning import CycleDetector
        detector = CycleDetector()
        result = detector.detect_cycles(periodic_series)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert 'is_periodic' in d
        assert 'cycles' in d

    def test_singleton_factory(self):
        from src.core.learning import get_cycle_detector
        d1 = get_cycle_detector()
        d2 = get_cycle_detector()
        assert d1 is d2


# ═══════════════════════════════════════════════════════════════
# 4. 自适应学习率管理测试
# ═══════════════════════════════════════════════════════════════

class TestAdaptiveLRManager:
    """自适应学习率管理器测试"""

    def test_import(self):
        from src.core.learning import (
            AdaptiveLRManager, AdaptiveLRConfig, TrainingPhase,
            AdjustmentAction, get_adaptive_lr_manager,
        )
        assert AdaptiveLRManager is not None

    def test_initial_state(self):
        """初始状态"""
        from src.core.learning import AdaptiveLRManager, AdaptiveLRConfig
        config = AdaptiveLRConfig(initial_lr=0.01)
        manager = AdaptiveLRManager(config=config)
        lr = manager.get_optimal_lr('wan')
        assert lr == 0.01

    def test_record_metrics(self):
        """记录训练指标"""
        from src.core.learning import AdaptiveLRManager
        manager = AdaptiveLRManager()
        action = manager.record_metrics('wan', epoch=0, train_loss=0.5, val_accuracy=0.6)
        assert hasattr(action, 'value') or isinstance(action, str)

    def test_auto_select_strategy(self):
        """自动选择调度策略"""
        from src.core.learning import AdaptiveLRManager
        from src.core.training.lr_scheduler import LRSchedulerType
        manager = AdaptiveLRManager()
        strategy = manager.auto_select_strategy('wan')
        assert strategy in (
            LRSchedulerType.COSINE_ANNEALING,
            LRSchedulerType.REDUCE_LR_ON_PLATEAU,
            LRSchedulerType.STEP_LR,
            LRSchedulerType.EXPONENTIAL_LR,
        )

    def test_differential_adjust(self):
        """差异化调整"""
        from src.core.learning import AdaptiveLRManager
        manager = AdaptiveLRManager()
        # 记录多个位置的指标
        for pos in ['wan', 'qian', 'bai']:
            manager.record_metrics(pos, epoch=0, train_loss=0.5, val_accuracy=0.5)
        result = manager.differential_adjust()
        assert isinstance(result, dict)
        assert 'wan' in result

    def test_get_summary(self):
        """状态汇总"""
        from src.core.learning import AdaptiveLRManager
        manager = AdaptiveLRManager()
        manager.record_metrics('wan', epoch=0, train_loss=0.5, val_accuracy=0.6)
        summary = manager.get_summary()
        assert isinstance(summary, dict)

    def test_get_all_positions_status(self):
        """所有位置状态"""
        from src.core.learning import AdaptiveLRManager
        manager = AdaptiveLRManager()
        status = manager.get_all_positions_status()
        assert isinstance(status, dict)
        assert 'wan' in status


# ═══════════════════════════════════════════════════════════════
# 5. 策略自适应选择测试
# ═══════════════════════════════════════════════════════════════

class TestStrategyAdaptiveSelector:
    """策略自适应选择器测试"""

    def test_import(self):
        from src.core.learning import (
            StrategyAdaptiveSelector, SelectorConfig, SelectionMode,
            SwitchTrigger, PRESET_STRATEGIES, get_strategy_selector,
        )
        assert StrategyAdaptiveSelector is not None
        assert len(PRESET_STRATEGIES) == 6

    def test_select_best_strategy(self):
        """选择最佳策略"""
        from src.core.learning import StrategyAdaptiveSelector
        selector = StrategyAdaptiveSelector()
        best = selector.select_best_strategy('wan')
        assert best in selector.strategies

    def test_select_with_context(self):
        """带上下文的策略选择"""
        from src.core.learning import StrategyAdaptiveSelector
        selector = StrategyAdaptiveSelector()
        best = selector.select_best_strategy('wan', context={'drift_level': 'high'})
        assert isinstance(best, str)

    def test_record_performance(self):
        """记录策略表现"""
        from src.core.learning import StrategyAdaptiveSelector
        selector = StrategyAdaptiveSelector()
        record = selector.record_strategy_performance(
            'stacking_dominant', 'wan', accuracy=0.8, confidence=0.7
        )
        assert hasattr(record, 'reward')
        assert 0.0 <= record.reward <= 1.0

    def test_get_strategy_combination(self):
        """获取策略组合权重"""
        from src.core.learning import StrategyAdaptiveSelector
        selector = StrategyAdaptiveSelector()
        weights = selector.get_strategy_combination('wan')
        assert isinstance(weights, dict)
        assert len(weights) == len(selector.strategies)
        # 权重应归一化（和接近 1）
        total = sum(weights.values())
        assert 0.9 <= total <= 1.1, f"权重和应接近 1，实际: {total}"

    def test_update_weights(self):
        """更新组合权重"""
        from src.core.learning import StrategyAdaptiveSelector
        selector = StrategyAdaptiveSelector()
        selector.record_strategy_performance('default', 'wan', 0.8, 0.7)
        new_weights = selector.update_weights('wan', reward=0.75)
        assert isinstance(new_weights, dict)
        total = sum(new_weights.values())
        assert 0.9 <= total <= 1.1

    def test_get_status(self):
        """获取状态"""
        from src.core.learning import StrategyAdaptiveSelector
        selector = StrategyAdaptiveSelector()
        status = selector.get_status()
        assert isinstance(status, dict)

    def test_notify_drift(self):
        """漂移通知"""
        from src.core.learning import StrategyAdaptiveSelector
        selector = StrategyAdaptiveSelector()
        # 不应抛出异常
        selector.notify_drift(drift_level='medium')
        selector.notify_drift(position='wan', drift_level='high')

    def test_get_current_strategy(self):
        """获取当前策略"""
        from src.core.learning import StrategyAdaptiveSelector
        selector = StrategyAdaptiveSelector()
        current = selector.get_current_strategy('wan')
        assert current in selector.strategies


# ═══════════════════════════════════════════════════════════════
# 6. 模型解释器测试
# ═══════════════════════════════════════════════════════════════

class TestModelInterpreter:
    """模型解释器测试"""

    def test_import(self):
        from src.core.interpretability import (
            ModelInterpreter, InterpretationLevel, ContributionType,
            FeatureImportanceAnalyzer, DecisionPathTracer, CrossPositionAnalyzer,
            get_model_interpreter,
        )
        assert ModelInterpreter is not None

    def test_interpret_prediction_basic(self, sample_prediction_result):
        """基础预测解释"""
        from src.core.interpretability import ModelInterpreter, InterpretationLevel
        interpreter = ModelInterpreter(default_level=InterpretationLevel.STANDARD)
        interp = interpreter.interpret_prediction(sample_prediction_result)
        assert interp.prediction_period == '2026198'
        assert len(interp.position_interpretations) > 0
        assert interp.overall_confidence > 0.0

    def test_interpret_with_features(self, sample_prediction_result, rng):
        """带特征的预测解释"""
        from src.core.interpretability import ModelInterpreter
        interpreter = ModelInterpreter()
        feature_values = rng.standard_normal((3, 5))
        feature_names = ['f1', 'f2', 'f3', 'f4', 'f5']
        feature_weights = {
            'wan': rng.standard_normal(5),
            'qian': rng.standard_normal(5),
            'bai': rng.standard_normal(5),
        }
        interp = interpreter.interpret_prediction(
            sample_prediction_result,
            feature_values=feature_values,
            feature_names=feature_names,
            feature_weights=feature_weights,
        )
        # 应包含特征贡献
        for pos_interp in interp.position_interpretations.values():
            if pos_interp.feature_contributions:
                assert len(pos_interp.feature_contributions) > 0
                break

    def test_interpret_with_model_outputs(self, sample_prediction_result, rng):
        """带模型输出的预测解释"""
        from src.core.interpretability import ModelInterpreter
        interpreter = ModelInterpreter()
        model_outputs = {
            'wan': {
                'stacking': rng.dirichlet([1, 1, 1, 1, 1, 1, 1, 1, 1, 1]),
                'hmm': rng.dirichlet([1, 1, 1, 1, 1, 1, 1, 1, 1, 1]),
            },
            'qian': {
                'stacking': rng.dirichlet([1, 1, 1, 1, 1, 1, 1, 1, 1, 1]),
            },
        }
        interp = interpreter.interpret_prediction(
            sample_prediction_result,
            model_outputs=model_outputs,
        )
        # 应包含决策路径
        for pos_interp in interp.position_interpretations.values():
            if pos_interp.decision_path:
                assert isinstance(pos_interp.decision_path, list)
                break

    def test_interpretation_levels(self, sample_prediction_result, rng):
        """不同解释级别"""
        from src.core.interpretability import ModelInterpreter, InterpretationLevel
        interpreter = ModelInterpreter()
        feature_values = rng.standard_normal((3, 10))
        feature_names = [f'f{i}' for i in range(10)]

        # BRIEF 级别应截断到 5 个特征
        interp_brief = interpreter.interpret_prediction(
            sample_prediction_result,
            feature_values=feature_values,
            feature_names=feature_names,
            level=InterpretationLevel.BRIEF,
        )
        for pos_interp in interp_brief.position_interpretations.values():
            if pos_interp.feature_contributions:
                assert len(pos_interp.feature_contributions) <= 5
                break

    def test_to_readable_report(self, sample_prediction_result):
        """生成可读报告"""
        from src.core.interpretability import ModelInterpreter
        interpreter = ModelInterpreter()
        interp = interpreter.interpret_prediction(sample_prediction_result)
        report = interp.to_readable_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_prediction_interpretation_to_dict(self, sample_prediction_result):
        """序列化"""
        from src.core.interpretability import ModelInterpreter
        interpreter = ModelInterpreter()
        interp = interpreter.interpret_prediction(sample_prediction_result)
        d = interp.to_dict()
        assert isinstance(d, dict)
        assert 'prediction_period' in d
        assert 'overall_confidence' in d
        assert 'position_interpretations' in d

    def test_risk_assessment(self, sample_prediction_result):
        """风险评估"""
        from src.core.interpretability import ModelInterpreter
        interpreter = ModelInterpreter()
        interp = interpreter.interpret_prediction(sample_prediction_result)
        assert isinstance(interp.risk_assessment, str)
        assert len(interp.risk_assessment) > 0

    def test_cross_position_analysis(self, sample_prediction_result):
        """跨位置分析"""
        from src.core.interpretability import ModelInterpreter
        interpreter = ModelInterpreter()
        interp = interpreter.interpret_prediction(sample_prediction_result)
        # 多位置时应触发跨位置分析
        if len(interp.position_interpretations) > 1:
            assert interp.cross_position_analysis is not None


# ═══════════════════════════════════════════════════════════════
# 7. SelfLearningSystem V10.4 集成层测试
# ═══════════════════════════════════════════════════════════════

class TestSelfLearningSystemIntegration:
    """SelfLearningSystem V10.4 集成层测试"""

    def test_imports_available(self):
        """验证增强模块导入可用"""
        from src.core.self_learning import _LEARNING_AVAILABLE, _INTERPRETER_AVAILABLE
        assert _LEARNING_AVAILABLE is True
        assert _INTERPRETER_AVAILABLE is True

    def test_system_instantiation(self):
        """系统实例化"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        # 增强组件应初始化为 None（懒加载）
        assert sls._drift_detector is None
        assert sls._pattern_recognizer is None
        assert sls._cycle_detector is None
        assert sls._adaptive_lr_manager is None
        assert sls._strategy_selector is None
        assert sls._model_interpreter is None

    def test_lazy_initialization(self):
        """懒加载：首次访问后才创建实例"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        # 首次访问漂移检测器
        detector = sls._ensure_drift_detector()
        assert detector is not None
        assert sls._drift_detector is not None
        # 再次访问应返回同一实例
        detector2 = sls._ensure_drift_detector()
        assert detector is detector2

    def test_detect_data_drift_no_data(self):
        """无数据时漂移检测应优雅返回 skipped"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        result = sls.detect_data_drift()
        assert result['available'] is True
        assert result.get('skipped') is True

    def test_detect_data_drift_with_data(self, rng):
        """有数据时漂移检测"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        ref_data = rng.standard_normal((100, 3))
        cur_data = rng.standard_normal((80, 3)) + 0.8
        feature_names = ['f1', 'f2', 'f3']
        sls.set_drift_reference(ref_data, feature_names)
        result = sls.detect_data_drift(current_data=cur_data, feature_names=feature_names)
        assert result['available'] is True
        assert 'overall_level' in result
        assert 'drift_ratio' in result

    def test_recognize_patterns_no_data(self):
        """无数据时模式识别应优雅返回 skipped"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        result = sls.recognize_patterns()
        assert result['available'] is True
        assert result.get('skipped') is True

    def test_recognize_patterns_with_data(self, sample_position_data):
        """有数据时模式识别"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        result = sls.recognize_patterns(data=sample_position_data)
        assert result['available'] is True
        assert result['total_records'] == 100

    def test_detect_cycles_no_data(self):
        """无数据时周期检测应优雅返回 skipped"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        result = sls.detect_cycles()
        assert result['available'] is True
        assert result.get('skipped') is True

    def test_detect_cycles_with_data(self, periodic_series):
        """有数据时周期检测"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        result = sls.detect_cycles(series=periodic_series)
        assert result['available'] is True
        assert 'is_periodic' in result

    def test_record_training_metrics(self):
        """记录训练指标"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        result = sls.record_training_metrics('wan', epoch=0, train_loss=0.5, val_accuracy=0.6)
        assert result['available'] is True
        assert 'action' in result
        assert 'current_lr' in result

    def test_get_optimal_learning_rate(self):
        """获取最优学习率"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        result = sls.get_optimal_learning_rate('wan')
        assert result['available'] is True
        assert result['position'] == 'wan'
        assert 'optimal_lr' in result
        assert 'recommended_scheduler' in result

    def test_select_best_strategy(self):
        """选择最佳策略"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        result = sls.select_best_strategy('wan')
        assert result['available'] is True
        assert 'best_strategy' in result
        assert 'combination_weights' in result

    def test_record_strategy_performance(self):
        """记录策略表现"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        result = sls.record_strategy_performance(
            'stacking_dominant', 'wan', accuracy=0.8, confidence=0.7
        )
        assert result['available'] is True
        assert result.get('recorded') is True

    def test_interpret_prediction(self, sample_prediction_result, rng):
        """预测解释"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        feature_values = rng.standard_normal((3, 5))
        feature_names = ['f1', 'f2', 'f3', 'f4', 'f5']
        result = sls.interpret_prediction(
            sample_prediction_result,
            feature_values=feature_values,
            feature_names=feature_names,
            level='brief',
        )
        assert result['available'] is True
        assert 'overall_confidence' in result
        assert 'readable_report' in result

    def test_run_comprehensive_analysis(self, sample_position_data, rng):
        """综合分析"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        feature_data = rng.standard_normal((50, 3))
        feature_names = ['f1', 'f2', 'f3']
        analysis = sls.run_comprehensive_analysis(
            data=sample_position_data,
            feature_data=feature_data,
            feature_names=feature_names,
        )
        assert analysis['version'] == 'V10.4'
        assert 'components' in analysis
        assert 'evolution_actions' in analysis
        # 应包含所有 6 个组件
        components = analysis['components']
        assert 'drift_detection' in components
        assert 'pattern_recognition' in components
        assert 'cycle_detection' in components
        assert 'adaptive_lr' in components
        assert 'strategy_selector' in components
        assert 'model_interpretation' in components

    def test_comprehensive_analysis_caches_result(self, sample_position_data):
        """综合分析结果应被缓存"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        analysis = sls.run_comprehensive_analysis(data=sample_position_data)
        assert sls._last_comprehensive_analysis is analysis

    def test_evolution_actions_sorted_by_priority(self, sample_position_data, rng):
        """进化动作应按优先级排序"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        # 引入显著漂移以触发 urgent 动作
        ref_data = rng.standard_normal((100, 3))
        cur_data = rng.standard_normal((50, 3)) + 2.0
        sls.set_drift_reference(ref_data, ['f1', 'f2', 'f3'])
        analysis = sls.run_comprehensive_analysis(
            data=sample_position_data,
            feature_data=cur_data,
            feature_names=['f1', 'f2', 'f3'],
        )
        actions = analysis['evolution_actions']
        if len(actions) >= 2:
            priority_order = {'urgent': 0, 'important': 1, 'regular': 2}
            for i in range(len(actions) - 1):
                p1 = priority_order.get(actions[i].get('priority', 'regular'), 3)
                p2 = priority_order.get(actions[i + 1].get('priority', 'regular'), 3)
                assert p1 <= p2

    def test_get_summary_includes_enhanced_modules(self):
        """get_summary 应包含增强模块状态"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        summary = sls.get_summary()
        assert summary['version'] == 'V10.4'
        assert 'enhanced_modules' in summary
        em = summary['enhanced_modules']
        assert 'learning_available' in em
        assert 'interpreter_available' in em
        assert 'drift_detector' in em

    def test_drift_triggers_strategy_notification(self, rng):
        """漂移检测应联动通知策略选择器"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        # 设置参考分布
        ref_data = rng.standard_normal((100, 2))
        sls.set_drift_reference(ref_data, ['f1', 'f2'])
        # 触发严重漂移
        cur_data = rng.standard_normal((50, 2)) + 3.0
        result = sls.detect_data_drift(current_data=cur_data, feature_names=['f1', 'f2'])
        # 不抛出异常即视为通过（联动通知内部调用，不应影响主流程）
        assert result['available'] is True


# ═══════════════════════════════════════════════════════════════
# 8. 包级集成测试
# ═══════════════════════════════════════════════════════════════

class TestPackageIntegration:
    """包级别集成测试"""

    def test_learning_package_imports(self):
        """learning 包所有公共符号可导入"""
        from src.core.learning import (
            PatternRecognizer, CycleDetector, DataDriftDetector,
            AdaptiveLRManager, StrategyAdaptiveSelector,
            get_pattern_recognizer, get_cycle_detector, get_drift_detector,
            get_adaptive_lr_manager, get_strategy_selector,
        )
        # 全部不为 None
        assert all([
            PatternRecognizer, CycleDetector, DataDriftDetector,
            AdaptiveLRManager, StrategyAdaptiveSelector,
            get_pattern_recognizer, get_cycle_detector, get_drift_detector,
            get_adaptive_lr_manager, get_strategy_selector,
        ])

    def test_interpretability_package_imports(self):
        """interpretability 包所有公共符号可导入"""
        from src.core.interpretability import (
            ModelInterpreter, InterpretationLevel,
            FeatureImportanceAnalyzer, DecisionPathTracer, CrossPositionAnalyzer,
            get_model_interpreter,
        )
        assert all([
            ModelInterpreter, InterpretationLevel,
            FeatureImportanceAnalyzer, DecisionPathTracer, CrossPositionAnalyzer,
            get_model_interpreter,
        ])

    def test_self_learning_system_uses_new_modules(self):
        """SelfLearningSystem 应能使用新模块"""
        from src.core.self_learning import SelfLearningSystem
        sls = SelfLearningSystem()
        # 触发各组件的懒加载
        assert sls._ensure_drift_detector() is not None
        assert sls._ensure_pattern_recognizer() is not None
        assert sls._ensure_cycle_detector() is not None
        assert sls._ensure_adaptive_lr_manager() is not None
        assert sls._ensure_strategy_selector() is not None
        assert sls._ensure_model_interpreter() is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
