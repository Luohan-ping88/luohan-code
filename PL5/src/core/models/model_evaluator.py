"""模型评估和自动调优模块

评估模型性能并自动调整参数，以提高预测准确性和系统效率。
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Any
from sklearn.model_selection import cross_val_score, TimeSeriesSplit

from src.core.utils.logger import logger


class ModelEvaluator:
    """模型评估器"""

    def __init__(
        self,
        target_accuracy_8: float = 0.95,  # 8码准确率目标
        target_accuracy_5: float = 0.70,  # 5码准确率目标
        target_accuracy_3: float = 0.50,  # 3码准确率目标
        evaluation_window: int = 30,  # 评估窗口大小
    ):
        """初始化模型评估器

        Args:
            target_accuracy_8: 8码准确率目标
            target_accuracy_5: 5码准确率目标
            target_accuracy_3: 3码准确率目标
            evaluation_window: 评估窗口大小
        """
        self.target_accuracy_8 = target_accuracy_8
        self.target_accuracy_5 = target_accuracy_5
        self.target_accuracy_3 = target_accuracy_3
        self.evaluation_window = evaluation_window
        self.evaluation_history = []

    def evaluate_prediction(
        self, prediction: Dict[str, List[int]], actual: Dict[str, int]
    ) -> Dict[str, Any]:
        """评估单个预测结果

        Args:
            prediction: 预测结果
            actual: 实际结果

        Returns:
            Dict: 评估结果
        """
        evaluation = {
            "timestamp": datetime.now().isoformat(),
            "positions": {},
            "overall": {},
        }

        total_correct_8 = 0
        total_correct_5 = 0
        total_correct_3 = 0
        total_positions = 0

        for pos, pred_numbers in prediction.items():
            if pos in actual:
                actual_number = actual[pos]
                correct_8 = actual_number in pred_numbers[:8]
                correct_5 = actual_number in pred_numbers[:5]
                correct_3 = actual_number in pred_numbers[:3]

                evaluation["positions"][pos] = {
                    "predicted": pred_numbers,
                    "actual": actual_number,
                    "correct_8": correct_8,
                    "correct_5": correct_5,
                    "correct_3": correct_3,
                }

                total_correct_8 += correct_8
                total_correct_5 += correct_5
                total_correct_3 += correct_3
                total_positions += 1

        if total_positions > 0:
            accuracy_8 = total_correct_8 / total_positions
            accuracy_5 = total_correct_5 / total_positions
            accuracy_3 = total_correct_3 / total_positions

            evaluation["overall"] = {
                "accuracy_8": accuracy_8,
                "accuracy_5": accuracy_5,
                "accuracy_3": accuracy_3,
                "total_positions": total_positions,
                "target_accuracy_8": self.target_accuracy_8,
                "target_accuracy_5": self.target_accuracy_5,
                "target_accuracy_3": self.target_accuracy_3,
                "meets_target_8": accuracy_8 >= self.target_accuracy_8,
                "meets_target_5": accuracy_5 >= self.target_accuracy_5,
                "meets_target_3": accuracy_3 >= self.target_accuracy_3,
            }

        self.evaluation_history.append(evaluation)
        if len(self.evaluation_history) > self.evaluation_window:
            self.evaluation_history = self.evaluation_history[
                -self.evaluation_window :
            ]

        return evaluation

    def evaluate_model(
        self, model, X: np.ndarray, y: np.ndarray, cv: int = 5
    ) -> Dict[str, Any]:
        """评估模型性能

        Args:
            model: 模型实例
            X: 特征数据
            y: 目标数据
            cv: 交叉验证折数

        Returns:
            Dict: 评估结果
        """
        tscv = TimeSeriesSplit(n_splits=cv)

        # 计算准确率
        accuracy_scores = cross_val_score(
            model, X, y, cv=tscv, scoring="accuracy"
        )

        # 计算精确率、召回率和F1分数
        precision_scores = cross_val_score(
            model, X, y, cv=tscv, scoring="precision_macro"
        )
        recall_scores = cross_val_score(
            model, X, y, cv=tscv, scoring="recall_macro"
        )
        f1_scores = cross_val_score(model, X, y, cv=tscv, scoring="f1_macro")

        return {
            "accuracy": {
                "mean": np.mean(accuracy_scores),
                "std": np.std(accuracy_scores),
                "scores": accuracy_scores.tolist(),
            },
            "precision": {
                "mean": np.mean(precision_scores),
                "std": np.std(precision_scores),
                "scores": precision_scores.tolist(),
            },
            "recall": {
                "mean": np.mean(recall_scores),
                "std": np.std(recall_scores),
                "scores": recall_scores.tolist(),
            },
            "f1": {
                "mean": np.mean(f1_scores),
                "std": np.std(f1_scores),
                "scores": f1_scores.tolist(),
            },
        }

    def get_evaluation_summary(self) -> Dict[str, Any]:
        """获取评估摘要

        Returns:
            Dict: 评估摘要
        """
        if not self.evaluation_history:
            return {"message": "No evaluation history available"}

        recent_evaluations = self.evaluation_history[-self.evaluation_window :]

        overall_accuracies_8 = []
        overall_accuracies_5 = []
        overall_accuracies_3 = []

        for eval_result in recent_evaluations:
            if "overall" in eval_result:
                overall_accuracies_8.append(
                    eval_result["overall"].get("accuracy_8", 0)
                )
                overall_accuracies_5.append(
                    eval_result["overall"].get("accuracy_5", 0)
                )
                overall_accuracies_3.append(
                    eval_result["overall"].get("accuracy_3", 0)
                )

        return {
            "evaluation_count": len(recent_evaluations),
            "average_accuracy_8": (
                np.mean(overall_accuracies_8) if overall_accuracies_8 else 0
            ),
            "average_accuracy_5": (
                np.mean(overall_accuracies_5) if overall_accuracies_5 else 0
            ),
            "average_accuracy_3": (
                np.mean(overall_accuracies_3) if overall_accuracies_3 else 0
            ),
            "target_accuracy_8": self.target_accuracy_8,
            "target_accuracy_5": self.target_accuracy_5,
            "target_accuracy_3": self.target_accuracy_3,
            "meets_target_8": (
                np.mean(overall_accuracies_8) >= self.target_accuracy_8
                if overall_accuracies_8
                else False
            ),
            "meets_target_5": (
                np.mean(overall_accuracies_5) >= self.target_accuracy_5
                if overall_accuracies_5
                else False
            ),
            "meets_target_3": (
                np.mean(overall_accuracies_3) >= self.target_accuracy_3
                if overall_accuracies_3
                else False
            ),
        }

    def suggest_hyperparameters(
        self, current_params: Dict[str, Any], performance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """根据性能建议超参数调整

        Args:
            current_params: 当前超参数
            performance: 模型性能

        Returns:
            Dict: 建议的超参数
        """
        suggested_params = current_params.copy()

        # 根据准确率调整参数
        accuracy = performance.get("accuracy", {}).get("mean", 0)

        if accuracy < 0.5:
            # 准确率较低，增加模型复杂度
            if "n_layers" in suggested_params:
                suggested_params["n_layers"] = min(
                    suggested_params["n_layers"] + 1, 6
                )
            if "d_model" in suggested_params:
                suggested_params["d_model"] = min(
                    suggested_params["d_model"] * 2, 128
                )
            if "epochs" in suggested_params:
                suggested_params["epochs"] = min(
                    suggested_params["epochs"] * 2, 200
                )
        elif accuracy > 0.8:
            # 准确率较高，可以减小模型复杂度以提高速度
            if (
                "n_layers" in suggested_params
                and suggested_params["n_layers"] > 2
            ):
                suggested_params["n_layers"] -= 1
            if (
                "d_model" in suggested_params
                and suggested_params["d_model"] > 16
            ):
                suggested_params["d_model"] = max(
                    suggested_params["d_model"] // 2, 16
                )
            if (
                "epochs" in suggested_params
                and suggested_params["epochs"] > 20
            ):
                suggested_params["epochs"] = max(
                    suggested_params["epochs"] // 2, 20
                )

        return suggested_params


class AutoTuner:
    """自动调优器"""

    def __init__(
        self,
        evaluator: ModelEvaluator,
        max_iterations: int = 10,  # 最大调优迭代次数
        improvement_threshold: float = 0.05,  # 性能改进阈值
    ):
        """初始化自动调优器

        Args:
            evaluator: 模型评估器
            max_iterations: 最大调优迭代次数
            improvement_threshold: 性能改进阈值
        """
        self.evaluator = evaluator
        self.max_iterations = max_iterations
        self.improvement_threshold = improvement_threshold
        self.tuning_history = []

    def tune_model(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        param_grid: Dict[str, List[Any]],
    ) -> Dict[str, Any]:
        """调优模型参数

        Args:
            model: 模型实例
            X: 特征数据
            y: 目标数据
            param_grid: 参数网格

        Returns:
            Dict: 最佳参数和性能
        """
        best_score = -1
        best_params = {}

        # 简单的网格搜索
        from itertools import product

        # 生成参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = product(*param_values)

        for i, params in enumerate(param_combinations):
            if i >= self.max_iterations:
                break

            # 设置参数
            param_dict = dict(zip(param_names, params))
            for key, value in param_dict.items():
                setattr(model, key, value)

            # 评估模型
            performance = self.evaluator.evaluate_model(model, X, y)
            accuracy = performance.get("accuracy", {}).get("mean", 0)

            # 记录结果
            self.tuning_history.append(
                {"params": param_dict, "performance": performance}
            )

            # 更新最佳参数
            if accuracy > best_score:
                best_score = accuracy
                best_params = param_dict

                logger.info(
                    f"找到更好的参数: {param_dict}, 准确率: {accuracy:.4f}"
                )

        return {
            "best_params": best_params,
            "best_score": best_score,
            "tuning_history": self.tuning_history,
        }

    def get_tuning_summary(self) -> Dict[str, Any]:
        """获取调优摘要

        Returns:
            Dict: 调优摘要
        """
        if not self.tuning_history:
            return {"message": "No tuning history available"}

        best_entry = max(
            self.tuning_history,
            key=lambda x: x["performance"].get("accuracy", {}).get("mean", 0),
        )

        return {
            "tuning_iterations": len(self.tuning_history),
            "best_params": best_entry["params"],
            "best_accuracy": best_entry["performance"]
            .get("accuracy", {})
            .get("mean", 0),
            "improvement_threshold": self.improvement_threshold,
        }


# 全局模型评估器和自动调优器实例
model_evaluator = ModelEvaluator()
auto_tuner = AutoTuner(model_evaluator)


def get_model_evaluator() -> ModelEvaluator:
    """获取模型评估器实例

    Returns:
        ModelEvaluator: 模型评估器实例
    """
    return model_evaluator


def get_auto_tuner() -> AutoTuner:
    """获取自动调优器实例

    Returns:
        AutoTuner: 自动调优器实例
    """
    return auto_tuner


def evaluate_prediction(
    prediction: Dict[str, List[int]], actual: Dict[str, int]
) -> Dict[str, Any]:
    """评估单个预测结果

    Args:
        prediction: 预测结果
        actual: 实际结果

    Returns:
        Dict: 评估结果
    """
    return model_evaluator.evaluate_prediction(prediction, actual)


def evaluate_model(
    model, X: np.ndarray, y: np.ndarray, cv: int = 5
) -> Dict[str, Any]:
    """评估模型性能

    Args:
        model: 模型实例
        X: 特征数据
        y: 目标数据
        cv: 交叉验证折数

    Returns:
        Dict: 评估结果
    """
    return model_evaluator.evaluate_model(model, X, y, cv)


def get_evaluation_summary() -> Dict[str, Any]:
    """获取评估摘要

    Returns:
        Dict: 评估摘要
    """
    return model_evaluator.get_evaluation_summary()


def tune_model(
    model, X: np.ndarray, y: np.ndarray, param_grid: Dict[str, List[Any]]
) -> Dict[str, Any]:
    """调优模型参数

    Args:
        model: 模型实例
        X: 特征数据
        y: 目标数据
        param_grid: 参数网格

    Returns:
        Dict: 最佳参数和性能
    """
    return auto_tuner.tune_model(model, X, y, param_grid)
