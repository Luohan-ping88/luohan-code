"""
上下文感知权重融合器 V1.0
基于上下文的动态权重预测

改进点:
1. 简化RL状态空间 (128→32维)
2. 上下文感知的权重预测
3. 置信度加权的集成
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from collections import deque
import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class ContextAwareWeightFusion:
    """
    上下文感知的动态权重融合
    
    核心原理:
    1. 编码上下文信息到紧凑向量 (32维)
    2. 基于上下文预测各模型权重
    3. 结合置信度进行加权融合
    """
    
    POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
    MODEL_NAMES = ['stacking', 'hmm', 'copula', 'bayesian', 'mamba']
    
    DEFAULT_WEIGHTS = {
        'stacking': 0.35,
        'hmm': 0.15,
        'copula': 0.25,
        'bayesian': 0.15,
        'mamba': 0.10
    }
    
    def __init__(
        self,
        context_dim: int = 32,
        history_window: int = 30,
        enable_online_update: bool = True,
        confidence_temperature: float = 1.0
    ):
        """
        Args:
            context_dim: 上下文向量维度
            history_window: 历史表现窗口大小
            enable_online_update: 是否启用在线权重更新
            confidence_temperature: 置信度温度参数
        """
        self.context_dim = context_dim
        self.history_window = history_window
        self.enable_online_update = enable_online_update
        self.confidence_temperature = confidence_temperature
        
        self.model_weights = self.DEFAULT_WEIGHTS.copy()
        self.model_performance: Dict[str, deque] = {
            m: deque(maxlen=history_window) for m in self.MODEL_NAMES
        }
        
        self.position_performance: Dict[str, Dict[str, float]] = {
            pos: {m: 0.0 for m in self.MODEL_NAMES}
            for pos in self.POSITIONS
        }
        
        self.reward_history: deque = deque(maxlen=history_window)
        self.context_history: List[np.ndarray] = []
        
        self.weight_adjustment_factor = 0.1
        
        self._init_weight_predictor()
    
    def _init_weight_predictor(self):
        """初始化简化的权重预测器 (无外部依赖的纯NumPy实现)"""
        np.random.seed(42)
        
        self.context_encoder_weights = np.random.randn(32, self.context_dim) * 0.1
        self.context_encoder_bias = np.zeros(self.context_dim)
        
        self.weight_predictor_weights = np.random.randn(self.context_dim, len(self.MODEL_NAMES)) * 0.1
        self.weight_predictor_bias = np.zeros(len(self.MODEL_NAMES))
    
    def _extract_context_features(self) -> np.ndarray:
        """
        提取上下文特征 (32维)
        
        组成:
        [0:5)   - 模型置信度 (5维)
        [5:10)  - 模型熵 (5维)
        [10:15) - 模型近期表现 (5维)
        [15:20) - 位置命中率 (5维)
        [20:25) - 位置熵 (5维)
        [25:27) - 全局统计 (2维)
        [27:32) - 趋势特征 (5维)
        """
        features = np.zeros(self.context_dim)
        idx = 0
        
        for m in self.MODEL_NAMES:
            if self.model_performance[m]:
                recent = list(self.model_performance[m])
                features[idx] = np.mean([r.get('confidence', 0) for r in recent])
            idx += 1
        
        for m in self.MODEL_NAMES:
            if self.model_performance[m]:
                recent = list(self.model_performance[m])
                features[idx] = np.mean([r.get('entropy', 0) for r in recent])
            idx += 1
        
        for m in self.MODEL_NAMES:
            if self.model_performance[m]:
                recent = list(self.model_performance[m])
                features[idx] = np.mean([r.get('reward', 0) for r in recent])
            idx += 1
        
        for pos in self.POSITIONS:
            features[idx] = self.position_performance[pos].get('hit_rate', 0)
            idx += 1
        
        for pos in self.POSITIONS:
            features[idx] = self.position_performance[pos].get('consistency', 0)
            idx += 1
        
        if self.reward_history:
            rewards = list(self.reward_history)
            features[idx] = np.mean(rewards)
            features[idx + 1] = np.std(rewards)
        idx += 2
        
        if len(self.reward_history) >= 10:
            recent = list(self.reward_history)
            half = len(recent) // 2
            first_half = np.mean(recent[:half])
            second_half = np.mean(recent[half:])
            trend = second_half - first_half
            
            for i in range(5):
                offset = (i - 2) * 0.5
                features[idx + i] = np.clip(trend + offset, -1, 1)
        idx += 5
        
        features = np.clip(features, -3, 3)
        
        return features
    
    def _encode_context(self, raw_features: np.ndarray) -> np.ndarray:
        """
        编码原始特征到上下文向量
        """
        hidden = np.tanh(
            raw_features @ self.context_encoder_weights + self.context_encoder_bias
        )
        
        return hidden
    
    def _predict_weights(self, context: np.ndarray) -> np.ndarray:
        """
        基于上下文预测权重
        """
        logits = context @ self.weight_predictor_weights + self.weight_predictor_bias
        
        exp_logits = np.exp(logits - logits.max())
        weights = exp_logits / exp_logits.sum()
        
        return weights
    
    def get_weights(
        self,
        model_confidences: Optional[Dict[str, float]] = None,
        model_entropies: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        获取当前上下文感知的动态权重
        
        Args:
            model_confidences: 各模型的预测置信度
            model_entropies: 各模型的预测熵
            
        Returns:
            {模型名: 权重}
        """
        raw_features = self._extract_context_features()
        context = self._encode_context(raw_features)
        raw_weights = self._predict_weights(context)
        
        if model_confidences:
            for i, m in enumerate(self.MODEL_NAMES):
                conf = model_confidences.get(m, 0.5)
                raw_weights[i] *= (1 + conf * self.weight_adjustment_factor)
        
        raw_weights = raw_weights / raw_weights.sum()
        
        self.current_weights = dict(zip(self.MODEL_NAMES, raw_weights))
        self.current_context = context
        
        return self.current_weights
    
    def fuse_predictions(
        self,
        predictions: Dict[str, np.ndarray],
        use_confidence_weighting: bool = True
    ) -> np.ndarray:
        """
        上下文感知的概率融合
        
        Args:
            predictions: {模型名: 预测概率数组}
            use_confidence_weighting: 是否使用置信度加权
            
        Returns:
            融合后的概率分布
        """
        weights = self.get_weights()
        
        if use_confidence_weighting:
            return self._confidence_weighted_fusion(predictions, weights)
        else:
            return self._simple_weighted_fusion(predictions, weights)
    
    def _simple_weighted_fusion(
        self,
        predictions: Dict[str, np.ndarray],
        weights: Dict[str, float]
    ) -> np.ndarray:
        """简单加权融合"""
        fused = np.zeros(10)
        
        for model_name, proba in predictions.items():
            w = weights.get(model_name, 0.2)
            fused += w * proba
        
        fused = fused / (fused.sum() + 1e-12)
        return fused
    
    def _confidence_weighted_fusion(
        self,
        predictions: Dict[str, np.ndarray],
        base_weights: Dict[str, float]
    ) -> np.ndarray:
        """置信度加权融合"""
        fused = np.zeros(10)
        total_weight = 0.0
        
        for model_name, proba in predictions.items():
            base_w = base_weights.get(model_name, 0.2)
            
            max_prob = np.max(proba)
            entropy = -np.sum(proba * np.log(proba + 1e-12))
            confidence = (max_prob - entropy / np.log(10)) / 2
            
            confidence = np.clip(confidence, 0, 1)
            adjusted_weight = base_w * (1 + confidence * self.confidence_temperature)
            
            fused += adjusted_weight * proba
            total_weight += adjusted_weight
        
        fused = fused / (total_weight + 1e-12)
        return fused
    
    def update_with_feedback(
        self,
        predictions: Dict[str, np.ndarray],
        actual: Dict[str, int],
        top_k: int = 3
    ):
        """
        基于预测反馈更新模型表现
        
        Args:
            predictions: 各模型预测 {模型名: {位置: [top_k预测]}}
            actual: 实际结果 {位置: 实际值}
            top_k: 评估的top-k
        """
        for model_name, pos_predictions in predictions.items():
            total_reward = 0.0
            confidence = 0.0
            entropy = 0.0
            count = 0
            
            for pos in self.POSITIONS:
                if pos not in pos_predictions or pos not in actual:
                    continue
                
                pred_list = pos_predictions[pos][:top_k]
                actual_val = actual[pos]
                
                hit = actual_val in pred_list
                rank = pred_list.index(actual_val) + 1 if hit else 0
                
                reward = 1.0 if hit else 0.0
                if hit:
                    reward += 1.0 / rank
                
                total_reward += reward
                count += 1
                
                self.position_performance[pos][model_name] = (
                    0.7 * self.position_performance[pos].get(model_name, 0) +
                    0.3 * (1.0 if hit else 0.0)
                )
            
            if count > 0:
                avg_reward = total_reward / count
                
                self.model_performance[model_name].append({
                    'reward': avg_reward,
                    'confidence': confidence / count if confidence > 0 else 0.5,
                    'entropy': entropy / count if entropy > 0 else 0.5,
                    'timestamp': len(self.reward_history)
                })
                
                self.reward_history.append(avg_reward)
        
        if self.enable_online_update and len(self.reward_history) >= 10:
            self._update_weight_predictor()
    
    def _update_weight_predictor(self):
        """
        基于历史表现更新权重预测器
        
        使用策略梯度方法的简化版
        """
        if not self.reward_history:
            return
        
        rewards = np.array(list(self.reward_history))
        
        if len(rewards) < 10:
            return
        
        half = len(rewards) // 2
        first_half_reward = np.mean(rewards[:half])
        second_half_reward = np.mean(rewards[half:])
        
        improvement = second_half_reward - first_half_reward
        
        adjustment = improvement * 0.01
        
        for i in range(len(self.MODEL_NAMES)):
            if self.model_performance[self.MODEL_NAMES[i]]:
                recent = list(self.model_performance[self.MODEL_NAMES[i]])
                avg_reward = np.mean([r.get('reward', 0) for r in recent])
                
                if avg_reward > 0.3:
                    self.weight_predictor_bias[i] += adjustment
                else:
                    self.weight_predictor_bias[i] -= adjustment * 0.5
        
        self.weight_predictor_bias = np.clip(self.weight_predictor_bias, -2, 2)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取模型性能摘要"""
        summary = {
            'model_performance': {},
            'position_performance': {},
            'global_stats': {},
            'current_weights': self.current_weights if hasattr(self, 'current_weights') else self.model_weights
        }
        
        for m in self.MODEL_NAMES:
            if self.model_performance[m]:
                recent = list(self.model_performance[m])
                summary['model_performance'][m] = {
                    'avg_reward': np.mean([r.get('reward', 0) for r in recent]),
                    'avg_confidence': np.mean([r.get('confidence', 0) for r in recent]),
                    'samples': len(recent)
                }
            else:
                summary['model_performance'][m] = {
                    'avg_reward': 0.0,
                    'avg_confidence': 0.5,
                    'samples': 0
                }
        
        summary['position_performance'] = {
            pos: {
                'hit_rate': data.get('hit_rate', 0),
                'consistency': data.get('consistency', 0)
            }
            for pos, data in self.position_performance.items()
        }
        
        if self.reward_history:
            rewards = list(self.reward_history)
            summary['global_stats'] = {
                'avg_reward': np.mean(rewards),
                'std_reward': np.std(rewards),
                'trend': rewards[-1] - rewards[0] if len(rewards) > 1 else 0,
                'samples': len(rewards)
            }
        
        return summary
    
    def reset(self):
        """重置所有状态"""
        self.model_weights = self.DEFAULT_WEIGHTS.copy()
        
        for m in self.MODEL_NAMES:
            self.model_performance[m].clear()
        
        for pos in self.POSITIONS:
            self.position_performance[pos] = {m: 0.0 for m in self.MODEL_NAMES}
        
        self.reward_history.clear()
        self.context_history.clear()
        
        self._init_weight_predictor()
        
        logger.info("上下文感知权重融合器已重置")
    
    def save(self, filepath: Path):
        """保存状态"""
        state = {
            'model_weights': self.model_weights,
            'model_performance': {
                m: list(scores) for m, scores in self.model_performance.items()
            },
            'position_performance': self.position_performance,
            'reward_history': list(self.reward_history),
            'context_encoder_weights': self.context_encoder_weights,
            'context_encoder_bias': self.context_encoder_bias,
            'weight_predictor_weights': self.weight_predictor_weights,
            'weight_predictor_bias': self.weight_predictor_bias,
            'weight_adjustment_factor': self.weight_adjustment_factor,
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        
        logger.info(f"上下文感知权重融合器状态已保存: {filepath}")
    
    def load(self, filepath: Path):
        """加载状态"""
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        self.model_weights = state['model_weights']
        self.model_performance = {
            m: deque(scores, maxlen=self.history_window)
            for m, scores in state['model_performance'].items()
        }
        self.position_performance = state['position_performance']
        self.reward_history = deque(state['reward_history'], maxlen=self.history_window)
        self.context_encoder_weights = state['context_encoder_weights']
        self.context_encoder_bias = state['context_encoder_bias']
        self.weight_predictor_weights = state['weight_predictor_weights']
        self.weight_predictor_bias = state['weight_predictor_bias']
        self.weight_adjustment_factor = state['weight_adjustment_factor']
        
        logger.info(f"上下文感知权重融合器状态已加载: {filepath}")


class ThompsonSamplingOptimizer:
    """
    Thompson Sampling在线权重优化器
    
    基于Beta分布的探索-利用平衡算法
    """
    
    def __init__(self, model_names: List[str], initial_alpha: float = 1.0, initial_beta: float = 1.0):
        self.model_names = model_names
        self.prior = {'alpha': initial_alpha, 'beta': initial_beta}
        
        self.posterior: Dict[str, Dict[str, float]] = {
            m: {'alpha': initial_alpha, 'beta': initial_beta}
            for m in model_names
        }
        
        self.sample_history: List[Dict[str, float]] = []
    
    def update(self, hit_results: Dict[str, bool]):
        """
        根据预测结果更新后验分布
        
        使用Beta-Bernoulli共轭:
        Prior: Beta(α, β)
        Posterior: Beta(α + hits, β + misses)
        """
        for model, hit in hit_results.items():
            if model in self.posterior:
                self.posterior[model]['alpha'] += hit
                self.posterior[model]['beta'] += not hit
    
    def sample_weights(self, n_samples: int = 1000) -> Dict[str, float]:
        """
        Thompson Sampling采样
        
        Returns:
            {模型名: 采样权重}
        """
        samples = np.zeros((n_samples, len(self.model_names)))
        
        for i, model in enumerate(self.model_names):
            alpha = self.posterior[model]['alpha']
            beta = self.posterior[model]['beta']
            samples[:, i] = np.random.beta(alpha, beta, n_samples)
        
        normalized_samples = samples / samples.sum(axis=1, keepdims=True)
        mean_weights = normalized_samples.mean(axis=0)
        
        self.sample_history.append(dict(zip(self.model_names, mean_weights)))
        
        return dict(zip(self.model_names, mean_weights))
    
    def get_confidence_interval(self, model: str, confidence: float = 0.95) -> Tuple[float, float]:
        """
        获取权重的置信区间
        """
        if model not in self.posterior:
            return 0.0, 1.0
        
        alpha = self.posterior[model]['alpha']
        beta = self.posterior[model]['beta']
        
        lower = alpha / (alpha + beta)
        
        z = 1.96 if confidence == 0.95 else 2.576
        margin = z * np.sqrt(alpha * beta / ((alpha + beta)**2 * (alpha + beta + 1)))
        
        return max(0, lower - margin), min(1, lower + margin)
