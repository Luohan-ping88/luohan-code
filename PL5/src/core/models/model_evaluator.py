"""
模型评估器 V2.0 - 增强版
支持交叉验证、多指标评估、模型对比分析
"""

import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import pickle
from collections import defaultdict

from sklearn.model_selection import KFold, TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)


class EvaluationMetric(Enum):
    """评估指标"""
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1 = "f1"
    TOP_K_ACCURACY = "top_k_accuracy"


@dataclass
class CrossValidationConfig:
    """交叉验证配置"""
    n_splits: int = 5
    use_time_series_split: bool = True
    shuffle: bool = False
    random_state: int = 42


@dataclass
class EvaluationResult:
    """评估结果"""
    model_name: str
    timestamp: str
    cv_scores: Dict[str, List[float]] = field(default_factory=dict)
    mean_scores: Dict[str, float] = field(default_factory=dict)
    std_scores: Dict[str, float] = field(default_factory=dict)
    fold_details: List[Dict] = field(default_factory=list)
    overall_metrics: Dict[str, float] = field(default_factory=dict)
    confusion_matrices: Dict[str, np.ndarray] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'model_name': self.model_name,
            'timestamp': self.timestamp,
            'cv_scores': {k: [float(v) for v in vs] for k, vs in self.cv_scores.items()},
            'mean_scores': {k: float(v) for k, v in self.mean_scores.items()},
            'std_scores': {k: float(v) for k, v in self.std_scores.items()},
            'fold_details': self.fold_details,
            'overall_metrics': {k: float(v) if isinstance(v, (int, float, np.number)) else v
                               for k, v in self.overall_metrics.items()},
            'confusion_matrices': {k: v.tolist() for k, v in self.confusion_matrices.items()},
            'metadata': self.metadata
        }


