"""
黄金分割-波动率范围移动识别集成模块 V1.0

设计理念：
黄金分割不再作为独立的特征组（如旧的 fibonacci rolling mean/std）使用，
而是与波动率范围（rolling max-min）核心功能深度整合，形成"黄金分割波动率
范围移动识别器"（Golden-Ratio Volatility Range Movement Identifier, GRVR）。

核心能力：
1. 在滚动波动率范围内应用黄金分割回撤位（0.236/0.382/0.5/0.618/0.786）
   作为支撑/阻力参考系
2. 识别当前值在波动率范围内的相对位置（归一化 0~1）
3. 检测波动率范围移动模式：
   - 向上突破（Breakout Up）：突破 0.786 扩展位
   - 向下突破（Breakout Down）：跌破 0.236 支撑位
   - 反转信号（Reversal）：在 0.382/0.618 黄金位出现反弹/回落
   - 整理信号（Consolidation）：在 0.5 中轴附近震荡
   - 范围扩张/收缩（Range Expansion/Contraction）：波动率状态变化
4. 输出多维特征，直接供下游模型融合使用

适用场景：排列5等数字型序列的波动率结构分析。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 黄金分割关键回撤位（Fibonacci retracement levels）
GOLDEN_RATIO_LEVELS: Dict[str, float] = {
    'extreme_support': 0.236,   # 极强支撑/扩展
    'deep_support': 0.382,      # 深度回撤支撑
    'pivot': 0.5,               # 中轴
    'golden_resistance': 0.618, # 黄金阻力
    'extension': 0.786,         # 扩展位
}

# 默认分析窗口（保留与原 fibonacci 一致的 5/8/13，新增 21）
DEFAULT_WINDOWS: tuple = (5, 8, 13, 21)

# 默认位置（排列5五位）
DEFAULT_POSITIONS: tuple = ('wan', 'qian', 'bai', 'shi', 'ge')


class RangeMovementType(Enum):
    """波动率范围移动类型"""
    CONSOLIDATION = "consolidation"   # 整理：接近 0.5 中轴
    REVERSAL_UP = "reversal_up"       # 反转上行：在 0.382 支撑反弹
    REVERSAL_DOWN = "reversal_down"   # 反转下行：在 0.618 阻力回落
    BREAKOUT_UP = "breakout_up"       # 向上突破：超过 0.786 扩展
    BREAKOUT_DOWN = "breakout_down"   # 向下突破：跌破 0.236 支撑
    NEUTRAL = "neutral"               # 中性：未触发明显模式


@dataclass
class GoldenRatioVolatilityConfig:
    """黄金分割波动率识别配置"""
    windows: Sequence[int] = DEFAULT_WINDOWS
    positions: Sequence[str] = DEFAULT_POSITIONS
    # 黄金分割位阈值
    consolidation_band: float = 0.10      # 距离 0.5 中轴 ±0.10 视为整理
    reversal_band: float = 0.05           # 距离 0.382/0.618 ±0.05 视为反转触发
    breakout_extension: float = 0.786     # 突破扩展位阈值
    breakout_support: float = 0.236       # 跌破支撑位阈值
    # 范围扩张/收缩判定
    range_expansion_ratio: float = 1.2    # 当前范围 / 前期范围 > 1.2 视为扩张
    range_contraction_ratio: float = 0.8  # 当前范围 / 前期范围 < 0.8 视为收缩
    min_samples: int = 3                  # 最小样本数


@dataclass
class RangeMovementSignal:
    """单位置单窗口的范围移动信号"""
    position: str
    window: int
    range_low: float
    range_high: float
    range_width: float
    current_value: float
    normalized_position: float            # 0~1 归一化位置
    nearest_level_name: str               # 最近的黄金分割位名称
    nearest_level_value: float
    distance_to_nearest: float            # 距最近黄金位的归一化距离
    movement_type: RangeMovementType
    range_regime: str                     # 'expansion' / 'contraction' / 'stable'
    prev_range_width: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'position': self.position,
            'window': self.window,
            'range_low': float(self.range_low),
            'range_high': float(self.range_high),
            'range_width': float(self.range_width),
            'current_value': float(self.current_value),
            'normalized_position': float(self.normalized_position),
            'nearest_level_name': self.nearest_level_name,
            'nearest_level_value': float(self.nearest_level_value),
            'distance_to_nearest': float(self.distance_to_nearest),
            'movement_type': self.movement_type.value,
            'range_regime': self.range_regime,
            'prev_range_width': float(self.prev_range_width) if self.prev_range_width is not None else None,
        }


class GoldenRatioVolatilityModule:
    """黄金分割-波动率范围移动识别器

    将黄金分割回撤位与滚动波动率范围（rolling max-min）深度整合，
    识别序列在波动率范围内的移动模式，输出多维集成特征。

    用法：
        module = GoldenRatioVolatilityModule()
        features_df = module.transform(df)            # 仅生成特征列
        signals = module.identify_signals(df)         # 获取结构化信号
        report = module.generate_report(df)           # 生成可读报告
    """

    def __init__(self, config: Optional[GoldenRatioVolatilityConfig] = None):
        self.config = config or GoldenRatioVolatilityConfig()
        self.windows = tuple(self.config.windows)
        self.positions = tuple(self.config.positions)
        # 预计算黄金分割位列表（按升序）
        self._level_items = sorted(
            GOLDEN_RATIO_LEVELS.items(), key=lambda kv: kv[1]
        )

    # ------------------------------------------------------------------
    # 核心特征生成
    # ------------------------------------------------------------------

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """为 DataFrame 添加黄金分割-波动率集成特征列。

        Args:
            df: 包含各位置列的原始数据

        Returns:
            添加了新特征列的 DataFrame（副本）
        """
        if df is None or len(df) == 0:
            return df.copy() if df is not None else df

        positions = [p for p in self.positions if p in df.columns]
        if not positions:
            logger.warning("[GRVR] 未找到任何位置列，跳过特征生成")
            return df.copy()

        # 批量收集所有新列，最后一次性 concat，避免 DataFrame 碎片化
        all_new_cols: Dict[str, pd.Series] = {}
        for pos in positions:
            for window in self.windows:
                self._collect_position_window_features(all_new_cols, df, pos, window)

        if not all_new_cols:
            return df.copy()

        new_df = pd.DataFrame(all_new_cols, index=df.index)
        return pd.concat([df.copy(), new_df], axis=1)

    def _collect_position_window_features(
        self,
        cols: Dict[str, pd.Series],
        source: pd.DataFrame,
        pos: str,
        window: int,
    ) -> None:
        """为指定位置+窗口计算黄金分割波动率特征，写入 cols 字典（批量收集）"""
        if len(source) < self.config.min_samples:
            return

        s = source[pos].astype(float)

        # 滚动范围（max-min）
        roll_max = s.rolling(window=window, min_periods=1).max()
        roll_min = s.rolling(window=window, min_periods=1).min()
        range_width = (roll_max - roll_min).abs()

        # 前期范围宽度（用于扩张/收缩判定）
        prev_range_width = range_width.shift(window).fillna(range_width)

        # 归一化位置 (0~1)：当前值在 [min, max] 中的相对位置
        denom = range_width.where(range_width > 1e-9, np.nan)
        normalized_pos = (s - roll_min) / denom
        normalized_pos = normalized_pos.fillna(0.5).clip(0.0, 1.0)

        prefix = f'{pos}_grv_{window}'

        # 1. 范围基础特征
        cols[f'{prefix}_range_low'] = roll_min
        cols[f'{prefix}_range_high'] = roll_max
        cols[f'{prefix}_range_width'] = range_width
        cols[f'{prefix}_prev_range_width'] = prev_range_width

        # 2. 归一化位置
        cols[f'{prefix}_norm_pos'] = normalized_pos

        # 3. 距各黄金分割位的距离（5个特征）
        for level_name, level_val in self._level_items:
            cols[f'{prefix}_dist_{level_name}'] = (normalized_pos - level_val).abs()

        # 4. 最近的黄金分割位（one-hot 5维）
        nearest_name = self._compute_nearest_level(normalized_pos)
        for level_name, _ in self._level_items:
            cols[f'{prefix}_is_near_{level_name}'] = (nearest_name == level_name).astype(np.int8)

        # 5. 范围移动模式（one-hot 6维）
        movement_types = self._classify_movement(normalized_pos, range_width, prev_range_width)
        for mt in RangeMovementType:
            cols[f'{prefix}_movement_{mt.value}'] = (movement_types == mt).astype(np.int8)

        # 6. 范围状态（expansion/contraction/stable，one-hot 3维）
        regimes = self._classify_range_regime(range_width, prev_range_width)
        for regime in ('expansion', 'contraction', 'stable'):
            cols[f'{prefix}_regime_{regime}'] = (regimes == regime).astype(np.int8)

        # 7. 综合信号强度（0~1）：距离最近黄金位越近，信号越强
        nearest_dist = self._min_distance(normalized_pos)
        cols[f'{prefix}_signal_strength'] = (1.0 - nearest_dist).clip(0.0, 1.0)

    # ------------------------------------------------------------------
    # 分类与判定逻辑
    # ------------------------------------------------------------------

    def _compute_nearest_level(self, normalized_pos: pd.Series) -> pd.Series:
        """为每个样本判定最近的黄金分割位名称"""
        if len(normalized_pos) == 0:
            return normalized_pos
        # 构建距离矩阵 (n_samples, 5)
        pos_vals = normalized_pos.values.reshape(-1, 1)
        level_vals = np.array([lv for _, lv in self._level_items]).reshape(1, -1)
        dists = np.abs(pos_vals - level_vals)
        nearest_idx = np.argmin(dists, axis=1)
        nearest_names = np.array([name for name, _ in self._level_items])[nearest_idx]
        return pd.Series(nearest_names, index=normalized_pos.index)

    def _min_distance(self, normalized_pos: pd.Series) -> pd.Series:
        """每个样本到最近黄金位的最小距离"""
        if len(normalized_pos) == 0:
            return normalized_pos
        pos_vals = normalized_pos.values.reshape(-1, 1)
        level_vals = np.array([lv for _, lv in self._level_items]).reshape(1, -1)
        dists = np.abs(pos_vals - level_vals)
        return pd.Series(dists.min(axis=1), index=normalized_pos.index)

    def _classify_movement(
        self,
        normalized_pos: pd.Series,
        range_width: pd.Series,
        prev_range_width: pd.Series,
    ) -> pd.Series:
        """根据归一化位置判定范围移动类型"""
        n = len(normalized_pos)
        result = np.array([RangeMovementType.NEUTRAL.value] * n, dtype=object)

        pos_arr = normalized_pos.values
        cb = self.config.consolidation_band
        rb = self.config.reversal_band
        ext = self.config.breakout_extension
        sup = self.config.breakout_support

        # 整理：接近 0.5 中轴
        consolidation_mask = np.abs(pos_arr - 0.5) <= cb
        result[consolidation_mask] = RangeMovementType.CONSOLIDATION.value

        # 反转上行：在 0.382 支撑位附近
        reversal_up_mask = np.abs(pos_arr - 0.382) <= rb
        result[reversal_up_mask] = RangeMovementType.REVERSAL_UP.value

        # 反转下行：在 0.618 阻力位附近
        reversal_down_mask = np.abs(pos_arr - 0.618) <= rb
        result[reversal_down_mask] = RangeMovementType.REVERSAL_DOWN.value

        # 向上突破：超过 0.786 扩展位
        breakout_up_mask = pos_arr >= ext
        result[breakout_up_mask] = RangeMovementType.BREAKOUT_UP.value

        # 向下突破：跌破 0.236 支撑位
        breakout_down_mask = pos_arr <= sup
        result[breakout_down_mask] = RangeMovementType.BREAKOUT_DOWN.value

        # 优先级：突破 > 反转 > 整理（按强度覆盖）
        # （上面赋值顺序已自然实现优先级，后赋值覆盖先赋值）

        return pd.Series(result, index=normalized_pos.index).map(
            lambda v: RangeMovementType(v) if isinstance(v, str) else v
        )

    def _classify_range_regime(
        self,
        range_width: pd.Series,
        prev_range_width: pd.Series,
    ) -> pd.Series:
        """判定波动率范围状态：扩张/收缩/稳定"""
        n = len(range_width)
        result = np.array(['stable'] * n, dtype=object)

        rw = range_width.values
        prw = prev_range_width.values
        safe_prw = np.where(np.abs(prw) < 1e-9, 1.0, prw)
        ratio = rw / safe_prw

        result[ratio > self.config.range_expansion_ratio] = 'expansion'
        result[ratio < self.config.range_contraction_ratio] = 'contraction'

        return pd.Series(result, index=range_width.index)

    # ------------------------------------------------------------------
    # 结构化信号与报告
    # ------------------------------------------------------------------

    def identify_signals(self, df: pd.DataFrame) -> List[RangeMovementSignal]:
        """识别最新的范围移动信号（每个位置+窗口一个信号）。

        Args:
            df: 原始数据

        Returns:
            信号列表
        """
        if df is None or len(df) == 0:
            return []

        signals: List[RangeMovementSignal] = []
        positions = [p for p in self.positions if p in df.columns]

        for pos in positions:
            s = df[pos].astype(float)
            for window in self.windows:
                if len(s) < max(window, self.config.min_samples):
                    continue
                sig = self._build_signal(s, pos, window)
                if sig is not None:
                    signals.append(sig)

        return signals

    def _build_signal(
        self,
        s: pd.Series,
        pos: str,
        window: int,
    ) -> Optional[RangeMovementSignal]:
        """为最新样本构建信号"""
        recent = s.iloc[-window:]
        if len(recent) < self.config.min_samples:
            return None

        range_low = float(recent.min())
        range_high = float(recent.max())
        range_width = range_high - range_low
        current_value = float(s.iloc[-1])

        if range_width < 1e-9:
            normalized_pos = 0.5
        else:
            normalized_pos = (current_value - range_low) / range_width
            normalized_pos = float(max(0.0, min(1.0, normalized_pos)))

        # 最近黄金分割位
        nearest_name, nearest_val, nearest_dist = self._find_nearest_level(normalized_pos)

        # 前期范围宽度
        if len(s) >= 2 * window:
            prev_window = s.iloc[-2 * window:-window]
            prev_range_width = float(prev_window.max() - prev_window.min())
        else:
            prev_range_width = None

        # 移动类型
        movement_type = self._classify_single(normalized_pos)
        # 范围状态
        range_regime = self._classify_regime_single(range_width, prev_range_width)

        return RangeMovementSignal(
            position=pos,
            window=window,
            range_low=range_low,
            range_high=range_high,
            range_width=range_width,
            current_value=current_value,
            normalized_position=normalized_pos,
            nearest_level_name=nearest_name,
            nearest_level_value=nearest_val,
            distance_to_nearest=nearest_dist,
            movement_type=movement_type,
            range_regime=range_regime,
            prev_range_width=prev_range_width,
        )

    def _find_nearest_level(self, normalized_pos: float) -> tuple:
        """找出最近的黄金分割位"""
        best_name, best_val, best_dist = 'pivot', 0.5, abs(normalized_pos - 0.5)
        for name, val in self._level_items:
            d = abs(normalized_pos - val)
            if d < best_dist:
                best_name, best_val, best_dist = name, val, d
        return best_name, best_val, best_dist

    def _classify_single(self, normalized_pos: float) -> RangeMovementType:
        """判定单个样本的移动类型"""
        cb = self.config.consolidation_band
        rb = self.config.reversal_band
        ext = self.config.breakout_extension
        sup = self.config.breakout_support

        if normalized_pos >= ext:
            return RangeMovementType.BREAKOUT_UP
        if normalized_pos <= sup:
            return RangeMovementType.BREAKOUT_DOWN
        if abs(normalized_pos - 0.382) <= rb:
            return RangeMovementType.REVERSAL_UP
        if abs(normalized_pos - 0.618) <= rb:
            return RangeMovementType.REVERSAL_DOWN
        if abs(normalized_pos - 0.5) <= cb:
            return RangeMovementType.CONSOLIDATION
        return RangeMovementType.NEUTRAL

    def _classify_regime_single(
        self,
        range_width: float,
        prev_range_width: Optional[float],
    ) -> str:
        """判定单个样本的范围状态"""
        if prev_range_width is None or prev_range_width < 1e-9:
            return 'stable'
        ratio = range_width / prev_range_width
        if ratio > self.config.range_expansion_ratio:
            return 'expansion'
        if ratio < self.config.range_contraction_ratio:
            return 'contraction'
        return 'stable'

    # ------------------------------------------------------------------
    # 报告生成
    # ------------------------------------------------------------------

    def generate_report(self, df: pd.DataFrame) -> str:
        """生成人类可读的范围移动识别报告"""
        signals = self.identify_signals(df)
        if not signals:
            return "[GRVR] 数据不足，无法生成报告"

        lines = ["=== 黄金分割-波动率范围移动识别报告 ==="]
        lines.append(f"分析位置: {sorted(set(sig.position for sig in signals))}")
        lines.append(f"分析窗口: {sorted(set(sig.window for sig in signals))}")
        lines.append("")

        # 按位置分组
        by_pos: Dict[str, List[RangeMovementSignal]] = {}
        for sig in signals:
            by_pos.setdefault(sig.position, []).append(sig)

        for pos in sorted(by_pos.keys()):
            lines.append(f"--- 位置: {pos} ---")
            for sig in by_pos[pos]:
                lines.append(
                    f"  [w={sig.window}] 当前值={sig.current_value:.2f} | "
                    f"范围=[{sig.range_low:.2f}, {sig.range_high:.2f}] "
                    f"(宽={sig.range_width:.2f}) | "
                    f"归一化位置={sig.normalized_position:.3f} | "
                    f"最近黄金位={sig.nearest_level_name}({sig.nearest_level_value:.3f}) | "
                    f"移动类型={sig.movement_type.value} | "
                    f"范围状态={sig.range_regime}"
                )
            lines.append("")

        # 汇总统计
        movement_counts: Dict[str, int] = {}
        regime_counts: Dict[str, int] = {}
        for sig in signals:
            movement_counts[sig.movement_type.value] = movement_counts.get(sig.movement_type.value, 0) + 1
            regime_counts[sig.range_regime] = regime_counts.get(sig.range_regime, 0) + 1

        lines.append("--- 汇总 ---")
        lines.append(f"移动类型分布: {movement_counts}")
        lines.append(f"范围状态分布: {regime_counts}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 便捷接口
    # ------------------------------------------------------------------

    def get_feature_columns(self) -> List[str]:
        """返回该模块会生成的所有特征列名（用于特征选择/对齐）"""
        cols: List[str] = []
        for pos in self.positions:
            for window in self.windows:
                prefix = f'{pos}_grv_{window}'
                cols.extend([
                    f'{prefix}_range_low',
                    f'{prefix}_range_high',
                    f'{prefix}_range_width',
                    f'{prefix}_prev_range_width',
                    f'{prefix}_norm_pos',
                ])
                for level_name, _ in self._level_items:
                    cols.append(f'{prefix}_dist_{level_name}')
                for level_name, _ in self._level_items:
                    cols.append(f'{prefix}_is_near_{level_name}')
                for mt in RangeMovementType:
                    cols.append(f'{prefix}_movement_{mt.value}')
                for regime in ('expansion', 'contraction', 'stable'):
                    cols.append(f'{prefix}_regime_{regime}')
                cols.append(f'{prefix}_signal_strength')
        return cols


# 模块级单例（懒加载）
_module_instance: Optional[GoldenRatioVolatilityModule] = None


def get_grvr_module(config: Optional[GoldenRatioVolatilityConfig] = None) -> GoldenRatioVolatilityModule:
    """获取黄金分割波动率识别模块实例（单例）"""
    global _module_instance
    if _module_instance is None or config is not None:
        _module_instance = GoldenRatioVolatilityModule(config=config)
    return _module_instance


def add_golden_ratio_volatility_features(
    df: pd.DataFrame,
    config: Optional[GoldenRatioVolatilityConfig] = None,
) -> pd.DataFrame:
    """便捷函数：为 DataFrame 添加黄金分割-波动率集成特征"""
    module = get_grvr_module(config) if config is None else GoldenRatioVolatilityModule(config=config)
    return module.transform(df)
