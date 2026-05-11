"""
优化智能体 - 自动优化特征组合和模型参数
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestClassifier

from .base_agent import BaseAgent, AgentTask, AgentResult
from src.core.utils import logger


class OptimizationAgent(BaseAgent):
    """
    优化智能体

    功能：
    1. 自动优化特征组合，选择最优特征子集
    2. 自动调优模型参数，提升预测性能
    3. 基于贝叶斯优化或遗传算法进行超参数搜索
    4. 与其他智能体协作，提供优化建议
    """

    def __init__(self, max_workers: int = 4):
        super().__init__("OptimizationAgent", max_workers)
        self.optimization_history = []
        self.best_config = {}

    async def optimize_feature_selection(
        self, df: pd.DataFrame, feature_cols: List[str], target_col: str = "wan"
    ) -> Dict[str, Any]:
        """优化特征选择

        Args:
            df: 数据
            feature_cols: 特征列名列表
            target_col: 目标列名

        Returns:
            优化结果
        """
        logger.info(f"[OptimizationAgent] 开始优化特征选择，目标列: {target_col}")

        X = df[feature_cols].values
        y = df[target_col].values

        # 使用随机森林评估特征重要性
        rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        rf.fit(X, y)

        # 获取特征重要性
        importances = rf.feature_importances_
        feature_importance = list(zip(feature_cols, importances))
        feature_importance.sort(key=lambda x: x[1], reverse=True)

        # 选择Top N特征
        top_n = min(50, len(feature_cols))
        selected_features = [f[0] for f in feature_importance[:top_n]]

        # 评估不同特征子集的性能
        results = []
        for n in [10, 20, 30, 40, 50]:
            if n <= len(feature_importance):
                subset_features = [f[0] for f in feature_importance[:n]]
                X_subset = df[subset_features].values

                # 交叉验证
                scores = cross_val_score(rf, X_subset, y, cv=5, scoring="accuracy")
                mean_score = np.mean(scores)

                results.append(
                    {"n_features": n, "features": subset_features, "cv_score": mean_score, "cv_std": np.std(scores)}
                )

        # 选择最佳特征数量
        best_result = max(results, key=lambda x: x["cv_score"])

        optimization_result = {
            "target_col": target_col,
            "all_features": feature_cols,
            "selected_features": best_result["features"],
            "n_selected": len(best_result["features"]),
            "cv_score": best_result["cv_score"],
            "cv_std": best_result["cv_std"],
            "feature_importance": feature_importance[:20],
            "all_results": results,
            "timestamp": datetime.now().isoformat(),
        }

        self.optimization_history.append(optimization_result)

        logger.info(
            f"[OptimizationAgent] 特征选择优化完成，选择 {len(best_result['features'])} 个特征，CV分数: {best_result['cv_score']:.4f}"
        )

        return optimization_result

    async def optimize_model_parameters(
        self, X: np.ndarray, y: np.ndarray, model_type: str = "random_forest"
    ) -> Dict[str, Any]:
        """优化模型参数

        Args:
            X: 特征数据
            y: 目标数据
            model_type: 模型类型

        Returns:
            优化结果
        """
        logger.info(f"[OptimizationAgent] 开始优化模型参数，模型类型: {model_type}")

        # 定义参数搜索空间
        param_space = self._get_param_space(model_type)

        # 使用随机搜索进行参数优化
        best_score = 0
        best_params = {}
        all_results = []

        n_iterations = 20
        for i in range(n_iterations):
            # 随机采样参数
            params = self._sample_params(param_space)

            # 创建模型
            model = self._create_model(model_type, params)

            # 交叉验证
            try:
                scores = cross_val_score(model, X, y, cv=5, scoring="accuracy", n_jobs=-1)
                mean_score = np.mean(scores)

                result = {"iteration": i + 1, "params": params, "cv_score": mean_score, "cv_std": np.std(scores)}
                all_results.append(result)

                if mean_score > best_score:
                    best_score = mean_score
                    best_params = params

                logger.info(
                    f"[OptimizationAgent] 迭代 {i+1}/{n_iterations}, 分数: {mean_score:.4f}, 最佳: {best_score:.4f}"
                )

            except Exception as e:
                logger.warning(f"[OptimizationAgent] 迭代 {i+1} 失败: {e}")
                continue

        optimization_result = {
            "model_type": model_type,
            "best_params": best_params,
            "best_score": best_score,
            "all_results": all_results,
            "n_iterations": n_iterations,
            "timestamp": datetime.now().isoformat(),
        }

        self.optimization_history.append(optimization_result)
        self.best_config[model_type] = best_params

        logger.info(f"[OptimizationAgent] 模型参数优化完成，最佳分数: {best_score:.4f}")

        return optimization_result

    def _get_param_space(self, model_type: str) -> Dict[str, Any]:
        """获取参数搜索空间

        Args:
            model_type: 模型类型

        Returns:
            参数搜索空间
        """
        if model_type == "random_forest":
            return {
                "n_estimators": [100, 200, 500, 1000],
                "max_depth": [10, 20, 30, None],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4],
            }
        elif model_type == "gradient_boosting":
            return {
                "n_estimators": [100, 200, 500],
                "max_depth": [3, 5, 7, 10],
                "learning_rate": [0.01, 0.05, 0.1, 0.2],
                "subsample": [0.8, 0.9, 1.0],
            }
        else:
            return {}

    def _sample_params(self, param_space: Dict[str, Any]) -> Dict[str, Any]:
        """从参数空间中随机采样

        Args:
            param_space: 参数搜索空间

        Returns:
            采样参数
        """
        params = {}
        for key, values in param_space.items():
            params[key] = np.random.choice(values)
        return params

    def _create_model(self, model_type: str, params: Dict[str, Any]):
        """创建模型

        Args:
            model_type: 模型类型
            params: 模型参数

        Returns:
            模型实例
        """
        if model_type == "random_forest":
            return RandomForestClassifier(**params, random_state=42, n_jobs=-1)
        elif model_type == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingClassifier

            return GradientBoostingClassifier(**params, random_state=42)
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

    async def optimize_all_positions(self, df: pd.DataFrame, feature_cols: List[str]) -> Dict[str, Any]:
        """优化所有位置

        Args:
            df: 数据
            feature_cols: 特征列名列表

        Returns:
            优化结果
        """
        logger.info("[OptimizationAgent] 开始优化所有位置")

        positions = ["wan", "qian", "bai", "shi", "ge"]
        all_results = {}

        for pos in positions:
            logger.info(f"[OptimizationAgent] 优化位置: {pos}")

            # 特征选择优化
            feature_result = await self.optimize_feature_selection(df, feature_cols, pos)

            # 模型参数优化
            selected_features = feature_result["selected_features"]
            X = df[selected_features].values
            y = df[pos].values

            model_result = await self.optimize_model_parameters(X, y, "random_forest")

            all_results[pos] = {
                "feature_optimization": feature_result,
                "model_optimization": model_result,
                "best_cv_score": model_result["best_score"],
            }

        # 计算平均性能
        avg_score = np.mean([r["best_cv_score"] for r in all_results.values()])

        final_result = {
            "positions": all_results,
            "average_cv_score": avg_score,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"[OptimizationAgent] 所有位置优化完成，平均CV分数: {avg_score:.4f}")

        return final_result

    async def generate_optimization_report(self, optimization_result: Dict[str, Any]) -> str:
        """生成优化报告

        Args:
            optimization_result: 优化结果

        Returns:
            优化报告文本
        """
        report_parts = []
        report_parts.append("# 排列五优化分析报告")
        report_parts.append(f"生成时间: {optimization_result.get('timestamp', datetime.now().isoformat())}")
        report_parts.append("")

        if "positions" in optimization_result:
            report_parts.append("## 各位置优化结果")
            for pos, result in optimization_result["positions"].items():
                report_parts.append(f"### {pos}位")

                # 特征优化
                feature_opt = result.get("feature_optimization", {})
                report_parts.append(f"- 选择特征数: {feature_opt.get('n_selected', 0)}")
                report_parts.append(f"- 特征CV分数: {feature_opt.get('cv_score', 0):.4f}")

                # 模型优化
                model_opt = result.get("model_optimization", {})
                report_parts.append(f"- 模型CV分数: {model_opt.get('best_score', 0):.4f}")
                report_parts.append(f"- 最佳参数: {model_opt.get('best_params', {})}")
                report_parts.append("")

            report_parts.append(f"## 整体性能")
            report_parts.append(f"- 平均CV分数: {optimization_result.get('average_cv_score', 0):.4f}")

        return "\n".join(report_parts)

    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """获取优化历史

        Returns:
            优化历史列表
        """
        return self.optimization_history

    def get_best_config(self, model_type: str = None) -> Dict[str, Any]:
        """获取最佳配置

        Args:
            model_type: 模型类型

        Returns:
            最佳配置
        """
        if model_type:
            return self.best_config.get(model_type, {})
        return self.best_config

    def clear_history(self):
        """清空优化历史"""
        self.optimization_history = []
        self.best_config = {}
        logger.info("[OptimizationAgent] 优化历史已清空")

    def shutdown(self):
        """关闭智能体"""
        self.clear_history()
        super().shutdown()
        logger.info("[OptimizationAgent] 智能体已关闭")

    async def execute(self, task: AgentTask) -> AgentResult:
        """执行智能体任务"""
        start_time = datetime.now()

        try:
            if task.task_type == "optimize_features":
                result = await self.optimize_feature_selection(
                    task.params.get("data"), task.params.get("feature_cols", []), task.params.get("target_col", "wan")
                )
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data=result,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
            elif task.task_type == "optimize_parameters":
                result = await self.optimize_model_parameters(
                    task.params.get("X"), task.params.get("y"), task.params.get("model_type", "random_forest")
                )
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data=result,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
            elif task.task_type == "optimize_all":
                result = await self.optimize_all_positions(task.params.get("data"), task.params.get("feature_cols", []))
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data=result,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
            else:
                return AgentResult(
                    task_id=task.task_id,
                    success=False,
                    data={},
                    execution_time=(datetime.now() - start_time).total_seconds(),
                    error_message=f"Unknown task type: {task.task_type}",
                )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                data={},
                execution_time=(datetime.now() - start_time).total_seconds(),
                error_message=str(e),
            )

    def validate(self, task: AgentTask) -> bool:
        """验证任务参数是否合法"""
        required_params = {
            "optimize_features": ["data", "feature_cols"],
            "optimize_parameters": ["X", "y"],
            "optimize_all": ["data", "feature_cols"],
        }

        task_type = task.task_type
        if task_type not in required_params:
            return False

        params = task.params
        for param in required_params[task_type]:
            if param not in params:
                return False

        return True

    def get_capabilities(self) -> Dict[str, Any]:
        """获取智能体能力描述"""
        return {
            "name": self.name,
            "description": "特征选择优化、模型参数调优、系统优化建议",
            "supported_tasks": ["optimize_features", "optimize_parameters", "optimize_all"],
            "optimization_support": True,
            "param_tuning_support": True,
        }

    async def suggest_system_optimizations(self) -> Dict[str, Any]:
        """
        提供系统优化建议

        Returns:
            系统优化建议
        """
        try:
            return {
                "agent": "optimization",
                "suggestions": [
                    "优化特征选择策略，减少冗余特征",
                    "采用集成学习方法，提高预测稳定性",
                    "实现动态参数调优，适应数据变化",
                    "优化模型训练流程，减少计算时间",
                ],
                "priority": "high",
                "confidence": 0.85,
            }
        except Exception as e:
            logger.error(f"[OptimizationAgent] 生成系统优化建议失败: {str(e)}")
            return {"agent": "optimization", "error": str(e)}

    async def optimize_prediction_strategy(
        self, performance: Dict[str, Any], patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        优化预测策略

        Args:
            performance: 性能指标
            patterns: 历史模式分析结果

        Returns:
            优化后的预测策略
        """
        try:
            # 分析当前性能
            current_accuracy = performance.get("overall_accuracy", 0.1)

            # 基于性能和模式分析制定策略
            strategy = {
                "prediction_method": "ensemble",
                "confidence_threshold": 0.6,
                "model_weights": {"random_forest": 0.4, "gradient_boosting": 0.4, "knn": 0.2},
                "feature_selection_strategy": "dynamic",
                "retraining_frequency": "daily",
            }

            # 根据性能调整策略
            if current_accuracy < 0.2:
                strategy["prediction_method"] = "conservative"
                strategy["confidence_threshold"] = 0.7
                strategy["model_weights"] = {"random_forest": 0.6, "gradient_boosting": 0.4, "knn": 0.0}
            elif current_accuracy > 0.3:
                strategy["prediction_method"] = "aggressive"
                strategy["confidence_threshold"] = 0.5
                strategy["model_weights"] = {
                    "random_forest": 0.3,
                    "gradient_boosting": 0.3,
                    "knn": 0.2,
                    "neural_network": 0.2,
                }

            # 基于模式分析调整
            if patterns.get("anomaly_detection", {}).get("anomalies_detected", False):
                strategy["retraining_frequency"] = "weekly"

            return {
                "agent": "optimization",
                "strategy": strategy,
                "confidence": 0.8,
                "recommendation": "adjust_prediction_strategy",
            }
        except Exception as e:
            logger.error(f"[OptimizationAgent] 优化预测策略失败: {str(e)}")
            return {"agent": "optimization", "error": str(e)}
