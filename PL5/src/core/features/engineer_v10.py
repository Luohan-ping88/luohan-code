"""
特征工程模块 V10.0 - 重构优化版
主要优化：
1. RFE特征选择并行化（关键性能优化）
2. 多级缓存集成
3. 并行特征计算优化
4. 代码结构优化，降低耦合度
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.fft import fft
from scipy.stats import entropy as scipy_entropy
import warnings
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Callable
import json
import pickle
import hashlib
import time
from collections import OrderedDict
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectFromModel, VarianceThreshold, RFE
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler as SklearnRobustScaler

from .config import setup_logging, MODELS_DIR, PROCESSED_DATA_DIR
from src.core.config import ModelConfig, get_model_config
from src.core.monitoring.performance_monitor import track_performance
from src.core.cache import FeatureCacheManager, MultiLevelCache, get_global_cache
from src.core.utils.parallel import parallel_map, ParallelExecutor, get_optimal_n_jobs

logger = setup_logging(__name__)

POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']


# ═══════════════════════════════════════════════════════════════
# 向量化计算工具函数
# ═══════════════════════════════════════════════════════════════

def _vectorized_rolling_skew(series: pd.Series, window: int) -> pd.Series:
    """向量化rolling skew - 避免逐行apply"""
    if len(series) < window:
        return pd.Series(np.nan, index=series.index)
    rolled = series.rolling(window=window, min_periods=window)
    mean = rolled.mean()
    std = rolled.std()
    n = window
    m3 = ((series - mean) ** 3).rolling(window=window, min_periods=window).sum()
    with np.errstate(invalid='ignore', divide='ignore'):
        result = (m3 / n) / (std ** 3) if std is not None else pd.Series(np.nan, index=series.index)
        if isinstance(result, (int, float)):
            result = pd.Series(np.full(len(series), result), index=series.index)
    return result


def _vectorized_rolling_kurtosis(series: pd.Series, window: int) -> pd.Series:
    """向量化rolling kurtosis - 避免逐行apply"""
    if len(series) < window:
        return pd.Series(np.nan, index=series.index)
    rolled = series.rolling(window=window, min_periods=window)
    mean = rolled.mean()
    std = rolled.std()
    n = window
    m4 = ((series - mean) ** 4).rolling(window=window, min_periods=window).sum()
    m2_var = (std ** 2)
    with np.errstate(invalid='ignore', divide='ignore'):
        result = (m4 / n) / (m2_var ** 2) - 3
        if isinstance(result, (int, float)):
            result = pd.Series(np.full(len(series), result), index=series.index)
    return result


def _vectorized_rolling_polyfit_trend(series: pd.Series, window: int) -> pd.Series:
    """向量化rolling trend (polyfit slope)"""
    n = len(series)
    result = np.full(n, np.nan)
    x = np.arange(window, dtype=np.float64)
    x_mean = x.mean()
    x_ss = ((x - x_mean) ** 2).sum()
    if x_ss == 0:
        return pd.Series(result, index=series.index)
    for i in range(window - 1, n):
        y = series.iloc[i - window + 1:i + 1].values.astype(np.float64)
        y_mean = y.mean()
        result[i] = ((x - x_mean) * (y - y_mean)).sum() / x_ss
    return pd.Series(result, index=series.index)


def _compute_data_hash(df: pd.DataFrame, columns: Optional[List[str]] = None) -> str:
    """基于DataFrame内容计算hash用于缓存"""
    cols = columns or list(df.columns)
    hash_obj = hashlib.sha256()
    for col in cols:
        if col in df.columns:
            values = df[col].values.tobytes()
            hash_obj.update(values)
            hash_obj.update(str(len(df)).encode())
    return hash_obj.hexdigest()


# ═══════════════════════════════════════════════════════════════
# 并行RFE特征选择器
# ═══════════════════════════════════════════════════════════════

class ParallelRFESelector:
    """并行RFE特征选择器 - 关键性能优化"""
    
    def __init__(self, n_features: int = 50, step: int = 20, n_jobs: int = -1):
        self.n_features = n_features
        self.step = step
        self.n_jobs = get_optimal_n_jobs(n_jobs)
        self.selected_features_: List[str] = []
        self.ranking_: Dict[str, int] = {}
        
    def fit(self, X: pd.DataFrame, y: pd.Series, feature_cols: List[str]) -> 'ParallelRFESelector':
        """
        并行拟合RFE
        将特征分成多个组，每组独立进行RFE，然后合并结果
        """
        logger.info(f"并行RFE特征选择开始: n_features={self.n_features}, n_jobs={self.n_jobs}")
        start_time = time.time()
        
        X_features = X[feature_cols].fillna(0)
        
        # 如果特征数量不多，直接使用标准RFE
        if len(feature_cols) <= self.n_features * 2:
            model = RandomForestClassifier(
                n_estimators=30, max_depth=8, random_state=42, n_jobs=self.n_jobs
            )
            rfe = RFE(estimator=model, n_features_to_select=self.n_features, step=self.step)
            rfe.fit(X_features, y)
            self.selected_features_ = [feature_cols[i] for i in range(len(feature_cols)) if rfe.support_[i]]
            self.ranking_ = {feature_cols[i]: rfe.ranking_[i] for i in range(len(feature_cols))}
            logger.info(f"标准RFE完成: 选择 {len(self.selected_features_)} 个特征, 耗时: {time.time()-start_time:.2f}s")
            return self
        
        # 并行RFE策略：将特征分组，每组独立进行RFE
        n_groups = min(self.n_jobs, 5)  # 最多分5组
        group_size = len(feature_cols) // n_groups
        
        def rfe_on_group(group_idx: int) -> Tuple[int, List[str], Dict[str, int]]:
            """对单个组执行RFE"""
            start_idx = group_idx * group_size
            end_idx = start_idx + group_size if group_idx < n_groups - 1 else len(feature_cols)
            group_features = feature_cols[start_idx:end_idx]
            
            X_group = X[group_features].fillna(0)
            n_select = max(1, int(self.n_features / n_groups))
            
            model = RandomForestClassifier(
                n_estimators=20, max_depth=6, random_state=42 + group_idx, n_jobs=1
            )
            rfe = RFE(estimator=model, n_features_to_select=min(n_select, len(group_features)), step=max(1, self.step // 2))
            rfe.fit(X_group, y)
            
            selected = [group_features[i] for i in range(len(group_features)) if rfe.support_[i]]
            ranking = {group_features[i]: rfe.ranking_[i] for i in range(len(group_features))}
            
            return group_idx, selected, ranking
        
        # 并行执行各组的RFE
        results = parallel_map(rfe_on_group, range(n_groups), n_jobs=self.n_jobs, prefer='processes')
        
        # 合并结果
        all_selected = []
        all_rankings = {}
        for _, selected, ranking in sorted(results, key=lambda x: x[0]):
            all_selected.extend(selected)
            all_rankings.update(ranking)
        
        # 如果选择的特征过多，进行二次筛选
        if len(all_selected) > self.n_features:
            logger.info(f"二次筛选: 从 {len(all_selected)} 个特征中选择 top {self.n_features}")
            X_selected = X[all_selected].fillna(0)
            model = RandomForestClassifier(
                n_estimators=30, max_depth=8, random_state=42, n_jobs=self.n_jobs
            )
            model.fit(X_selected, y)
            importances = model.feature_importances_
            
            # 按重要性排序选择
            feature_importance = list(zip(all_selected, importances))
            feature_importance.sort(key=lambda x: x[1], reverse=True)
            self.selected_features_ = [f for f, _ in feature_importance[:self.n_features]]
        else:
            self.selected_features_ = all_selected
            
        self.ranking_ = all_rankings
        
        elapsed = time.time() - start_time
        logger.info(f"并行RFE完成: 选择 {len(self.selected_features_)} 个特征, 耗时: {elapsed:.2f}s")
        return self


# ═══════════════════════════════════════════════════════════════
# 特征重要性分析器
# ═══════════════════════════════════════════════════════════════

class FeatureImportanceAnalyzer:
    """特征重要性分析器 - 优化版"""

    def __init__(self):
        self.importance_scores = {}
        self.feature_ranking = []
        self.selector = None
        self._parallel_executor = ParallelExecutor(n_jobs=-1)

    def calculate_importance(self, X: pd.DataFrame, y: pd.Series,
                            method: str = 'random_forest') -> Dict[str, float]:
        """计算特征重要性 - 内存优化版本"""
        logger.info(f"使用 {method} 方法计算特征重要性...")

        feature_cols = [col for col in X.columns 
                       if col not in ['period', 'full_number', 'date']]
        X_features = X[feature_cols].fillna(0)

        if len(feature_cols) > 200:
            logger.info(f"特征数量过多 ({len(feature_cols)})，先进行初步筛选...")
            selector = VarianceThreshold(threshold=0.01)
            X_filtered = selector.fit_transform(X_features)
            mask = selector.get_support()
            feature_cols = [feature_cols[i] for i in range(len(feature_cols)) if mask[i]]
            X_features = X[feature_cols].fillna(0)
            logger.info(f"初步筛选后剩余 {len(feature_cols)} 个特征")

        if method == 'random_forest':
            model = RandomForestClassifier(
                n_estimators=30, max_depth=8, random_state=42, n_jobs=-1
            )
            model.fit(X_features, y)
            importance = dict(zip(feature_cols, model.feature_importances_))

        elif method == 'mutual_info':
            from sklearn.feature_selection import mutual_info_classif
            scores = mutual_info_classif(X_features, y, random_state=42)
            importance = dict(zip(feature_cols, scores))

        else:
            raise ValueError(f"未知方法: {method}")

        self.importance_scores = dict(sorted(
            importance.items(),
            key=lambda x: x[1],
            reverse=True
        ))
        self.feature_ranking = list(self.importance_scores.keys())

        logger.info(f"特征重要性计算完成，共 {len(self.importance_scores)} 个特征")
        return self.importance_scores

    def select_top_features(self, n_features: int = 100,
                           threshold: float = 0.001) -> List[str]:
        """选择Top N特征"""
        if not self.importance_scores:
            raise ValueError("请先计算特征重要性")
        selected = [
            name for name, score in self.importance_scores.items()
            if score >= threshold
        ][:n_features]
        logger.info(f"选择Top {len(selected)} 个特征 (阈值: {threshold})")
        return selected

    def save_importance(self, filepath: Path):
        data = {
            'importance_scores': self.importance_scores,
            'feature_ranking': self.feature_ranking
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"特征重要性已保存: {filepath}")

    def load_importance(self, filepath: Path):
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.importance_scores = data['importance_scores']
        self.feature_ranking = data['feature_ranking']
        logger.info(f"特征重要性已加载: {filepath}")

    def rfe_feature_selection(self, X: pd.DataFrame, y: pd.Series, 
                             n_features: int = 50, n_jobs: int = -1) -> List[str]:
        """使用并行RFE选择特征"""
        logger.info(f"使用并行RFE选择 {n_features} 个特征...")
        
        feature_cols = [col for col in X.columns 
                        if col not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        
        X_features = X[feature_cols].fillna(0)

        if len(feature_cols) > 200:
            logger.info(f"特征数量过多 ({len(feature_cols)})，先进行初步筛选...")
            selector = VarianceThreshold(threshold=0.01)
            X_filtered = selector.fit_transform(X_features)
            mask = selector.get_support()
            feature_cols = [feature_cols[i] for i in range(len(feature_cols)) if mask[i]]
            logger.info(f"初步筛选后剩余 {len(feature_cols)} 个特征")

        # 使用并行RFE选择器
        selector = ParallelRFESelector(n_features=n_features, step=20, n_jobs=n_jobs)
        selector.fit(X, y, feature_cols)
        
        logger.info(f"并行RFE特征选择完成，选择了 {len(selector.selected_features_)} 个特征")
        return selector.selected_features_

    def model_based_feature_selection(self, X: pd.DataFrame, y: pd.Series, 
                                     n_features: int = 50) -> List[str]:
        """使用基于模型的方法选择特征"""
        logger.info(f"使用基于模型的方法选择 {n_features} 个特征...")
        
        feature_cols = [col for col in X.columns 
                        if col not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        X_features = X[feature_cols].fillna(0)

        if len(feature_cols) > 200:
            logger.info(f"特征数量过多 ({len(feature_cols)})，先进行初步筛选...")
            selector = VarianceThreshold(threshold=0.01)
            X_filtered = selector.fit_transform(X_features)
            mask = selector.get_support()
            feature_cols = [feature_cols[i] for i in range(len(feature_cols)) if mask[i]]
            X_features = X[feature_cols].fillna(0)
            logger.info(f"初步筛选后剩余 {len(feature_cols)} 个特征")

        model = RandomForestClassifier(
            n_estimators=30, max_depth=8, random_state=42, n_jobs=-1
        )
        selector = SelectFromModel(estimator=model, max_features=min(n_features, len(feature_cols)))
        selector.fit(X_features, y)
        selected_features = [feature_cols[i] for i in range(len(feature_cols)) if selector.get_support()[i]]
        logger.info(f"基于模型的特征选择完成，选择了 {len(selected_features)} 个特征")
        return selected_features


# ═══════════════════════════════════════════════════════════════
# 特征工程主类 V10
# ═══════════════════════════════════════════════════════════════

class FeatureConfig:
    """特征配置管理器"""

    DEFAULT_CONFIG = {
        'fibonacci': {'enabled': True, 'windows': [5, 8, 13], 'description': '黄金分割特征'},
        'entropy': {'enabled': False, 'windows': [10, 20, 30], 'description': '熵值特征'},
        'markov': {'enabled': True, 'order': 2, 'description': '马尔可夫特征'},
        'chaos': {'enabled': False, 'hurst_windows': [10, 20, 50], 'lyapunov': True, 'description': '混沌特征'},
        'fourier': {'enabled': True, 'n_components': 3, 'description': '傅里叶特征'},
        'cross_correlation': {'enabled': False, 'max_lag': 5, 'description': '互相关特征'},
        'extreme': {'enabled': True, 'windows': [10, 20], 'description': '极值特征'},
        'pattern': {'enabled': True, 'patterns': ['consecutive', 'repeat'], 'description': '形态模式特征'},
        'momentum': {'enabled': True, 'windows': [3, 5], 'description': '动量特征'},
        'garch': {'enabled': False, 'windows': [20, 50], 'description': 'GARCH波动率特征'},
        'granger': {'enabled': False, 'maxlag': 5, 'description': '格兰杰因果特征'},
        'time_series': {'enabled': True, 'description': '时间序列特征'},
        'statistical': {'enabled': True, 'description': '统计特征'},
        'nonlinear': {'enabled': True, 'description': '非线性特征'},
        'pattern_recognition': {'enabled': True, 'description': '模式识别特征'},
        'cross_period_interaction': {
            'enabled': True,
            'max_lag': 3,
            'description': '跨期位置间动态交互依赖特征'
        },
    }

    def __init__(self, config_path: Path = None):
        self.config_path = config_path or MODELS_DIR / "feature_config_v10.json"
        self.config = self.load_config()

    def load_config(self) -> Dict:
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self.DEFAULT_CONFIG.copy()

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        logger.info(f"特征配置已保存: {self.config_path}")

    def get_enabled_features(self) -> List[str]:
        return [name for name, cfg in self.config.items() if cfg.get('enabled', True)]

    def update_config(self, feature_name: str, **kwargs):
        if feature_name in self.config:
            self.config[feature_name].update(kwargs)
            self.save_config()
            logger.info(f"特征配置已更新: {feature_name}")
        else:
            raise ValueError(f"未知特征类型: {feature_name}")


class FeatureEngineerV10:
    """特征工程 V10.0 - 重构优化版"""

    def __init__(self, use_config: bool = True,
                 enable_parallel: bool = True,
                 cache_max_size: int = 100,
                 scaler_method: str = 'standard',
                 model_config: Optional[ModelConfig] = None):
        self._mc = model_config or get_model_config()
        self.config = FeatureConfig() if use_config else None
        self.importance_analyzer = FeatureImportanceAnalyzer()
        self.selected_features = None

        fe_cfg = self._mc.feature_config()
        parallel_cfg = fe_cfg.get('parallel', {})
        self.enable_parallel = enable_parallel and parallel_cfg.get('enable', True)
        self.n_jobs = get_optimal_n_jobs(-1) if self.enable_parallel else 1

        # 使用新的多级缓存
        cache_cfg = fe_cfg.get('cache', {})
        self.cache = FeatureCacheManager(max_size=cache_cfg.get('max_size', cache_max_size))
        self._global_cache = get_global_cache()

        # 并行执行器
        self._parallel_executor = ParallelExecutor(n_jobs=self.n_jobs, prefer='threads')

        logger.info(f"[FeatureEngineerV10] 初始化完成: 并行={self.enable_parallel}, n_jobs={self.n_jobs}")

    def prewarm_cache(self, df: pd.DataFrame):
        """预热缓存，提高缓存命中率"""
        common_configs = [
            (100, 'rfe', False),
            (100, 'model_based', False),
            (150, 'rfe', False),
            (150, 'model_based', False),
        ]
        self.cache.prewarm(df, common_configs)

    # ===================== 特征计算方法（向量化优化） =====================

    def _add_fibonacci_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """黄金分割特征 - 向量化版本"""
        result = df.copy()
        fib_windows = [5, 8, 13, 21]

        for pos in POSITIONS:
            s = df[pos]
            for window in fib_windows:
                if len(df) >= window:
                    result[f'{pos}_fib_mean_{window}'] = s.rolling(window=window, min_periods=1).mean()
                    result[f'{pos}_fib_std_{window}'] = s.rolling(window=window, min_periods=1).std()

        return result

    def _add_entropy_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """熵值特征 - 向量化版本"""
        result = df.copy()
        windows = [10, 20, 30]

        for pos in POSITIONS:
            s = df[pos].values.astype(np.int32)
            for window in windows:
                if len(df) < window:
                    continue
                entropies = np.full(len(df), np.nan)
                for i in range(window - 1, len(df)):
                    window_vals = s[i - window + 1:i + 1]
                    counts = np.bincount(window_vals, minlength=10)
                    probs = counts[counts > 0] / window
                    entropies[i] = -np.sum(probs * np.log2(probs + 1e-10))
                entropies[:window - 1] = entropies[window - 1] if not np.isnan(entropies[window - 1]) else 0.0
                result[f'{pos}_entropy_{window}'] = entropies

        return result

    def _add_markov_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """马尔可夫特征 - 完全向量化版本"""
        result = df.copy()

        for pos in POSITIONS:
            values = df[pos].values.astype(np.int64)
            n = len(values)
            if n < 10:
                result[f'{pos}_markov_entropy'] = np.log(10)
                continue

            prev_vals = values[:-1]
            curr_vals = values[1:]
            valid_mask = (prev_vals >= 0) & (prev_vals < 10) & (curr_vals >= 0) & (curr_vals < 10)

            trans_counts = np.zeros((10, 10), dtype=np.float64)
            np.add.at(trans_counts, (prev_vals[valid_mask], curr_vals[valid_mask]), 1.0)

            row_sums = trans_counts.sum(axis=1, keepdims=True)
            trans_probs = (trans_counts + 0.1) / (row_sums + 1.0)

            log_probs = np.log(trans_probs + 1e-10)
            per_row_entropy = -np.sum(trans_probs * log_probs, axis=1)

            markov_entropies = np.full(n, np.log(10))
            valid_prev = (values[:-1] >= 0) & (values[:-1] < 10)
            markov_entropies[1:][valid_prev] = per_row_entropy[values[:-1][valid_prev]]
            markov_entropies[0] = np.log(10)

            result[f'{pos}_markov_entropy'] = markov_entropies

        return result

    def _add_cross_period_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """跨期位置间动态交互依赖特征

        依据时序构建跨期位置间动态交互依赖建模（包括但不限于两期），
        以增强号码间状态转移概率曲线值。

        生成特征：
        1. 多阶跨期转移概率（lag-1/2/3 同位置）
        2. 跨位置跨期交互强度（Cramér's V）
        3. 多阶融合转移概率Top值
        4. 跨期联合转移熵
        """
        from src.core.models.cross_period_dynamic_model import (
            extract_cross_period_features,
        )

        max_lag = 3
        if self.config and 'cross_period_interaction' in self.config.config:
            max_lag = self.config.config['cross_period_interaction'].get('max_lag', 3)

        try:
            result = extract_cross_period_features(df, max_lag=max_lag)
            logger.info(f"  跨期位置交互特征提取完成: max_lag={max_lag}, "
                        f"新增{result.shape[1] - df.shape[1]}列")
            return result
        except Exception as e:
            logger.warning(f"  跨期位置交互特征提取失败: {e}，返回原始数据")
            return df.copy()

    def _add_fourier_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """傅里叶特征 - 向量化"""
        result = df.copy()
        n_components = 3

        for pos in POSITIONS:
            if len(df) >= 20:
                fft_vals = fft(df[pos].values[-20:])
                real_parts = np.real(fft_vals[:n_components])
                imag_parts = np.imag(fft_vals[:n_components])
                for i in range(n_components):
                    result[f'{pos}_fft_real_{i}'] = real_parts[i] if i < len(real_parts) else 0.0
                    result[f'{pos}_fft_imag_{i}'] = imag_parts[i] if i < len(imag_parts) else 0.0

        return result

    def _add_extreme_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """极值特征 - 向量化"""
        result = df.copy()
        windows = [10, 20, 50]

        for pos in POSITIONS:
            s = df[pos]
            for window in windows:
                if len(df) >= window:
                    result[f'{pos}_max_{window}'] = s.rolling(window=window, min_periods=1).max()
                    result[f'{pos}_min_{window}'] = s.rolling(window=window, min_periods=1).min()

        return result

    def _add_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """形态模式特征 - 向量化"""
        result = df.copy()
        for pos in POSITIONS:
            result[f'{pos}_repeat_2'] = (df[pos] == df[pos].shift(1)).astype(int)
            result[f'{pos}_increasing'] = ((df[pos] - df[pos].shift(1)) == 1).astype(int)
            result[f'{pos}_decreasing'] = ((df[pos] - df[pos].shift(1)) == -1).astype(int)
            result[f'{pos}_alternating'] = ((df[pos] - df[pos].shift(1)) * (df[pos].shift(1) - df[pos].shift(2)) < 0).astype(int)
            result[f'{pos}_repeat_3'] = ((df[pos] == df[pos].shift(1)) & (df[pos].shift(1) == df[pos].shift(2))).astype(int)
        return result

    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """动量特征 - 向量化"""
        result = df.copy()
        windows = [3, 5, 10]

        for pos in POSITIONS:
            s = df[pos]
            for window in windows:
                if len(df) >= window:
                    result[f'{pos}_momentum_{window}'] = s - s.shift(window)

        return result

    def _add_time_series_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """时间序列特征 - 全面向量化"""
        result = df.copy()
        windows = [3, 5, 10, 20, 30, 50]

        for pos in POSITIONS:
            s = df[pos].astype(np.float64)

            for window in windows:
                if len(df) >= window:
                    result[f'{pos}_ma_{window}'] = s.rolling(window=window, min_periods=1).mean()
                    result[f'{pos}_ema_{window}'] = s.ewm(span=window, adjust=False).mean()
                    result[f'{pos}_std_{window}'] = s.rolling(window=window, min_periods=1).std()
                    result[f'{pos}_skew_{window}'] = _vectorized_rolling_skew(s, window)
                    result[f'{pos}_kurtosis_{window}'] = _vectorized_rolling_kurtosis(s, window)

            for window in [5, 10, 20, 30]:
                if len(df) >= window:
                    result[f'{pos}_trend_{window}'] = _vectorized_rolling_polyfit_trend(s, window)

            returns = s.diff()
            for window in [5, 10, 20]:
                if len(df) >= window:
                    result[f'{pos}_volatility_{window}'] = returns.rolling(window=window, min_periods=1).std()

        return result

    def _add_nonlinear_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """非线性特征 - 完全向量化"""
        result = df.copy()

        for pos in POSITIONS:
            vals = df[pos].astype(np.float64)
            result[f'{pos}_square'] = vals ** 2
            result[f'{pos}_cube'] = vals ** 3
            result[f'{pos}_sqrt'] = np.sqrt(vals + 1e-10)
            result[f'{pos}_log'] = np.log(vals + 1e-10)
            result[f'{pos}_exp'] = np.exp(vals / 10)

        for i, pos1 in enumerate(POSITIONS):
            for j, pos2 in enumerate(POSITIONS[i + 1:], i + 1):
                v1 = df[pos1].astype(np.float64)
                v2 = df[pos2].astype(np.float64)
                result[f'{pos1}_{pos2}_product'] = v1 * v2
                result[f'{pos1}_{pos2}_sum'] = v1 + v2
                result[f'{pos1}_{pos2}_diff'] = v1 - v2

        return result

    def _add_statistical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """统计特征 - 向量化"""
        result = df.copy()
        windows = [5, 10, 20]

        for pos in POSITIONS:
            s = df[pos].astype(np.float64)
            for window in windows:
                if len(df) >= window:
                    result[f'{pos}_quantile_25_{window}'] = s.rolling(window=window, min_periods=1).quantile(0.25)
                    result[f'{pos}_quantile_50_{window}'] = s.rolling(window=window, min_periods=1).quantile(0.5)
                    result[f'{pos}_quantile_75_{window}'] = s.rolling(window=window, min_periods=1).quantile(0.75)

        return result

    # ===================== 并行调度 =====================

    def _compute_feature_group(self, df: pd.DataFrame, group_name: str) -> pd.DataFrame:
        """计算单个特征组（供并行调用）"""
        dispatch = {
            'fibonacci': self._add_fibonacci_features,
            'entropy': self._add_entropy_features,
            'markov': self._add_markov_features,
            'cross_period_interaction': self._add_cross_period_interaction_features,
            'fourier': self._add_fourier_features,
            'extreme': self._add_extreme_features,
            'pattern': self._add_pattern_features,
            'momentum': self._add_momentum_features,
            'time_series': self._add_time_series_features,
            'statistical': self._add_statistical_features,
            'nonlinear': self._add_nonlinear_features,
        }
        fn = dispatch.get(group_name)
        if fn:
            return fn(df)
        return df.copy()

    # ===================== 主入口 =====================

    @track_performance
    def extract_all_features(self, df: pd.DataFrame,
                            select_top: Optional[int] = 100,
                            feature_selection_method: str = 'rfe',
                            enable_scaler: bool = False) -> pd.DataFrame:
        """提取所有特征（V10.0重构版）

        Args:
            df: 输入数据
            select_top: 特征选择Top N
            feature_selection_method: 特征选择方法
            enable_scaler: 是否启用标准化
        """
        start_time = time.time()
        logger.info("V10.0 特征工程开始（重构优化版）...")

        # 生成缓存key
        cache_key = self.cache.get_key(df, (select_top, feature_selection_method, enable_scaler))

        # 检查缓存
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.info("  从缓存加载特征（命中）")
            duration = time.time() - start_time
            logger.info(f"V10.0 特征工程完成（缓存）: {cached.shape[1]} 列, 耗时: {duration:.3f}s")
            return cached

        # 检查全局缓存
        global_cached, level = self._global_cache.get(cache_key)
        if global_cached is not None:
            logger.info(f"  从全局缓存加载特征（命中 {level.name if level else 'None'}）")
            # 回填本地缓存
            self.cache.put(cache_key, global_cached)
            return global_cached

        enabled_features = (
            self.config.get_enabled_features() if self.config
            else list(FeatureConfig.DEFAULT_CONFIG.keys())
        )
        logger.info(f"启用的特征类型: {enabled_features}, 并行={'开启' if self.enable_parallel else '关闭'}")

        result_df = df.copy()

        feature_groups = [
            ('fibonacci', 'fibonacci'),
            ('markov', 'markov'),
            ('cross_period_interaction', 'cross_period_interaction'),
            ('fourier', 'fourier'),
            ('extreme', 'extreme'),
            ('pattern', 'pattern'),
            ('momentum', 'momentum'),
            ('time_series', 'time_series'),
            ('statistical', 'statistical'),
            ('nonlinear', 'nonlinear'),
        ]

        active_groups = [(cfg_key, method_name) for cfg_key, method_name in feature_groups
                         if cfg_key in enabled_features]

        # 并行计算特征组
        if self.enable_parallel and len(active_groups) >= 2:
            logger.info(f"  并行计算 {len(active_groups)} 个特征组 (n_jobs={self.n_jobs})...")
            
            def compute_group(args):
                _, method_name = args
                return self._compute_feature_group(df.copy(), method_name)
            
            results = self._parallel_executor.map(compute_group, active_groups)

            base_cols = set(result_df.columns)
            for partial_result in results:
                new_cols = [c for c in partial_result.columns if c not in base_cols]
                if new_cols:
                    for col in new_cols:
                        result_df[col] = partial_result[col]
                    base_cols.update(new_cols)
        else:
            for cfg_key, method_name in active_groups:
                t0 = time.time()
                result_df = self._compute_feature_group(result_df, method_name)
                logger.info(f"  {method_name} OK ({time.time()-t0:.3f}s)")

        # 特征选择
        if select_top and len(result_df.columns) > select_top + 10:
            result_df = self._select_features_parallel(result_df, select_top, feature_selection_method)

        # 存入缓存
        self.cache.put(cache_key, result_df)
        self._global_cache.put(cache_key, result_df)

        duration = time.time() - start_time
        logger.info(f"V10.0 特征工程完成: {result_df.shape[1]} 列, 耗时: {duration:.2f}s | 缓存统计: {self.cache.stats}")
        return result_df

    def _select_features_parallel(self, df: pd.DataFrame, n_features: int, method: str = 'rfe') -> pd.DataFrame:
        """并行特征选择 - 关键优化"""
        feature_cols = [col for col in df.columns
                        if col not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]

        if len(feature_cols) <= n_features:
            return df

        basic_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']

        logger.info(f"并行特征选择: 从 {len(feature_cols)} 个中选择 {n_features} 个 (方法: {method})")
        start_time = time.time()

        if method == 'rfe':
            # 使用并行RFE - 为每个位置并行执行
            def process_position(pos):
                y = df[pos]
                selector = ParallelRFESelector(
                    n_features=max(10, n_features // len(POSITIONS)),
                    step=20,
                    n_jobs=1  # 内部已经并行化
                )
                return selector.fit(df, y, feature_cols).selected_features_

            results = self._parallel_executor.map(process_position, POSITIONS)
            
            selected_features = []
            for pos_features in results:
                selected_features.extend(pos_features)
        
        elif method == 'model_based':
            def process_position(pos):
                y = df[pos]
                return self.importance_analyzer.model_based_feature_selection(df, y, n_features // len(POSITIONS))

            results = self._parallel_executor.map(process_position, POSITIONS)
            selected_features = []
            for pos_features in results:
                selected_features.extend(pos_features)
        
        else:
            # 默认方法
            selected_features = feature_cols[:n_features]

        # 去重并限制数量
        selected_features = list(dict.fromkeys(selected_features))[:n_features]
        selected_cols = basic_cols + selected_features

        elapsed = time.time() - start_time
        logger.info(f"特征选择完成: 选择 {len(selected_features)} 个特征, 耗时: {elapsed:.2f}s")
        
        return df[selected_cols]

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            'local_cache': self.cache.stats,
            'global_cache': self._global_cache.stats
        }


# 向后兼容
FeatureEngineer = FeatureEngineerV10
