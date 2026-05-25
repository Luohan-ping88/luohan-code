"""
增量训练管理器 - V11
对深度训练进行审查、复核，找出推理组合方案缺陷，进一步优化，为最终预测结果提供调整方案。
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

# 首先确保正确的目录
_current_file = Path(__file__)
_project_root = _current_file.parent.parent.parent
LOGS_DIR = _project_root / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

from src.core.utils.logger import get_logger
from src.core.training.deep_training_manager import DeepTrainingManager, StrategyCombination

logger = get_logger('incremental_training')


class StrategyDefect:
    """策略缺陷分析"""
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.defect_type = ""
        self.defect_description = ""
        self.severity = "medium"  # low, medium, high, critical
        self.affected_positions = []
        self.suggested_fix = {}
        self.detected_at = datetime.now().isoformat()
        
    def to_dict(self) -> Dict:
        return {
            'strategy_id': self.strategy_id,
            'defect_type': self.defect_type,
            'defect_description': self.defect_description,
            'severity': self.severity,
            'affected_positions': self.affected_positions,
            'suggested_fix': self.suggested_fix,
            'detected_at': self.detected_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StrategyDefect':
        defect = cls(data['strategy_id'])
        defect.defect_type = data.get('defect_type', '')
        defect.defect_description = data.get('defect_description', '')
        defect.severity = data.get('severity', 'medium')
        defect.affected_positions = data.get('affected_positions', [])
        defect.suggested_fix = data.get('suggested_fix', {})
        defect.detected_at = data.get('detected_at', datetime.now().isoformat())
        return defect


class AdjustmentProposal:
    """调整方案"""
    def __init__(self, proposal_id: str):
        self.proposal_id = proposal_id
        self.base_strategy_id = ""
        self.adjustments = {}
        self.expected_improvement = 0.0
        self.priority = 0
        self.implemented = False
        self.created_at = datetime.now().isoformat()
        
    def to_dict(self) -> Dict:
        return {
            'proposal_id': self.proposal_id,
            'base_strategy_id': self.base_strategy_id,
            'adjustments': self.adjustments,
            'expected_improvement': self.expected_improvement,
            'priority': self.priority,
            'implemented': self.implemented,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AdjustmentProposal':
        proposal = cls(data['proposal_id'])
        proposal.base_strategy_id = data.get('base_strategy_id', '')
        proposal.adjustments = data.get('adjustments', {})
        proposal.expected_improvement = data.get('expected_improvement', 0.0)
        proposal.priority = data.get('priority', 0)
        proposal.implemented = data.get('implemented', False)
        proposal.created_at = data.get('created_at', datetime.now().isoformat())
        return proposal


class IncrementalTrainingManager:
    """增量训练管理器 - 审查、优化策略"""
    
    def __init__(self, deep_training_manager: Optional[DeepTrainingManager] = None):
        self.deep_manager = deep_training_manager or DeepTrainingManager()
        self.defects: Dict[str, List[StrategyDefect]] = {}
        self.proposals: Dict[str, AdjustmentProposal] = {}
        self.defects_store_path = LOGS_DIR / "strategy_defects.json"
        self.proposals_store_path = LOGS_DIR / "adjustment_proposals.json"
        self.load_data()
        
    def load_data(self):
        """加载缺陷和方案数据"""
        # 加载缺陷
        if self.defects_store_path.exists():
            try:
                with open(self.defects_store_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for sid, defect_list in data.get('defects', {}).items():
                        self.defects[sid] = [StrategyDefect.from_dict(d) for d in defect_list]
                logger.info(f"已加载 {len(self.defects)} 个策略的缺陷分析")
            except Exception as e:
                logger.warning(f"加载缺陷数据失败: {e}")
        
        # 加载方案
        if self.proposals_store_path.exists():
            try:
                with open(self.proposals_store_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for pid, proposal_data in data.get('proposals', {}).items():
                        self.proposals[pid] = AdjustmentProposal.from_dict(proposal_data)
                logger.info(f"已加载 {len(self.proposals)} 个调整方案")
            except Exception as e:
                logger.warning(f"加载方案数据失败: {e}")
                
    def save_data(self):
        """保存数据"""
        try:
            # 保存缺陷
            defects_data = {
                'defects': {sid: [d.to_dict() for d in dl] for sid, dl in self.defects.items()},
                'saved_at': datetime.now().isoformat()
            }
            with open(self.defects_store_path, 'w', encoding='utf-8') as f:
                json.dump(defects_data, f, indent=2, ensure_ascii=False)
                
            # 保存方案
            proposals_data = {
                'proposals': {pid: p.to_dict() for pid, p in self.proposals.items()},
                'saved_at': datetime.now().isoformat()
            }
            with open(self.proposals_store_path, 'w', encoding='utf-8') as f:
                json.dump(proposals_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"已保存缺陷和方案数据")
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            
    def review_strategy(self, strategy: StrategyCombination) -> List[StrategyDefect]:
        """
        审查策略，找出缺陷
        检查维度：
        1. 过拟合/欠拟合
        2. 特征选择不合理
        3. 超参数不当
        4. 窗口配置不合适
        5. 模型组合问题
        """
        logger.info(f"审查策略: {strategy.strategy_id}")
        defects = []
        
        # 检查性能数据
        performance = strategy.performance
        if not performance:
            defect = StrategyDefect(strategy.strategy_id)
            defect.defect_type = "missing_performance"
            defect.defect_description = "缺少性能评估数据"
            defect.severity = "high"
            defects.append(defect)
            return defects
        
        # 1. 检查过拟合迹象 - 训练集与验证集性能差距过大
        train_acc = performance.get('train_accuracy', 0)
        val_acc = performance.get('validation_accuracy', 0)
        if train_acc - val_acc > 0.15:
            defect = StrategyDefect(strategy.strategy_id)
            defect.defect_type = "overfitting"
            defect.defect_description = f"训练准确率({train_acc:.2%})显著高于验证准确率({val_acc:.2%})，存在过拟合"
            defect.severity = "high"
            defect.suggested_fix = {
                'action': 'reduce_overfitting',
                'adjust_n_estimators': -50,
                'adjust_max_depth': -2,
                'increase_regularization': True
            }
            defects.append(defect)
        
        # 2. 检查欠拟合迹象 - 整体准确率偏低
        if val_acc < 0.2:
            defect = StrategyDefect(strategy.strategy_id)
            defect.defect_type = "underfitting"
            defect.defect_description = f"验证准确率({val_acc:.2%})过低，可能欠拟合"
            defect.severity = "high"
            defect.suggested_fix = {
                'action': 'reduce_underfitting',
                'adjust_n_estimators': 100,
                'adjust_max_depth': 3,
                'add_more_features': True
            }
            defects.append(defect)
        
        # 3. 检查各位置性能不均衡
        pos_accuracies = performance.get('position_accuracies', {})
        if pos_accuracies:
            accuracies = list(pos_accuracies.values())
            acc_std = np.std(accuracies) if len(accuracies) > 1 else 0
            if acc_std > 0.1:
                defect = StrategyDefect(strategy.strategy_id)
                defect.defect_type = "position_imbalance"
                defect.defect_description = f"各位置性能不均衡，标准差: {acc_std:.3f}"
                defect.severity = "medium"
                defect.affected_positions = [
                    pos for pos, acc in pos_accuracies.items() 
                    if acc < np.mean(accuracies) - 0.05
                ]
                defect.suggested_fix = {
                    'action': 'balance_positions',
                    'adjust_weights': True,
                    'target_positions': defect.affected_positions
                }
                defects.append(defect)
        
        # 4. 检查超参数配置
        hp = strategy.hyperparameters
        if hp.get('max_depth', 0) > 15:
            defect = StrategyDefect(strategy.strategy_id)
            defect.defect_type = "excessive_depth"
            defect.defect_description = f"树深度过大({hp.get('max_depth')})，可能过拟合"
            defect.severity = "medium"
            defect.suggested_fix = {
                'action': 'adjust_depth',
                'new_max_depth': 10
            }
            defects.append(defect)
        
        # 5. 检查特征配置
        feat_cfg = strategy.feature_config
        if feat_cfg.get('select_top', 0) is not None and feat_cfg.get('select_top', 0) < 20:
            defect = StrategyDefect(strategy.strategy_id)
            defect.defect_type = "insufficient_features"
            defect.defect_description = f"特征数量过少({feat_cfg.get('select_top')})，可能信息不足"
            defect.severity = "medium"
            defect.suggested_fix = {
                'action': 'add_features',
                'new_select_top': 40
            }
            defects.append(defect)
        
        # 保存缺陷
        if defects:
            self.defects[strategy.strategy_id] = defects
            logger.info(f"策略 {strategy.strategy_id} 发现 {len(defects)} 个缺陷")
        
        return defects
    
    def review_all_strategies(self) -> Dict[str, List[StrategyDefect]]:
        """审查所有策略"""
        logger.info("=" * 80)
        logger.info("开始审查所有深度训练策略")
        logger.info("=" * 80)
        
        all_defects = {}
        strategies = self.deep_manager.get_all_strategies()
        
        for strategy in strategies:
            if strategy.evaluated:
                defects = self.review_strategy(strategy)
                if defects:
                    all_defects[strategy.strategy_id] = defects
        
        self.save_data()
        logger.info(f"审查完成，共发现 {len(all_defects)} 个策略有缺陷")
        return all_defects
    
    def generate_adjustment_proposal(self, strategy: StrategyCombination, defects: List[StrategyDefect]) -> AdjustmentProposal:
        """
        基于缺陷生成调整方案
        """
        proposal_id = f"proposal_{strategy.strategy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        proposal = AdjustmentProposal(proposal_id)
        proposal.base_strategy_id = strategy.strategy_id
        
        # 整合所有缺陷的修复建议
        adjustments = {
            'feature_config': strategy.feature_config.copy(),
            'hyperparameters': strategy.hyperparameters.copy(),
            'window_config': strategy.window_config.copy(),
            'model_config': strategy.model_config.copy()
        }
        
        # 按严重程度排序缺陷
        sorted_defects = sorted(defects, key=lambda d: ['low', 'medium', 'high', 'critical'].index(d.severity), reverse=True)
        
        expected_improvement = 0.0
        
        for defect in sorted_defects:
            fix = defect.suggested_fix
            action = fix.get('action', '')
            
            if action == 'reduce_overfitting':
                # 降低过拟合
                hp = adjustments['hyperparameters']
                hp['n_estimators'] = max(50, hp.get('n_estimators', 200) + fix.get('adjust_n_estimators', 0))
                hp['max_depth'] = max(3, hp.get('max_depth', 8) + fix.get('adjust_max_depth', 0))
                hp['subsample'] = min(0.9, hp.get('subsample', 0.85) - 0.05)
                expected_improvement += 0.02
                
            elif action == 'reduce_underfitting':
                # 减少欠拟合
                hp = adjustments['hyperparameters']
                hp['n_estimators'] = hp.get('n_estimators', 200) + fix.get('adjust_n_estimators', 0)
                hp['max_depth'] = hp.get('max_depth', 8) + fix.get('adjust_max_depth', 0)
                if fix.get('add_more_features'):
                    fc = adjustments['feature_config']
                    fc['select_top'] = min(100, (fc.get('select_top') or 50) + 20)
                expected_improvement += 0.03
                
            elif action == 'balance_positions':
                # 平衡各位置
                adjustments['position_specific_adjustment'] = {
                    'enabled': True,
                    'target_positions': fix.get('target_positions', [])
                }
                expected_improvement += 0.015
                
            elif action == 'adjust_depth':
                # 调整深度
                hp = adjustments['hyperparameters']
                hp['max_depth'] = fix.get('new_max_depth', 10)
                expected_improvement += 0.01
                
            elif action == 'add_features':
                # 增加特征
                fc = adjustments['feature_config']
                fc['select_top'] = fix.get('new_select_top', 40)
                expected_improvement += 0.02
        
        proposal.adjustments = adjustments
        proposal.expected_improvement = expected_improvement
        proposal.priority = int(expected_improvement * 100)
        
        # 保存方案
        self.proposals[proposal_id] = proposal
        
        logger.info(f"为策略 {strategy.strategy_id} 生成调整方案 {proposal_id}，预期提升: {expected_improvement:.2%}")
        
        return proposal
    
    def generate_all_proposals(self) -> List[AdjustmentProposal]:
        """为所有有缺陷的策略生成调整方案"""
        logger.info("=" * 80)
        logger.info("开始生成调整方案")
        logger.info("=" * 80)
        
        all_proposals = []
        
        for strategy_id, defects in self.defects.items():
            strategy = self.deep_manager.get_strategy(strategy_id)
            if strategy:
                proposal = self.generate_adjustment_proposal(strategy, defects)
                all_proposals.append(proposal)
        
        # 按优先级排序
        all_proposals.sort(key=lambda p: p.priority, reverse=True)
        
        self.save_data()
        logger.info(f"共生成 {len(all_proposals)} 个调整方案")
        return all_proposals
    
    def get_top_proposals(self, n: int = 3) -> List[AdjustmentProposal]:
        """获取Top N调整方案"""
        sorted_proposals = sorted(
            [p for p in self.proposals.values() if not p.implemented],
            key=lambda p: p.priority,
            reverse=True
        )
        return sorted_proposals[:n]
    
    def implement_proposal(self, proposal_id: str) -> Optional[StrategyCombination]:
        """实施方案，生成新的策略"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            logger.warning(f"方案 {proposal_id} 不存在")
            return None
        
        base_strategy = self.deep_manager.get_strategy(proposal.base_strategy_id)
        if not base_strategy:
            logger.warning(f"基础策略 {proposal.base_strategy_id} 不存在")
            return None
        
        # 创建新策略
        new_strategy_id = f"{base_strategy.strategy_id}_optimized"
        new_strategy = StrategyCombination(new_strategy_id)
        
        # 应用调整
        adjustments = proposal.adjustments
        new_strategy.feature_config = adjustments.get('feature_config', base_strategy.feature_config).copy()
        new_strategy.hyperparameters = adjustments.get('hyperparameters', base_strategy.hyperparameters).copy()
        new_strategy.window_config = adjustments.get('window_config', base_strategy.window_config).copy()
        new_strategy.model_config = adjustments.get('model_config', base_strategy.model_config).copy()
        
        # 保存新策略
        self.deep_manager.strategies[new_strategy_id] = new_strategy
        self.deep_manager.save_strategies()
        
        # 标记方案为已实施
        proposal.implemented = True
        self.save_data()
        
        logger.info(f"已实施方案 {proposal_id}，生成新策略 {new_strategy_id}")
        return new_strategy
    
    def get_adjustment_summary(self) -> Dict:
        """获取调整方案总结"""
        total_proposals = len(self.proposals)
        implemented = sum(1 for p in self.proposals.values() if p.implemented)
        pending = total_proposals - implemented
        
        if self.proposals:
            avg_improvement = np.mean([p.expected_improvement for p in self.proposals.values()])
            top_proposal = self.get_top_proposals(1)[0] if pending > 0 else None
        else:
            avg_improvement = 0
            top_proposal = None
        
        return {
            'total_proposals': total_proposals,
            'implemented': implemented,
            'pending': pending,
            'average_expected_improvement': avg_improvement,
            'top_proposal': top_proposal.to_dict() if top_proposal else None,
            'defect_summary': {
                sid: len(ds) for sid, ds in self.defects.items()
            }
        }
