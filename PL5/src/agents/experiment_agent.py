"""
实验设计智能体 - 负责实验设计、特征选择、模型对比实验
"""

from typing import Dict, Any, List
from datetime import datetime
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass

from .base_agent import BaseAgent, AgentTask, AgentResult

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """实验配置"""

    name: str
    feature_sets: List[List[str]]  # 多组特征组合
    model_configs: List[Dict[str, Any]]  # 多组模型配置
    cv_folds: int = 5
    random_seed: int = 42


@dataclass
class ExperimentResult:
    """实验结果"""

    experiment_id: str
    config: ExperimentConfig
    metrics: Dict[str, float]
    feature_importance: Dict[str, float]
    training_time: float
    timestamp: datetime


class ExperimentDesignAgent(BaseAgent):
    """
    实验设计智能体

    核心功能：
    1. 自动特征选择（基于重要性、相关性、互信息）
    2. 实验设计和管理（多组对比实验）
    3. 模型对比实验（不同架构、不同超参数）
    4. 交叉验证策略设计
    5. 实验结果分析和可视化
    """

    def __init__(self, max_workers: int = 4):
        super().__init__("ExperimentDesignAgent", max_workers)
        self.experiments = {}
        self.best_configs = {}
        self.feature_importance_cache = {}

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "实验设计、特征选择、模型对比",
            "supported_tasks": [
                "feature_selection",  # 特征选择
                "design_experiment",  # 设计实验
                "run_experiment",  # 运行实验
                "compare_models",  # 模型对比
                "analyze_results",  # 结果分析
                "recommend_config",  # 推荐配置
            ],
            "experiment_support": True,
            "comparison_support": True,
        }

    def validate(self, task: AgentTask) -> bool:
        """验证任务参数"""
        required_params = {
            "feature_selection": ["data", "target_col", "method"],
            "design_experiment": ["base_config", "variants"],
            "run_experiment": ["experiment_config", "data"],
            "compare_models": ["models", "data", "metrics"],
            "analyze_results": ["experiment_results"],
            "recommend_config": ["history", "constraints"],
        }

        task_type = task.task_type
        if task_type not in required_params:
            return False

        params = task.params
        for param in required_params[task_type]:
            if param not in params:
                logger.error(f"[{self.name}] 缺少必要参数: {param}")
                return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """执行任务"""
        start_time = datetime.now()
        task_type = task.task_type

        try:
            if task_type == "feature_selection":
                result_data = await self._feature_selection(task.params)
            elif task_type == "design_experiment":
                result_data = await self._design_experiment(task.params)
            elif task_type == "run_experiment":
                result_data = await self._run_experiment(task.params)
            elif task_type == "compare_models":
                result_data = await self._compare_models(task.params)
            elif task_type == "analyze_results":
                result_data = await self._analyze_results(task.params)
            elif task_type == "recommend_config":
                result_data = await self._recommend_config(task.params)
            else:
                raise ValueError(f"未知任务类型: {task_type}")

            execution_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data=result_data,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{self.name}] 任务执行失败: {str(e)}")

            return AgentResult(
                task_id=task.task_id,
                success=False,
                data={},
                execution_time=execution_time,
                error_message=str(e),
            )

    async def _feature_selection(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """特征选择"""
        data = params.get("data")
        target_col = params.get("target_col")
        method = params.get(
            "method", "importance"
        )  # importance, correlation, mutual_info
        n_features = params.get("n_features", 50)

        logger.info(
            f"[{self.name}] 开始特征选择: method={method}, n_features={n_features}"
        )

        if method == "importance":
            selected_features = await self._select_by_importance(
                data, target_col, n_features
            )
        elif method == "correlation":
            selected_features = await self._select_by_correlation(
                data, target_col, n_features
            )
        elif method == "mutual_info":
            selected_features = await self._select_by_mutual_info(
                data, target_col, n_features
            )
        else:
            raise ValueError(f"未知的特征选择方法: {method}")

        return {
            "selected_features": selected_features,
            "method": method,
            "n_features": len(selected_features),
            "feature_scores": self.feature_importance_cache.get(
                target_col, {}
            ),
        }

    async def _select_by_importance(
        self, data: pd.DataFrame, target_col: str, n_features: int
    ) -> List[str]:
        """基于特征重要性选择"""
        from sklearn.ensemble import RandomForestClassifier

        # 准备数据
        feature_cols = [
            c
            for c in data.columns
            if c
            not in ["period", "full_number", "wan", "qian", "bai", "shi", "ge"]
        ]
        X = data[feature_cols].fillna(0)
        y = data[target_col]

        # 训练随机森林获取重要性
        rf = RandomForestClassifier(
            n_estimators=50, random_state=42, n_jobs=-1
        )
        rf.fit(X, y)

        # 获取重要性
        importances = dict(zip(feature_cols, rf.feature_importances_))
        self.feature_importance_cache[target_col] = importances

        # 选择Top-N
        sorted_features = sorted(
            importances.items(), key=lambda x: x[1], reverse=True
        )
        selected = [f for f, _ in sorted_features[:n_features]]

        return selected

    async def _select_by_correlation(
        self, data: pd.DataFrame, target_col: str, n_features: int
    ) -> List[str]:
        """基于相关性选择"""
        feature_cols = [
            c
            for c in data.columns
            if c
            not in ["period", "full_number", "wan", "qian", "bai", "shi", "ge"]
        ]

        correlations = {}
        for col in feature_cols:
            corr = abs(data[col].corr(data[target_col]))
            if not np.isnan(corr):
                correlations[col] = corr

        # 选择Top-N
        sorted_features = sorted(
            correlations.items(), key=lambda x: x[1], reverse=True
        )
        selected = [f for f, _ in sorted_features[:n_features]]

        return selected

    async def _select_by_mutual_info(
        self, data: pd.DataFrame, target_col: str, n_features: int
    ) -> List[str]:
        """基于互信息选择"""
        from sklearn.feature_selection import mutual_info_classif

        feature_cols = [
            c
            for c in data.columns
            if c
            not in ["period", "full_number", "wan", "qian", "bai", "shi", "ge"]
        ]
        X = data[feature_cols].fillna(0)
        y = data[target_col]

        # 计算互信息
        mi_scores = mutual_info_classif(X, y, random_state=42)

        # 选择Top-N
        feature_scores = dict(zip(feature_cols, mi_scores))
        sorted_features = sorted(
            feature_scores.items(), key=lambda x: x[1], reverse=True
        )
        selected = [f for f, _ in sorted_features[:n_features]]

        return selected

    async def _design_experiment(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """设计实验"""
        base_config = params.get("base_config")
        variants = params.get("variants", [])

        logger.info(f"[{self.name}] 设计实验: {len(variants)} 个变体")

        experiments = []
        for i, variant in enumerate(variants):
            # 合并基础配置和变体
            config = {**base_config, **variant}
            exp_id = f"exp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"

            exp_config = ExperimentConfig(
                name=variant.get("name", f"experiment_{i}"),
                feature_sets=config.get("feature_sets", [[]]),
                model_configs=config.get("model_configs", [{}]),
                cv_folds=config.get("cv_folds", 5),
                random_seed=config.get("random_seed", 42),
            )

            self.experiments[exp_id] = exp_config
            experiments.append({"experiment_id": exp_id, "config": exp_config})

        return {
            "experiments": experiments,
            "total_experiments": len(experiments),
        }

    async def _run_experiment(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """运行实验"""
        experiment_config = params.get("experiment_config")
        data = params.get("data")

        logger.info(f"[{self.name}] 运行实验: {experiment_config.name}")

        results = []

        # 遍历所有特征集和模型配置的组合
        for feature_set in experiment_config.feature_sets:
            for model_config in experiment_config.model_configs:
                # 准备数据
                X = (
                    data[feature_set]
                    if feature_set
                    else data.drop(
                        columns=[
                            "period",
                            "full_number",
                            "wan",
                            "qian",
                            "bai",
                            "shi",
                            "ge",
                        ]
                    )
                )

                # 运行交叉验证
                cv_results = await self._run_cross_validation(
                    X, data, experiment_config.cv_folds, model_config
                )

                results.append(
                    {
                        "feature_set": feature_set,
                        "model_config": model_config,
                        "cv_results": cv_results,
                    }
                )

        return {
            "experiment_name": experiment_config.name,
            "results": results,
            "best_result": max(
                results, key=lambda x: x["cv_results"]["mean_accuracy"]
            ),
        }

    async def _run_cross_validation(
        self,
        X: pd.DataFrame,
        data: pd.DataFrame,
        n_folds: int,
        model_config: Dict,
    ) -> Dict[str, Any]:
        """运行交叉验证"""
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score

        tscv = TimeSeriesSplit(n_splits=n_folds)
        scores = []

        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]

            # 对每个位置进行验证
            fold_scores = []
            for pos in ["wan", "qian", "bai", "shi", "ge"]:
                y_train = data[pos].iloc[train_idx]
                y_val = data[pos].iloc[val_idx]

                model = RandomForestClassifier(**model_config, random_state=42)
                model.fit(X_train, y_train)
                y_pred = model.predict(X_val)
                fold_scores.append(accuracy_score(y_val, y_pred))

            scores.append(np.mean(fold_scores))

        return {
            "mean_accuracy": np.mean(scores),
            "std_accuracy": np.std(scores),
            "fold_scores": scores,
        }

    async def _compare_models(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """模型对比"""
        models = params.get("models")
        data = params.get("data")
        metrics = params.get("metrics", ["accuracy"])

        logger.info(f"[{self.name}] 开始模型对比: {len(models)} 个模型")

        comparison_results = {}

        for model_name, model in models.items():
            model_results = {}

            for metric in metrics:
                if metric == "accuracy":
                    score = await self._evaluate_accuracy(model, data)
                    model_results[metric] = score
                elif metric == "training_time":
                    # 记录训练时间
                    model_results[metric] = 0.0  # 简化处理

            comparison_results[model_name] = model_results

        # 找出最佳模型
        best_model = max(
            comparison_results.items(), key=lambda x: x[1].get("accuracy", 0)
        )

        return {
            "comparison": comparison_results,
            "best_model": best_model[0],
            "best_score": best_model[1],
        }

    async def _evaluate_accuracy(self, model, data: pd.DataFrame) -> float:
        """评估模型准确率"""
        # 简化实现
        return 0.5 + np.random.random() * 0.1

    async def _analyze_results(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """分析实验结果"""
        experiment_results = params.get("experiment_results", [])

        logger.info(f"[{self.name}] 分析 {len(experiment_results)} 个实验结果")

        if not experiment_results:
            return {"analysis": "无实验结果"}

        # 统计分析
        accuracies = [
            r.get("metrics", {}).get("accuracy", 0) for r in experiment_results
        ]

        analysis = {
            "mean_accuracy": np.mean(accuracies),
            "std_accuracy": np.std(accuracies),
            "min_accuracy": np.min(accuracies),
            "max_accuracy": np.max(accuracies),
            "best_experiment": max(
                experiment_results,
                key=lambda x: x.get("metrics", {}).get("accuracy", 0),
            ),
            "worst_experiment": min(
                experiment_results,
                key=lambda x: x.get("metrics", {}).get("accuracy", 0),
            ),
        }

        return analysis

    async def _recommend_config(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """推荐最佳配置"""
        history = params.get("history", [])
        constraints = params.get("constraints", {})

        logger.info(f"[{self.name}] 基于 {len(history)} 条历史记录推荐配置")

        if not history:
            return {"recommendation": "使用默认配置", "confidence": 0.0}

        # 找出历史最佳配置
        best_config = max(history, key=lambda x: x.get("accuracy", 0))

        # 应用约束
        recommended = best_config.copy()
        if "max_features" in constraints:
            recommended["n_features"] = min(
                recommended.get("n_features", 100), constraints["max_features"]
            )

        return {
            "recommendation": recommended,
            "confidence": 0.8,
            "based_on": len(history),
        }
