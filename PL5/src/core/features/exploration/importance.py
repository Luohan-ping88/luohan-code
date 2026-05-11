"""
特征重要性评估模块
支持多种特征重要性评估方法：
- SHAP特征重要性
- LIME特征重要性
- Permutation Importance
- 基于模型的特征重要性
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
import warnings
import logging
from pathlib import Path
import pickle
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.base import BaseEstimator

logger = logging.getLogger(__name__)


class FeatureImportanceEvaluator:
    """特征重要性评估器 - 支持多种评估方法"""

    SUPPORTED_METHODS = ["shap", "lime", "permutation", "model_based"]

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.importance_results: Dict[str, Dict[str, float]] = {}
        self._shap_available = False
        self._lime_available = False

        try:
            import shap

            self._shap_available = True
        except ImportError:
            logger.warning("SHAP库未安装，SHAP特征重要性不可用")

        try:
            import lime
            import lime.lime_tabular

            self._lime_available = True
        except ImportError:
            logger.warning("LIME库未安装，LIME特征重要性不可用")

    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        method: str = "model_based",
        model: Optional[BaseEstimator] = None,
        feature_cols: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, float]:
        """
        评估特征重要性

        Args:
            X: 特征数据
            y: 目标变量
            method: 评估方法 ('shap', 'lime', 'permutation', 'model_based')
            model: 可选的模型对象，若不提供则使用默认的RandomForest
            feature_cols: 要评估的特征列，默认使用所有数值列
            **kwargs: 各方法的额外参数

        Returns:
            特征重要性字典，按重要性降序排列
        """
        if method not in self.SUPPORTED_METHODS:
            raise ValueError(f"不支持的方法: {method}，可选: {self.SUPPORTED_METHODS}")

        if feature_cols is None:
            feature_cols = [col for col in X.columns if np.issubdtype(X[col].dtype, np.number)]

        X_features = X[feature_cols].fillna(0)

        if method == "shap":
            importance = self._shap_importance(X_features, y, model, **kwargs)
        elif method == "lime":
            importance = self._lime_importance(X_features, y, model, **kwargs)
        elif method == "permutation":
            importance = self._permutation_importance(X_features, y, model, **kwargs)
        elif method == "model_based":
            importance = self._model_based_importance(X_features, y, model, **kwargs)
        else:
            raise ValueError(f"未知方法: {method}")

        self.importance_results[method] = importance
        return importance

    def _model_based_importance(
        self, X: pd.DataFrame, y: pd.Series, model: Optional[BaseEstimator] = None, **kwargs
    ) -> Dict[str, float]:
        """基于模型的特征重要性（使用RandomForest）"""
        if model is None:
            is_classification = len(np.unique(y)) <= 10
            if is_classification:
                model = RandomForestClassifier(
                    n_estimators=100, max_depth=10, random_state=self.random_state, n_jobs=-1
                )
            else:
                model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=self.random_state, n_jobs=-1)

        model.fit(X, y)

        if hasattr(model, "feature_importances_"):
            importance = dict(zip(X.columns, model.feature_importances_))
        else:
            raise ValueError("模型不支持feature_importances_属性")

        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    def _permutation_importance(
        self, X: pd.DataFrame, y: pd.Series, model: Optional[BaseEstimator] = None, n_repeats: int = 10, **kwargs
    ) -> Dict[str, float]:
        """Permutation Importance"""
        if model is None:
            is_classification = len(np.unique(y)) <= 10
            if is_classification:
                model = RandomForestClassifier(
                    n_estimators=100, max_depth=10, random_state=self.random_state, n_jobs=-1
                )
            else:
                model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=self.random_state, n_jobs=-1)

        model.fit(X, y)

        result = permutation_importance(model, X, y, n_repeats=n_repeats, random_state=self.random_state, n_jobs=-1)

        importance = dict(zip(X.columns, result.importances_mean))
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    def _shap_importance(
        self, X: pd.DataFrame, y: pd.Series, model: Optional[BaseEstimator] = None, **kwargs
    ) -> Dict[str, float]:
        """SHAP特征重要性"""
        if not self._shap_available:
            raise ImportError("SHAP库未安装，请先安装: pip install shap")

        import shap

        if model is None:
            is_classification = len(np.unique(y)) <= 10
            if is_classification:
                model = RandomForestClassifier(
                    n_estimators=100, max_depth=10, random_state=self.random_state, n_jobs=-1
                )
            else:
                model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=self.random_state, n_jobs=-1)

        model.fit(X, y)

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)

        if isinstance(shap_values, list):
            shap_values = np.abs(shap_values).mean(axis=0)
        else:
            shap_values = np.abs(shap_values).mean(axis=0)

        importance = dict(zip(X.columns, shap_values))
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    def _lime_importance(
        self, X: pd.DataFrame, y: pd.Series, model: Optional[BaseEstimator] = None, sample_size: int = 100, **kwargs
    ) -> Dict[str, float]:
        """LIME特征重要性"""
        if not self._lime_available:
            raise ImportError("LIME库未安装，请先安装: pip install lime")

        import lime.lime_tabular

        if model is None:
            is_classification = len(np.unique(y)) <= 10
            if is_classification:
                model = RandomForestClassifier(
                    n_estimators=100, max_depth=10, random_state=self.random_state, n_jobs=-1
                )
            else:
                model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=self.random_state, n_jobs=-1)

        model.fit(X, y)

        is_classification = hasattr(model, "predict_proba")
        predict_fn = model.predict_proba if is_classification else model.predict

        explainer = lime.lime_tabular.LimeTabularExplainer(
            X.values,
            feature_names=list(X.columns),
            mode="classification" if is_classification else "regression",
            random_state=self.random_state,
        )

        importance_scores = np.zeros(len(X.columns))
        sample_indices = np.random.choice(len(X), min(sample_size, len(X)), replace=False)

        for idx in sample_indices:
            exp = explainer.explain_instance(X.values[idx], predict_fn, num_features=len(X.columns))
            for feature_idx, weight in exp.as_map()[1 if is_classification else 0]:
                importance_scores[feature_idx] += abs(weight)

        importance_scores /= len(sample_indices)
        importance = dict(zip(X.columns, importance_scores))
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    def ensemble_importance(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        methods: Optional[List[str]] = None,
        weights: Optional[List[float]] = None,
        **kwargs,
    ) -> Dict[str, float]:
        """
        集成多种方法的特征重要性

        Args:
            X: 特征数据
            y: 目标变量
            methods: 要集成的方法列表
            weights: 各方法的权重，默认等权重
            **kwargs: 各方法的额外参数

        Returns:
            集成后的特征重要性
        """
        if methods is None:
            methods = [m for m in self.SUPPORTED_METHODS if self._is_method_available(m)]

        if weights is None:
            weights = [1.0 / len(methods)] * len(methods)

        if len(methods) != len(weights):
            raise ValueError("方法数量和权重数量不匹配")

        all_importances = {}
        for method in methods:
            try:
                imp = self.evaluate(X, y, method, **kwargs)
                all_importances[method] = imp
            except Exception as e:
                logger.warning(f"方法 {method} 执行失败: {e}")

        if not all_importances:
            raise ValueError("所有方法都执行失败")

        normalized_importances = {}
        for method, imp in all_importances.items():
            max_val = max(imp.values()) if imp.values() else 1.0
            normalized_importances[method] = {k: v / max_val for k, v in imp.items()}

        ensemble_imp = {}
        for method, weight in zip(methods, weights):
            if method not in normalized_importances:
                continue
            for feature, score in normalized_importances[method].items():
                if feature not in ensemble_imp:
                    ensemble_imp[feature] = 0.0
                ensemble_imp[feature] += score * weight

        return dict(sorted(ensemble_imp.items(), key=lambda x: x[1], reverse=True))

    def _is_method_available(self, method: str) -> bool:
        """检查方法是否可用"""
        if method == "shap":
            return self._shap_available
        elif method == "lime":
            return self._lime_available
        return True

    def save_results(self, filepath: Path):
        """保存评估结果"""
        with open(filepath, "wb") as f:
            pickle.dump(self.importance_results, f)
        logger.info(f"特征重要性结果已保存: {filepath}")

    def load_results(self, filepath: Path):
        """加载评估结果"""
        with open(filepath, "rb") as f:
            self.importance_results = pickle.load(f)
        logger.info(f"特征重要性结果已加载: {filepath}")

    def get_top_features(
        self, importance: Dict[str, float], n: int = 20, threshold: Optional[float] = None
    ) -> List[str]:
        """
        获取Top N特征

        Args:
            importance: 特征重要性字典
            n: 要选择的特征数量
            threshold: 重要性阈值，可选

        Returns:
            特征列表
        """
        features = list(importance.keys())[:n]
        if threshold is not None:
            features = [f for f in features if importance[f] >= threshold]
        return features
