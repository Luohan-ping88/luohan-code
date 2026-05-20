"""
优化模块集成接口
整合所有新优化的模块，提供统一的API
"""

from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd
from pathlib import Path
import logging

from .features.adaptive_selector import AdaptiveFeatureSelector, OnlineImportanceTracker
from .features.interaction_extractor import FeatureInteractionExtractor
from .models.context_weight_fusion import ContextAwareWeightFusion, ThompsonSamplingOptimizer
from .models.enhanced_stacking import EnhancedStackingEnsemble
from .models.tail_aware_copula import TailAwareCopula

logger = logging.getLogger(__name__)


class OptimizedPredictor:
    """
    优化后的预测器
    
    整合所有优化模块的完整预测流程
    """
    
    POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
    
    def __init__(
        self,
        enable_feature_optimization: bool = True,
        enable_weight_optimization: bool = True,
        enable_model_optimization: bool = True,
        config: Optional[Dict] = None
    ):
        self.config = config or {}
        
        self.enable_feature_optimization = enable_feature_optimization
        self.enable_weight_optimization = enable_weight_optimization
        self.enable_model_optimization = enable_model_optimization
        
        self.feature_selector: Optional[AdaptiveFeatureSelector] = None
        self.interaction_extractor: Optional[FeatureInteractionExtractor] = None
        self.importance_tracker: Optional[OnlineImportanceTracker] = None
        self.weight_fusion: Optional[ContextAwareWeightFusion] = None
        self.thompson_optimizer: Optional[ThompsonSamplingOptimizer] = None
        self.enhanced_stacking: Optional[EnhancedStackingEnsemble] = None
        self.tail_copula: Optional[TailAwareCopula] = None
        
        self._is_fitted = False
        self.selected_features: List[str] = []
        
        self._init_modules()
    
    def _init_modules(self):
        """初始化各优化模块"""
        if self.enable_feature_optimization:
            self.feature_selector = AdaptiveFeatureSelector(
                decay_factor=self.config.get('decay_factor', 0.95),
                min_importance=self.config.get('min_importance', 0.01),
                max_features_per_group=self.config.get('max_features_per_group', 3),
                warmup_periods=self.config.get('warmup_periods', 10)
            )
            
            self.interaction_extractor = FeatureInteractionExtractor(
                enable_position_cross=True,
                enable_temporal_cross=True,
                enable_frequency_cross=True,
                max_interaction_features=self.config.get('max_interaction_features', 50)
            )
            
            self.importance_tracker = OnlineImportanceTracker(
                n_positions=5,
                window_size=self.config.get('tracker_window', 100)
            )
            
            logger.info("特征优化模块初始化完成")
        
        if self.enable_weight_optimization:
            self.weight_fusion = ContextAwareWeightFusion(
                context_dim=self.config.get('context_dim', 32),
                history_window=self.config.get('history_window', 30),
                enable_online_update=True,
                confidence_temperature=self.config.get('confidence_temperature', 1.0)
            )
            
            self.thompson_optimizer = ThompsonSamplingOptimizer(
                model_names=['stacking', 'hmm', 'copula', 'bayesian', 'mamba']
            )
            
            logger.info("权重融合模块初始化完成")
        
        if self.enable_model_optimization:
            self.enhanced_stacking = EnhancedStackingEnsemble(
                diversity_threshold=self.config.get('diversity_threshold', 0.7),
                cv_folds=self.config.get('cv_folds', 5),
                enable_calibration=True
            )
            
            self.tail_copula = TailAwareCopula(
                copula_types=['gaussian', 't', 'gumbel'],
                enable_tail_boost=True,
                tail_threshold=0.1
            )
            
            logger.info("模型优化模块初始化完成")
    
    def fit(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        fit_stacking: bool = True,
        fit_copula: bool = True
    ):
        """
        训练优化后的预测器
        
        Args:
            df: 训练数据
            feature_cols: 基础特征列
            fit_stacking: 是否训练增强Stacking
            fit_copula: 是否训练尾部Copula
        """
        logger.info("开始训练优化预测器...")
        
        if self.enable_feature_optimization:
            df_enhanced = self.interaction_extractor.extract_all(df)
            
            interaction_cols = [
                c for c in df_enhanced.columns 
                if c not in df.columns and not c.startswith(('period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge'))
            ]
            
            all_features = feature_cols + interaction_cols
            
            self.selected_features = self.feature_selector.get_selected_features(
                all_features,
                min_count=20,
                max_count=100
            )
            
            logger.info(f"特征选择完成，选中 {len(self.selected_features)} 个特征")
        
        if fit_stacking and self.enhanced_stacking:
            self.enhanced_stacking.fit(df, self.selected_features)
            logger.info("增强Stacking训练完成")
        
        if fit_copula and self.tail_copula:
            copula_data = self._prepare_copula_data(df)
            if copula_data is not None:
                self.tail_copula.fit(copula_data)
                logger.info("尾部Copula训练完成")
        
        self._is_fitted = True
        logger.info("优化预测器训练完成")
    
    def _prepare_copula_data(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """准备Copula数据"""
        try:
            data = np.zeros((len(df), len(self.POSITIONS)))
            
            for i, pos in enumerate(self.POSITIONS):
                if pos in df.columns:
                    values = df[pos].values.astype(float)
                    values = np.clip(values, 0, 9.5)
                    data[:, i] = values / 9.0
            
            return data
        except Exception as e:
            logger.warning(f"Copula数据准备失败: {e}")
            return None
    
    def predict(
        self,
        df: pd.DataFrame,
        features: Optional[np.ndarray] = None,
        top_k: int = 8
    ) -> Dict[str, Dict[str, Any]]:
        """
        进行预测
        
        Returns:
            {位置: {top_k, probabilities, uncertainty, weights_used}}
        """
        if not self._is_fitted:
            raise ValueError("预测器尚未训练")
        
        results = {}
        
        if self.enhanced_stacking and features is not None:
            stacking_preds = self.enhanced_stacking.predict(features)
        else:
            stacking_preds = {}
        
        if self.tail_copula:
            copula_preds = self._predict_copula(df)
        else:
            copula_preds = {}
        
        for pos in self.POSITIONS:
            stacking_proba = stacking_preds.get(pos, np.ones(10) / 10)
            copula_proba = copula_preds.get(pos, np.ones(10) / 10)
            
            if self.weight_fusion:
                model_predictions = {
                    'stacking': stacking_proba,
                    'copula': copula_proba,
                    'hmm': np.ones(10) / 10,
                    'bayesian': np.ones(10) / 10,
                    'mamba': np.ones(10) / 10
                }
                
                fused_proba = self.weight_fusion.fuse_predictions(model_predictions)
            else:
                fused_proba = 0.6 * stacking_proba + 0.4 * copula_proba
                fused_proba = fused_proba / fused_proba.sum()
            
            uncertainty = self._compute_uncertainty(fused_proba)
            
            top_indices = np.argsort(fused_proba)[::-1][:top_k]
            top_k_digits = top_indices.tolist()
            top_k_probs = fused_proba[top_indices].tolist()
            
            results[pos] = {
                'top_k': top_k_digits,
                'probabilities': top_k_probs,
                'uncertainty': uncertainty,
                'weights_used': self.weight_fusion.current_weights if self.weight_fusion else None
            }
        
        return results
    
    def _predict_copula(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """使用Copula预测"""
        predictions = {}
        
        copula_data = self._prepare_copula_data(df)
        if copula_data is None or len(copula_data) < 10:
            for pos in self.POSITIONS:
                predictions[pos] = np.ones(10) / 10
            return predictions
        
        for i, pos in enumerate(self.POSITIONS):
            marginal = np.zeros(10)
            
            for j in range(10):
                u_val = (j + 0.5) / 10.0
                count = np.sum(copula_data[:, i] < u_val) / len(copula_data)
                marginal[j] = count
            
            marginal = marginal / (marginal.sum() + 1e-10)
            predictions[pos] = marginal
        
        return predictions
    
    def _compute_uncertainty(self, proba: np.ndarray) -> float:
        """计算预测不确定性"""
        entropy = -np.sum(proba * np.log(proba + 1e-10))
        max_entropy = np.log(10)
        return entropy / max_entropy
    
    def update_with_feedback(
        self,
        predictions: Dict[str, List[int]],
        actual: Dict[str, int]
    ):
        """基于反馈更新模型"""
        if self.importance_tracker:
            logger.info("更新特征重要性...")
        
        if self.weight_fusion and self.enhanced_stacking:
            self.weight_fusion.update_with_feedback(
                predictions={'stacking': predictions},
                actual=actual
            )
            
            self.thompson_optimizer.update({
                'stacking': actual.get('wan') in predictions.get('wan', [])[:3],
                'copula': actual.get('wan') in predictions.get('wan', [])[:3],
                'hmm': actual.get('wan') in predictions.get('wan', [])[:3],
            })
    
    def save(self, filepath: Path):
        """保存模型状态"""
        import pickle
        
        state = {
            'is_fitted': self._is_fitted,
            'selected_features': self.selected_features,
            'feature_selector': self.feature_selector,
            'weight_fusion': self.weight_fusion,
            'thompson_optimizer': self.thompson_optimizer,
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        
        logger.info(f"优化预测器状态已保存: {filepath}")
    
    def load(self, filepath: Path):
        """加载模型状态"""
        import pickle
        
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        self._is_fitted = state['is_fitted']
        self.selected_features = state['selected_features']
        self.feature_selector = state['feature_selector']
        self.weight_fusion = state['weight_fusion']
        self.thompson_optimizer = state['thompson_optimizer']
        
        logger.info(f"优化预测器状态已加载: {filepath}")
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """获取优化摘要"""
        summary = {
            'is_fitted': self._is_fitted,
            'selected_features_count': len(self.selected_features),
        }
        
        if self.feature_selector:
            summary['feature_groups'] = self.feature_selector.get_group_statistics()
        
        if self.weight_fusion:
            summary['model_weights'] = self.weight_fusion.get_performance_summary()
        
        if self.thompson_optimizer:
            summary['thompson_sampling'] = {
                'weights': {m: float(self.thompson_optimizer.sample_weights()[m]) 
                           for m in self.thompson_optimizer.model_names}
            }
        
        return summary
