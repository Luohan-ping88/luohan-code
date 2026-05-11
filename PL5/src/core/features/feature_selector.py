"""
多方法特征选择器 - 整合多种特征重要性评估方法，通过投票机制智能选择最优特征子集
"""

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
import warnings
import logging

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import (
    mutual_info_classif,
    chi2,
    f_classif,
    RFE,
    SelectKBest,
    VarianceThreshold,
)
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import cross_val_score
from sklearn.linear_model import LogisticRegression

from .config import setup_logging, MODELS_DIR

logger = setup_logging(__name__)


class MultiMethodFeatureSelector:
    """多方法特征选择器 - 通过多方法投票机制实现智能特征选择"""

    METHOD_ALIASES = {
        "rf": "random_forest",
        "random_forest": "random_forest",
        "mi": "mutual_info",
        "mutual_info": "mutual_info",
        "rfe": "rfe",
        "chi2": "chi2",
    }

    DEFAULT_WEIGHTS = {
        "random_forest": 1.0,
        "mutual_info": 0.9,
        "rfe": 0.8,
        "chi2": 0.7,
    }

    def __init__(
        self,
        methods: List[str] = ["rf", "mi", "rfe", "chi2"],
        correlation_threshold: float = 0.95,
        weights: Optional[Dict[str, float]] = None,
        exclude_cols: Optional[List[str]] = None,
        random_state: int = 42,
    ):
        self.methods = [self.METHOD_ALIASES.get(m, m) for m in methods]
        self.methods = [m for m in self.methods if m in self.DEFAULT_WEIGHTS]
        if not self.methods:
            raise ValueError("至少需要指定一个有效的特征选择方法")
        self.correlation_threshold = correlation_threshold
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}
        self.exclude_cols = exclude_cols or ["period", "full_number"]
        self.random_state = random_state

        self._fitted = False
        self._feature_names: List[str] = []
        self._method_rankings: Dict[str, List[str]] = {}
        self._method_scores: Dict[str, Dict[str, float]] = {}
        self._vote_scores: Dict[str, float] = {}
        self._correlation_matrix: Optional[pd.DataFrame] = None
        self._removed_correlated: List[Tuple[str, str]] = []
        self._optimal_n_features: Optional[int] = None
        self._elbow_curve: Optional[Dict[int, float]] = None
        self._selected_features: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "MultiMethodFeatureSelector":
        logger.info(f"开始多方法特征选择，共 {X.shape[1]} 个特征，使用方法: {self.methods}")

        feature_cols = self._get_feature_columns(X)
        X_features = X[feature_cols].fillna(0).copy()

        if len(feature_cols) < 2:
            raise ValueError("可用特征数量不足")

        for method in self.methods:
            logger.info(f"  计算方法 [{method}] 的特征重要性...")
            scores = self._compute_method_scores(method, X_features, y, feature_cols)
            self._method_scores[method] = scores
            ranking = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
            self._method_rankings[method] = ranking
            logger.info(f"    方法 [{method}] 完成，Top-5: {ranking[:5]}")

        self._compute_vote_scores()
        self._correlation_matrix = self._compute_correlation_matrix(X_features, feature_cols)
        self._remove_highly_correlated()
        self._determine_optimal_n_features(X_features, y)

        self._feature_names = list(self._vote_scores.keys())
        self._fitted = True
        logger.info(f"特征选择拟合完成，最终候选特征数: {len(self._selected_features)}")
        return self

    def transform(
        self,
        X: pd.DataFrame,
        n_features: Optional[int] = None,
    ) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("请先调用 fit() 拟合选择器")
        target_n = n_features or self._optimal_n_features or min(100, len(self._selected_features))
        target_n = min(target_n, len(self._selected_features))
        selected = sorted(
            self._selected_features,
            key=lambda f: self._vote_scores.get(f, 0),
            reverse=True,
        )[:target_n]
        keep_cols = [c for c in X.columns if c in self.exclude_cols] + selected
        result = X[[c for c in keep_cols if c in X.columns]].copy()
        logger.info(f"transform 完成: 从 {len(self._feature_names)} 个原始特征中选择 {len(selected)} 个")
        return result

    def fit_transform(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_features: Optional[int] = None,
    ) -> pd.DataFrame:
        return self.fit(X, y).transform(X, n_features=n_features)

    def get_feature_importance_report(self) -> Dict:
        if not self._fitted:
            raise RuntimeError("请先调用 fit() 拟合选择器")
        report = {
            "total_original_features": len(self._feature_names),
            "total_after_correlation_filter": len(self._selected_features),
            "methods_used": self.methods,
            "weights_used": {m: self.weights[m] for m in self.methods},
            "optimal_n_features": self._optimal_n_features,
            "correlation_threshold": self.correlation_threshold,
            "removed_correlated_pairs": self._removed_correlated,
            "method_rankings": {},
            "vote_ranking": [],
            "top_50_features": [],
        }
        for method, ranking in self._method_rankings.items():
            report["method_rankings"][method] = ranking[:50]
        vote_sorted = sorted(self._vote_scores.items(), key=lambda x: x[1], reverse=True)
        report["vote_ranking"] = [(f, round(s, 6)) for f, s in vote_sorted]
        report["top_50_features"] = [(f, round(s, 6)) for f, s in vote_sorted[:50]]
        if self._elbow_curve is not None:
            report["elbow_curve"] = dict(sorted(self._elbow_curve.items()))
        return report

    def suggest_optimal_n_features(self) -> int:
        if not self._fitted:
            raise RuntimeError("请先调用 fit() 拟合选择器")
        return self._optimal_n_features or len(self._selected_features)

    @property
    def selected_features(self) -> List[str]:
        if not self._fitted:
            raise RuntimeError("请先调用 fit() 拟合选择器")
        return list(self._selected_features)

    @property
    def vote_scores(self) -> Dict[str, float]:
        if not self._fitted:
            raise RuntimeError("请先调用 fit() 拟合选择器")
        return dict(self._vote_scores)

    def save_selector(self, filepath: Union[str, Path]):
        data = {
            "_fitted": self._fitted,
            "_feature_names": self._feature_names,
            "_method_rankings": self._method_rankings,
            "_method_scores": {k: {kk: float(vv) for kk, vv in v.items()} for k, v in self._method_scores.items()},
            "_vote_scores": {k: float(v) for k, v in self._vote_scores.items()},
            "_selected_features": self._selected_features,
            "_removed_correlated": self._removed_correlated,
            "_optimal_n_features": self._optimal_n_features,
            "_elbow_curve": self._elbow_curve,
            "methods": self.methods,
            "correlation_threshold": self.correlation_threshold,
            "weights": self.weights,
            "exclude_cols": self.exclude_cols,
        }
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        import pickle

        with open(filepath, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"特征选择器已保存: {filepath}")

    def load_selector(self, filepath: Union[str, Path]):
        import pickle

        with open(filepath, "rb") as f:
            data = pickle.load(f)
        self._fitted = data["_fitted"]
        self._feature_names = data["_feature_names"]
        self._method_rankings = data["_method_rankings"]
        self._method_scores = data["_method_scores"]
        self._vote_scores = data["_vote_scores"]
        self._selected_features = data["_selected_features"]
        self._removed_correlated = data["_removed_correlated"]
        self._optimal_n_features = data["_optimal_n_features"]
        self._elbow_curve = data["_elbow_curve"]
        self.methods = data["methods"]
        self.correlation_threshold = data["correlation_threshold"]
        self.weights = data["weights"]
        self.exclude_cols = data["exclude_cols"]
        logger.info(f"特征选择器已加载: {filepath}")

    # ==================== 内部方法 ====================

    def _get_feature_columns(self, X: pd.DataFrame) -> List[str]:
        return [c for c in X.columns if c not in self.exclude_cols]

    def _normalize_scores(self, scores: Dict[str, float]) -> Dict[str, float]:
        values = np.array(list(scores.values()), dtype=float)
        if values.max() == values.min() == 0:
            return {k: 0.0 for k in scores}
        scaler = MinMaxScaler()
        normalized = scaler.fit_transform(values.reshape(-1, 1)).flatten()
        return dict(zip(scores.keys(), normalized))

    def _compute_method_scores(
        self,
        method: str,
        X: pd.DataFrame,
        y: pd.Series,
        feature_cols: List[str],
    ) -> Dict[str, float]:
        if method == "random_forest":
            return self._rf_importance(X, y, feature_cols)
        elif method == "mutual_info":
            return self._mi_importance(X, y, feature_cols)
        elif method == "rfe":
            return self._rfe_importance(X, y, feature_cols)
        elif method == "chi2":
            return self._chi2_importance(X, y, feature_cols)
        else:
            raise ValueError(f"未知方法: {method}")

    def _rf_importance(self, X: pd.DataFrame, y: pd.Series, feature_cols: List[str]) -> Dict[str, float]:
        model = RandomForestClassifier(
            n_estimators=50,
            max_depth=10,
            random_state=self.random_state,
            n_jobs=-1,
        )
        model.fit(X.values, y.values)
        return dict(zip(feature_cols, model.feature_importances_))

    def _mi_importance(self, X: pd.DataFrame, y: pd.Series, feature_cols: List[str]) -> Dict[str, float]:
        mi_scores = mutual_info_classif(X.values, y.values, random_state=self.random_state)
        return dict(zip(feature_cols, mi_scores))

    def _rfe_importance(self, X: pd.DataFrame, y: pd.Series, feature_cols: List[str]) -> Dict[str, float]:
        estimator = RandomForestClassifier(
            n_estimators=30,
            max_depth=8,
            random_state=self.random_state,
            n_jobs=-1,
        )
        step = max(1, len(feature_cols) // 20)
        rfe = RFE(estimator=estimator, n_features_to_select=max(1, len(feature_cols) // 2), step=step)
        rfe.fit(X.values, y.values)
        rankings = rfe.ranking_
        max_rank = rankings.max()
        scores = {col: (max_rank - rank + 1) / max_rank for col, rank in zip(feature_cols, rankings)}
        return scores

    def _chi2_importance(self, X: pd.DataFrame, y: pd.Series, feature_cols: List[str]) -> Dict[str, float]:
        X_shifted = X.copy()
        for col in X_shifted.columns:
            min_val = X_shifted[col].min()
            if min_val < 0:
                X_shifted[col] -= min_val
        try:
            chi2_stats, _ = chi2(X_shifted.values, y.values)
            return dict(zip(feature_cols, chi2_stats))
        except Exception:
            f_vals, _ = f_classif(X.values, y.values)
            return dict(zip(feature_cols, f_vals))

    def _compute_vote_scores(self):
        self._vote_scores = {}
        all_features = set()
        for scores in self._method_scores.values():
            all_features.update(scores.keys())
        for feature in all_features:
            weighted_sum = 0.0
            total_weight = 0.0
            for method in self.methods:
                if feature in self._method_scores[method]:
                    w = self.weights.get(method, 1.0)
                    norm_score = self._normalize_scores(self._method_scores[method])
                    weighted_sum += w * norm_score[feature]
                    total_weight += w
            self._vote_scores[feature] = weighted_sum / total_weight if total_weight > 0 else 0.0
        logger.info(f"投票得分计算完成，涉及 {len(self._vote_scores)} 个特征")

    def _compute_correlation_matrix(self, X: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
        logger.info("计算特征间相关系数矩阵...")
        corr_matrix = X[feature_cols].corr(method="pearson").abs()
        return corr_matrix

    def _remove_highly_correlated(self):
        self._removed_correlated = []
        features_to_remove = set()
        features_by_vote = sorted(
            self._vote_scores.keys(),
            key=lambda f: self._vote_scores[f],
            reverse=True,
        )
        for i, feat_a in enumerate(features_by_vote):
            if feat_a in features_to_remove:
                continue
            for feat_b in features_by_vote[i + 1 :]:
                if feat_b in features_to_remove:
                    continue
                if self._correlation_matrix is not None:
                    try:
                        corr_val = self._correlation_matrix.loc[feat_a, feat_b]
                        if pd.isna(corr_val):
                            corr_val = 0.0
                    except (KeyError, IndexError):
                        corr_val = 0.0
                    if isinstance(corr_val, (int, float)) and corr_val >= self.correlation_threshold:
                        features_to_remove.add(feat_b)
                        self._removed_correlated.append((feat_a, feat_b))
        self._selected_features = [f for f in features_by_vote if f not in features_to_remove]
        logger.info(
            f"相关性过滤完成: 阈值={self.correlation_threshold}, "
            f"移除 {len(self._removed_correlated)} 对高相关性特征, "
            f"剩余 {len(self._selected_features)} 个"
        )

    def _determine_optimal_n_features(self, X: pd.DataFrame, y: pd.Series):
        logger.info("使用肘部法则确定最优特征数量...")
        n_total = len(self._selected_features)
        if n_total <= 10:
            self._optimal_n_features = n_total
            return
        max_test = min(n_total, 300)
        step = max(1, max_test // 30)
        test_points = list(range(step, max_test + 1, step))
        if max_test not in test_points:
            test_points.append(max_test)
        sorted_features = sorted(
            self._selected_features,
            key=lambda f: self._vote_scores[f],
            reverse=True,
        )
        cumulative_scores = []
        for n in test_points:
            top_n = sorted_features[:n]
            score_sum = sum(self._vote_scores.get(f, 0) for f in top_n)
            cumulative_scores.append(score_sum)
        self._elbow_curve = dict(zip(test_points, cumulative_scores))
        elbow_idx = self._find_elbow_point(list(cumulative_scores), test_points)
        self._optimal_n_features = test_points[elbow_idx] if elbow_idx is not None else min(100, n_total)
        logger.info(f"肘部法则分析完成，建议最优特征数量: {self._optimal_n_features}")

    def _find_elbow_point(self, scores: List[float], points: List[int]) -> Optional[int]:
        if len(scores) < 4:
            return len(scores) - 1
        coords = np.array(list(zip(points, scores)))
        p1 = coords[0]
        pn = coords[-1]
        line_vec = pn - p1
        line_len = np.linalg.norm(line_vec)
        if line_len < 1e-9:
            return len(coords) // 2
        unit_line = line_vec / line_len
        distances = []
        for coord in coords[1:-1]:
            vec = coord - p1
            proj_len = np.dot(vec, unit_line)
            proj = unit_line * proj_len
            perp = vec - proj
            dist = np.linalg.norm(perp)
            distances.append(dist)
        if not distances:
            return len(coords) // 2
        elbow_idx = int(np.argmax(distances)) + 1
        return elbow_idx
