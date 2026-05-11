"""
PL5 预测器 V9.0 — 重构优化版
优化项：
1. 并行模型训练
2. 多级缓存集成
3. 预测结果缓存
4. 代码结构优化
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

from src.core.cache import get_global_cache
from src.core.utils.parallel import parallel_map, ParallelExecutor, get_optimal_n_jobs

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
DIGITS = list(range(10))


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════
# HMM 模型（条件频率 + 平滑）
# ═══════════════════════════════════════════════════════════════


class HMMModel:
    """隐马尔可夫近似：把历史序列的 lag-1 条件频率当转移矩阵使用。"""

    def __init__(self, n_states: int = 4):
        self.n_states = n_states
        self.transition: Dict[int, np.ndarray] = {}
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
        d = int(prev_digit)
        if d in self.transition:
            return self.transition[d].copy()
        return np.ones(10) / 10


# ═══════════════════════════════════════════════════════════════
# Copula 模型（位置相关性校正）
# ═══════════════════════════════════════════════════════════════


class CopulaModel:
    """Copula 近似：计算各位置间的 Kendall τ 相关矩阵。"""

    def __init__(self):
        self.kendall_tau: Optional[np.ndarray] = None
        self._fitted = False

    def fit(self, data: np.ndarray) -> "CopulaModel":
        data = np.asarray(data, dtype=float)
        n = data.shape[1]
        tau = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                xi, xj = data[:, i], data[:, j]
                concordant = 0
                discordant = 0
                N = len(xi)
                for k in range(N - 1):
                    di = xi[k + 1 :] - xi[k]
                    dj = xj[k + 1 :] - xj[k]
                    concordant += int(np.sum(di * dj > 0))
                    discordant += int(np.sum(di * dj < 0))
                n_pairs = N * (N - 1) // 2
                tau[i, j] = tau[j, i] = (concordant - discordant) / (n_pairs + 1e-12)
        self.kendall_tau = tau
        self._fitted = True
        return self

    def predict(self, data: np.ndarray) -> np.ndarray:
        if self._fitted:
            return self.kendall_tau
        return np.eye(5)


# ═══════════════════════════════════════════════════════════════
# BSTS 模型（局部线性趋势近似）
# ═══════════════════════════════════════════════════════════════


class BSTSModel:
    """贝叶斯结构时序近似：用指数加权频率代替完整贝叶斯推断。"""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.proba = np.ones(10) / 10
        self._fitted = False

    def fit(self, data: np.ndarray) -> "BSTSModel":
        data = np.asarray(data, dtype=int).ravel()
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


# ═══════════════════════════════════════════════════════════════
# 极值模型（遗漏统计）
# ═══════════════════════════════════════════════════════════════


class ExtremeValueModel:
    """遗漏统计极值模型：遗漏越大，概率越高（归一化）。"""

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
        w = self.omission + 1.0
        return w / w.sum()


# ═══════════════════════════════════════════════════════════════
# Stacking 集成模型（每位置独立）- 并行优化版
# ═══════════════════════════════════════════════════════════════


class StackingEnsemble:
    """
    Stacking 集成：RF + GBM + ET + AdaBoost 作为 base learners，
    LogisticRegression 作为元学习器，TimeSeriesSplit 交叉验证。
    优化：支持并行训练
    """

    BASE_MODELS = {
        "rf": RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42, n_jobs=-1),
        "gbm": GradientBoostingClassifier(n_estimators=50, max_depth=4, random_state=42),
        "et": ExtraTreesClassifier(n_estimators=50, max_depth=8, random_state=42, n_jobs=-1),
    }

    def __init__(self, n_jobs: int = -1):
        self.position_models: Dict[str, Dict] = {}
        self.meta_models: Dict[str, LogisticRegression] = {}
        self._fitted = False
        self.n_jobs = get_optimal_n_jobs(n_jobs)
        self._parallel_executor = ParallelExecutor(n_jobs=self.n_jobs)

    def fit_position_models(self, data: pd.DataFrame, feature_cols: List[str]) -> "StackingEnsemble":
        X = data[feature_cols].fillna(0).values
        tscv = TimeSeriesSplit(n_splits=3)

        logger.info(f"使用并行训练模式 (n_jobs={self.n_jobs})")

        def fit_single_position(pos):
            y = data[pos].values.astype(int)
            return self._fit_single_position(X, y, tscv, pos)

        results = self._parallel_executor.map(fit_single_position, POSITIONS)

        for pos, (base_fitted, meta_clf) in zip(POSITIONS, results):
            self.position_models[pos] = base_fitted
            self.meta_models[pos] = meta_clf

        self._fitted = True
        return self

    def _fit_single_position(self, X, y, tscv, pos):
        """训练单个位置的模型"""
        logger.info(f"[Stacking] 训练位置 {pos}...")

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

            meta_X[:, b_idx * 10 : (b_idx + 1) * 10] = oof_proba
            clf.fit(X, y)
            base_fitted[name] = clf

        meta_clf = LogisticRegression(max_iter=300, C=1.0, solver="lbfgs", random_state=42)
        meta_clf.fit(meta_X, y)

        return base_fitted, meta_clf

    def predict_proba_position(self, pos: str, x: np.ndarray) -> np.ndarray:
        if pos not in self.position_models:
            return np.ones(10) / 10

        x2d = x.reshape(1, -1)
        n_base = len(self.BASE_MODELS)
        meta_x = np.zeros((1, n_base * 10))

        for b_idx, (name, clf) in enumerate(self.position_models[pos].items()):
            raw = clf.predict_proba(x2d)[0]
            classes = clf.classes_
            p = np.zeros(10)
            for ci, c in enumerate(classes):
                if 0 <= c <= 9:
                    p[c] = raw[ci]
            meta_x[0, b_idx * 10 : (b_idx + 1) * 10] = _safe_proba(p)

        meta_clf = self.meta_models[pos]
        raw_meta = meta_clf.predict_proba(meta_x)[0]
        classes = meta_clf.classes_
        p = np.zeros(10)
        for ci, c in enumerate(classes):
            if 0 <= c <= 9:
                p[c] = raw_meta[ci]
        return _safe_proba(p)


# ═══════════════════════════════════════════════════════════════
# 主预测器 V9.0 - 重构优化版
# ═══════════════════════════════════════════════════════════════

MODEL_WEIGHTS = {
    "stacking": 0.55,
    "hmm": 0.10,
    "bsts": 0.12,
    "evm": 0.15,
    "copula": 0.08,
}


class PL5PredictorV9:
    """
    PL5 主预测器 V9.0 - 重构优化版
    整合 StackingEnsemble / HMM / BSTS / ExtremeValueModel / Copula。
    优化：并行训练、缓存集成
    """

    MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"

    def __init__(self, n_jobs: int = -1):
        self.stacking: Dict[str, StackingEnsemble] = {}
        self.hmm_models: Dict[str, HMMModel] = {}
        self.bsts_models: Dict[str, BSTSModel] = {}
        self.evm_models: Dict[str, ExtremeValueModel] = {}
        self.copula: Optional[CopulaModel] = None
        self.feature_cols: List[str] = []
        self.is_trained = False
        self.weights = MODEL_WEIGHTS.copy()
        self.n_jobs = get_optimal_n_jobs(n_jobs)
        self._parallel_executor = ParallelExecutor(n_jobs=self.n_jobs)
        self._cache = get_global_cache()

    @track_performance
    def fit(self, df: pd.DataFrame, feature_cols: List[str]) -> "PL5PredictorV9":
        """
        Args:
            df: 含 ['period','wan','qian','bai','shi','ge'] + feature_cols 的 DataFrame
            feature_cols: 特征列名列表
        """
        self.feature_cols = feature_cols
        logger.info("[PL5PredictorV9] 开始训练所有子模型...")

        # 并行训练不同类型的模型
        def train_stacking():
            stacking = StackingEnsemble(n_jobs=self.n_jobs)
            stacking.fit_position_models(df, feature_cols)
            return ("stacking", stacking)

        def train_copula():
            position_matrix = df[POSITIONS].values.astype(float)
            return ("copula", CopulaModel().fit(position_matrix))

        def train_position_models(pos):
            seq = df[pos].values
            return (
                pos,
                {"hmm": HMMModel().fit(seq), "bsts": BSTSModel().fit(seq), "evm": ExtremeValueModel().fit(seq)},
            )

        # 并行执行所有训练任务
        results = self._parallel_executor.map(
            lambda fn: fn(),
            [train_stacking, train_copula] + [lambda p=pos: train_position_models(p) for pos in POSITIONS],
        )

        # 处理结果
        for result in results:
            if result[0] == "stacking":
                for pos in POSITIONS:
                    self.stacking[pos] = result[1]
            elif result[0] == "copula":
                self.copula = result[1]
            else:
                pos = result[0]
                models = result[1]
                self.hmm_models[pos] = models["hmm"]
                self.bsts_models[pos] = models["bsts"]
                self.evm_models[pos] = models["evm"]

        self.is_trained = True
        logger.info("[PL5PredictorV9] 所有子模型训练完成")
        return self

    @track_performance
    def predict(
        self,
        features: np.ndarray,
        recent_original_data: Optional[Dict[str, np.ndarray]] = None,
        top_k: int = 8,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Args:
            features: 特征向量 (n_features,)
            recent_original_data: {pos: np.ndarray} 最近 N 期的原始号码序列
            top_k: 返回前 k 个推荐号码

        Returns:
            {pos: {'top_k': [...], 'probabilities': [...]}}
        """
        if not self.is_trained:
            logger.warning("[PL5PredictorV9] 模型未训练，返回均匀分布")
            return {pos: {"top_k": list(range(10))[:top_k], "probabilities": [0.1] * top_k} for pos in POSITIONS}

        # 检查缓存
        cache_key = f"pred_{hash(features.tobytes())}_{top_k}"
        cached, _ = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("预测结果缓存命中")
            return cached

        result: Dict[str, Dict[str, Any]] = {}

        for pos in POSITIONS:
            p_stacking = (
                self.stacking[pos].predict_proba_position(pos, features) if pos in self.stacking else np.ones(10) / 10
            )
            seq = (recent_original_data or {}).get(pos, np.array([0]))
            p_hmm = self.hmm_models.get(pos, HMMModel()).predict(seq)
            p_bsts = self.bsts_models.get(pos, BSTSModel()).predict(seq)
            p_evm = self.evm_models.get(pos, ExtremeValueModel()).predict(seq)

            w = self.weights
            p_fused = w["stacking"] * p_stacking + w["hmm"] * p_hmm + w["bsts"] * p_bsts + w["evm"] * p_evm
            p_fused = p_fused / (p_fused.sum() + 1e-12)

            top_indices = _top_k_from_proba(p_fused, top_k)
            result[pos] = {
                "top_k": top_indices,
                "probabilities": [float(p_fused[i]) for i in top_indices],
            }

        # 存入缓存
        self._cache.put(cache_key, result, ttl=300)  # 5分钟TTL

        return result

    def save_models(self) -> None:
        """保存所有模型到 models/ 目录。"""
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        save_path = self.MODELS_DIR / "pl5_predictor_v9.joblib"

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
                    "version": "v9.0",
                },
                save_path,
                compress=3,
            )
            logger.info(f"[PL5PredictorV9] 模型已保存: {save_path}")
        except ImportError:
            save_path = self.MODELS_DIR / "pl5_predictor_v9.pkl"
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
                        "version": "v9.0",
                    },
                    f,
                )
            logger.info(f"[PL5PredictorV9] 模型已保存 (pickle): {save_path}")

    def load_models(self) -> bool:
        """从 models/ 目录加载模型。返回是否成功。"""
        load_path = self.MODELS_DIR / "pl5_predictor_v9.joblib"
        if load_path.exists():
            try:
                import joblib

                state = joblib.load(load_path)
                self._load_state(state)
                logger.info(f"[PL5PredictorV9] 模型已加载: {load_path}")
                return True
            except Exception as exc:
                logger.error(f"[PL5PredictorV9] 加载joblib模型失败: {exc}")

        load_path = self.MODELS_DIR / "pl5_predictor_v9.pkl"
        if load_path.exists():
            try:
                with open(load_path, "rb") as f:
                    state = pickle.load(f)
                self._load_state(state)
                logger.info(f"[PL5PredictorV9] 模型已加载: {load_path}")
                return True
            except Exception as exc:
                logger.error(f"[PL5PredictorV9] 加载模型失败: {exc}")

        return False

    def _load_state(self, state: Dict):
        """加载状态"""
        self.stacking = state.get("stacking", {})
        self.hmm_models = state.get("hmm", {})
        self.bsts_models = state.get("bsts", {})
        self.evm_models = state.get("evm", {})
        self.copula = state.get("copula")
        self.feature_cols = state.get("feature_cols", [])
        self.weights = state.get("weights", MODEL_WEIGHTS.copy())
        self.is_trained = state.get("is_trained", False)

    # 向后兼容旧接口
    def save(self, path: str = None) -> None:
        self.save_models()

    def load(self, path: str = None) -> None:
        self.load_models()

    def train(self, data: pd.DataFrame, feature_cols: List[str]) -> None:
        """向后兼容旧接口名称。"""
        self.fit(data, feature_cols)


# 向后兼容
PL5Predictor = PL5PredictorV9
