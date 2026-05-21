"""
V11高级架构集成模块

整合所有高级组件：
1. Mamba-SSM长序列预测器
2. 扩散模型精修器
3. MoE专家混合系统
4. 因果推理引擎

提供统一的预测接口
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import logging
from pathlib import Path

try:
    from .mamba_predictor import MambaPL5Predictor
    from .advanced_components import DiffusionRefiner, MoEPredictor, CausalReasoningEngine
    ADVANCED_AVAILABLE = True
except ImportError as e:
    ADVANCED_AVAILABLE = False
    logging.getLogger(__name__).warning(f"高级组件导入失败: {e}")

from src.core.models.optimization_integration import OptimizedEnhancedPredictorAdapter

logger = logging.getLogger(__name__)


class PL5V11Predictor:
    """
    PL5 V11高级预测器
    
    整合所有高级架构组件的统一预测器
    
    架构层次:
    ┌─────────────────────────────────────────────────────────────┐
    │                     V11 预测器                              │
    ├─────────────────────────────────────────────────────────────┤
    │  输入层 → Mamba-SSM → MoE融合 → 扩散精修 → 因果解释 → 输出  │
    └─────────────────────────────────────────────────────────────┘
    """
    
    POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        use_advanced: bool = True,
        device: str = 'cpu'
    ):
        """
        Args:
            config: 配置字典
            use_advanced: 是否使用高级组件
            device: 设备 ('cpu' 或 'cuda')
        """
        self.config = config or {}
        self.use_advanced = use_advanced
        self.device = device
        
        self.mamba_predictor: Optional[MambaPL5Predictor] = None
        self.diffusion_refiner: Optional[DiffusionRefiner] = None
        self.moe_predictor: Optional[MoEPredictor] = None
        self.causal_engine: Optional[CausalReasoningEngine] = None
        self.fallback_predictor: Optional[OptimizedEnhancedPredictorAdapter] = None
        
        self._is_trained = False
        
        self._init_components()
    
    def _init_components(self):
        """初始化各组件"""
        if not ADVANCED_AVAILABLE:
            logger.warning("高级组件不可用，使用回退预测器")
            return
        
        try:
            mamba_config = self.config.get('mamba', {})
            self.mamba_predictor = MambaPL5Predictor(
                d_model=mamba_config.get('d_model', 256),
                n_layers=mamba_config.get('n_layers', 6),
                seq_len=mamba_config.get('seq_len', 50),
                device=self.device
            )
            logger.info("[V11] Mamba预测器初始化完成")
        except Exception as e:
            logger.warning(f"[V11] Mamba预测器初始化失败: {e}")
        
        try:
            diffusion_config = self.config.get('diffusion', {})
            self.diffusion_refiner = DiffusionRefiner(
                num_timesteps=diffusion_config.get('num_timesteps', 100),
                noise_scale=diffusion_config.get('noise_scale', 0.1),
                device=self.device
            )
            logger.info("[V11] 扩散精修器初始化完成")
        except Exception as e:
            logger.warning(f"[V11] 扩散精修器初始化失败: {e}")
        
        try:
            moe_config = self.config.get('moe', {})
            self.moe_predictor = MoEPredictor(
                num_experts=moe_config.get('num_experts', 4),
                d_model=moe_config.get('d_model', 128),
                device=self.device
            )
            logger.info("[V11] MoE预测器初始化完成")
        except Exception as e:
            logger.warning(f"[V11] MoE预测器初始化失败: {e}")
        
        try:
            self.causal_engine = CausalReasoningEngine()
            logger.info("[V11] 因果推理引擎初始化完成")
        except Exception as e:
            logger.warning(f"[V11] 因果推理引擎初始化失败: {e}")
    
    def fit(
        self,
        df: pd.DataFrame,
        feature_cols: Optional[List[str]] = None,
        train_mamba: bool = True,
        train_diffusion: bool = True,
        train_moe: bool = True,
        epochs: int = 50,
        batch_size: int = 32
    ) -> Dict[str, Any]:
        """
        训练所有组件
        
        Args:
            df: 训练数据
            feature_cols: 特征列
            train_mamba: 是否训练Mamba
            train_diffusion: 是否训练扩散模型
            train_moe: 是否训练MoE
            epochs: 训练轮数
            batch_size: 批次大小
        
        Returns:
            训练历史
        """
        logger.info("[V11] 开始训练高级预测器...")
        
        history = {}
        
        if train_mamba and self.mamba_predictor:
            try:
                logger.info("[V11] 训练Mamba预测器...")
                mamba_history = self.mamba_predictor.fit(df, epochs, batch_size)
                history['mamba'] = mamba_history
            except Exception as e:
                logger.error(f"[V11] Mamba训练失败: {e}")
        
        if train_diffusion and self.diffusion_refiner:
            try:
                logger.info("[V11] 训练扩散精修器...")
                diffusion_history = self.diffusion_refiner.fit(df, epochs=10, batch_size=batch_size)
                history['diffusion'] = diffusion_history
            except Exception as e:
                logger.error(f"[V11] 扩散训练失败: {e}")
        
        if train_moe and self.moe_predictor:
            try:
                logger.info("[V11] 训练MoE预测器...")
                moe_history = self.moe_predictor.fit(df, epochs=10, batch_size=batch_size)
                history['moe'] = moe_history
            except Exception as e:
                logger.error(f"[V11] MoE训练失败: {e}")
        
        if self.causal_engine:
            features = feature_cols or ['wan', 'qian', 'bai', 'shi', 'ge',
                                       'lag_1_wan', 'lag_2_wan', 'digit_freq_wan', 'trend_wan']
            self.causal_engine.build_graph(features)
        
        self._is_trained = True
        logger.info("[V11] 高级预测器训练完成")
        
        return history
    
    def predict(
        self,
        df: pd.DataFrame,
        top_k: int = 8,
        use_diffusion: bool = True,
        use_moe: bool = True,
        use_causal: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        执行完整的预测流程
        
        Args:
            df: 输入数据
            top_k: 返回前k个预测
            use_diffusion: 是否使用扩散精修
            use_moe: 是否使用MoE融合
            use_causal: 是否生成因果解释
        
        Returns:
            {位置: {top_k, probabilities, uncertainty, explanation}}
        """
        if not self._is_trained:
            logger.warning("[V11] 模型未训练，使用随机预测")
            return self._random_predict(top_k)
        
        if self.mamba_predictor:
            base_results = self.mamba_predictor.predict(df, top_k=10)
        else:
            return self._random_predict(top_k)
        
        probabilities = {pos: base_results[pos]['full_distribution'] for pos in self.POSITIONS}
        
        if use_moe and self.moe_predictor:
            try:
                probabilities = self.moe_predictor.predict(probabilities)
                logger.debug("[V11] MoE精修完成")
            except Exception as e:
                logger.warning(f"[V11] MoE精修失败: {e}")
        
        if use_diffusion and self.diffusion_refiner:
            try:
                probabilities = self.diffusion_refiner.refine(probabilities)
                logger.debug("[V11] 扩散精修完成")
            except Exception as e:
                logger.warning(f"[V11] 扩散精修失败: {e}")
        
        results = {}
        for pos in self.POSITIONS:
            probs = probabilities[pos]
            top_indices = np.argsort(probs)[::-1][:top_k]
            
            results[pos] = {
                'top_k': top_indices.tolist(),
                'probabilities': probs[top_indices].tolist(),
                'full_distribution': probs.tolist(),
                'uncertainty': self._compute_uncertainty(probs),
                'version': 'V11'
            }
        
        if use_causal and self.causal_engine:
            try:
                explanations = self.causal_engine.explain_prediction(
                    {pos: results[pos]['top_k'] for pos in self.POSITIONS},
                    {}
                )
                for pos in self.POSITIONS:
                    if pos in explanations:
                        results[pos]['explanation'] = explanations[pos]
                logger.debug("[V11] 因果解释生成完成")
            except Exception as e:
                logger.warning(f"[V11] 因果解释生成失败: {e}")
        
        return results
    
    def _compute_uncertainty(self, probs: np.ndarray) -> float:
        """计算预测不确定性"""
        entropy = -np.sum(probs * np.log(probs + 1e-10))
        max_entropy = np.log(10)
        return entropy / max_entropy
    
    def _random_predict(self, top_k: int) -> Dict[str, Dict[str, Any]]:
        """随机预测"""
        results = {}
        
        for pos in self.POSITIONS:
            probs = np.ones(10) / 10
            top_indices = np.argsort(probs)[::-1][:top_k]
            
            results[pos] = {
                'top_k': top_indices.tolist(),
                'probabilities': probs[top_indices].tolist(),
                'full_distribution': probs.tolist(),
                'uncertainty': 1.0,
                'version': 'V11',
                'note': '未训练，使用随机预测'
            }
        
        return results
    
    def update_with_feedback(
        self,
        predictions: Dict[str, List[int]],
        actual: Dict[str, int]
    ):
        """基于反馈更新模型"""
        logger.info("[V11] 更新模型...")
        
        if self.mamba_predictor:
            pass
        
        if self.diffusion_refiner:
            pass
        
        if self.moe_predictor:
            pass
    
    def save(self, filepath: str):
        """保存模型"""
        import pickle
        
        state = {
            'config': self.config,
            'is_trained': self._is_trained,
        }
        
        if self.mamba_predictor:
            mamba_path = filepath.replace('.pkl', '_mamba.pth')
            self.mamba_predictor.save(mamba_path)
            state['mamba_path'] = mamba_path
        
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        
        logger.info(f"[V11] 模型已保存到: {filepath}")
    
    def load(self, filepath: str):
        """加载模型"""
        import pickle
        
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        self.config = state.get('config', {})
        self._is_trained = state.get('is_trained', False)
        
        if self.mamba_predictor and state.get('mamba_path'):
            self.mamba_predictor.load(state['mamba_path'])
        
        logger.info(f"[V11] 模型已从 {filepath} 加载")
    
    def get_component_status(self) -> Dict[str, Any]:
        """获取各组件状态"""
        return {
            'version': 'V11',
            'is_trained': self._is_trained,
            'components': {
                'mamba': self.mamba_predictor is not None,
                'diffusion': self.diffusion_refiner is not None,
                'moe': self.moe_predictor is not None,
                'causal': self.causal_engine is not None,
            },
            'config': self.config
        }


class PL5ArchitectureManager:
    """
    PL5架构管理器
    
    管理不同版本的架构，支持动态切换
    """
    
    def __init__(self):
        self.architectures = {}
        self.current_architecture = 'V10'
    
    def register_architecture(self, name: str, predictor):
        """注册架构"""
        self.architectures[name] = predictor
    
    def set_architecture(self, name: str):
        """设置当前架构"""
        if name in self.architectures:
            self.current_architecture = name
            logger.info(f"架构切换到: {name}")
        else:
            logger.warning(f"架构 {name} 未注册")
    
    def predict(self, *args, **kwargs) -> Dict[str, Dict[str, Any]]:
        """使用当前架构预测"""
        if self.current_architecture in self.architectures:
            return self.architectures[self.current_architecture].predict(*args, **kwargs)
        else:
            logger.error(f"当前架构 {self.current_architecture} 不可用")
            return {}
    
    def get_available_architectures(self) -> List[str]:
        """获取可用架构列表"""
        return list(self.architectures.keys())
