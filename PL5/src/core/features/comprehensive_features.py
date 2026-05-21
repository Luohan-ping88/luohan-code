"""
PL5综合先进特征工程模块

统一管理所有先进特征提取：
1. 基础统计特征
2. 时序特征
3. 频域特征
4. 信息论特征
5. 混沌与分形特征
6. 深度学习特征
7. C++加速
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from pathlib import Path
import logging
import json
import hashlib

from .advanced_features import AdvancedFeatureEngineering, extract_advanced_features
from .config import setup_logging, MODELS_DIR

logger = setup_logging(__name__)

DEEP_FEATURES_AVAILABLE = False
DeepFeatureExtractor = None
extract_deep_features = None

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
    
    from .deep_features import DeepFeatureExtractor, extract_deep_features
    DEEP_FEATURES_AVAILABLE = True
except (ImportError, NameError) as e:
    HAS_TORCH = False
    logger.warning(f"深度学习特征不可用: {e}")


class ComprehensiveFeatureExtractor:
    """
    综合特征提取器
    
    整合所有先进特征提取方法，提供统一的特征提取接口
    """
    
    POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
    
    def __init__(
        self,
        enable_advanced: bool = True,
        enable_deep: bool = False,
        enable_cpp: bool = True,
        use_cache: bool = True,
        cache_dir: Optional[str] = None
    ):
        """
        Args:
            enable_advanced: 启用先进特征
            enable_deep: 启用深度学习特征
            enable_cpp: 启用C++加速
            use_cache: 使用特征缓存
            cache_dir: 缓存目录
        """
        self.enable_advanced = enable_advanced
        self.enable_deep = enable_deep and DEEP_FEATURES_AVAILABLE
        self.enable_cpp = enable_cpp
        self.use_cache = use_cache
        
        self.cache_dir = Path(cache_dir) if cache_dir else MODELS_DIR / "feature_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.advanced_extractor: Optional[AdvancedFeatureEngineering] = None
        self.deep_extractor = None
        
        self._initialize_extractors()
        
        self.cache: Dict[str, Any] = {}
    
    def _initialize_extractors(self):
        """初始化各特征提取器"""
        if self.enable_advanced:
            self.advanced_extractor = AdvancedFeatureEngineering(use_cpp=self.enable_cpp)
            logger.info("[ComprehensiveFeature] 先进特征提取器初始化完成")
        
        if self.enable_deep and DeepFeatureExtractor:
            try:
                self.deep_extractor = DeepFeatureExtractor()
                self.deep_extractor.initialize()
                logger.info("[ComprehensiveFeature] 深度学习特征提取器初始化完成")
            except Exception as e:
                logger.warning(f"[ComprehensiveFeature] 深度学习特征初始化失败: {e}")
                self.enable_deep = False
    
    def extract_all(
        self,
        df: pd.DataFrame,
        include_positions: bool = True,
        include_advanced: bool = True,
        include_deep: bool = False
    ) -> pd.DataFrame:
        """
        提取所有特征
        
        Args:
            df: 输入数据
            include_positions: 包含位置原始数据
            include_advanced: 包含先进特征
            include_deep: 包含深度学习特征
        
        Returns:
            包含所有特征的DataFrame
        """
        cache_key = self._compute_cache_key(df)
        
        if self.use_cache and cache_key in self.cache:
            logger.info(f"[ComprehensiveFeature] 使用缓存特征")
            return self.cache[cache_key]
        
        logger.info("[ComprehensiveFeature] 开始提取综合特征...")
        
        result = df.copy()
        
        if include_positions:
            result = self._add_position_features(result)
        
        if include_advanced and self.advanced_extractor:
            logger.info("[ComprehensiveFeature] 提取先进特征...")
            result = self.advanced_extractor.extract_all_features(result)
        
        if include_deep and self.enable_deep and self.deep_extractor:
            logger.info("[ComprehensiveFeature] 提取深度学习特征...")
            result = self.deep_extractor.extract_features(result)
        
        logger.info(f"[ComprehensiveFeature] 特征提取完成，共{len(result.columns)}个特征")
        
        if self.use_cache:
            self.cache[cache_key] = result
        
        return result
    
    def _add_position_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加位置基础特征"""
        result = df.copy()
        
        for pos in self.POSITIONS:
            result[f'{pos}_is_even'] = (df[pos] % 2 == 0).astype(int)
            result[f'{pos}_is_odd'] = (df[pos] % 2 == 1).astype(int)
            result[f'{pos}_is_small'] = (df[pos] < 5).astype(int)
            result[f'{pos}_is_large'] = (df[pos] >= 5).astype(int)
            result[f'{pos}_is_prime'] = df[pos].isin([2, 3, 5, 7]).astype(int)
        
        position_data = df[self.POSITIONS].values
        
        result['sum_all'] = position_data.sum(axis=1)
        result['product_all'] = np.clip(position_data.prod(axis=1), 0, 1e6)
        result['mean_all'] = position_data.mean(axis=1)
        result['std_all'] = position_data.std(axis=1)
        result['min_all'] = position_data.min(axis=1)
        result['max_all'] = position_data.max(axis=1)
        result['range_all'] = result['max_all'] - result['min_all']
        result['median_all'] = np.median(position_data, axis=1)
        
        for i, pos in enumerate(self.POSITIONS):
            for j in range(1, 4):
                shifted = df[pos].shift(j)
                result[f'{pos}_diff_{j}'] = df[pos] - shifted
                result[f'{pos}_pct_change_{j}'] = df[pos].pct_change(j)
        
        return result
    
    def _compute_cache_key(self, df: pd.DataFrame) -> str:
        """计算缓存键"""
        data_str = df[self.POSITIONS].tail(100).to_csv()
        hash_obj = hashlib.md5(data_str.encode())
        return hash_obj.hexdigest()
    
    def fit_deep_model(self, df: pd.DataFrame, epochs: int = 10):
        """训练深度学习模型"""
        if self.enable_deep and self.deep_extractor:
            logger.info(f"[ComprehensiveFeature] 训练深度学习模型，epochs={epochs}")
            self.deep_extractor.fit(df, epochs=epochs)
        else:
            logger.warning("[ComprehensiveFeature] 深度学习特征未启用")
    
    def get_feature_summary(self, features: pd.DataFrame) -> Dict[str, Any]:
        """
        获取特征摘要
        
        Args:
            features: 特征DataFrame
        
        Returns:
            特征摘要信息
        """
        return {
            'total_features': len(features.columns),
            'position_features': len([c for c in features.columns if any(p in c for p in self.POSITIONS)]),
            'advanced_features': len([c for c in features.columns if any(x in c for x in ['_ms_', '_freq_', '_entropy_', '_hurst_', '_lyapunov_'])]),
            'deep_features': len([c for c in features.columns if any(x in c for x in ['_ae_feat_', '_conv_feat_', '_attn_feat_'])])
        }
    
    def get_feature_importance(self, features: pd.DataFrame, target: np.ndarray) -> Dict[str, float]:
        """
        获取特征重要性（基于相关性）
        
        Args:
            features: 特征DataFrame
            target: 目标数组
        
        Returns:
            特征重要性字典
        """
        importance = {}
        
        for col in features.columns:
            if col in self.POSITIONS:
                continue
            
            try:
                corr = np.corrcoef(features[col].fillna(0), target)[0, 1]
                if not np.isnan(corr):
                    importance[col] = abs(corr)
            except:
                pass
        
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:50])
    
    def save_features(self, features: pd.DataFrame, filepath: str):
        """保存特征到文件"""
        features.to_parquet(filepath, index=False)
        logger.info(f"[ComprehensiveFeature] 特征已保存到: {filepath}")
    
    def load_features(self, filepath: str) -> pd.DataFrame:
        """从文件加载特征"""
        features = pd.read_parquet(filepath)
        logger.info(f"[ComprehensiveFeature] 特征已从: {filepath} 加载")
        return features
    
    def clear_cache(self):
        """清除缓存"""
        self.cache.clear()
        logger.info("[ComprehensiveFeature] 缓存已清除")


def extract_comprehensive_features(
    df: pd.DataFrame,
    enable_advanced: bool = True,
    enable_deep: bool = False,
    enable_cpp: bool = True
) -> pd.DataFrame:
    """
    便捷函数：提取综合特征
    
    Args:
        df: 输入数据
        enable_advanced: 启用先进特征
        enable_deep: 启用深度学习特征
        enable_cpp: 启用C++加速
    
    Returns:
        包含综合特征的DataFrame
    """
    extractor = ComprehensiveFeatureExtractor(
        enable_advanced=enable_advanced,
        enable_deep=enable_deep,
        enable_cpp=enable_cpp
    )
    
    return extractor.extract_all(df)
