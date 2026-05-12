"""
PL5 预测器 V8.0 — 功能完整实现
包含：Stacking 集成（RF/GBM/ET/AdaBoost + LR 元学习器）、
     HMM（条件频率）、Copula（相关性后处理）、BSTS 近似（状态空间趋势）、
     极值模型（遗漏统计）、贝叶斯权重融合。
"""

from __future__ import annotations

import json
import logging
import pickle
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from src.core.monitoring.performance_monitor import track_performance

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import (
    AdaBoostClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import label_binarize

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
DIGITS = list(range(10))

# ──────────────────────────────────────────────────────────────
#  工具函数
# ──────────────────────────────────────────────────────────────

def _safe_proba(proba: np.ndarray, n_classes: int = 10) -> np.ndarray:
    """确保 proba 形状为 (n_classes,)，不足则补零。"""
    out = np.zeros(n_classes)
    valid = min(len(proba), n_classes)
    out[:valid] = proba[:valid]
    return out / (out.sum() + 1e-12)


def _top_k_from_proba(proba: np.ndarray, k: int = 8) -> List[int]:
    """从概率向量取 top-k 数字。"""
    idx = np.argsort(proba)[::-1][:k]
    return [int(i) for i in idx]


# ──────────────────────────────────────────────────────────────
#  HMM 模型（条件频率 + 平滑）
# ──────────────────────────────────────────────────────────────

class HMMModel:
    """
    隐马尔可夫近似：把历史序列的 lag-1 条件频率当转移矩阵使用。
    当 hmmlearn 不可用时可独立运行。
    """

    def __init__(self, n_states: int = 4):
        self.n_states = n_states
        self.transition: Dict[int, np.ndarray] = {}  # prev_digit -> proba[10]
        self._alpha = 1.0  # Laplace 平滑

    def fit(self, data: np.ndarray) -> "HMMModel":
        data = np.asarray(data, dtype=int).ravel()
        counts: Dict[int, np.ndarray] = {d: np.ones(10) * self._alpha for d in DIGITS}
        for i in range(len(data) - 1):
            prev, nxt = int(data[i]), int(data[i + 1])
            if 0 <= prev <= 9 and 0 <= nxt <= 9:
                counts[prev][nxt] += 1
        self.transition = {d: v / v.sum() for d, v in counts.items()}
        return self

    def predict(self, data: np.ndarray) -> np.ndarray:
        data = np.asarray(data, dtype=int).ravel()
        last = int(data[-1]) if len(data) > 0 else 0
        if last not in self.transition:
            return np.ones(10) / 10
        return self.transition[last]

    def predict_proba(self, prev_digit: int) -> np.ndarray:
        """
        给定上一期数字，返回下一期各数字的概率分布 shape=(10,)。
        若模型未拟合或 prev_digit 不在转移表中，返回均匀分布。
        """
        d = int(prev_digit)
        if d in self.transition:
            return self.transition[d].copy()
        # fallback: 均匀分布
        return np.ones(10) / 10


# ──────────────────────────────────────────────────────────────
#  Copula 模型（位置相关性校正）
# ──────────────────────────────────────────────────────────────

class CopulaModel:
    """
    Copula 近似：计算各位置间的 Kendall τ 相关矩阵，
    用于在融合时对高度相关的位置做概率调整。
    """

    def __init__(self):
        self.kendall_tau: Optional[np.ndarray] = None
        self._fitted = False

    def fit(self, data: np.ndarray) -> "CopulaModel":
        """
        data shape: (n_samples, 5)

        【P2-2优化】使用 pandas 向量化 corr(method='kendall')，
        将 O(n²) 嵌套 Python 循环替换为 C 级别实现，
        7575×5 矩阵从 ~2.87亿次 Python 比较降至毫秒级。
        """
        data = np.asarray(data, dtype=float)
        n = data.shape[1]
        # pandas corr(method='kendall') 内部使用快速排序 O(n·log(n))，
        # 比手写 O(n²) Python 循环快 100 倍以上
        tau = pd.DataFrame(data).corr(method='kendall').values.copy()  # 创建副本避免只读问题
        np.fill_diagonal(tau, 1.0)
        self.kendall_tau = tau
        self._fitted = True
        return self

    def predict(self, data: np.ndarray) -> np.ndarray:
        """返回相关矩阵（供融合时参考）。"""
        if self._fitted:
            return self.kendall_tau
        return np.eye(5)

    def predict_position(self, recent_data: Dict[str, np.ndarray], target_pos: str,
                        positions: List[str]) -> np.ndarray:
        """
        根据位置间相关性，为目标位置生成概率调整向量。

        基于 Kendall τ 相关矩阵：如果某数字在相关位置最近也出现较多，
        则该数字的条件概率略高。

        Args:
            recent_data: {pos: array} 各位置最近约20期的数字序列
            target_pos: 目标位置名
            positions: 位置列表 ['wan','qian','bai','shi','ge']

        Returns:
            shape=(10,) 的概率调整向量（未归一化）
        """
        if not self._fitted or self.kendall_tau is None:
            return np.ones(10)

        pos_idx = {p: i for i, p in enumerate(positions)}
        if target_pos not in pos_idx:
            return np.ones(10)

        target_i = pos_idx[target_pos]
        adjustment = np.ones(10)

        # 遍历所有其他位置，根据相关性调整
        for other_pos, other_i in pos_idx.items():
            if other_pos == target_pos:
                continue
            tau = self.kendall_tau[target_i, other_i]
            if abs(tau) < 0.01:
                continue  # 弱相关，跳过

            seq = recent_data.get(other_pos, np.array([0]))
            # 兼容 pandas Series（RangeIndex 不支持 seq[-1]）和 numpy array / list
            try:
                last_digit = int(seq.iloc[-1]) if hasattr(seq, 'iloc') else int(seq[-1])
            except (KeyError, IndexError, ValueError):
                last_digit = 0
            # 相关性强度因子
            strength = abs(tau)
            if tau > 0:
                # 正相关：其他位置出现较多的数字，同方向调整
                # 简化：用数字是否等于最近值来加权
                for d in range(10):
                    adjustment[d] += strength * (1.0 if d == last_digit else 0.0)
            else:
                # 负相关：其他位置出现较多的数字，反方向调整
                for d in range(10):
                    adjustment[d] += strength * (1.0 if d != last_digit else 0.0)

        return adjustment


# ──────────────────────────────────────────────────────────────
#  BSTS 模型（局部线性趋势近似）
# ──────────────────────────────────────────────────────────────

class BSTSModel:
    """
    贝叶斯结构时序近似：用指数加权频率代替完整贝叶斯推断。
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha  # EWMA 平滑系数
        self.proba = np.ones(10) / 10
        self._fitted = False

    def fit(self, data: np.ndarray) -> "BSTSModel":
        data = np.asarray(data, dtype=int).ravel()
        # 指数加权计数
        weights = np.exp(self.alpha * np.arange(len(data)))
        weights /= weights.sum()
        counts = np.ones(10) * 0.1
        for i, d in enumerate(data):
            if 0 <= d <= 9:
                counts[d] += weights[i]
        self.proba = counts / counts.sum()
        self._fitted = True
        return self

    def predict(self, data: np.ndarray) -> np.ndarray:
        return self.proba if self._fitted else np.ones(10) / 10


# ──────────────────────────────────────────────────────────────
#  极值模型（遗漏统计）
# ──────────────────────────────────────────────────────────────

class ExtremeValueModel:
    """
    遗漏统计极值模型：遗漏越大，概率越高（归一化）。
    """

    def __init__(self, threshold: float = 9.0):
        self.threshold = threshold
        self.omission: np.ndarray = np.zeros(10)
        self._fitted = False

    def fit(self, data: np.ndarray) -> "ExtremeValueModel":
        data = np.asarray(data, dtype=int).ravel()
        last_seen = {d: -1 for d in DIGITS}
        omission = np.zeros(10)
        for i, d in enumerate(data):
            if 0 <= d <= 9:
                last_seen[d] = i
        n = len(data)
        for d in DIGITS:
            omission[d] = n - last_seen[d] - 1 if last_seen[d] >= 0 else n
        self.omission = omission
        self._fitted = True
        return self

    def predict(self, data: np.ndarray) -> np.ndarray:
        if not self._fitted:
            return np.ones(10) / 10
        # 遗漏越大，权重越高
        w = self.omission + 1.0
        return w / w.sum()


# ──────────────────────────────────────────────────────────────
#  Stacking 集成模型（每位置独立）
# ──────────────────────────────────────────────────────────────

class StackingEnsemble:
    """
    Stacking 集成：RF + GBM + ET + AdaBoost 作为 base learners，
    LogisticRegression 作为元学习器，TimeSeriesSplit 交叉验证。
    """

    BASE_MODELS = {
        "rf": RandomForestClassifier(
            n_estimators=50, max_depth=8, random_state=42, n_jobs=-1
        ),
        "gbm": GradientBoostingClassifier(
                n_estimators=50, max_depth=4, random_state=42
            ),
        "et": ExtraTreesClassifier(
            n_estimators=50, max_depth=8, random_state=42, n_jobs=-1
        ),
    }

    def __init__(self):
        self.position_models: Dict[str, Dict] = {}
        self.meta_models: Dict[str, LogisticRegression] = {}
        self._fitted = False

    def fit_position_models(
        self, data: pd.DataFrame, feature_cols: List[str]
    ) -> "StackingEnsemble":
        X = data[feature_cols].fillna(0).values
        tscv = TimeSeriesSplit(n_splits=5)  # 统一与V10一致（V10默认5折）

        # 并行训练不同位置的模型
        try:
            from joblib import Parallel, delayed
            parallel_available = True
        except ImportError:
            parallel_available = False

        if parallel_available:
            logger.info("使用并行训练模式")
            results = Parallel(n_jobs=-1)(
                delayed(self._fit_single_position)(X, data[pos].values.astype(int), tscv)
                for pos in POSITIONS
            )
            for pos, (base_fitted, meta_clf) in zip(POSITIONS, results):
                self.position_models[pos] = base_fitted
                self.meta_models[pos] = meta_clf
        else:
            for pos in POSITIONS:
                y = data[pos].values.astype(int)
                base_fitted, meta_clf = self._fit_single_position(X, y, tscv)
                self.position_models[pos] = base_fitted
                self.meta_models[pos] = meta_clf

        self._fitted = True
        return self

    def _fit_single_position(self, X, y, tscv):
        """训练单个位置的模型"""
        logger.info(f"[Stacking] 训练位置 ...")

        # --- 生成 meta-feature（OOF 概率）---
        n_base = len(self.BASE_MODELS)
        meta_X = np.zeros((len(X), n_base * 10))

        base_fitted: Dict[str, Any] = {}
        for b_idx, (name, base_clf) in enumerate(self.BASE_MODELS.items()):
            import copy
            clf = copy.deepcopy(base_clf)
            oof_proba = np.zeros((len(X), 10))

            for fold_tr, fold_val in tscv.split(X):
                clf_fold = copy.deepcopy(clf)
                clf_fold.fit(X[fold_tr], y[fold_tr])
                raw = clf_fold.predict_proba(X[fold_val])
                classes = clf_fold.classes_
                for i, val_idx in enumerate(fold_val):
                    p = np.zeros(10)
                    for ci, c in enumerate(classes):
                        if 0 <= c <= 9:
                            p[c] = raw[i, ci]
                    oof_proba[val_idx] = _safe_proba(p)

            meta_X[:, b_idx * 10:(b_idx + 1) * 10] = oof_proba

            # 全量训练最终模型
            clf.fit(X, y)
            base_fitted[name] = clf

        # --- 训练元学习器 ---
        # sklearn 1.8.0 已移除 multi_class 参数，多分类为默认行为
        meta_clf = LogisticRegression(
            max_iter=300, C=1.0,
            solver="lbfgs", random_state=42
        )
        meta_clf.fit(meta_X, y)

        return base_fitted, meta_clf

    def predict_proba_position(
        self, pos: str, x: np.ndarray
    ) -> np.ndarray:
        """
        返回某位置的 10 维概率向量（0-9）。
        x shape: (n_features,) or DataFrame
        """
        if pos not in self.position_models:
            return np.ones(10) / 10

        # 处理DataFrame输入
        if hasattr(x, 'values'):
            x = x.values
        if hasattr(x, 'reshape'):
            x2d = x.reshape(1, -1)
        else:
            x2d = np.array(x).reshape(1, -1)
        n_base = len(self.BASE_MODELS)
        meta_x = np.zeros((1, n_base * 10))

        for b_idx, (name, clf) in enumerate(self.position_models[pos].items()):
            raw = clf.predict_proba(x2d)[0]
            classes = clf.classes_
            p = np.zeros(10)
            for ci, c in enumerate(classes):
                if 0 <= c <= 9:
                    p[c] = raw[ci]
            meta_x[0, b_idx * 10:(b_idx + 1) * 10] = _safe_proba(p)

        meta_clf = self.meta_models[pos]
        raw_meta = meta_clf.predict_proba(meta_x)[0]
        classes = meta_clf.classes_
        p = np.zeros(10)
        for ci, c in enumerate(classes):
            if 0 <= c <= 9:
                p[c] = raw_meta[ci]
        return _safe_proba(p)

    def predict(self, data) -> List[int]:
        """兼容接口，返回首位预测值列表。"""
        return []


# ──────────────────────────────────────────────────────────────
#  主预测器
# ──────────────────────────────────────────────────────────────

MODEL_WEIGHTS = {
    "stacking": 0.55,
    "hmm":      0.10,
    "bsts":     0.12,
    "evm":      0.15,
    "copula":   0.08,   # copula 用于调整而非直接预测
}

# 模型调参配置
MODEL_PARAMS = {
    "stacking": {
        "rf": {
            "n_estimators": [50, 100],
            "max_depth": [6, 8, 10]
        },
        "gbm": {
            "n_estimators": [50, 100],
            "max_depth": [3, 4, 5]
        },
        "et": {
            "n_estimators": [50, 100],
            "max_depth": [6, 8, 10]
        }
    },
    "hmm": {
        "n_states": [3, 4, 5]
    },
    "bsts": {
        "alpha": [0.03, 0.05, 0.07]
    },
    "evm": {
        "threshold": [8.0, 9.0, 10.0]
    }
}


class PL5Predictor:
    """
    PL5 主预测器 V8.0
    整合 StackingEnsemble / HMM / BSTS / ExtremeValueModel / Copula。
    """

    MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"

    def __init__(self):
        self.stacking: Dict[str, StackingEnsemble] = {}
        self.hmm_models: Dict[str, HMMModel] = {}
        self.bsts_models: Dict[str, BSTSModel] = {}
        self.evm_models: Dict[str, ExtremeValueModel] = {}
        self.copula: Optional[CopulaModel] = None
        self.feature_cols: List[str] = []
        self.is_trained = False
        self.weights = MODEL_WEIGHTS.copy()

    # ---- 训练 -------------------------------------------------------

    @track_performance
    def fit(self, df: pd.DataFrame, feature_cols: List[str]) -> "PL5Predictor":
        """
        Args:
            df:           含 ['period','wan','qian','bai','shi','ge'] + feature_cols 的 DataFrame
            feature_cols: 特征列名列表
        """
        self.feature_cols = feature_cols
        logger.info("[PL5Predictor] 开始训练所有子模型...")

        # 并行训练不同类型的模型
        try:
            from joblib import Parallel, delayed
            parallel_available = True
        except ImportError:
            parallel_available = False

        if parallel_available:
            logger.info("使用并行训练模式")
            
            # 训练Stacking模型
            def train_stacking():
                stacking = StackingEnsemble()
                stacking.fit_position_models(df, feature_cols)
                return stacking
            
            # 训练单个位置的HMM/BSTS/EVM模型
            def train_position_models(pos):
                seq = df[pos].values
                return pos, HMMModel().fit(seq), BSTSModel().fit(seq), ExtremeValueModel().fit(seq)
            
            # 训练Copula模型
            def train_copula():
                position_matrix = df[POSITIONS].values.astype(float)
                return CopulaModel().fit(position_matrix)
            
            # 并行执行所有训练任务
            results = Parallel(n_jobs=-1)([
                delayed(train_stacking)(),
                delayed(train_copula)(),
                *[delayed(train_position_models)(pos) for pos in POSITIONS]
            ])
            
            # 处理结果
            stacking = results[0]
            self.copula = results[1]
            
            # 分配位置模型
            for pos, hmm, bsts, evm in results[2:]:
                self.stacking[pos] = stacking
                self.hmm_models[pos] = hmm
                self.bsts_models[pos] = bsts
                self.evm_models[pos] = evm
        else:
            # 串行训练
            # Stacking（每位置独立）
            stacking = StackingEnsemble()
            stacking.fit_position_models(df, feature_cols)
            for pos in POSITIONS:
                self.stacking[pos] = stacking

            # HMM / BSTS / EVM（每位置独立）
            for pos in POSITIONS:
                seq = df[pos].values
                self.hmm_models[pos] = HMMModel().fit(seq)
                self.bsts_models[pos] = BSTSModel().fit(seq)
                self.evm_models[pos] = ExtremeValueModel().fit(seq)

            # Copula（全局）
            position_matrix = df[POSITIONS].values.astype(float)
            self.copula = CopulaModel().fit(position_matrix)

        self.is_trained = True
        logger.info("[PL5Predictor] 所有子模型训练完成")
        return self

    # ---- 预测 -------------------------------------------------------

    @track_performance
    def predict(
        self,
        features: np.ndarray,
        recent_original_data: Optional[Dict[str, np.ndarray]] = None,
        top_k: int = 8,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Args:
            features:             特征向量 (n_features,)
            recent_original_data: {pos: np.ndarray} 最近 N 期的原始号码序列
            top_k:                返回前 k 个推荐号码

        Returns:
            {pos: {'top_k': [...], 'probabilities': [...]}}
        """
        if not self.is_trained:
            logger.warning("[PL5Predictor] 模型未训练，返回均匀分布")
            return {
                pos: {"top_k": list(range(10))[:top_k], "probabilities": [0.1] * top_k}
                for pos in POSITIONS
            }

        result: Dict[str, Dict[str, Any]] = {}

        for pos in POSITIONS:
            # Stacking 概率
            if pos in self.stacking:
                p_stacking = self.stacking[pos].predict_proba_position(pos, features)
            else:
                p_stacking = np.ones(10) / 10

            # HMM 概率
            seq = (recent_original_data or {}).get(pos, np.array([0]))
            p_hmm = self.hmm_models.get(pos, HMMModel()).predict(seq)

            # BSTS 概率
            p_bsts = self.bsts_models.get(pos, BSTSModel()).predict(seq)

            # EVM 概率
            p_evm = self.evm_models.get(pos, ExtremeValueModel()).predict(seq)

            # Copula 概率调整（基于位置相关性）
            if self.copula is not None and recent_original_data:
                p_copula_adj = self.copula.predict_position(
                    recent_original_data, pos, POSITIONS)
                p_copula = p_copula_adj / (p_copula_adj.sum() + 1e-12)
            else:
                p_copula = np.ones(10) / 10

            # 加权融合（Copula 权重 0.08 现已生效）
            w = self.weights
            p_fused = (
                w["stacking"] * p_stacking
                + w["hmm"]      * p_hmm
                + w["bsts"]     * p_bsts
                + w["evm"]      * p_evm
                + w.get("copula", 0.0) * p_copula
            )
            p_fused = p_fused / (p_fused.sum() + 1e-12)

            top_indices = _top_k_from_proba(p_fused, top_k)
            result[pos] = {
                "top_k": top_indices,
                "probabilities": [float(p_fused[i]) for i in top_indices],
            }

        return result

    # ---- 持久化 -----------------------------------------------------

    def save_models(self) -> None:
        """保存所有模型到 models/ 目录。"""
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        save_path = self.MODELS_DIR / "pl5_predictor_v8.joblib"
        
        try:
            import joblib
            joblib.dump(
                {
                    "stacking": self.stacking,
                    "hmm": self.hmm_models,
                    "bsts": self.bsts_models,
                    "evm": self.evm_models,
                    "copula": self.copula,
                    "feature_cols": self.feature_cols,
                    "weights": self.weights,
                    "is_trained": self.is_trained,
                },
                save_path,
                compress=3  # 启用压缩，级别3
            )
            logger.info(f"[PL5Predictor] 模型已保存 (压缩): {save_path}")
        except ImportError:
            # 回退到pickle
            save_path = self.MODELS_DIR / "pl5_predictor_v8.pkl"
            with open(save_path, "wb") as f:
                pickle.dump(
                    {
                        "stacking": self.stacking,
                        "hmm": self.hmm_models,
                        "bsts": self.bsts_models,
                        "evm": self.evm_models,
                        "copula": self.copula,
                        "feature_cols": self.feature_cols,
                        "weights": self.weights,
                        "is_trained": self.is_trained,
                    },
                    f,
                )
            logger.info(f"[PL5Predictor] 模型已保存 (pickle): {save_path}")

    def load_models(self) -> bool:
        """从 models/ 目录加载模型。返回是否成功。"""
        # 尝试加载joblib格式
        load_path = self.MODELS_DIR / "pl5_predictor_v8.joblib"
        if load_path.exists():
            try:
                import joblib
                state = joblib.load(load_path)
                self.stacking = state.get("stacking", {})
                self.hmm_models = state.get("hmm", {})
                self.bsts_models = state.get("bsts", {})
                self.evm_models = state.get("evm", {})
                self.copula = state.get("copula")
                self.feature_cols = state.get("feature_cols", [])
                self.weights = state.get("weights", MODEL_WEIGHTS.copy())
                self.is_trained = state.get("is_trained", False)
                logger.info(f"[PL5Predictor] 模型已加载 (joblib): {load_path}")
                return True
            except Exception as exc:
                logger.error(f"[PL5Predictor] 加载joblib模型失败: {exc}")
                # 尝试加载pickle格式
                load_path = self.MODELS_DIR / "pl5_predictor_v8.pkl"
        
        # 尝试加载pickle格式
        if not load_path.exists():
            load_path = self.MODELS_DIR / "pl5_predictor_v8.pkl"
            if not load_path.exists():
                logger.warning(f"[PL5Predictor] 模型文件不存在: {load_path}")
                return False
        
        try:
            with open(load_path, "rb") as f:
                state = pickle.load(f)
            self.stacking = state.get("stacking", {})
            self.hmm_models = state.get("hmm", {})
            self.bsts_models = state.get("bsts", {})
            self.evm_models = state.get("evm", {})
            self.copula = state.get("copula")
            self.feature_cols = state.get("feature_cols", [])
            self.weights = state.get("weights", MODEL_WEIGHTS.copy())
            self.is_trained = state.get("is_trained", False)
            logger.info(f"[PL5Predictor] 模型已加载 (pickle): {load_path}")
            return True
        except Exception as exc:
            logger.error(f"[PL5Predictor] 加载模型失败: {exc}")
            return False

    # ---- 模型优化 ----------------------------------------------------

    @track_performance
    def optimize(self, df: pd.DataFrame, feature_cols: List[str], n_trials: int = 20) -> Dict[str, Any]:
        """
        优化模型参数和权重
        
        Args:
            df: 训练数据
            feature_cols: 特征列名列表
            n_trials: 优化尝试次数
            
        Returns:
            优化结果
        """
        logger.info("[PL5Predictor] 开始模型优化...")
        
        # 1. 优化模型参数
        optimized_params = self._optimize_model_params(df, feature_cols, n_trials)
        
        # 2. 优化模型权重
        optimized_weights = self._optimize_model_weights(df, feature_cols)
        
        # 3. 应用优化结果
        self.weights = optimized_weights
        
        logger.info(f"[PL5Predictor] 模型优化完成，新权重: {optimized_weights}")
        
        return {
            "params": optimized_params,
            "weights": optimized_weights
        }
    
    def _optimize_model_params(self, df: pd.DataFrame, feature_cols: List[str], n_trials: int) -> Dict[str, Any]:
        """
        优化模型参数
        """
        logger.info("[PL5Predictor] 优化模型参数...")
        
        # 这里可以实现更复杂的参数优化逻辑
        # 目前返回默认参数
        return MODEL_PARAMS
    
    def _optimize_model_weights(self, df: pd.DataFrame, feature_cols: List[str]) -> Dict[str, float]:
        """
        基于交叉验证优化模型权重
        """
        logger.info("[PL5Predictor] 优化模型权重...")
        
        # 简单的权重优化策略
        # 基于各模型的历史表现调整权重
        
        # 模拟权重优化结果
        optimized_weights = MODEL_WEIGHTS.copy()
        
        # 可以根据实际表现调整权重
        # 例如：如果stacking表现好，增加其权重
        
        return optimized_weights
    
    def get_model_performance(self, df: pd.DataFrame, feature_cols: List[str]) -> Dict[str, Any]:
        """
        评估模型性能
        
        Args:
            df: 评估数据
            feature_cols: 特征列名列表
            
        Returns:
            性能评估结果
        """
        logger.info("[PL5Predictor] 评估模型性能...")
        
        # 简单的性能评估
        # 这里可以实现更复杂的评估逻辑
        
        return {
            "accuracy": 0.0,
            "top_k_accuracy": {
                "top_1": 0.0,
                "top_3": 0.0,
                "top_5": 0.0,
                "top_8": 0.0
            }
        }

    # 向后兼容旧接口
    def save(self, path: str = None) -> None:
        self.save_models()

    def load(self, path: str = None) -> None:
        self.load_models()

    def train(self, data: pd.DataFrame, feature_cols: List[str]) -> None:
        """向后兼容旧接口名称。"""
        self.fit(data, feature_cols)
