"""
黄金分割-波动率范围移动识别集成模块测试

验证 GoldenRatioVolatilityModule 的核心能力：
1. 特征生成（500 列集成特征）
2. 信号识别（移动类型/范围状态）
3. 报告生成
4. 边界条件与一致性
5. 与特征工程的集成
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

logging.disable(logging.CRITICAL)

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.features.golden_ratio_volatility import (
    GOLDEN_RATIO_LEVELS,
    DEFAULT_WINDOWS,
    DEFAULT_POSITIONS,
    GoldenRatioVolatilityConfig,
    GoldenRatioVolatilityModule,
    RangeMovementType,
    RangeMovementSignal,
    add_golden_ratio_volatility_features,
    get_grvr_module,
)


# ═══════════════════════════════════════════════════════════════
# 测试夹具
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def rng():
    return np.random.default_rng(seed=42)


@pytest.fixture
def sample_df(rng):
    """5 位置 × 50 行的样本数据"""
    n = 50
    return pd.DataFrame({
        pos: rng.integers(0, 10, n)
        for pos in DEFAULT_POSITIONS
    })


@pytest.fixture
def breakout_df():
    """构造向上突破场景：前期低位震荡，末尾突破上行"""
    n = 30
    data = {pos: list(np.random.default_rng(0).integers(0, 3, n - 5)) + [8, 9, 8, 9, 8]
            for pos in DEFAULT_POSITIONS}
    return pd.DataFrame(data)


@pytest.fixture
def consolidation_df():
    """构造整理场景：在中轴附近震荡"""
    n = 30
    data = {pos: [4, 5, 4, 5, 6, 4, 5, 5, 4, 5] * 3
            for pos in DEFAULT_POSITIONS}
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════
# 1. 模块基础与配置测试
# ═══════════════════════════════════════════════════════════════

class TestModuleBasics:
    """模块基础功能测试"""

    def test_golden_ratio_levels_defined(self):
        """黄金分割位定义完整"""
        assert GOLDEN_RATIO_LEVELS['extreme_support'] == 0.236
        assert GOLDEN_RATIO_LEVELS['deep_support'] == 0.382
        assert GOLDEN_RATIO_LEVELS['pivot'] == 0.5
        assert GOLDEN_RATIO_LEVELS['golden_resistance'] == 0.618
        assert GOLDEN_RATIO_LEVELS['extension'] == 0.786

    def test_default_windows(self):
        """默认窗口包含原 fibonacci 窗口"""
        assert 5 in DEFAULT_WINDOWS
        assert 8 in DEFAULT_WINDOWS
        assert 13 in DEFAULT_WINDOWS

    def test_module_instantiation(self):
        """模块实例化"""
        module = GoldenRatioVolatilityModule()
        assert module.config is not None
        assert tuple(module.windows) == DEFAULT_WINDOWS
        assert tuple(module.positions) == DEFAULT_POSITIONS

    def test_custom_config(self):
        """自定义配置"""
        cfg = GoldenRatioVolatilityConfig(
            windows=(3, 7),
            positions=('wan', 'qian'),
            consolidation_band=0.15,
        )
        module = GoldenRatioVolatilityModule(config=cfg)
        assert tuple(module.windows) == (3, 7)
        assert tuple(module.positions) == ('wan', 'qian')
        assert module.config.consolidation_band == 0.15

    def test_singleton_factory(self):
        """单例工厂"""
        m1 = get_grvr_module()
        m2 = get_grvr_module()
        assert m1 is m2

    def test_convenience_function(self, sample_df):
        """便捷函数"""
        result = add_golden_ratio_volatility_features(sample_df)
        assert len(result.columns) > len(sample_df.columns)


# ═══════════════════════════════════════════════════════════════
# 2. 特征生成测试
# ═══════════════════════════════════════════════════════════════

class TestFeatureGeneration:
    """特征生成测试"""

    def test_transform_adds_features(self, sample_df):
        """transform 添加新特征列"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(sample_df)
        new_cols = [c for c in result.columns if c not in sample_df.columns]
        # 5 位置 × 4 窗口 × 25 特征 = 500
        assert len(new_cols) == 500

    def test_feature_naming_convention(self, sample_df):
        """特征命名规范：{pos}_grv_{window}_{suffix}"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(sample_df)
        # 检查 wan 位置 window=5 的特征前缀
        expected_prefix = 'wan_grv_5_'
        grv_cols = [c for c in result.columns if c.startswith(expected_prefix)]
        assert len(grv_cols) > 0

    def test_range_features_present(self, sample_df):
        """范围基础特征存在"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(sample_df)
        assert 'wan_grv_5_range_low' in result.columns
        assert 'wan_grv_5_range_high' in result.columns
        assert 'wan_grv_5_range_width' in result.columns
        assert 'wan_grv_5_prev_range_width' in result.columns

    def test_normalized_position_in_range(self, sample_df):
        """归一化位置在 [0, 1]"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(sample_df)
        for col in [c for c in result.columns if c.endswith('_norm_pos')]:
            vals = result[col].dropna()
            assert vals.min() >= 0.0, f"{col} min={vals.min()}"
            assert vals.max() <= 1.0, f"{col} max={vals.max()}"

    def test_distance_features_for_all_levels(self, sample_df):
        """5 个黄金位的距离特征全部存在"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(sample_df)
        for level_name in GOLDEN_RATIO_LEVELS.keys():
            col = f'wan_grv_5_dist_{level_name}'
            assert col in result.columns, f"缺少距离列: {col}"

    def test_one_hot_near_level_sums_to_one(self, sample_df):
        """is_near one-hot 每行和为 1"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(sample_df)
        is_near_cols = [c for c in result.columns if c.startswith('wan_grv_5_is_near_')]
        assert len(is_near_cols) == 5
        row_sums = result[is_near_cols].sum(axis=1)
        unique_sums = row_sums.unique()
        assert all(s == 1 for s in unique_sums), f"one-hot 行和应为 1，实际: {unique_sums}"

    def test_one_hot_movement_sums_to_one(self, sample_df):
        """movement one-hot 每行和为 1"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(sample_df)
        movement_cols = [c for c in result.columns if c.startswith('wan_grv_5_movement_')]
        assert len(movement_cols) == 6  # 6 种移动类型
        row_sums = result[movement_cols].sum(axis=1)
        unique_sums = row_sums.unique()
        assert all(s == 1 for s in unique_sums), f"movement one-hot 行和应为 1，实际: {unique_sums}"

    def test_one_hot_regime_sums_to_one(self, sample_df):
        """regime one-hot 每行和为 1"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(sample_df)
        regime_cols = [c for c in result.columns if c.startswith('wan_grv_5_regime_')]
        assert len(regime_cols) == 3  # expansion/contraction/stable
        row_sums = result[regime_cols].sum(axis=1)
        unique_sums = row_sums.unique()
        assert all(s == 1 for s in unique_sums), f"regime one-hot 行和应为 1，实际: {unique_sums}"

    def test_signal_strength_in_range(self, sample_df):
        """信号强度在 [0, 1]"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(sample_df)
        for col in [c for c in result.columns if c.endswith('_signal_strength')]:
            vals = result[col].dropna()
            assert vals.min() >= 0.0
            assert vals.max() <= 1.0

    def test_get_feature_columns(self):
        """get_feature_columns 返回完整列名列表"""
        module = GoldenRatioVolatilityModule()
        cols = module.get_feature_columns()
        assert len(cols) == 500  # 5 × 4 × 25
        # 检查命名一致性
        assert all(c.startswith(('wan_', 'qian_', 'bai_', 'shi_', 'ge_')) for c in cols)

    def test_transform_preserves_original_columns(self, sample_df):
        """transform 不修改原始列"""
        module = GoldenRatioVolatilityModule()
        original_cols = list(sample_df.columns)
        result = module.transform(sample_df)
        for col in original_cols:
            assert col in result.columns
        # 原始 DataFrame 不应被修改
        assert list(sample_df.columns) == original_cols


