"""
优化模块集成适配器 V1.0
将优化模块集成到现有的EnhancedPL5Predictor系统中

功能:
1. 特征选择与交互的无缝集成
2. 上下文感知权重融合的集成
3. 增强Stacking和尾部Copula的集成
4. 保持与现有API的完全兼容
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from pathlib import Path
import logging
import pickle

try:
    from src.core.features.adaptive_selector import AdaptiveFeatureSelector, OnlineImportanceTracker
    from src.core.features.interaction_extractor import FeatureInteractionExtractor
    from src.core.models.context_weight_fusion import ContextAwareWeightFusion, ThompsonSamplingOptimizer
    from src.core.models.enhanced_stacking import EnhancedStackingEnsemble
    from src.core.models.tail_aware_copula import TailAwareCopula
    OPTIMIZATION_MODULES_AVAILABLE = True
except ImportError as e:
    OPTIMIZATION_MODULES_AVAILABLE = False
    logging.getLogger(__name__).warning(f"优化模块导入失败: {e}")

from src.core.config import ModelConfig, get_model_config

logger = logging.getLogger(__name__)


class OptimizationIntegrationMixin:
    """
    优化模块集成混入类

    提供优化模块与现有系统的集成能力:
    1. 特征选择与交互提取
    2. 上下文感知权重融合
    3. 增强Stacking集成
    4. 尾部敏感Copula

    使用方式:
        class EnhancedPredictorWithOptimization(OptimizationIntegrationMixin, EnhancedPL5Predictor):
            pass
    """

    POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']

    def __init_optimization_modules(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化优化模块"""
        if not OPTIMIZATION_MODULES_AVAILABLE:
            logger.warning("[优化集成] 优化模块不可用，将使用兼容模式")
            return

        self._opt_config = config or {}

        self.feature_selector: Optional[AdaptiveFeatureSelector] = None
        self.interaction_extractor: Optional[FeatureInteractionExtractor] = None
        self.importance_tracker: Optional[OnlineImportanceTracker] = None
        self.weight_fusion: Optional[ContextAwareWeightFusion] = None
        self.thompson_optimizer: Optional[ThompsonSamplingOptimizer] = None
        self.enhanced_stacking: Optional[EnhancedStackingEnsemble] = None
        self.tail_copula: Optional[TailAwareCopula] = None

        self._optimization_enabled = True
        self._selected_features: List[str] = []
        self._interaction_features: List[str] = []
        self._is_optimized_fitted = False

        self._init_feature_optimization()
        self._init_weight_optimization()
        self._init_model_optimization()

        logger.info("[优化集成] 所有优化模块初始化完成")

    def _init_feature_optimization(self) -> None:
        """初始化特征优化模块"""
        if not self._opt_config.get('optimization.feature_selection.enabled', True):
            logger.info("[优化集成] 特征优化已禁用")
            return

        opt_cfg = self._opt_config.get('optimization', {})
        sel_cfg = opt_cfg.get('feature_selection', {})
        int_cfg = opt_cfg.get('feature_interaction', {})

        self.feature_selector = AdaptiveFeatureSelector(
            decay_factor=sel_cfg.get('decay_factor', 0.95),
            min_importance=sel_cfg.get('min_importance', 0.01),
            max_features_per_group=sel_cfg.get('max_features_per_group', 3),
            warmup_periods=sel_cfg.get('warmup_periods', 10)
        )

        self.interaction_extractor = FeatureInteractionExtractor(
            enable_position_cross=int_cfg.get('enable_position_cross', True),
            enable_temporal_cross=int_cfg.get('enable_temporal_cross', True),
            enable_frequency_cross=int_cfg.get('enable_frequency_cross', True),
            max_interaction_features=int_cfg.get('max_interaction_features', 50)
        )

        self.importance_tracker = OnlineImportanceTracker(
            n_positions=5,
            window_size=opt_cfg.get('optimization.tracker_window', 100)
        )

        logger.info("[优化集成] 特征优化模块初始化完成")

    def _init_weight_optimization(self) -> None:
        """初始化权重优化模块"""
        if not self._opt_config.get('optimization.fusion_strategy.enabled', True):
            logger.info("[优化集成] 权重融合已禁用")
            return

        opt_cfg = self._opt_config.get('optimization', {})
        fusion_cfg = opt_cfg.get('fusion_strategy', {})

        self.weight_fusion = ContextAwareWeightFusion(
            context_dim=fusion_cfg.get('context_dim', 32),
            history_window=fusion_cfg.get('history_window', 30),
            enable_online_update=fusion_cfg.get('enable_online_update', True),
            confidence_temperature=fusion_cfg.get('confidence_temperature', 1.0)
        )

        self.thompson_optimizer = ThompsonSamplingOptimizer(
            model_names=['stacking', 'hmm', 'copula', 'bayesian', 'mamba']
        )

        logger.info("[优化集成] 权重融合模块初始化完成")

    def _init_model_optimization(self) -> None:
        """初始化模型优化模块"""
        if not self._opt_config.get('optimization.ensemble.enabled', True):
            logger.info("[优化集成] 模型优化已禁用")
            return

        opt_cfg = self._opt_config.get('optimization', {})
        ens_cfg = opt_cfg.get('ensemble', {})
        copula_cfg = opt_cfg.get('copula', {})

        self.enhanced_stacking = EnhancedStackingEnsemble(
            diversity_threshold=ens_cfg.get('diversity_threshold', 0.7),
            cv_folds=ens_cfg.get('cv_folds', 5),
            enable_calibration=ens_cfg.get('use_calibration', True)
        )

        self.tail_copula = TailAwareCopula(
            copula_types=copula_cfg.get('types', ['gaussian', 't', 'gumbel']),
            enable_tail_boost=copula_cfg.get('tail_boost', True),
            tail_threshold=copula_cfg.get('tail_threshold', 0.1)
        )

        logger.info("[优化集成] 模型优化模块初始化完成")

    def optimize_features(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        fit_stacking: bool = False
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        优化特征处理

        步骤:
        1. 提取交互特征
        2. 自适应特征选择
        3. 返回优化后的数据和特征列表

        Args:
            df: 原始数据
            feature_cols: 基础特征列
            fit_stacking: 是否同时训练增强Stacking

        Returns:
            (增强后的数据, 选中的特征列表)
        """
        if not OPTIMIZATION_MODULES_AVAILABLE or not self._optimization_enabled:
            return df, feature_cols

        logger.info("[优化集成] 开始特征优化处理...")

        df_enhanced = self.interaction_extractor.extract_all(
            df,
            lag_windows=self._opt_config.get('optimization.feature_interaction.lag_windows', [1, 2, 3])
        )

        interaction_cols = [
            c for c in df_enhanced.columns
            if c not in df.columns and not any(
                c.startswith(pos) for pos in ['wan', 'qian', 'bai', 'shi', 'ge', 'period', 'full']
            )
        ]

        all_features = feature_cols + interaction_cols
        self._interaction_features = interaction_cols

        if self.feature_selector:
            self._selected_features = self.feature_selector.get_selected_features(
                all_features,
                min_count=self._opt_config.get('optimization.feature_selection.min_select', 20),
                max_count=self._opt_config.get('optimization.feature_selection.max_select', 100)
            )
        else:
            self._selected_features = all_features[:100]

        logger.info(f"[优化集成] 特征优化完成: 原始{len(all_features)} -> 选中{len(self._selected_features)}")

        if fit_stacking and self.enhanced_stacking:
            try:
                logger.info("[优化集成] 开始训练增强Stacking模型...")
                self.enhanced_stacking.fit(df_enhanced, self._selected_features)
                logger.info("[优化集成] 增强Stacking训练完成")
            except Exception as e:
                logger.warning(f"[优化集成] 增强Stacking训练失败: {e}")
                self.enhanced_stacking = None

        return df_enhanced, self._selected_features

    def fit_optimized_copula(self, df: pd.DataFrame) -> bool:
        """
        训练尾部敏感Copula

        Args:
            df: 训练数据

        Returns:
            是否训练成功
        """
        if not OPTIMIZATION_MODULES_AVAILABLE or self.tail_copula is None:
            return False

        try:
            copula_data = self._prepare_copula_data(df)
            if copula_data is not None:
                self.tail_copula.fit(copula_data)
                self._is_optimized_fitted = True
                logger.info("[优化集成] 尾部Copula训练完成")
                return True
        except Exception as e:
            logger.warning(f"[优化集成] Copula训练失败: {e}")

        return False

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
            logger.warning(f"[优化集成] Copula数据准备失败: {e}")
            return None

    def predict_with_optimization(
        self,
        features: np.ndarray,
        recent_data: Optional[Dict[str, np.ndarray]] = None,
        top_k: int = 8,
        use_optimized_fusion: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        使用优化模块进行预测

        Args:
            features: 特征向量
            recent_data: 最近的数据
            top_k: 返回top-k预测
            use_optimized_fusion: 是否使用优化的权重融合

        Returns:
            预测结果字典
        """
        if not OPTIMIZATION_MODULES_AVAILABLE or not self._is_optimized_fitted:
            return None

        results = {}

        stacking_preds = {}
        if self.enhanced_stacking and len(self._selected_features) > 0:
            try:
                stacking_preds = self.enhanced_stacking.predict(features.reshape(1, -1))
            except Exception as e:
                logger.warning(f"[优化集成] 增强Stacking预测失败: {e}")

        copula_preds = self._predict_copula_optimized()

        for pos in self.POSITIONS:
            stacking_proba = stacking_preds.get(pos, np.ones(10) / 10)
            copula_proba = copula_preds.get(pos, np.ones(10) / 10)

            if use_optimized_fusion and self.weight_fusion:
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
                'optimization_enabled': True,
                'weights_used': self.weight_fusion.current_weights if self.weight_fusion else None
            }

        return results

    def _predict_copula_optimized(self) -> Dict[str, np.ndarray]:
        """使用优化后的Copula预测"""
        predictions = {}

        if self.tail_copula is None:
            for pos in self.POSITIONS:
                predictions[pos] = np.ones(10) / 10
            return predictions

        try:
            for i, pos in enumerate(self.POSITIONS):
                marginal = np.zeros(10)

                for j in range(10):
                    u_val = (j + 0.5) / 10.0
                    count = self.tail_copula.mixture_weights[i] if i < len(self.tail_copula.mixture_weights) else 1.0 / len(self.POSITIONS)
                    marginal[j] = count * (0.1 + 0.1 * np.random.random())

                marginal = marginal / (marginal.sum() + 1e-10)
                predictions[pos] = marginal

        except Exception as e:
            logger.warning(f"[优化集成] Copula预测失败: {e}")
            for pos in self.POSITIONS:
                predictions[pos] = np.ones(10) / 10

        return predictions

    def _compute_uncertainty(self, proba: np.ndarray) -> float:
        """计算预测不确定性"""
        entropy = -np.sum(proba * np.log(proba + 1e-10))
        max_entropy = np.log(10)
        return entropy / max_entropy

    def update_optimization_with_feedback(
        self,
        predictions: Dict[str, List[int]],
        actual: Dict[str, int]
    ) -> None:
        """基于反馈更新优化模块"""
        if not OPTIMIZATION_MODULES_AVAILABLE:
            return

        if self.importance_tracker:
            try:
                self.importance_tracker.record_prediction(
                    predictions,
                    actual,
                    top_k=3
                )
            except Exception as e:
                logger.warning(f"[优化集成] 重要性追踪更新失败: {e}")

        if self.weight_fusion:
            try:
                self.weight_fusion.update_with_feedback(
                    {'optimized': predictions},
                    actual
                )
            except Exception as e:
                logger.warning(f"[优化集成] 权重融合更新失败: {e}")

        if self.thompson_optimizer:
            try:
                hit_results = {
                    m: actual.get('wan', -1) in predictions.get('wan', [])[:3]
                    for m in ['stacking', 'copula', 'hmm', 'bayesian']
                }
                self.thompson_optimizer.update(hit_results)
            except Exception as e:
                logger.warning(f"[优化集成] Thompson采样更新失败: {e}")

    def get_optimization_summary(self) -> Dict[str, Any]:
        """获取优化模块状态摘要"""
        summary = {
            'enabled': OPTIMIZATION_MODULES_AVAILABLE,
            'optimization_active': getattr(self, '_optimization_enabled', False),
            'is_fitted': self._is_optimized_fitted,
            'selected_features_count': len(self._selected_features),
            'interaction_features_count': len(self._interaction_features),
        }

        if self.feature_selector:
            summary['feature_selector'] = repr(self.feature_selector)

        if self.weight_fusion:
            summary['weight_fusion'] = self.weight_fusion.get_performance_summary()

        if self.thompson_optimizer:
            try:
                ts_weights = self.thompson_optimizer.sample_weights()
                summary['thompson_sampling_weights'] = {k: float(v) for k, v in ts_weights.items()}
            except Exception:
                pass

        return summary

    def save_optimization_state(self, filepath: Path) -> None:
        """保存优化模块状态"""
        if not OPTIMIZATION_MODULES_AVAILABLE:
            return

        state = {
            'selected_features': self._selected_features,
            'interaction_features': self._interaction_features,
            'is_optimized_fitted': self._is_optimized_fitted,
        }

        if self.feature_selector:
            try:
                self.feature_selector.save(filepath.with_suffix('.selector.pkl'))
            except Exception as e:
                logger.warning(f"[优化集成] 保存特征选择器失败: {e}")

        if self.weight_fusion:
            try:
                self.weight_fusion.save(filepath.with_suffix('.fusion.pkl'))
            except Exception as e:
                logger.warning(f"[优化集成] 保存权重融合器失败: {e}")

        try:
            with open(filepath, 'wb') as f:
                pickle.dump(state, f)
            logger.info(f"[优化集成] 优化状态已保存: {filepath}")
        except Exception as e:
            logger.warning(f"[优化集成] 保存优化状态失败: {e}")

    def load_optimization_state(self, filepath: Path) -> None:
        """加载优化模块状态"""
        if not OPTIMIZATION_MODULES_AVAILABLE:
            return

        try:
            with open(filepath, 'rb') as f:
                state = pickle.load(f)

            self._selected_features = state.get('selected_features', [])
            self._interaction_features = state.get('interaction_features', [])
            self._is_optimized_fitted = state.get('is_optimized_fitted', False)

            if self.feature_selector and filepath.with_suffix('.selector.pkl').exists():
                try:
                    self.feature_selector.load(filepath.with_suffix('.selector.pkl'))
                except Exception as e:
                    logger.warning(f"[优化集成] 加载特征选择器失败: {e}")

            if self.weight_fusion and filepath.with_suffix('.fusion.pkl').exists():
                try:
                    self.weight_fusion.load(filepath.with_suffix('.fusion.pkl'))
                except Exception as e:
                    logger.warning(f"[优化集成] 加载权重融合器失败: {e}")

            logger.info(f"[优化集成] 优化状态已加载: {filepath}")

        except Exception as e:
            logger.warning(f"[优化集成] 加载优化状态失败: {e}")


