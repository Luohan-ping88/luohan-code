#!/usr/bin/env python3
"""
模型解释器 V1.0 - 决策路径追踪 + 多维分析 + 可解释性输出

功能:
1. 决策路径追踪: 记录从输入特征到预测结果的完整推理链
2. 多维分析: 从时序、位置、特征重要性、模型贡献等多维度分析预测
3. 可解释性输出: 生成结构化的解释报告，提升模型透明度与可信度
"""

import numpy as np
import pandas as pd
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from collections import OrderedDict

logger = logging.getLogger(__name__)

POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
POSITION_LABELS = {"wan": "万位", "qian": "千位", "bai": "百位", "shi": "十位", "ge": "个位"}


class DecisionPathTracker:
    """决策路径追踪器 - 记录预测推理的每一步"""

    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self._current_trace_id: Optional[str] = None

    def start_trace(self, trace_id: str, context: Dict[str, Any]):
        """开始一条新的决策追踪"""
        self._current_trace_id = trace_id
        self.steps = []
        self._add_step("trace_start", {
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat(),
            "context": context
        })

    def record_step(self, step_name: str, step_data: Dict[str, Any]):
        """记录一个决策步骤"""
        self._add_step(step_name, step_data)

    def _add_step(self, name: str, data: Dict[str, Any]):
        self.steps.append({
            "step": name,
            "data": data,
            "timestamp": time.time()
        })

    def end_trace(self, final_result: Dict[str, Any]):
        """结束决策追踪"""
        self._add_step("trace_end", {
            "trace_id": self._current_trace_id,
            "final_result": final_result,
            "total_steps": len(self.steps)
        })

    def get_path(self) -> List[Dict[str, Any]]:
        """获取完整决策路径"""
        return self.steps.copy()

    def summarize_path(self) -> Dict[str, Any]:
        """生成决策路径摘要"""
        step_names = [s["step"] for s in self.steps]
        return {
            "trace_id": self._current_trace_id,
            "total_steps": len(self.steps),
            "step_sequence": step_names,
            "has_feature_analysis": "feature_analysis" in step_names,
            "has_model_fusion": "model_fusion" in step_names,
            "has_bayesian_calibration": "bayesian_calibration" in step_names,
            "has_repeat_penalty": "repeat_penalty" in step_names,
        }