# ═══════════════════════════════════════════════════════════════
# 3. 信号识别测试
# ═══════════════════════════════════════════════════════════════

class TestSignalIdentification:
    """信号识别测试"""

    def test_identify_signals_returns_list(self, sample_df):
        """identify_signals 返回信号列表"""
        module = GoldenRatioVolatilityModule()
        signals = module.identify_signals(sample_df)
        assert isinstance(signals, list)
        assert len(signals) == 20  # 5 位置 × 4 窗口

    def test_signal_structure(self, sample_df):
        """信号结构完整"""
        module = GoldenRatioVolatilityModule()
        signals = module.identify_signals(sample_df)
        assert len(signals) > 0
        sig = signals[0]
        assert isinstance(sig, RangeMovementSignal)
        assert sig.position in DEFAULT_POSITIONS
        assert sig.window in DEFAULT_WINDOWS
        assert 0.0 <= sig.normalized_position <= 1.0
        assert isinstance(sig.movement_type, RangeMovementType)
        assert sig.range_regime in ('expansion', 'contraction', 'stable')
        assert sig.nearest_level_name in GOLDEN_RATIO_LEVELS.keys()

    def test_signal_to_dict(self, sample_df):
        """信号序列化"""
        module = GoldenRatioVolatilityModule()
        signals = module.identify_signals(sample_df)
        d = signals[0].to_dict()
        assert isinstance(d, dict)
        assert 'position' in d
        assert 'movement_type' in d
        assert 'range_regime' in d

    def test_breakout_up_detection(self, breakout_df):
        """向上突破检测"""
        module = GoldenRatioVolatilityModule()
        signals = module.identify_signals(breakout_df)
        # 应至少有一个信号检测到突破
        breakout_signals = [s for s in signals if s.movement_type == RangeMovementType.BREAKOUT_UP]
        assert len(breakout_signals) > 0, "未检测到向上突破信号"

    def test_consolidation_detection(self, consolidation_df):
        """整理模式检测"""
        module = GoldenRatioVolatilityModule()
        signals = module.identify_signals(consolidation_df)
        # 应至少有一个信号检测到整理
        consolidation_signals = [s for s in signals if s.movement_type == RangeMovementType.CONSOLIDATION]
        assert len(consolidation_signals) > 0, "未检测到整理信号"

    def test_movement_type_enum_complete(self):
        """移动类型枚举完整"""
        types = {mt.value for mt in RangeMovementType}
        assert types == {
            'consolidation', 'reversal_up', 'reversal_down',
            'breakout_up', 'breakout_down', 'neutral'
        }


