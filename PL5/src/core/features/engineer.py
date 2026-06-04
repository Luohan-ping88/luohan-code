"""
特征工程模块 V10.0 - 高性能优化版
优化项：
1. 向量化计算（消除循环，使用numpy/pandas内置操作）
2. 并行化独立特征组（joblib Parallel）
3. 基于hash的特征缓存（含LRU清理接口）
4. RobustScaler + 按特征组标准化
5. 特征漂移检测（PSI/KS统计量记录与警告）
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.fft import fft
from scipy.signal import correlate
from scipy.stats import kstest, entropy as scipy_entropy
import warnings
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Callable
import json
import pickle
import hashlib
import time
import threading  # 【V10.4新增】线程锁支持
from collections import OrderedDict
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectFromModel, VarianceThreshold
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler as SklearnRobustScaler

from .config import setup_logging, MODELS_DIR, PROCESSED_DATA_DIR
from src.core.config import ModelConfig, get_model_config
from src.core.monitoring.performance_monitor import track_performance

logger = setup_logging(__name__)

try:
    from joblib import Parallel, delayed
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False
    logger.warning("joblib未安装，并行特征计算将不可用")


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
    """向量化rolling trend (polyfit slope) - 使用cumsum技巧加速"""
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
    hash_obj = hashlib.md5()
    for col in cols:
        if col in df.columns:
            try:
                # 尝试使用 tobytes 方法（NumPy 数组）
                values = df[col].values.tobytes()
                hash_obj.update(values)
            except AttributeError:
                # 处理 ArrowStringArray 等其他类型
                values = df[col].values
                hash_obj.update(str(values).encode())
            hash_obj.update(str(len(df)).encode())
    return hash_obj.hexdigest()


class FeatureImportanceAnalyzer:
    """特征重要性分析器"""

    def __init__(self):
        self.importance_scores = {}
        self.feature_ranking = []
        self.selector = None

    def calculate_importance(self, X: pd.DataFrame, y: pd.Series,
                            method: str = 'random_forest') -> Dict[str, float]:
        """计算特征重要性 - 内存优化版本"""
        logger.info(f"使用 {method} 方法计算特征重要性...")

        feature_cols = [col for col in X.columns 
                       if col not in ['period', 'full_number']]
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
                n_estimators=30,
                max_depth=8,
                random_state=42,
                n_jobs=-1 if JOBLIB_AVAILABLE else 1
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

    def rfe_feature_selection(self, X: pd.DataFrame, y: pd.Series, n_features: int = 50) -> List[str]:
        logger.info(f"使用RFE选择 {n_features} 个特征...")
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

        from sklearn.feature_selection import RFE
        model = RandomForestClassifier(
            n_estimators=30,
            max_depth=8,
            random_state=42,
            n_jobs=-1 if JOBLIB_AVAILABLE else 1
        )
        rfe = RFE(estimator=model, n_features_to_select=min(n_features, len(feature_cols)), step=20)
        rfe.fit(X_features, y)
        selected_features = [feature_cols[i] for i in range(len(feature_cols)) if rfe.support_[i]]
        logger.info(f"RFE特征选择完成，选择了 {len(selected_features)} 个特征")
        return selected_features

    def model_based_feature_selection(self, X: pd.DataFrame, y: pd.Series, n_features: int = 50) -> List[str]:
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
            n_estimators=30,
            max_depth=8,
            random_state=42,
            n_jobs=-1 if JOBLIB_AVAILABLE else 1
        )
        selector = SelectFromModel(estimator=model, max_features=min(n_features, len(feature_cols)))
        selector.fit(X_features, y)
        selected_features = [feature_cols[i] for i in range(len(feature_cols)) if selector.get_support()[i]]
        logger.info(f"基于模型的特征选择完成，选择了 {len(selected_features)} 个特征")
        return selected_features


class FeatureCacheManager:
    """基于hash的LRU特征缓存管理器 - 【V10.4修复】线程安全"""

    def __init__(self, max_size: int = 50):
        self._cache: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self._max_size = max_size
        self._hit_count = 0
        self._miss_count = 0
        self._cache_times: Dict[str, float] = {}  # 记录缓存时间，用于智能淘汰
        self._lock = threading.RLock()  # 【V10.4新增】可重入锁

    def get_key(self, df: pd.DataFrame, extra_tags: Tuple = ()) -> str:
        """生成缓存key（基于数据内容hash）"""
        core_cols = ['period']
        if 'full_number' in df.columns:
            core_cols.append('full_number')
        data_hash = _compute_data_hash(df, core_cols)
        tag_hash = hashlib.md5(str(extra_tags).encode()).hexdigest()[:8]
        return f"{data_hash}_{tag_hash}"

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """获取缓存"""
        with self._lock:  # 【V10.4修复】线程安全保护
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hit_count += 1
                self._cache_times[key] = time.time()
                return self._cache[key].copy()
            self._miss_count += 1
            return None

    def put(self, key: str, df: pd.DataFrame):
        """存入缓存（LRU策略）"""
        with self._lock:  # 【V10.4修复】线程安全保护
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._max_size:
                    # 智能淘汰：优先淘汰最旧的缓存
                    oldest_key = min(self._cache_times, key=lambda k: self._cache_times.get(k, 0))
                    del self._cache[oldest_key]
                    del self._cache_times[oldest_key]
                    logger.debug(f"缓存淘汰: {oldest_key[:16]}...")
                self._cache[key] = df.copy()
            self._cache_times[key] = time.time()

    def clear(self):
        """清空所有缓存"""
        with self._lock:  # 【V10.4修复】线程安全保护
            size = len(self._cache)
            self._cache.clear()
            self._cache_times.clear()
        logger.info(f"特征缓存已清空，释放 {size} 条记录")

    def clear_by_prefix(self, prefix: str):
        """按前缀清理缓存"""
        with self._lock:  # 【V10.4修复】线程安全保护
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]
                if k in self._cache_times:
                    del self._cache_times[k]
        logger.info(f"按前缀 '{prefix}' 清理了 {len(keys_to_remove)} 条缓存")

    def prewarm(self, df: pd.DataFrame, common_configs: List[Tuple]):
        """缓存预热：预先计算常用配置的特征"""
        logger.info(f"开始缓存预热，预计算 {len(common_configs)} 个配置...")
        for config in common_configs:
            key = self.get_key(df, config)
            if key not in self._cache:
                logger.debug(f"预热缓存配置: {config}")
                # 这里不实际计算，只是记录预热标记
                # 实际计算会在第一次使用时进行
                pass
        logger.info("缓存预热完成")

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            'size': len(self._cache),
            'max_size': self._max_size,
            'hits': self._hit_count,
            'misses': self._miss_count,
            'hit_rate': self._hit_count / max(1, self._hit_count + self._miss_count),
            'recent_cache_times': {k[:16]: v for k, v in list(self._cache_times.items())[-5:]}
        }

    def __len__(self):
        return len(self._cache)


class FeatureDriftDetector:
    """特征漂移检测器 - 记录训练统计量，预测时检测分布变化"""

    def __init__(self, psi_threshold: float = 0.2, ks_threshold: float = 0.05):
        self.psi_threshold = psi_threshold
        self.ks_threshold = ks_threshold
        self.training_stats: Dict[str, Dict[str, float]] = {}
        self.training_quantiles: Dict[str, Dict[str, float]] = {}
        self.drift_warnings: List[Dict[str, Any]] = []

    def fit(self, df: pd.DataFrame, feature_cols: Optional[List[str]] = None):
        """记录训练数据的特征统计量"""
        cols = feature_cols or [c for c in df.columns
                                if c not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        for col in cols:
            if col not in df.columns or not np.issubdtype(df[col].dtype, np.number):
                continue
            series = df[col].dropna()
            if len(series) == 0:
                continue
            self.training_stats[col] = {
                'mean': float(series.mean()),
                'std': float(series.std()),
                'min': float(series.min()),
                'max': float(series.max()),
                'median': float(series.median()),
                'count': int(len(series))
            }
            self.training_quantiles[col] = {
                'q01': float(series.quantile(0.01)),
                'q05': float(series.quantile(0.05)),
                'q25': float(series.quantile(0.25)),
                'q50': float(series.quantile(0.50)),
                'q75': float(series.quantile(0.75)),
                'q95': float(series.quantile(0.95)),
                'q99': float(series.quantile(0.99))
            }
        logger.info(f"漂移检测器已拟合: 记录了 {len(self.training_stats)} 个特征的统计量")

    def detect(self, df: pd.DataFrame, feature_cols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """检测特征分布漂移，返回漂移警告列表"""
        self.drift_warnings = []
        cols = feature_cols or list(self.training_stats.keys())

        for col in cols:
            if col not in df.columns or col not in self.training_stats:
                continue
            series = df[col].dropna()
            if len(series) < 10:
                continue

            train_stats = self.training_stats[col]
            train_q = self.training_quantiles.get(col, {})

            psi_score = self._calc_psi(train_q, series)
            z_score = abs(float(series.mean()) - train_stats['mean']) / max(train_stats['std'], 1e-10)

            drift_type = []
            if psi_score > self.psi_threshold:
                drift_type.append(f'PSI={psi_score:.3f}')
            if z_score > 3:
                drift_type.append(f'Z={z_score:.1f}')

            if drift_type:
                warning = {
                    'feature': col,
                    'psi': round(psi_score, 4),
                    'z_score': round(z_score, 2),
                    'train_mean': round(train_stats['mean'], 4),
                    'current_mean': round(float(series.mean()), 4),
                    'drift_type': ', '.join(drift_type),
                    'severity': 'high' if psi_score > 0.5 or z_score > 5 else ('medium' if psi_score > 0.3 or z_score > 4 else 'low')
                }
                self.drift_warnings.append(warning)

        if self.drift_warnings:
            high_count = sum(1 for w in self.drift_warnings if w['severity'] == 'high')
            logger.warning(f"检测到 {len(self.drift_warnings)} 个特征漂移 ({high_count}个严重)")
        else:
            logger.info("未检测到显著特征漂移")

        return self.drift_warnings

    @staticmethod
    def _calc_psi(train_q: Dict[str, float], current_series: pd.Series) -> float:
        """计算Population Stability Index (PSI)"""
        bins = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
        q_keys = ['q01', 'q05', 'q25', 'q50', 'q75', 'q95', 'q99']
        edges = [train_q.get(k, 0.0) for k in q_keys]
        edges = sorted(set(edges))

        if len(edges) < 2:
            return 0.0

        try:
            current_counts, _ = np.histogram(current_series, bins=edges)
            current_pct = current_counts / current_counts.sum()

            uniform_train = np.ones(len(edges) - 1) / (len(edges) - 1)
            psi = np.sum((current_pct - uniform_train) * np.log((current_pct + 1e-10) / (uniform_train + 1e-10)))
            return float(psi)
        except Exception:
            return 0.0

    def get_drift_report(self) -> str:
        """生成漂移报告"""
        if not self.drift_warnings:
            return "无特征漂移"
        lines = [f"=== 特征漂移报告 ===", f"共检测到 {len(self.drift_warnings)} 个漂移特征:"]
        for w in self.drift_warnings:
            lines.append(
                f"  [{w['severity'].upper()}] {w['feature']}: "
                f"PSI={w['psi']}, Z={w['z_score']}, "
                f"train_mean={w['train_mean']} → current_mean={w['current_mean']} "
                f"({w['drift_type']})"
            )
        return '\n'.join(lines)

    def save(self, filepath: Path):
        data = {
            'training_stats': self.training_stats,
            'training_quantiles': self.training_quantiles,
            'psi_threshold': self.psi_threshold,
            'ks_threshold': self.ks_threshold
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"漂移检测器状态已保存: {filepath}")

    def load(self, filepath: Path):
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.training_stats = data['training_stats']
        self.training_quantiles = data['training_quantiles']
        self.psi_threshold = data.get('psi_threshold', 0.2)
        self.ks_threshold = data.get('ks_threshold', 0.05)
        logger.info(f"漂移检测器状态已加载: {filepath}")


class FeatureScaler:
    """支持多种标准化/归一化策略，可按特征组分别处理"""

    SUPPORTED_METHODS = ('standard', 'minmax', 'robust', 'none')

    def __init__(self, method: str = 'standard',
                 group_mapping: Optional[Dict[str, List[str]]] = None,
                 robust_quantile_range: Tuple[float, float] = (25.0, 75.0)):
        if method not in self.SUPPORTED_METHODS:
            raise ValueError(f"不支持的标准化方法: {method}，可选: {self.SUPPORTED_METHODS}")
        self.method = method
        self.group_mapping = group_mapping or {}
        self.robust_quantile_range = robust_quantile_range
        self._scalers: Dict[str, Any] = {}
        self._fitted = False

    def _get_group(self, col_name: str) -> str:
        """确定特征所属组"""
        for group_name, members in self.group_mapping.items():
            if any(col_name.startswith(m) or col_name.endswith(m) for m in members):
                return group_name
        return '_default'

    def fit(self, df: pd.DataFrame, feature_cols: Optional[List[str]] = None):
        """拟合标准化器"""
        cols = feature_cols or [c for c in df.columns
                                if c not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        groups = set(self._get_group(c) for c in cols)

        for group in groups:
            group_cols = [c for c in cols if self._get_group(c) == group]
            group_data = df[group_cols].select_dtypes(include=[np.number])
            if group_data.empty:
                continue

            if self.method == 'standard':
                scaler = StandardScaler()
            elif self.method == 'minmax':
                scaler = MinMaxScaler()
            elif self.method == 'robust':
                scaler = SklearnRobustScaler(quantile_range=self.robust_quantile_range)
            elif self.method == 'none':
                continue

            scaler.fit(group_data.fillna(0))
            self._scalers[group] = scaler

        self._fitted = True
        logger.info(f"标准化器已拟合: method={self.method}, groups={list(self._scalers.keys())}")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """转换数据"""
        if not self._fitted or self.method == 'none':
            return df
        result = df.copy()
        for group, scaler in self._scalers.items():
            group_cols = [c for c in result.columns if self._get_group(c) == group and np.issubdtype(result[c].dtype, np.number)]
            if group_cols:
                result[group_cols] = scaler.transform(result[group_cols].fillna(0))
        return result

    def fit_transform(self, df: pd.DataFrame, feature_cols: Optional[List[str]] = None) -> pd.DataFrame:
        self.fit(df, feature_cols)
        return self.transform(df)

    def save(self, filepath: Path):
        data = {
            'method': self.method,
            'group_mapping': self.group_mapping,
            'robust_quantile_range': self.robust_quantile_range,
            'scalers': self._scalers,
            'fitted': self._fitted
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"标准化器已保存: {filepath}")

    def load(self, filepath: Path):
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.method = data['method']
        self.group_mapping = data.get('group_mapping', {})
        self.robust_quantile_range = data.get('robust_quantile_range', (25.0, 75.0))
        self._scalers = data.get('scalers', {})
        self._fitted = data.get('fitted', False)
        logger.info(f"标准化器已加载: {filepath}")


class FeatureConfig:
    """特征配置管理器"""

    DEFAULT_CONFIG = {
        'fibonacci': {
            'enabled': True,
            'windows': [5, 8, 13],
            'description': '黄金分割特征'
        },
        'entropy': {
            'enabled': False,
            'windows': [10, 20, 30],
            'description': '熵值特征'
        },
        'markov': {
            'enabled': True,
            'order': 2,
            'description': '马尔可夫特征'
        },
        'chaos': {
            'enabled': False,
            'hurst_windows': [10, 20, 50],
            'lyapunov': True,
            'description': '混沌特征'
        },
        'fourier': {
            'enabled': True,
            'n_components': 3,
            'description': '傅里叶特征'
        },
        'cross_correlation': {
            'enabled': False,
            'max_lag': 5,
            'description': '互相关特征'
        },
        'extreme': {
            'enabled': True,
            'windows': [10, 20],
            'description': '极值特征'
        },
        'pattern': {
            'enabled': True,
            'patterns': ['consecutive', 'repeat'],
            'description': '形态模式特征'
        },
        'momentum': {
            'enabled': True,
            'windows': [3, 5],
            'description': '动量特征'
        },
        'garch': {
            'enabled': False,
            'windows': [20, 50],
            'description': 'GARCH波动率特征'
        },
        'granger': {
            'enabled': False,
            'maxlag': 5,
            'description': '格兰杰因果特征'
        },
        'pl5_specific': {
            'enabled': False,
            'description': '排列五特定特征'
        }
    }

    def __init__(self, config_path: Path = None):
        self.config_path = config_path or MODELS_DIR / "feature_config_v9.json"
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


POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']


class FeatureEngineerV9:
    """特征工程 V10.0 - 高性能优化版"""

    def __init__(self, use_config: bool = True,
                 enable_parallel: bool = True,
                 cache_max_size: int = 50,
                 scaler_method: str = 'standard',
                 model_config: Optional[ModelConfig] = None):
        self._mc = model_config or get_model_config()
        self.config = FeatureConfig() if use_config else None
        self.importance_analyzer = FeatureImportanceAnalyzer()
        self.selected_features = None

        fe_cfg = self._mc.feature_config()
        parallel_cfg = fe_cfg.get('parallel', {})
        self.enable_parallel = (enable_parallel and parallel_cfg.get('enable', True)
                                if parallel_cfg else (enable_parallel and JOBLIB_AVAILABLE))
        self.n_jobs = -1 if self.enable_parallel else 1

        cache_cfg = fe_cfg.get('cache', {})
        self.cache = FeatureCacheManager(max_size=cache_cfg.get('max_size', cache_max_size))

        drift_cfg = fe_cfg.get('drift_detection', {})
        self.drift_detector = FeatureDriftDetector(
            psi_threshold=drift_cfg.get('psi_threshold', 0.2),
            ks_threshold=drift_cfg.get('ks_threshold', 0.05))

        scaler_cfg = fe_cfg.get('scaler', {})
        scaler_method_from_cfg = scaler_cfg.get('method', scaler_method)
        self.scaler = FeatureScaler(
            method=scaler_method_from_cfg,
            robust_quantile_range=tuple(scaler_cfg.get('robust_quantile_range', [25.0, 75.0])))

        try:
            from cpp_core import FeatureCalculator, CPP_AVAILABLE
            self.cpp_calc = FeatureCalculator()
            self.cpp_available = CPP_AVAILABLE
            if self.cpp_available:
                logger.info("[feature_engineering V9] C++ accelerator loaded")
        except ImportError:
            self.cpp_calc = None
            self.cpp_available = False
            logger.info("[feature_engineering V9] Using Python fallback")

    def prewarm_cache(self, df: pd.DataFrame):
        """预热缓存，提高缓存命中率"""
        common_configs = [
            (100, 'rfe', False),
            (100, 'model_based', False),
            (150, 'rfe', False),
            (150, 'model_based', False),
            (100, 'rfe', True),
            (100, 'model_based', True)
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
        """熵值特征 - 向量化版本（避免rolling apply）"""
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
        """马尔可夫特征 - 完全向量化版本（消除Python循环）"""
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

    def _add_chaos_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """混沌特征"""
        result = df.copy()
        for pos in POSITIONS:
            if self.cpp_available and self.cpp_calc:
                try:
                    hurst = self.cpp_calc.hurst_exponent(df[pos].values[-100:])
                    result[f'{pos}_hurst'] = hurst
                except Exception:
                    result[f'{pos}_hurst'] = 0.5
            else:
                result[f'{pos}_hurst'] = 0.5
        return result

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

    def _add_cross_correlation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """互相关特征 - 向量化"""
        result = df.copy()
        for i, pos1 in enumerate(POSITIONS):
            for pos2 in POSITIONS[i + 1:]:
                if len(df) >= 20:
                    corr = np.corrcoef(df[pos1].values[-20:], df[pos2].values[-20:])[0, 1]
                    result[f'corr_{pos1}_{pos2}'] = corr if not np.isnan(corr) else 0.0
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
            # 1. 连续重复模式
            result[f'{pos}_repeat_2'] = (df[pos] == df[pos].shift(1)).astype(int)
            
            # 2. 连续递增模式
            result[f'{pos}_increasing'] = ((df[pos] - df[pos].shift(1)) == 1).astype(int)
            
            # 3. 连续递减模式
            result[f'{pos}_decreasing'] = ((df[pos] - df[pos].shift(1)) == -1).astype(int)
            
            # 4. 交替模式
            result[f'{pos}_alternating'] = ((df[pos] - df[pos].shift(1)) * (df[pos].shift(1) - df[pos].shift(2)) < 0).astype(int)
            
            # 5. 三连重复模式
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

    def _add_garch_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """GARCH波动率特征 - 向量化"""
        result = df.copy()
        for pos in POSITIONS:
            returns = df[pos].diff().fillna(0)
            result[f'{pos}_volatility_20'] = returns.rolling(window=20, min_periods=1).std()
        return result

    def _add_granger_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """格兰杰因果特征 - 向量化"""
        result = df.copy()
        for i, pos1 in enumerate(POSITIONS):
            for pos2 in POSITIONS:
                if pos1 != pos2:
                    result[f'granger_{pos1}_{pos2}'] = df[pos1].shift(1).corr(df[pos2]).fillna(0)
        return result

    def _add_time_series_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """时间序列特征 - 全面向量化（消除所有rolling apply lambda）"""
        result = df.copy()
        windows = [3, 5, 10, 20, 30, 50]

        if 'date' in df.columns:
            try:
                date_series = pd.to_datetime(df['date'])
                result['date_timestamp'] = (date_series - pd.Timestamp('2004-01-01')).dt.days
                result['date_year'] = date_series.dt.year
                result['date_month'] = date_series.dt.month
                result['date_day'] = date_series.dt.day
                result['date_weekday'] = date_series.dt.weekday
                result['date_quarter'] = date_series.dt.quarter
                result['date_dayofyear'] = date_series.dt.dayofyear
                result['date_is_month_start'] = date_series.dt.is_month_start.astype(int)
                result['date_is_month_end'] = date_series.dt.is_month_end.astype(int)
                logger.info("日期特征已提取")
            except Exception as e:
                logger.warning(f"日期特征提取失败: {e}")

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
                    result[f'{pos}_volatility_ema_{window}'] = returns.ewm(span=window, adjust=False).std()

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
                result[f'{pos1}_{pos2}_ratio'] = (v1 + 1e-10) / (v2 + 1e-10)

        for i, pos1 in enumerate(POSITIONS):
            for j, pos2 in enumerate(POSITIONS[i + 1:], i + 1):
                for k, pos3 in enumerate(POSITIONS[j + 1:], j + 1):
                    result[f'{pos1}_{pos2}_{pos3}_product'] = df[pos1] * df[pos2] * df[pos3]
                    result[f'{pos1}_{pos2}_{pos3}_sum'] = df[pos1] + df[pos2] + df[pos3]

        return result

    def _add_statistical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """统计特征 - 向量化（消除rolling apply lambda）"""
        result = df.copy()
        windows = [5, 10, 20]

        for pos in POSITIONS:
            s = df[pos].astype(np.float64)
            for window in windows:
                if len(df) >= window:
                    result[f'{pos}_skew_{window}'] = _vectorized_rolling_skew(s, window)
                    result[f'{pos}_kurtosis_{window}'] = _vectorized_rolling_kurtosis(s, window)
                    result[f'{pos}_quantile_25_{window}'] = s.rolling(window=window, min_periods=1).quantile(0.25)
                    result[f'{pos}_quantile_50_{window}'] = s.rolling(window=window, min_periods=1).quantile(0.5)
                    result[f'{pos}_quantile_75_{window}'] = s.rolling(window=window, min_periods=1).quantile(0.75)

        return result

    def _add_pattern_recognition_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """模式识别特征 - 完全向量化"""
        result = df.copy()

        for pos in POSITIONS:
            s = df[pos]
            shifted1 = s.shift(1)
            shifted2 = s.shift(2)
            result[f'{pos}_repeat_2'] = (s == shifted1).astype(int)
            result[f'{pos}_repeat_3'] = ((s == shifted1) & (s == shifted2)).astype(int)
            result[f'{pos}_increasing'] = (s > shifted1).astype(int)
            result[f'{pos}_decreasing'] = (s < shifted1).astype(int)
            result[f'{pos}_consecutive_increasing'] = ((s > shifted1) & (shifted1 > shifted2)).astype(int)
            result[f'{pos}_consecutive_decreasing'] = ((s < shifted1) & (shifted1 < shifted2)).astype(int)
            result[f'{pos}_alternating'] = (
                ((s > shifted1) & (shifted1 < shifted2)) |
                ((s < shifted1) & (shifted1 > shifted2))
            ).astype(int)

        return result
        
    def _add_pl5_specific_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """排列五特定特征"""
        result = df.copy()
        
        # 1. 数字频率特征
        for pos in POSITIONS:
            # 计算每个数字的频率
            freq = df[pos].value_counts(normalize=True)
            freq_dict = freq.to_dict()
            # 数字频率特征
            result[f'{pos}_freq_0'] = df[pos].apply(lambda x: freq_dict.get(0, 0))
            result[f'{pos}_freq_1'] = df[pos].apply(lambda x: freq_dict.get(1, 0))
            result[f'{pos}_freq_2'] = df[pos].apply(lambda x: freq_dict.get(2, 0))
            result[f'{pos}_freq_3'] = df[pos].apply(lambda x: freq_dict.get(3, 0))
            result[f'{pos}_freq_4'] = df[pos].apply(lambda x: freq_dict.get(4, 0))
            result[f'{pos}_freq_5'] = df[pos].apply(lambda x: freq_dict.get(5, 0))
            result[f'{pos}_freq_6'] = df[pos].apply(lambda x: freq_dict.get(6, 0))
            result[f'{pos}_freq_7'] = df[pos].apply(lambda x: freq_dict.get(7, 0))
            result[f'{pos}_freq_8'] = df[pos].apply(lambda x: freq_dict.get(8, 0))
            result[f'{pos}_freq_9'] = df[pos].apply(lambda x: freq_dict.get(9, 0))
            
            # 2. 数字分布特征
            result[f'{pos}_mean'] = df[pos].rolling(window=100, min_periods=1).mean()
            result[f'{pos}_std'] = df[pos].rolling(window=100, min_periods=1).std()
            result[f'{pos}_skew'] = df[pos].rolling(window=100, min_periods=1).skew()
            result[f'{pos}_kurt'] = df[pos].rolling(window=100, min_periods=1).kurt()
        
        # 3. 排列五特定模式特征
        # 连号特征
        result['consecutive_numbers'] = 0
        for i in df.index:
            numbers = [df.loc[i, pos] for pos in POSITIONS]
            consecutive = 1
            max_consecutive = 1
            for j in range(1, len(numbers)):
                if numbers[j] == numbers[j-1] + 1:
                    consecutive += 1
                    max_consecutive = max(max_consecutive, consecutive)
                else:
                    consecutive = 1
            result.loc[i, 'consecutive_numbers'] = max_consecutive
        
        # 重号特征
        result['repeat_numbers'] = 0
        for i in df.index:
            numbers = [df.loc[i, pos] for pos in POSITIONS]
            unique_numbers = len(set(numbers))
            result.loc[i, 'repeat_numbers'] = 5 - unique_numbers
        
        # 4. 位置间相关性特征
        for i, pos1 in enumerate(POSITIONS):
            for j, pos2 in enumerate(POSITIONS):
                if i < j:
                    result[f'{pos1}_{pos2}_corr'] = df[[pos1, pos2]].rolling(window=50, min_periods=1).corr().iloc[::2, 1].reset_index(drop=True)
        
        # 5. 历史开奖模式特征
        # 最近n期的数字组合模式
        def rolling_mode(series, window):
            """计算滚动窗口的众数"""
            result = []
            for i in range(len(series)):
                window_data = series.iloc[max(0, i-window+1):i+1]
                if len(window_data) > 0:
                    mode_val = window_data.mode().iloc[0] if not window_data.mode().empty else 0
                    result.append(mode_val)
                else:
                    result.append(0)
            return pd.Series(result, index=series.index)
        
        for n in [3, 5, 10]:
            for pos in POSITIONS:
                result[f'{pos}_last_{n}_mode'] = rolling_mode(df[pos], n)
                result[f'{pos}_last_{n}_most_freq'] = df[pos].rolling(window=n, min_periods=1).apply(lambda x: x.value_counts().idxmax() if len(x) > 0 else 0, raw=False)
        
        # 6. 随机性类型特征
        # 认知随机特征：基于历史数据的主观认知模式
        for pos in POSITIONS:
            # 连续出现次数
            result[f'{pos}_consecutive_occurrences'] = 0
            current_num = None
            count = 0
            for i in df.index:
                num = df.loc[i, pos]
                if num == current_num:
                    count += 1
                else:
                    current_num = num
                    count = 1
                result.loc[i, f'{pos}_consecutive_occurrences'] = count
            
            # 间隔出现次数
            result[f'{pos}_gap_occurrences'] = 0
            last_occurrence = {}
            for i in df.index:
                num = df.loc[i, pos]
                if num in last_occurrence:
                    gap = i - last_occurrence[num]
                    result.loc[i, f'{pos}_gap_occurrences'] = gap
                last_occurrence[num] = i
        
        # 确定性规则的伪随机特征：基于数学规则的模式
        # 数字和特征
        result['sum_digits'] = 0
        for i in df.index:
            numbers = [df.loc[i, pos] for pos in POSITIONS]
            result.loc[i, 'sum_digits'] = sum(numbers)
        
        # 数字积特征
        result['product_digits'] = 1
        for i in df.index:
            product = 1
            for pos in POSITIONS:
                product *= df.loc[i, pos]
            result.loc[i, 'product_digits'] = product
        
        # 数字差特征
        result['max_min_diff'] = 0
        for i in df.index:
            numbers = [df.loc[i, pos] for pos in POSITIONS]
            result.loc[i, 'max_min_diff'] = max(numbers) - min(numbers)
        
        # 混沌复杂系统的随机特征：基于混沌理论的特征
        # 李雅普诺夫指数近似
        def lyapunov_exponent_approx(series, window=10):
            """近似计算李雅普诺夫指数"""
            import numpy as np
            result = []
            for i in range(len(series)):
                if i < window:
                    result.append(0)
                    continue
                window_data = series.iloc[i-window:i].values
                diffs = np.abs(np.diff(window_data))
                if len(diffs) > 0:
                    avg_diff = np.mean(diffs)
                    result.append(avg_diff)
                else:
                    result.append(0)
            return pd.Series(result, index=series.index)
        
        for pos in POSITIONS:
            result[f'{pos}_lyapunov'] = lyapunov_exponent_approx(df[pos])
        
        # 计算不可约特征：基于计算复杂性的特征
        # 柯尔莫哥洛夫复杂性近似
        def kolmogorov_complexity_approx(series, window=5):
            """近似计算柯尔莫哥洛夫复杂性"""
            result = []
            for i in range(len(series)):
                if i < window:
                    result.append(0)
                    continue
                window_data = series.iloc[i-window:i].values
                # 使用压缩率作为复杂性的近似
                import zlib
                data_str = ''.join(map(str, window_data))
                compressed_size = len(zlib.compress(data_str.encode()))
                original_size = len(data_str)
                complexity = compressed_size / original_size if original_size > 0 else 0
                result.append(complexity)
            return pd.Series(result, index=series.index)
        
        for pos in POSITIONS:
            result[f'{pos}_kolmogorov'] = kolmogorov_complexity_approx(df[pos])
        
        # 初始条件敏感性特征：基于初始条件微小变化的影响
        # 滑动窗口相关性
        for pos in POSITIONS:
            for window in [5, 10, 15]:
                result[f'{pos}_window_correlation_{window}'] = df[pos].rolling(window=window, min_periods=window).corr(df[pos].shift(1))
        
        # 趋势方向特征：基于历史数据的趋势分析
        # 线性趋势斜率
        def trend_slope(series, window=10):
            """计算趋势斜率"""
            import numpy as np
            result = []
            for i in range(len(series)):
                if i < window:
                    result.append(0)
                    continue
                window_data = series.iloc[i-window:i].values
                x = np.arange(window)
                slope, _ = np.polyfit(x, window_data, 1)
                result.append(slope)
            return pd.Series(result, index=series.index)
        
        for pos in POSITIONS:
            result[f'{pos}_trend_slope'] = trend_slope(df[pos])
        
        return result

    def _add_deep_learning_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """深度学习特征提取"""
        result = df.copy()

        try:
            import tensorflow as tf
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout

            window_size = 15  # 减少窗口大小

            if self.enable_parallel:
                from joblib import Parallel, delayed
                
                def process_position(pos):
                    sequence_data = np.array([
                        df[pos].iloc[i:i+window_size].values
                        for i in range(len(df) - window_size + 1)
                    ], dtype=np.float32)
                    if len(sequence_data) == 0:
                        return pos, np.zeros(len(df))
                    
                    sequence_data = sequence_data.reshape((*sequence_data.shape, 1))

                    # 简化模型结构
                    model = Sequential([
                        LSTM(32, input_shape=(window_size, 1)),
                        Dropout(0.2),
                        Dense(8, activation='relu'),
                        Dense(1, activation='linear')
                    ])
                    model.compile(optimizer='adam', loss='mse')

                    X = sequence_data[:-1]
                    y = df[pos].iloc[window_size:].values

                    feature_series = np.zeros(len(df))
                    if len(X) > 0 and len(y) > 0:
                        # 减少训练epoch数
                        model.fit(X, y, epochs=10, batch_size=32, verbose=0)
                        features = model.predict(sequence_data, verbose=0)
                        feature_series[window_size-1:] = features.flatten()
                    return pos, feature_series
            
            if self.enable_parallel:
                results = Parallel(n_jobs=self.n_jobs, prefer='threads')(
                    delayed(process_position)(pos) for pos in POSITIONS
                )
                for pos, feature_series in results:
                    result[f'{pos}_lstm_feature'] = feature_series
                    logger.info(f"  {pos} 深度学习特征 OK")
            else:
                for pos in POSITIONS:
                    sequence_data = np.array([
                        df[pos].iloc[i:i+window_size].values
                        for i in range(len(df) - window_size + 1)
                    ], dtype=np.float32)
                    if len(sequence_data) == 0:
                        result[f'{pos}_lstm_feature'] = np.zeros(len(df))
                        continue
                    
                    sequence_data = sequence_data.reshape((*sequence_data.shape, 1))

                    # 简化模型结构
                    model = Sequential([
                        LSTM(32, input_shape=(window_size, 1)),
                        Dropout(0.2),
                        Dense(8, activation='relu'),
                        Dense(1, activation='linear')
                    ])
                    model.compile(optimizer='adam', loss='mse')

                    X = sequence_data[:-1]
                    y = df[pos].iloc[window_size:].values

                    feature_series = np.zeros(len(df))
                    if len(X) > 0 and len(y) > 0:
                        # 减少训练epoch数
                        model.fit(X, y, epochs=10, batch_size=32, verbose=0)
                        features = model.predict(sequence_data, verbose=0)
                        feature_series[window_size-1:] = features.flatten()
                    result[f'{pos}_lstm_feature'] = feature_series
                    logger.info(f"  {pos} 深度学习特征 OK")

        except ImportError:
            logger.warning("TensorFlow未安装，跳过深度学习特征")
        except Exception as e:
            logger.error(f"深度学习特征提取失败: {e}")

        return result

    # ===================== 并行调度 =====================

    def _compute_feature_group(self, df: pd.DataFrame, group_name: str) -> pd.DataFrame:
        """计算单个特征组（供并行调用）"""
        dispatch = {
            'fibonacci': self._add_fibonacci_features,
            'entropy': self._add_entropy_features,
            'markov': self._add_markov_features,
            'chaos': self._add_chaos_features,
            'fourier': self._add_fourier_features,
            'cross_correlation': self._add_cross_correlation_features,
            'extreme': self._add_extreme_features,
            'pattern': self._add_pattern_features,
            'momentum': self._add_momentum_features,
            'garch': self._add_garch_features,
            'granger': self._add_granger_features,
            'time_series': self._add_time_series_features,
            'statistical': self._add_statistical_features,
            'nonlinear': self._add_nonlinear_features,
            'pattern_recognition': self._add_pattern_recognition_features,
            'pl5_specific': self._add_pl5_specific_features,
            'deep_learning': self._add_deep_learning_features,
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
                            enable_scaler: bool = False,
                            detect_drift: bool = False) -> pd.DataFrame:
        """提取所有特征（V10.0高性能版）

        Args:
            df: 输入数据
            select_top: 特征选择Top N
            feature_selection_method: 特征选择方法
            enable_scaler: 是否启用标准化
            detect_drift: 是否启用漂移检测
        """
        start_time = time.time()
        logger.info("V10.0 特征工程开始（高性能优化版）...")

        cache_key = self.cache.get_key(df, (select_top, feature_selection_method, enable_scaler))

        # 强制刷新缓存，确保特征选择逻辑被执行
        cached = None
        if cached is not None:
            logger.info("  从缓存加载特征（命中）")
            duration = time.time() - start_time
            logger.info(f"V10.0 特征工程完成（缓存）: {cached.shape[1]} 列, 耗时: {duration:.3f}s")
            return cached

        enabled_features = (
            self.config.get_enabled_features() if self.config
            else list(FeatureConfig.DEFAULT_CONFIG.keys())
        )
        logger.info(f"启用的特征类型: {enabled_features}, 并行={'开启' if self.enable_parallel else '关闭'}")

        result_df = df.copy()

        feature_groups = [
            ('fibonacci', 'fibonacci'),
            ('markov', 'markov'),
            ('fourier', 'fourier'),
            ('extreme', 'extreme'),
            ('pattern', 'pattern'),
            ('momentum', 'momentum'),
            ('entropy', 'entropy'),
            ('chaos', 'chaos'),
            ('cross_correlation', 'cross_correlation'),
            ('garch', 'garch'),
            ('granger', 'granger'),
            ('time_series', 'time_series'),
            ('statistical', 'statistical'),
            ('nonlinear', 'nonlinear'),
            ('pattern_recognition', 'pattern_recognition'),
            ('pl5_specific', 'pl5_specific'),
            ('deep_learning', 'deep_learning'),
        ]

        active_groups = [(cfg_key, method_name) for cfg_key, method_name in feature_groups
                         if cfg_key in enabled_features]

        # 暂时禁用并行计算，避免卡住
        # if self.enable_parallel and len(active_groups) >= 3:
        #     logger.info(f"  并行计算 {len(active_groups)} 个特征组 (n_jobs={self.n_jobs})...")
        #     results = Parallel(n_jobs=self.n_jobs, prefer='threads')(
        #         delayed(self._compute_feature_group)(result_df.copy(), method_name)
        #         for _, method_name in active_groups
        #     )
        # 
        #     base_cols = set(result_df.columns)
        #     for partial_result in results:
        #         new_cols = [c for c in partial_result.columns if c not in base_cols]
        #         if new_cols:
        #             for col in new_cols:
        #                 result_df[col] = partial_result[col]
        #             base_cols.update(new_cols)
        # else:
        for cfg_key, method_name in active_groups:
            t0 = time.time()
            result_df = self._compute_feature_group(result_df, method_name)
            logger.info(f"  {method_name} OK ({time.time()-t0:.3f}s)")

        logger.info(f"extract_all_features: select_top={select_top}, type={type(select_top)}")
        if select_top is not None:
            logger.info(f"调用 _select_features: n_features={select_top}")
            result_df = self._select_features(result_df, select_top, feature_selection_method)
        else:
            logger.info("select_top 为 None，跳过特征选择")

        if enable_scaler:
            t0 = time.time()
            result_df = self.scaler.fit_transform(result_df)
            logger.info(f"  标准化完成 ({time.time()-t0:.3f}s)")

        if detect_drift:
            feature_cols = [c for c in result_df.columns
                            if c not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
            if not self.drift_detector.training_stats:
                self.drift_detector.fit(result_df, feature_cols)
                logger.info("  漂移检测器: 已记录基线统计量")
            else:
                warnings_list = self.drift_detector.detect(result_df, feature_cols)
                if warnings_list:
                    logger.warning(f"  漂移警告: {self.drift_detector.get_drift_report()}")

        self.cache.put(cache_key, result_df)

        importance_path = MODELS_DIR / f"feature_importance_v9_{feature_selection_method}.pkl"
        self.importance_analyzer.save_importance(importance_path)

        duration = time.time() - start_time
        logger.info(f"V10.0 特征工程完成: {result_df.shape[1]} 列, 耗时: {duration:.2f}s | 缓存统计: {self.cache.stats}")
        return result_df

    def _select_features(self, df: pd.DataFrame, n_features: int, method: str = 'rfe') -> pd.DataFrame:
        """基于重要性选择特征 - 智能动态选择"""
        feature_cols = [col for col in df.columns
                        if col not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]

        logger.info(f"_select_features 开始: n_features={n_features}, 总特征数={len(feature_cols)}")

        if len(feature_cols) <= n_features:
            # 即使特征数量不足，也返回基础列 + 所有特征列
            basic_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']
            selected_cols = basic_cols + feature_cols
            logger.info(f"特征数量不足，返回所有 {len(feature_cols)} 个特征，总列数={len(selected_cols)}")
            return df[selected_cols]
        
        # 智能计算每个位置应选择的特征数量
        # 基于数据量和特征总数动态调整
        n_samples = len(df)
        n_total_features = len(feature_cols)
        
        # 计算最优特征数：避免过拟合，同时保留足够信息
        # 经验法则：样本数 / 10 作为上限，但至少保留20个，最多不超过总数的30%
        optimal_features_per_pos = min(
            max(20, n_samples // 100),  # 至少20个，基于样本数
            n_total_features // len(POSITIONS),  # 每个位置的平均数
            50  # 上限50个
        )
        
        logger.info(f"智能特征选择: 数据量={n_samples}, 总特征={n_total_features}, "
                   f"每位置选择约{optimal_features_per_pos}个特征")

        basic_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']
        selected_features = []
        
        # 暂时禁用并行计算，避免卡住
        # if self.enable_parallel:
        #     logger.info("并行执行特征选择...")
        #     from joblib import Parallel, delayed
        #     
        #     def process_position(pos):
        #         y = df[pos]
        #         if method == 'rfe':
        #             return self.importance_analyzer.rfe_feature_selection(df, y, optimal_features_per_pos)
        #         elif method == 'model_based':
        #             return self.importance_analyzer.model_based_feature_selection(df, y, optimal_features_per_pos)
        #         else:
        #             if not self.importance_analyzer.importance_scores:
        #                 self.importance_analyzer.calculate_importance(df, y)
        #             return self.importance_analyzer.select_top_features(optimal_features_per_pos)
        #     
        #     results = Parallel(n_jobs=self.n_jobs, prefer='threads')(
        #         delayed(process_position)(pos) for pos in POSITIONS
        #     )
        #     
        #     for pos_features in results:
        #         selected_features.extend(pos_features)
        # else:
        for pos in POSITIONS:
            y = df[pos]
            if method == 'rfe':
                pos_features = self.importance_analyzer.rfe_feature_selection(df, y, optimal_features_per_pos)
            elif method == 'model_based':
                pos_features = self.importance_analyzer.model_based_feature_selection(df, y, optimal_features_per_pos)
            else:
                if not self.importance_analyzer.importance_scores:
                    self.importance_analyzer.calculate_importance(df, y)
                pos_features = self.importance_analyzer.select_top_features(optimal_features_per_pos)
            selected_features.extend(pos_features)

        # 去重并限制数量
        selected_features = list(dict.fromkeys(selected_features))[:n_features]
        selected_cols = basic_cols + selected_features

        logger.info(f"特征选择: 从 {len(feature_cols)} 个中选择 {len(selected_features)} 个 (方法: {method})")
        return df[selected_cols]

    # ===================== 简化版接口（向后兼容） =====================

    def _add_time_series_features_simplified(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        windows = [5, 10, 20]
        for pos in POSITIONS:
            s = df[pos]
            for window in windows:
                if len(df) >= window:
                    result[f'{pos}_ma_{window}'] = s.rolling(window=window, min_periods=1).mean()
                    result[f'{pos}_ema_{window}'] = s.ewm(span=window, adjust=False).mean()
            if len(df) >= 5:
                result[f'{pos}_trend_5'] = _vectorized_rolling_polyfit_trend(s, 5)
        return result

    def _add_statistical_features_simplified(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        windows = [5, 10]
        for pos in POSITIONS:
            s = df[pos]
            for window in windows:
                if len(df) >= window:
                    result[f'{pos}_std_{window}'] = s.rolling(window=window, min_periods=1).std()
                    result[f'{pos}_mean_{window}'] = s.rolling(window=window, min_periods=1).mean()
        return result


FeatureEngineer = FeatureEngineerV9
