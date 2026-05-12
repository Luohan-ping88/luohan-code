"""
排列五号码冷热分析模块
针对中国体育彩票排列五 0-9 数字分布特征的专业分析
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import Counter


class HotColdAnalyzer:
    """
    号码冷热分析器
    
    分析排列五历史数据中各号码的出现频率，
    识别热号（高频）、温号（中频）、冷号（低频）
    """
    
    def __init__(self, hot_threshold: float = 0.12, cold_threshold: float = 0.08):
        """
        初始化冷热分析器
        
        Args:
            hot_threshold: 热号阈值（出现概率高于此值视为热号）
            cold_threshold: 冷号阈值（出现概率低于此值视为冷号）
        """
        self.hot_threshold = hot_threshold
        self.cold_threshold = cold_threshold
        self.digit_freq: Dict[str, Dict[int, int]] = {}
        self.hot_cold_cache: Optional[Dict] = None
        
    def analyze_frequency(self, df: pd.DataFrame, positions: List[str], 
                        window: int = 50) -> Dict[str, np.ndarray]:
        """
        分析各位置号码出现频率
        
        Args:
            df: 历史数据DataFrame
            positions: 位置列表
            window: 分析窗口大小
            
        Returns:
            {位置: 频率数组[0-9]}
        """
        freq_result = {}
        
        for pos in positions:
            if pos not in df.columns:
                freq_result[pos] = np.ones(10) / 10
                continue
                
            recent = df[pos].tail(window)
            counter = Counter(recent.values.flatten())
            freq = np.zeros(10)
            
            for digit, count in counter.items():
                if 0 <= digit <= 9:
                    freq[digit] = count / len(recent)
                    
            freq_result[pos] = freq
            
        return freq_result
    
    def identify_hot_cold(self, freq: np.ndarray) -> Dict[str, List[int]]:
        """
        识别热号和冷号
        
        Args:
            freq: 频率数组 shape=(10,)
            
        Returns:
            {'hot': [热号列表], 'warm': [温号列表], 'cold': [冷号列表]}
        """
        hot = []
        warm = []
        cold = []
        
        for digit, f in enumerate(freq):
            if f > self.hot_threshold:
                hot.append(digit)
            elif f < self.cold_threshold:
                cold.append(digit)
            else:
                warm.append(digit)
                
        return {'hot': hot, 'warm': warm, 'cold': cold}
    
    def compute_hot_cold_features(self, df: pd.DataFrame, 
                                positions: List[str]) -> pd.DataFrame:
        """
        计算冷热分析特征
        
        Args:
            df: 历史数据DataFrame
            positions: 位置列表
            
        Returns:
            包含冷热分析特征的DataFrame
        """
        features = pd.DataFrame(index=df.index)
        
        # 不同窗口的频率分析
        for window in [10, 20, 50]:
            freq_dict = self.analyze_frequency(df, positions, window)
            
            for pos in positions:
                freq = freq_dict[pos]
                prefix = f'{pos}_w{window}'
                
                # 基本频率特征
                features[f'{prefix}_freq'] = [freq[d] for d in df[pos].values]
                
                # 热冷号标识
                hot_ids = self.identify_hot_cold(freq)['hot']
                cold_ids = self.identify_hot_cold(freq)['cold']
                features[f'{prefix}_is_hot'] = df[pos].isin(hot_ids).astype(int)
                features[f'{prefix}_is_cold'] = df[pos].isin(cold_ids).astype(int)
                
                # 热号占比
                features[f'{prefix}_hot_ratio'] = len(hot_ids) / 10
                features[f'{prefix}_cold_ratio'] = len(cold_ids) / 10
                
                # 频率的统计特征
                features[f'{prefix}_freq_std'] = freq.std()
                features[f'{prefix}_freq_max'] = freq.max()
                features[f'{prefix}_freq_min'] = freq.min()
                features[f'{prefix}_freq_range'] = freq.max() - freq.min()
                
        # 遗漏值分析（某号码距上次出现多少期）
        miss_features = self._compute_miss_values(df, positions)
        for col, values in miss_features.items():
            features[col] = values
            
        return features
    
    def _compute_miss_values(self, df: pd.DataFrame, 
                            positions: List[str]) -> Dict[str, np.ndarray]:
        """
        计算各号码的遗漏值（距上次出现期数）
        """
        miss_result = {}
        
        for pos in positions:
            if pos not in df.columns:
                continue
                
            # 当前遗漏
            current_miss = np.zeros(len(df))
            
            for i, row in enumerate(df[pos].values):
                digit = int(row)
                
                # 查找上一次出现的位置
                miss = 0
                for j in range(i - 1, -1, -1):
                    miss += 1
                    if int(df[pos].iloc[j]) == digit:
                        break
                        
                current_miss[i] = miss
                
            miss_result[f'{pos}_miss'] = current_miss
            
            # 平均遗漏
            avg_miss = np.zeros(10)
            for digit in range(10):
                appearances = np.where(df[pos].values == digit)[0]
                if len(appearances) > 1:
                    gaps = np.diff(appearances)
                    avg_miss[digit] = np.mean(gaps)
                else:
                    avg_miss[digit] = 50  # 默认值
                    
            miss_result[f'{pos}_avg_miss'] = [avg_miss[int(d)] for d in df[pos].values]
            
        return miss_result
    
    def compute_position_correlation(self, df: pd.DataFrame,
                                   positions: List[str]) -> pd.DataFrame:
        """
        计算位置间冷热相关性
        
        Returns:
            相关性特征DataFrame
        """
        features = pd.DataFrame(index=df.index)
        
        # 计算同期冷热一致性
        freq_dict = self.analyze_frequency(df, positions, 20)
        
        # 各位置冷热一致性
        hot_counts = np.zeros(len(df))
        cold_counts = np.zeros(len(df))
        
        for pos in positions:
            freq = freq_dict[pos]
            hot_ids = self.identify_hot_cold(freq)['hot']
            cold_ids = self.identify_hot_cold(freq)['cold']
            
            hot_counts += df[pos].isin(hot_ids).astype(int).values
            cold_counts += df[pos].isin(cold_ids).astype(int).values
            
        features['all_pos_hot_count'] = hot_counts
        features['all_pos_cold_count'] = cold_counts
        features['hot_cold_balance'] = hot_counts - cold_counts
        
        # 位置间冷热传递性
        for i, pos1 in enumerate(positions):
            for j, pos2 in enumerate(positions):
                if i >= j:
                    continue
                    
                # 统计同热号出现的次数
                freq1 = freq_dict[pos1]
                freq2 = freq_dict[pos2]
                
                hot1 = set(self.identify_hot_cold(freq1)['hot'])
                hot2 = set(self.identify_hot_cold(freq2)['hot'])
                cold1 = set(self.identify_hot_cold(freq1)['cold'])
                cold2 = set(self.identify_hot_cold(freq2)['cold'])
                
                # 共热率
                if len(hot1) > 0 and len(hot2) > 0:
                    co_hot = len(hot1 & hot2) / len(hot1 | hot2)
                else:
                    co_hot = 0
                    
                features[f'co_hot_{pos1}_{pos2}'] = co_hot
                
        return features
    
    def get_frequency_trend(self, df: pd.DataFrame, pos: str,
                           windows: List[int] = [10, 20, 50]) -> Dict[int, float]:
        """
        分析某位置频率变化趋势
        
        Returns:
            {窗口大小: 频率变化斜率}
        """
        trends = {}
        
        for window in windows:
            freq_dict = self.analyze_frequency(df, [pos], window)
            freq = freq_dict[pos]
            
            # 计算频率的标准差作为稳定性指标
            freq_std = freq.std()
            freq_mean = freq.mean()
            
            # 稳定性系数
            stability = freq_std / freq_mean if freq_mean > 0 else 0
            trends[window] = stability
            
        return trends


class NumberPatternAnalyzer:
    """
    号码形态分析器
    
    分析排列五开奖号码的形态特征：
    - 奇偶比例
    - 大小比例  
    - 连号情况
    - 重号情况
    """
    
    @staticmethod
    def is_odd(digit: int) -> bool:
        return digit % 2 == 1
    
    @staticmethod
    def is_large(digit: int, threshold: int = 5) -> bool:
        return digit >= threshold
    
    def compute_morphology_features(self, df: pd.DataFrame,
                                   positions: List[str]) -> pd.DataFrame:
        """
        计算形态特征
        
        Returns:
            形态特征DataFrame
        """
        features = pd.DataFrame(index=df.index)
        
        # 奇偶特征
        odd_counts = np.zeros(len(df))
        large_counts = np.zeros(len(df))
        
        for pos in positions:
            digits = df[pos].values
            
            # 奇数个数
            odd_count = np.array([self.is_odd(int(d)) for d in digits]).sum(axis=0)
            odd_counts += odd_count
            
            # 大号个数 (>=5为大)
            large_count = np.array([self.is_large(int(d)) for d in digits]).sum(axis=0)
            large_counts += large_count
            
        features['odd_count'] = odd_counts
        features['even_count'] = 5 - odd_counts
        features['large_count'] = large_counts
        features['small_count'] = 5 - large_counts
        
        # 奇偶形态
        features['morphology_odd_even'] = odd_counts.astype(str) + 'o' + (5 - odd_counts).astype(str) + 'e'
        
        # 连号检测
        for i in range(len(positions) - 1):
            pos1, pos2 = positions[i], positions[i + 1]
            diff = np.abs(df[pos1].values.astype(int) - df[pos2].values.astype(int))
            features[f'consecutive_{pos1}_{pos2}'] = (diff == 1).astype(int)
            features[f'same_{pos1}_{pos2}'] = (diff == 0).astype(int)
            
        # 重号检测（与上期相同位置相同号码）
        for pos in positions:
            same_as_prev = np.zeros(len(df))
            for i in range(1, len(df)):
                if df[pos].iloc[i] == df[pos].iloc[i-1]:
                    same_as_prev[i] = 1
            features[f'repeat_{pos}'] = same_as_prev
            
        features['total_repeat'] = features[[f'repeat_{pos}' for pos in positions]].sum(axis=1)
        
        return features
    
    def compute_distribution_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算号码分布特征
        
        分析5个位置号码的整体分布情况
        """
        features = pd.DataFrame(index=df.index)
        
        # 合并所有位置号码
        all_digits = np.zeros((len(df), 5))
        for i, pos in enumerate(POSITIONS):
            if pos in df.columns:
                all_digits[:, i] = df[pos].values.astype(int)
                
        # 分布特征
        features['digit_mean'] = all_digits.mean(axis=1)
        features['digit_std'] = all_digits.std(axis=1)
        features['digit_max'] = all_digits.max(axis=1)
        features['digit_min'] = all_digits.min(axis=1)
        features['digit_range'] = features['digit_max'] - features['digit_min']
        
        # 中位数
        features['digit_median'] = np.median(all_digits, axis=1)
        
        # 唯一数字个数
        features['unique_digits'] = np.array([
            len(set(row)) for row in all_digits
        ])
        
        return features


# 全局实例
_hot_cold_analyzer: Optional[HotColdAnalyzer] = None
_pattern_analyzer: Optional[NumberPatternAnalyzer] = None


def get_hot_cold_analyzer() -> HotColdAnalyzer:
    """获取冷热分析器全局实例"""
    global _hot_cold_analyzer
    if _hot_cold_analyzer is None:
        _hot_cold_analyzer = HotColdAnalyzer()
    return _hot_cold_analyzer


def get_pattern_analyzer() -> NumberPatternAnalyzer:
    """获取形态分析器全局实例"""
    global _pattern_analyzer
    if _pattern_analyzer is None:
        _pattern_analyzer = NumberPatternAnalyzer()
    return _pattern_analyzer
