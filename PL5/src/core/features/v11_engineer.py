"""
V11 增强版特征工程 - 集成先进特征与深度学习特征
向后兼容 V10，通过配置切换
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import logging
import time

from .engineer import FeatureEngineer
from .config import setup_logging, MODELS_DIR
from .advanced_features import AdvancedFeatureEngineering
from .comprehensive_features import ComprehensiveFeatureExtractor

try:
    from .deep_features import DeepFeatureExtractor, HAS_TORCH
    DEEP_FEATURES_AVAILABLE = HAS_TORCH
except (ImportError, NameError):
    DEEP_FEATURES_AVAILABLE = False
    HAS_TORCH = False

logger = setup_logging(__name__)

POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']


class V11FeatureEngineer:
    """
    V11 增强版特征工程

    整合：
    - V10 核心特征（向后兼容）
    - V11 先进特征（多尺度、频域、信息论、混沌等）
    - 深度学习特征（可选，需要PyTorch）
    - C++加速（可选）

    支持模式切换：
    - 'v10': 仅使用V10特征（默认，向后兼容）
    - 'v11_advanced': V10 + 先进特征
    - 'v11_full': V10 + 先进 + 深度学习（PyTorch需要）
    """

    V10_FEATURE_COUNT = 76  # V10特征数量

    def __init__(self, mode: str = 'v10', config=None):
        """
        Args:
            mode: 特征工程模式
                - 'v10': 仅V10特征（向后兼容）
                - 'v11_advanced': V10 + 先进特征
                - 'v11_full': V10 + 先进 + 深度学习
            config: 配置对象
        """
        self.mode = mode.lower()
        self.config = config
        
        # 验证模式
        valid_modes = ['v10', 'v11_advanced', 'v11_full']
        if self.mode not in valid_modes:
            logger.warning(f"无效模式 '{self.mode}'，默认使用 'v10'")
            self.mode = 'v10'

        # 初始化V10特征引擎
        self.v10_engineer = FeatureEngineer()
        
        # 初始化先进特征引擎
        self.advanced_engineer = None
        if self.mode in ['v11_advanced', 'v11_full']:
            try:
                use_cpp = getattr(config, 'use_cpp', True)
                self.advanced_engineer = AdvancedFeatureEngineering(use_cpp=use_cpp)
                logger.info("[V11] 先进特征工程已初始化")
            except Exception as e:
                logger.warning(f"[V11] 先进特征工程初始化失败: {e}")
                self.advanced_engineer = None

        # 初始化深度学习特征引擎
        self.deep_engineer = None
        self.deep_enabled = False
        if self.mode == 'v11_full' and DEEP_FEATURES_AVAILABLE:
            try:
                device = getattr(config, 'device', 'cpu')
                self.deep_engineer = DeepFeatureExtractor(device=device)
                self.deep_engineer.initialize()
                self.deep_enabled = True
                logger.info("[V11] 深度学习特征已初始化")
            except Exception as e:
                logger.warning(f"[V11] 深度学习特征初始化失败: {e}")
                self.deep_enabled = False

        logger.info(f"[V11] 特征工程初始化完成，模式: {self.mode}")

    def extract_all_features(
        self,
        df: pd.DataFrame,
        select_top: Optional[int] = None,
        feature_selection_method: str = 'rfe',
        enable_scaler: bool = False,
        detect_drift: bool = False,
        **kwargs
    ) -> pd.DataFrame:
        """
        提取所有特征（V11增强版）

        Args:
            df: 输入数据
            select_top: 特征选择Top N
            feature_selection_method: 特征选择方法
            enable_scaler: 是否启用标准化
            detect_drift: 是否启用漂移检测
            **kwargs: 其他参数

        Returns:
            包含特征的DataFrame
        """
        start_time = time.time()
        logger.info(f"[V11] 特征工程开始（模式: {self.mode}）...")

        # 先提取V10特征（确保向后兼容）
        result = self.v10_engineer.extract_all_features(
            df,
            select_top=select_top,
            feature_selection_method=feature_selection_method,
            enable_scaler=enable_scaler,
            detect_drift=detect_drift
        )

        # 添加V11先进特征
        if self.advanced_engineer and self.mode in ['v11_advanced', 'v11_full']:
            try:
                advanced_features = self.advanced_engineer.extract_all_features(df)
                result = self._merge_features(result, advanced_features, 'advanced')
                logger.info(f"[V11] 已添加先进特征: {len(advanced_features.columns)} 个")
            except Exception as e:
                logger.error(f"[V11] 添加先进特征失败: {e}")

        # 添加深度学习特征
        if self.deep_enabled and self.mode == 'v11_full':
            try:
                deep_features = self.deep_engineer.extract_features(df)
                result = self._merge_features(result, deep_features, 'deep')
                logger.info(f"[V11] 已添加深度学习特征: {len(deep_features.columns)} 个")
            except Exception as e:
                logger.error(f"[V11] 添加深度学习特征失败: {e}")

        duration = time.time() - start_time
        total_features = len([c for c in result.columns if c not in ['period', 'full_number'] + POSITIONS])
        logger.info(f"[V11] 特征工程完成: {total_features} 个特征, 耗时: {duration:.2f}s")

        return result

    def _merge_features(
        self,
        base_df: pd.DataFrame,
        extra_df: pd.DataFrame,
        prefix: str
    ) -> pd.DataFrame:
        """
        合并特征，避免列名冲突

        Args:
            base_df: 基础DataFrame
            extra_df: 要添加的特征DataFrame
            prefix: 前缀（用于冲突时重命名）

        Returns:
            合并后的DataFrame
        """
        base_cols = set(base_df.columns)
        extra_cols = set(extra_df.columns)
        
        result = base_df.copy()

        for col in extra_cols:
            if col in base_cols:
                if col not in ['period', 'full_number'] + POSITIONS:
                    new_col = f"{prefix}_{col}"
                    logger.warning(f"[V11] 列名冲突，重命名: {col} → {new_col}")
                    result[new_col] = extra_df[col]
            else:
                result[col] = extra_df[col]

        return result

    def get_feature_summary(self, features: pd.DataFrame) -> Dict[str, Any]:
        """获取特征摘要"""
        total_features = len([c for c in features.columns if c not in ['period', 'full_number'] + POSITIONS])
        
        v10_features = sum(1 for c in features.columns 
                          if not c.startswith(('advanced_', 'deep_', 'ms_', 'spectral_', 'gini_', 'prime_')))
        
        v11_features = total_features - v10_features

        return {
            'mode': self.mode,
            'total_features': total_features,
            'v10_features': v10_features,
            'v11_features': v11_features,
            'deep_features_enabled': self.deep_enabled
        }

    def fit_deep_model(self, df: pd.DataFrame, epochs: int = 10):
        """训练深度学习模型（可选）"""
        if self.deep_enabled and self.deep_engineer:
            self.deep_engineer.fit(df, epochs=epochs)
        else:
            logger.warning("[V11] 深度学习特征未启用或不可用")


def create_feature_engineer(use_v11: bool = False, mode: str = 'v10', config=None):
    """
    工厂函数：创建特征工程师

    Args:
        use_v11: 是否使用V11
        mode: V11模式
        config: 配置

    Returns:
        FeatureEngineer 或 V11FeatureEngineer 实例
    """
    if use_v11:
        return V11FeatureEngineer(mode=mode, config=config)
    else:
        return FeatureEngineer()
