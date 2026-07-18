# -*- coding: utf-8 -*-
"""
跨期位置间动态交互依赖建模模块 (Cross-Period Position-wise Dynamic Interaction Dependency Modeling)

依据时序构建跨期位置间动态交互依赖建模（包括但不限于两期），
以增强号码间状态转移概率曲线值。

核心功能：
1. 多阶跨期状态转移概率矩阵（lag-1, lag-2, lag-3）
2. 跨期位置间交互依赖建模（如 t-1期万位 → t期千位）
3. 动态状态转移概率曲线增强
4. 跨期联合分布建模

作者: PL5 System
版本: V1.0
创建时间: 2026-07-18
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import logging
from pathlib import Path
import pickle
import json

logger = logging.getLogger(__name__)

# 5个位置
POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
# 数字范围 0-9
DIGITS = list(range(10))


class CrossPeriodTransitionMatrix:
    """
    多阶跨期状态转移概率矩阵

    构建同一位置在不同lag下的状态转移概率矩阵：
    - lag-1: P(X_t | X_{t-1})  — 一阶马尔可夫
    - lag-2: P(X_t | X_{t-2})  — 二阶跨期
    - lag-3: P(X_t | X_{t-3})  — 三阶跨期

    并通过指数加权融合多阶转移概率，生成增强的状态转移概率曲线。
    """

    def __init__(self, max_lag: int = 3, smoothing_alpha: float = 0.1,
                 decay_factor: float = 0.6):
        """
        Args:
            max_lag: 最大跨期阶数（默认3，即考虑t-1/t-2/t-3期）
            smoothing_alpha: Laplace平滑系数
            decay_factor: 多阶融合时的指数衰减因子（越远的lag权重越低）
        """
        self.max_lag = max_lag
        self.smoothing_alpha = smoothing_alpha
        self.decay_factor = decay_factor
        self.fitted = False

        # 各lag的转移矩阵: {lag: {pos: 10x10矩阵}}
        self.transition_matrices: Dict[int, Dict[str, np.ndarray]] = {}

        # 融合后的增强转移概率曲线: {pos: 10x10矩阵}
        self.enhanced_curves: Dict[str, np.ndarray] = {}

        # 各位置的历史状态转移熵（用于评估可预测性）
        self.transition_entropies: Dict[str, float] = {}

    def fit(self, data: pd.DataFrame) -> "CrossPeriodTransitionMatrix":
        """
        拟合多阶跨期状态转移概率矩阵

        Args:
            data: 包含 wan/qian/bai/shi/ge 列的 DataFrame
        """
        n_samples = len(data)
        if n_samples < self.max_lag + 10:
            logger.warning(f"数据量不足({n_samples})，跨期转移矩阵需要至少{self.max_lag + 10}条记录")
            return self

        for lag in range(1, self.max_lag + 1):
            self.transition_matrices[lag] = {}
            for pos in POSITIONS:
                self.transition_matrices[lag][pos] = self._compute_lag_transition(
                    data[pos].values, lag
                )

        # 融合多阶转移概率，生成增强曲线
        self._fuse_multi_lag_curves()

        # 计算转移熵
        for pos in POSITIONS:
            trans = self.enhanced_curves[pos]
            entropy = -np.sum(trans * np.log(trans + 1e-12), axis=1).mean()
            self.transition_entropies[pos] = float(entropy)

        self.fitted = True
        logger.info(f"跨期状态转移矩阵拟合完成: max_lag={self.max_lag}, "
                    f"平均转移熵={np.mean(list(self.transition_entropies.values())):.4f}")
        return self

    def _compute_lag_transition(self, values: np.ndarray, lag: int) -> np.ndarray:
        """
        计算指定lag的10x10状态转移概率矩阵

        P(X_t = j | X_{t-lag} = i)
        """
        values = values.astype(np.int64)
        n = len(values)

        if n <= lag:
            return np.ones((10, 10)) / 10

        prev_vals = values[:-lag]
        curr_vals = values[lag:]

        valid_mask = ((prev_vals >= 0) & (prev_vals < 10) &
                      (curr_vals >= 0) & (curr_vals < 10))

        trans_counts = np.zeros((10, 10), dtype=np.float64)
        np.add.at(trans_counts, (prev_vals[valid_mask], curr_vals[valid_mask]), 1.0)

        # Laplace平滑
        trans_probs = (trans_counts + self.smoothing_alpha) / \
                      (trans_counts.sum(axis=1, keepdims=True) + 10 * self.smoothing_alpha)

        return trans_probs

    def _fuse_multi_lag_curves(self):
        """
        融合多阶转移概率，生成增强的状态转移概率曲线

        使用指数衰减加权融合：
        P_enhanced = Σ (decay^(lag-1) * P_lag) / Σ decay^(lag-1)

        这样近期的lag-1权重最高，远期的lag-3权重递减，
        但仍保留远期依赖信息。
        """
        for pos in POSITIONS:
            fused = np.zeros((10, 10))
            total_weight = 0.0

            for lag in range(1, self.max_lag + 1):
                weight = self.decay_factor ** (lag - 1)
                fused += weight * self.transition_matrices[lag][pos]
                total_weight += weight

            fused = fused / (total_weight + 1e-12)

            # 行归一化确保概率分布
            row_sums = fused.sum(axis=1, keepdims=True)
            fused = fused / (row_sums + 1e-12)

            self.enhanced_curves[pos] = fused

    def get_transition_probability(self, pos: str, prev_digit: int) -> np.ndarray:
        """
        获取指定位置、指定上期数字的状态转移概率分布

        Args:
            pos: 位置名 (wan/qian/bai/shi/ge)
            prev_digit: 上期该位置的数字 (0-9)

        Returns:
            10维概率向量 P(X_t=0..9 | X_{t-1}=prev_digit)
        """
        if not self.fitted or pos not in self.enhanced_curves:
            return np.ones(10) / 10

        if prev_digit < 0 or prev_digit > 9:
            return np.ones(10) / 10

        return self.enhanced_curves[pos][prev_digit].copy()

    def get_lag_transition_probability(self, pos: str, lag: int,
                                       prev_digit: int) -> np.ndarray:
        """
        获取指定lag的转移概率（用于多阶分析）

        Args:
            pos: 位置名
            lag: 跨期阶数 (1, 2, ..., max_lag)
            prev_digit: lag期前的数字
        """
        if not self.fitted or lag not in self.transition_matrices:
            return np.ones(10) / 10
        if pos not in self.transition_matrices[lag]:
            return np.ones(10) / 10
        if prev_digit < 0 or prev_digit > 9:
            return np.ones(10) / 10

        return self.transition_matrices[lag][pos][prev_digit].copy()


class CrossPositionInteractionModel:
    """
    跨期位置间交互依赖模型

    建模不同位置之间、跨期的动态交互依赖关系。
    例如：t-1期的万位数字 → t期的千位数字的概率影响。

    构建跨期跨位置的联合转移张量：
    P(X_t^{pos_j} | X_{t-lag}^{pos_i})

    这是一个 5×5×10×10 的四维张量（源位置×目标位置×源数字×目标数字）。
    """

    def __init__(self, max_lag: int = 2, smoothing_alpha: float = 0.1,
                 min_samples: int = 30):
        """
        Args:
            max_lag: 最大跨期阶数
            smoothing_alpha: Laplace平滑系数
            min_samples: 最小样本数（低于此数不建模交互）
        """
        self.max_lag = max_lag
        self.smoothing_alpha = smoothing_alpha
        self.min_samples = min_samples
        self.fitted = False

        # 跨期跨位置转移张量
        # {lag: {(src_pos, dst_pos): 10x10矩阵}}
        self.interaction_tensors: Dict[int, Dict[Tuple[str, str], np.ndarray]] = {}

        # 位置间交互强度（Kendall tau-like度量）
        self.interaction_strengths: Dict[int, Dict[Tuple[str, str], float]] = {}

        # 融合后的交互调整系数
        self.fused_interactions: Dict[Tuple[str, str], np.ndarray] = {}

    def fit(self, data: pd.DataFrame) -> "CrossPositionInteractionModel":
        """
        拟合跨期位置间交互依赖模型
        """
        n_samples = len(data)
        if n_samples < self.min_samples:
            logger.warning(f"数据量不足({n_samples})，跨位置交互建模需要至少{self.min_samples}条记录")
            return self

        for lag in range(1, self.max_lag + 1):
            self.interaction_tensors[lag] = {}
            self.interaction_strengths[lag] = {}

            for src_pos in POSITIONS:
                for dst_pos in POSITIONS:
                    if src_pos == dst_pos:
                        continue  # 同位置由CrossPeriodTransitionMatrix处理

                    trans_matrix, strength = self._compute_cross_position_transition(
                        data[src_pos].values,
                        data[dst_pos].values,
                        lag
                    )

                    self.interaction_tensors[lag][(src_pos, dst_pos)] = trans_matrix
                    self.interaction_strengths[lag][(src_pos, dst_pos)] = strength

        # 融合多lag的交互
        self._fuse_interactions()

        self.fitted = True

        # 日志统计
        total_pairs = sum(len(v) for v in self.interaction_tensors.values())
        strong_pairs = sum(
            1 for lag_dict in self.interaction_strengths.values()
            for strength in lag_dict.values() if strength > 0.05
        )
        logger.info(f"跨期位置间交互模型拟合完成: {total_pairs}个位置对, "
                    f"{strong_pairs}个强交互对(>0.05)")

        return self

    def _compute_cross_position_transition(self,
                                           src_values: np.ndarray,
                                           dst_values: np.ndarray,
                                           lag: int) -> Tuple[np.ndarray, float]:
        """
        计算跨期跨位置转移概率

        P(dst_t = j | src_{t-lag} = i)

        同时计算交互强度（基于Cramér's V统计量）
        """
        n = len(src_values)
        src_vals = src_values[:-lag].astype(np.int64)
        dst_vals = dst_values[lag:].astype(np.int64)

        valid = ((src_vals >= 0) & (src_vals < 10) &
                 (dst_vals >= 0) & (dst_vals < 10))

        if valid.sum() < self.min_samples:
            return np.ones((10, 10)) / 10, 0.0

        # 构建10x10列联表
        contingency = np.zeros((10, 10), dtype=np.float64)
        np.add.at(contingency, (src_vals[valid], dst_vals[valid]), 1.0)

        # Laplace平滑
        trans_probs = (contingency + self.smoothing_alpha) / \
                      (contingency.sum(axis=1, keepdims=True) + 10 * self.smoothing_alpha)

        # 计算Cramér's V作为交互强度
        strength = self._compute_cramers_v(contingency)

        return trans_probs, strength

    def _compute_cramers_v(self, contingency: np.ndarray) -> float:
        """
        计算Cramér's V统计量（0-1标准化关联强度）

        V = sqrt(chi2 / (n * min(k-1, r-1)))
        """
        n = contingency.sum()
        if n < 2:
            return 0.0

        # 期望频数
        row_sums = contingency.sum(axis=1, keepdims=True)
        col_sums = contingency.sum(axis=0, keepdims=True)
        expected = row_sums @ col_sums / (n + 1e-12)

        # 卡方统计量
        chi2 = ((contingency - expected) ** 2 / (expected + 1e-12)).sum()

        k, r = contingency.shape
        min_dim = min(k - 1, r - 1)
        if min_dim == 0:
            return 0.0

        v = np.sqrt(chi2 / (n * min_dim))
        return float(min(v, 1.0))  # 限制在[0,1]

    def _fuse_interactions(self):
        """融合多lag的交互依赖"""
        decay = 0.7  # 衰减因子

        all_pairs = set()
        for lag_dict in self.interaction_tensors.values():
            all_pairs.update(lag_dict.keys())

        for pair in all_pairs:
            fused = np.zeros((10, 10))
            total_weight = 0.0

            for lag in range(1, self.max_lag + 1):
                if pair in self.interaction_tensors.get(lag, {}):
                    weight = decay ** (lag - 1)
                    fused += weight * self.interaction_tensors[lag][pair]
                    total_weight += weight

            if total_weight > 0:
                fused = fused / (total_weight + 1e-12)
                row_sums = fused.sum(axis=1, keepdims=True)
                fused = fused / (row_sums + 1e-12)
                self.fused_interactions[pair] = fused

    def get_cross_position_adjustment(self, target_pos: str,
                                      recent_data: Dict[str, np.ndarray],
                                      max_lag: int = 2) -> np.ndarray:
        """
        获取目标位置的跨位置交互调整概率

        基于 t-1, t-2 等lag期其他位置的数字，
        计算对目标位置t期的联合调整概率。

        Args:
            target_pos: 目标位置
            recent_data: {pos: np.array([...])} 各位置最近几期的数字
            max_lag: 使用的最大lag

        Returns:
            10维调整概率向量
        """
        if not self.fitted:
            return np.ones(10) / 10

        adjustment = np.ones(10)
        total_weight = 0.0

        for src_pos in POSITIONS:
            if src_pos == target_pos:
                continue
            if src_pos not in recent_data:
                continue

            src_values = recent_data[src_pos]

            for lag in range(1, min(self.max_lag, max_lag) + 1):
                if len(src_values) < lag:
                    continue

                prev_digit = int(src_values[-lag])
                if prev_digit < 0 or prev_digit > 9:
                    continue

                pair = (src_pos, target_pos)
                if pair not in self.fused_interactions:
                    continue

                # 获取跨位置转移概率
                trans_prob = self.fused_interactions[pair][prev_digit]

                # 获取交互强度作为权重
                strength = self.interaction_strengths.get(lag, {}).get(pair, 0.0)

                if strength > 0.01:  # 仅考虑有意义的交互
                    weight = strength * (0.7 ** (lag - 1))
                    adjustment = adjustment * (1 + weight * (trans_prob * 10 - 1))
                    total_weight += weight

        # 归一化
        adjustment = np.maximum(adjustment, 1e-8)
        adjustment = adjustment / (adjustment.sum() + 1e-12)

        return adjustment

    def get_strongest_interactions(self, top_k: int = 5) -> List[Tuple[Tuple[str, str], float]]:
        """
        获取交互强度最高的位置对

        Returns:
            [( (src_pos, dst_pos), strength ), ...] 按强度降序
        """
        all_strengths = []
        for lag_dict in self.interaction_strengths.values():
            for pair, strength in lag_dict.items():
                all_strengths.append((pair, strength))

        all_strengths.sort(key=lambda x: x[1], reverse=True)
        return all_strengths[:top_k]


class CrossPeriodDynamicModel:
    """
    跨期位置间动态交互依赖模型（统一接口）

    整合 CrossPeriodTransitionMatrix 和 CrossPositionInteractionModel，
    提供统一的概率增强接口。

    核心能力：
    1. 同位置多阶跨期状态转移概率增强
    2. 跨位置跨期交互依赖调整
    3. 动态融合生成最终增强概率曲线
    """

    def __init__(self, max_lag: int = 3, smoothing_alpha: float = 0.1,
                 same_pos_weight: float = 0.7,
                 cross_pos_weight: float = 0.3):
        """
        Args:
            max_lag: 最大跨期阶数
            smoothing_alpha: Laplace平滑系数
            same_pos_weight: 同位置转移的融合权重
            cross_pos_weight: 跨位置交互的融合权重
        """
        self.max_lag = max_lag
        self.same_pos_weight = same_pos_weight
        self.cross_pos_weight = cross_pos_weight

        self.transition_model = CrossPeriodTransitionMatrix(
            max_lag=max_lag,
            smoothing_alpha=smoothing_alpha,
            decay_factor=0.6
        )

        self.interaction_model = CrossPositionInteractionModel(
            max_lag=max(2, max_lag - 1),  # 跨位置交互最多用2阶
            smoothing_alpha=smoothing_alpha,
            min_samples=30
        )

        self.fitted = False

        # 缓存最近一次的增强概率
        self._enhanced_cache: Dict[str, np.ndarray] = {}

    def fit(self, data: pd.DataFrame) -> "CrossPeriodDynamicModel":
        """
        拟合跨期动态交互依赖模型

        Args:
            data: 包含 wan/qian/bai/shi/ge 列的 DataFrame
        """
        logger.info("=" * 60)
        logger.info("跨期位置间动态交互依赖建模开始")
        logger.info(f"  max_lag={self.max_lag}, 同位置权重={self.same_pos_weight}, "
                    f"跨位置权重={self.cross_pos_weight}")
        logger.info("=" * 60)

        # 拟合同位置多阶转移
        self.transition_model.fit(data)

        # 拟合跨位置交互
        self.interaction_model.fit(data)

        # 输出强交互对
        strong_pairs = self.interaction_model.get_strongest_interactions(top_k=5)
        if strong_pairs:
            logger.info("  最强跨期位置交互对:")
            for (src, dst), strength in strong_pairs:
                logger.info(f"    {src} → {dst}: 强度={strength:.4f}")
        else:
            logger.info("  未检测到显著的跨期位置交互")

        self.fitted = True
        logger.info("跨期位置间动态交互依赖建模完成")
        return self

    def enhance_probability(self, pos: str,
                            recent_data: Dict[str, np.ndarray],
                            base_prob: Optional[np.ndarray] = None,
                            alpha: float = 0.15) -> np.ndarray:
        """
        增强指定位置的预测概率

        融合三部分信息：
        1. 基础预测概率（来自Stacking等模型）
        2. 同位置多阶跨期转移概率
        3. 跨位置跨期交互调整概率

        最终概率 = (1-alpha) * base_prob + alpha * (w1*same_pos + w2*cross_pos)

        Args:
            pos: 目标位置
            recent_data: {pos: np.array([...])} 各位置最近几期的数字
            base_prob: 基础预测概率（10维），若为None则均匀分布
            alpha: 增强强度（0-1，值越大跨期模型影响越大）

        Returns:
            增强后的10维概率向量
        """
        if not self.fitted:
            return base_prob if base_prob is not None else np.ones(10) / 10

        if base_prob is None:
            base_prob = np.ones(10) / 10

        # 1. 同位置多阶跨期转移概率
        same_pos_prob = self._compute_same_position_enhanced(pos, recent_data)

        # 2. 跨位置交互调整概率
        cross_pos_prob = self.interaction_model.get_cross_position_adjustment(
            pos, recent_data, max_lag=2
        )

        # 融合同位置和跨位置
        w1 = self.same_pos_weight
        w2 = self.cross_pos_weight
        enhanced_component = w1 * same_pos_prob + w2 * cross_pos_prob
        enhanced_component = enhanced_component / (enhanced_component.sum() + 1e-12)

        # 与基础概率融合
        final_prob = (1 - alpha) * base_prob + alpha * enhanced_component
        final_prob = final_prob / (final_prob.sum() + 1e-12)

        self._enhanced_cache[pos] = final_prob.copy()
        return final_prob

    def _compute_same_position_enhanced(self, pos: str,
                                        recent_data: Dict[str, np.ndarray]) -> np.ndarray:
        """
        计算同位置的多阶跨期增强概率

        使用最近几期的数字，通过多阶转移矩阵计算加权概率
        """
        if pos not in recent_data:
            return np.ones(10) / 10

        values = recent_data[pos]
        if len(values) == 0:
            return np.ones(10) / 10

        # 多阶加权融合
        probs = np.zeros(10)
        total_weight = 0.0

        for lag in range(1, min(self.max_lag, len(values)) + 1):
            prev_digit = int(values[-lag])
            if prev_digit < 0 or prev_digit > 9:
                continue

            # 获取该lag的转移概率
            lag_prob = self.transition_model.get_lag_transition_probability(
                pos, lag, prev_digit
            )

            # 权重随lag衰减
            weight = 0.6 ** (lag - 1)
            probs += weight * lag_prob
            total_weight += weight

        if total_weight > 0:
            probs = probs / (total_weight + 1e-12)
        else:
            probs = np.ones(10) / 10

        return probs

    def get_enhanced_transition_curves(self) -> Dict[str, np.ndarray]:
        """
        获取所有位置的增强状态转移概率曲线

        Returns:
            {pos: 10x10矩阵} 每个位置的增强转移概率矩阵
        """
        return self.transition_model.enhanced_curves.copy()

    def get_transition_entropies(self) -> Dict[str, float]:
        """
        获取各位置的转移熵（衡量可预测性）

        熵越低 → 转移模式越确定 → 可预测性越高
        """
        return self.transition_model.transition_entropies.copy()

    def get_interaction_summary(self) -> Dict[str, Any]:
        """
        获取交互依赖摘要信息
        """
        strong_pairs = self.interaction_model.get_strongest_interactions(top_k=10)
        entropies = self.get_transition_entropies()

        return {
            'max_lag': self.max_lag,
            'same_pos_weight': self.same_pos_weight,
            'cross_pos_weight': self.cross_pos_weight,
            'transition_entropies': entropies,
            'avg_entropy': float(np.mean(list(entropies.values()))) if entropies else 0.0,
            'strongest_interactions': [
                {'src': src, 'dst': dst, 'strength': float(strength)}
                for (src, dst), strength in strong_pairs
            ],
            'total_interaction_pairs': sum(
                len(v) for v in self.interaction_model.interaction_tensors.values()
            ),
        }

    def save(self, path: Path):
        """保存模型"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        save_data = {
            'max_lag': self.max_lag,
            'same_pos_weight': self.same_pos_weight,
            'cross_pos_weight': self.cross_pos_weight,
            'transition_matrices': self.transition_model.transition_matrices,
            'enhanced_curves': self.transition_model.enhanced_curves,
            'transition_entropies': self.transition_model.transition_entropies,
            'interaction_tensors': self.interaction_model.interaction_tensors,
            'interaction_strengths': self.interaction_model.interaction_strengths,
            'fused_interactions': self.interaction_model.fused_interactions,
        }

        with open(path, 'wb') as f:
            pickle.dump(save_data, f)

        logger.info(f"跨期动态模型已保存: {path}")

    def load(self, path: Path) -> "CrossPeriodDynamicModel":
        """加载模型"""
        path = Path(path)
        if not path.exists():
            logger.warning(f"模型文件不存在: {path}")
            return self

        with open(path, 'rb') as f:
            save_data = pickle.load(f)

        self.max_lag = save_data['max_lag']
        self.same_pos_weight = save_data['same_pos_weight']
        self.cross_pos_weight = save_data['cross_pos_weight']

        self.transition_model.max_lag = self.max_lag
        self.transition_model.transition_matrices = save_data['transition_matrices']
        self.transition_model.enhanced_curves = save_data['enhanced_curves']
        self.transition_model.transition_entropies = save_data['transition_entropies']
        self.transition_model.fitted = True

        self.interaction_model.max_lag = max(2, self.max_lag - 1)
        self.interaction_model.interaction_tensors = save_data['interaction_tensors']
        self.interaction_model.interaction_strengths = save_data['interaction_strengths']
        self.interaction_model.fused_interactions = save_data['fused_interactions']
        self.interaction_model.fitted = True

        self.fitted = True
        logger.info(f"跨期动态模型已加载: {path}")
        return self


