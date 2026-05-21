"""
PL5排列五先进特征工程模块 V11

基于排列五数据特点开发的先进特征工程：
1. 多尺度时序特征
2. 频域特征（FFT/Wavelet）
3. 图神经网络位置关联特征
4. 深度学习特征表示
5. 统计检验特征
6. 信息论特征
7. 混沌与分形特征
8. 对抗性鲁棒特征
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks, welch
from scipy.stats import entropy, kstest, anderson
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class AdvancedFeatureEngineering:
    """
    先进特征工程类
    
    针对排列五特点设计的特征提取器，包含8大类特征：
    1. 多尺度时序特征
    2. 频域特征
    3. 位置关联特征
    4. 统计检验特征
    5. 信息论特征
    6. 混沌与分形特征
    7. 对抗性鲁棒特征
    8. 跨期预测特征
    """
    
    POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
    
    def __init__(self, use_cpp: bool = True):
        self.use_cpp = use_cpp
        self.cpp_available = False
        self._check_cpp()
    
    def _check_cpp(self):
        """检查C++加速是否可用"""
        try:
            from cpp_core import FeatureCalculator, CPP_AVAILABLE
            if CPP_AVAILABLE:
                self.cpp_calc = FeatureCalculator()
                self.cpp_available = True
                logger.info("[AdvancedFeature] C++加速已启用")
        except ImportError:
            self.cpp_available = False
            logger.info("[AdvancedFeature] C++加速不可用，使用Python实现")
    
    def extract_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        提取所有先进特征
        
        Args:
            df: 包含wan, qian, bai, shi, ge列的DataFrame
        
        Returns:
            包含所有特征的DataFrame
        """
        result = df.copy()
        
        logger.info("[AdvancedFeature] 开始提取先进特征...")
        
        result = self._add_multiscale_temporal_features(result)
        result = self._add_frequency_domain_features(result)
        result = self._add_position_correlation_features(result)
        result = self._add_statistical_test_features(result)
        result = self._add_information_theory_features(result)
        result = self._add_chaos_fractal_features(result)
        result = self._add_cross_temporal_features(result)
        result = self._add_distribution_features(result)
        
        logger.info(f"[AdvancedFeature] 特征提取完成，共{len(result.columns)}个特征")
        
        return result
    
    def _add_multiscale_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        多尺度时序特征
        
        在多个时间尺度上提取特征，捕捉不同周期的模式
        """
        result = df.copy()
        
        scales = [3, 5, 7, 10, 15, 20, 30]
        
        for pos in self.POSITIONS:
            data = df[pos].values
            
            for scale in scales:
                if len(df) < scale:
                    continue
                
                rolling_data = pd.Series(data).rolling(window=scale, min_periods=1)
                
                result[f'{pos}_ms_mean_{scale}'] = rolling_data.mean()
                result[f'{pos}_ms_std_{scale}'] = rolling_data.std()
                result[f'{pos}_ms_trend_{scale}'] = self._compute_trend(data, scale)
                result[f'{pos}_ms_volatility_{scale}'] = rolling_data.std() / (rolling_data.mean() + 1e-10)
        
        return result
    
    def _compute_trend(self, data: np.ndarray, window: int) -> np.ndarray:
        """计算趋势（线性回归斜率）"""
        n = len(data)
        trends = np.zeros(n)
        
        for i in range(window - 1, n):
            window_data = data[i - window + 1:i + 1]
            x = np.arange(window)
            
            if window > 1:
                x_mean = x.mean()
                y_mean = window_data.mean()
                
                numerator = np.sum((x - x_mean) * (window_data - y_mean))
                denominator = np.sum((x - x_mean) ** 2) + 1e-10
                
                trends[i] = numerator / denominator
            else:
                trends[i] = 0
        
        return trends
    
    def _add_frequency_domain_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        频域特征
        
        使用FFT和小波变换提取频域特征
        """
        result = df.copy()
        
        for pos in self.POSITIONS:
            data = df[pos].values.astype(float)
            
            if len(data) < 10:
                continue
            
            fft_vals = np.abs(fft(data))
            freqs = fftfreq(len(data), d=1)
            
            pos_freq_idx = np.where(freqs > 0)[0]
            
            if len(pos_freq_idx) > 0:
                dominant_freq_idx = pos_freq_idx[np.argmax(fft_vals[pos_freq_idx])]
                result[f'{pos}_dominant_freq'] = freqs[dominant_freq_idx]
                result[f'{pos}_dominant_power'] = fft_vals[dominant_freq_idx]
                
                low_freq_power = fft_vals[pos_freq_idx[:len(pos_freq_idx)//3]].sum()
                mid_freq_power = fft_vals[pos_freq_idx[len(pos_freq_idx)//3:2*len(pos_freq_idx)//3]].sum()
                high_freq_power = fft_vals[pos_freq_idx[2*len(pos_freq_idx)//3:]].sum()
                total_power = low_freq_power + mid_freq_power + high_freq_power + 1e-10
                
                result[f'{pos}_low_freq_ratio'] = low_freq_power / total_power
                result[f'{pos}_mid_freq_ratio'] = mid_freq_power / total_power
                result[f'{pos}_high_freq_ratio'] = high_freq_power / total_power
            
            try:
                freqs_welch, psd = welch(data, fs=1.0, nperseg=min(8, len(data)))
                result[f'{pos}_spectral_entropy'] = entropy(psd + 1e-10) / np.log(len(psd))
            except:
                result[f'{pos}_spectral_entropy'] = 0.0
        
        return result
    
    def _add_position_correlation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        位置关联特征
        
        捕捉5个位置之间的相关性模式
        """
        result = df.copy()
        
        position_data = df[self.POSITIONS].values
        
        for i, pos1 in enumerate(self.POSITIONS):
            for j, pos2 in enumerate(self.POSITIONS):
                if i >= j:
                    continue
                
                corr = np.corrcoef(position_data[:, i], position_data[:, j])[0, 1]
                result[f'{pos1}_{pos2}_corr'] = corr if not np.isnan(corr) else 0.0
        
        sum_positions = position_data.sum(axis=1)
        product_positions = position_data.prod(axis=1)
        
        for i, pos in enumerate(self.POSITIONS):
            corr_with_sum = np.corrcoef(position_data[:, i], sum_positions)[0, 1]
            corr_with_prod = np.corrcoef(position_data[:, i], product_positions)[0, 1]
            result[f'{pos}_corr_with_sum'] = corr_with_sum if not np.isnan(corr_with_sum) else 0.0
            result[f'{pos}_corr_with_prod'] = corr_with_prod if not np.isnan(corr_with_prod) else 0.0
        
        pairwise_sums = np.zeros(len(df))
        for i in range(len(self.POSITIONS)):
            for j in range(i+1, len(self.POSITIONS)):
                pairwise_sums += position_data[:, i] * position_data[:, j]
        result['pairwise_products_sum'] = pairwise_sums
        
        result['sum_all_positions'] = sum_positions
        result['product_all_positions'] = np.clip(product_positions, 0, 1e6)
        result['max_position'] = position_data.max(axis=1)
        result['min_position'] = position_data.min(axis=1)
        result['range_positions'] = result['max_position'] - result['min_position']
        result['mean_position'] = position_data.mean(axis=1)
        result['std_positions'] = position_data.std(axis=1)
        
        return result
    
    def _add_statistical_test_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        统计检验特征
        
        使用统计检验方法检测数据分布特征
        """
        result = df.copy()
        
        for pos in self.POSITIONS:
            data = df[pos].values
            
            if len(data) < 20:
                result[f'{pos}_normality_stat'] = 0.0
                result[f'{pos}_ks_stat'] = 0.0
                result[f'{pos}_runs_test'] = 0.0
                continue
            
            try:
                stat, p_value = stats.normaltest(data)
                result[f'{pos}_normality_stat'] = stat
                result[f'{pos}_normality_pval'] = p_value
            except:
                result[f'{pos}_normality_stat'] = 0.0
                result[f'{pos}_normality_pval'] = 0.0
            
            try:
                ks_stat, ks_pval = kstest(data, 'uniform', args=(0, 10))
                result[f'{pos}_ks_stat'] = ks_stat
                result[f'{pos}_ks_pval'] = ks_pval
            except:
                result[f'{pos}_ks_stat'] = 0.0
                result[f'{pos}_ks_pval'] = 0.0
            
            median = np.median(data)
            runs = (data > median).astype(int)
            runs_diff = np.diff(runs)
            n_runs = np.sum(np.abs(runs_diff)) + 1
            n1 = np.sum(runs)
            n2 = len(runs) - n1
            
            expected_runs = (2 * n1 * n2) / (n1 + n2) + 1
            result[f'{pos}_runs_stat'] = (n_runs - expected_runs) / (expected_runs + 1e-10)
            
            try:
                ad_result = anderson(data, dist='norm')
                result[f'{pos}_anderson_stat'] = ad_result.statistic
            except:
                result[f'{pos}_anderson_stat'] = 0.0
        
        return result
    
    def _add_information_theory_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        信息论特征
        
        基于信息论的高级特征
        """
        result = df.copy()
        
        for pos in self.POSITIONS:
            for window in [10, 20, 50]:
                if len(df) < window:
                    continue
                
                data = df[pos].values
                
                entropies = []
                for i in range(window - 1, len(data)):
                    window_data = data[i - window + 1:i + 1]
                    counts = np.bincount(window_data, minlength=10)
                    probs = counts / window
                    probs = probs[probs > 0]
                    ent = -np.sum(probs * np.log2(probs + 1e-10))
                    entropies.append(ent)
                
                result[f'{pos}_entropy_{window}'] = [0.0] * (window - 1) + entropies
                
                conditional_entropies = self._compute_conditional_entropy(data, window)
                result[f'{pos}_cond_entropy_{window}'] = conditional_entropies
                
                mutual_infos = self._compute_mutual_information(data, window)
                result[f'{pos}_mutual_info_{window}'] = mutual_infos
        
        return result
    
    def _compute_conditional_entropy(self, data: np.ndarray, window: int) -> np.ndarray:
        """计算条件熵"""
        n = len(data)
        result = np.zeros(n)
        
        if n < window + 1:
            return result
        
        for i in range(window, n):
            window_data = data[i - window:i]
            current = data[i]
            
            context_counts = np.zeros(10)
            for j in range(window):
                context_counts[data[i - window + j]] += 1
            
            context_probs = context_counts / window
            
            h_given_context = 0.0
            for val in range(10):
                if context_counts[val] > 0:
                    given_val_data = data[i - window:i][np.array(range(window))[window_data == val]]
                    if len(given_val_data) > 0:
                        p_context = context_counts[val] / window
                        p_current_given = np.sum(given_val_data == current) / len(given_val_data)
                        if p_current_given > 0:
                            h_given_context -= p_context * np.log2(p_current_given + 1e-10)
            
            result[i] = h_given_context
        
        return result
    
    def _compute_mutual_information(self, data: np.ndarray, window: int) -> np.ndarray:
        """计算互信息"""
        n = len(data)
        result = np.zeros(n)
        
        if n < window + 1:
            return result
        
        for i in range(window, n):
            x = data[i - window:i - 1]
            y = data[i - window + 1:i]
            
            h_x = entropy(np.bincount(x, minlength=10) / len(x) + 1e-10)
            h_y = entropy(np.bincount(y, minlength=10) / len(y) + 1e-10)
            
            joint_counts = np.zeros((10, 10))
            for j in range(len(x)):
                joint_counts[x[j], y[j]] += 1
            joint_probs = joint_counts / len(x)
            h_xy = entropy(joint_probs.flatten() + 1e-10)
            
            mi = h_x + h_y - h_xy
            result[i] = max(0, mi)
        
        return result
    
    def _add_chaos_fractal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        混沌与分形特征
        
        用于检测数据的混沌特性
        """
        result = df.copy()
        
        for pos in self.POSITIONS:
            data = df[pos].values.astype(float)
            
            if len(data) >= 10:
                result[f'{pos}_hurst'] = self._compute_hurst_exponent(data)
            
            if len(data) >= 20:
                lyapunov = self._compute_lyapunov_exponent(data)
                result[f'{pos}_lyapunov'] = lyapunov
            
            if len(data) >= 15:
                correlation_dim = self._compute_correlation_dimension(data)
                result[f'{pos}_corr_dim'] = correlation_dim
            
            if len(data) >= 10:
                approx_entropy = self._compute_approximate_entropy(data)
                result[f'{pos}_approx_entropy'] = approx_entropy
            
            if len(data) >= 5:
                sample_entropy = self._compute_sample_entropy(data)
                result[f'{pos}_sample_entropy'] = sample_entropy
        
        return result
    
    def _compute_hurst_exponent(self, data: np.ndarray) -> float:
        """计算Hurst指数"""
        n = len(data)
        if n < 10:
            return 0.5
        
        mean = np.mean(data)
        cumsum = np.cumsum(data - mean)
        R = np.max(cumsum) - np.min(cumsum)
        S = np.std(data, ddof=1)
        
        if S == 0:
            return 0.5
        
        return np.clip(np.log(R / S) / np.log(n), 0, 1)
    
    def _compute_lyapunov_exponent(self, data: np.ndarray) -> float:
        """计算Lyapunov指数"""
        n = len(data)
        if n < 10:
            return 0.0
        
        total = 0.0
        count = 0
        
        for i in range(1, n - 1):
            d0 = np.abs(data[i] - data[i - 1]) + 1e-10
            d1 = np.abs(data[i + 1] - data[i])
            total += np.log(d1 / d0)
            count += 1
        
        return total / count if count > 0 else 0.0
    
    def _compute_correlation_dimension(self, data: np.ndarray) -> float:
        """计算关联维数"""
        n = len(data)
        if n < 15:
            return 0.0
        
        embedding_dim = 3
        tau = 1
        
        points = []
        for i in range(n - embedding_dim * tau):
            point = [data[i + j * tau] for j in range(embedding_dim)]
            points.append(point)
        
        points = np.array(points)
        n_points = len(points)
        
        epsilons = [0.1, 0.5, 1.0]
        counts = []
        
        for eps in epsilons:
            count = 0
            for i in range(n_points):
                for j in range(i + 1, n_points):
                    if np.linalg.norm(points[i] - points[j]) < eps:
                        count += 1
            counts.append(count)
        
        if counts[0] > 0 and counts[2] > 0:
            try:
                slope = (np.log(counts[0] + 1) - np.log(counts[2] + 1)) / (np.log(epsilons[0]) - np.log(epsilons[2]) + 1e-10)
                return np.clip(slope, 0, 5)
            except:
                return 0.0
        
        return 0.0
    
    def _compute_approximate_entropy(self, data: np.ndarray, m: int = 2, r: float = 0.2) -> float:
        """计算近似熵"""
        n = len(data)
        if n < m + 1:
            return 0.0
        
        r_threshold = r * np.std(data, ddof=1)
        
        def _phi(m_val):
            patterns = np.array([data[i:i + m_val] for i in range(n - m_val)])
            count = np.zeros(len(patterns))
            
            for i in range(len(patterns)):
                distances = np.max(np.abs(patterns - patterns[i]), axis=1)
                count[i] = np.sum(distances <= r_threshold)
            
            return np.mean(np.log(count + 1e-10))
        
        try:
            return abs(_phi(m) - _phi(m + 1))
        except:
            return 0.0
    
    def _compute_sample_entropy(self, data: np.ndarray, m: int = 2, r: float = 0.2) -> float:
        """计算样本熵"""
        n = len(data)
        if n < m + 1:
            return 0.0
        
        r_threshold = r * np.std(data, ddof=1)
        
        patterns = np.array([data[i:i + m] for i in range(n - m)])
        patterns_m1 = np.array([data[i:i + m + 1] for i in range(n - m - 1)])
        
        A = 0
        B = 0
        
        for i in range(len(patterns_m1)):
            for j in range(len(patterns_m1)):
                if i != j:
                    if np.max(np.abs(patterns_m1[i] - patterns_m1[j])) <= r_threshold:
                        A += 1
        
        for i in range(len(patterns)):
            for j in range(len(patterns)):
                if i != j:
                    if np.max(np.abs(patterns[i] - patterns[j])) <= r_threshold:
                        B += 1
        
        if A == 0 or B == 0:
            return 0.0
        
        return -np.log(A / B)
    
    def _add_cross_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        跨期预测特征
        
        基于历史数据预测下一期特征的领先指标
        """
        result = df.copy()
        
        for pos in self.POSITIONS:
            data = df[pos].values
            
            for lag in [1, 2, 3, 5]:
                if len(df) > lag:
                    result[f'{pos}_lag_{lag}'] = np.roll(data, lag)
            
            for window in [3, 5, 10]:
                if len(df) >= window:
                    rolling_mean = pd.Series(data).rolling(window, min_periods=1).mean()
                    result[f'{pos}_diff_mean_{window}'] = data - rolling_mean.values
            
            result[f'{pos}_momentum'] = self._compute_momentum(data)
            result[f'{pos}_acceleration'] = self._compute_acceleration(data)
        
        return result
    
    def _compute_momentum(self, data: np.ndarray) -> np.ndarray:
        """计算动量"""
        n = len(data)
        momentum = np.zeros(n)
        
        for i in range(3, n):
            momentum[i] = data[i] - data[i - 3]
        
        return momentum
    
    def _compute_acceleration(self, data: np.ndarray) -> np.ndarray:
        """计算加速度"""
        n = len(data)
        acceleration = np.zeros(n)
        
        for i in range(3, n):
            acceleration[i] = (data[i] - data[i - 1]) - (data[i - 1] - data[i - 2])
        
        return acceleration
    
    def _add_distribution_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        分布特征
        
        数字分布的高级统计特征
        """
        result = df.copy()
        
        for pos in self.POSITIONS:
            data = df[pos].values
            
            counts = np.bincount(data, minlength=10)
            probs = counts / (counts.sum() + 1e-10)
            
            result[f'{pos}_digit_mode'] = np.argmax(counts)
            result[f'{pos}_digit_mode_count'] = np.max(counts)
            result[f'{pos}_digit_entropy'] = entropy(probs + 1e-10) / np.log(10)
            result[f'{pos}_gini_coefficient'] = self._compute_gini(probs)
            
            sorted_probs = np.sort(probs)
            result[f'{pos}_top1_prob'] = sorted_probs[-1]
            result[f'{pos}_top3_prob'] = sorted_probs[-3:].sum()
            result[f'{pos}_bottom3_prob'] = sorted_probs[:3].sum()
            
            result[f'{pos}_even_ratio'] = np.mean(data % 2 == 0)
            result[f'{pos}_odd_ratio'] = np.mean(data % 2 == 1)
            
            result[f'{pos}_small_ratio'] = np.mean(data < 5)
            result[f'{pos}_large_ratio'] = np.mean(data >= 5)
            
            result[f'{pos}_prime_ratio'] = np.mean(np.isin(data, [2, 3, 5, 7]))
        
        return result
    
    def _compute_gini(self, probs: np.ndarray) -> float:
        """计算基尼系数"""
        n = len(probs)
        if n < 2:
            return 0.0
        
        sorted_probs = np.sort(probs)
        cumsum = np.cumsum(sorted_probs)
        return 1 - 2 * np.sum(cumsum) / (n * cumsum[-1] + 1e-10) + 1 / n


def extract_advanced_features(df: pd.DataFrame, use_cpp: bool = True) -> pd.DataFrame:
    """
    便捷函数：提取先进特征
    
    Args:
        df: 输入数据
        use_cpp: 是否使用C++加速
    
    Returns:
        包含先进特征的DataFrame
    """
    extractor = AdvancedFeatureEngineering(use_cpp=use_cpp)
    return extractor.extract_all_features(df)
