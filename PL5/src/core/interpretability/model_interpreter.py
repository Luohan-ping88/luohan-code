"""
模型解释器模块 V1.0

提供模型决策的可解释性分析，包括：
1. 特征重要性分析 - 全局和局部特征贡献度
2. 决策路径追踪 - 追踪模型从输入到预测的完整决策链
3. 预测归因分析 - 量化各因素对最终预测的贡献
4. 模型行为可视化 - 生成可读的决策逻辑描述
5. 多维数据分析 - 跨位置/跨模型的综合解释

确保模型预测的透明度和可信度。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

_INTERPRETATION_HISTORY_PATH = Path(__file__).parent.parent.parent.parent / "models" / "interpretation_history.json"


class InterpretationLevel(Enum):
    """解释详细程度"""
    BRIEF = "brief"        # 简要（关键因素）
    STANDARD = "standard"  # 标准（Top-10因素+路径）
    DETAILED = "detailed"  # 详细（全量分析）


class ContributionType(Enum):
    """贡献类型"""
    POSITIVE = "positive"    # 正向贡献（推高概率）
    NEGATIVE = "negative"    # 负向贡献（降低概率）
    NEUTRAL = "neutral"      # 中性贡献


@dataclass
class FeatureContribution:
    """单个特征贡献"""
    feature_name: str
    feature_value: float
    contribution: float                    # 贡献度（SHAP-like值）
    contribution_type: ContributionType
    rank: int = 0                          # 贡献排名
    description: str = ""                  # 人类可读描述

    def to_dict(self) -> Dict[str, Any]:
        return {
            'feature_name': self.feature_name,
            'feature_value': round(float(self.feature_value), 6),
            'contribution': round(float(self.contribution), 6),
            'contribution_type': self.contribution_type.value,
            'rank': self.rank,
            'description': self.description,
        }


@dataclass
class DecisionStep:
    """决策路径中的单个步骤"""
    step_index: int
    model_name: str                        # 来源模型（stacking/hmm/copula/bsts/mamba/itransformer）
    action: str                            # 动作描述
    input_summary: str                     # 输入摘要
    output_summary: str                    # 输出摘要
    confidence: float = 0.0                # 本步骤置信度
    weight: float = 0.0                    # 本步骤在最终决策中的权重

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_index': self.step_index,
            'model_name': self.model_name,
            'action': self.action,
            'input_summary': self.input_summary,
            'output_summary': self.output_summary,
            'confidence': round(float(self.confidence), 4),
            'weight': round(float(self.weight), 4),
        }


@dataclass
class PositionInterpretation:
    """单位置预测解释"""
    position: str                          # wan/qian/bai/shi/ge
    predicted_top_k: List[int] = field(default_factory=list)
    confidence: float = 0.0
    model_weights: Dict[str, float] = field(default_factory=dict)
    feature_contributions: List[FeatureContribution] = field(default_factory=list)
    decision_path: List[DecisionStep] = field(default_factory=list)
    model_outputs: Dict[str, Any] = field(default_factory=dict)  # 各子模型的输出
    summary: str = ""                      # 人类可读的预测摘要

    def to_dict(self) -> Dict[str, Any]:
        return {
            'position': self.position,
            'predicted_top_k': self.predicted_top_k,
            'confidence': round(float(self.confidence), 4),
            'model_weights': {k: round(float(v), 4) for k, v in self.model_weights.items()},
            'feature_contributions': [c.to_dict() for c in self.feature_contributions],
            'decision_path': [s.to_dict() for s in self.decision_path],
            'model_outputs': self.model_outputs,
            'summary': self.summary,
        }


@dataclass
class PredictionInterpretation:
    """完整预测解释报告"""
    prediction_period: str = ""
    timestamp: str = ""
    position_interpretations: Dict[str, PositionInterpretation] = field(default_factory=dict)
    global_feature_importance: List[FeatureContribution] = field(default_factory=list)
    cross_position_analysis: Dict[str, Any] = field(default_factory=dict)
    overall_confidence: float = 0.0
    interpretation_level: InterpretationLevel = InterpretationLevel.STANDARD
    risk_assessment: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'prediction_period': self.prediction_period,
            'timestamp': self.timestamp,
            'position_interpretations': {k: v.to_dict() for k, v in self.position_interpretations.items()},
            'global_feature_importance': [c.to_dict() for c in self.global_feature_importance],
            'cross_position_analysis': self.cross_position_analysis,
            'overall_confidence': round(float(self.overall_confidence), 4),
            'interpretation_level': self.interpretation_level.value,
            'risk_assessment': self.risk_assessment,
        }

    def to_readable_report(self) -> str:
        """生成人类可读的解释报告"""
        lines = []
        lines.append("=" * 70)
        lines.append("模型预测解释报告")
        lines.append(f"预测期号: {self.prediction_period}")
        lines.append(f"生成时间: {self.timestamp}")
        lines.append(f"整体置信度: {self.overall_confidence:.2%}")
        lines.append("=" * 70)

        for pos, interp in self.position_interpretations.items():
            pos_names = {'wan': '万位', 'qian': '千位', 'bai': '百位', 'shi': '十位', 'ge': '个位'}
            lines.append(f"\n【{pos_names.get(pos, pos)}位】预测: Top-8 = {interp.predicted_top_k}")
            lines.append(f"  置信度: {interp.confidence:.2%}")
            lines.append(f"  摘要: {interp.summary}")

            if interp.model_weights:
                lines.append(f"  模型权重:")
                for model, weight in sorted(interp.model_weights.items(), key=lambda x: -x[1]):
                    lines.append(f"    {model}: {weight:.2%}")

            if interp.feature_contributions:
                lines.append(f"  关键贡献特征 (Top-5):")
                for c in interp.feature_contributions[:5]:
                    arrow = "↑" if c.contribution_type == ContributionType.POSITIVE else "↓"
                    lines.append(f"    {c.rank}. {c.feature_name} = {c.feature_value:.4f} "
                                 f"{arrow} 贡献={c.contribution:.4f}")

            if interp.decision_path:
                lines.append(f"  决策路径:")
                for step in interp.decision_path:
                    lines.append(f"    [{step.step_index}] {step.model_name}: {step.action}")
                    lines.append(f"        {step.output_summary} (权重={step.weight:.2%})")

        if self.cross_position_analysis:
            lines.append(f"\n【跨位置分析】")
            for key, value in self.cross_position_analysis.items():
                lines.append(f"  {key}: {value}")

        if self.risk_assessment:
            lines.append(f"\n【风险评估】{self.risk_assessment}")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


class FeatureImportanceAnalyzer:
    """特征重要性分析器

    提供全局和局部特征重要性分析。
    """

    @staticmethod
    def compute_permutation_importance(
        model_predict_fn,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        n_repeats: int = 5,
        random_state: int = 42
    ) -> List[FeatureContribution]:
        """排列特征重要性（模型无关方法）

        通过打乱每个特征的值，观察预测性能下降程度来衡量重要性。
        """
        rng = np.random.RandomState(random_state)
        baseline_score = FeatureImportanceAnalyzer._compute_accuracy(model_predict_fn, X, y)

        contributions = []
        for i, name in enumerate(feature_names):
            score_drops = []
            X_permuted = X.copy()

            for _ in range(n_repeats):
                X_permuted[:, i] = rng.permutation(X_permuted[:, i])
                permuted_score = FeatureImportanceAnalyzer._compute_accuracy(model_predict_fn, X_permuted, y)
                score_drops.append(baseline_score - permuted_score)

            mean_drop = float(np.mean(score_drops))
            std_drop = float(np.std(score_drops))

            contrib_type = (ContributionType.POSITIVE if mean_drop > 0.01
                           else ContributionType.NEGATIVE if mean_drop < -0.01
                           else ContributionType.NEUTRAL)

            contributions.append(FeatureContribution(
                feature_name=name,
                feature_value=float(np.mean(X[:, i])),
                contribution=mean_drop,
                contribution_type=contrib_type,
                description=f"排列后准确率下降 {mean_drop:.4f}±{std_drop:.4f}"
            ))

        # 排序并设置排名
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        for i, c in enumerate(contributions, 1):
            c.rank = i

        return contributions

    @staticmethod
    def compute_local_contribution(
        feature_values: np.ndarray,
        feature_weights: np.ndarray,
        feature_names: List[str],
        bias: float = 0.0
    ) -> List[FeatureContribution]:
        """局部特征贡献（基于线性近似）

        contribution_i = weight_i * (value_i - mean_i)

        Args:
            feature_values: 单样本特征值
            feature_weights: 特征权重（模型系数）
            feature_names: 特征名
            bias: 偏置项
        """
        contributions = []
        for i, name in enumerate(feature_names):
            val = float(feature_values[i]) if i < len(feature_values) else 0.0
            weight = float(feature_weights[i]) if i < len(feature_weights) else 0.0
            contribution = weight * val

            contrib_type = (ContributionType.POSITIVE if contribution > 0
                           else ContributionType.NEGATIVE if contribution < 0
                           else ContributionType.NEUTRAL)

            contributions.append(FeatureContribution(
                feature_name=name,
                feature_value=val,
                contribution=contribution,
                contribution_type=contrib_type,
                description=f"权重={weight:.4f}, 值={val:.4f}, 贡献={contribution:.4f}"
            ))

        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        for i, c in enumerate(contributions, 1):
            c.rank = i

        return contributions

    @staticmethod
    def compute_tree_importance(
        tree_models: List[Any],
        feature_names: List[str]
    ) -> List[FeatureContribution]:
        """树模型特征重要性（基于不纯度减少）

        Args:
            tree_models: sklearn 树模型列表（含 feature_importances_ 属性）
            feature_names: 特征名
        """
        importances = np.zeros(len(feature_names))

        for model in tree_models:
            if hasattr(model, 'feature_importances_'):
                fi = model.feature_importances_
                if len(fi) == len(feature_names):
                    importances += fi

        if len(tree_models) > 0:
            importances /= len(tree_models)

        contributions = []
        for i, name in enumerate(feature_names):
            val = float(importances[i])
            contrib_type = (ContributionType.POSITIVE if val > 0.01
                           else ContributionType.NEUTRAL)

            contributions.append(FeatureContribution(
                feature_name=name,
                feature_value=0.0,  # 树模型重要性不绑定具体值
                contribution=val,
                contribution_type=contrib_type,
                description=f"不纯度减少重要性={val:.4f}"
            ))

        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        for i, c in enumerate(contributions, 1):
            c.rank = i

        return contributions

    @staticmethod
    def _compute_accuracy(predict_fn, X, y) -> float:
        """计算预测准确率"""
        try:
            predictions = predict_fn(X)
            if isinstance(predictions, np.ndarray) and predictions.ndim > 1:
                predictions = np.argmax(predictions, axis=1)
            return float(np.mean(predictions == y))
        except Exception:
            return 0.0


class DecisionPathTracer:
    """决策路径追踪器

    追踪模型从输入到预测的完整决策链。
    """

    @staticmethod
    def trace_ensemble_decision(
        position: str,
        model_outputs: Dict[str, np.ndarray],
        model_weights: Dict[str, float],
        final_prediction: List[int]
    ) -> List[DecisionStep]:
        """追踪集成模型的决策路径

        Args:
            position: 位置名
            model_outputs: 各子模型的输出概率 {model_name: proba_array}
            model_weights: 各子模型的权重
            final_prediction: 最终预测的 Top-K

        Returns:
            决策步骤列表
        """
        steps = []
        step_idx = 0

        # 步骤0: 输入特征摘要
        steps.append(DecisionStep(
            step_index=step_idx,
            model_name="input",
            action="特征输入",
            input_summary=f"位置={position}, 特征维度={next(iter(model_outputs.values()), np.array([])).shape[-1] if model_outputs else 0}",
            output_summary="特征向量已就绪",
            confidence=1.0,
            weight=0.0
        ))
        step_idx += 1

        # 步骤1~N: 各子模型预测
        for model_name, proba in sorted(model_outputs.items(), key=lambda x: -model_weights.get(x[0], 0)):
            weight = model_weights.get(model_name, 0.0)
            top3 = np.argsort(proba)[::-1][:3] if proba is not None else []

            # 计算模型置信度（Top-1 与 Top-2 概率差）
            if proba is not None and len(proba) > 1:
                sorted_p = np.sort(proba)[::-1]
                confidence = float(sorted_p[0] - sorted_p[1]) if len(sorted_p) > 1 else float(sorted_p[0])
            else:
                confidence = 0.0

            steps.append(DecisionStep(
                step_index=step_idx,
                model_name=model_name,
                action=f"{model_name}模型预测",
                input_summary="输入特征向量",
                output_summary=f"Top-3={[int(x) for x in top3]}, "
                              f"P(top1)={float(np.max(proba)) if proba is not None else 0:.4f}",
                confidence=confidence,
                weight=weight
            ))
            step_idx += 1

        # 最终步骤: 加权融合
        steps.append(DecisionStep(
            step_index=step_idx,
            model_name="ensemble",
            action="加权融合",
            input_summary=f"{len(model_outputs)}个模型输出",
            output_summary=f"最终Top-K={final_prediction}",
            confidence=float(np.mean([s.confidence for s in steps[1:]])) if len(steps) > 1 else 0.0,
            weight=1.0
        ))

        return steps


class CrossPositionAnalyzer:
    """跨位置分析器

    分析各位置预测之间的关联和一致性。
    """

    @staticmethod
    def analyze(
        position_interpretations: Dict[str, PositionInterpretation]
    ) -> Dict[str, Any]:
        """执行跨位置分析

        Returns:
            分析结果字典
        """
        result = {}

        # 1. 置信度一致性
        confidences = {pos: interp.confidence for pos, interp in position_interpretations.items()}
        if confidences:
            result['confidence_consistency'] = {
                'mean': float(np.mean(list(confidences.values()))),
                'std': float(np.std(list(confidences.values()))),
                'min_pos': min(confidences, key=confidences.get),
                'max_pos': max(confidences, key=confidences.get),
            }

        # 2. 模型权重一致性
        weight_diffs = []
        positions = list(position_interpretations.keys())
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                w1 = position_interpretations[positions[i]].model_weights
                w2 = position_interpretations[positions[j]].model_weights
                common_models = set(w1.keys()) & set(w2.keys())
                if common_models:
                    diff = np.mean([abs(w1[m] - w2[m]) for m in common_models])
                    weight_diffs.append(float(diff))

        if weight_diffs:
            result['model_weight_consistency'] = {
                'avg_diff': float(np.mean(weight_diffs)),
                'max_diff': float(np.max(weight_diffs)),
                'assessment': '高一致性' if np.mean(weight_diffs) < 0.1 else
                             '中等一致性' if np.mean(weight_diffs) < 0.3 else '低一致性',
            }

        # 3. 预测号码重复分析
        all_predicted = []
        for interp in position_interpretations.values():
            all_predicted.extend(interp.predicted_top_k[:3])  # Top-3

        if all_predicted:
            from collections import Counter
            counter = Counter(all_predicted)
            result['number_distribution'] = {
                'top3_numbers': counter.most_common(5),
                'unique_count': len(set(all_predicted)),
                'total_count': len(all_predicted),
            }

        # 4. 关键特征重叠分析
        all_top_features = set()
        feature_overlap = {}
        for pos, interp in position_interpretations.items():
            top_features = {c.feature_name for c in interp.feature_contributions[:5]}
            overlap = all_top_features & top_features
            feature_overlap[pos] = len(overlap)
            all_top_features.update(top_features)

        result['feature_overlap'] = {
            'shared_top_features': len(all_top_features),
            'overlap_by_position': feature_overlap,
        }

        return result


class ModelInterpreter:
    """模型解释器主类

    整合特征重要性分析、决策路径追踪和跨位置分析，
    提供完整的模型可解释性输出。
    """

    def __init__(
        self,
        default_level: InterpretationLevel = InterpretationLevel.STANDARD,
        max_features_to_show: int = 20,
        history_path: Optional[Path] = None
    ):
        """
        Args:
            default_level: 默认解释详细程度
            max_features_to_show: 最多展示的特征数量
            history_path: 解释历史持久化路径
        """
        self.default_level = default_level
        self.max_features_to_show = max_features_to_show
        self.history_path = history_path or _INTERPRETATION_HISTORY_PATH

        self.feature_analyzer = FeatureImportanceAnalyzer()
        self.path_tracer = DecisionPathTracer()
        self.cross_analyzer = CrossPositionAnalyzer()

        # 解释历史
        self.interpretation_history: List[Dict] = []
        self._load_history()

        logger.info(f"模型解释器初始化完成 (级别={default_level.value})")

    def interpret_prediction(
        self,
        prediction_result: Dict[str, Any],
        feature_values: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        feature_weights: Optional[Dict[str, np.ndarray]] = None,
        model_outputs: Optional[Dict[str, Dict[str, np.ndarray]]] = None,
        level: Optional[InterpretationLevel] = None
    ) -> PredictionInterpretation:
        """解释预测结果

        Args:
            prediction_result: 预测结果字典，包含各位置的 predictions
            feature_values: 特征值矩阵 (n_positions, n_features) 或单行
            feature_names: 特征名列表
            feature_weights: 各位置的特征权重 {position: weight_array}
            model_outputs: 各位置各模型的输出 {position: {model_name: proba}}
            level: 解释详细程度

        Returns:
            完整预测解释
        """
        level = level or self.default_level
        interpretation = PredictionInterpretation(
            prediction_period=str(prediction_result.get('next_period', '')),
            interpretation_level=level,
        )

        predictions = prediction_result.get('predictions', {})
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']

        # 逐位置解释
        for pos in positions:
            if pos not in predictions:
                continue

            pred = predictions[pos]
            top_k = pred.get('top_k', [])
            weights = pred.get('weights_used', {})
            confidence = pred.get('confidence', 0.0)

            pos_interp = PositionInterpretation(
                position=pos,
                predicted_top_k=top_k,
                confidence=confidence,
                model_weights=weights,
            )

            # 特征贡献分析
            if feature_values is not None and feature_names is not None:
                pos_features = self._get_position_features(feature_values, pos, len(feature_names))
                pos_weights = None
                if feature_weights and pos in feature_weights:
                    pos_weights = feature_weights[pos]

                if pos_weights is not None:
                    contributions = self.feature_analyzer.compute_local_contribution(
                        pos_features, pos_weights, feature_names
                    )
                else:
                    # 无权重时使用简化贡献度（基于特征值大小）
                    contributions = self._compute_simple_contribution(pos_features, feature_names)

                # 按级别截断
                if level == InterpretationLevel.BRIEF:
                    contributions = contributions[:5]
                elif level == InterpretationLevel.STANDARD:
                    contributions = contributions[:10]

                pos_interp.feature_contributions = contributions

            # 决策路径追踪
            if model_outputs and pos in model_outputs:
                pos_model_outputs = model_outputs[pos]
                decision_path = self.path_tracer.trace_ensemble_decision(
                    position=pos,
                    model_outputs=pos_model_outputs,
                    model_weights=weights,
                    final_prediction=top_k
                )
                pos_interp.decision_path = decision_path
                pos_interp.model_outputs = {
                    m: {'top3': np.argsort(p)[::-1][:3].tolist() if p is not None else [],
                        'max_prob': float(np.max(p)) if p is not None else 0.0}
                    for m, p in pos_model_outputs.items()
                }
            else:
                # 简化决策路径（基于模型权重）
                pos_interp.decision_path = self._build_simplified_path(pos, weights, top_k)

            # 生成摘要
            pos_interp.summary = self._generate_position_summary(pos, top_k, confidence, weights)

            interpretation.position_interpretations[pos] = pos_interp

        # 跨位置分析
        if len(interpretation.position_interpretations) > 1:
            interpretation.cross_position_analysis = self.cross_analyzer.analyze(
                interpretation.position_interpretations
            )

        # 整体置信度
        confidences = [pi.confidence for pi in interpretation.position_interpretations.values()]
        interpretation.overall_confidence = float(np.mean(confidences)) if confidences else 0.0

        # 风险评估
        interpretation.risk_assessment = self._assess_risk(interpretation)

        # 持久化
        self._save_interpretation(interpretation)

        logger.info(f"预测解释完成: 期号={interpretation.prediction_period}, "
                    f"位置数={len(interpretation.position_interpretations)}, "
                    f"整体置信度={interpretation.overall_confidence:.2%}")

        return interpretation

    def _get_position_features(
        self,
        feature_values: np.ndarray,
        position: str,
        n_features: int
    ) -> np.ndarray:
        """获取指定位置的特征值"""
        if feature_values.ndim == 1:
            return feature_values
        elif feature_values.ndim == 2:
            pos_idx = {'wan': 0, 'qian': 1, 'bai': 2, 'shi': 3, 'ge': 4}.get(position, 0)
            if pos_idx < feature_values.shape[0]:
                return feature_values[pos_idx]
        return np.zeros(n_features)

    def _compute_simple_contribution(
        self,
        feature_values: np.ndarray,
        feature_names: List[str]
    ) -> List[FeatureContribution]:
        """简化的特征贡献度计算（无模型权重时）"""
        contributions = []
        # 使用特征值的绝对值作为贡献度的粗略估计
        abs_values = np.abs(feature_values)
        for i, name in enumerate(feature_names):
            val = float(feature_values[i]) if i < len(feature_values) else 0.0
            contribution = float(abs_values[i]) if i < len(abs_values) else 0.0
            contrib_type = (ContributionType.POSITIVE if val > 0
                           else ContributionType.NEGATIVE if val < 0
                           else ContributionType.NEUTRAL)
            contributions.append(FeatureContribution(
                feature_name=name,
                feature_value=val,
                contribution=contribution,
                contribution_type=contrib_type,
                description=f"特征值={val:.4f}"
            ))

        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        for i, c in enumerate(contributions, 1):
            c.rank = i
        return contributions

    def _build_simplified_path(
        self,
        position: str,
        model_weights: Dict[str, float],
        top_k: List[int]
    ) -> List[DecisionStep]:
        """构建简化决策路径（无详细模型输出时）"""
        steps = []
        steps.append(DecisionStep(
            step_index=0,
            model_name="input",
            action="特征输入",
            input_summary=f"位置={position}",
            output_summary="特征向量已就绪",
            confidence=1.0,
            weight=0.0
        ))

        for i, (model, weight) in enumerate(sorted(model_weights.items(), key=lambda x: -x[1]), 1):
            steps.append(DecisionStep(
                step_index=i,
                model_name=model,
                action=f"{model}模型预测",
                input_summary="输入特征向量",
                output_summary=f"权重={weight:.2%}",
                confidence=weight,
                weight=weight
            ))

        steps.append(DecisionStep(
            step_index=len(steps),
            model_name="ensemble",
            action="加权融合",
            input_summary=f"{len(model_weights)}个模型输出",
            output_summary=f"最终Top-K={top_k}",
            confidence=float(np.mean(list(model_weights.values()))) if model_weights else 0.0,
            weight=1.0
        ))

        return steps

    def _generate_position_summary(
        self,
        position: str,
        top_k: List[int],
        confidence: float,
        weights: Dict[str, float]
    ) -> str:
        """生成位置预测摘要"""
        pos_names = {'wan': '万位', 'qian': '千位', 'bai': '百位', 'shi': '十位', 'ge': '个位'}
        pos_name = pos_names.get(position, position)

        top3 = top_k[:3] if len(top_k) >= 3 else top_k
        dominant_model = max(weights, key=weights.get) if weights else "未知"

        conf_desc = "高置信度" if confidence > 0.7 else "中等置信度" if confidence > 0.4 else "低置信度"

        summary = (f"{pos_name}预测Top-3={top3}，{conf_desc}({confidence:.1%})，"
                  f"主导模型={dominant_model}({weights.get(dominant_model, 0):.1%})")
        return summary

    def _assess_risk(self, interpretation: PredictionInterpretation) -> str:
        """评估预测风险"""
        if interpretation.overall_confidence > 0.7:
            risk = "低风险：模型预测一致性高，各位置置信度充足"
        elif interpretation.overall_confidence > 0.4:
            risk = "中等风险：部分位置预测不确定性较高，建议关注低置信度位置"
        else:
            risk = "高风险：整体预测置信度偏低，建议结合其他分析方法"

        # 检查跨位置一致性
        cross = interpretation.cross_position_analysis
        if cross and 'model_weight_consistency' in cross:
            consistency = cross['model_weight_consistency'].get('assessment', '')
            if '低' in consistency:
                risk += "；各位置模型权重差异较大，预测稳定性存疑"

        return risk

    def _load_history(self):
        """加载解释历史"""
        try:
            if self.history_path.exists():
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    self.interpretation_history = json.load(f)
        except Exception as e:
            logger.warning(f"加载解释历史失败: {e}")
            self.interpretation_history = []

    def _save_interpretation(self, interpretation: PredictionInterpretation):
        """保存解释记录"""
        record = interpretation.to_dict()
        # 简化存储（只保留关键信息）
        simplified = {
            'prediction_period': record['prediction_period'],
            'timestamp': record['timestamp'],
            'overall_confidence': record['overall_confidence'],
            'risk_assessment': record['risk_assessment'],
            'position_count': len(record['position_interpretations']),
            'top_predictions': {
                pos: data['predicted_top_k'][:3]
                for pos, data in record['position_interpretations'].items()
            }
        }
        self.interpretation_history.append(simplified)
        if len(self.interpretation_history) > 200:
            self.interpretation_history = self.interpretation_history[-200:]

        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self.interpretation_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存解释历史失败: {e}")

    def get_interpretation_summary(self, window: int = 10) -> Dict[str, Any]:
        """获取解释历史摘要"""
        recent = self.interpretation_history[-window:]
        if not recent:
            return {'message': '无解释历史'}

        confidences = [r.get('overall_confidence', 0) for r in recent]
        return {
            'total_interpretations': len(self.interpretation_history),
            'recent_count': len(recent),
            'avg_confidence': float(np.mean(confidences)) if confidences else 0.0,
            'confidence_trend': 'improving' if len(confidences) >= 3 and confidences[-1] > confidences[0] else 'stable',
            'recent_periods': [r.get('prediction_period', '') for r in recent],
        }


# 全局单例
_model_interpreter: Optional[ModelInterpreter] = None


def get_model_interpreter(**kwargs) -> ModelInterpreter:
    """获取全局模型解释器单例"""
    global _model_interpreter
    if _model_interpreter is None:
        _model_interpreter = ModelInterpreter(**kwargs)
    return _model_interpreter
