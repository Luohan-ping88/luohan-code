"""
增强型预测器 V10.0 - 集成RL优化、贝叶斯推断、高级时序模型
增强: 统一错误分类、结构化日志、错误恢复机制
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import pickle
import logging
import time
from datetime import datetime
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, ExtraTreesClassifier, AdaBoostClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.model_selection import TimeSeriesSplit, cross_val_score

try:
    from lightgbm import LGBMClassifier
    _HAS_LIGHTGBM = True
except ImportError:
    _HAS_LIGHTGBM = False

try:
    from xgboost import XGBClassifier
    _HAS_XGBOOST = True
except ImportError:
    _HAS_XGBOOST = False

from src.core.models.advanced_sequence import HiddenMarkovModel, MultivariateCopula, BayesianStructuralTimeSeries
from src.core.config import ModelConfig, get_model_config

_HAS_RL = False
ModelWeightRLOptimizer = None
ThompsonSamplingOptimizer = None
BayesianEnsemble = None

def _load_rl_modules():
    global _HAS_RL, ModelWeightRLOptimizer, ThompsonSamplingOptimizer, BayesianEnsemble
    if _HAS_RL:
        return
    try:
        from src.core.rl import ModelWeightRLOptimizer, ThompsonSamplingOptimizer
        from src.core.rl.bayesian_inference import BayesianEnsemble
        _HAS_RL = True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"RL模块加载失败，将使用备用方案: {e}")
        _HAS_RL = False
from src.core.utils.errors import (
    ModelError, ModelLoadError, ModelSaveError, ModelPredictionError,
    ModelTrainingError, ConfigError, ConfigSafeLoader,
    StructuredLogger, structured_logger, prediction_cache,
    handle_model_prediction_failure, retry_with_exponential_backoff,
    PL5BaseError, ErrorSeverity
)
from src.core.models.model_version_manager import (
    ModelVersionManager, CURRENT_VERSION, MODEL_FILENAME, VersionChangeLog
)

logger = logging.getLogger(__name__)

POSITIONS = ["wan", "qian", "bai", "shi", "ge"]


class StackingEnsemble:
    """Stacking集成模型 - 增强版 V2

    改进点:
    - 可配置元学习器 (LogisticRegression / SGDClassifier-ElasticNet)
    - 交叉验证折数从3增加到5
    - 增强元特征工程: 预测概率标准差 + 基学习器一致性指标
    - 元学习器自动选择机制 (基于CV分数)
    """

    DEFAULT_BASE_CONFIG = {
        "n_estimators": 100,
        "max_depth": 10,
        "random_state": 42,
        "n_jobs": -1,
        "learning_rate": 0.06,
        "reg_alpha": 0.1,        # L1正则化
        "reg_lambda": 1.0,       # L2正则化
        "min_child_weight": 5,   # 最小子权重增强稳定性
        "subsample": 0.8,        # 行采样比例
        "colsample_bytree": 0.8, # 列采样比例
    }

    DEFAULT_META_CONFIG = {
        "type": "logistic",
        "C": 1.0,
        "max_iter": 500,
        "l1_ratio": 0.5,
        "alpha": 0.0001,
        "cv_folds": 5,
        "auto_select": True,
        "enable_meta_features": True,
    }

    @classmethod
    def _get_model_configs(cls, config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """根据配置获取基学习器配置字典（不包含lambda，可序列化）

        修复: 不再对 n_estimators 和 max_depth 执行 //2 缩放，
        配置值即为实际使用的值，确保配置生效。
        """
        n_est = config.get("n_estimators", cls.DEFAULT_BASE_CONFIG["n_estimators"])
        max_d = config.get("max_depth", cls.DEFAULT_BASE_CONFIG["max_depth"])
        rs = config.get("random_state", cls.DEFAULT_BASE_CONFIG["random_state"])
        n_jobs = config.get("n_jobs", cls.DEFAULT_BASE_CONFIG["n_jobs"])
        lr = config.get("learning_rate", cls.DEFAULT_BASE_CONFIG["learning_rate"])

        model_configs = {
            "rf": {
                "class": RandomForestClassifier,
                "params": {
                    "n_estimators": n_est, "max_depth": max_d,
                    "random_state": rs, "n_jobs": n_jobs
                }
            },
        }

        # 添加一个额外模型以保持多样性
        if _HAS_LIGHTGBM:
            model_configs["lgbm"] = {
                "class": LGBMClassifier,
                "params": {
                    "n_estimators": n_est, "max_depth": max_d,
                    "random_state": rs, "n_jobs": n_jobs,
                    "learning_rate": lr, "verbose": -1,
                    "reg_alpha": config.get("reg_alpha", 0.1),
                    "reg_lambda": config.get("reg_lambda", 1.0),
                    "min_child_weight": config.get("min_child_weight", 5),
                    "subsample": config.get("subsample", 0.8),
                    "colsample_bytree": config.get("colsample_bytree", 0.8),
                }
            }
        elif _HAS_XGBOOST:
            model_configs["xgb"] = {
                "class": XGBClassifier,
                "params": {
                    "n_estimators": n_est, "max_depth": max_d,
                    "random_state": rs, "n_jobs": n_jobs,
                    "learning_rate": lr, "use_label_encoder": False,
                    "eval_metric": "mlogloss", "verbosity": 0,
                    "reg_alpha": config.get("reg_alpha", 0.1),
                    "reg_lambda": config.get("reg_lambda", 1.0),
                    "min_child_weight": config.get("min_child_weight", 5),
                    "subsample": config.get("subsample", 0.8),
                    "colsample_bytree": config.get("colsample_bytree", 0.8),
                }
            }
        else:
            model_configs["gbm"] = {
                "class": GradientBoostingClassifier,
                "params": {
                    "n_estimators": n_est, "max_depth": max_d,
                    "random_state": rs, "learning_rate": lr
                }
            }

        return model_configs

    @classmethod
    def _build_base_models(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """根据配置构建基学习器字典（用于训练时）

        使用默认参数 c=cfg 在定义时捕获循环变量当前值（而非延迟绑定），
        确保每个基学习器获得正确的独立配置。
        """
        model_configs = cls._get_model_configs(config)
        models = {}
        for name, cfg in model_configs.items():
            models[name] = lambda c=cfg: c["class"](**c["params"])
        return models

    @classmethod
    def _build_meta_learner(cls, meta_config: Dict[str, Any]):
        """根据配置构建元学习器"""
        meta_type = meta_config.get("type", "logistic")
        rs = 42

        if meta_type == "elasticnet" or meta_type == "sgd":
            return SGDClassifier(
                loss="modified_huber",
                penalty="elasticnet",
                alpha=meta_config.get("alpha", 0.0001),
                l1_ratio=meta_config.get("l1_ratio", 0.5),
                max_iter=meta_config.get("max_iter", 1000),
                random_state=rs,
                warm_start=True,
            )
        else:
            return LogisticRegression(
                C=meta_config.get("C", 1.0),
                max_iter=meta_config.get("max_iter", 500),
                solver="lbfgs",
                random_state=rs,
            )

    @classmethod
    def _compute_enhanced_meta_features(cls, oof_probas: np.ndarray, n_base: int, n_classes: int = 10) -> np.ndarray:
        """计算增强元特征: 原始概率 + 标准差 + 一致性指标

        Args:
            oof_probas: shape (n_samples, n_base * n_classes) 基学习器OOF预测概率
            n_base: 基学习器数量
            n_classes: 分类数

        Returns:
            enhanced_meta_X: 增强后的元特征矩阵
        """
        n_samples = oof_probas.shape[0]
        base_proba = oof_probas.reshape(n_samples, n_base, n_classes)

        extra_features = []

        proba_std = np.std(base_proba, axis=1)
        extra_features.append(proba_std)

        proba_mean = np.mean(base_proba, axis=1)
        entropy_per_learner = -np.sum(base_proba * np.log(base_proba + 1e-12), axis=2)
        avg_entropy = np.mean(entropy_per_learner, axis=1)
        extra_features.append(avg_entropy.reshape(-1, 1))

        pred_labels = np.argmax(base_proba, axis=2)
        mode_pred = np.apply_along_axis(lambda x: np.bincount(x, minlength=n_classes).argmax(), 1, pred_labels)
        agreement = np.mean(pred_labels == mode_pred[:, None], axis=1)
        extra_features.append(agreement.reshape(-1, 1))

        pairwise_corr = []
        for i in range(n_base):
            for j in range(i + 1, n_base):
                corr = np.corrcoef(base_proba[:, i, :].ravel(), base_proba[:, j, :].ravel())[0, 1]
                pairwise_corr.append(corr)
        if pairwise_corr:
            mean_corr = np.mean(pairwise_corr)
            extra_features.append(np.full((n_samples, 1), mean_corr))

        variance_of_probs = np.var(proba_mean, axis=1)
        extra_features.append(variance_of_probs.reshape(-1, 1))

        enhanced = np.hstack([oof_probas] + extra_features)
        return enhanced

    def __init__(self, base_config: Optional[Dict[str, Any]] = None,
                 meta_config: Optional[Dict[str, Any]] = None,
                 model_config: Optional[ModelConfig] = None):
        _mc = model_config or get_model_config()
        resolved_base = base_config or _mc.stacking_base_config()
        resolved_meta = meta_config or _mc.stacking_meta_config()

        if base_config is not None:
            self.base_config = {**self.DEFAULT_BASE_CONFIG, **base_config}
        else:
            self.base_config = {**self.DEFAULT_BASE_CONFIG, **resolved_base}

        if meta_config is not None:
            self.meta_config = {**self.DEFAULT_META_CONFIG, **meta_config}
        else:
            self.meta_config = {**self.DEFAULT_META_CONFIG, **resolved_meta}

        self.BASE_MODELS = self._build_base_models(self.base_config)
        self.position_models: Dict[str, Dict[str, Any]] = {}
        self.meta_models: Dict[str, Any] = {}
        self.meta_scores: Dict[str, float] = {}
        self._fitted = False

        logger.info(
            f"[Stacking V2] 初始化完成, 基学习器: {list(self.BASE_MODELS.keys())}, "
            f"元学习器类型: {self.meta_config['type']}, "
            f"CV折数: {self.meta_config['cv_folds']}, "
            f"增强元特征: {'开启' if self.meta_config['enable_meta_features'] else '关闭'}, "
            f"自动选择: {'开启' if self.meta_config['auto_select'] else '关闭'}"
        )

    def fit_position_models(self, data: pd.DataFrame, feature_cols: List[str]) -> "StackingEnsemble":
        X = data[feature_cols].fillna(0).values
        cv_folds = self.meta_config.get("cv_folds", 5)
        tscv = TimeSeriesSplit(n_splits=cv_folds)

        for pos in POSITIONS:
            y = data[pos].values.astype(int)
            logger.info(f"[Stacking V2] Training position {pos} (cv={cv_folds})...")

            n_base = len(self.BASE_MODELS)
            raw_meta_X = np.zeros((len(X), n_base * 10))

            base_fitted: Dict[str, Any] = {}
            for b_idx, (name, base_fn) in enumerate(self.BASE_MODELS.items()):
                clf = base_fn()
                oof_proba = np.zeros((len(X), 10))

                for fold_tr, fold_val in tscv.split(X):
                    clf_fold = clone(clf)
                    clf_fold.fit(X[fold_tr], y[fold_tr])
                    raw = clf_fold.predict_proba(X[fold_val])
                    classes = clf_fold.classes_
                    for i, val_idx in enumerate(fold_val):
                        p = np.zeros(10)
                        for ci, c in enumerate(classes):
                            if 0 <= c <= 9:
                                p[c] = raw[i, ci]
                        oof_proba[val_idx] = self._safe_proba(p)

                raw_meta_X[:, b_idx * 10:(b_idx + 1) * 10] = oof_proba

                clf.fit(X, y)
                base_fitted[name] = clf

            self.position_models[pos] = base_fitted

            enable_extra = self.meta_config.get("enable_meta_features", True)
            if enable_extra:
                meta_X = self._compute_enhanced_meta_features(raw_meta_X, n_base, n_classes=10)
                logger.info(f"[Stacking V2] 位置{pos} 增强元特征维度: {raw_meta_X.shape[1]} -> {meta_X.shape[1]}")
            else:
                meta_X = raw_meta_X

            auto_select = self.meta_config.get("auto_select", True)
            if auto_select:
                best_clf, best_score, selected_type = self._select_best_meta_learner(meta_X, y, pos)
                logger.info(f"[Stacking V2] 位置{pos} 自动选择元学习器: {selected_type} (CV score={best_score:.4f})")
            else:
                best_clf = self._build_meta_learner(self.meta_config)
                best_score = float(np.mean(cross_val_score(best_clf, meta_X, y, cv=tscv)))
                selected_type = self.meta_config.get("type", "logistic")

            best_clf.fit(meta_X, y)
            self.meta_models[pos] = best_clf
            self.meta_scores[pos] = best_score

        self._fitted = True
        return self

    def _select_best_meta_learner(self, meta_X: np.ndarray, y: np.ndarray, pos: str) -> Tuple[Any, float, str]:
        """自动选择最优元学习器

        候选:
        1. LogisticRegression (L2正则化)
        2. SGDClassifier with ElasticNet (L1+L2正则化)
        3. LogisticRegression with stronger regularization

        返回: (最佳模型实例, 最佳CV分数, 选择的类型名称)
        """
        candidates = {}

        lr_standard = LogisticRegression(
            C=self.meta_config.get("C", 1.0),
            max_iter=self.meta_config.get("max_iter", 500),
            solver="lbfgs", random_state=42,
        )
        scores_lr = cross_val_score(lr_standard, meta_X, y, cv=TimeSeriesSplit(n_splits=self.meta_config.get("cv_folds", 5)))
        candidates["logistic"] = (lr_standard, float(np.mean(scores_lr)))

        sgd_elastic = SGDClassifier(
            loss="modified_huber",
            penalty="elasticnet",
            alpha=self.meta_config.get("alpha", 0.0001),
            l1_ratio=self.meta_config.get("l1_ratio", 0.5),
            max_iter=self.meta_config.get("max_iter", 1000),
            random_state=42, warm_start=True,
        )
        scores_sgd = cross_val_score(sgd_elastic, meta_X, y, cv=TimeSeriesSplit(n_splits=self.meta_config.get("cv_folds", 5)))
        candidates["elasticnet"] = (sgd_elastic, float(np.mean(scores_sgd)))

        lr_strong = LogisticRegression(
            C=self.meta_config.get("C", 1.0) * 0.1,
            max_iter=self.meta_config.get("max_iter", 500) * 2,
            solver="lbfgs", random_state=42,
        )
        scores_strong = cross_val_score(lr_strong, meta_X, y, cv=TimeSeriesSplit(n_splits=self.meta_config.get("cv_folds", 5)))
        candidates["logistic_strong_reg"] = (lr_strong, float(np.mean(scores_strong)))

        best_type = max(candidates.keys(), key=lambda k: candidates[k][1])
        best_model, best_score = candidates[best_type]

        logger.debug(f"[Stacking V2 MetaSelect] 位置{pos} 候选分数: "
                      f"{ {k: f'{v[1]:.4f}' for k, v in candidates.items()} }")

        return clone(best_model), best_score, best_type

    @staticmethod
    def _safe_proba(proba: np.ndarray, n_classes: int = 10) -> np.ndarray:
        out = np.zeros(n_classes)
        valid = min(len(proba), n_classes)
        out[:valid] = proba[:valid]
        return out / (out.sum() + 1e-12)

    def predict_proba_position(self, pos: str, x: np.ndarray) -> np.ndarray:
        if pos not in self.position_models or not self._fitted:
            return np.ones(10) / 10

        x2d = x.reshape(1, -1)
        n_base = len(self.position_models[pos])
        raw_meta_x = np.zeros((1, n_base * 10))

        for b_idx, (name, clf) in enumerate(self.position_models[pos].items()):
            raw = clf.predict_proba(x2d)[0]
            classes = clf.classes_
            p = np.zeros(10)
            for ci, c in enumerate(classes):
                if 0 <= c <= 9:
                    p[c] = raw[ci]
            raw_meta_x[0, b_idx * 10:(b_idx + 1) * 10] = self._safe_proba(p)

        enable_extra = self.meta_config.get("enable_meta_features", True)
        if enable_extra:
            meta_x = self._compute_enhanced_meta_features(raw_meta_x, n_base, n_classes=10)
        else:
            meta_x = raw_meta_x

        meta_clf = self.meta_models[pos]
        raw_meta = meta_clf.predict_proba(meta_x)[0]
        classes = meta_clf.classes_
        p = np.zeros(10)
        for ci, c in enumerate(classes):
            if 0 <= c <= 9:
                p[c] = raw_meta[ci]
        return self._safe_proba(p)

    def __getstate__(self):
        """自定义序列化方法，避免保存lambda函数"""
        state = self.__dict__.copy()
        # 删除不可序列化的BASE_MODELS（训练时使用，预测时不需要）
        if 'BASE_MODELS' in state:
            del state['BASE_MODELS']
        return state

    def __setstate__(self, state):
        """自定义反序列化方法，重新构建BASE_MODELS"""
        self.__dict__.update(state)
        # 重新构建BASE_MODELS（如果需要的话）
        if 'base_config' in state and 'BASE_MODELS' not in state:
            self.BASE_MODELS = self._build_base_models(self.base_config)


class EnhancedPL5Predictor:
    """
    增强型PL5预测器 V10.0

    新增功能:
    1. RL自适应权重优化 (Actor-Critic)
    2. 贝叶斯不确定性量化 (MC Dropout)
    3. 真正的HMM时序建模
    4. 多元Copula联合分布
    5. Thompson Sampling探索策略
    6. 并行化训练
    """

    DEFAULT_WEIGHTS = {
        "stacking": 0.25,
        "hmm": 0.10,
        "copula": 0.15,
        "bayesian": 0.10,
        "mamba": 0.20,
        "itransformer": 0.20
    }

    def __init__(self, model_config: Optional[ModelConfig] = None):
        self._mc = model_config or get_model_config()
        self.stacking: Dict[str, StackingEnsemble] = {}
        self.hmm_models: Dict[str, HiddenMarkovModel] = {}
        self.copula_model: Optional[MultivariateCopula] = None
        self.bsts_models: Dict[str, BayesianStructuralTimeSeries] = {}

        self.mamba_predictor: Optional[Any] = None
        self.itransformer_predictor: Optional[Any] = None
        self.bayesian_quantifier: Optional[Any] = None

        self.rl_optimizer: Optional[ModelWeightRLOptimizer] = None
        self.thompson_sampler: Optional[ThompsonSamplingOptimizer] = None

        self.feature_cols: List[str] = []
        self.trained_feature_dim: int = 0
        self.is_trained = False
        self.weights = self._mc.model_weights().copy()
        if "mamba" not in self.weights:
            self.weights["mamba"] = 0.20
        if "itransformer" not in self.weights:
            self.weights["itransformer"] = 0.20

        self.models_dir = Path(__file__).parent.parent.parent.parent / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.version_manager = ModelVersionManager(self.models_dir)

        self._states_history: List[np.ndarray] = []
        self._rewards_history: List[float] = []

        self._model_performance_history: Dict[str, List[float]] = {
            "stacking": [], "hmm": [], "copula": [], "bayesian": [],
            "mamba": [], "itransformer": []
        }
        self._performance_window = self._mc.get_int('rl_optimizer.performance_window', 30)
        self._prediction_results_cache: List[Dict] = []

        rl_ts_cfg = self._mc.get_dict('rl_optimizer.thompson_sampling', {})
        self._thompson_weight_params: Dict[str, Dict[str, float]] = {
            "stacking": {"alpha": rl_ts_cfg.get('initial_alpha', 2.0), "beta": rl_ts_cfg.get('initial_beta', 3.0)},
            "hmm": {"alpha": 1.5, "beta": 4.0},
            "copula": {"alpha": rl_ts_cfg.get('initial_alpha', 2.0), "beta": rl_ts_cfg.get('initial_beta', 3.0)},
            "bayesian": {"alpha": 1.5, "beta": 4.0}
        }

    def fit(self, df: pd.DataFrame, feature_cols: List[str],
            parallel: bool = True, incremental: bool = False) -> "EnhancedPL5Predictor":
        """训练增强模型
        
        Args:
            df: 训练数据
            feature_cols: 特征列
            parallel: 是否并行训练
            incremental: 是否增量训练
        """
        # 导入资源管理模块
        from src.core.utils.resource_manager import get_optimal_workers, check_system_resources, get_resource_summary, suggest_batch_size
        
        # 检查系统资源
        if not check_system_resources():
            logger.warning(f"系统资源使用较高: {get_resource_summary()}")
            logger.warning("将调整并行度以避免资源过度使用")
            parallel = False
        import asyncio
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self.feature_cols = feature_cols
        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_FEATURE_ENGINEERING,
            {"data_rows": len(df), "feature_count": len(feature_cols), "parallel": parallel, "incremental": incremental}
        )
        start_time = time.time()

        try:
            logger.debug(f"[训练步骤] 开始训练 - {datetime.now().strftime('%H:%M:%S')}")
            
            # 检查是否为增量学习
            if incremental:
                logger.debug(f"[训练步骤] 执行增量学习 - {datetime.now().strftime('%H:%M:%S')}")
                logger.info("[EnhancedPredictor] 执行增量学习")
                
                # 尝试加载现有模型
                if hasattr(self, 'is_trained') and self.is_trained:
                    logger.info("[EnhancedPredictor] 加载现有模型进行增量学习")
                else:
                    # 如果模型未训练，则执行完整训练
                    logger.debug("[训练步骤] 模型未训练，执行完整训练")
                    incremental = False
            
            X = df[feature_cols].fillna(0).values
            actual_dim = X.shape[1]

            if actual_dim == 0:
                raise ValueError(f"[EnhancedPredictor] 特征维度为0, 请检查feature_cols: {feature_cols}")

            self.trained_feature_dim = actual_dim
            logger.debug(f"[训练步骤] 特征维度: {actual_dim}, 特征列数: {len(feature_cols)}")
            logger.info(f"[EnhancedPredictor V10] 训练特征维度: {actual_dim}, 特征列数: {len(feature_cols)}")

            missing_cols = [c for c in feature_cols if c not in df.columns]
            if missing_cols:
                logger.warning(f"[EnhancedPredictor] 以下特征列不存在于数据中(将用0填充): {missing_cols}")

            logger.debug(f"[训练步骤] 开始训练位置模型 - {datetime.now().strftime('%H:%M:%S')}")
            if parallel:
                # 使用资源管理器获取最优的工作线程数
                optimal_workers = get_optimal_workers()
                max_workers = min(optimal_workers, len(POSITIONS))
                logger.info(f"使用最优工作线程数: {max_workers}")
                
                # 根据资源使用情况调整训练强度
                base_batch_size = 32
                adjusted_batch_size = suggest_batch_size(base_batch_size)
                if adjusted_batch_size != base_batch_size:
                    logger.info(f"根据资源使用情况调整批处理大小: {base_batch_size} -> {adjusted_batch_size}")
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {}

                    # 获取资源使用情况
                    from src.core.utils.resource_manager import get_resource_manager
                    resource_usage = get_resource_manager().get_resource_usage()
                    
                    for pos in POSITIONS:
                        if incremental and pos in self.stacking:
                            # 增量学习：只更新现有模型
                            logger.debug(f"[训练步骤] 提交位置 {pos} 增量学习任务")
                            future = executor.submit(self._incremental_update_position_models, df, feature_cols, pos, resource_usage)
                        else:
                            # 完整训练
                            future = executor.submit(self._fit_position_models, df, feature_cols, pos, resource_usage)
                            logger.debug(f"[训练步骤] 提交位置 {pos} 训练任务")
                        futures[future] = pos

                    for future in as_completed(futures):
                        pos = futures[future]
                        try:
                            result = future.result()
                            self.stacking[pos] = result['stacking']
                            self.hmm_models[pos] = result['hmm']
                            self.bsts_models[pos] = result['bsts']
                            logger.debug(f"[训练步骤] 位置 {pos} 训练完成 - {datetime.now().strftime('%H:%M:%S')}")
                            logger.info(f"[EnhancedPredictor] 位置 {pos} 训练完成")
                        except Exception as e:
                            logger.error(
                                f"[EnhancedPredictor] 位置 {pos} 训练失败: {e}",
                                exc_info=True
                            )
                            raise ModelTrainingError(
                                f"Position {pos} training failed: {e}",
                                model_name=f"position_{pos}",
                                operation="fit",
                                original_error=e,
                                severity=ErrorSeverity.ERROR_SEVERITY_HIGH
                            )
            else:
                # 获取资源使用情况
                from src.core.utils.resource_manager import get_resource_manager
                resource_usage = get_resource_manager().get_resource_usage()
                
                for pos in POSITIONS:
                    try:
                        logger.debug(f"[训练步骤] 开始训练位置 {pos} - {datetime.now().strftime('%H:%M:%S')}")
                        if incremental and pos in self.stacking:
                            # 增量学习：只更新现有模型
                            logger.debug(f"[训练步骤] 执行位置 {pos} 增量学习")
                            result = self._incremental_update_position_models(df, feature_cols, pos, resource_usage)
                        else:
                            # 完整训练
                            result = self._fit_position_models(df, feature_cols, pos, resource_usage)
                        self.stacking[pos] = result['stacking']
                        self.hmm_models[pos] = result['hmm']
                        self.bsts_models[pos] = result['bsts']
                        logger.debug(f"[训练步骤] 位置 {pos} 训练完成 - {datetime.now().strftime('%H:%M:%S')}")
                    except Exception as e:
                        raise ModelTrainingError(
                            f"Position {pos} training failed: {e}",
                            model_name=f"position_{pos}",
                            operation="fit",
                            original_error=e,
                            severity=ErrorSeverity.ERROR_SEVERITY_HIGH
                        )

            logger.debug(f"[训练步骤] 开始训练Copula模型 - {datetime.now().strftime('%H:%M:%S')}")
            position_matrix = df[POSITIONS].values.astype(float)
            copula_cfg = self._mc.copula_config()
            self.copula_model = MultivariateCopula(
                copula_type=copula_cfg.get('type', 'gaussian'),
                regularization=copula_cfg.get('regularization', 1e-6),
                auto_select=copula_cfg.get('auto_select', False))
            self.copula_model.fit(position_matrix)
            logger.debug(f"[训练步骤] Copula模型训练完成 - {datetime.now().strftime('%H:%M:%S')}")
            logger.info("[EnhancedPredictor] Copula模型训练完成")

            # 尝试训练Mamba模型（使用优化参数）
            logger.debug(f"[训练步骤] 开始训练Mamba模型 - {datetime.now().strftime('%H:%M:%S')}")
            try:
                from src.core.models.mamba_predictor import MultiPositionMambaPredictor
                self.mamba_predictor = MultiPositionMambaPredictor(
                    n_layers=2,  # 减少层数
                    d_model=32,  # 减少维度
                    d_state=8,   # 减少状态维度
                    seq_length=20  # 减少序列长度
                )
                # 准备Mamba训练数据
                mamba_data = {pos: df[pos].values for pos in POSITIONS}
                self.mamba_predictor.fit(mamba_data, epochs=20, verbose=False)
                logger.debug(f"[训练步骤] Mamba模型训练完成 - {datetime.now().strftime('%H:%M:%S')}")
                logger.info("[EnhancedPredictor] Mamba模型训练完成")
            except Exception as e:
                logger.debug(f"[训练步骤] Mamba模型训练失败(非致命): {e}")
                logger.warning(f"[EnhancedPredictor] Mamba模型训练失败(非致命): {e}")
                self.mamba_predictor = None

            # 尝试训练iTransformer模型（使用优化参数）
            logger.debug(f"[训练步骤] 开始训练iTransformer模型 - {datetime.now().strftime('%H:%M:%S')}")
            try:
                from src.core.models.itransformer_predictor import iTransformerPredictor
                self.itransformer_predictor = iTransformerPredictor(
                    n_layers=2,  # 减少层数
                    d_model=32,  # 减少维度
                    n_heads=2,   # 减少头数
                    d_ff=64,     # 减少前馈网络维度
                    seq_length=20  # 减少序列长度
                )
                # 准备iTransformer训练数据
                itrans_data = {pos: df[pos].values for pos in POSITIONS}
                self.itransformer_predictor.fit(itrans_data, epochs=20, verbose=False)
                logger.debug(f"[训练步骤] iTransformer模型训练完成 - {datetime.now().strftime('%H:%M:%S')}")
                logger.info("[EnhancedPredictor] iTransformer模型训练完成")
            except Exception as e:
                logger.debug(f"[训练步骤] iTransformer模型训练失败(非致命): {e}")
                logger.warning(f"[EnhancedPredictor] iTransformer模型训练失败(非致命): {e}")
                self.itransformer_predictor = None

            logger.debug(f"[训练步骤] 初始化贝叶斯量化器 - {datetime.now().strftime('%H:%M:%S')}")
            try:
                from src.core.models.bayesian_uncertainty import EnhancedBayesianQuantifier
                self.bayesian_quantifier = EnhancedBayesianQuantifier(calibration_alpha=0.1)
                logger.debug(f"[训练步骤] 贝叶斯量化器初始化完成 - {datetime.now().strftime('%H:%M:%S')}")
                logger.info("[EnhancedPredictor] 贝叶斯不确定性量化器初始化完成")
            except Exception as e:
                logger.debug(f"[训练步骤] 贝叶斯量化器初始化失败(非致命): {e}")
                logger.warning(f"[EnhancedPredictor] 贝叶斯量化器初始化失败(非致命): {e}")
                self.bayesian_quantifier = None

            # 检查V10模块训练状态
            v10_modules_fitted = (
                self.mamba_predictor is not None and
                self.itransformer_predictor is not None and
                self.bayesian_quantifier is not None
            )
            if not v10_modules_fitted:
                logger.warning(
                    f"[EnhancedPredictor V10] V10模块训练不完整: "
                    f"Mamba={self.mamba_predictor is not None}, "
                    f"iTransformer={self.itransformer_predictor is not None}, "
                    f"Bayesian={self.bayesian_quantifier is not None}"
                )

            logger.debug(f"[训练步骤] 加载RL模块 - {datetime.now().strftime('%H:%M:%S')}")
            _load_rl_modules()
            if _HAS_RL and ThompsonSamplingOptimizer is not None:
                rl_ts_cfg = self._mc.get_dict('rl_optimizer.thompson_sampling', {})
                self.thompson_sampler = ThompsonSamplingOptimizer(n_arms=rl_ts_cfg.get('n_arms', len(POSITIONS)))
            else:
                self.thompson_sampler = None
            
            if _HAS_RL and ModelWeightRLOptimizer is not None:
                rl_cfg = self._mc.rl_config()
                self.rl_optimizer = ModelWeightRLOptimizer(
                    n_models=rl_cfg.get('n_models', 4),
                    state_dim=rl_cfg.get('state_dim', 64))  # 减少状态维度
            else:
                self.rl_optimizer = None

            # 当基础模块训练成功时，就标记为已训练（V10模块为可选）
            basic_modules_fitted = (
                bool(self.stacking) and
                bool(self.hmm_models) and
                self.copula_model is not None and
                bool(self.bsts_models)
            )
            self.is_trained = basic_modules_fitted
            
            if not self.is_trained:
                logger.warning("[EnhancedPredictor V10] 模型训练不完整，部分模块缺失")
                logger.warning(f"  基础模块: {'完整' if basic_modules_fitted else '缺失'}")
                logger.warning(f"  V10模块: {'完整' if v10_modules_fitted else '缺失'}")
            else:
                logger.info("[EnhancedPredictor V10] 基础模型训练完成")
                if v10_modules_fitted:
                    logger.info("[EnhancedPredictor V10] V10模块训练完成")
                else:
                    logger.info("[EnhancedPredictor V10] V10模块训练跳过")

            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"[训练步骤] 训练完成，耗时: {duration_ms/1000:.2f} 秒 - {datetime.now().strftime('%H:%M:%S')}")
            structured_logger.log_operation_success(
                StructuredLogger.OPERATION_FEATURE_ENGINEERING,
                duration_ms,
                {"positions_trained": len(POSITIONS), "models": ["stacking", "hmm", "copula", "bsts", "mamba", "itransformer"], "incremental": incremental}
            )
            return self

        except ModelTrainingError:
            raise
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"[训练步骤] 训练失败: {e} - {datetime.now().strftime('%H:%M:%S')}")
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_FEATURE_ENGINEERING,
                ModelTrainingError(str(e), operation="fit", original_error=e),
                duration_ms
            )
            raise ModelTrainingError(
                f"Model training failed: {e}", operation="fit", original_error=e
            )

    def _fit_position_models(self, df: pd.DataFrame, feature_cols: List[str],
                            pos: str, resource_usage: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """训练单个位置的所有模型 - 增强版"""
        X = df[feature_cols].fillna(0).values
        y = df[pos].values.astype(int)
        seq = df[pos].values.reshape(-1, 1)

        # 导入资源管理模块
        from src.core.utils.resource_manager import get_resource_summary
        
        # 根据资源使用情况调整模型复杂度
        high_resource_usage = False
        if resource_usage:
            high_resource_usage = (
                resource_usage['cpu']['over_threshold'] or
                resource_usage['memory']['over_threshold']
            )
        
        if high_resource_usage:
            logger.info(f"资源使用较高 {get_resource_summary()}，将降低模型复杂度")

        # 创建StackingEnsemble并只训练当前位置
        stacking = StackingEnsemble(model_config=self._mc)
        
        # 手动训练单个位置，避免训练所有位置
        cv_folds = stacking.meta_config.get("cv_folds", 5)
        # 根据资源使用情况调整交叉验证折数
        if high_resource_usage:
            cv_folds = max(3, cv_folds - 2)
            logger.info(f"调整交叉验证折数: {cv_folds}")
        
        tscv = TimeSeriesSplit(n_splits=cv_folds)
        
        n_base = len(stacking.BASE_MODELS)
        # 根据资源使用情况调整基础模型数量
        if high_resource_usage and n_base > 3:
            # 只使用前3个基础模型
            base_models = list(stacking.BASE_MODELS.items())[:3]
            n_base = 3
            logger.info(f"调整基础模型数量: {n_base}")
        else:
            base_models = list(stacking.BASE_MODELS.items())
        
        raw_meta_X = np.zeros((len(X), n_base * 10))
        
        base_fitted: Dict[str, Any] = {}
        for b_idx, (name, base_fn) in enumerate(base_models):
            clf = base_fn()
            oof_proba = np.zeros((len(X), 10))
            
            # 添加早停机制和学习率调度
            if hasattr(clf, 'set_params'):
                # 为支持早停的模型设置参数
                if 'n_estimators' in clf.get_params():
                    params = {
                        'n_estimators': 200,
                        'verbose': 0
                    }
                    # 只有支持早停的模型才添加early_stopping_rounds参数
                    if 'early_stopping_rounds' in clf.get_params():
                        params['early_stopping_rounds'] = 10
                    clf.set_params(**params)
            
            for fold_tr, fold_val in tscv.split(X):
                clf_fold = clone(clf)
                clf_fold.fit(X[fold_tr], y[fold_tr])
                raw = clf_fold.predict_proba(X[fold_val])
                classes = clf_fold.classes_
                for i, val_idx in enumerate(fold_val):
                    p = np.zeros(10)
                    for ci, c in enumerate(classes):
                        if 0 <= c <= 9:
                            p[c] = raw[i, ci]
                    oof_proba[val_idx] = stacking._safe_proba(p)
            
            raw_meta_X[:, b_idx * 10:(b_idx + 1) * 10] = oof_proba
            
            clf.fit(X, y)
            base_fitted[name] = clf
        
        stacking.position_models[pos] = base_fitted
        
        enable_extra = stacking.meta_config.get("enable_meta_features", True)
        # 根据资源使用情况调整是否启用额外特征
        if high_resource_usage:
            enable_extra = False
            logger.info("禁用额外特征以降低计算复杂度")
        
        if enable_extra:
            meta_X = stacking._compute_enhanced_meta_features(raw_meta_X, n_base, n_classes=10)
        else:
            meta_X = raw_meta_X
        
        auto_select = stacking.meta_config.get("auto_select", True)
        # 根据资源使用情况调整是否自动选择元学习器
        if high_resource_usage:
            auto_select = False
            logger.info("禁用自动选择元学习器以降低计算复杂度")
        
        if auto_select:
            best_clf, best_score, selected_type = stacking._select_best_meta_learner(meta_X, y, pos)
        else:
            best_clf = stacking._build_meta_learner(stacking.meta_config)
            best_score = float(np.mean(cross_val_score(best_clf, meta_X, y, cv=tscv)))
            selected_type = stacking.meta_config.get("type", "logistic")
        
        best_clf.fit(meta_X, y)
        stacking.meta_models[pos] = best_clf
        stacking.meta_scores[pos] = best_score
        stacking._fitted = True

        # 增强的HMM训练
        hmm_cfg = self._mc.hmm_config()
        # 根据资源使用情况调整HMM参数
        if high_resource_usage:
            hmm_n_states = max(2, hmm_cfg.get('n_states', 4) - 2)
            hmm_n_mixtures = max(1, hmm_cfg.get('n_mixtures', 2) - 1)
            logger.info(f"调整HMM参数: 状态数={hmm_n_states}, 混合数={hmm_n_mixtures}")
        else:
            hmm_n_states = hmm_cfg.get('n_states', 4)
            hmm_n_mixtures = hmm_cfg.get('n_mixtures', 2)
        
        # 自动选择最佳HMM参数
        best_hmm = None
        best_hmm_score = -float('inf')
        
        # 尝试不同的HMM参数组合
        if not high_resource_usage:
            state_options = [hmm_n_states - 1, hmm_n_states, hmm_n_states + 1]
            state_options = [s for s in state_options if s >= 2 and s <= 8]
            mixture_options = [hmm_n_mixtures, hmm_n_mixtures + 1]
            mixture_options = [m for m in mixture_options if m >= 1 and m <= 3]
            
            for n_states in state_options:
                for n_mixtures in mixture_options:
                    try:
                        hmm_candidate = HiddenMarkovModel(
                            n_states=n_states,
                            n_mixtures=n_mixtures,
                            auto_select=False,
                            criterion='bic'
                        )
                        hmm_candidate.fit(seq)
                        score = -hmm_candidate.score(seq)
                        if score > best_hmm_score:
                            best_hmm_score = score
                            best_hmm = hmm_candidate
                    except Exception as e:
                        logger.warning(f"HMM参数组合 ({n_states}, {n_mixtures}) 训练失败: {e}")
        
        if best_hmm is None:
            # 如果自动选择失败，使用默认参数
            best_hmm = HiddenMarkovModel(
                n_states=hmm_n_states,
                n_mixtures=hmm_n_mixtures,
                auto_select=hmm_cfg.get('auto_select', False),
                criterion=hmm_cfg.get('criterion', 'bic')
            )
            best_hmm.fit(seq)

        # 增强的BSTS训练
        bsts_cfg = self._mc.bsts_config()
        # 根据资源使用情况调整BSTS参数
        if high_resource_usage:
            n_posterior_samples = max(500, bsts_cfg.get('n_posterior_samples', 1000) // 2)
            trend_window = max(10, bsts_cfg.get('trend_window', 20) // 2)
            logger.info(f"调整BSTS参数: 后验样本数={n_posterior_samples}, 趋势窗口={trend_window}")
        else:
            n_posterior_samples = bsts_cfg.get('n_posterior_samples', 1000)
            trend_window = bsts_cfg.get('trend_window', 20)
        
        bsts = BayesianStructuralTimeSeries(
            trend_window=trend_window,
            seasonality_period=bsts_cfg.get('seasonality_period'),
            outlier_threshold=bsts_cfg.get('outlier_threshold', 2.5),
            n_posterior_samples=n_posterior_samples,
            confidence_level=bsts_cfg.get('confidence_level', 0.95))
        bsts.fit(seq)

        return {
            'stacking': stacking,
            'hmm': best_hmm,
            'bsts': bsts
        }
        
    def _incremental_update_position_models(self, df: pd.DataFrame, feature_cols: List[str],
                                          pos: str, resource_usage: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """增量更新单个位置的所有模型 - 增强版"""
        X = df[feature_cols].fillna(0).values
        y = df[pos].values.astype(int)
        seq = df[pos].values.reshape(-1, 1)

        logger.info(f"[EnhancedPredictor] 执行位置 {pos} 的增量学习")
        
        # 获取现有模型
        stacking = self.stacking[pos]
        hmm = self.hmm_models[pos]
        bsts = self.bsts_models[pos]
        
        # 增量更新Stacking模型
        logger.info(f"[EnhancedPredictor] 增量更新Stacking模型")
        
        # 对每个基础模型进行增量更新
        for name, model in stacking.position_models[pos].items():
            if hasattr(model, 'warm_start'):
                model.warm_start = True
                if hasattr(model, 'n_estimators'):
                    # 增加树的数量
                    model.n_estimators += 10
                    # 添加自适应学习率
                    if hasattr(model, 'learning_rate'):
                        # 随着训练轮数增加，逐渐降低学习率
                        current_lr = model.learning_rate
                        new_lr = max(0.001, current_lr * 0.95)
                        model.learning_rate = new_lr
                        logger.info(f"[EnhancedPredictor] 调整 {name} 模型学习率: {current_lr} -> {new_lr}")
                    logger.info(f"[EnhancedPredictor] 增量更新 {name} 模型，增加至 {model.n_estimators} 棵树")
                    model.fit(X, y)
            elif hasattr(model, 'partial_fit'):
                # 对于支持partial_fit的模型
                model.partial_fit(X, y)
                logger.info(f"[EnhancedPredictor] 增量更新 {name} 模型")
        
        # 增量更新元学习器
        if pos in stacking.meta_models:
            meta_model = stacking.meta_models[pos]
            # 重新计算元特征
            n_base = len(stacking.position_models[pos])
            raw_meta_X = np.zeros((len(X), n_base * 10))
            
            for b_idx, (name, model) in enumerate(stacking.position_models[pos].items()):
                raw = model.predict_proba(X)
                classes = model.classes_
                for i in range(len(X)):
                    p = np.zeros(10)
                    for ci, c in enumerate(classes):
                        if 0 <= c <= 9:
                            p[c] = raw[i, ci]
                    raw_meta_X[i, b_idx * 10:(b_idx + 1) * 10] = p
            
            # 计算增强元特征
            enable_extra = stacking.meta_config.get("enable_meta_features", True)
            if enable_extra:
                meta_X = stacking._compute_enhanced_meta_features(raw_meta_X, n_base, n_classes=10)
            else:
                meta_X = raw_meta_X
            
            # 增量更新元学习器
            if hasattr(meta_model, 'partial_fit'):
                meta_model.partial_fit(meta_X, y)
            else:
                meta_model.fit(meta_X, y)
            logger.info(f"[EnhancedPredictor] 增量更新元学习器")
        
        # 增量更新HMM模型
        logger.info(f"[EnhancedPredictor] 增量更新HMM模型")
        if hasattr(hmm, 'partial_fit'):
            hmm.partial_fit(seq)
        else:
            # 对于不支持partial_fit的HMM模型，使用自动参数选择重新训练
            logger.info(f"[EnhancedPredictor] HMM模型不支持增量学习，使用自动参数选择重新训练")
            best_hmm = None
            best_score = -float('inf')
            
            for n_states in [hmm.n_states - 1, hmm.n_states, hmm.n_states + 1]:
                if n_states < 2 or n_states > 8:
                    continue
                for n_mixtures in [hmm.n_mixtures, hmm.n_mixtures + 1]:
                    if n_mixtures < 1 or n_mixtures > 3:
                        continue
                    try:
                        new_hmm = HiddenMarkovModel(
                            n_states=n_states,
                            n_mixtures=n_mixtures,
                            auto_select=False,
                            criterion='bic'
                        )
                        new_hmm.fit(seq)
                        score = -new_hmm.score(seq)
                        if score > best_score:
                            best_score = score
                            best_hmm = new_hmm
                    except Exception as e:
                        logger.warning(f"HMM参数组合 ({n_states}, {n_mixtures}) 训练失败: {e}")
            
            if best_hmm is not None:
                hmm = best_hmm
                logger.info(f"[EnhancedPredictor] 选择最佳HMM参数: 状态数={hmm.n_states}, 混合数={hmm.n_mixtures}")
            else:
                # 如果自动选择失败，使用默认参数重新训练
                hmm.fit(seq)
        
        # 增量更新BSTS模型
        logger.info(f"[EnhancedPredictor] 增量更新BSTS模型")
        if hasattr(bsts, 'partial_fit'):
            bsts.partial_fit(seq)
        else:
            # 对于不支持partial_fit的BSTS模型，使用新数据重新训练
            bsts.fit(seq)
        
        return {
            'stacking': stacking,
            'hmm': hmm,
            'bsts': bsts
        }

    def predict(self,
              features: np.ndarray,
              recent_original_data: Optional[Dict[str, np.ndarray]] = None,
              top_k: int = 8,
              use_rl: bool = True,
              use_uncertainty: bool = True) -> Dict[str, Dict[str, Any]]:
        """增强预测 - 带不确定性量化和RL自适应权重，含错误恢复"""
        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_PREDICTION,
            {"feature_dim": len(features) if features is not None else 0, "top_k": top_k}
        )
        start_time = time.time()
        logger.info(f"开始推理: {time.strftime('%H:%M:%S')}")

        try:
            if not self.is_trained:
                structured_logger.log_fallback_used(
                    StructuredLogger.OPERATION_PREDICTION,
                    "model_not_trained",
                    "Model not trained, returning uniform distribution"
                )
                logger.warning("[EnhancedPredictor] 模型未训练，返回均匀分布预测")
                return {pos: {"top_k": list(range(10))[:top_k],
                            "probabilities": [0.1] * top_k,
                            "uncertainty": 0.5,
                            "fallback": True} for pos in POSITIONS}

            # 检查V10模块完整性
            v10_modules_present = (
                self.mamba_predictor is not None and
                self.itransformer_predictor is not None and
                self.bayesian_quantifier is not None
            )
            if not v10_modules_present:
                logger.warning(
                    f"[EnhancedPredictor] V10模块不完整: "
                    f"Mamba={self.mamba_predictor is not None}, "
                    f"iTransformer={self.itransformer_predictor is not None}, "
                    f"Bayesian={self.bayesian_quantifier is not None}"
                )
                logger.info("[EnhancedPredictor] 将使用基础模块进行预测")
                # 继续使用基础模块进行预测，不返回均匀分布

            result: Dict[str, Dict[str, Any]] = {}

            if self.trained_feature_dim > 0:
                input_dim = len(features) if features is not None else 0
                if input_dim != self.trained_feature_dim:
                    logger.warning(
                        f"[EnhancedPredictor] 特征维度不匹配: 输入={input_dim}, 训练时={self.trained_feature_dim}"
                    )
                    if features is not None and input_dim > 0:
                        if input_dim > self.trained_feature_dim:
                            logger.info(f"  → 截断特征: {input_dim} -> {self.trained_feature_dim}")
                            features = features[:self.trained_feature_dim]
                        elif input_dim < self.trained_feature_dim:
                            pad_size = self.trained_feature_dim - input_dim
                            logger.info(f"  → 零填充特征: {input_dim} -> {self.trained_feature_dim} (填充{pad_size}维)")
                            features = np.pad(features, (0, pad_size), constant_values=0)
                        else:
                            pass
                    else:
                        structured_logger.log_fallback_used(
                            StructuredLogger.OPERATION_PREDICTION,
                            "invalid_features",
                            f"Invalid feature dimensions: input={input_dim}, expected={self.trained_feature_dim}"
                        )
                        return {pos: {"top_k": list(range(10))[:top_k],
                                    "probabilities": [0.1] * top_k,
                                    "uncertainty": 0.5,
                                    "fallback": True} for pos in POSITIONS}

            # 并行预测所有位置
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def predict_position(pos):
                try:
                    p_stacking = self.stacking.get(pos, StackingEnsemble()).predict_proba_position(
                        pos, features) if pos in self.stacking else np.ones(10) / 10

                    seq = (recent_original_data or {}).get(pos, np.array([0]))
                    if isinstance(seq, (pd.Series, list)):
                        seq = np.array(seq)
                    if len(seq) == 0:
                        seq = np.array([0])

                    p_hmm = self.hmm_models.get(pos, HiddenMarkovModel()).predict_proba(
                        seq[-10:] if len(seq) >= 10 else seq) if pos in self.hmm_models else np.ones(10) / 10

                    bsts_model = self.bsts_models.get(pos, BayesianStructuralTimeSeries())
                    if pos in self.bsts_models:
                        try:
                            p_bsts, _ = bsts_model.predict(1)
                        except Exception as e:
                            logger.warning(f"[EnhancedPredictor] BSTS预测失败: {e}")
                            p_bsts = np.ones(10) / 10
                    else:
                        p_bsts = np.ones(10) / 10

                    if self.copula_model is not None and recent_original_data:
                        copula_adjustment = np.ones(10)
                        for d in range(10):
                            test_values = np.zeros(len(POSITIONS))
                            for i, p in enumerate(POSITIONS):
                                if p in recent_original_data:
                                    data_series = recent_original_data[p]
                                    # 修复：检查data_series类型，使用不同的方法获取最后一个值
                                    if hasattr(data_series, 'iloc'):
                                        test_values[i] = data_series.iloc[-1] if len(data_series) > 0 else 0
                                    else:
                                        test_values[i] = data_series[-1] if len(data_series) > 0 else 0
                            test_values[POSITIONS.index(pos)] = d
                            copula_adjustment[d] = self.copula_model.get_joint_probability(test_values)
                        p_copula = copula_adjustment / (copula_adjustment.sum() + 1e-12)
                    else:
                        p_copula = np.ones(10) / 10

                    p_mamba = np.ones(10) / 10
                    if self.mamba_predictor is not None and pos in self.mamba_predictor.predictors:
                        try:
                            p_mamba, mamba_uncertainty = self.mamba_predictor.predictors[pos].predict_with_uncertainty(
                                seq[-20:] if len(seq) >= 20 else seq  # 减少序列长度以提高速度
                            )
                        except Exception as e:
                            logger.warning(f"[EnhancedPredictor] Mamba预测失败: {e}")
                            p_mamba = np.ones(10) / 10

                    p_itransformer = np.ones(10) / 10
                    if self.itransformer_predictor is not None and hasattr(self.itransformer_predictor, 'fitted') and self.itransformer_predictor.fitted:
                        try:
                            itrans_probs = self.itransformer_predictor.predict_proba(recent_original_data or {})
                            if pos in itrans_probs:
                                p_itransformer = itrans_probs[pos]
                        except Exception as e:
                            logger.warning(f"[EnhancedPredictor] iTransformer预测失败: {e}")
                            p_itransformer = np.ones(10) / 10

                    if use_rl and self.rl_optimizer is not None and hasattr(self.rl_optimizer, 'is_trained') and self.rl_optimizer.is_trained:
                        state = self._build_rl_state(features, p_stacking, p_hmm, p_copula)
                        weights = self.rl_optimizer.get_optimal_weights(state)
                    else:
                        # 改进的权重分配策略
                        # 基于模型性能动态调整权重
                        weights = self._get_dynamic_weights(p_stacking, p_hmm, p_copula, p_bsts, p_mamba, p_itransformer)
                        weights = weights / weights.sum()

                    p_fused = (
                        weights[0] * p_stacking +
                        weights[1] * p_hmm +
                        weights[2] * p_copula +
                        weights[3] * p_bsts +
                        weights[4] * p_mamba +
                        weights[5] * p_itransformer
                    )
                    p_fused = p_fused / (p_fused.sum() + 1e-12)

                    entropy = -np.sum(p_fused * np.log(p_fused + 1e-12))

                    top_indices = np.argsort(p_fused)[::-1][:top_k]

                    pos_result = {
                        "top_k": [int(i) for i in top_indices],
                        "probabilities": [float(p_fused[i]) for i in top_indices],
                        "uncertainty": float(entropy / np.log(10)),
                        "weights_used": {
                            "stacking": float(weights[0]),
                            "hmm": float(weights[1]),
                            "copula": float(weights[2]),
                            "bsts": float(weights[3]),
                            "mamba": float(weights[4]),
                            "itransformer": float(weights[5])
                        }
                    }

                    if self.thompson_sampler is not None:
                        arm = POSITIONS.index(pos)
                        self.thompson_sampler.update(arm, True)

                    return pos, pos_result
                except Exception as pos_error:
                    logger.error(f"[EnhancedPredictor] 位置 {pos} 预测异常: {pos_error}", exc_info=True)
                    return pos, {
                        "top_k": list(range(10))[:top_k],
                        "probabilities": [0.1] * top_k,
                        "uncertainty": 1.0,
                        "weights_used": {},
                        "error": str(pos_error),
                        "fallback": True
                    }
            
            # 并行执行预测
            with ThreadPoolExecutor(max_workers=min(5, len(POSITIONS))) as executor:
                futures = {executor.submit(predict_position, pos): pos for pos in POSITIONS}
                
                for future in as_completed(futures):
                    pos, pos_result = future.result()
                    result[pos] = pos_result
                    logger.debug(f"[预测步骤] 位置 {pos} 预测完成")
            
            # 应用贝叶斯不确定性量化（如果可用）
            if use_uncertainty and self.bayesian_quantifier is not None:
                try:
                    logger.debug("[预测步骤] 应用贝叶斯不确定性量化")
                    # 转换为贝叶斯量化器期望的格式
                    bayesian_input = {}
                    for pos, data in result.items():
                        # 创建一个概率数组，对应0-9的数字
                        probs = np.zeros(10)
                        for num, prob in zip(data['top_k'], data['probabilities']):
                            if 0 <= num < 10:
                                probs[num] = prob
                        # 归一化概率
                        probs = probs / (probs.sum() + 1e-12)
                        bayesian_input[pos] = probs
                    
                    # 使用 quantify 方法而不是 calibrate_predictions
                    uncertainty_report = self.bayesian_quantifier.quantify(bayesian_input)
                    
                    # 更新预测结果
                    for pos, data in result.items():
                        if pos in uncertainty_report.get('calibrated_probabilities', {}):
                            calibrated_probs = np.array(uncertainty_report['calibrated_probabilities'][pos])
                            top_indices = np.argsort(calibrated_probs)[::-1][:top_k]
                            result[pos]['top_k'] = [int(i) for i in top_indices]
                            result[pos]['probabilities'] = [float(calibrated_probs[i]) for i in top_indices]
                    logger.debug("[预测步骤] 贝叶斯不确定性量化完成")
                except Exception as e:
                    logger.warning(f"[EnhancedPredictor] 贝叶斯不确定性量化失败: {e}")

            duration_ms = (time.time() - start_time) * 1000
            duration_sec = duration_ms / 1000
            logger.debug(f"[预测步骤] 预测完成，耗时: {duration_sec:.2f} 秒")
            logger.info(f"推理完成: {time.strftime('%H:%M:%S')}, 耗时: {duration_sec:.2f} 秒")
            
            # 检查推理延迟是否符合要求
            if duration_sec <= 5:
                logger.info("✓ 推理延迟符合要求 (≤5秒)")
            else:
                logger.warning(f"⚠ 推理延迟超过要求: {duration_sec:.2f} 秒 > 5秒")
            
            structured_logger.log_operation_success(
                StructuredLogger.OPERATION_PREDICTION,
                duration_ms,
                {"positions": len(result), "top_k": top_k, "inference_time": duration_sec}
            )

            prediction_cache.store(f"pred_{time.time()}", result)
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_PREDICTION,
                ModelPredictionError(f"Prediction failed: {e}", operation="predict", original_error=e),
                duration_ms
            )

            cached = prediction_cache.get_latest()
            if cached:
                cache_key, cached_result = cached
                structured_logger.log_fallback_used(
                    StructuredLogger.OPERATION_PREDICTION,
                    "fallback_to_cache",
                    f"Prediction failed ({e}), using cached result from {cache_key}"
                )
                logger.warning(f"[ModelFallback] Using cached prediction due to: {e}")
                return cached_result

            logger.error(f"[EnhancedPredictor] 预测完全失败，使用均匀分布回退: {e}")
            return {pos: {"top_k": list(range(10))[:top_k],
                        "probabilities": [0.125] * top_k,
                        "uncertainty": 1.0,
                        "fallback": True} for pos in POSITIONS}

    def _build_rl_state(self, features: np.ndarray, p_stacking: np.ndarray,
                       p_hmm: np.ndarray, p_copula: np.ndarray) -> np.ndarray:
        """构建增强RL状态向量 V3 - 高信息密度状态表示（128维）

        状态向量组成:
        [0:30)    特征空间 (压缩到前30维主特征)
        [30:40)   Stacking模型概率分布 (10维)
        [40:50)   HMM模型概率分布 (10维)
        [50:60)   Copula模型概率分布 (10维)
        [60:64)   各模型置信度指标 (4维): max_proba each model
        [64:68)   各模型预测熵 (4维)
        [68:76)   模型间一致性/分歧度 (8维):
                  - 两两预测相关系数(6维) + 预测标签一致性(1维) + 概率方差(1维)
        [76:88)   增强近期表现特征 (12维):
                  - 近10次平均奖励、近10次奖励趋势、近10次命中率
                  - 近期最优模型索引(4维one-hot)
                  - 近5次/近20次滚动命中率对比
                  - 奖励加速度（二阶导数）
        [88:96)   权重分布统计 (8维):
                  - 权重熵、均值、标准差、偏度、最大值、最小值、权重动量方向、权重变化率
        [96:106)  位置级表现特征 (10维):
                  - 5个位置的近期命中one-hot编码 + 5个位置的模型偏好差异
        [106:116) 时间衰减表现 (10维):
                  - 指数加权移动平均(EWMA)奖励(不同半衰期4维)
                  - 近期连续命中/失误streak(2维)
                  - 全局表现分位数(2维)
                  - 表现波动性指标(2维)
        [116:124) 模型置信度方差 (8维):
                  - 各模型在所有位置的置信度标准差(4维)
                  - 各模型置信度的位置间极差(4维)
        [124:128) 跨模型分歧深度 (4维):
                  - 预测标签的投票熵、最大概率差异、次优概率比、预测集中度
        """
        feature_part = features[:30] if len(features) >= 30 else np.pad(features, (0, 30 - len(features)))

        model_probas = np.concatenate([p_stacking[:10], p_hmm[:10], p_copula[:10]])

        confidence_features = np.array([
            np.max(p_stacking), np.max(p_hmm), np.max(p_copula),
            np.max((p_stacking + p_hmm + p_copula) / 3)
        ])

        entropy_features = np.array([
            -np.sum(p_stacking * np.log(p_stacking + 1e-12)),
            -np.sum(p_hmm * np.log(p_hmm + 1e-12)),
            -np.sum(p_copula * np.log(p_copula + 1e-12)),
            -np.sum(((p_stacking + p_hmm + p_copula) / 3) *
                    np.log((p_stacking + p_hmm + p_copula) / 3 + 1e-12))
        ]) / np.log(10)

        all_preds = [np.argmax(p_stacking), np.argmax(p_hmm), np.argmax(p_copula)]
        agreement_features = np.zeros(8)
        proba_matrix = np.stack([p_stacking[:10], p_hmm[:10], p_copula[:10]])
        idx = 0
        for i in range(3):
            for j in range(i + 1, 3):
                corr = np.corrcoef(proba_matrix[i], proba_matrix[j])[0, 1]
                if not np.isnan(corr):
                    agreement_features[idx] = corr
                idx += 1
        mode_pred = max(set(all_preds), key=all_preds.count)
        agreement_features[6] = sum(1 for p in all_preds if p == mode_pred) / 3
        agreement_features[7] = np.var(proba_matrix.mean(axis=0))

        recent_perf = np.zeros(12)
        if self._rewards_history:
            recent_rewards = self._rewards_history[-10:]
            recent_perf[0] = np.mean(recent_rewards)
            if len(recent_rewards) >= 2:
                recent_perf[1] = (recent_rewards[-1] - recent_rewards[0]) / len(recent_rewards)
            hits = [r for r in recent_rewards if r > 0.5]
            recent_perf[2] = len(hits) / max(len(recent_rewards), 1)

            if self._model_performance_history:
                avg_perfs = {m: (np.mean(h) if h else 0.0)
                            for m, h in self._model_performance_history.items()}
                best_model = max(avg_perfs, key=avg_perfs.get)
                model_idx_map = {"stacking": 0, "hmm": 1, "copula": 2, "bayesian": 3}
                if best_model in model_idx_map:
                    recent_perf[3 + model_idx_map[best_model]] = 1.0

            if len(self._rewards_history) >= 5:
                recent_perf[8] = len([r for r in self._rewards_history[-5:] if r > 0.5]) / 5.0
            if len(self._rewards_history) >= 20:
                recent_perf[9] = len([r for r in self._rewards_history[-20:] if r > 0.5]) / 20.0

            if len(recent_rewards) >= 3:
                first_deriv = (recent_rewards[-1] - recent_rewards[-3]) / 2
                if len(recent_rewards) >= 5:
                    second_deriv = (first_deriv - (recent_rewards[-3] - recent_rewards[-5]) / 2) / 2
                    recent_perf[10] = np.clip(second_deriv, -1.0, 1.0)
                    recent_perf[11] = np.clip(first_deriv, -1.0, 1.0)

        current_weights = list(self.weights.values())
        weight_entropy = -np.sum(current_weights * np.log(current_weights + 1e-12))
        weight_mean = np.mean(current_weights)
        weight_std = np.std(current_weights)
        weight_skewness = 0.0
        if weight_std > 1e-8:
            weight_skewness = np.mean(((np.array(current_weights) - weight_mean) / weight_std) ** 3)

        prev_weights = getattr(self, '_prev_weights', current_weights)
        weight_momentum = np.array(current_weights) - np.array(prev_weights)
        weight_change_rate = np.linalg.norm(weight_momentum) / (np.linalg.norm(prev_weights) + 1e-8)
        self._prev_weights = current_weights.copy()

        weight_dist_features = np.array([
            weight_entropy / np.log(4),
            weight_mean,
            weight_std,
            weight_skewness,
            np.max(current_weights),
            np.min(current_weights),
            float(np.sign(weight_momentum[np.argmax(np.abs(weight_momentum))])),
            float(weight_change_rate)
        ])

        position_perf = np.zeros(10)
        if self._prediction_results_cache:
            recent_cache = self._prediction_results_cache[-20:]
            for pi, pos in enumerate(POSITIONS):
                pos_hits = sum(
                    1 for entry in recent_cache
                    if pos in entry.get('actual', {}) and
                       pos in entry.get('prediction', {}) and
                       entry['actual'][pos] in entry['prediction'][pos][:3]
                )
                position_perf[pi] = pos_hits / max(len(recent_cache), 1)

            for pi, pos in enumerate(POSITIONS):
                stacking_prefers = sum(
                    1 for entry in recent_cache[-10:]
                    if pos in entry.get('prediction', {}) and
                       len(entry['prediction'][pos]) > 0 and
                       entry['prediction'][pos][0] == entry.get('actual', {}).get(pos, -1)
                ) / max(min(len(recent_cache), 10), 1)
                position_perf[5 + pi] = stacking_prefers

        time_decay_perf = np.zeros(10)
        if self._rewards_history:
            rewards_arr = np.array(self._rewards_history)
            n = len(rewards_arr)

            half_lives = [5, 15, 30, 60]
            for hi, hl in enumerate(half_lives):
                decay_factors = np.exp(-np.arange(n) * np.log(2) / hl)[::-1]
                ewma = np.sum(rewards_arr * decay_factors) / (decay_factors.sum() + 1e-12)
                time_decay_perf[hi] = ewma

            max_streak = cur_streak = 0
            for r in reversed(rewards_arr):
                if r > 0.5:
                    cur_streak += 1
                    max_streak = max(max_streak, cur_streak)
                else:
                    cur_streak = 0
            time_decay_perf[4] = min(max_streak, 10) / 10.0

            miss_streak = 0
            for r in reversed(rewards_arr):
                if r <= 0.5:
                    miss_streak += 1
                else:
                    break
            time_decay_perf[5] = min(miss_streak, 10) / 10.0

            if n >= 10:
                time_decay_perf[6] = float(np.percentile(rewards_arr[-50:], 75)) if n >= 50 else float(np.percentile(rewards_arr, 75))
                time_decay_perf[7] = float(np.percentile(rewards_arr[-50:], 25)) if n >= 50 else float(np.percentile(rewards_arr, 25))

            if n >= 5:
                rolling_std_5 = np.std(rewards_arr[-5:])
                rolling_std_20 = np.std(rewards_arr[-min(20, n):])
                time_decay_perf[8] = rolling_std_5
                time_decay_perf[9] = rolling_std_20

        model_confidence_variance = np.zeros(8)
        all_model_probas = {'stacking': p_stacking, 'hmm': p_hmm, 'copula': p_copula}
        for mi, (mname, proba) in enumerate(all_model_probas.items()):
            confidences_per_pos = []
            for _pos in POSITIONS:
                pos_hist = self._model_performance_history.get(mname, [])
                if pos_hist:
                    confidences_per_pos.append(np.mean(pos_hist[-5:]) if len(pos_hist) >= 5 else np.mean(pos_hist))
                else:
                    confidences_per_pos.append(float(np.max(proba)))
            if len(confidences_per_pos) >= 2:
                model_confidence_variance[mi] = np.std(confidences_per_pos)
                model_confidence_variance[4 + mi] = np.max(confidences_per_pos) - np.min(confidences_per_pos)

        cross_disagreement = np.zeros(4)
        vote_counts = {}
        for pred in all_preds:
            vote_counts[pred] = vote_counts.get(pred, 0) + 1
        total_votes = len(all_preds)
        vote_entropy = -sum((c / total_votes) * np.log(c / total_votes + 1e-12) for c in vote_counts.values())
        cross_disagreement[0] = vote_entropy / np.log(min(total_votes, 10) + 1e-12)

        max_probas = [np.max(p) for p in [p_stacking, p_hmm, p_copula]]
        cross_disagreement[1] = (max(max_probas) - min(max_probas)) / (max(max_probas) + 1e-8)

        sorted_probas = sorted(max_probas, reverse=True)
        if len(sorted_probas) >= 2:
            cross_disagreement[2] = sorted_probas[1] / (sorted_probas[0] + 1e-12)

        pred_proba_values = [p_stacking[np.argmax(p_stacking)], p_hmm[np.argmax(p_hmm)], p_copula[np.argmax(p_copula)]]
        cross_disagreement[3] = np.sum(pred_proba_values) / (len(pred_proba_values) * max(pred_proba_values) + 1e-12)

        state = np.concatenate([
            feature_part,
            model_probas,
            confidence_features,
            entropy_features,
            agreement_features,
            recent_perf,
            weight_dist_features,
            position_perf,
            time_decay_perf,
            model_confidence_variance,
            cross_disagreement
        ])

        target_dim = 128
        if len(state) < target_dim:
            state = np.pad(state, (0, target_dim - len(state)))
        return state[:target_dim]
        
    def _get_dynamic_weights(self, p_stacking: np.ndarray, p_hmm: np.ndarray, p_copula: np.ndarray, 
                            p_bsts: np.ndarray, p_mamba: np.ndarray, p_itransformer: np.ndarray) -> np.ndarray:
        """基于模型性能动态调整权重 - 强化随机性类型整合
        
        Args:
            p_stacking: Stacking模型的预测概率
            p_hmm: HMM模型的预测概率
            p_copula: Copula模型的预测概率
            p_bsts: BSTS模型的预测概率
            p_mamba: Mamba模型的预测概率
            p_itransformer: iTransformer模型的预测概率
            
        Returns:
            np.ndarray: 动态调整后的权重
        """
        # 计算每个模型的预测质量指标
        def calculate_model_quality(probs):
            """计算模型预测质量"""
            # 1. 概率分布的峰度（值越大，预测越集中）
            peakiness = np.max(probs)
            # 2. 概率分布的熵（值越小，预测越确定）
            entropy = -np.sum(probs * np.log(probs + 1e-12))
            # 3. 综合质量分数
            quality = peakiness * (1 - entropy / np.log(10))
            return quality
        
        # 计算每个模型的质量分数
        quality_stacking = calculate_model_quality(p_stacking)
        quality_hmm = calculate_model_quality(p_hmm)
        quality_copula = calculate_model_quality(p_copula)
        quality_bsts = calculate_model_quality(p_bsts)
        quality_mamba = calculate_model_quality(p_mamba)
        quality_itransformer = calculate_model_quality(p_itransformer)
        
        # 基础权重 - 考虑不同模型对不同类型随机性的捕捉能力
        # Stacking: 认知随机 + 确定性规则的伪随机
        # HMM: 混沌复杂系统的随机 + 初始条件敏感性
        # Copula: 认知随机 + 混沌复杂系统的随机
        # BSTS: 确定性规则的伪随机 + 趋势方向
        # Mamba: 计算不可约 + 混沌复杂系统的随机
        # iTransformer: 初始条件敏感性 + 趋势方向
        base_weights = np.array([0.25, 0.20, 0.15, 0.10, 0.15, 0.15])
        
        # 质量分数
        quality_scores = np.array([
            quality_stacking,
            quality_hmm,
            quality_copula,
            quality_bsts,
            quality_mamba,
            quality_itransformer
        ])
        
        # 归一化质量分数
        quality_scores = quality_scores / (np.sum(quality_scores) + 1e-12)
        
        # 动态权重 = 基础权重 * 质量分数
        dynamic_weights = base_weights * quality_scores
        
        # 确保权重不为负
        dynamic_weights = np.maximum(dynamic_weights, 0.01)
        
        return dynamic_weights

    def _compute_enhanced_reward(self, prediction: Dict, actual: Dict) -> Tuple[float, Dict[str, float]]:
        """计算增强奖励 V3 - 多维度位置加权奖励函数

        位置重要性权重 (PL5排列5特点: 万位和个位信息量更大):
            wan=1.4, qian=1.0, bai=0.9, shi=1.0, ge=1.4

        奖励组成:
        1. 基础联合命中奖励 (0~1.2): 多位置同时命中的比例，考虑位置重要性
        2. Top-k覆盖率奖励 (0~0.35): 实际值落在top-k预测中的位置越靠前奖励越高，位置加权
        3. 概率校准奖励 (-0.1~0.15): 预测概率与实际命中率的一致性
        4. 熵正则化项 (0~0.15): 鼓励适度的权重多样性
        5. 连续命中链奖励 (0~0.25): 鼓励多位置连续命中模式
        6. 关键位置命中加成 (0~0.3): 万位/个位命中额外奖励

        Returns:
            (total_reward, per_model_scores): 总奖励和各模型得分
        """
        top_k = 3
        POSITION_IMPORTANCE = {"wan": 1.4, "qian": 1.0, "bai": 0.9, "shi": 1.0, "ge": 1.4}
        positions_hit = []
        weighted_hits = []
        per_model_hits = {"stacking": 0, "hmm": 0, "copula": 0, "bayesian": 0}
        top_k_coverage = []
        key_position_bonus = 0.0

        for pos in POSITIONS:
            if pos not in prediction or pos not in actual:
                continue

            pred_info = prediction[pos]
            top_k_preds = pred_info.get('top_k', [])[:top_k]
            probabilities = pred_info.get('probabilities', [])
            actual_val = actual[pos]

            pos_importance = POSITION_IMPORTANCE.get(pos, 1.0)
            pos_hit = int(actual_val in top_k_preds)
            positions_hit.append(pos_hit)

            if actual_val in top_k_preds:
                rank = top_k_preds.index(actual_val)
                coverage_score = (top_k - rank) / top_k
                rank_weight = (top_k - rank) / top_k
                top_k_coverage.append(coverage_score * pos_importance)

                if rank < len(probabilities):
                    predicted_proba = probabilities[rank]
                    calibration_error = abs(predicted_proba - 1.0 / (rank + 1))
                else:
                    calibration_error = 0.5

                weighted_hits.append(pos_importance * (1.0 + rank_weight * 0.5))

                if pos in ("wan", "ge"):
                    key_position_bonus += 0.06 * pos_importance * (1.0 - rank * 0.15)
            else:
                top_k_coverage.append(0.0)
                calibration_error = 0.5

            weights_used = pred_info.get('weights_used', {})
            model_names = ["stacking", "hmm", "copula", "bsts"]
            for mname in ["stacking", "hmm", "copula", "bayesian"]:
                wkey = "bsts" if mname == "bayesian" else mname
                w = weights_used.get(wkey, self.DEFAULT_WEIGHTS.get(mname, 0.25))
                if pos_hit and w > 0:
                    hit_contribution = w * (1.0 - calibration_error * 0.3) * pos_importance
                    per_model_hits[mname] += hit_contribution

        n_positions = len([p for p in POSITIONS if p in prediction and p in actual])
        raw_hit_rate = sum(positions_hit) / max(n_positions, 1)
        total_importance = sum(POSITION_IMPORTANCE.get(p, 1.0) for p in POSITIONS if p in prediction and p in actual)
        weighted_hit_rate = sum(weighted_hits) / max(total_importance, 1.0)
        joint_hit_rate = 0.7 * raw_hit_rate + 0.3 * min(weighted_hit_rate, 1.0)

        multi_position_bonus = 0.0
        if len(positions_hit) >= 3:
            consecutive_hits = 0
            max_consecutive = 0
            total_weighted_streak = 0.0
            current_streak_importance = 0.0
            for hi, h in enumerate(positions_hit):
                pos_name = POSITIONS[hi] if hi < len(POSITIONS) else ""
                pos_imp = POSITION_IMPORTANCE.get(pos_name, 1.0)
                if h == 1:
                    consecutive_hits += 1
                    max_consecutive = max(max_consecutive, consecutive_hits)
                    current_streak_importance += pos_imp
                else:
                    if consecutive_hits >= 2:
                        total_weighted_streak += current_streak_importance * consecutive_hits * 0.05
                    consecutive_hits = 0
                    current_streak_importance = 0.0
            if consecutive_hits >= 2:
                total_weighted_streak += current_streak_importance * consecutive_hits * 0.05

            if max_consecutive >= 4:
                multi_position_bonus = 0.20 * (max_consecutive / n_positions) * (total_weighted_streak + 1)
            elif max_consecutive >= 3:
                multi_position_bonus = 0.12 * (max_consecutive / n_positions)
            elif max_consecutive >= 2:
                multi_position_bonus = 0.05

        avg_topk_coverage = np.mean(top_k_coverage) if top_k_coverage else 0.0
        normalized_coverage = avg_topk_coverage / max(total_importance / n_positions, 0.9)
        topk_bonus = normalized_coverage * 0.35

        avg_calibration = 1.0 - np.mean([
            abs(p.get('probabilities', [0.1])[0] - 0.1)
            for p in prediction.values() if isinstance(p, dict) and p.get('probabilities')
        ]) if prediction and all(isinstance(p, dict) and p.get('probabilities') for p in prediction.values()) else 0.0
        calibration_reward = (avg_calibration - 0.5) * 0.2

        weights_entropy = 0.0
        if any('weights_used' in v for v in prediction.values() if isinstance(v, dict)):
            sample_weights = list(next(v['weights_used'].values())
                                  for v in prediction.values()
                                  if isinstance(v, dict) and 'weights_used' in v)
            if sample_weights:
                warr = np.array(sample_weights).mean(axis=0)
                weights_entropy = -np.sum(warr * np.log(warr + 1e-12)) / np.log(len(warr))

        entropy_regularization = min(weights_entropy, 1.0) * 0.15

        chain_bonus = min(key_position_bonus, 0.30)

        total_reward = (
            joint_hit_rate * 1.0 +
            multi_position_bonus +
            topk_bonus +
            max(calibration_reward, 0) +
            entropy_regularization +
            chain_bonus
        )
        total_reward = float(np.clip(total_reward, 0.0, 2.5))

        return total_reward, per_model_hits

    def update_with_feedback(self, prediction: Dict, actual: Dict):
        """根据实际结果更新RL优化器 + 跟踪模型表现 + 更新贝叶斯参数"""
        if self.rl_optimizer is None or not self.is_trained:
            return

        total_reward, per_model_scores = self._compute_enhanced_reward(prediction, actual)

        window = self._performance_window
        for model_name, score in per_model_scores.items():
            hist = self._model_performance_history[model_name]
            hist.append(score)
            if len(hist) > window:
                hist.pop(0)

        self._prediction_results_cache.append({
            "prediction": {p: prediction[p].get("top_k", [])[:5] for p in POSITIONS if p in prediction},
            "actual": {p: actual[p] for p in POSITIONS if p in actual},
            "reward": total_reward,
            "per_model_scores": per_model_scores.copy(),
            "timestamp": time.time()
        })
        if len(self._prediction_results_cache) > 200:
            self._prediction_results_cache.pop(0)

        for model_name, hit_score in per_model_scores.items():
            params = self._thompson_weight_params[model_name]
            if hit_score > 0.3:
                params["alpha"] += hit_score * 0.8
                params["beta"] += (1.0 - hit_score) * 0.2
            else:
                params["alpha"] += 0.1
                params["beta"] += 0.6
            params["alpha"] = max(params["alpha"], 0.5)
            params["beta"] = max(params["beta"], 0.5)

        state = self._build_rl_state(
            np.random.randn(min(len(self.feature_cols), 30)),
            np.random.dirichlet(np.ones(10)),
            np.random.dirichlet(np.ones(10)),
            np.random.dirichlet(np.ones(10))
        )

        action = np.array([
            prediction[pos].get('weights_used', {}).get('stacking', 0.4)
            for pos in POSITIONS[:4]
        ]) if isinstance(prediction, dict) and 'wan' in prediction else np.ones(4) / 4

        if self.rl_optimizer is not None:
            self.rl_optimizer.memory.push(state, action, total_reward,
                                          np.zeros(128), True)
            self._rewards_history.append(total_reward)
            self._states_history.append(state)

            if len(self.rl_optimizer.memory.buffer) >= self.rl_optimizer.config.batch_size:
                self.rl_optimizer.update(state, action, total_reward, np.zeros(128), True)

    def fit_rl_online(self, n_episodes: int = 50):
        """在线训练RL优化器"""
        if not self._states_history or not self._rewards_history:
            logger.warning("[EnhancedPredictor] 无历史数据用于RL训练")
            return

        if self.rl_optimizer is not None:
            logger.info(f"[EnhancedPredictor] 开始RL在线训练, {len(self._states_history)} 条历史")
            self.rl_optimizer.fit(self._states_history, self._rewards_history, n_episodes=n_episodes)
            logger.info("[EnhancedPredictor] RL在线训练完成")
        else:
            logger.warning("[EnhancedPredictor] RL优化器不可用，跳过在线训练")

    def _get_history_based_weights(self) -> np.ndarray:
        """基于历史表现的动态权重调整策略

        当RL未训练或不可用时，使用此策略：
        1. 计算各模型近期滚动平均表现
        2. 使用softmax将表现分数转换为权重
        3. 对表现极差的模型施加最小权重约束
        4. 考虑表现趋势（上升/下降）进行微调

        Returns:
            weights: 归一化的权重向量 (stacking, hmm, copula, bayesian)
        """
        model_names = ["stacking", "hmm", "copula", "bayesian"]
        raw_scores = []
        temperature = 2.0

        for mname in model_names:
            hist = self._model_performance_history.get(mname, [])
            if len(hist) >= 5:
                recent = hist[-min(len(hist), self._performance_window):]
                avg_score = np.mean(recent)

                if len(recent) >= 10:
                    first_half = np.mean(recent[:len(recent)//2])
                    second_half = np.mean(recent[len(recent)//2:])
                    trend = (second_half - first_half) / (abs(first_half) + 1e-8)
                    trend_bonus = max(0, min(trend * 0.5, 0.3))
                else:
                    trend_bonus = 0.0

                score_variance = np.std(recent) if len(recent) > 1 else 0.0
                stability_bonus = max(0, 0.1 - score_variance * 0.5)

                final_score = avg_score + trend_bonus + stability_bonus
                raw_scores.append(max(final_score, 0.01))
            elif len(hist) > 0:
                raw_scores.append(np.mean(hist) + 0.1)
            else:
                raw_scores.append(0.1)

        scores_array = np.array(raw_scores)
        exp_scores = np.exp(scores_array / temperature)
        weights = exp_scores / (exp_scores.sum() + 1e-12)

        min_weight = 0.05
        weights = np.clip(weights, min_weight, None)
        weights = weights / (weights.sum() + 1e-12)

        logger.debug(f"[DynamicWeights] 原始得分: {dict(zip(model_names, [f'{s:.3f}' for s in raw_scores]))}, "
                     f"权重: {dict(zip(model_names, [f'{w:.3f}' for w in weights]))}")
        return weights

    def adjust_weights_by_history(self, history: List[Dict[str, Any]],
                                   ema_alpha: float = 0.3,
                                   min_weight: float = 0.05,
                                   max_weight: float = 0.50) -> Dict[str, Any]:
        """基于历史表现的指数移动平均(EMA)动态权重调整

        核心算法:
        1. 从历史记录中提取各模型的逐次命中得分
        2. 使用EMA平滑各模型的近期表现，降低噪声
        3. 将EMA表现分数通过softmax转换为权重
        4. 应用最小/最大权重约束防止极端化
        5. 输出权重不确定性估计（基于得分离散度）

        Args:
            history: 历史预测结果列表，每项包含 per_model_scores 字典
            ema_alpha: EMA平滑系数 (0~1)，越大越重视近期数据，默认0.3
            min_weight: 单模型最小权重约束，默认0.05
            max_weight: 单模型最大权重约束，默认0.50

        Returns:
            调整结果字典:
            - weights: Dict[str, float] 调整后的权重
            - ema_scores: Dict[str, float] 各模型的EMA平滑得分
            - raw_hit_rates: Dict[str, float] 各模型的原始命中率
            - uncertainty: Dict 权重不确定性估计
            - adjustment_magnitude: float 权重调整幅度
        """
        model_names = ["stacking", "hmm", "copula", "bayesian"]

        if not history:
            logger.warning("[AdjustWeightsByHistory] 无历史数据，返回默认权重")
            default_w = self.DEFAULT_WEIGHTS.copy()
            return {
                "weights": default_w,
                "ema_scores": {m: 0.25 for m in model_names},
                "raw_hit_rates": {m: 0.0 for m in model_names},
                "uncertainty": {"std": 0.0, "confidence": "none"},
                "adjustment_magnitude": 0.0
            }

        model_raw_scores: Dict[str, List[float]] = {m: [] for m in model_names}
        for entry in history:
            pms = entry.get("per_model_scores", {})
            for mname in model_names:
                score = pms.get(mname, 0.0)
                model_raw_scores[mname].append(score)

        raw_hit_rates = {}
        for mname in model_names:
            scores = model_raw_scores[mname]
            if scores:
                hits = sum(1 for s in scores if s > 0.3)
                raw_hit_rates[mname] = hits / len(scores)
            else:
                raw_hit_rates[mname] = 0.0

        ema_scores: Dict[str, float] = {}
        for mname in model_names:
            scores = model_raw_scores[mname]
            if not scores:
                ema_scores[mname] = 0.1
                continue

            ema_val = scores[0]
            for s in scores[1:]:
                ema_val = ema_alpha * s + (1 - ema_alpha) * ema_val
            ema_scores[mname] = max(ema_val, 0.01)

        trend_adjusted_scores = {}
        for mname in model_names:
            scores = model_raw_scores[mname]
            base_score = ema_scores[mname]

            if len(scores) >= 10:
                first_half_ema = scores[0]
                for s in scores[:len(scores)//2]:
                    first_half_ema = ema_alpha * s + (1 - ema_alpha) * first_half_ema

                second_half_ema = scores[len(scores)//2]
                for s in scores[len(scores)//2:]:
                    second_half_ema = ema_alpha * s + (1 - ema_alpha) * second_half_ema

                trend = (second_half_ema - first_half_ema) / (abs(first_half_ema) + 1e-8)
                trend_bonus = np.clip(trend * 0.3, -0.15, 0.20)
            else:
                trend_bonus = 0.0

            score_variance = np.std(scores) if len(scores) > 1 else 0.0
            stability_penalty = min(0.10, score_variance * 0.3)

            final_score = base_score + trend_bonus - stability_penalty
            trend_adjusted_scores[mname] = max(final_score, 0.01)

        temperature = 2.0
        scores_array = np.array([trend_adjusted_scores[m] for m in model_names])
        exp_scores = np.exp(scores_array / temperature)
        raw_weights = exp_scores / (exp_scores.sum() + 1e-12)

        clipped_weights = np.clip(raw_weights, min_weight, max_weight)
        normalized_weights = clipped_weights / (clipped_weights.sum() + 1e-12)

        weight_dict = {m: float(normalized_weights[i]) for i, m in enumerate(model_names)}

        prev_weights_arr = np.array([self.weights.get(m, 0.25) for m in model_names])
        adj_magnitude = float(np.linalg.norm(normalized_weights - prev_weights_arr))

        score_values = list(trend_adjusted_scores.values())
        uncertainty_std = float(np.std(score_values)) if len(score_values) > 1 else 0.0
        uncertainty_mean = float(np.mean(score_values))
        cv = uncertainty_std / (abs(uncertainty_mean) + 1e-8)

        if cv < 0.2:
            confidence_level = "high"
        elif cv < 0.5:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        self.weights = weight_dict.copy()

        logger.info(
            f"[AdjustWeightsByHistory] EMA调整完成 | "
            f"alpha={ema_alpha} | "
            f"权重={dict(zip(model_names, [f'{w:.3f}' for w in normalized_weights]))} | "
            f"EMA得分={dict(zip(model_names, [f'{s:.3f}' for s in ema_scores.values()]))} | "
            f"命中率={dict(zip(model_names, [f'{r:.1%}' for r in raw_hit_rates.values()]))} | "
            f"调整幅度={adj_magnitude:.4f} | 置信度={confidence_level}"
        )

        return {
            "weights": weight_dict,
            "ema_scores": ema_scores,
            "raw_hit_rates": raw_hit_rates,
            "uncertainty": {
                "std": uncertainty_std,
                "cv": cv,
                "score_range": [float(min(score_values)), float(max(score_values))],
                "confidence": confidence_level,
                "n_samples": len(history)
            },
            "adjustment_magnitude": adj_magnitude
        }

    def _get_bayesian_weights_with_uncertainty(self, n_samples: int = 1000
                                              ) -> Tuple[np.ndarray, Dict[str, Dict[str, float]]]:
        """基于Thompson Sampling的贝叶斯权重不确定量化 V2

        使用Beta分布作为各模型权重的先验/后验分布：
        - 每个模型的权重从 Beta(alpha, beta) 中采样
        - 多次采样得到权重的后验分布
        - 输出点估计（均值）+ 多级置信区间 + 不确定性综合评估

        增强输出:
        - 95% / 80% / 50% 多级置信区间
        - 权重间相关性矩阵
        - 全局不确定性指标（总熵、有效维度数）
        - 模型排名概率分布
        - 不确定性可视化数据

        Args:
            n_samples: Thompson采样次数，用于估计置信区间

        Returns:
            (mean_weights, uncertainty_info):
                mean_weights: 权重点估计 (4维)
                uncertainty_info: 包含每个模型的多级CI、全局不确定性等信息
        """
        model_names = ["stacking", "hmm", "copula", "bayesian"]
        samples = np.zeros((n_samples, len(model_names)))

        for i, mname in enumerate(model_names):
            params = self._thompson_weight_params[mname]
            alpha = params["alpha"]
            beta_val = params["beta"]
            samples[:, i] = np.random.beta(alpha, beta_val, size=n_samples)

        row_sums = samples.sum(axis=1, keepdims=True)
        normalized_samples = samples / (row_sums + 1e-12)

        mean_weights = normalized_samples.mean(axis=0)
        std_weights = normalized_samples.std(axis=0)
        ci_lower_95 = np.percentile(normalized_samples, 2.5, axis=0)
        ci_upper_95 = np.percentile(normalized_samples, 97.5, axis=0)
        ci_lower_80 = np.percentile(normalized_samples, 10, axis=0)
        ci_upper_80 = np.percentile(normalized_samples, 90, axis=0)
        ci_lower_50 = np.percentile(normalized_samples, 25, axis=0)
        ci_upper_50 = np.percentile(normalized_samples, 75, axis=0)

        median_weights = np.median(normalized_samples, axis=0)
        mode_estimates = np.zeros(len(model_names))
        for i in range(len(model_names)):
            hist, bin_edges = np.histogram(normalized_samples[:, i], bins=20)
            mode_idx = np.argmax(hist)
            mode_estimates[i] = (bin_edges[mode_idx] + bin_edges[mode_idx + 1]) / 2

        weight_correlation = np.corrcoef(normalized_samples.T) if n_samples > 10 else np.eye(len(model_names))

        rank_counts = {mname: {j: 0 for j in range(len(model_names))} for mname in model_names}
        for sample_idx in range(n_samples):
            ranks = np.argsort(-normalized_samples[sample_idx])
            for rank_pos, model_idx in enumerate(ranks):
                rank_counts[model_names[model_idx]][rank_pos] += 1
        rank_probabilities = {
            mname: {f"rank_{r+1}": count / n_samples for r, count in ranks.items()}
            for mname, ranks in rank_counts.items()
        }

        global_entropy = -np.sum(mean_weights * np.log(mean_weights + 1e-12))
        effective_dim = np.exp(global_entropy)

        sample_entropies = [-np.sum(s * np.log(s + 1e-12)) for s in normalized_samples]
        avg_sample_entropy = float(np.mean(sample_entropies))
        entropy_std = float(np.std(sample_entropies))

        total_weight_variance = float(np.trace(np.cov(normalized_samples.T)))
        uncertainty_ratio = float(total_weight_variance / (np.mean(mean_weights ** 2) + 1e-8))

        most_certain_model_idx = int(np.argmin(std_weights))
        least_certain_model_idx = int(np.argmax(std_weights))

        uncertainty_info: Dict[str, Any] = {}
        for i, mname in enumerate(model_names):
            uncertainty_info[mname] = {
                "mean": float(mean_weights[i]),
                "median": float(median_weights[i]),
                "mode": float(mode_estimates[i]),
                "std": float(std_weights[i]),
                "ci_95": {"lower": float(ci_lower_95[i]), "upper": float(ci_upper_95[i])},
                "ci_80": {"lower": float(ci_lower_80[i]), "upper": float(ci_upper_80[i])},
                "ci_50": {"lower": float(ci_lower_50[i]), "upper": float(ci_upper_50[i])},
                "ci_95_width": float(ci_upper_95[i] - ci_lower_95[i]),
                "cv": float(std_weights[i] / (abs(mean_weights[i]) + 1e-8)),
                "alpha_beta": (
                    float(self._thompson_weight_params[mname]["alpha"]),
                    float(self._thompson_weight_params[mname]["beta"])
                ),
                "skewness": float(
                    ((mean_weights[i] - median_weights[i]) / (std_weights[i] + 1e-8))
                    if std_weights[i] > 1e-8 else 0.0
                ),
                "rank_probability": rank_probabilities.get(mname, {})
            }

        uncertainty_info["_global"] = {
            "total_entropy": float(global_entropy),
            "effective_dimensions": float(effective_dim),
            "avg_sample_entropy": avg_sample_entropy,
            "entropy_stability": float(entropy_std),
            "total_weight_variance": total_weight_variance,
            "uncertainty_ratio": uncertainty_ratio,
            "most_certain_model": model_names[most_certain_model_idx],
            "least_certain_model": model_names[least_certain_model_idx],
            "n_samples": n_samples
        }

        uncertainty_info["_correlation_matrix"] = {
            f"{model_names[i]}_{model_names[j]}": float(weight_correlation[i, j])
            for i in range(len(model_names)) for j in range(len(model_names))
        }

        overall_confidence = "high"
        if uncertainty_ratio > 1.5 or effective_dim < 1.5:
            overall_confidence = "low"
        elif uncertainty_ratio > 0.8 or effective_dim < 2.5:
            overall_confidence = "medium"
        uncertainty_info["_global"]["overall_confidence"] = overall_confidence

        logger.debug(
            f"[BayesianWeights V2] 点估计: {dict(zip(model_names, [f'{w:.3f}' for w in mean_weights]))}, "
            f"95% CI宽度: {[f'{ci_upper_95[j]-ci_lower_95[j]:.3f}' for j in range(len(model_names))]}, "
            f"有效维度={effective_dim:.2f}, 置信度={overall_confidence}"
        )

        return mean_weights, uncertainty_info

    def get_adaptive_weights(self, use_rl: bool = True,
                            include_uncertainty: bool = True
                            ) -> Tuple[np.ndarray, Optional[Dict]]:
        """获取自适应融合权重 - 统一入口

        权重选择优先级:
        1. RL优化器已训练 → 使用RL输出
        2. 有足够历史表现数据 → 使用动态历史策略
        3. 无任何信息 → 回退到贝叶斯Thompson采样 + 默认值混合

        Args:
            use_rl: 是否尝试使用RL优化器
            include_uncertainty: 是否返回不确定性信息

        Returns:
            (weights, uncertainty_info): 归一化权重向量和可选的不确定性字典
        """
        has_enough_history = any(
            len(h) >= 5 for h in self._model_performance_history.values()
        )

        if use_rl and self.rl_optimizer is not None and self.rl_optimizer.is_trained:
            dummy_state = np.zeros(128)
            weights = self.rl_optimizer.get_optimal_weights(dummy_state)
            weights = weights / (weights.sum() + 1e-12)

            uncertainty = None
            if include_uncertainty:
                _, uncertainty = self._get_bayesian_weights_with_uncertainty()
                uncertainty["source"] = "rl_optimized"

            return weights, uncertainty

        elif has_enough_history:
            weights = self._get_history_based_weights()

            uncertainty = None
            if include_uncertainty:
                _, uncertainty = self._get_bayesian_weights_with_uncertainty()
                uncertainty["source"] = "history_based"
                uncertainty["history_samples"] = {
                    m: len(h) for m, h in self._model_performance_history.items()
                }

            return weights, uncertainty

        else:
            thompson_weights, uncertainty = self._get_bayesian_weights_with_uncertainty()

            default_w = np.array(list(self.DEFAULT_WEIGHTS.values()))
            blend_factor = 0.6
            weights = blend_factor * default_w + (1 - blend_factor) * thompson_weights
            weights = weights / (weights.sum() + 1e-12)

            if include_uncertainty:
                uncertainty["source"] = "default_thompson_blend"
                uncertainty["blend_factor"] = blend_factor

            return weights, uncertainty

    def save_models(self, performance_metrics: Optional[Dict[str, float]] = None,
                    training_samples: int = 0, auto_backup: bool = True) -> None:
        """保存所有模型 - V10.0 完整格式 (含元数据/校验和/备份)

        Args:
            performance_metrics: 训练后的性能指标字典
            training_samples: 训练样本数量
            auto_backup: 是否在保存前自动创建当前版本备份
        """
        save_path = self.models_dir / MODEL_FILENAME
        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_MODEL_SAVE,
            {"path": str(save_path), "positions": list(self.stacking.keys()), "version": CURRENT_VERSION}
        )
        start_time = time.time()

        try:
            if auto_backup and save_path.exists():
                backup_name = self.version_manager.create_backup(save_path)
                if backup_name:
                    logger.info(f"[EnhancedPredictor V10] 保存前已自动备份: {backup_name}")

            save_data = {
                "stacking": self.stacking,
                "hmm_models": self.hmm_models,
                "copula_model": self.copula_model,
                "bsts_models": self.bsts_models,
                "mamba_predictor": self.mamba_predictor,
                "itransformer_predictor": self.itransformer_predictor,
                "bayesian_quantifier": self.bayesian_quantifier,
                "weights": self.weights,
                "is_trained": self.is_trained,
                "feature_cols": self.feature_cols,
                "trained_feature_dim": self.trained_feature_dim,
                "model_version": CURRENT_VERSION,
                "rl_training_history": self._rewards_history[-100:] if self._rewards_history else [],
                "_thompson_weight_params": self._thompson_weight_params,
                "_model_performance_history": self._model_performance_history,
            }

            v10_data = self.version_manager.wrap_v10_format(
                save_data,
                performance_metrics=performance_metrics,
                training_samples=training_samples
            )

            with open(save_path, 'wb') as f:
                pickle.dump(v10_data, f)

            meta = v10_data.get("metadata", {})
            checksum = v10_data.get("_v10_checksum", "")

            self.version_manager._log_change(
                VersionChangeLog(
                    timestamp=__import__('datetime').datetime.now().isoformat(),
                    operation="save",
                    from_version=meta.get("source_version", ""),
                    to_version=CURRENT_VERSION,
                    operator="system",
                    description=f"Save model V10.0 | features={len(self.feature_cols)} | "
                                f"checksum={checksum[:16] if checksum else 'N/A'}",
                    checksum_after=checksum,
                )
            )

            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_success(
                StructuredLogger.OPERATION_MODEL_SAVE,
                duration_ms,
                {"file_size_kb": save_path.stat().st_size / 1024 if save_path.exists() else 0,
                 "feature_count": len(self.feature_cols),
                 "version": CURRENT_VERSION,
                 "checksum": (checksum or "")[:16]}
            )
            logger.info(
                f"[EnhancedPredictor V10] 模型已保存: {save_path} | "
                f"version={CURRENT_VERSION} | features={len(self.feature_cols)} | "
                f"checksum={checksum[:16] if checksum else 'N/A'}"
            )

        except PermissionError as e:
            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_MODEL_SAVE,
                ModelSaveError(f"Permission denied saving model: {e}",
                              operation="save", original_error=e),
                duration_ms
            )
            raise ModelSaveError(
                f"Cannot save model (permission denied): {e}",
                operation="save", original_error=e
            )
        except OSError as e:
            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_MODEL_SAVE,
                ModelSaveError(f"IO error saving model: {e}",
                              operation="save", original_error=e),
                duration_ms
            )
            raise ModelSaveError(
                f"Cannot save model (IO error): {e}",
                operation="save", original_error=e
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_MODEL_SAVE,
                ModelSaveError(f"Unexpected error saving model: {e}",
                              operation="save", original_error=e),
                duration_ms
            )
            logger.error(f"[EnhancedPredictor] 保存模型异常: {e}", exc_info=True)
            raise ModelSaveError(
                f"Failed to save model: {e}", operation="save", original_error=e
            )

    def load_models(self, validate_integrity: bool = True,
                    auto_migrate: bool = True) -> bool:
        """加载模型 - V10.0 (含版本检测/自动迁移/完整性校验)

        Args:
            validate_integrity: 是否执行数据完整性校验
            auto_migrate: 是否自动将旧版格式迁移到V10.0

        Returns:
            是否加载成功
        """
        load_path = self.models_dir / MODEL_FILENAME
        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_MODEL_LOAD,
            {"path": str(load_path)}
        )
        start_time = time.time()

        if not load_path.exists():
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_MODEL_LOAD,
                ModelLoadError(f"Model file not found: {load_path}",
                              operation="load"),
                0
            )
            logger.warning(f"[EnhancedPredictor V10] 模型文件不存在: {load_path}")
            return False

        try:
            with open(load_path, 'rb') as f:
                state = pickle.load(f)

            detected_version = self.version_manager.detect_version(state)
            logger.info(f"[EnhancedPredictor V10] 检测到模型版本: {detected_version}")

            if validate_integrity:
                integrity_result = self.version_manager.validate_model_integrity(load_path)
                if not integrity_result["valid"]:
                    logger.error(
                        f"[EnhancedPredictor V10] 完整性校验失败: {integrity_result['errors']}"
                    )
                elif not integrity_result.get("checksum_match", True):
                    logger.warning(
                        f"[EnhancedPredictor V10] 校验和不匹配! 数据可能已损坏或被篡改"
                    )
                for w in integrity_result.get("warnings", []):
                    logger.warning(f"[EnhancedPredictor V10] 校验警告: {w}")

            if detected_version != CURRENT_VERSION and auto_migrate:
                if detected_version in ("V9.0", "unknown"):
                    logger.info(f"[EnhancedPredictor V10] 自动迁移: {detected_version} → {CURRENT_VERSION}")
                    state = self.version_manager.migrate_v9_to_v10(state)

                    should_resave = True
                    try:
                        with open(load_path, 'wb') as f:
                            pickle.dump(state, f)
                        logger.info("[EnhancedPredictor V10] 迁移后已保存为新格式")
                    except Exception as save_err:
                        logger.warning(f"[EnhancedPredictor V10] 迁移后保存失败(非致命): {save_err}")
                        should_resave = False

                    self.version_manager._log_change(
                        VersionChangeLog(
                            timestamp=__import__('datetime').datetime.now().isoformat(),
                            operation="load_migrate",
                            from_version=detected_version,
                            to_version=CURRENT_VERSION,
                            operator="system",
                            description=f"Auto-migrated on load from {detected_version}",
                            checksum_after=state.get("_v10_checksum", ""),
                        )
                    )

            self.stacking = state.get("stacking", {})
            self.hmm_models = state.get("hmm_models", {})
            self.copula_model = state.get("copula_model")
            self.bsts_models = state.get("bsts_models", {})

            self.mamba_predictor = state.get("mamba_predictor")
            self.itransformer_predictor = state.get("itransformer_predictor")
            self.bayesian_quantifier = state.get("bayesian_quantifier")

            v10_modules_present = (
                self.mamba_predictor is not None and
                self.itransformer_predictor is not None and
                self.bayesian_quantifier is not None
            )
            if self.is_trained and not v10_modules_present:
                logger.warning(
                    f"[EnhancedPredictor V10] 模型文件缺少V10模块 "
                    f"(mamba={self.mamba_predictor is not None}, "
                    f"itransformer={self.itransformer_predictor is not None}, "
                    f"bayesian={self.bayesian_quantifier is not None}), "
                    f"建议重新训练以获得完整V10功能"
                )

            loaded_weights = state.get("weights")
            if loaded_weights and isinstance(loaded_weights, dict):
                self.weights = loaded_weights
                logger.debug(f"[EnhancedPredictor V10] 已加载自定义权重: {list(self.weights.keys())}")
            else:
                self.weights = self.DEFAULT_WEIGHTS.copy()
                if loaded_weights:
                    logger.warning("[EnhancedPredictor V10] 加载的权重格式异常，使用默认值")

            self.is_trained = state.get("is_trained", False)
            self.feature_cols = state.get("feature_cols", [])
            self.trained_feature_dim = state.get("trained_feature_dim", 0)
            model_version = state.get("model_version", detected_version)

            if self.trained_feature_dim == 0 and len(self.feature_cols) > 0:
                logger.info(f"[EnhancedPredictor V10] 加载模型({model_version}), 特征维度未记录, 使用特征列数: {len(self.feature_cols)}")
                self.trained_feature_dim = len(self.feature_cols)

            restored_thompson = state.get("_thompson_weight_params")
            if isinstance(restored_thompson, dict) and restored_thompson:
                for key in self._thompson_weight_params:
                    if key in restored_thompson and isinstance(restored_thompson[key], dict):
                        self._thompson_weight_params[key].update(restored_thompson[key])

            restored_perf_history = state.get("_model_performance_history")
            if isinstance(restored_perf_history, dict) and restored_perf_history:
                for key in self._model_performance_history:
                    if key in restored_perf_history and isinstance(restored_perf_history[key], list):
                        self._model_performance_history[key] = restored_perf_history[key][-self._performance_window:]

            meta = state.get("metadata", {})
            if meta and isinstance(meta, dict):
                logger.info(
                    f"[EnhancedPredictor V10] 模型元数据 | version={meta.get('version', '?')} | "
                    f"created={meta.get('created_at', '?')} | features={meta.get('feature_count', '?')} | "
                    f"samples={meta.get('training_samples', '?')} | "
                    f"checksum={meta.get('checksum', 'N/A')[:16]}"
                )

            logger.info(f"[EnhancedPredictor V10] 模型版本: {model_version}, 训练特征维度: {self.trained_feature_dim}")

            _load_rl_modules()
            if _HAS_RL and ThompsonSamplingOptimizer is not None:
                self.thompson_sampler = ThompsonSamplingOptimizer(n_arms=len(POSITIONS))
            else:
                self.thompson_sampler = None
            
            if _HAS_RL and ModelWeightRLOptimizer is not None:
                rl_cfg = self._mc.rl_config()
                self.rl_optimizer = ModelWeightRLOptimizer(
                    n_models=rl_cfg.get('n_models', 4),
                    state_dim=rl_cfg.get('state_dim', 128))
            else:
                self.rl_optimizer = None

            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_success(
                StructuredLogger.OPERATION_MODEL_LOAD,
                duration_ms,
                {
                    "positions_loaded": len(self.stacking),
                    "feature_count": len(self.feature_cols),
                    "is_trained": self.is_trained,
                    "version": model_version,
                    "migrated": detected_version != CURRENT_VERSION
                }
            )
            logger.info(f"[EnhancedPredictor V10] 模型已加载: {load_path} (version={model_version})")
            return True

        except pickle.UnpicklingError as e:
            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_MODEL_LOAD,
                ModelLoadError(f"Corrupted model file: {e}",
                              operation="load", original_error=e),
                duration_ms
            )
            logger.error(f"[EnhancedPredictor] 模型文件损坏: {e}")
            return False
        except EOFError as e:
            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_MODEL_LOAD,
                ModelLoadError(f"Incomplete/truncated model file: {e}",
                              operation="load", original_error=e),
                duration_ms
            )
            logger.error(f"[EnhancedPredictor] 模型文件不完整: {e}")
            return False
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_MODEL_LOAD,
                ModelLoadError(f"Unexpected error loading model: {e}",
                              operation="load", original_error=e),
                duration_ms
            )
            logger.error(f"[EnhancedPredictor] 加载失败: {e}", exc_info=True)
            return False

    def validate_model_integrity(self) -> Dict[str, Any]:
        """校验当前模型文件的完整性和必要字段

        Returns:
            校验结果字典，包含 valid/version/errors/warnings/checksum_match/metadata
        """
        return self.version_manager.validate_model_integrity()

    def rollback_to_version(self, version: str) -> bool:
        """回滚到指定版本的最新备份

        Args:
            version: 目标版本号，如 "V10.0" 或 "V9.0"

        Returns:
            是否回滚成功
        """
        success = self.version_manager.rollback_to_version(version)
        if success:
            self.load_models(validate_integrity=False, auto_migrate=False)
            logger.info(f"[EnhancedPredictor V10] 已回滚到版本 {version} 并重新加载")
        return success

    def rollback_to_backup(self, backup_filename: str) -> bool:
        """回滚到指定的备份文件

        Args:
            backup_filename: 备份文件名，如 "backup_20260101_120000.pkl"

        Returns:
            是否回滚成功
        """
        success = self.version_manager.rollback_to_backup(backup_filename)
        if success:
            self.load_models(validate_integrity=False, auto_migrate=False)
            logger.info(f"[EnhancedPredictor V10] 已回滚到备份 {backup_filename} 并重新加载")
        return success

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有可用的模型备份

        Returns:
            备份信息列表，每项包含 filename/path/size_kb/created_time
        """
        return self.version_manager.list_backups()

    def get_version_history(self) -> List[Dict[str, Any]]:
        """获取模型的版本变更历史记录

        Returns:
            变更日志列表（按时间倒序）
        """
        return self.version_manager.get_version_history()

    def get_model_info(self) -> Dict[str, Any]:
        """获取当前加载模型的详细信息摘要

        Returns:
            模型信息字典：version/metadata/feature_dim/integrity/backups等
        """
        integrity = self.version_manager.validate_model_integrity()
        backups = self.version_manager.list_backups()
        history = self.version_manager.get_version_history()[:10]

        meta = integrity.get("metadata", {})
        return {
            "current_version": integrity.get("version", "unknown"),
            "is_trained": self.is_trained,
            "feature_count": len(self.feature_cols),
            "trained_feature_dim": self.trained_feature_dim,
            "positions_loaded": list(self.stacking.keys()),
            "integrity_valid": integrity.get("valid", False),
            "checksum_match": integrity.get("checksum_match", True),
            "metadata": {
                "created_at": meta.get("created_at"),
                "feature_count": meta.get("feature_count"),
                "training_samples": meta.get("training_samples"),
                "model_params_hash": (meta.get("model_params_hash") or "")[:16],
                "performance_metrics": meta.get("performance_metrics"),
                "source_version": meta.get("source_version"),
                "migration_notes": meta.get("migration_notes"),
            } if meta else None,
            "backups_available": len(backups),
            "latest_backup": backups[-1] if backups else None,
            "recent_changes": history,
        }

    @classmethod
    def as_tool(cls, **predictor_kwargs) -> "PredictorTool":
        """创建 PredictorTool 工具实例并绑定当前预测器

        将 EnhancedPL5Predictor 实例封装为标准工具接口，
        使其可通过 ToolContext 共享和 ToolRegistry 管理。

        Args:
            predictor_kwargs: 传递给 EnhancedPL5Predictor.__init__ 的参数

        Returns:
            PredictorTool 实例（内部持有已初始化的 predictor）
        """
        from src.tools.core_tools import PredictorTool

        predictor_instance = cls(**predictor_kwargs)
        tool = PredictorTool()
        tool._predictor = predictor_instance
        logger.info(f"[EnhancedPredictor V10] as_tool(): 已创建 PredictorTool 实例 (trained={predictor_instance.is_trained})")
        return tool

    @classmethod
    def get_capabilities(cls) -> Dict[str, Any]:
        """返回模型能力描述字典 (V10.0 格式)

        提供完整的模型能力清单，供工具发现、文档生成和运行时决策使用。

        Returns:
            能力描述字典，包含以下维度:
            - version: 模型版本号
            - prediction: 预测能力（位置/Top-K/不确定性/权重）
            - models: 子模型组件列表及状态
            - features: 特征工程相关能力
            - learning: 自学习与优化能力
            - reliability: 可靠性保障机制
            - tools: 已注册的工具接口列表
        """
        from src.tools.base import get_registry, ToolLayer

        registry = get_registry()
        core_tools = registry.list_by_layer(ToolLayer.CORE)

        return {
            "version": "V10.0",
            "class_name": "EnhancedPL5Predictor",
            "prediction": {
                "positions": POSITIONS.copy(),
                "top_k_range": [1, 10],
                "default_top_k": 8,
                "supports_uncertainty": True,
                "uncertainty_method": "entropy_normalization",
                "weight_adaptation": {
                    "rl_optimizer": "Actor-Critic with Thompson Sampling",
                    "history_based": "EMA dynamic weights",
                    "bayesian": "Beta posterior with multi-level CI",
                    "confidence_levels": ["95%", "80%", "50%"],
                },
                "output_format": {
                    "per_position": ["top_k", "probabilities", "uncertainty", "weights_used"],
                    "fallback": "uniform_distribution",
                },
            },
            "models": {
                "stacking": {
                    "type": "StackingEnsemble V2",
                    "base_learners": ["RandomForest", "GradientBoosting", "ExtraTrees", "AdaBoost",
                                     "LightGBM (optional)", "XGBoost (optional)"],
                    "meta_learner": "LogisticRegression / SGD ElasticNet (auto-select)",
                    "cv_folds": 5,
                    "enhanced_meta_features": True,
                },
                "hmm": {
                    "type": "HiddenMarkovModel",
                    "states": "auto-select (default=4)",
                    "mixtures": 2,
                },
                "copula": {
                    "type": "MultivariateCopula",
                    "copula_types": ["gaussian"],
                    "purpose": "joint_probability_adjustment",
                },
                "bsts": {
                    "type": "BayesianStructuralTimeSeries",
                    "components": ["trend", "seasonality", "outlier_detection"],
                },
                "rl": {
                    "type": "ModelWeightRLOptimizer (Actor-Critic)",
                    "state_dim": 128,
                    "reward_function": "enhanced_v3_multi_dimensional",
                },
                "thompson_sampling": {
                    "type": "ThompsonSamplingOptimizer",
                    "arms": len(POSITIONS),
                    "posterior": "Beta(alpha, beta)",
                },
            },
            "features": {
                "engineer_version": "FeatureEngineerV10",
                "feature_groups": [
                    "fibonacci", "markov", "fourier", "extreme", "pattern",
                    "momentum", "entropy", "chaos", "cross_correlation",
                    "garch", "granger", "time_series", "statistical",
                    "nonlinear", "pattern_recognition", "deep_learning",
                ],
                "selection_methods": ["random_forest", "mutual_info", "rfe", "chi2"],
                "scaling_methods": ["standard", "minmax", "robust", "none"],
                "drift_detection": {"psi_threshold": 0.2, "ks_threshold": 0.05},
                "cache": "LRU hash-based",
            },
            "learning": {
                "self_learning_version": "V10.0",
                "retrain_trigger": ["mann_kendall_trend", "dynamic_threshold", "urgent_alert"],
                "suggestion_types": ["parameter_adjustment", "model_retraining",
                                     "data_quality", "strategy_change"],
                "priority_levels": ["urgent", "important", "regular"],
                "effect_estimation": "confidence_interval_with_historical_feedback",
                "feedback_loop": "record_suggestion_outcome -> update_effect_model",
            },
            "reliability": {
                "model_versioning": "V10.0 format with checksum and metadata",
                "integrity_check": "SHA256 checksum validation",
                "auto_backup": "before_save",
                "auto_migration": "V9.0/V10.0 -> V10.0 on load",
                "error_recovery": "fallback_to_cache / fallback_to_uniform",
                "structured_logging": "StructuredLogger with operation tracking",
            },
            "tools": {
                "core_tools_registered": list(core_tools.keys()),
                "tool_count": len(core_tools),
                "as_tool_available": True,
            },
        }
