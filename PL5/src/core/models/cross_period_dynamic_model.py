# -*- coding: utf-8 -*-
"""
跨期位置间动态交互依赖建模模块 (Cross-Period Position-wise Dynamic Interaction Dependency Modeling)

依据时序构建跨期位置间动态交互依赖建模（包括但不限于两期），
以增强号码间状态转移概率曲线值。

核心功能：
1. 多阶跨期号码转移概率矩阵（lag-1, lag-2, lag-3, 10x10）
2. 跨期位置间交互依赖建模（如 t-1期万位 → t期千位, 5x5x10x10张量）
3. 奇偶/大小/冷热状态跨期转移检测（2x2转移矩阵，基于多期状态序列）
4. 动态状态转移概率曲线增强（号码级+状态级融合）
5. 跨期联合分布建模

状态检测说明：
- 奇偶状态: 0=偶, 1=奇, 检测奇偶跨期转移趋势
- 大小状态: 0=小(0-4), 1=大(5-9), 检测大小跨期转移趋势
- 冷热状态: 0=冷, 1=热, 基于滚动频率检测冷热跨期转移趋势
- 所有状态均基于多期序列推理，避免单个实例影响整体判断

作者: PL5 System
版本: V2.0
创建时间: 2026-07-18
更新时间: 2026-07-18 (V2.0: 新增状态转移分析器)
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


# ===================== 状态映射辅助函数 =====================

def _digit_to_parity(d: int) -> int:
    """数字→奇偶状态: 0=偶, 1=奇"""
    return int(d) % 2

def _digit_to_size(d: int) -> int:
    """数字→大小状态: 0=小(0-4), 1=大(5-9)"""
    return 1 if int(d) >= 5 else 0

def _digits_to_hot_cold(values: np.ndarray, window: int = 30) -> np.ndarray:
    """将数字序列→冷热状态序列: 0=冷, 1=热

    基于滚动窗口内各数字的出现频率，频率高于均值的为热，低于均值的为冷。
    使用多期序列而非单个实例，避免单点推理影响。
    """
    values = values.astype(np.int64)
    n = len(values)
    states = np.zeros(n, dtype=np.int64)

    for t in range(n):
        start = max(0, t - window)
        segment = values[start:t + 1]
        if len(segment) < 5:
            states[t] = 1  # 数据不足时默认热
            continue
        counts = np.zeros(10)
        for v in segment:
            if 0 <= v <= 9:
                counts[v] += 1
        freq = counts / (len(segment) + 1e-12)
        avg_freq = 1.0 / 10
        d = int(values[t])
        if 0 <= d <= 9:
            states[t] = 1 if freq[d] >= avg_freq else 0
        else:
            states[t] = 1
    return states


class StateTransitionAnalyzer:
    """
    状态转移分析器

    检测奇偶、大小、冷热三种状态的跨期转移概率，
    基于状态序列（多期）进行推理，避免单个实例影响整体判断。

    核心理念：
    - 不仅看最近一期的状态，而是看最近多期的状态序列趋势
    - 构建多阶(lag-1/2/3)状态转移矩阵
    - 将状态约束映射回号码级概率调整

    三种状态：
    1. 奇偶: 0=偶, 1=奇
    2. 大小: 0=小(0-4), 1=大(5-9)
    3. 冷热: 0=冷, 1=热 (基于滚动频率)
    """

    # 状态定义
    STATE_TYPES = ['parity', 'size', 'hot_cold']
    STATE_CARDINALITY = 2  # 每种状态都是二元的

    # 数字→状态映射表
    DIGIT_PARITY = np.array([d % 2 for d in range(10)])       # 0=偶,1=奇
    DIGIT_SIZE = np.array([1 if d >= 5 else 0 for d in range(10)])  # 0=小,1=大

    def __init__(self, max_lag: int = 3, smoothing_alpha: float = 0.5,
                 hot_cold_window: int = 30):
        """
        Args:
            max_lag: 最大跨期阶数
            smoothing_alpha: Laplace平滑系数（状态转移用较大平滑避免过拟合）
            hot_cold_window: 冷热状态计算的滚动窗口
        """
        self.max_lag = max_lag
        self.smoothing_alpha = smoothing_alpha
        self.hot_cold_window = hot_cold_window
        self.fitted = False

        # 各状态各lag的2x2转移矩阵: {state_type: {lag: {pos: 2x2矩阵}}}
        self.state_matrices: Dict[str, Dict[int, Dict[str, np.ndarray]]] = {}

        # 融合后的增强状态转移矩阵: {state_type: {pos: 2x2矩阵}}
        self.fused_state_matrices: Dict[str, Dict[str, np.ndarray]] = {}

        # 各位置的状态转移熵
        self.state_entropies: Dict[str, Dict[str, float]] = {}

        # 当前各位置的状态序列（最近几期的状态）
        self._current_states: Dict[str, Dict[str, List[int]]] = {}

    def fit(self, data: pd.DataFrame) -> "StateTransitionAnalyzer":
        """
        拟合状态转移分析器

        Args:
            data: 包含 wan/qian/bai/shi/ge 列的 DataFrame
        """
        n_samples = len(data)
        if n_samples < self.max_lag + 10:
            logger.warning(f"数据量不足({n_samples})，状态转移分析需要至少{self.max_lag + 10}条记录")
            return self

        for state_type in self.STATE_TYPES:
            self.state_matrices[state_type] = {}
            self.fused_state_matrices[state_type] = {}
            self.state_entropies[state_type] = {}

            for pos in POSITIONS:
                values = data[pos].values

                # 将数字序列映射为状态序列
                if state_type == 'parity':
                    state_seq = np.array([_digit_to_parity(v) for v in values])
                elif state_type == 'size':
                    state_seq = np.array([_digit_to_size(v) for v in values])
                else:  # hot_cold
                    state_seq = _digits_to_hot_cold(values, self.hot_cold_window)

                # 计算各lag的2x2转移矩阵
                self.state_matrices[state_type][pos] = {}
                for lag in range(1, self.max_lag + 1):
                    self.state_matrices[state_type][pos][lag] = self._compute_state_transition(
                        state_seq, lag
                    )

                # 融合多阶状态转移
                self.fused_state_matrices[state_type][pos] = self._fuse_state_lags(
                    self.state_matrices[state_type][pos]
                )

                # 计算状态转移熵
                fused = self.fused_state_matrices[state_type][pos]
                entropy = -np.sum(fused * np.log(fused + 1e-12), axis=1).mean()
                self.state_entropies[state_type][pos] = float(entropy)

                # 缓存当前状态序列（最近max_lag期）
                self._current_states.setdefault(pos, {})
                self._current_states[pos][state_type] = state_seq[-self.max_lag:].tolist()

        self.fitted = True
        logger.info(f"状态转移分析器拟合完成: "
                    f"奇偶平均熵={np.mean(list(self.state_entropies['parity'].values())):.4f}, "
                    f"大小平均熵={np.mean(list(self.state_entropies['size'].values())):.4f}, "
                    f"冷热平均熵={np.mean(list(self.state_entropies['hot_cold'].values())):.4f}")
        return self

    def _compute_state_transition(self, state_seq: np.ndarray, lag: int) -> np.ndarray:
        """
        计算二元状态的2x2转移矩阵

        P(S_t = j | S_{t-lag} = i), i,j ∈ {0,1}
        """
        n = len(state_seq)
        if n <= lag:
            return np.ones((2, 2)) / 2

        prev_states = state_seq[:-lag]
        curr_states = state_seq[lag:]

        valid = (prev_states >= 0) & (prev_states < 2) & (curr_states >= 0) & (curr_states < 2)

        counts = np.zeros((2, 2), dtype=np.float64)
        np.add.at(counts, (prev_states[valid], curr_states[valid]), 1.0)

        # Laplace平滑
        probs = (counts + self.smoothing_alpha) / \
                (counts.sum(axis=1, keepdims=True) + 2 * self.smoothing_alpha)
        return probs

    def _fuse_state_lags(self, lag_matrices: Dict[int, np.ndarray]) -> np.ndarray:
        """融合多阶状态转移矩阵"""
        decay = 0.6
        fused = np.zeros((2, 2))
        total_weight = 0.0

        for lag in range(1, self.max_lag + 1):
            if lag in lag_matrices:
                weight = decay ** (lag - 1)
                fused += weight * lag_matrices[lag]
                total_weight += weight

        fused = fused / (total_weight + 1e-12)
        row_sums = fused.sum(axis=1, keepdims=True)
        fused = fused / (row_sums + 1e-12)
        return fused

    def get_state_transition_prob(self, pos: str, state_type: str,
                                  recent_data: Dict[str, np.ndarray]) -> np.ndarray:
        """
        获取状态转移概率（基于多期状态序列，非单实例）

        根据最近几期的状态序列，通过多阶融合转移矩阵计算
        下一期各状态的概率分布。

        Args:
            pos: 位置
            state_type: 'parity' / 'size' / 'hot_cold'
            recent_data: {pos: np.array([...])} 各位置最近几期数字

        Returns:
            2维概率向量 [P(state=0), P(state=1)]
        """
        if not self.fitted:
            return np.ones(2) / 2

        if pos not in recent_data or pos not in self.fused_state_matrices.get(state_type, {}):
            return np.ones(2) / 2

        values = recent_data[pos]
        if len(values) == 0:
            return np.ones(2) / 2

        # 将最近几期数字映射为状态序列
        if state_type == 'parity':
            state_seq = np.array([_digit_to_parity(v) for v in values])
        elif state_type == 'size':
            state_seq = np.array([_digit_to_size(v) for v in values])
        else:  # hot_cold
            state_seq = _digits_to_hot_cold(values, self.hot_cold_window)

        # 多阶加权融合
        probs = np.zeros(2)
        total_weight = 0.0

        for lag in range(1, min(self.max_lag, len(state_seq)) + 1):
            prev_state = int(state_seq[-lag])
            if prev_state < 0 or prev_state > 1:
                continue

            # 获取该lag的转移概率
            if lag in self.state_matrices.get(state_type, {}).get(pos, {}):
                lag_prob = self.state_matrices[state_type][pos][lag][prev_state]
            else:
                lag_prob = np.ones(2) / 2

            weight = 0.6 ** (lag - 1)
            probs += weight * lag_prob
            total_weight += weight

        if total_weight > 0:
            probs = probs / (total_weight + 1e-12)
        else:
            probs = np.ones(2) / 2

        return probs

    def get_digit_adjustment(self, pos: str, state_type: str,
                             recent_data: Dict[str, np.ndarray]) -> np.ndarray:
        """
        将状态转移概率映射为号码级调整因子

        根据状态转移概率，对0-9各数字施加调整：
        - 奇偶: P(奇)高的→奇数号码增益，P(偶)高的→偶数号码增益
        - 大小: P(大)高的→大数号码增益，P(小)高的→小数号码增益
        - 冷热: P(热)高的→热号增益，P(冷)高的→冷号增益

        Args:
            pos: 位置
            state_type: 状态类型
            recent_data: 最近几期数据

        Returns:
            10维调整因子向量（乘法因子，1.0=无调整）
        """
        state_probs = self.get_state_transition_prob(pos, state_type, recent_data)

        if state_type == 'parity':
            # state=0(偶)→偶数增益, state=1(奇)→奇数增益
            adjustment = np.ones(10)
            for d in range(10):
                s = self.DIGIT_PARITY[d]
                adjustment[d] = state_probs[s] / (state_probs.mean() + 1e-12)

        elif state_type == 'size':
            # state=0(小)→小数增益, state=1(大)→大数增益
            adjustment = np.ones(10)
            for d in range(10):
                s = self.DIGIT_SIZE[d]
                adjustment[d] = state_probs[s] / (state_probs.mean() + 1e-12)

        else:  # hot_cold
            # 基于近期频率计算冷热状态
            if pos in recent_data and len(recent_data[pos]) >= 5:
                values = recent_data[pos]
                window = min(self.hot_cold_window, len(values))
                segment = values[-window:]
                counts = np.zeros(10)
                for v in segment:
                    v_int = int(v)
                    if 0 <= v_int <= 9:
                        counts[v_int] += 1
                freq = counts / (len(segment) + 1e-12)
                avg_freq = 1.0 / 10

                adjustment = np.ones(10)
                for d in range(10):
                    if freq[d] >= avg_freq:
                        # 热号
                        adjustment[d] = state_probs[1] / (state_probs.mean() + 1e-12)
                    else:
                        # 冷号
                        adjustment[d] = state_probs[0] / (state_probs.mean() + 1e-12)
            else:
                adjustment = np.ones(10)

        return adjustment

    def get_combined_adjustment(self, pos: str,
                                recent_data: Dict[str, np.ndarray]) -> np.ndarray:
        """
        获取三种状态的综合号码级调整因子

        将奇偶、大小、冷热三种状态的调整因子相乘，
        生成综合调整因子。

        Args:
            pos: 位置
            recent_data: 最近几期数据

        Returns:
            10维综合调整因子向量
        """
        if not self.fitted:
            return np.ones(10)

        combined = np.ones(10)
        for state_type in self.STATE_TYPES:
            adj = self.get_digit_adjustment(pos, state_type, recent_data)
            combined = combined * adj

        # 归一化为概率分布
        combined = np.maximum(combined, 1e-8)
        combined = combined / (combined.sum() + 1e-12)
        return combined

    def get_state_summary(self) -> Dict[str, Any]:
        """获取状态转移摘要"""
        summary = {}
        for state_type in self.STATE_TYPES:
            if state_type in self.state_entropies:
                entropies = self.state_entropies[state_type]
                summary[state_type] = {
                    'avg_entropy': float(np.mean(list(entropies.values()))) if entropies else 0.0,
                    'position_entropies': entropies,
                    'predictability': float(1.0 - np.mean(list(entropies.values())) / np.log(2)) if entropies else 0.0,
                }
        return summary


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

    整合 CrossPeriodTransitionMatrix、CrossPositionInteractionModel
    和 StateTransitionAnalyzer，提供统一的概率增强接口。

    核心能力：
    1. 同位置多阶跨期状态转移概率增强（号码级 10x10）
    2. 跨位置跨期交互依赖调整（5x5 位置对）
    3. 奇偶/大小/冷热状态跨期转移约束（避免单实例推理）
    4. 动态融合生成最终增强概率曲线
    """

    def __init__(self, max_lag: int = 3, smoothing_alpha: float = 0.1,
                 same_pos_weight: float = 0.5,
                 cross_pos_weight: float = 0.25,
                 state_weight: float = 0.25):
        """
        Args:
            max_lag: 最大跨期阶数
            smoothing_alpha: Laplace平滑系数
            same_pos_weight: 同位置号码转移的融合权重
            cross_pos_weight: 跨位置交互的融合权重
            state_weight: 状态转移约束（奇偶/大小/冷热）的融合权重
        """
        self.max_lag = max_lag
        self.same_pos_weight = same_pos_weight
        self.cross_pos_weight = cross_pos_weight
        self.state_weight = state_weight

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

        self.state_analyzer = StateTransitionAnalyzer(
            max_lag=max_lag,
            smoothing_alpha=0.5,
            hot_cold_window=30
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
        logger.info(f"  max_lag={self.max_lag}, 号码转移权重={self.same_pos_weight}, "
                    f"跨位置权重={self.cross_pos_weight}, 状态约束权重={self.state_weight}")
        logger.info("=" * 60)

        # 拟合同位置多阶转移
        self.transition_model.fit(data)

        # 拟合跨位置交互
        self.interaction_model.fit(data)

        # 拟合状态转移分析器（奇偶/大小/冷热）
        self.state_analyzer.fit(data)

        # 输出强交互对
        strong_pairs = self.interaction_model.get_strongest_interactions(top_k=5)
        if strong_pairs:
            logger.info("  最强跨期位置交互对:")
            for (src, dst), strength in strong_pairs:
                logger.info(f"    {src} → {dst}: 强度={strength:.4f}")
        else:
            logger.info("  未检测到显著的跨期位置交互")

        # 输出状态转移摘要
        state_summary = self.state_analyzer.get_state_summary()
        for st, info in state_summary.items():
            logger.info(f"  {st}状态: 平均熵={info['avg_entropy']:.4f}, "
                        f"可预测性={info['predictability']:.4f}")

        self.fitted = True
        logger.info("跨期位置间动态交互依赖建模完成")
        return self

    def enhance_probability(self, pos: str,
                            recent_data: Dict[str, np.ndarray],
                            base_prob: Optional[np.ndarray] = None,
                            alpha: float = 0.15) -> np.ndarray:
        """
        增强指定位置的预测概率

        融合四部分信息：
        1. 基础预测概率（来自Stacking等模型）
        2. 同位置多阶跨期号码转移概率
        3. 跨位置跨期交互调整概率
        4. 奇偶/大小/冷热状态转移约束（基于多期状态序列，避免单实例推理）

        最终概率 = (1-alpha) * base_prob + alpha * (
            w1*same_pos + w2*cross_pos + w3*state_constraint
        )

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

        # 1. 同位置多阶跨期号码转移概率
        same_pos_prob = self._compute_same_position_enhanced(pos, recent_data)

        # 2. 跨位置交互调整概率
        cross_pos_prob = self.interaction_model.get_cross_position_adjustment(
            pos, recent_data, max_lag=2
        )

        # 3. 状态转移约束（奇偶/大小/冷热，基于多期状态序列）
        state_prob = self.state_analyzer.get_combined_adjustment(pos, recent_data)

        # 融合号码转移、跨位置交互、状态约束
        w1 = self.same_pos_weight
        w2 = self.cross_pos_weight
        w3 = self.state_weight
        enhanced_component = w1 * same_pos_prob + w2 * cross_pos_prob + w3 * state_prob
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
        state_summary = self.state_analyzer.get_state_summary()

        return {
            'max_lag': self.max_lag,
            'same_pos_weight': self.same_pos_weight,
            'cross_pos_weight': self.cross_pos_weight,
            'state_weight': self.state_weight,
            'transition_entropies': entropies,
            'avg_entropy': float(np.mean(list(entropies.values()))) if entropies else 0.0,
            'strongest_interactions': [
                {'src': src, 'dst': dst, 'strength': float(strength)}
                for (src, dst), strength in strong_pairs
            ],
            'total_interaction_pairs': sum(
                len(v) for v in self.interaction_model.interaction_tensors.values()
            ),
            'state_transition_summary': state_summary,
        }

    def save(self, path: Path):
        """保存模型"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        save_data = {
            'max_lag': self.max_lag,
            'same_pos_weight': self.same_pos_weight,
            'cross_pos_weight': self.cross_pos_weight,
            'state_weight': self.state_weight,
            'transition_matrices': self.transition_model.transition_matrices,
            'enhanced_curves': self.transition_model.enhanced_curves,
            'transition_entropies': self.transition_model.transition_entropies,
            'interaction_tensors': self.interaction_model.interaction_tensors,
            'interaction_strengths': self.interaction_model.interaction_strengths,
            'fused_interactions': self.interaction_model.fused_interactions,
            'state_matrices': self.state_analyzer.state_matrices,
            'fused_state_matrices': self.state_analyzer.fused_state_matrices,
            'state_entropies': self.state_analyzer.state_entropies,
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
        self.same_pos_weight = save_data.get('same_pos_weight', 0.5)
        self.cross_pos_weight = save_data.get('cross_pos_weight', 0.25)
        self.state_weight = save_data.get('state_weight', 0.25)

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

        # 加载状态分析器（兼容旧版无状态分析器的模型文件）
        if 'state_matrices' in save_data:
            self.state_analyzer.max_lag = self.max_lag
            self.state_analyzer.state_matrices = save_data['state_matrices']
            self.state_analyzer.fused_state_matrices = save_data['fused_state_matrices']
            self.state_analyzer.state_entropies = save_data['state_entropies']
            self.state_analyzer.fitted = True

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

    # 4. 状态转移特征（奇偶/大小/冷热，基于多期状态序列避免单实例推理）
    result = _extract_state_transition_features(result, max_lag)

    return result


def _extract_state_transition_features(df: pd.DataFrame, max_lag: int = 3) -> pd.DataFrame:
    """
    提取状态转移特征（奇偶/大小/冷热）

    基于多期状态序列计算状态转移概率，避免单个实例推理影响整体。
    """
    result = df.copy()
    n = len(df)

    if n < max_lag + 10:
        return result

    for pos in POSITIONS:
        values = df[pos].values.astype(np.int64)

        # === 奇偶状态转移特征 ===
        parity_seq = np.array([_digit_to_parity(v) for v in values])

        for lag in range(1, max_lag + 1):
            # 计算lag阶奇偶转移矩阵
            prev_states = parity_seq[:-lag]
            curr_states = parity_seq[lag:]
            valid = (prev_states >= 0) & (prev_states < 2) & (curr_states >= 0) & (curr_states < 2)

            counts = np.zeros((2, 2))
            np.add.at(counts, (prev_states[valid], curr_states[valid]), 1.0)
            probs = (counts + 0.5) / (counts.sum(axis=1, keepdims=True) + 1.0)

            # 为每行生成奇偶转移概率特征
            parity_prob = np.zeros((n, 2))
            for t in range(n):
                if t >= lag:
                    prev_s = int(parity_seq[t - lag])
                    if 0 <= prev_s <= 1:
                        parity_prob[t] = probs[prev_s]
                else:
                    parity_prob[t] = np.ones(2) / 2

            result[f'{pos}_parity_lag{lag}_p_odd'] = parity_prob[:, 1]
            result[f'{pos}_parity_lag{lag}_p_even'] = parity_prob[:, 0]

            # 奇偶转移熵
            parity_entropy = -np.sum(probs * np.log(probs + 1e-12), axis=1).mean()
            result[f'{pos}_parity_lag{lag}_entropy'] = parity_entropy

        # === 大小状态转移特征 ===
        size_seq = np.array([_digit_to_size(v) for v in values])

        for lag in range(1, max_lag + 1):
            prev_states = size_seq[:-lag]
            curr_states = size_seq[lag:]
            valid = (prev_states >= 0) & (prev_states < 2) & (curr_states >= 0) & (curr_states < 2)

            counts = np.zeros((2, 2))
            np.add.at(counts, (prev_states[valid], curr_states[valid]), 1.0)
            probs = (counts + 0.5) / (counts.sum(axis=1, keepdims=True) + 1.0)

            size_prob = np.zeros((n, 2))
            for t in range(n):
                if t >= lag:
                    prev_s = int(size_seq[t - lag])
                    if 0 <= prev_s <= 1:
                        size_prob[t] = probs[prev_s]
                else:
                    size_prob[t] = np.ones(2) / 2

            result[f'{pos}_size_lag{lag}_p_big'] = size_prob[:, 1]
            result[f'{pos}_size_lag{lag}_p_small'] = size_prob[:, 0]

            size_entropy = -np.sum(probs * np.log(probs + 1e-12), axis=1).mean()
            result[f'{pos}_size_lag{lag}_entropy'] = size_entropy

        # === 冷热状态转移特征 ===
        hot_cold_seq = _digits_to_hot_cold(values, window=30)

        for lag in range(1, max_lag + 1):
            prev_states = hot_cold_seq[:-lag]
            curr_states = hot_cold_seq[lag:]
            valid = (prev_states >= 0) & (prev_states < 2) & (curr_states >= 0) & (curr_states < 2)

            counts = np.zeros((2, 2))
            np.add.at(counts, (prev_states[valid], curr_states[valid]), 1.0)
            probs = (counts + 0.5) / (counts.sum(axis=1, keepdims=True) + 1.0)

            hc_prob = np.zeros((n, 2))
            for t in range(n):
                if t >= lag:
                    prev_s = int(hot_cold_seq[t - lag])
                    if 0 <= prev_s <= 1:
                        hc_prob[t] = probs[prev_s]
                else:
                    hc_prob[t] = np.ones(2) / 2

            result[f'{pos}_hotcold_lag{lag}_p_hot'] = hc_prob[:, 1]
            result[f'{pos}_hotcold_lag{lag}_p_cold'] = hc_prob[:, 0]

            hc_entropy = -np.sum(probs * np.log(probs + 1e-12), axis=1).mean()
            result[f'{pos}_hotcold_lag{lag}_entropy'] = hc_entropy

        # === 多阶融合状态概率特征 ===
        # 奇偶融合
        parity_fused = np.zeros(n)
        for t in range(n):
            weighted_p = 0.0
            total_w = 0.0
            for lag in range(1, min(max_lag + 1, t + 1)):
                prev_s = int(parity_seq[t - lag])
                if 0 <= prev_s <= 1:
                    # 简化：使用预计算的转移概率
                    prev_st = parity_seq[:t - lag + 1]
                    curr_st = parity_seq[lag:t + 1]
                    min_len = min(len(prev_st), len(curr_st))
                    if min_len > 3:
                        c = np.zeros((2, 2))
                        ps = prev_st[-min_len:]
                        cs = curr_st[-min_len:]
                        v = (ps >= 0) & (ps < 2) & (cs >= 0) & (cs < 2)
                        np.add.at(c, (ps[v], cs[v]), 1.0)
                        p = (c + 0.5) / (c.sum(axis=1, keepdims=True) + 1.0)
                        w = 0.6 ** (lag - 1)
                        weighted_p += w * p[prev_s][1]  # P(奇)
                        total_w += w
            parity_fused[t] = weighted_p / (total_w + 1e-12) if total_w > 0 else 0.5
        result[f'{pos}_parity_fused_p_odd'] = parity_fused

        # 大小融合
        size_fused = np.zeros(n)
        for t in range(n):
            weighted_p = 0.0
            total_w = 0.0
            for lag in range(1, min(max_lag + 1, t + 1)):
                prev_s = int(size_seq[t - lag])
                if 0 <= prev_s <= 1:
                    prev_st = size_seq[:t - lag + 1]
                    curr_st = size_seq[lag:t + 1]
                    min_len = min(len(prev_st), len(curr_st))
                    if min_len > 3:
                        c = np.zeros((2, 2))
                        ps = prev_st[-min_len:]
                        cs = curr_st[-min_len:]
                        v = (ps >= 0) & (ps < 2) & (cs >= 0) & (cs < 2)
                        np.add.at(c, (ps[v], cs[v]), 1.0)
                        p = (c + 0.5) / (c.sum(axis=1, keepdims=True) + 1.0)
                        w = 0.6 ** (lag - 1)
                        weighted_p += w * p[prev_s][1]  # P(大)
                        total_w += w
            size_fused[t] = weighted_p / (total_w + 1e-12) if total_w > 0 else 0.5
        result[f'{pos}_size_fused_p_big'] = size_fused

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