# ═══════════════════════════════════════════════════════════════
# 4. 报告生成测试
# ═══════════════════════════════════════════════════════════════

class TestReportGeneration:
    """报告生成测试"""

    def test_generate_report(self, sample_df):
        """生成可读报告"""
        module = GoldenRatioVolatilityModule()
        report = module.generate_report(sample_df)
        assert isinstance(report, str)
        assert '黄金分割' in report or 'GRVR' in report
        assert '位置' in report

    def test_report_with_empty_data(self):
        """空数据报告"""
        module = GoldenRatioVolatilityModule()
        report = module.generate_report(pd.DataFrame())
        assert isinstance(report, str)
        assert len(report) > 0

    def test_report_contains_movement_summary(self, sample_df):
        """报告包含移动类型汇总"""
        module = GoldenRatioVolatilityModule()
        report = module.generate_report(sample_df)
        assert '移动类型分布' in report
        assert '范围状态分布' in report


# ═══════════════════════════════════════════════════════════════
# 5. 边界条件测试
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件测试"""

    def test_empty_dataframe(self):
        """空 DataFrame"""
        module = GoldenRatioVolatilityModule()
        result = module.transform(pd.DataFrame())
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_single_row(self):
        """单行数据"""
        module = GoldenRatioVolatilityModule()
        df = pd.DataFrame({'wan': [5], 'qian': [4], 'bai': [3], 'shi': [2], 'ge': [1]})
        result = module.transform(df)
        assert len(result) == 1

    def test_insufficient_samples(self):
        """样本数不足（min_samples=3）"""
        cfg = GoldenRatioVolatilityConfig(min_samples=10)
        module = GoldenRatioVolatilityModule(config=cfg)
        df = pd.DataFrame({
            'wan': [1, 2], 'qian': [3, 4], 'bai': [5, 6], 'shi': [7, 8], 'ge': [9, 0]
        })
        result = module.transform(df)
        # 样本不足时不生成特征，但返回原数据
        assert list(result.columns) == list(df.columns)

    def test_missing_position_columns(self):
        """缺少位置列"""
        module = GoldenRatioVolatilityModule()
        df = pd.DataFrame({'other': [1, 2, 3]})
        result = module.transform(df)
        # 无位置列时不添加特征
        assert list(result.columns) == ['other']

    def test_partial_positions(self):
        """仅部分位置存在"""
        module = GoldenRatioVolatilityModule()
        df = pd.DataFrame({'wan': [1, 2, 3, 4, 5], 'qian': [5, 4, 3, 2, 1]})
        result = module.transform(df)
        # 仅为存在的位置生成特征
        wan_cols = [c for c in result.columns if c.startswith('wan_grv_')]
        qian_cols = [c for c in result.columns if c.startswith('qian_grv_')]
        bai_cols = [c for c in result.columns if c.startswith('bai_grv_')]
        assert len(wan_cols) > 0
        assert len(qian_cols) > 0
        assert len(bai_cols) == 0  # bai 列不存在

    def test_constant_series(self):
        """常数序列（range_width=0）"""
        module = GoldenRatioVolatilityModule()
        df = pd.DataFrame({
            'wan': [5] * 20, 'qian': [3] * 20, 'bai': [7] * 20,
            'shi': [2] * 20, 'ge': [9] * 20
        })
        result = module.transform(df)
        # 常数序列不应崩溃，归一化位置应为 0.5
        norm_vals = result['wan_grv_5_norm_pos'].dropna()
        assert all(abs(v - 0.5) < 1e-6 for v in norm_vals)

    def test_with_nan_values(self):
        """含 NaN 值"""
        module = GoldenRatioVolatilityModule()
        df = pd.DataFrame({
            'wan': [1, np.nan, 3, 4, 5, 6, 7, 8, 9, 0],
            'qian': [5, 4, np.nan, 2, 1, 0, 9, 8, 7, 6],
            'bai': [3, 2, 1, np.nan, 9, 8, 7, 6, 5, 4],
            'shi': [7, 8, 9, 0, np.nan, 4, 3, 2, 1, 0],
            'ge': [9, 8, 7, 6, 5, np.nan, 3, 2, 1, 0],
        })
        result = module.transform(df)
        # 不应崩溃
        assert len(result) == 10


# ═══════════════════════════════════════════════════════════════
# 6. 与特征工程集成测试
# ═══════════════════════════════════════════════════════════════

class TestEngineerIntegration:
    """与 FeatureEngineer 的集成测试"""

    def test_engineer_v10_has_grv_method(self):
        """FeatureEngineerV10 集成了新模块"""
        from src.core.features.engineer_v10 import FeatureEngineerV10, FeatureConfig
        # 默认配置应包含 golden_ratio_volatility 而非 fibonacci
        assert 'golden_ratio_volatility' in FeatureConfig.DEFAULT_CONFIG
        assert 'fibonacci' not in FeatureConfig.DEFAULT_CONFIG
        # 应有 _add_golden_ratio_volatility_features 方法
        assert hasattr(FeatureEngineerV10, '_add_golden_ratio_volatility_features')
        # 不应有 _add_fibonacci_features 方法
        assert not hasattr(FeatureEngineerV10, '_add_fibonacci_features')

    def test_engineer_v9_has_grv_method(self):
        """FeatureEngineerV9（旧版）也集成了新模块"""
        from src.core.features.engineer import FeatureEngineerV9, FeatureConfig
        assert 'golden_ratio_volatility' in FeatureConfig.DEFAULT_CONFIG
        assert 'fibonacci' not in FeatureConfig.DEFAULT_CONFIG
        assert hasattr(FeatureEngineerV9, '_add_golden_ratio_volatility_features')
        assert not hasattr(FeatureEngineerV9, '_add_fibonacci_features')

    def test_engineer_v10_dispatch_uses_grv(self, sample_df):
        """V10 调度表使用新模块"""
        from src.core.features.engineer_v10 import FeatureEngineerV10
        engineer = FeatureEngineerV10(use_config=False, enable_parallel=False)
        result = engineer._compute_feature_group(sample_df, 'golden_ratio_volatility')
        # 应生成 grv_ 前缀的特征
        grv_cols = [c for c in result.columns if '_grv_' in c]
        assert len(grv_cols) > 0

    def test_engineer_v9_dispatch_uses_grv(self, sample_df):
        """V9 调度表使用新模块"""
        from src.core.features.engineer import FeatureEngineerV9
        engineer = FeatureEngineerV9(use_config=False, enable_parallel=False)
        result = engineer._compute_feature_group(sample_df, 'golden_ratio_volatility')
        grv_cols = [c for c in result.columns if '_grv_' in c]
        assert len(grv_cols) > 0

    def test_no_fibonacci_dispatch(self, sample_df):
        """调度表不再包含 fibonacci"""
        from src.core.features.engineer_v10 import FeatureEngineerV10
        engineer = FeatureEngineerV10(use_config=False, enable_parallel=False)
        # fibonacci 不应在 dispatch 中
        result = engineer._compute_feature_group(sample_df, 'fibonacci')
        # 不识别的 group 应返回原始 df（无新列）
        assert list(result.columns) == list(sample_df.columns)


# ═══════════════════════════════════════════════════════════════
# 7. 配置一致性测试
# ═══════════════════════════════════════════════════════════════

class TestConfigConsistency:
    """配置一致性测试"""

    def test_yaml_config_uses_grv(self):
        """YAML 配置使用 golden_ratio_volatility"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML 未安装，跳过 YAML 配置验证")
        yaml_path = PROJECT_ROOT / 'config' / 'model_config.yaml'
        if not yaml_path.exists():
            pytest.skip("YAML 配置文件不存在")
        with open(yaml_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        feng = cfg.get('feature_engineering', {})
        groups = feng.get('feature_groups', {})
        assert 'golden_ratio_volatility' in groups
        assert 'fibonacci' not in groups

    def test_multi_feature_fusion_uses_grv(self):
        """multi_feature_fusion 使用新模块"""
        from src.core.models.multi_feature_fusion import DynamicFeatureSelector
        selector = DynamicFeatureSelector()
        assert 'golden_ratio_volatility' in selector.base_feature_groups
        assert 'fibonacci' not in selector.base_feature_groups


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