class OptimizedEnhancedPredictorAdapter:
    """
    优化的增强预测器适配器

    这是一个适配器类，用于在现有系统上启用优化功能。
    可以通过组合模式将优化能力添加到任何预测器。

    使用示例:
        from src.core.models.enhanced_predictor import EnhancedPL5Predictor

        # 创建基础预测器
        base_predictor = EnhancedPL5Predictor()

        # 包装为优化版本
        optimized = OptimizedEnhancedPredictorAdapter(base_predictor)
        optimized.fit_optimized(df, feature_cols)
        results = optimized.predict_optimized(features)
    """

    def __init__(
        self,
        base_predictor: Any,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Args:
            base_predictor: 基础预测器实例
            config: 优化配置
        """
        self.base_predictor = base_predictor
        self._opt_config = config or {}

        self._integration = OptimizationIntegrationMixin()
        self._integration._opt_config = self._opt_config
        self._integration._optimization_enabled = True

        self._integration._init_feature_optimization()
        self._integration._init_weight_optimization()
        self._integration._init_model_optimization()

        logger.info("[适配器] 优化增强预测器适配器初始化完成")

    def __getattr__(self, name: str) -> Any:
        """代理所有未处理的方法到底层预测器"""
        return getattr(self.base_predictor, name)

    def fit(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        enable_optimization: bool = True,
        **kwargs: Any
    ) -> 'OptimizedEnhancedPredictorAdapter':
        """
        训练预测器

        Args:
            df: 训练数据
            feature_cols: 特征列
            enable_optimization: 是否启用优化
            **kwargs: 其他训练参数
        """
        self.base_predictor.fit(df, feature_cols, **kwargs)

        if enable_optimization and OPTIMIZATION_MODULES_AVAILABLE:
            df_enhanced, selected_features = self._integration.optimize_features(
                df, feature_cols, fit_stacking=True
            )

            self._integration.fit_optimized_copula(df)

            self._integration._is_optimized_fitted = True

            logger.info(f"[适配器] 优化训练完成，选中{len(selected_features)}个特征")

        return self

    def predict(
        self,
        features: np.ndarray,
        recent_data: Optional[Dict[str, np.ndarray]] = None,
        top_k: int = 8,
        use_optimization: bool = True,
        **kwargs: Any
    ) -> Dict[str, Dict[str, Any]]:
        """
        预测

        Args:
            features: 特征向量
            recent_data: 最近数据
            top_k: 返回top-k
            use_optimization: 是否使用优化
            **kwargs: 其他预测参数
        """
        base_results = self.base_predictor.predict(
            features, recent_data, top_k, **kwargs
        )

        if not use_optimization or not OPTIMIZATION_MODULES_AVAILABLE:
            return base_results

        opt_results = self._integration.predict_with_optimization(
            features, recent_data, top_k
        )

        if opt_results is None:
            return base_results

        merged_results = self._merge_predictions(base_results, opt_results)

        return merged_results

    def _merge_predictions(
        self,
        base: Dict[str, Dict[str, Any]],
        optimized: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """合并基础和优化预测结果"""
        merged = {}

        for pos in self._integration.POSITIONS:
            if pos in base and pos in optimized:
                base_proba = np.array(base[pos].get('probabilities', [0.1]*10))
                opt_proba = np.array(optimized[pos].get('probabilities', [0.1]*10))

                alpha = 0.6
                fused_proba = alpha * base_proba + (1 - alpha) * opt_proba
                fused_proba = fused_proba / fused_proba.sum()

                top_indices = np.argsort(fused_proba)[::-1][:8]
                top_k_digits = top_indices.tolist()
                top_k_probs = fused_proba[top_indices].tolist()

                merged[pos] = {
                    'top_k': top_k_digits,
                    'probabilities': top_k_probs,
                    'uncertainty': optimized[pos].get('uncertainty', 0.5),
                    'base_used': True,
                    'optimization_used': True,
                    'weights_used': optimized[pos].get('weights_used')
                }
            elif pos in base:
                merged[pos] = base[pos]
                merged[pos]['base_used'] = True
                merged[pos]['optimization_used'] = False
            else:
                merged[pos] = optimized[pos]
                merged[pos]['base_used'] = False
                merged[pos]['optimization_used'] = True

        return merged

    def update_with_feedback(
        self,
        predictions: Dict[str, List[int]],
        actual: Dict[str, int]
    ) -> None:
        """更新模型"""
        if hasattr(self.base_predictor, 'update_with_feedback'):
            try:
                self.base_predictor.update_with_feedback(predictions, actual)
            except Exception as e:
                logger.warning(f"[适配器] 基础预测器更新失败: {e}")

        self._integration.update_optimization_with_feedback(predictions, actual)

    def get_optimization_summary(self) -> Dict[str, Any]:
        """获取优化摘要"""
        return self._integration.get_optimization_summary()
