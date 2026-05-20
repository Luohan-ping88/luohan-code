"""
增强Stacking集成器 V1.0
多样性驱动的基学习器选择和层次化Stacking

改进点:
1. 多样性驱动的基学习器选择
2. 加权元学习器集成
3. 层次化Stacking架构
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from sklearn.base import clone
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier, 
    ExtraTreesClassifier, AdaBoostClassifier
)
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import TimeSeriesSplit
from sklearn.calibration import CalibratedClassifierCV
import logging

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

logger = logging.getLogger(__name__)


class DiversityDrivenSelector:
    """
    多样性驱动的基学习器选择器
    
    选择策略:
    1. 计算基学习器间的预测相关性
    2. 选择相关性低、互补性强的子集
    3. 优先选择不同类型的模型
    """
    
    def __init__(self, diversity_threshold: float = 0.7, min_models: int = 2, max_models: int = 4):
        self.diversity_threshold = diversity_threshold
        self.min_models = min_models
        self.max_models = max_models
    
    def select_diverse_models(
        self,
        model_pool: Dict[str, Any],
        X: np.ndarray,
        y: np.ndarray,
        n_select: int = 3
    ) -> Dict[str, Any]:
        """
        选择多样化的模型子集
        
        Args:
            model_pool: 模型池 {名称: 模型实例}
            X: 特征数据
            y: 标签
            n_select: 选择数量
            
        Returns:
            选中的模型 {名称: 模型实例}
        """
        predictions = {}
        model_types = {}
        
        for name, model in model_pool.items():
            try:
                clf = clone(model)
                clf.fit(X[:min(1000, len(X))], y[:min(1000, len(y))])
                pred = clf.predict_proba(X[:min(500, len(X))])
                predictions[name] = pred
                model_types[name] = self._classify_model_type(name)
            except Exception as e:
                logger.warning(f"模型 {name} 训练失败: {e}")
        
        if len(predictions) < self.min_models:
            return model_pool
        
        correlations = self._compute_pairwise_correlations(predictions)
        
        selected = self._greedy_selection(correlations, model_types, n_select)
        
        result = {}
        for name in selected:
            if name in model_pool:
                result[name] = clone(model_pool[name])
        
        logger.info(f"选择了 {len(result)} 个多样化模型: {list(result.keys())}")
        
        return result
    
    def _classify_model_type(self, name: str) -> str:
        """分类模型类型"""
        name_lower = name.lower()
        
        if 'rf' in name_lower or 'forest' in name_lower:
            return 'tree_bagging'
        elif 'lgbm' in name_lower or 'lightgbm' in name_lower:
            return 'tree_boosting'
        elif 'xgb' in name_lower or 'xgboost' in name_lower:
            return 'tree_boosting'
        elif 'et' in name_lower or 'extratree' in name_lower:
            return 'tree_bagging'
        elif 'gb' in name_lower or 'gradient' in name_lower:
            return 'tree_boosting'
        elif 'knn' in name_lower or 'kneighbor' in name_lower:
            return 'distance'
        elif 'lr' in name_lower or 'logistic' in name_lower:
            return 'linear'
        elif 'ridge' in name_lower:
            return 'linear'
        elif 'nb' in name_lower or 'naive' in name_lower or 'bayes' in name_lower:
            return 'probabilistic'
        else:
            return 'other'
    
    def _compute_pairwise_correlations(self, predictions: Dict[str, np.ndarray]) -> Dict[Tuple[str, str], float]:
        """计算预测对之间的相关性"""
        correlations = {}
        names = list(predictions.keys())
        
        for i, name1 in enumerate(names):
            for name2 in names[i+1:]:
                pred1 = predictions[name1]
                pred2 = predictions[name2]
                
                if len(pred1) != len(pred2):
                    continue
                
                argmax1 = np.argmax(pred1, axis=1)
                argmax2 = np.argmax(pred2, axis=1)
                
                agreement = np.mean(argmax1 == argmax2)
                correlation = 2 * agreement - 1
                
                correlations[(name1, name2)] = correlation
        
        return correlations
    
    def _greedy_selection(
        self,
        correlations: Dict[Tuple[str, str], float],
        model_types: Dict[str, str],
        n_select: int
    ) -> List[str]:
        """贪心选择多样化模型"""
        names = list(set(name for pair in correlations.keys() for name in pair))
        
        if len(names) <= n_select:
            return names
        
        type_groups = {}
        for name in names:
            t = model_types.get(name, 'other')
            if t not in type_groups:
                type_groups[t] = []
            type_groups[t].append(name)
        
        selected = []
        remaining = set(names)
        
        for group in ['tree_boosting', 'tree_bagging', 'distance', 'linear', 'probabilistic', 'other']:
            if group in type_groups and type_groups[group]:
                candidates = [n for n in type_groups[group] if n in remaining]
                if candidates:
                    selected.append(candidates[0])
                    remaining.discard(candidates[0])
        
        while len(selected) < n_select and remaining:
            best_name = None
            best_min_corr = float('inf')
            
            for name in remaining:
                min_corr = 1.0
                for sel_name in selected:
                    corr = correlations.get((name, sel_name), correlations.get((sel_name, name), 0))
                    min_corr = min(min_corr, abs(corr))
                
                if min_corr < best_min_corr:
                    best_min_corr = min_corr
                    best_name = name
            
            if best_name and best_min_corr < self.diversity_threshold:
                selected.append(best_name)
                remaining.discard(best_name)
            else:
                selected.append(list(remaining)[0])
                remaining.discard(list(remaining)[0])
        
        return selected[:n_select]


class EnhancedStackingEnsemble:
    """
    增强版Stacking集成
    
    架构:
    Level 1: 多个基学习器 (多样化选择)
    Level 2: 多个元学习器 (集成)
    输出: 加权概率
    """
    
    POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
    
    def __init__(
        self,
        diversity_threshold: float = 0.7,
        cv_folds: int = 5,
        enable_calibration: bool = True
    ):
        self.diversity_threshold = diversity_threshold
        self.cv_folds = cv_folds
        self.enable_calibration = enable_calibration
        
        self.base_models: Dict[str, Any] = {}
        self.meta_models: Dict[str, Any] = {}
        self.meta_weights: Dict[str, float] = {}
        self.position_models: Dict[str, Dict[str, Any]] = {}
        self.position_meta_models: Dict[str, Dict[str, Any]] = {}
        
        self.selector = DiversityDrivenSelector(diversity_threshold=diversity_threshold)
        
        self._init_base_models()
        self._init_meta_models()
    
    def _init_base_models(self):
        """初始化基学习器池"""
        self.base_models = {
            'rf': RandomForestClassifier(
                n_estimators=50, max_depth=8, random_state=42, n_jobs=-1
            ),
            'et': ExtraTreesClassifier(
                n_estimators=50, max_depth=8, random_state=42, n_jobs=-1
            ),
        }
        
        if HAS_LIGHTGBM:
            self.base_models['lgbm'] = LGBMClassifier(
                n_estimators=50, max_depth=6, learning_rate=0.1,
                random_state=42, n_jobs=-1, verbose=-1
            )
        elif HAS_XGBOOST:
            self.base_models['xgb'] = XGBClassifier(
                n_estimators=50, max_depth=6, learning_rate=0.1,
                random_state=42, n_jobs=-1, use_label_encoder=False, eval_metric='mlogloss'
            )
        else:
            self.base_models['gbm'] = GradientBoostingClassifier(
                n_estimators=50, max_depth=6, learning_rate=0.1, random_state=42
            )
        
        self.base_models['knn_5'] = KNeighborsClassifier(n_neighbors=5, n_jobs=-1)
        self.base_models['nb'] = GaussianNB()
    
    def _init_meta_models(self):
        """初始化元学习器"""
        self.meta_models = {
            'lr': LogisticRegression(C=1.0, max_iter=500, solver='lbfgs', random_state=42),
            'ridge': RidgeClassifier(alpha=1.0, random_state=42),
        }
    
    def fit(self, df: pd.DataFrame, feature_cols: List[str], parallel: bool = True):
        """
        训练增强Stacking模型
        
        Args:
            df: 训练数据
            feature_cols: 特征列
            parallel: 是否并行训练
        """
        X = df[feature_cols].fillna(0).values
        
        for pos in self.POSITIONS:
            y = df[pos].values.astype(int)
            
            logger.info(f"训练位置 {pos} 的增强Stacking模型...")
            
            diverse_models = self.selector.select_diverse_models(
                self.base_models, X, y, n_select=3
            )
            self.position_models[pos] = diverse_models
            
            meta_X = self._generate_meta_features(X, y, diverse_models)
            
            self.position_meta_models[pos] = {}
            for meta_name, meta_clf in self.meta_models.items():
                try:
                    meta_clf_copy = clone(meta_clf)
                    meta_clf_copy.fit(meta_X, y)
                    self.position_meta_models[pos][meta_name] = meta_clf_copy
                except Exception as e:
                    logger.warning(f"元学习器 {meta_name} 训练失败: {e}")
            
            if self.enable_calibration and 'lr' in self.position_meta_models[pos]:
                calibrated = CalibratedClassifierCV(
                    self.position_meta_models[pos]['lr'], method='isotonic', cv=3
                )
                calibrated.fit(meta_X, y)
                self.position_meta_models[pos]['lr_calibrated'] = calibrated
        
        logger.info("增强Stacking模型训练完成")
    
    def _generate_meta_features(
        self,
        X: np.ndarray,
        y: np.ndarray,
        models: Dict[str, Any]
    ) -> np.ndarray:
        """生成元特征 (带多样性增强)"""
        tscv = TimeSeriesSplit(n_splits=self.cv_folds)
        
        n_classes = 10
        n_models = len(models)
        meta_features_list = []
        
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train = y[train_idx]
            
            fold_features = []
            
            for name, model in models.items():
                model_copy = clone(model)
                model_copy.fit(X_train, y_train)
                
                proba = model_copy.predict_proba(X_val)
                
                padded_proba = np.zeros((len(val_idx), n_classes))
                for i, (p, c) in enumerate(zip(proba, model_copy.classes_)):
                    if 0 <= c < n_classes:
                        padded_proba[:, c] = p
                
                fold_features.append(padded_proba)
                
                pred_class = model_copy.predict(X_val)
                class_encoding = np.zeros((len(val_idx), n_classes))
                for i, c in enumerate(pred_class):
                    if 0 <= c < n_classes:
                        class_encoding[i, c] = 1
                fold_features.append(class_encoding)
            
            fold_meta = np.hstack(fold_features)
            meta_features_list.append(fold_meta)
        
        meta_X = np.vstack(meta_features_list)
        
        proba_mean = np.mean([f[:, :n_classes] for f in meta_features_list], axis=0)
        proba_std = np.std([f[:, :n_classes] for f in meta_features_list], axis=0)
        
        diversity_features = np.zeros((len(meta_X), n_models))
        for i in range(n_models):
            start, end = i * n_classes, (i + 1) * n_classes
            diversity_features[:, i] = np.std(meta_X[:, start:end], axis=1)
        
        final_meta = np.hstack([meta_X, proba_mean, proba_std, diversity_features])
        
        return final_meta
    
    def predict_proba_position(self, pos: str, X: np.ndarray) -> np.ndarray:
        """
        预测单个位置的概率
        
        Args:
            pos: 位置名称
            X: 特征向量
            
        Returns:
            10维概率分布
        """
        if pos not in self.position_models:
            return np.ones(10) / 10
        
        models = self.position_models[pos]
        meta_features = []
        
        X_2d = X.reshape(1, -1) if X.ndim == 1 else X
        
        for name, model in models.items():
            proba = model.predict_proba(X_2d)
            
            padded_proba = np.zeros((len(X_2d), 10))
            for i, (p, c) in enumerate(zip(proba, model.classes_)):
                if 0 <= c < 10:
                    padded_proba[:, c] = p
            meta_features.append(padded_proba)
            
            pred_class = model.predict(X_2d)
            class_encoding = np.zeros((len(X_2d), 10))
            for i, c in enumerate(pred_class):
                if 0 <= c < 10:
                    class_encoding[i, c] = 1
            meta_features.append(class_encoding)
        
        meta_X = np.hstack(meta_features)
        
        proba_mean = np.mean([f for f in meta_features[::2]], axis=0)
        proba_std = np.std([f for f in meta_features[::2]], axis=0)
        diversity_features = np.zeros((len(X_2d), len(models)))
        for i in range(len(models)):
            start = i * 10
            end = (i + 1) * 10
            diversity_features[:, i] = np.std(meta_X[:, start:end], axis=1)
        
        final_meta = np.hstack([meta_X, proba_mean, proba_std, diversity_features])
        
        meta_predictions = []
        for meta_name, meta_clf in self.position_meta_models[pos].items():
            if hasattr(meta_clf, 'predict_proba'):
                pred = meta_clf.predict_proba(final_meta)[0]
            else:
                pred = np.zeros(10)
                pred_class = meta_clf.predict(final_meta)[0]
                if 0 <= pred_class < 10:
                    pred[pred_class] = 1.0
            
            meta_predictions.append(pred)
        
        if not meta_predictions:
            return np.ones(10) / 10
        
        avg_pred = np.mean(meta_predictions, axis=0)
        avg_pred = avg_pred / (avg_pred.sum() + 1e-12)
        
        return avg_pred
    
    def predict(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """
        预测所有位置
        
        Returns:
            {位置: 概率分布}
        """
        predictions = {}
        
        for pos in self.POSITIONS:
            predictions[pos] = self.predict_proba_position(pos, X)
        
        return predictions