class EnhancedModelEvaluator:
    """增强的模型评估器"""

    def __init__(self, cv_config: Optional[CrossValidationConfig] = None):
        self.cv_config = cv_config or CrossValidationConfig()
        self.evaluation_history: List[EvaluationResult] = []

    def evaluate_with_cross_validation(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        model_name: str = "model",
        metrics: List[EvaluationMetric] = None,
        top_k: int = 3
    ) -> EvaluationResult:
        """
        使用交叉验证评估模型

        Args:
            model: 要评估的模型
            X: 特征数据
            y: 标签数据
            model_name: 模型名称
            metrics: 评估指标列表
            top_k: Top-K准确率中的K值

        Returns:
            EvaluationResult: 评估结果
        """
        if metrics is None:
            metrics = [
                EvaluationMetric.ACCURACY,
                EvaluationMetric.PRECISION,
                EvaluationMetric.RECALL,
                EvaluationMetric.F1
            ]

        print(f"\n开始使用交叉验证评估模型: {model_name}")
        print(f"数据形状: X={X.shape}, y={y.shape}")
        print(f"交叉验证折数: {self.cv_config.n_splits}")

        # 创建交叉验证器
        if self.cv_config.use_time_series_split:
            kfold = TimeSeriesSplit(n_splits=self.cv_config.n_splits)
        else:
            kfold = KFold(
                n_splits=self.cv_config.n_splits,
                shuffle=self.cv_config.shuffle,
                random_state=self.cv_config.random_state
            )

        # 存储每折的结果
        cv_scores = {metric.value: [] for metric in metrics}
        fold_details = []
        confusion_matrices = {}

        for fold_idx, (train_idx, val_idx) in enumerate(kfold.split(X)):
            print(f"\n第 {fold_idx + 1}/{self.cv_config.n_splits} 折...")

            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # 训练模型
            try:
                model.fit(X_train, y_train)

                # 预测
                if hasattr(model, 'predict'):
                    y_pred = model.predict(X_val)
                else:
                    raise ValueError("模型没有predict方法")

                # 计算各项指标
                fold_metrics = {}

                for metric in metrics:
                    if metric == EvaluationMetric.ACCURACY:
                        score = accuracy_score(y_val, y_pred)
                    elif metric == EvaluationMetric.PRECISION:
                        score = precision_score(y_val, y_pred, average='macro', zero_division=0)
                    elif metric == EvaluationMetric.RECALL:
                        score = recall_score(y_val, y_pred, average='macro', zero_division=0)
                    elif metric == EvaluationMetric.F1:
                        score = f1_score(y_val, y_pred, average='macro', zero_division=0)
                    elif metric == EvaluationMetric.TOP_K_ACCURACY:
                        # Top-K准确率
                        if hasattr(model, 'predict_proba'):
                            probas = model.predict_proba(X_val)
                            top_k_preds = np.argsort(probas, axis=1)[:, -top_k:]
                            score = np.mean([y_val[i] in top_k_preds[i] for i in range(len(y_val))])
                        else:
                            score = 0.0
                    else:
                        score = 0.0

                    cv_scores[metric.value].append(score)
                    fold_metrics[metric.value] = score

                # 计算混淆矩阵
                cm = confusion_matrix(y_val, y_pred)
                confusion_matrices[f'fold_{fold_idx}'] = cm

                # 保存折的详细信息
                fold_details.append({
                    'fold': fold_idx,
                    'train_size': len(train_idx),
                    'val_size': len(val_idx),
                    'metrics': fold_metrics,
                    'accuracy': accuracy_score(y_val, y_pred)
                })

                print(f"  准确率: {fold_metrics.get('accuracy', 0):.4f}")

            except Exception as e:
                print(f"  错误: 第{fold_idx}折训练失败: {e}")
                for metric in metrics:
                    cv_scores[metric.value].append(0.0)

        # 计算平均值和标准差
        mean_scores = {metric: np.mean(scores) for metric, scores in cv_scores.items()}
        std_scores = {metric: np.std(scores) for metric, scores in cv_scores.items()}

        # 创建评估结果
        result = EvaluationResult(
            model_name=model_name,
            timestamp=datetime.now().isoformat(),
            cv_scores=cv_scores,
            mean_scores=mean_scores,
            std_scores=std_scores,
            fold_details=fold_details,
            confusion_matrices=confusion_matrices,
            metadata={
                'n_splits': self.cv_config.n_splits,
                'data_shape': X.shape,
                'top_k': top_k
            }
        )

        self.evaluation_history.append(result)
        self._print_evaluation_summary(result)

        return result

    def compare_models(
        self,
        models: Dict[str, Any],
        X: np.ndarray,
        y: np.ndarray,
        metrics: List[EvaluationMetric] = None
    ) -> pd.DataFrame:
        """
        对比多个模型的性能

        Args:
            models: 模型字典 {name: model}
            X: 特征数据
            y: 标签数据
            metrics: 评估指标

        Returns:
            DataFrame: 对比结果
        """
        if metrics is None:
            metrics = [
                EvaluationMetric.ACCURACY,
                EvaluationMetric.PRECISION,
                EvaluationMetric.RECALL,
                EvaluationMetric.F1
            ]

        print("\n" + "=" * 80)
        print("模型性能对比")
        print("=" * 80)

        results = []

        for model_name, model in models.items():
            print(f"\n评估模型: {model_name}")
            try:
                result = self.evaluate_with_cross_validation(
                    model, X, y, model_name, metrics
                )

                results.append({
                    'model': model_name,
                    'accuracy': result.mean_scores.get('accuracy', 0),
                    'accuracy_std': result.std_scores.get('accuracy', 0),
                    'precision': result.mean_scores.get('precision', 0),
                    'recall': result.mean_scores.get('recall', 0),
                    'f1': result.mean_scores.get('f1', 0),
                    'cv_folds': self.cv_config.n_splits
                })
            except Exception as e:
                print(f"  模型 {model_name} 评估失败: {e}")
                results.append({
                    'model': model_name,
                    'accuracy': 0,
                    'accuracy_std': 0,
                    'precision': 0,
                    'recall': 0,
                    'f1': 0,
                    'cv_folds': self.cv_config.n_splits
                })

        # 创建对比DataFrame
        df = pd.DataFrame(results)
        df = df.sort_values('accuracy', ascending=False)

        print("\n" + "=" * 80)
        print("模型排名（按准确率）")
        print("=" * 80)
        print(df.to_string(index=False))

        return df

    def analyze_prediction_errors(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        top_n: int = 10
    ) -> Dict:
        """
        分析预测错误

        Returns:
            Dict: 错误分析结果
        """
        errors = np.where(y_true != y_pred)[0]
        error_rate = len(errors) / len(y_true) if len(y_true) > 0 else 0

        # 分析每个类别的错误
        class_errors = defaultdict(list)
        for idx in errors:
            true_label = y_true[idx]
            pred_label = y_pred[idx]
            class_errors[true_label].append(pred_label)

        # 统计每个类别的错误模式
        error_patterns = {}
        for true_label, pred_labels in class_errors.items():
            unique_preds, counts = np.unique(pred_labels, return_counts=True)
            error_patterns[int(true_label)] = {
                'total_errors': len(pred_labels),
                'common_mistakes': {
                    int(p): int(c) for p, c in zip(unique_preds, counts)
                }
            }

        return {
            'total_errors': len(errors),
            'error_rate': error_rate,
            'accuracy': 1 - error_rate,
            'class_errors': error_patterns,
            'error_indices': errors.tolist()[:top_n]  # 只返回前N个错误的索引
        }

    def generate_evaluation_report(
        self,
        result: EvaluationResult,
        output_path: Optional[Path] = None
    ) -> str:
        """生成评估报告"""
        report_lines = [
            "=" * 80,
            "模型评估报告",
            "=" * 80,
            f"模型名称: {result.model_name}",
            f"评估时间: {result.timestamp}",
            f"数据形状: {result.metadata.get('data_shape', 'N/A')}",
            "",
            "交叉验证结果:",
            "-" * 40
        ]

        for metric, mean_score in result.mean_scores.items():
            std_score = result.std_scores.get(metric, 0)
            cv_values = result.cv_scores.get(metric, [])

            report_lines.append(
                f"{metric.upper()}: {mean_score:.4f} ± {std_score:.4f}"
            )
            report_lines.append(
                f"  各折得分: {[f'{s:.4f}' for s in cv_values]}"
            )

        report_lines.extend([
            "",
            "各折详细结果:",
            "-" * 40
        ])

        for fold_detail in result.fold_details:
            report_lines.append(
                f"第{fold_detail['fold']}折: 准确率={fold_detail['accuracy']:.4f}"
            )

        report = "\n".join(report_lines)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"评估报告已保存: {output_path}")

        return report

    def save_evaluation_history(
        self,
        output_path: Path
    ):
        """保存评估历史"""
        history_data = [result.to_dict() for result in self.evaluation_history]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False, default=str)

        print(f"评估历史已保存: {output_path}")

    def load_evaluation_history(
        self,
        input_path: Path
    ) -> bool:
        """加载评估历史"""
        if not input_path.exists():
            print(f"评估历史文件不存在: {input_path}")
            return False

        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                history_data = json.load(f)

            self.evaluation_history = []
            for data in history_data:
                result = EvaluationResult(
                    model_name=data['model_name'],
                    timestamp=data['timestamp'],
                    cv_scores=data['cv_scores'],
                    mean_scores=data['mean_scores'],
                    std_scores=data['std_scores'],
                    fold_details=data['fold_details'],
                    confusion_matrices={k: np.array(v) for k, v in data['confusion_matrices'].items()},
                    metadata=data['metadata']
                )
                self.evaluation_history.append(result)

            print(f"评估历史已加载: {len(self.evaluation_history)} 条记录")
            return True

        except Exception as e:
            print(f"加载评估历史失败: {e}")
            return False

    def _print_evaluation_summary(self, result: EvaluationResult):
        """打印评估摘要"""
        print("\n" + "=" * 80)
        print(f"评估完成: {result.model_name}")
        print("=" * 80)

        print("\n平均分数:")
        for metric, score in result.mean_scores.items():
            std = result.std_scores.get(metric, 0)
            print(f"  {metric.upper()}: {score:.4f} ± {std:.4f}")

        # 找出最佳折
        if result.fold_details:
            best_fold = max(result.fold_details, key=lambda x: x['accuracy'])
            worst_fold = min(result.fold_details, key=lambda x: x['accuracy'])

            print(f"\n最佳折: 第{best_fold['fold']}折 (准确率: {best_fold['accuracy']:.4f})")
            print(f"最差折: 第{worst_fold['fold']}折 (准确率: {worst_fold['accuracy']:.4f})")

    def get_best_model(self) -> Optional[EvaluationResult]:
        """获取评估历史中最佳模型"""
        if not self.evaluation_history:
            return None

        best_result = max(
            self.evaluation_history,
            key=lambda r: r.mean_scores.get('accuracy', 0)
        )

        return best_result

    def get_performance_trend(self) -> pd.DataFrame:
        """获取性能趋势"""
        if not self.evaluation_history:
            return pd.DataFrame()

        trend_data = []
        for result in self.evaluation_history:
            row = {
                'timestamp': result.timestamp,
                'model_name': result.model_name,
                'accuracy': result.mean_scores.get('accuracy', 0),
                'precision': result.mean_scores.get('precision', 0),
                'recall': result.mean_scores.get('recall', 0),
                'f1': result.mean_scores.get('f1', 0)
            }
            trend_data.append(row)

        return pd.DataFrame(trend_data)


# 便捷函数
def quick_evaluate(
    model,
    X: np.ndarray,
    y: np.ndarray,
    model_name: str = "model",
    n_splits: int = 5
) -> EvaluationResult:
    """快速评估模型"""
    evaluator = EnhancedModelEvaluator(
        cv_config=CrossValidationConfig(n_splits=n_splits)
    )
    return evaluator.evaluate_with_cross_validation(model, X, y, model_name)