# ===================== 特征提取接口 =====================

def extract_cross_period_features(df: pd.DataFrame,
                                  max_lag: int = 3) -> pd.DataFrame:
    """
    提取跨期位置间动态交互依赖特征

    生成以下特征：
    1. 各位置多阶转移概率特征（lag-1/2/3的转移概率行）
    2. 跨位置交互强度特征
    3. 转移熵特征
    4. 跨期联合概率特征

    Args:
        df: 包含 wan/qian/bai/shi/ge 列的 DataFrame
        max_lag: 最大跨期阶数

    Returns:
        添加了跨期特征的 DataFrame
    """
    result = df.copy()
    n = len(df)

    if n < max_lag + 10:
        logger.warning(f"数据量不足({n})，无法提取跨期特征")
        return result

    # 1. 多阶马尔可夫转移概率特征
    for pos in POSITIONS:
        values = df[pos].values.astype(np.int64)

        for lag in range(1, max_lag + 1):
            # 计算该lag的转移矩阵
            prev_vals = values[:-lag]
            curr_vals = values[lag:]
            valid = ((prev_vals >= 0) & (prev_vals < 10) &
                     (curr_vals >= 0) & (curr_vals < 10))

            trans_counts = np.zeros((10, 10), dtype=np.float64)
            np.add.at(trans_counts, (prev_vals[valid], curr_vals[valid]), 1.0)
            trans_probs = (trans_counts + 0.1) / (trans_counts.sum(axis=1, keepdims=True) + 1.0)

            # 为每行生成转移概率特征
            prob_features = np.zeros((n, 10))
            for t in range(n):
                if t >= lag:
                    prev_digit = int(values[t - lag])
                    if 0 <= prev_digit <= 9:
                        prob_features[t] = trans_probs[prev_digit]
                else:
                    prob_features[t] = np.ones(10) / 10

            for d in range(10):
                result[f'{pos}_lag{lag}_trans_prob_{d}'] = prob_features[:, d]

            # 转移熵特征
            trans_entropy = -np.sum(trans_probs * np.log(trans_probs + 1e-12), axis=1).mean()
            result[f'{pos}_lag{lag}_trans_entropy'] = trans_entropy

    # 2. 跨位置交互强度特征（滚动窗口）
    window = min(100, n // 5)
    for i, src_pos in enumerate(POSITIONS):
        for dst_pos in POSITIONS[i + 1:]:
            for lag in range(1, min(3, max_lag + 1)):
                # 滚动计算跨位置Cramér's V
                strengths = np.zeros(n)
                for t in range(window + lag, n):
                    src_window = df[src_pos].values[t - window - lag:t - lag]
                    dst_window = df[dst_pos].values[t - window:t]
                    if len(src_window) > 10:
                        contingency = np.zeros((10, 10))
                        src_int = src_window.astype(int)
                        dst_int = dst_window.astype(int)
                        valid = (src_int >= 0) & (src_int < 10) & (dst_int >= 0) & (dst_int < 10)
                        if valid.sum() > 0:
                            np.add.at(contingency, (src_int[valid], dst_int[valid]), 1.0)
                            strengths[t] = _compute_cramers_v_from_contingency(contingency)

                result[f'interaction_{src_pos}_{dst_pos}_lag{lag}'] = strengths

    # 3. 多阶融合转移概率特征
    for pos in POSITIONS:
        values = df[pos].values.astype(np.int64)
        fused_prob = np.zeros((n, 10))

        for t in range(n):
            weighted_prob = np.zeros(10)
            total_weight = 0.0
            for lag in range(1, min(max_lag + 1, t + 1)):
                prev_digit = int(values[t - lag])
                if 0 <= prev_digit <= 9:
                    # 重新计算（简化版，实际应使用预计算的矩阵）
                    prev_vals = values[:t - lag + 1]
                    curr_vals = values[lag:t + 1]
                    min_len = min(len(prev_vals), len(curr_vals))
                    if min_len > 5:
                        trans_counts = np.zeros((10, 10))
                        pv = prev_vals[-min_len:].astype(int)
                        cv = curr_vals[-min_len:].astype(int)
                        valid = (pv >= 0) & (pv < 10) & (cv >= 0) & (cv < 10)
                        np.add.at(trans_counts, (pv[valid], cv[valid]), 1.0)
                        tp = (trans_counts + 0.1) / (trans_counts.sum(axis=1, keepdims=True) + 1.0)
                        weight = 0.6 ** (lag - 1)
                        weighted_prob += weight * tp[prev_digit]
                        total_weight += weight

            if total_weight > 0:
                fused_prob[t] = weighted_prob / (total_weight + 1e-12)
            else:
                fused_prob[t] = np.ones(10) / 10

        # 输出Top-3融合概率作为特征
        for d in range(3):
            result[f'{pos}_fused_trans_top{d + 1}'] = np.sort(fused_prob, axis=1)[:, -(d + 1)]

    return result


def _compute_cramers_v_from_contingency(contingency: np.ndarray) -> float:
    """从列联表计算Cramér's V"""
    n = contingency.sum()
    if n < 2:
        return 0.0

    row_sums = contingency.sum(axis=1, keepdims=True)
    col_sums = contingency.sum(axis=0, keepdims=True)
    expected = row_sums @ col_sums / (n + 1e-12)

    chi2 = ((contingency - expected) ** 2 / (expected + 1e-12)).sum()
    k, r = contingency.shape
    min_dim = min(k - 1, r - 1)
    if min_dim == 0:
        return 0.0

    v = np.sqrt(chi2 / (n * min_dim))
    return float(min(v, 1.0))
