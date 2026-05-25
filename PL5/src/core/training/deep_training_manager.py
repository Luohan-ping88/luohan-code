"""
深度训练管理器 - V11
根据数据变化，训练多个不同动态特征组合、树深度、窗口动态组合、超参数组合应用、模型动态组合，生成多套训练推理组合策略。
"""
import json
import logging
import pickle
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

# 首先确保正确的目录
_current_file = Path(__file__)
_project_root = _current_file.parent.parent.parent
LOGS_DIR = _project_root / 'logs'
MODELS_DIR = _project_root / 'models'
LOGS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

from src.core.utils.logger import get_logger

logger = get_logger('deep_training')


class StrategyCombination:
    """单套训练推理策略组合"""
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.feature_config = {}
        self.hyperparameters = {}
        self.window_config = {}
        self.model_config = {}
        self.performance = {}
        self.model_objects = {}
        self.created_at = datetime.now().isoformat()
        self.evaluated = False
        
    def to_dict(self) -> Dict:
        return {
            'strategy_id': self.strategy_id,
            'feature_config': self.feature_config,
            'hyperparameters': self.hyperparameters,
            'window_config': self.window_config,
            'model_config': self.model_config,
            'performance': self.performance,
            'created_at': self.created_at,
            'evaluated': self.evaluated
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StrategyCombination':
        strategy = cls(data['strategy_id'])
        strategy.feature_config = data.get('feature_config', {})
        strategy.hyperparameters = data.get('hyperparameters', {})
        strategy.window_config = data.get('window_config', {})
        strategy.model_config = data.get('model_config', {})
        strategy.performance = data.get('performance', {})
        strategy.created_at = data.get('created_at', datetime.now().isoformat())
        strategy.evaluated = data.get('evaluated', False)
        return strategy


class DeepTrainingManager:
    """深度训练管理器 - 生成和管理多套训练推理组合策略"""
    
    def __init__(self):
        self.strategies: Dict[str, StrategyCombination] = {}
        self.best_strategy_id: Optional[str] = None
        self.strategy_store_path = LOGS_DIR / "deep_training_strategies.json"
        self.model_store_dir = MODELS_DIR / "deep_strategies"
        self.model_store_dir.mkdir(exist_ok=True)
        self.load_strategies()
        
    def load_strategies(self):
        """加载已保存的策略组合"""
        if self.strategy_store_path.exists():
            try:
                with open(self.strategy_store_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for strategy_id, strategy_data in data.get('strategies', {}).items():
                        self.strategies[strategy_id] = StrategyCombination.from_dict(strategy_data)
                    self.best_strategy_id = data.get('best_strategy_id')
                logger.info(f"已加载 {len(self.strategies)} 套深度训练策略")
            except Exception as e:
                logger.warning(f"加载策略失败: {e}")
                
    def save_strategies(self):
        """保存策略组合"""
        try:
            data = {
                'strategies': {sid: s.to_dict() for sid, s in self.strategies.items()},
                'best_strategy_id': self.best_strategy_id,
                'saved_at': datetime.now().isoformat()
            }
            with open(self.strategy_store_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"已保存 {len(self.strategies)} 套深度训练策略")
        except Exception as e:
            logger.error(f"保存策略失败: {e}")
            
    def generate_feature_combinations(self, base_features: List[str]) -> List[Dict]:
        """生成多个动态特征组合"""
        combinations = []
        
        # 1. 全特征组合
        combinations.append({
            'name': 'full_features',
            'select_top': None,
            'feature_selection_method': 'all'
        })
        
        # 2. RFE选择的特征
        combinations.append({
            'name': 'rfe_selected',
            'select_top': 50,
            'feature_selection_method': 'rfe'
        })
        
        # 3. 基于重要性选择的特征
        combinations.append({
            'name': 'importance_selected',
            'select_top': 30,
            'feature_selection_method': 'importance'
        })
        
        # 4. 统计特征优先
        combinations.append({
            'name': 'statistical_priority',
            'select_top': 40,
            'feature_selection_method': 'statistical'
        })
        
        return combinations
    
    def generate_hyperparameter_combinations(self) -> List[Dict]:
        """生成多个超参数组合"""
        combinations = []
        
        # 1. 保守配置
        combinations.append({
            'name': 'conservative',
            'n_estimators': 100,
            'max_depth': 6,
            'learning_rate': 0.1,
            'subsample': 0.8
        })
        
        # 2. 平衡配置
        combinations.append({
            'name': 'balanced',
            'n_estimators': 200,
            'max_depth': 8,
            'learning_rate': 0.08,
            'subsample': 0.85
        })
        
        # 3. 激进配置
        combinations.append({
            'name': 'aggressive',
            'n_estimators': 300,
            'max_depth': 12,
            'learning_rate': 0.05,
            'subsample': 0.9
        })
        
        # 4. 深度配置
        combinations.append({
            'name': 'deep',
            'n_estimators': 250,
            'max_depth': 15,
            'learning_rate': 0.03,
            'subsample': 0.95
        })
        
        return combinations
    
    def generate_window_combinations(self) -> List[Dict]:
        """生成多个窗口动态组合"""
        combinations = []
        
        # 1. 短期窗口
        combinations.append({
            'name': 'short_term',
            'lookback_window': 30,
            'validation_window': 10
        })
        
        # 2. 中期窗口
        combinations.append({
            'name': 'medium_term',
            'lookback_window': 60,
            'validation_window': 20
        })
        
        # 3. 长期窗口
        combinations.append({
            'name': 'long_term',
            'lookback_window': 100,
            'validation_window': 30
        })
        
        # 4. 超长窗口
        combinations.append({
            'name': 'very_long_term',
            'lookback_window': 150,
            'validation_window': 40
        })
        
        return combinations
    
    def generate_model_combinations(self) -> List[Dict]:
        """生成多个模型动态组合"""
        combinations = []
        
        # 1. 单一XGBoost
        combinations.append({
            'name': 'xgboost_only',
            'models': ['xgboost']
        })
        
        # 2. 单一LightGBM
        combinations.append({
            'name': 'lightgbm_only',
            'models': ['lightgbm']
        })
        
        # 3. 单一CatBoost
        combinations.append({
            'name': 'catboost_only',
            'models': ['catboost']
        })
        
        # 4. XGBoost + LightGBM 集成
        combinations.append({
            'name': 'xgb_lgb_ensemble',
            'models': ['xgboost', 'lightgbm']
        })
        
        # 5. 三模型集成
        combinations.append({
            'name': 'full_ensemble',
            'models': ['xgboost', 'lightgbm', 'catboost']
        })
        
        return combinations
    
    def generate_all_strategies(self, base_features: List[str]) -> List[StrategyCombination]:
        """
        生成所有策略组合
        通过组合不同的特征、超参数、窗口、模型配置来生成多套策略
        """
        logger.info("=" * 80)
        logger.info("开始生成深度训练策略组合")
        logger.info("=" * 80)
        
        # 生成各个维度的组合
        feature_combinations = self.generate_feature_combinations(base_features)
        hyperparam_combinations = self.generate_hyperparameter_combinations()
        window_combinations = self.generate_window_combinations()
        model_combinations = self.generate_model_combinations()
        
        logger.info(f"特征组合数: {len(feature_combinations)}")
        logger.info(f"超参数组合数: {len(hyperparam_combinations)}")
        logger.info(f"窗口组合数: {len(window_combinations)}")
        logger.info(f"模型组合数: {len(model_combinations)}")
        
        # 使用网格搜索生成策略（智能采样，避免过多组合）
        strategies = []
        strategy_index = 0
        
        # 策略生成策略：
        # 1. 每个特征组合与最优的超参数、窗口、模型组合
        # 2. 每个模型组合与平衡的超参数、窗口组合
        # 3. 关键组合的全排列
        
        # 第一组：特征组合为主
        for feat_cfg in feature_combinations:
            for model_cfg in model_combinations:
                strategy_id = f"strategy_{strategy_index:03d}"
                strategy = StrategyCombination(strategy_id)
                strategy.feature_config = feat_cfg
                strategy.hyperparameters = hyperparam_combinations[1]  # 平衡配置
                strategy.window_config = window_combinations[1]  # 中期窗口
                strategy.model_config = model_cfg
                strategies.append(strategy)
                self.strategies[strategy_id] = strategy
                strategy_index += 1
        
        # 第二组：超参数组合为主
        for hp_cfg in hyperparam_combinations:
            for window_cfg in window_combinations:
                strategy_id = f"strategy_{strategy_index:03d}"
                strategy = StrategyCombination(strategy_id)
                strategy.feature_config = feature_combinations[1]  # RFE选择
                strategy.hyperparameters = hp_cfg
                strategy.window_config = window_cfg
                strategy.model_config = model_combinations[-1]  # 全集成
                strategies.append(strategy)
                self.strategies[strategy_id] = strategy
                strategy_index += 1
        
        logger.info(f"共生成 {len(strategies)} 套策略组合")
        
        # 保存策略
        self.save_strategies()
        
        return strategies
    
    def evaluate_strategy(self, strategy_id: str, performance_metrics: Dict):
        """评估策略性能"""
        if strategy_id in self.strategies:
            strategy = self.strategies[strategy_id]
            strategy.performance = performance_metrics
            strategy.evaluated = True
            logger.info(f"策略 {strategy_id} 评估完成: {performance_metrics}")
            
    def select_best_strategy(self) -> Optional[StrategyCombination]:
        """选择最优策略"""
        if not self.strategies:
            return None
            
        # 按综合分数排序
        sorted_strategies = sorted(
            self.strategies.values(),
            key=lambda s: s.performance.get('overall_score', 0),
            reverse=True
        )
        
        if sorted_strategies:
            self.best_strategy_id = sorted_strategies[0].strategy_id
            self.save_strategies()
            logger.info(f"最优策略: {self.best_strategy_id}, 分数: {sorted_strategies[0].performance.get('overall_score', 0)}")
            return sorted_strategies[0]
            
        return None
    
    def get_all_strategies(self) -> List[StrategyCombination]:
        """获取所有策略"""
        return list(self.strategies.values())
    
    def get_strategy(self, strategy_id: str) -> Optional[StrategyCombination]:
        """获取指定策略"""
        return self.strategies.get(strategy_id)
    
    def get_top_n_strategies(self, n: int = 3) -> List[StrategyCombination]:
        """获取Top N策略"""
        sorted_strategies = sorted(
            [s for s in self.strategies.values() if s.evaluated],
            key=lambda s: s.performance.get('overall_score', 0),
            reverse=True
        )
        return sorted_strategies[:n]
    
    def clear_old_strategies(self, keep_days: int = 7):
        """清理旧策略"""
        cutoff_time = datetime.now() - (datetime.now() - datetime(2000, 1, 1)).fromtimestamp(keep_days * 86400)
        old_ids = [
            sid for sid, s in self.strategies.items()
            if datetime.fromisoformat(s.created_at) < cutoff_time
        ]
        for sid in old_ids:
            del self.strategies[sid]
        if old_ids:
            self.save_strategies()
            logger.info(f"已清理 {len(old_ids)} 套旧策略")