class MultiDimensionalAnalyzer:
    """多维分析器 - 从多个维度分析预测结果"""

    def __init__(self, n_positions: int = 5, n_classes: int = 10):
        self.n_positions = n_positions
        self.n_classes = n_classes

    def analyze_temporal_dimension(self, recent_data: Dict[str, np.ndarray],
                                    predictions: Dict[str, Dict]) -> Dict[str, Any]:
        """时序维度分析: 预测号码与近期走势的关系"""
        analysis = {}
        for pos in POSITIONS:
            if pos not in recent_data or pos not in predictions:
                continue
            recent = np.array(recent_data[pos])
            pred_top1 = predictions[pos]["top_k"][0]
            pred_top3 = set(predictions[pos]["top_k"][:3])

            # 近10期出现频率
            recent_10 = recent[-10:] if len(recent) >= 10 else recent
            freq = np.bincount(recent_10, minlength=10) / len(recent_10)

            # 冷热分析
            is_hot = freq[pred_top1] > 0.2
            is_cold = freq[pred_top1] < 0.05

            # 连续性分析: top-3是否包含上期号码
            last_num = int(recent[-1]) if len(recent) > 0 else -1
            continuity = last_num in pred_top3

            # 趋势方向: 近5期移动平均方向
            recent_5 = recent[-5:] if len(recent) >= 5 else recent
            trend_up = np.mean(recent_5[-2:]) > np.mean(recent_5[:2]) if len(recent_5) >= 4 else False

            analysis[pos] = {
                "predicted_top1": pred_top1,
                "frequency_in_recent_10": float(freq[pred_top1]),
                "temperature": "hot" if is_hot else ("cold" if is_cold else "warm"),
                "continuity_with_last": continuity,
                "trend_direction": "up" if trend_up else "down",
                "last_number": last_num,
            }

        return analysis

    def analyze_position_dimension(self, predictions: Dict[str, Dict]) -> Dict[str, Any]:
        """位置维度分析: 各位置预测的一致性与互补性"""
        top1s = [predictions[pos]["top_k"][0] for pos in POSITIONS if pos in predictions]
        top3_sets = [set(predictions[pos]["top_k"][:3]) for pos in POSITIONS if pos in predictions]

        # 位置间号码重复度
        overlap_matrix = {}
        for i, pos1 in enumerate(POSITIONS):
            for j, pos2 in enumerate(POSITIONS):
                if i < j and pos1 in predictions and pos2 in predictions:
                    overlap = len(top3_sets[i] & top3_sets[j])
                    overlap_matrix[f"{pos1}_{pos2}"] = overlap

        # 号码分布
        all_top1 = set(top1s)
        unique_ratio = len(all_top1) / len(top1s) if top1s else 0

        return {
            "top1_numbers": dict(zip(POSITIONS, top1s)),
            "position_overlap": overlap_matrix,
            "unique_ratio": float(unique_ratio),
            "distribution_balance": "balanced" if unique_ratio > 0.6 else "concentrated",
        }

    def analyze_confidence_dimension(self, predictions: Dict[str, Dict]) -> Dict[str, Any]:
        """置信度维度分析: 预测概率分布的集中度与确定性"""
        analysis = {}
        for pos in POSITIONS:
            if pos not in predictions:
                continue
            probs = predictions[pos].get("probabilities", [])
            if not probs:
                continue
            probs_arr = np.array(probs)

            # 概率分布熵
            entropy = -np.sum(probs_arr * np.log2(probs_arr + 1e-10))
            max_entropy = np.log2(len(probs))
            normalized_entropy = entropy / max_entropy if max_entropy > 0 else 1.0

            # Top-1与Top-2概率差距
            gap = probs_arr[0] - probs_arr[1] if len(probs_arr) >= 2 else 0

            # 确定性等级
            if normalized_entropy < 0.7 and gap > 0.05:
                confidence_level = "high"
            elif normalized_entropy < 0.85:
                confidence_level = "medium"
            else:
                confidence_level = "low"

            analysis[pos] = {
                "top1_probability": float(probs_arr[0]),
                "top1_top2_gap": float(gap),
                "entropy": float(entropy),
                "normalized_entropy": float(normalized_entropy),
                "confidence_level": confidence_level,
            }

        return analysis

    def analyze_feature_dimension(self, feature_values: np.ndarray,
                                   feature_names: Optional[List[str]] = None,
                                   top_n: int = 10) -> Dict[str, Any]:
        """特征维度分析: 识别对当前预测贡献最大的特征"""
        if feature_values is None or len(feature_values) == 0:
            return {"error": "no features provided"}

        abs_values = np.abs(feature_values)
        top_indices = np.argsort(abs_values)[::-1][:top_n]

        if feature_names and len(feature_names) >= len(feature_values):
            top_features = [(feature_names[i], float(feature_values[i])) for i in top_indices]
        else:
            top_features = [(f"feature_{i}", float(feature_values[i])) for i in top_indices]

        return {
            "top_features": top_features,
            "feature_norm": float(np.linalg.norm(feature_values)),
            "feature_mean": float(np.mean(feature_values)),
            "feature_std": float(np.std(feature_values)),
            "n_active_features": int(np.sum(abs_values > np.mean(abs_values))),
        }

    def full_analysis(self, predictions: Dict[str, Dict],
                      recent_data: Optional[Dict[str, np.ndarray]] = None,
                      feature_values: Optional[np.ndarray] = None,
                      feature_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """执行全维度分析"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "temporal": self.analyze_temporal_dimension(recent_data, predictions) if recent_data else {},
            "positional": self.analyze_position_dimension(predictions),
            "confidence": self.analyze_confidence_dimension(predictions),
        }
        if feature_values is not None:
            result["feature"] = self.analyze_feature_dimension(feature_values, feature_names)
        return result


class ModelExplainer:
    """
    模型解释器 - 集成决策路径追踪与多维分析

    提供完整的模型可解释性能力:
    - 决策路径追踪: 记录从输入到输出的完整推理链
    - 多维分析: 时序/位置/置信度/特征多维度分析
    - 解释报告生成: 结构化的人类可读报告
    """

    def __init__(self):
        self.path_tracker = DecisionPathTracker()
        self.analyzer = MultiDimensionalAnalyzer()
        self._explanation_history: List[Dict] = []

    def explain_prediction(self,
                           predictions: Dict[str, Dict],
                           recent_data: Optional[Dict[str, np.ndarray]] = None,
                           feature_values: Optional[np.ndarray] = None,
                           feature_names: Optional[List[str]] = None,
                           model_weights: Optional[Dict[str, float]] = None,
                           bayesian_applied: bool = False,
                           repeat_penalty_applied: bool = False,
                           period: Optional[str] = None) -> Dict[str, Any]:
        """
        解释一次预测的完整过程

        Args:
            predictions: 各位置的预测结果
            recent_data: 近期原始数据
            feature_values: 当前特征值
            feature_names: 特征名列表
            model_weights: 模型融合权重
            bayesian_applied: 是否应用了贝叶斯校准
            repeat_penalty_applied: 是否应用了重复惩罚
            period: 预测期号

        Returns:
            完整的解释报告
        """
        trace_id = f"explain_{period or datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 1. 启动决策路径追踪
        self.path_tracker.start_trace(trace_id, {
            "period": period,
            "n_positions": len(predictions),
        })

        # 2. 记录特征输入
        if feature_values is not None:
            self.path_tracker.record_step("feature_input", {
                "feature_dim": len(feature_values),
                "feature_norm": float(np.linalg.norm(feature_values)),
            })

        # 3. 记录模型融合
        if model_weights:
            self.path_tracker.record_step("model_fusion", {
                "weights": model_weights,
                "dominant_model": max(model_weights, key=model_weights.get),
            })

        # 4. 记录贝叶斯校准
        if bayesian_applied:
            self.path_tracker.record_step("bayesian_calibration", {
                "applied": True,
                "description": "贝叶斯量化器对概率进行了后验校准"
            })

        # 5. 记录重复惩罚
        if repeat_penalty_applied:
            self.path_tracker.record_step("repeat_penalty", {
                "applied": True,
                "description": "检测到预测重复上期号码，已执行概率惩罚"
            })

        # 6. 执行多维分析
        multi_dim = self.analyzer.full_analysis(
            predictions, recent_data, feature_values, feature_names
        )
        self.path_tracker.record_step("multi_dimensional_analysis", multi_dim)

        # 7. 记录最终预测
        self.path_tracker.record_step("final_prediction", {
            pos: pred["top_k"][:3] for pos, pred in predictions.items()
        })

        # 8. 结束追踪
        self.path_tracker.end_trace({
            "n_positions_predicted": len(predictions),
        })

        # 9. 生成解释报告
        explanation = {
            "trace_id": trace_id,
            "period": period,
            "timestamp": datetime.now().isoformat(),
            "decision_path": self.path_tracker.summarize_path(),
            "full_path": self.path_tracker.get_path(),
            "multi_dimensional_analysis": multi_dim,
            "summary": self._generate_summary(predictions, multi_dim, repeat_penalty_applied),
        }

        self._explanation_history.append(explanation)
        if len(self._explanation_history) > 100:
            self._explanation_history = self._explanation_history[-100:]

        return explanation

    def _generate_summary(self, predictions: Dict[str, Dict],
                          multi_dim: Dict, penalty_applied: bool) -> str:
        """生成人类可读的解释摘要"""
        lines = []
        lines.append("=== 预测解释摘要 ===")

        # 位置预测摘要
        for pos in POSITIONS:
            if pos not in predictions:
                continue
            top1 = predictions[pos]["top_k"][0]
            top3 = predictions[pos]["top_k"][:3]
            label = POSITION_LABELS.get(pos, pos)
            lines.append(f"  {label}: Top-1={top1}, Top-3={top3}")

        # 置信度分析
        conf = multi_dim.get("confidence", {})
        high_conf = [pos for pos, c in conf.items() if c.get("confidence_level") == "high"]
        low_conf = [pos for pos, c in conf.items() if c.get("confidence_level") == "low"]
        if high_conf:
            lines.append(f"  高置信度位置: {', '.join(POSITION_LABELS.get(p, p) for p in high_conf)}")
        if low_conf:
            lines.append(f"  低置信度位置: {', '.join(POSITION_LABELS.get(p, p) for p in low_conf)}")

        # 时序分析
        temporal = multi_dim.get("temporal", {})
        hot_nums = [f"{POSITION_LABELS.get(p, p)}={c['predicted_top1']}"
                    for p, c in temporal.items() if c.get("temperature") == "hot"]
        cold_nums = [f"{POSITION_LABELS.get(p, p)}={c['predicted_top1']}"
                     for p, c in temporal.items() if c.get("temperature") == "cold"]
        if hot_nums:
            lines.append(f"  热号预测: {', '.join(hot_nums)}")
        if cold_nums:
            lines.append(f"  冷号预测: {', '.join(cold_nums)}")

        if penalty_applied:
            lines.append("  [已应用重复号码惩罚]")

        return "\n".join(lines)

    def get_explanation_history(self) -> List[Dict]:
        """获取解释历史"""
        return self._explanation_history.copy()

    def save_explanation(self, explanation: Dict, filepath: Path):
        """保存解释报告到文件"""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(explanation, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"[ModelExplainer] 解释报告已保存: {filepath}")
        except Exception as e:
            logger.error(f"[ModelExplainer] 保存解释报告失败: {e}")
