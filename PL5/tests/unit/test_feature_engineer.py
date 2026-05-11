"""
特征工程模块单元测试
测试FeatureEngineer、FeatureCacheManager、FeatureDriftDetector等核心组件
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil

# 导入被测模块
from src.core.features.engineer import (
    FeatureEngineerV9,
    FeatureCacheManager,
    FeatureDriftDetector,
    FeatureScaler,
    FeatureImportanceAnalyzer,
    FeatureConfig,
    _compute_data_hash,
    _vectorized_rolling_skew,
    _vectorized_rolling_kurtosis,
    POSITIONS,
)

# ═══════════════════════════════════════════════════════════════
# 工具函数测试
# ═══════════════════════════════════════════════════════════════


class TestUtilityFunctions:
    """测试工具函数"""

    @pytest.mark.unit
    def test_compute_data_hash(self, sample_pl5_data):
        """测试数据哈希计算"""
        df = sample_pl5_data
        hash1 = _compute_data_hash(df, ["period"])
        hash2 = _compute_data_hash(df, ["period"])

        # 相同数据应产生相同哈希
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5哈希长度

        # 不同数据应产生不同哈希
        df_modified = df.copy()
        df_modified.iloc[0, 0] = "9999999"
        hash3 = _compute_data_hash(df_modified, ["period"])
        assert hash1 != hash3

    @pytest.mark.unit
    def test_vectorized_rolling_skew(self):
        """测试向量化滚动偏度"""
        series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = _vectorized_rolling_skew(series, window=5)

        assert isinstance(result, pd.Series)
        assert len(result) == len(series)
        # 前4个应该是NaN（因为窗口不够）
        assert result.iloc[:4].isna().all()

    @pytest.mark.unit
    def test_vectorized_rolling_kurtosis(self):
        """测试向量化滚动峰度"""
        series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = _vectorized_rolling_kurtosis(series, window=5)

        assert isinstance(result, pd.Series)
        assert len(result) == len(series)


# ═══════════════════════════════════════════════════════════════
# FeatureCacheManager 测试
# ═══════════════════════════════════════════════════════════════


class TestFeatureCacheManager:
    """测试特征缓存管理器"""

    @pytest.fixture
    def cache_manager(self):
        return FeatureCacheManager(max_size=5)

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({"period": ["2026001", "2026002", "2026003"], "wan": [1, 2, 3], "qian": [2, 3, 4]})

    @pytest.mark.unit
    def test_cache_initialization(self, cache_manager):
        """测试缓存管理器初始化"""
        assert cache_manager._max_size == 5
        assert len(cache_manager) == 0
        assert cache_manager.stats["hits"] == 0
        assert cache_manager.stats["misses"] == 0

    @pytest.mark.unit
    def test_cache_put_and_get(self, cache_manager, sample_df):
        """测试缓存存取"""
        key = cache_manager.get_key(sample_df)

        # 存入缓存
        cache_manager.put(key, sample_df)
        assert len(cache_manager) == 1

        # 获取缓存
        cached = cache_manager.get(key)
        assert cached is not None
        pd.testing.assert_frame_equal(cached, sample_df)

    @pytest.mark.unit
    def test_cache_miss(self, cache_manager, sample_df):
        """测试缓存未命中"""
        result = cache_manager.get("nonexistent_key")
        assert result is None
        assert cache_manager.stats["misses"] == 1

    @pytest.mark.unit
    def test_cache_hit_stats(self, cache_manager, sample_df):
        """测试缓存命中统计"""
        key = cache_manager.get_key(sample_df)
        cache_manager.put(key, sample_df)

        # 多次获取
        cache_manager.get(key)
        cache_manager.get(key)

        assert cache_manager.stats["hits"] == 2
        assert cache_manager.stats["hit_rate"] == 1.0

    @pytest.mark.unit
    def test_cache_lru_eviction(self, cache_manager):
        """测试LRU淘汰策略"""
        # 存入超过最大容量的数据
        for i in range(7):
            df = pd.DataFrame({"period": [f"2026{i:03d}"], "value": [i]})
            key = f"key_{i}"
            cache_manager.put(key, df)

        # 应该只保留最近5个
        assert len(cache_manager) == 5

    @pytest.mark.unit
    def test_cache_clear(self, cache_manager, sample_df):
        """测试清空缓存"""
        key = cache_manager.get_key(sample_df)
        cache_manager.put(key, sample_df)

        cache_manager.clear()
        assert len(cache_manager) == 0

    @pytest.mark.unit
    def test_cache_clear_by_prefix(self, cache_manager):
        """测试按前缀清理缓存"""
        cache_manager.put("prefix_key1", pd.DataFrame())
        cache_manager.put("prefix_key2", pd.DataFrame())
        cache_manager.put("other_key", pd.DataFrame())

        cache_manager.clear_by_prefix("prefix")

        assert len(cache_manager) == 1


# ═══════════════════════════════════════════════════════════════
# FeatureDriftDetector 测试
# ═══════════════════════════════════════════════════════════════


class TestFeatureDriftDetector:
    """测试特征漂移检测器"""

    @pytest.fixture
    def drift_detector(self):
        return FeatureDriftDetector(psi_threshold=0.2, ks_threshold=0.05)

    @pytest.fixture
    def training_data(self):
        """创建训练数据"""
        np.random.seed(42)
        return pd.DataFrame(
            {"feature_1": np.random.normal(0, 1, 100), "feature_2": np.random.normal(5, 2, 100), "period": range(100)}
        )

    @pytest.mark.unit
    def test_drift_detector_initialization(self, drift_detector):
        """测试漂移检测器初始化"""
        assert drift_detector.psi_threshold == 0.2
        assert drift_detector.ks_threshold == 0.05
        assert len(drift_detector.training_stats) == 0

    @pytest.mark.unit
    def test_fit_records_stats(self, drift_detector, training_data):
        """测试拟合记录统计量"""
        drift_detector.fit(training_data, ["feature_1", "feature_2"])

        assert "feature_1" in drift_detector.training_stats
        assert "feature_2" in drift_detector.training_stats

        stats = drift_detector.training_stats["feature_1"]
        assert "mean" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats

    @pytest.mark.unit
    def test_detect_no_drift(self, drift_detector, training_data):
        """测试无漂移检测"""
        # 使用相同数据拟合和检测
        drift_detector.fit(training_data, ["feature_1"])
        warnings = drift_detector.detect(training_data, ["feature_1"])

        # 相同数据应该无漂移
        assert len(warnings) == 0

    @pytest.mark.unit
    def test_detect_with_drift(self, drift_detector, training_data):
        """测试有漂移检测"""
        # 拟合原始数据
        drift_detector.fit(training_data, ["feature_1"])

        # 创建漂移数据（均值偏移）
        drift_data = training_data.copy()
        drift_data["feature_1"] = drift_data["feature_1"] + 10

        warnings = drift_detector.detect(drift_data, ["feature_1"])

        # 应该有漂移警告
        assert len(warnings) > 0

    @pytest.mark.unit
    def test_get_drift_report_no_warnings(self, drift_detector):
        """测试无警告时的漂移报告"""
        report = drift_detector.get_drift_report()
        assert report == "无特征漂移"

    @pytest.mark.unit
    def test_get_drift_report_with_warnings(self, drift_detector, training_data):
        """测试有警告时的漂移报告"""
        drift_detector.fit(training_data, ["feature_1"])

        drift_data = training_data.copy()
        drift_data["feature_1"] = drift_data["feature_1"] + 10
        drift_detector.detect(drift_data, ["feature_1"])

        report = drift_detector.get_drift_report()
        assert "特征漂移报告" in report


# ═══════════════════════════════════════════════════════════════
# FeatureScaler 测试
# ═══════════════════════════════════════════════════════════════


class TestFeatureScaler:
    """测试特征标准化器"""

    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        return pd.DataFrame(
            {
                "feature_1": np.random.normal(10, 2, 100),
                "feature_2": np.random.normal(100, 20, 100),
                "period": range(100),
            }
        )

    @pytest.mark.unit
    def test_scaler_initialization(self):
        """测试标准化器初始化"""
        scaler = FeatureScaler(method="standard")
        assert scaler.method == "standard"
        assert scaler._fitted is False

    @pytest.mark.unit
    def test_scaler_invalid_method(self):
        """测试无效标准化方法"""
        with pytest.raises(ValueError):
            FeatureScaler(method="invalid")

    @pytest.mark.unit
    def test_scaler_fit_transform_standard(self, sample_data):
        """测试标准标准化"""
        scaler = FeatureScaler(method="standard")
        result = scaler.fit_transform(sample_data)

        # 标准化后均值应接近0，标准差接近1
        assert abs(result["feature_1"].mean()) < 0.1
        assert abs(result["feature_1"].std() - 1) < 0.1

    @pytest.mark.unit
    def test_scaler_fit_transform_minmax(self, sample_data):
        """测试MinMax标准化"""
        scaler = FeatureScaler(method="minmax")
        result = scaler.fit_transform(sample_data)

        # MinMax后值应在0-1之间
        assert result["feature_1"].min() >= 0
        assert result["feature_1"].max() <= 1

    @pytest.mark.unit
    def test_scaler_none_method(self, sample_data):
        """测试无标准化"""
        scaler = FeatureScaler(method="none")
        result = scaler.fit_transform(sample_data)

        # 数据应保持不变
        pd.testing.assert_frame_equal(result, sample_data)


# ═══════════════════════════════════════════════════════════════
# FeatureConfig 测试
# ═══════════════════════════════════════════════════════════════


class TestFeatureConfig:
    """测试特征配置"""

    @pytest.fixture
    def temp_dir(self):
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.mark.unit
    def test_config_default_values(self, temp_dir):
        """测试默认配置值"""
        config_path = temp_dir / "feature_config.json"
        config = FeatureConfig(config_path=config_path)

        assert "fibonacci" in config.config
        assert "markov" in config.config
        assert "fourier" in config.config

    @pytest.mark.unit
    def test_get_enabled_features(self, temp_dir):
        """测试获取启用的特征"""
        config_path = temp_dir / "feature_config.json"
        config = FeatureConfig(config_path=config_path)

        enabled = config.get_enabled_features()
        assert isinstance(enabled, list)
        assert len(enabled) > 0

    @pytest.mark.unit
    def test_save_and_load_config(self, temp_dir):
        """测试保存和加载配置"""
        config_path = temp_dir / "feature_config.json"
        config = FeatureConfig(config_path=config_path)

        # 修改配置
        config.update_config("fibonacci", enabled=False)

        # 重新加载
        config2 = FeatureConfig(config_path=config_path)
        assert config2.config["fibonacci"]["enabled"] is False


# ═══════════════════════════════════════════════════════════════
# FeatureImportanceAnalyzer 测试
# ═══════════════════════════════════════════════════════════════


class TestFeatureImportanceAnalyzer:
    """测试特征重要性分析器"""

    @pytest.fixture
    def analyzer(self):
        return FeatureImportanceAnalyzer()

    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        df = pd.DataFrame(
            {
                "feature_1": np.random.randn(100),
                "feature_2": np.random.randn(100),
                "feature_3": np.random.randn(100),
                "period": range(100),
            }
        )
        return df

    @pytest.mark.unit
    def test_analyzer_initialization(self, analyzer):
        """测试分析器初始化"""
        assert len(analyzer.importance_scores) == 0
        assert len(analyzer.feature_ranking) == 0

    @pytest.mark.unit
    def test_calculate_importance(self, analyzer, sample_data):
        """测试计算特征重要性"""
        y = pd.Series(np.random.randint(0, 3, 100))

        importance = analyzer.calculate_importance(sample_data, y, method="random_forest")

        assert len(importance) > 0
        assert all(isinstance(v, (int, float)) for v in importance.values())

    @pytest.mark.unit
    def test_select_top_features(self, analyzer, sample_data):
        """测试选择Top特征"""
        y = pd.Series(np.random.randint(0, 3, 100))
        analyzer.calculate_importance(sample_data, y)

        selected = analyzer.select_top_features(n_features=2)
        assert len(selected) <= 2


# ═══════════════════════════════════════════════════════════════
# FeatureEngineerV9 测试
# ═══════════════════════════════════════════════════════════════


class TestFeatureEngineerV9:
    """测试特征工程器V9"""

    @pytest.fixture
    def engineer(self):
        return FeatureEngineerV9(use_config=False, enable_parallel=False, cache_max_size=10)

    @pytest.fixture
    def sample_pl5_data(self):
        """创建足够的PL5数据用于特征提取"""
        np.random.seed(42)
        n = 100
        return pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(n)],
                "wan": np.random.randint(0, 10, n),
                "qian": np.random.randint(0, 10, n),
                "bai": np.random.randint(0, 10, n),
                "shi": np.random.randint(0, 10, n),
                "ge": np.random.randint(0, 10, n),
            }
        )

    @pytest.mark.unit
    def test_engineer_initialization(self, engineer):
        """测试特征工程器初始化"""
        assert engineer.config is None
        assert engineer.enable_parallel is False
        assert engineer.cache is not None
        assert engineer.scaler is not None
        assert engineer.drift_detector is not None

    @pytest.mark.unit
    def test_add_fibonacci_features(self, engineer, sample_pl5_data):
        """测试添加黄金分割特征"""
        result = engineer._add_fibonacci_features(sample_pl5_data)

        # 检查新特征列
        assert any("fib_mean" in col for col in result.columns)
        assert any("fib_std" in col for col in result.columns)
        assert len(result.columns) > len(sample_pl5_data.columns)

    @pytest.mark.unit
    def test_add_markov_features(self, engineer, sample_pl5_data):
        """测试添加马尔可夫特征"""
        result = engineer._add_markov_features(sample_pl5_data)

        assert any("markov" in col for col in result.columns)

    @pytest.mark.unit
    def test_add_pattern_features(self, engineer, sample_pl5_data):
        """测试添加形态模式特征"""
        result = engineer._add_pattern_features(sample_pl5_data)

        pattern_cols = ["repeat_2", "increasing", "decreasing", "alternating", "repeat_3"]
        for col_suffix in pattern_cols:
            assert any(col_suffix in col for col in result.columns)

    @pytest.mark.unit
    def test_add_momentum_features(self, engineer, sample_pl5_data):
        """测试添加动量特征"""
        result = engineer._add_momentum_features(sample_pl5_data)

        assert any("momentum" in col for col in result.columns)

    @pytest.mark.unit
    def test_add_time_series_features(self, engineer, sample_pl5_data):
        """测试添加时间序列特征"""
        result = engineer._add_time_series_features(sample_pl5_data)

        # 检查各种时间序列特征
        assert any("_ma_" in col for col in result.columns)
        assert any("_ema_" in col for col in result.columns)
        assert any("_std_" in col for col in result.columns)

    @pytest.mark.unit
    def test_add_nonlinear_features(self, engineer, sample_pl5_data):
        """测试添加非线性特征"""
        result = engineer._add_nonlinear_features(sample_pl5_data)

        # 检查非线性变换特征
        assert any("_square" in col for col in result.columns)
        assert any("_cube" in col for col in result.columns)

    @pytest.mark.unit
    def test_extract_all_features(self, engineer, sample_pl5_data):
        """测试提取所有特征"""
        result = engineer.extract_all_features(
            sample_pl5_data, select_top=None, enable_scaler=False  # 不选择，保留所有特征
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result.columns) > len(sample_pl5_data.columns)
        assert len(result) == len(sample_pl5_data)

    @pytest.mark.unit
    def test_extract_features_with_cache(self, engineer, sample_pl5_data):
        """测试特征提取缓存"""
        # 第一次提取
        result1 = engineer.extract_all_features(sample_pl5_data, select_top=None, enable_scaler=False)

        # 第二次提取（应该命中缓存）
        result2 = engineer.extract_all_features(sample_pl5_data, select_top=None, enable_scaler=False)

        pd.testing.assert_frame_equal(result1, result2)
        assert engineer.cache.stats["hits"] >= 1

    @pytest.mark.unit
    def test_extract_features_with_scaler(self, engineer, sample_pl5_data):
        """测试带标准化的特征提取"""
        result = engineer.extract_all_features(sample_pl5_data, select_top=None, enable_scaler=True)

        assert isinstance(result, pd.DataFrame)


# ═══════════════════════════════════════════════════════════════
# 边界条件测试
# ═══════════════════════════════════════════════════════════════


class TestFeatureEngineerEdgeCases:
    """测试特征工程边界条件"""

    @pytest.mark.unit
    def test_empty_dataframe(self):
        """测试空数据框"""
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        empty_df = pd.DataFrame()

        result = engineer._add_fibonacci_features(empty_df)
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.unit
    def test_single_row_dataframe(self):
        """测试单行数据框"""
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        single_df = pd.DataFrame({"period": ["2026001"], "wan": [5], "qian": [4], "bai": [3], "shi": [2], "ge": [1]})

        result = engineer._add_fibonacci_features(single_df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    @pytest.mark.unit
    def test_dataframe_with_missing_values(self):
        """测试包含缺失值的数据框"""
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        df = pd.DataFrame(
            {
                "period": ["2026001", "2026002", "2026003"],
                "wan": [5, np.nan, 3],
                "qian": [4, 3, np.nan],
                "bai": [3, 2, 1],
                "shi": [2, 1, 0],
                "ge": [1, 0, 9],
            }
        )

        result = engineer._add_time_series_features(df)
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.unit
    def test_all_same_values(self):
        """测试所有值相同的数据"""
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        df = pd.DataFrame(
            {
                "period": [f"2026{i:04d}" for i in range(20)],
                "wan": [5] * 20,
                "qian": [4] * 20,
                "bai": [3] * 20,
                "shi": [2] * 20,
                "ge": [1] * 20,
            }
        )

        result = engineer._add_statistical_features(df)
        assert isinstance(result, pd.DataFrame)
