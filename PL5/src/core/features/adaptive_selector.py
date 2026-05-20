"""
自适应特征选择器 V1.0
基于在线学习的多阶段特征选择器

改进点:
1. 使用L1正则化在线学习进行动态特征筛选
2. 特征重要性衰减机制
3. 特征组内约束选择
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class AdaptiveFeatureSelector:
    """
    自适应特征选择器
    
    核心算法:
    1. 指数加权移动平均 (EWMA) 追踪特征重要性
    2. 组约束避免同组特征冗余
    3. 动态阈值自动调整
    """
    
    def __init__(
        self,
        decay_factor: float = 0.95,
        min_importance: float = 0.01,
        max_features_per_group: int = 3,
        warmup_periods: int = 10,
        selection_threshold: float = 0.05
    ):
        """
        Args:
            decay_factor: 指数衰减因子，控制历史重要性的衰减速度
            min_importance: 最小重要性阈值，低于此值的特征将被淘汰
            max_features_per_group: 每组最多选择的特征数
            warmup_periods: 预热期数，在预热期内不进行特征淘汰
            selection_threshold: 特征选择阈值
        """
        self.decay_factor = decay_factor
        self.min_importance = min_importance
        self.max_features_per_group = max_features_per_group
        self.warmup_periods = warmup_periods
        self.selection_threshold = selection_threshold
        
        self.feature_scores: Dict[str, float] = {}
        self.feature_groups: Dict[str, str] = {}
        self.group_constraints: Dict[str, int] = {}
        self.period_count: int = 0
        self.selected_features: List[str] = []
        self.history_scores: List[Dict[str, float]] = []
        
        self._initialized = False
    
    def register_group(self, group_name: str, features: List[str], max_select: Optional[int] = None):
        """
        注册特征组
        
        Args:
            group_name: 组名称 (如 'fibonacci', 'entropy')
            features: 该组包含的特征列表
            max_select: 该组最多选择的特征数，默认使用类级max_features_per_group
        """
        self.group_constraints[group_name] = max_select or self.max_features_per_group
        
        for feat in features:
            self.feature_groups[feat] = group_name
            if feat not in self.feature_scores:
                self.feature_scores[feat] = 0.0
        
        logger.info(f"注册特征组 '{group_name}': {len(features)} 个特征，最多选择 {self.group_constraints[group_name]} 个")
    
    def _infer_group(self, feature_name: str) -> str:
        """
        自动推断特征所属组
        
        基于特征名称的命名模式进行推断
        """
        name_lower = feature_name.lower()
        
        group_patterns = {
            'fibonacci': ['fib', 'fb'],
            'entropy': ['entr', 'entropy'],
            'markov': ['markov', 'trans'],
            'fourier': ['fouri', 'fft', 'harmon'],
            'chaos': ['hurst', 'lyap', 'chaos'],
            'extreme': ['extreme', 'max', 'min', 'range'],
            'pattern': ['pattern', 'repeat', 'consec'],
            'momentum': ['momentum', 'mom', 'diff'],
            'statistical': ['mean', 'std', 'var', 'skew', 'kurt'],
            'cross_correlation': ['cross', 'corr'],
        }
        
        for group, patterns in group_patterns.items():
            if any(p in name_lower for p in patterns):
                return group
        
        return 'uncategorized'
    
    def update(self, feature_importance: Dict[str, float], period: Optional[int] = None):
        """
        更新特征重要性分数
        
        Args:
            feature_importance: 特征名 -> 重要性分数的字典
            period: 当前期号（可选）
        """
        if period is not None:
            self.period_count = period
        else:
            self.period_count += 1
        
        current_scores = {}
        
        for feat, score in feature_importance.items():
            if feat not in self.feature_scores:
                self.feature_scores[feat] = 0.0
            
            if feat not in self.feature_groups:
                self.feature_groups[feat] = self._infer_group(feat)
            
            self.feature_scores[feat] = (
                self.decay_factor * self.feature_scores[feat] +
                (1 - self.decay_factor) * score
            )
            
            current_scores[feat] = self.feature_scores[feat]
        
        self.history_scores.append(current_scores.copy())
        
        if len(self.history_scores) > 500:
            self.history_scores.pop(0)
        
        self._initialized = True
        
        if self.period_count > self.warmup_periods:
            self._prune_features()
    
    def _prune_features(self):
        """
        基于组约束进行特征剪枝
        
        策略:
        1. 淘汰低于最小重要性阈值的特征
        2. 每组只保留重要性最高的N个特征
        """
        new_selected = []
        
        grouped_features: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        
        for feat, score in self.feature_scores.items():
            if score < self.min_importance:
                continue
            
            group = self.feature_groups.get(feat, 'uncategorized')
            grouped_features[group].append((feat, score))
        
        for group, features_scores in grouped_features.items():
            features_scores.sort(key=lambda x: x[1], reverse=True)
            max_select = self.group_constraints.get(group, self.max_features_per_group)
            
            selected = features_scores[:max_select]
            new_selected.extend([f for f, _ in selected])
            
            if len(features_scores) > max_select:
                logger.debug(
                    f"特征组 '{group}': 选择了 {len(selected)}/{len(features_scores)} 个 "
                    f"(阈值: {features_scores[max_select][1]:.4f})"
                )
        
        self.selected_features = new_selected
        
        eliminated = set(self.feature_scores.keys()) - set(new_selected)
        if eliminated:
            logger.info(f"特征剪枝完成: {len(new_selected)} 个特征被选中, {len(eliminated)} 个特征被淘汰")
    
    def get_selected_features(self, 
                            feature_names: List[str],
                            min_count: int = 20,
                            max_count: int = 100) -> List[str]:
        """
        获取最终选择的特征列表
        
        Args:
            feature_names: 候选特征列表
            min_count: 最少选择的特征数
            max_count: 最多选择的特征数
            
        Returns:
            选中的特征列表
        """
        if not self._initialized or not self.selected_features:
            return feature_names[:max_count]
        
        selected = [f for f in self.selected_features if f in feature_names]
        
        if len(selected) < min_count:
            additional = [
                f for f in feature_names
                if f not in selected and f in self.feature_scores
            ]
            additional.sort(key=lambda x: self.feature_scores.get(x, 0), reverse=True)
            selected.extend(additional[:min_count - len(selected)])
        
        return selected[:max_count]
    
    def get_importance_ranking(self) -> List[Tuple[str, float]]:
        """
        获取特征重要性排名
        
        Returns:
            [(特征名, 重要性分数), ...] 按重要性降序排列
        """
        items = list(self.feature_scores.items())
        items.sort(key=lambda x: x[1], reverse=True)
        return items
    
    def get_group_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        获取各特征组的统计信息
        
        Returns:
            {组名: {count, avg_importance, top_features, selected_count}}
        """
        stats = {}
        
        grouped: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        for feat, score in self.feature_scores.items():
            group = self.feature_groups.get(feat, 'uncategorized')
            grouped[group].append((feat, score))
        
        for group, features_scores in grouped.items():
            features_scores.sort(key=lambda x: x[1], reverse=True)
            scores = [s for _, s in features_scores]
            
            stats[group] = {
                'total_count': len(features_scores),
                'avg_importance': np.mean(scores) if scores else 0,
                'max_importance': max(scores) if scores else 0,
                'top_features': [f for f, _ in features_scores[:5]],
                'selected_count': len([f for f in self.selected_features if self.feature_groups.get(f) == group])
            }
        
        return stats
    
    def reset(self):
        """重置选择器状态"""
        self.feature_scores.clear()
        self.feature_groups.clear()
        self.history_scores.clear()
        self.selected_features.clear()
        self.period_count = 0
        self._initialized = False
        logger.info("自适应特征选择器已重置")
    
    def save(self, filepath: Path):
        """保存选择器状态"""
        state = {
            'feature_scores': self.feature_scores,
            'feature_groups': self.feature_groups,
            'group_constraints': self.group_constraints,
            'period_count': self.period_count,
            'selected_features': self.selected_features,
            'history_scores': self.history_scores[-100:],
            'decay_factor': self.decay_factor,
            'min_importance': self.min_importance,
            'warmup_periods': self.warmup_periods,
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        
        logger.info(f"自适应特征选择器状态已保存: {filepath}")
    
    def load(self, filepath: Path):
        """加载选择器状态"""
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        self.feature_scores = state['feature_scores']
        self.feature_groups = state['feature_groups']
        self.group_constraints = state['group_constraints']
        self.period_count = state['period_count']
        self.selected_features = state['selected_features']
        self.history_scores = state['history_scores']
        self.decay_factor = state['decay_factor']
        self.min_importance = state['min_importance']
        self.warmup_periods = state['warmup_periods']
        self._initialized = True
        
        logger.info(f"自适应特征选择器状态已加载: {filepath}")
    
    def __repr__(self) -> str:
        return (
            f"<AdaptiveFeatureSelector "
            f"features={len(self.feature_scores)} "
            f"selected={len(self.selected_features)} "
            f"periods={self.period_count}>"
        )


class OnlineImportanceTracker:
    """
    在线特征重要性追踪器
    
    基于预测结果反馈在线更新特征重要性
    """
    
    def __init__(self, n_positions: int = 5, window_size: int = 100):
        self.n_positions = n_positions
        self.window_size = window_size
        
        self.hit_history: List[Dict[str, Any]] = []
        self.position_features: Dict[str, List[str]] = {}
        self.feature_hit_rate: Dict[str, List[float]] = defaultdict(list)
    
    def record_prediction(
        self,
        predictions: Dict[str, List[int]],
        actual: Dict[str, int],
        top_k: int = 3
    ):
        """
        记录预测结果
        
        Args:
            predictions: {位置: [预测的top_k数字列表]}
            actual: {位置: 实际开奖数字}
            top_k: 考虑前top_k个预测
        """
        record = {
            'predictions': predictions.copy(),
            'actual': actual.copy(),
            'hits': {}
        }
        
        for pos in predictions:
            if pos not in actual:
                continue
            
            pred_list = predictions[pos][:top_k]
            actual_val = actual[pos]
            
            hit = actual_val in pred_list
            rank = pred_list.index(actual_val) + 1 if hit else 0
            
            record['hits'][pos] = {'hit': hit, 'rank': rank, 'top_k': top_k}
        
        self.hit_history.append(record)
        
        if len(self.hit_history) > self.window_size:
            self.hit_history.pop(0)
    
    def get_feature_importance(
        self,
        feature_values: Dict[str, Dict[str, float]],
        lookback: int = 50
    ) -> Dict[str, float]:
        """
        基于预测表现计算特征重要性
        
        Args:
            feature_values: {位置: {特征名: 特征值}}
            lookback: 回看期数
            
        Returns:
            {特征名: 重要性分数}
        """
        if len(self.hit_history) < 10:
            return {k: 1.0 for v in feature_values.values() for k in v.keys()}
        
        recent = self.hit_history[-lookback:]
        importance = defaultdict(float)
        
        for i, record in enumerate(recent):
            recency_weight = (i + 1) / len(recent)
            
            for pos, hit_info in record['hits'].items():
                if pos not in feature_values:
                    continue
                
                hit = hit_info['hit']
                rank = hit_info['rank']
                base_reward = 1.0 if hit else 0.0
                if hit and rank > 0:
                    base_reward += 1.0 / rank
                
                for feat_name, feat_val in feature_values[pos].items():
                    normalized_val = feat_val / (abs(feat_val) + 1e-6)
                    importance[feat_name] += recency_weight * base_reward * normalized_val
        
        if not importance:
            return {k: 1.0 for v in feature_values.values() for k in v.keys()}
        
        max_imp = max(abs(v) for v in importance.values()) or 1.0
        for feat in importance:
            importance[feat] /= max_imp
        
        return dict(importance)
    
    def get_position_statistics(self) -> Dict[str, Dict[str, float]]:
        """
        获取各位置的预测统计
        
        Returns:
            {位置: {hit_rate, avg_rank, consistency}}
        """
        stats = {}
        
        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            hits = []
            ranks = []
            
            for record in self.hit_history:
                if pos in record['hits']:
                    hits.append(1 if record['hits'][pos]['hit'] else 0)
                    ranks.append(record['hits'][pos]['rank'])
            
            if hits:
                stats[pos] = {
                    'hit_rate': np.mean(hits),
                    'avg_rank': np.mean([r for r in ranks if r > 0]) if any(r > 0 for r in ranks) else 0,
                    'consistency': 1 - np.std(hits) if len(hits) > 1 else 0,
                    'total_predictions': len(hits)
                }
            else:
                stats[pos] = {
                    'hit_rate': 0,
                    'avg_rank': 0,
                    'consistency': 0,
                    'total_predictions': 0
                }
        
        return stats
