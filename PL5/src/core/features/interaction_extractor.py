"""
特征交互提取器 V1.0
建模特征间的二阶/高阶交互

改进点:
1. 位置交叉特征: wan_qian_sum, bai_shi_diff
2. 跨期交互: lag_1_wan * lag_2_qian
3. 数字频率交叉特征
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class FeatureInteractionExtractor:
    """
    特征交互提取器
    
    支持的交互类型:
    1. 位置内交叉 (同位置不同窗口)
    2. 位置间交叉 (不同位置间)
    3. 跨期交互 (当前期与历史期)
    4. 频率交互 (数字出现频率)
    """
    
    POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
    
    def __init__(
        self,
        enable_position_cross: bool = True,
        enable_temporal_cross: bool = True,
        enable_frequency_cross: bool = True,
        max_interaction_features: int = 50
    ) -> None:
        self.enable_position_cross: bool = enable_position_cross
        self.enable_temporal_cross: bool = enable_temporal_cross
        self.enable_frequency_cross: bool = enable_frequency_cross
        self.max_interaction_features: int = max_interaction_features
        
        self.digit_frequency_cache: Optional[pd.DataFrame] = None
        self.feature_stats: Dict[str, Dict[str, float]] = {}
    
    def extract_all(self, df: pd.DataFrame, lag_windows: List[int] = [1, 2, 3]) -> pd.DataFrame:
        """
        提取所有交互特征
        
        Args:
            df: 输入数据框
            lag_windows: 考虑的历史期数列表
            
        Returns:
            包含交互特征的增强数据框
        """
        result = df.copy()
        interaction_features = {}
        
        if self.enable_position_cross:
            pos_features = self.extract_position_cross_features(df)
            if pos_features:
                interaction_features.update(pos_features)
                logger.debug(f"提取了 {len(pos_features)} 个位置交叉特征")
            else:
                logger.warning("未能提取位置交叉特征，请检查数据列")
        
        if self.enable_temporal_cross:
            temp_features = self.extract_temporal_cross_features(df, lag_windows)
            if temp_features:
                interaction_features.update(temp_features)
                logger.debug(f"提取了 {len(temp_features)} 个跨期交互特征")
            else:
                logger.warning(f"未能提取跨期交互特征，请确保存在 lag_{{1,2,...}}_{{位置}} 列")
        
        if self.enable_frequency_cross:
            freq_features = self.extract_frequency_cross_features(df)
            if freq_features:
                interaction_features.update(freq_features)
                logger.debug(f"提取了 {len(freq_features)} 个频率交互特征")
            else:
                logger.warning("未能提取频率交互特征")
        
        if self.enable_position_cross:
            stats_features = self.extract_statistical_interactions(df)
            if stats_features:
                interaction_features.update(stats_features)
                logger.debug(f"提取了 {len(stats_features)} 个统计交互特征")
        
        if not interaction_features:
            logger.warning("未能提取任何交互特征")
            return result
        
        max_features = min(len(interaction_features), self.max_interaction_features)
        
        sorted_features = sorted(
            interaction_features.items(),
            key=lambda x: abs(x[1]['importance']),
            reverse=True
        )[:max_features]
        
        for feat_name, feat_data in sorted_features:
            values = feat_data['values']
            if len(values) < len(result):
                values = np.pad(values, (len(result) - len(values), 0), mode='edge')
            elif len(values) > len(result):
                values = values[:len(result)]
            result[feat_name] = values
        
        logger.info(f"提取了 {len(sorted_features)}/{len(interaction_features)} 个交互特征")
        
        return result
    
    def extract_position_cross_features(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """
        提取位置交叉特征
        
        组合方式:
        - 位置对: (wan, qian), (qian, bai), (bai, shi), (shi, ge)
        - 操作: sum, diff, product, ratio
        """
        features = {}
        
        position_pairs = [
            ('wan', 'qian'),
            ('qian', 'bai'),
            ('bai', 'shi'),
            ('shi', 'ge'),
            ('wan', 'ge'),
            ('wan', 'bai'),
            ('qian', 'shi'),
        ]
        
        for pos1, pos2 in position_pairs:
            if pos1 not in df.columns or pos2 not in df.columns:
                continue
            
            v1, v2 = df[pos1].values, df[pos2].values
            
            features[f'{pos1}_{pos2}_sum'] = {
                'values': v1 + v2,
                'importance': 1.0,
                'type': 'position_sum'
            }
            
            features[f'{pos1}_{pos2}_diff'] = {
                'values': v1 - v2,
                'importance': 0.9,
                'type': 'position_diff'
            }
            
            features[f'{pos1}_{pos2}_product'] = {
                'values': v1 * v2,
                'importance': 0.8,
                'type': 'position_product'
            }
            
            with np.errstate(divide='ignore', invalid='ignore'):
                ratio = np.where(np.abs(v2) > 0, v1 / (np.abs(v2) + 1e-6), 0)
                features[f'{pos1}_{pos2}_ratio'] = {
                    'values': np.clip(ratio, -10, 10),
                    'importance': 0.7,
                    'type': 'position_ratio'
                }
            
            features[f'{pos1}_{pos2}_mod'] = {
                'values': (v1 + v2) % 10,
                'importance': 0.85,
                'type': 'position_mod'
            }
            
            features[f'{pos1}_{pos2}_xor'] = {
                'values': (v1 + v2) % 2,
                'importance': 0.6,
                'type': 'position_xor'
            }
        
        for i, pos in enumerate(self.POSITIONS[:-1]):
            next_pos = self.POSITIONS[i + 1]
            if pos in df.columns and next_pos in df.columns:
                v1, v2 = df[pos].values, df[next_pos].values
                
                features[f'rolling_{pos}_mean_{next_pos}'] = {
                    'values': (v1 + v2) / 2,
                    'importance': 0.75,
                    'type': 'adjacent_mean'
                }
                
                features[f'rolling_{pos}_std_{next_pos}'] = {
                    'values': np.abs(v1 - v2),
                    'importance': 0.7,
                    'type': 'adjacent_std'
                }
        
        return features
    
    def extract_temporal_cross_features(
        self,
        df: pd.DataFrame,
        lag_windows: List[int] = [1, 2, 3]
    ) -> Dict[str, Dict[str, Any]]:
        """
        提取跨期交互特征
        
        组合方式:
        - 同位置lag: lag_n_pos * lag_m_pos
        - 异位置lag: lag_n_pos1 * lag_m_pos2
        """
        features = {}
        
        lag_cols = {}
        for lag in lag_windows:
            for pos in self.POSITIONS:
                col = f'lag_{lag}_{pos}'
                if col in df.columns:
                    if pos not in lag_cols:
                        lag_cols[pos] = {}
                    lag_cols[pos][lag] = df[col].values
        
        for pos1 in lag_cols:
            for pos2 in lag_cols:
                if pos1 != pos2:
                    lags1 = lag_cols[pos1]
                    lags2 = lag_cols[pos2]
                    
                    for lag1 in lags1:
                        for lag2 in lags2:
                            v1, v2 = lags1[lag1], lags2[lag2]
                            
                            importance = 0.6 / (abs(lag1 - lag2) + 1)
                            
                            features[f'temporal_{pos1}_lag{lag1}_x_{pos2}_lag{lag2}'] = {
                                'values': v1 * v2,
                                'importance': importance,
                                'type': 'temporal_cross'
                            }
                            
                            features[f'temporal_{pos1}_lag{lag1}_plus_{pos2}_lag{lag2}'] = {
                                'values': v1 + v2,
                                'importance': importance * 0.8,
                                'type': 'temporal_sum'
                            }
        
        for pos in lag_cols:
            lags = lag_cols[pos]
            sorted_lags = sorted(lags.keys())
            
            for i in range(len(sorted_lags) - 1):
                for j in range(i + 1, len(sorted_lags)):
                    lag1, lag2 = sorted_lags[i], sorted_lags[j]
                    v1, v2 = lags[lag1], lags[lag2]
                    
                    features[f'temporal_trend_{pos}_lag{lag1}_to_lag{lag2}'] = {
                        'values': v2 - v1,
                        'importance': 0.7,
                        'type': 'temporal_trend'
                    }
        
        return features
    
    def extract_frequency_cross_features(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """
        提取数字频率交叉特征
        
        包括:
        - 各位置数字出现频率
        - 频率乘积/比值
        - 冷热数字指示
        """
        features = {}
        
        window_sizes = [10, 20, 50]
        
        for pos in self.POSITIONS:
            if pos not in df.columns:
                continue
            
            values = df[pos].values
            
            for w in window_sizes:
                if len(values) < w:
                    continue
                
                window = values[-w:]
                
                digit_counts = defaultdict(int)
                for d in window:
                    digit_counts[d] += 1
                
                freq_array = np.array([digit_counts.get(d, 0) for d in range(10)])
                total = freq_array.sum() + 1e-6
                freq_norm = freq_array / total
                
                current_freq = np.array([digit_counts.get(int(values[-1]), 0)]) / total
                
                features[f'freq_{pos}_w{w}_entropy'] = {
                    'values': self._compute_entropy(freq_norm),
                    'importance': 0.5,
                    'type': 'frequency_entropy'
                }
                
                features[f'freq_{pos}_w{w}_hot_indicator'] = {
                    'values': self._compute_hotness(freq_norm, int(values[-1])),
                    'importance': 0.6,
                    'type': 'frequency_hotness'
                }
                
                features[f'freq_{pos}_w{w}_cold_indicator'] = {
                    'values': self._compute_coldness(freq_norm, int(values[-1])),
                    'importance': 0.5,
                    'type': 'frequency_coldness'
                }
        
        pos_pairs = [('wan', 'qian'), ('shi', 'ge'), ('wan', 'ge')]
        for w in [10, 20]:
            for pos1, pos2 in pos_pairs:
                freq1 = self._get_digit_frequency(df, pos1, w)
                freq2 = self._get_digit_frequency(df, pos2, w)
                
                if freq1 is not None and freq2 is not None:
                    features[f'freq_cross_{pos1}_{pos2}_w{w}_product'] = {
                        'values': freq1 * freq2,
                        'importance': 0.55,
                        'type': 'frequency_product'
                    }
                    
                    features[f'freq_cross_{pos1}_{pos2}_w{w}_ratio'] = {
                        'values': freq1 / (freq2 + 1e-6),
                        'importance': 0.5,
                        'type': 'frequency_ratio'
                    }
        
        return features
    
    def extract_statistical_interactions(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """
        提取统计交互特征
        
        包括:
        - 各位置的波动率交互
        - 偏度/峰度交叉
        - 序列相关性
        """
        features = {}
        
        for pos in self.POSITIONS:
            if pos not in df.columns:
                continue
            
            values = df[pos].values
            
            if len(values) < 20:
                continue
            
            for w in [10, 20]:
                if len(values) < w:
                    continue
                
                window = values[-w:]
                
                rolling_mean = pd.Series(window).rolling(5).mean().fillna(window.mean())
                rolling_std = pd.Series(window).rolling(5).std().fillna(window.std())
                
                cv = rolling_std / (np.abs(rolling_mean) + 1e-6)
                
                features[f'stat_cv_{pos}_w{w}'] = {
                    'values': cv.values[-len(values):] if len(cv) > len(values) else np.pad(
                        cv.values, (len(values) - len(cv), 0), mode='edge'
                    ),
                    'importance': 0.45,
                    'type': 'coefficient_of_variation'
                }
                
                rolling_range = pd.Series(window).rolling(5).max() - pd.Series(window).rolling(5).min()
                rolling_range = rolling_range.fillna(0)
                
                features[f'stat_range_{pos}_w{w}'] = {
                    'values': rolling_range.values[-len(values):] if len(rolling_range) > len(values) else np.pad(
                        rolling_range.values, (len(values) - len(rolling_range), 0), mode='edge'
                    ),
                    'importance': 0.4,
                    'type': 'rolling_range'
                }
        
        for i, pos1 in enumerate(self.POSITIONS[:-1]):
            pos2 = self.POSITIONS[i + 1]
            
            if pos1 not in df.columns or pos2 not in df.columns:
                continue
            
            v1, v2 = df[pos1].values, df[pos2].values
            
            if len(v1) > 10:
                corr = self._rolling_correlation(v1, v2, window=20)
                
                features[f'stat_corr_{pos1}_{pos2}'] = {
                    'values': corr,
                    'importance': 0.55,
                    'type': 'rolling_correlation'
                }
        
        return features
    
    def _compute_entropy(self, probs: np.ndarray) -> np.ndarray:
        """计算熵"""
        probs = probs + 1e-10
        return -np.sum(probs * np.log(probs), axis=-1)
    
    def _compute_hotness(self, freq: np.ndarray, current_digit: int) -> np.ndarray:
        """计算热号指标"""
        hotness = np.zeros(len(freq)) if len(freq.shape) > 0 else 0.0
        if len(freq.shape) > 0:
            if 0 <= current_digit < len(freq):
                hotness = freq / (freq.max() + 1e-6)
        return hotness
    
    def _compute_coldness(self, freq: np.ndarray, current_digit: int) -> np.ndarray:
        """计算冷号指标"""
        coldness = np.zeros(len(freq)) if len(freq.shape) > 0 else 0.0
        if len(freq.shape) > 0:
            if 0 <= current_digit < len(freq):
                min_freq = freq.min() + 1e-6
                coldness = (min_freq / (freq + 1e-6))
                if 0 <= current_digit < len(coldness):
                    coldness[current_digit] = 1.0
        return coldness
    
    def _get_digit_frequency(self, df: pd.DataFrame, pos: str, window: int) -> Optional[np.ndarray]:
        """获取指定窗口的数字频率"""
        if pos not in df.columns or len(df) < window:
            return None
        
        values = df[pos].values[-window:]
        freq = np.zeros(10)
        
        for v in values:
            if 0 <= v < 10:
                freq[int(v)] += 1
        
        return freq / freq.sum()
    
    def _rolling_correlation(self, x: np.ndarray, y: np.ndarray, window: int) -> np.ndarray:
        """计算滚动相关系数"""
        result = np.full(len(x), 0.0)
        
        for i in range(window, len(x)):
            x_window = x[i-window:i]
            y_window = y[i-window:i]
            
            x_mean = x_window.mean()
            y_mean = y_window.mean()
            
            cov = ((x_window - x_mean) * (y_window - y_mean)).mean()
            std_x = np.sqrt(((x_window - x_mean) ** 2).mean())
            std_y = np.sqrt(((y_window - y_mean) ** 2).mean())
            
            if std_x > 1e-10 and std_y > 1e-10:
                result[i] = cov / (std_x * std_y)
        
        return result
    
    def get_feature_importance(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        基于特征方差计算重要性
        """
        importance = {}
        
        for col in df.columns:
            if any(prefix in col for prefix in ['position_', 'temporal_', 'freq_', 'stat_']):
                variance = df[col].var()
                importance[col] = np.log1p(variance) if variance > 0 else 0
        
        return importance
