"""
预测模块单元测试
测试PL5Predictor、HMMModel、CopulaModel、BSTSModel、ExtremeValueModel等核心组件
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# 导入被测模块
from src.core.models.predictor import (
    PL5Predictor,
    HMMModel,
    CopulaModel,
    BSTSModel,
    ExtremeValueModel,
    StackingEnsemble,
    _safe_proba,
    _top_k_from_proba,
    POSITIONS,
    DIGITS,
    MODEL_WEIGHTS,
)

# ═══════════════════════════════════════════════════════════════
# 工具函数测试
# ═══════════════════════════════════════════════════════════════


class TestUtilityFunctions:
    """测试工具函数"""

    @pytest.mark.unit
    def test_safe_proba_normal(self):
        """测试正常概率数组"""
        proba = np.array([0.1, 0.2, 0.3, 0.4])
        result = _safe_proba(proba, n_classes=10)

        assert len(result) == 10
        assert np.isclose(result.sum(), 1.0)
        assert np.allclose(result[:4], proba)
        assert np.all(result[4:] == 0)

    @pytest.mark.unit
    def test_safe_proba_short(self):
        """测试短概率数组"""
        proba = np.array([0.5, 0.3])
        result = _safe_proba(proba, n_classes=10)

        assert len(result) == 10
        assert np.allclose(result[:2], proba)
        assert np.all(result[2:] == 0)

    @pytest.mark.unit
    def test_safe_proba_long(self):
        """测试长概率数组"""
        proba = np.array([0.1] * 15)
        result = _safe_proba(proba, n_classes=10)

        assert len(result) == 10
        assert np.allclose(result, proba[:10])

    @pytest.mark.unit
    def test_safe_proba_empty(self):
        """测试空概率数组"""
        proba = np.array([])
        result = _safe_proba(proba, n_classes=10)

        assert len(result) == 10
        assert np.all(result == 0)

    @pytest.mark.unit
    def test_top_k_from_proba(self):
        """测试从概率取Top K"""
        proba = np.array([0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5])
        result = _top_k_from_proba(proba, k=3)

        assert len(result) == 3
        assert result == [9, 8, 7]  # 最高概率的索引

    @pytest.mark.unit
    def test_top_k_from_proba_k_larger_than_n(self):
        """测试K大于数组长度"""
        proba = np.array([0.3, 0.2, 0.5])
        result = _top_k_from_proba(proba, k=5)

        assert len(result) == 3


# ═══════════════════════════════════════════════════════════════
# HMMModel 测试
# ═══════════════════════════════════════════════════════════════


class TestHMMModel:
    """测试HMM模型"""

    @pytest.fixture
    def hmm_model(self):
        return HMMModel(n_states=4)

    @pytest.fixture
    def sample_sequence(self):
        """创建样本序列"""
        np.random.seed(42)
        return np.random.randint(0, 10, 100)

    @pytest.mark.unit
    def test_hmm_initialization(self, hmm_model):
        """测试HMM模型初始化"""
        assert hmm_model.n_states == 4
        assert len(hmm_model.transition) == 0
        assert hmm_model._alpha == 1.0

    @pytest.mark.unit
    def test_hmm_fit(self, hmm_model, sample_sequence):
        """测试HMM拟合"""
        hmm_model.fit(sample_sequence)

        # 应该学习到转移概率
        assert len(hmm_model.transition) > 0

        # 每个状态应该有概率分布
        for state, probs in hmm_model.transition.items():
            assert len(probs) == 10
            assert np.isclose(probs.sum(), 1.0)

    @pytest.mark.unit
    def test_hmm_predict(self, hmm_model, sample_sequence):
        """测试HMM预测"""
        hmm_model.fit(sample_sequence)

        prediction = hmm_model.predict(sample_sequence)

        assert len(prediction) == 10
        assert np.isclose(prediction.sum(), 1.0)
        assert all(p >= 0 for p in prediction)

    @pytest.mark.unit
    def test_hmm_predict_untrained(self, hmm_model):
        """测试未训练HMM预测"""
        prediction = hmm_model.predict(np.array([1, 2, 3]))

        # 未训练时应返回均匀分布
        assert len(prediction) == 10
        assert np.allclose(prediction, 0.1)

    @pytest.mark.unit
    def test_hmm_predict_proba(self, hmm_model, sample_sequence):
        """测试HMM预测概率"""
        hmm_model.fit(sample_sequence)

        # 测试已知状态
        last_digit = int(sample_sequence[-1])
        if last_digit in hmm_model.transition:
            proba = hmm_model.predict_proba(last_digit)
            assert len(proba) == 10
            assert np.isclose(proba.sum(), 1.0)

    @pytest.mark.unit
    def test_hmm_predict_proba_unknown_state(self, hmm_model):
        """测试未知状态的HMM预测"""
        proba = hmm_model.predict_proba(5)

        # 未知状态应返回均匀分布
        assert len(proba) == 10
        assert np.allclose(proba, 0.1)


# ═══════════════════════════════════════════════════════════════
# CopulaModel 测试
# ═══════════════════════════════════════════════════════════════


class TestCopulaModel:
    """测试Copula模型"""

    @pytest.fixture
    def copula_model(self):
        return CopulaModel()

    @pytest.fixture
    def position_matrix(self):
        """创建位置矩阵"""
        np.random.seed(42)
        return np.random.randint(0, 10, (100, 5)).astype(float)

    @pytest.mark.unit
    def test_copula_initialization(self, copula_model):
        """测试Copula模型初始化"""
        assert copula_model.kendall_tau is None
        assert copula_model._fitted is False

    @pytest.mark.unit
    def test_copula_fit(self, copula_model, position_matrix):
        """测试Copula拟合"""
        copula_model.fit(position_matrix)

        assert copula_model._fitted is True
        assert copula_model.kendall_tau is not None
        assert copula_model.kendall_tau.shape == (5, 5)

    @pytest.mark.unit
    def test_copula_predict(self, copula_model, position_matrix):
        """测试Copula预测"""
        copula_model.fit(position_matrix)

        result = copula_model.predict(position_matrix)

        assert result.shape == (5, 5)
        # 对角线应为1（自相关）
        assert np.allclose(np.diag(result), 1.0)

    @pytest.mark.unit
    def test_copula_predict_untrained(self, copula_model, position_matrix):
        """测试未训练Copula预测"""
        result = copula_model.predict(position_matrix)

        # 未训练时应返回单位矩阵
        assert result.shape == (5, 5)
        assert np.allclose(result, np.eye(5))


# ═══════════════════════════════════════════════════════════════
# BSTSModel 测试
# ═══════════════════════════════════════════════════════════════


class TestBSTSModel:
    """测试BSTS模型"""

    @pytest.fixture
    def bsts_model(self):
        return BSTSModel(alpha=0.05)

    @pytest.fixture
    def sample_sequence(self):
        np.random.seed(42)
        return np.random.randint(0, 10, 100)

    @pytest.mark.unit
    def test_bsts_initialization(self, bsts_model):
        """测试BSTS模型初始化"""
        assert bsts_model.alpha == 0.05
        assert np.allclose(bsts_model.proba, 0.1)
        assert bsts_model._fitted is False

    @pytest.mark.unit
    def test_bsts_fit(self, bsts_model, sample_sequence):
        """测试BSTS拟合"""
        bsts_model.fit(sample_sequence)

        assert bsts_model._fitted is True
        assert len(bsts_model.proba) == 10
        assert np.isclose(bsts_model.proba.sum(), 1.0)

    @pytest.mark.unit
    def test_bsts_predict(self, bsts_model, sample_sequence):
        """测试BSTS预测"""
        bsts_model.fit(sample_sequence)

        prediction = bsts_model.predict(sample_sequence)

        assert len(prediction) == 10
        assert np.isclose(prediction.sum(), 1.0)

    @pytest.mark.unit
    def test_bsts_predict_untrained(self, bsts_model, sample_sequence):
        """测试未训练BSTS预测"""
        prediction = bsts_model.predict(sample_sequence)

        # 未训练时应返回均匀分布
        assert len(prediction) == 10
        assert np.allclose(prediction, 0.1)


# ═══════════════════════════════════════════════════════════════
# ExtremeValueModel 测试
# ═══════════════════════════════════════════════════════════════


class TestExtremeValueModel:
    """测试极值模型"""

    @pytest.fixture
    def evm_model(self):
        return ExtremeValueModel(threshold=9.0)

    @pytest.mark.unit
    def test_evm_initialization(self, evm_model):
        """测试极值模型初始化"""
        assert evm_model.threshold == 9.0
        assert np.all(evm_model.omission == 0)
        assert evm_model._fitted is False

    @pytest.mark.unit
    def test_evm_fit(self, evm_model):
        """测试极值模型拟合"""
        # 创建序列，其中数字5很久没出现
        sequence = np.array([0, 1, 2, 3, 4, 6, 7, 8, 9] * 10 + [0, 1, 2])

        evm_model.fit(sequence)

        assert evm_model._fitted is True
        # 数字5的遗漏应该很大
        assert evm_model.omission[5] > evm_model.omission[0]

    @pytest.mark.unit
    def test_evm_predict(self, evm_model):
        """测试极值模型预测"""
        sequence = np.array([0, 1, 2, 3, 4, 6, 7, 8, 9] * 10)

        evm_model.fit(sequence)
        prediction = evm_model.predict(sequence)

        assert len(prediction) == 10
        assert np.isclose(prediction.sum(), 1.0)
        # 遗漏大的数字应该有更高概率
        assert prediction[5] > prediction[0]

    @pytest.mark.unit
    def test_evm_predict_untrained(self, evm_model):
        """测试未训练极值模型预测"""
        prediction = evm_model.predict(np.array([1, 2, 3]))

        # 未训练时应返回均匀分布
        assert len(prediction) == 10
        assert np.allclose(prediction, 0.1)


# ═══════════════════════════════════════════════════════════════
# StackingEnsemble 测试
# ═══════════════════════════════════════════════════════════════


class TestStackingEnsemble:
    """测试Stacking集成模型"""

    @pytest.fixture
    def stacking(self):
        return StackingEnsemble()

    @pytest.fixture
    def sample_data(self):
        """创建样本数据"""
        np.random.seed(42)
        n = 50
        return pd.DataFrame(
            {
                "feature_1": np.random.randn(n),
                "feature_2": np.random.randn(n),
                "wan": np.random.randint(0, 10, n),
                "qian": np.random.randint(0, 10, n),
                "bai": np.random.randint(0, 10, n),
                "shi": np.random.randint(0, 10, n),
                "ge": np.random.randint(0, 10, n),
            }
        )

    @pytest.mark.unit
    def test_stacking_initialization(self, stacking):
        """测试Stacking初始化"""
        assert len(stacking.position_models) == 0
        assert len(stacking.meta_models) == 0
        assert stacking._fitted is False
        assert len(stacking.BASE_MODELS) == 3  # rf, gbm, et

    @pytest.mark.unit
    @pytest.mark.slow
    def test_stacking_fit_position_models(self, stacking, sample_data):
        """测试Stacking拟合"""
        feature_cols = ["feature_1", "feature_2"]

        stacking.fit_position_models(sample_data, feature_cols)

        assert stacking._fitted is True
        assert len(stacking.position_models) == 5  # 5个位置
        assert len(stacking.meta_models) == 5

    @pytest.mark.unit
    @pytest.mark.slow
    def test_stacking_predict_proba_position(self, stacking, sample_data):
        """测试Stacking位置预测"""
        feature_cols = ["feature_1", "feature_2"]

        stacking.fit_position_models(sample_data, feature_cols)

        x = np.array([0.5, -0.5])
        proba = stacking.predict_proba_position("wan", x)

        assert len(proba) == 10
        assert np.isclose(proba.sum(), 1.0)
        assert all(p >= 0 for p in proba)

    @pytest.mark.unit
    def test_stacking_predict_proba_untrained(self, stacking):
        """测试未训练Stacking预测"""
        x = np.array([0.5, -0.5])
        proba = stacking.predict_proba_position("wan", x)

        # 未训练时应返回均匀分布
        assert len(proba) == 10
        assert np.allclose(proba, 0.1)


# ═══════════════════════════════════════════════════════════════
# PL5Predictor 测试
# ═══════════════════════════════════════════════════════════════


class TestPL5Predictor:
    """测试PL5主预测器"""

    @pytest.fixture
    def predictor(self):
        return PL5Predictor()

    @pytest.fixture
    def sample_data(self):
        """创建样本数据"""
        np.random.seed(42)
        n = 50
        return pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(n)],
                "feature_1": np.random.randn(n),
                "feature_2": np.random.randn(n),
                "wan": np.random.randint(0, 10, n),
                "qian": np.random.randint(0, 10, n),
                "bai": np.random.randint(0, 10, n),
                "shi": np.random.randint(0, 10, n),
                "ge": np.random.randint(0, 10, n),
            }
        )

    @pytest.mark.unit
    def test_predictor_initialization(self, predictor):
        """测试预测器初始化"""
        assert len(predictor.stacking) == 0
        assert len(predictor.hmm_models) == 0
        assert len(predictor.bsts_models) == 0
        assert len(predictor.evm_models) == 0
        assert predictor.copula is None
        assert predictor.is_trained is False
        assert predictor.weights == MODEL_WEIGHTS

    @pytest.mark.unit
    @pytest.mark.slow
    def test_predictor_fit(self, predictor, sample_data):
        """测试预测器拟合"""
        feature_cols = ["feature_1", "feature_2"]

        predictor.fit(sample_data, feature_cols)

        assert predictor.is_trained is True
        assert len(predictor.stacking) == 5
        assert len(predictor.hmm_models) == 5
        assert len(predictor.bsts_models) == 5
        assert len(predictor.evm_models) == 5
        assert predictor.copula is not None
        assert predictor.feature_cols == feature_cols

    @pytest.mark.unit
    @pytest.mark.slow
    def test_predictor_predict(self, predictor, sample_data):
        """测试预测器预测"""
        feature_cols = ["feature_1", "feature_2"]
        predictor.fit(sample_data, feature_cols)

        features = np.array([0.5, -0.5])
        recent_data = {
            "wan": np.array([1, 2, 3]),
            "qian": np.array([2, 3, 4]),
            "bai": np.array([3, 4, 5]),
            "shi": np.array([4, 5, 6]),
            "ge": np.array([5, 6, 7]),
        }

        result = predictor.predict(features, recent_data, top_k=5)

        assert len(result) == 5  # 5个位置
        for pos in POSITIONS:
            assert pos in result
            assert "top_k" in result[pos]
            assert "probabilities" in result[pos]
            assert len(result[pos]["top_k"]) == 5
            assert len(result[pos]["probabilities"]) == 5

    @pytest.mark.unit
    def test_predictor_predict_untrained(self, predictor):
        """测试未训练预测器预测"""
        features = np.array([0.5, -0.5])

        result = predictor.predict(features, top_k=5)

        assert len(result) == 5
        for pos in POSITIONS:
            assert pos in result
            assert len(result[pos]["top_k"]) == 5
            # 未训练时应返回均匀分布
            assert np.allclose(result[pos]["probabilities"], [0.1] * 5)

    @pytest.mark.unit
    def test_predictor_save_and_load_models(self, predictor, sample_data, temp_directory):
        """测试模型保存和加载"""
        # 使用临时目录
        predictor.MODELS_DIR = temp_directory

        feature_cols = ["feature_1", "feature_2"]
        predictor.fit(sample_data, feature_cols)

        # 保存模型
        predictor.save_models()

        # 创建新预测器并加载
        new_predictor = PL5Predictor()
        new_predictor.MODELS_DIR = temp_directory
        success = new_predictor.load_models()

        assert success is True
        assert new_predictor.is_trained is True
        assert new_predictor.feature_cols == feature_cols

    @pytest.mark.unit
    def test_predictor_load_nonexistent_models(self, predictor, temp_directory):
        """测试加载不存在的模型"""
        predictor.MODELS_DIR = temp_directory
        success = predictor.load_models()
        assert success is False


# ═══════════════════════════════════════════════════════════════
# 边界条件测试
# ═══════════════════════════════════════════════════════════════


class TestPredictorEdgeCases:
    """测试预测器边界条件"""

    @pytest.mark.unit
    def test_predict_with_empty_features(self):
        """测试空特征预测"""
        predictor = PL5Predictor()
        predictor.is_trained = True

        # 模拟训练后的状态
        for pos in POSITIONS:
            predictor.hmm_models[pos] = HMMModel()
            predictor.bsts_models[pos] = BSTSModel()
            predictor.evm_models[pos] = ExtremeValueModel()

        features = np.array([])
        result = predictor.predict(features, top_k=3)

        assert len(result) == 5

    @pytest.mark.unit
    def test_predict_with_single_digit_sequence(self):
        """测试单数字序列预测"""
        hmm = HMMModel()
        sequence = np.array([5])

        hmm.fit(sequence)
        prediction = hmm.predict(sequence)

        assert len(prediction) == 10
        assert np.isclose(prediction.sum(), 1.0)

    @pytest.mark.unit
    def test_predict_with_all_same_digits(self):
        """测试全相同数字序列"""
        hmm = HMMModel()
        sequence = np.array([5] * 100)

        hmm.fit(sequence)
        prediction = hmm.predict(sequence)

        assert len(prediction) == 10
        # 应该强烈倾向于继续预测5
        assert prediction[5] > prediction[0]

    @pytest.mark.unit
    def test_safe_proba_with_nan(self):
        """测试包含NaN的概率数组"""
        proba = np.array([0.1, np.nan, 0.3, 0.4])
        result = _safe_proba(proba, n_classes=10)

        assert len(result) == 10
        # NaN应该被处理为0
        assert result[1] == 0
