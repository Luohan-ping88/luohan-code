#!/usr/bin/env python3
"""快速训练脚本 - 生成一个可用的基础模型以完成日循环任务"""
import sys
import os
import logging
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("quick_train")

sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.enhanced_predictor import (
    EnhancedPL5Predictor, POSITIONS, StackingEnsemble,
    HiddenMarkovModel, BayesianStructuralTimeSeries, MultivariateCopula
)
from src.core.config import get_model_config

logger.info("开始快速训练...")

collector = PL5DataCollector()
df = collector.update_data()
logger.info(f"数据加载完成: {len(df)} 条")

MAX_ROWS = 1000
if len(df) > MAX_ROWS:
    df_train = df.tail(MAX_ROWS).reset_index(drop=True)
    logger.info(f"截断数据: {len(df)} -> {MAX_ROWS} 条")
else:
    df_train = df

engineer = FeatureEngineer()
df_features = engineer.extract_all_features(df_train, select_top=100, feature_selection_method='model_based')
logger.info(f"特征工程完成: {df_features.shape[1]} 列")

feature_cols = [c for c in df_features.columns if c not in ['date','period','full_number','parse_line','wan','qian','bai','shi','ge']]
logger.info(f"特征列数: {len(feature_cols)}")

mc = get_model_config()
predictor = EnhancedPL5Predictor(model_config=mc)

X = df_features[feature_cols].fillna(0).values
predictor.feature_cols = feature_cols
predictor.trained_feature_dim = X.shape[1]

for pos in POSITIONS:
    logger.info(f"训练位置 {pos}...")
    y = df_features[pos].values.astype(int)
    
    stacking = StackingEnsemble(model_config=mc)
    n_base = len(stacking.BASE_MODELS)
    
    from sklearn.model_selection import TimeSeriesSplit
    cv_folds = 2
    tscv = TimeSeriesSplit(n_splits=cv_folds)
    
    raw_meta_X = np.zeros((len(X), n_base * 10))
    base_fitted = {}
    
    for b_idx, (name, base_fn) in enumerate(stacking.BASE_MODELS.items()):
        clf = base_fn()
        oof_proba = np.zeros((len(X), 10))
        
        for fold_tr, fold_val in tscv.split(X):
            try:
                clf_fold = type(clf)(**clf.get_params())
                clf_fold.fit(X[fold_tr], y[fold_tr])
                raw = clf_fold.predict_proba(X[fold_val])
                classes = clf_fold.classes_
                for i, val_idx in enumerate(fold_val):
                    p = np.zeros(10)
                    for ci, c in enumerate(classes):
                        if 0 <= c <= 9:
                            p[c] = raw[i, ci]
                    oof_proba[val_idx] = p
            except Exception as e:
                logger.warning(f"  折叠训练失败: {e}")
        
        raw_meta_X[:, b_idx*10:(b_idx+1)*10] = oof_proba
        clf.fit(X, y)
        base_fitted[name] = clf
    
    stacking.position_models[pos] = base_fitted
    
    meta_X = raw_meta_X
    best_clf = LogisticRegression(C=1.0, max_iter=200, solver='lbfgs', random_state=42)
    best_clf.fit(meta_X, y)
    stacking.meta_models[pos] = best_clf
    stacking.meta_scores[pos] = 0.1
    stacking._fitted = True
    
    predictor.stacking[pos] = stacking
    
    try:
        hmm = HiddenMarkovModel(n_states=2, n_mixtures=1, random_state=42)
        seq = y.reshape(-1, 1)
        hmm.fit(seq)
        predictor.hmm_models[pos] = hmm
        logger.info(f"  HMM训练完成")
    except Exception as e:
        logger.warning(f"  HMM训练失败: {e}")
        predictor.hmm_models[pos] = None
    
    try:
        bsts = BayesianStructuralTimeSeries(trend_window=10, n_posterior_samples=10)
        bsts.fit(seq)
        predictor.bsts_models[pos] = bsts
        logger.info(f"  BSTS训练完成")
    except Exception as e:
        logger.warning(f"  BSTS训练失败: {e}")
        predictor.bsts_models[pos] = None

try:
    position_matrix = df_features[POSITIONS].values.astype(float)
    predictor.copula_model = MultivariateCopula(copula_type='gaussian', regularization=1e-6, auto_select=False)
    predictor.copula_model.fit(position_matrix)
    logger.info("Copula模型训练完成")
except Exception as e:
    logger.warning(f"Copula训练失败: {e}")
    predictor.copula_model = None

predictor.mamba_predictor = None
predictor.itransformer_predictor = None
predictor.bayesian_quantifier = None
predictor.thompson_sampler = None
predictor.rl_optimizer = None

predictor.is_trained = bool(predictor.stacking) and predictor.copula_model is not None
logger.info(f"模型训练完成: is_trained={predictor.is_trained}")

predictor.save_models()
logger.info("模型保存成功!")

model_file = Path("models/enhanced_predictor_v10.pkl")
logger.info(f"模型文件大小: {model_file.stat().st_size / 1024 / 1024:.2f} MB")
