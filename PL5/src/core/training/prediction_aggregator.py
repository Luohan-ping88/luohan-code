"""
预测链路聚合器 - V11
实现各个环节佐证预测到最终预测的链路聚合，而不是各自为战。
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from collections import Counter

# 首先确保正确的目录
_current_file = Path(__file__)
_project_root = _current_file.parent.parent.parent
LOGS_DIR = _project_root / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

from src.core.utils.logger import get_logger
from src.core.training.deep_training_manager import DeepTrainingManager, StrategyCombination
from src.core.training.incremental_training_manager import IncrementalTrainingManager

logger = get_logger('prediction_aggregator')


class PredictionEvidence:
    """单一佐证预测"""
    def __init__(self, source: str):
        self.source = source  # 来源：first_verification, second_verification, third_verification, deep_strategy等
        self.predictions = {}  # {position: {top_k: [...], probabilities: {...}}}
        self.confidence = 0.0
        self.timestamp = datetime.now().isoformat()
        self.strategy_id = ""
        
    def to_dict(self) -> Dict:
        return {
            'source': self.source,
            'predictions': self.predictions,
            'confidence': self.confidence,
            'timestamp': self.timestamp,
            'strategy_id': self.strategy_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PredictionEvidence':
        evidence = cls(data.get('source', 'unknown'))
        evidence.predictions = data.get('predictions', {})
        evidence.confidence = data.get('confidence', 0.0)
        evidence.timestamp = data.get('timestamp', datetime.now().isoformat())
        evidence.strategy_id = data.get('strategy_id', '')
        return evidence


class AggregatedPrediction:
    """聚合后的预测结果"""
    def __init__(self):
        self.position_predictions = {}  # 各位置的最终预测
        self.confidence_scores = {}  # 各位置的置信度
        self.evidence_used = []  # 使用的佐证来源
        self.aggregation_method = ""
        self.created_at = datetime.now().isoformat()
        
    def to_dict(self) -> Dict:
        return {
            'position_predictions': self.position_predictions,
            'confidence_scores': self.confidence_scores,
            'evidence_used': self.evidence_used,
            'aggregation_method': self.aggregation_method,
            'created_at': self.created_at
        }


class PredictionAggregator:
    """预测链路聚合器"""
    
    def __init__(self, deep_manager: Optional[DeepTrainingManager] = None):
        self.deep_manager = deep_manager or DeepTrainingManager()
        self.evidences: Dict[str, PredictionEvidence] = {}
        self.evidences_store_path = LOGS_DIR / "prediction_evidences.json"
        self.load_evidences()
        
    def load_evidences(self):
        """加载佐证数据"""
        if self.evidences_store_path.exists():
            try:
                with open(self.evidences_store_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for source, evidence_data in data.get('evidences', {}).items():
                        self.evidences[source] = PredictionEvidence.from_dict(evidence_data)
                logger.info(f"已加载 {len(self.evidences)} 个佐证预测")
            except Exception as e:
                logger.warning(f"加载佐证数据失败: {e}")
                
    def save_evidences(self):
        """保存佐证数据"""
        try:
            data = {
                'evidences': {s: e.to_dict() for s, e in self.evidences.items()},
                'saved_at': datetime.now().isoformat()
            }
            with open(self.evidences_store_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"已保存 {len(self.evidences)} 个佐证预测")
        except Exception as e:
            logger.error(f"保存佐证数据失败: {e}")
            
    def add_evidence(self, evidence: PredictionEvidence):
        """添加佐证预测"""
        self.evidences[evidence.source] = evidence
        self.save_evidences()
        logger.info(f"添加佐证预测: {evidence.source}")
        
    def load_evidence_from_file(self, source: str, file_path: Path) -> Optional[PredictionEvidence]:
        """从文件加载佐证预测"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            evidence = PredictionEvidence(source)
            evidence.predictions = data.get('predictions', {})
            evidence.confidence = data.get('confidence', 0.5)
            evidence.timestamp = data.get('timestamp', datetime.now().isoformat())
            evidence.strategy_id = data.get('strategy_id', '')
            
            self.add_evidence(evidence)
            return evidence
        except Exception as e:
            logger.warning(f"从文件 {file_path} 加载佐证失败: {e}")
            return None
            
    def aggregate_by_voting(self, position: str, evidences: List[PredictionEvidence], top_k: int = 8) -> Tuple[List[int], float]:
        """
        基于投票的聚合方法
        对各佐证的top_k预测进行加权投票
        """
        all_candidates = []
        weights = []
        
        for evidence in evidences:
            pred = evidence.predictions.get(position, {})
            candidates = pred.get('top_k', [])
            weight = evidence.confidence
            
            for i, candidate in enumerate(candidates):
                all_candidates.append(candidate)
                # 排名越靠前权重越大
                rank_weight = weight * (1.0 - i * 0.1)  # 每降一名权重减10%
                weights.append(max(0.1, rank_weight))
        
        if not all_candidates:
            return [], 0.0
        
        # 加权计数
        weighted_counts = Counter()
        for candidate, weight in zip(all_candidates, weights):
            weighted_counts[candidate] += weight
        
        # 按权重排序
        sorted_candidates = sorted(weighted_counts.items(), key=lambda x: x[1], reverse=True)
        top_candidates = [c for c, _ in sorted_candidates[:top_k]]
        
        # 计算置信度 - 基于票数集中度
        total_weight = sum(weighted_counts.values())
        if total_weight > 0:
            top1_weight = sorted_candidates[0][1] if sorted_candidates else 0
            top3_weight = sum(w for _, w in sorted_candidates[:3])
            confidence = (top1_weight + top3_weight * 0.5) / total_weight
        else:
            confidence = 0.5
        
        return top_candidates, min(1.0, confidence)
    
    def aggregate_by_strategy_performance(self, position: str, evidences: List[PredictionEvidence], top_k: int = 8) -> Tuple[List[int], float]:
        """
        基于策略历史性能的聚合方法
        优先使用历史表现更好的策略的预测
        """
        # 获取策略性能
        strategy_performance = {}
        for evidence in evidences:
            if evidence.strategy_id:
                strategy = self.deep_manager.get_strategy(evidence.strategy_id)
                if strategy:
                    pos_acc = strategy.performance.get('position_accuracies', {}).get(position, 0.3)
                    strategy_performance[evidence.strategy_id] = pos_acc
        
        if not strategy_performance:
            # 降级到投票法
            return self.aggregate_by_voting(position, evidences, top_k)
        
        # 按策略性能加权
        all_candidates = []
        weights = []
        
        for evidence in evidences:
            pred = evidence.predictions.get(position, {})
            candidates = pred.get('top_k', [])
            
            # 基础权重
            base_weight = evidence.confidence
            
            # 策略性能权重
            if evidence.strategy_id in strategy_performance:
                strategy_weight = strategy_performance[evidence.strategy_id]
                combined_weight = base_weight * (0.5 + strategy_weight * 0.5)
            else:
                combined_weight = base_weight
            
            for i, candidate in enumerate(candidates):
                all_candidates.append(candidate)
                rank_weight = combined_weight * (1.0 - i * 0.08)
                weights.append(max(0.1, rank_weight))
        
        if not all_candidates:
            return [], 0.0
        
        # 加权计数
        weighted_counts = Counter()
        for candidate, weight in zip(all_candidates, weights):
            weighted_counts[candidate] += weight
        
        sorted_candidates = sorted(weighted_counts.items(), key=lambda x: x[1], reverse=True)
        top_candidates = [c for c, _ in sorted_candidates[:top_k]]
        
        # 计算置信度 - 考虑策略性能
        total_weight = sum(weighted_counts.values())
        if total_weight > 0:
            avg_performance = np.mean(list(strategy_performance.values()))
            confidence = 0.5 + avg_performance * 0.5
        else:
            confidence = 0.5
        
        return top_candidates, min(1.0, confidence)
    
    def aggregate_by_consensus(self, position: str, evidences: List[PredictionEvidence], top_k: int = 8) -> Tuple[List[int], float]:
        """
        基于一致性的聚合方法
        优先选择多个佐证都推荐的候选
        """
        if len(evidences) < 2:
            # 佐证太少，降级到投票法
            return self.aggregate_by_voting(position, evidences, top_k)
        
        # 计算各候选出现的佐证数量
        candidate_sources = {}
        for evidence in evidences:
            pred = evidence.predictions.get(position, {})
            candidates = pred.get('top_k', [])
            for candidate in candidates:
                if candidate not in candidate_sources:
                    candidate_sources[candidate] = set()
                candidate_sources[candidate].add(evidence.source)
        
        # 计算候选得分：出现次数 + 排名权重
        candidate_scores = Counter()
        for evidence in evidences:
            pred = evidence.predictions.get(position, {})
            candidates = pred.get('top_k', [])
            weight = evidence.confidence
            
            for i, candidate in enumerate(candidates):
                # 基础得分：出现的佐证数量
                base_score = len(candidate_sources.get(candidate, []))
                # 排名加分
                rank_bonus = (len(candidates) - i) / len(candidates)
                total_score = base_score + rank_bonus * weight
                candidate_scores[candidate] += total_score
        
        sorted_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        top_candidates = [c for c, _ in sorted_candidates[:top_k]]
        
        # 计算置信度 - 基于一致性
        if sorted_candidates:
            top_candidate = sorted_candidates[0][0]
            consensus_count = len(candidate_sources.get(top_candidate, []))
            confidence = consensus_count / len(evidences)
        else:
            confidence = 0.5
        
        return top_candidates, min(1.0, confidence)
    
    def aggregate_predictions(self, method: str = "hybrid") -> AggregatedPrediction:
        """
        聚合所有佐证预测
        方法：
        - voting: 纯投票法
        - strategy_performance: 基于策略性能
        - consensus: 基于一致性
        - hybrid: 混合方法（默认）
        """
        logger.info("=" * 80)
        logger.info(f"开始聚合预测，方法: {method}")
        logger.info("=" * 80)
        
        aggregated = AggregatedPrediction()
        aggregated.aggregation_method = method
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        valid_evidences = list(self.evidences.values())
        
        if not valid_evidences:
            logger.warning("没有可用的佐证预测")
            return aggregated
        
        logger.info(f"使用 {len(valid_evidences)} 个佐证: {[e.source for e in valid_evidences]}")
        
        for position in positions:
            if method == "voting":
                top_k, confidence = self.aggregate_by_voting(position, valid_evidences)
            elif method == "strategy_performance":
                top_k, confidence = self.aggregate_by_strategy_performance(position, valid_evidences)
            elif method == "consensus":
                top_k, confidence = self.aggregate_by_consensus(position, valid_evidences)
            else:  # hybrid
                # 混合方法：尝试多种方法，取一致性最高的
                results = []
                results.append(self.aggregate_by_voting(position, valid_evidences))
                results.append(self.aggregate_by_strategy_performance(position, valid_evidences))
                results.append(self.aggregate_by_consensus(position, valid_evidences))
                
                # 选择置信度最高的
                best_idx = np.argmax([r[1] for r in results])
                top_k, confidence = results[best_idx]
            
            aggregated.position_predictions[position] = {
                'top_k': top_k,
                'top_8': top_k[:8],
                'top_5': top_k[:5],
                'top_3': top_k[:3],
                'top_1': top_k[0] if top_k else None
            }
            aggregated.confidence_scores[position] = confidence
            
            logger.info(f"  {position} 位: 预测={top_k[:5]}, 置信度={confidence:.2%}")
        
        aggregated.evidence_used = [e.source for e in valid_evidences]
        
        # 保存聚合结果
        result_path = LOGS_DIR / "aggregated_prediction.json"
        try:
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(aggregated.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"聚合预测已保存到 {result_path}")
        except Exception as e:
            logger.error(f"保存聚合预测失败: {e}")
        
        return aggregated
    
    def get_aggregation_summary(self) -> Dict:
        """获取聚合总结"""
        return {
            'total_evidences': len(self.evidences),
            'evidence_sources': list(self.evidences.keys()),
            'evidence_timestamps': {
                s: e.timestamp for s, e in self.evidences.items()
            },
            'evidence_confidences': {
                s: e.confidence for s, e in self.evidences.items()
            }
        }
