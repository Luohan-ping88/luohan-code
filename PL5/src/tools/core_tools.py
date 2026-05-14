"""
PL5 核心能力层工具 (Layer 2 - CORE)

封装 V10.0 模型能力为标准化工具接口:
1. PredictorTool          - 单次预测 (EnhancedPL5Predictor.predict)
2. BatchPredictorTool     - 批量预测
3. FeatureEngineerTool    - 特征工程 (FeatureEngineerV9)
4. FeatureSelectorTool    - 特征选择 (MultiMethodFeatureSelector)
5. ModelAnalyzerTool      - 模型诊断
6. WeightAnalyzerTool     - 权重分析
7. HistoryEvaluatorTool   - 历史评估 (SelfLearningSystem)
8. OptimizationAdvisorTool - 优化建议 (SelfLearningSystem V10.0)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from .base import (
    BaseTool,
    ToolResult,
    ToolContext,
    ToolLayer,
    register_tool,
)


@register_tool(tags=["prediction", "core", "v10"])
class PredictorTool(BaseTool):
    """预测工具 - 封装 EnhancedPL5Predictor.predict() 能力

    输入特征向量，返回各位置的 Top-K 推荐号码、概率分布、不确定性度量和融合权重。
    """

    name = "predictor"
    description = "V10.0 单次预测工具：输入特征向量，输出Top-K推荐号码、概率分布、不确定性度量与使用权重"
    layer = ToolLayer.CORE
    tags = ["prediction", "core", "v10", "inference"]
    input_schema = {
        "type": "object",
        "properties": {
            "features": {
                "type": "array",
                "description": "特征向量 (np.ndarray 或 list)",
            },
            "recent_original_data": {
                "type": "object",
                "description": "近期原始数据字典 {pos: np.ndarray}",
            },
            "top_k": {
                "type": "integer",
                "description": "推荐号码数量",
                "default": 8,
            },
        },
        "required": ["features"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "predictions": {"type": "object"},
            "summary": {"type": "object"},
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        predictor = ctx.get("predictor")
        if predictor is None:
            return ToolResult.error_result(
                "上下文中未找到 predictor 实例，请先通过 ModelAnalyzerTool 加载模型",
                code="PREDICTOR_NOT_FOUND",
            )

        features = kwargs.get("features")
        if features is None:
            return ToolResult.error_result(
                "缺少必填参数: features", code="MISSING_FEATURES"
            )

        if isinstance(features, list):
            features = np.array(features, dtype=np.float64)
        elif not isinstance(features, np.ndarray):
            return ToolResult.error_result(
                f"features 类型错误: 期望 np.ndarray/list, 实际 {type(features).__name__}",
                code="INVALID_FEATURES_TYPE",
            )

        recent_original_data = kwargs.get("recent_original_data")
        top_k = kwargs.get("top_k", 8)

        try:
            result = predictor.predict(
                features=features,
                recent_original_data=recent_original_data,
                top_k=top_k,
            )

            summary = self._build_prediction_summary(result, top_k)

            ctx.set("last_prediction", result)
            ctx.record_metric("predictor.top_k", top_k)
            ctx.record_metric("predictor.positions", len(result))

            return ToolResult.success_result(
                data={
                    "predictions": result,
                    "summary": summary,
                },
                model_version=getattr(predictor, "_mc", None),
                feature_dim=int(len(features)),
            )

        except Exception as e:
            ctx.log.exception(f"[{self.name}] 预测异常")
            return ToolResult.error_result(
                f"预测执行失败: {str(e)}",
                code="PREDICTION_ERROR",
            )

    @staticmethod
    def _build_prediction_summary(result: Dict, top_k: int) -> Dict:
        positions = list(result.keys())
        avg_uncertainty = 0.0
        total_positions = len(positions)

        position_details = {}
        for pos in positions:
            pos_info = result[pos]
            avg_uncertainty += pos_info.get("uncertainty", 0.0)
            weights_used = pos_info.get("weights_used", {})
            position_details[pos] = {
                "top_k_recommendations": pos_info.get("top_k", []),
                "uncertainty": round(pos_info.get("uncertainty", 0.0), 4),
                "weights_used": {
                    k: round(v, 4) for k, v in weights_used.items()
                },
                "is_fallback": pos_info.get("fallback", False),
            }

        if total_positions > 0:
            avg_uncertainty /= total_positions

        return {
            "total_positions": total_positions,
            "top_k": top_k,
            "avg_uncertainty": round(avg_uncertainty, 4),
            "positions": position_details,
        }


@register_tool(tags=["prediction", "batch", "core"])
class BatchPredictorTool(BaseTool):
    """批量预测工具 - 循环调用 PredictorTool 或直接调用 predictor

    支持对多组特征向量进行批量预测，并汇总统计结果。
    """

    name = "batch_predictor"
    description = (
        "V10.0 批量预测工具：输入多组特征向量，批量输出预测结果及汇总统计"
    )
    layer = ToolLayer.CORE
    tags = ["prediction", "batch", "core", "v10"]
    input_schema = {
        "type": "object",
        "properties": {
            "features_list": {
                "type": "array",
                "description": "特征向量列表 (list of np.ndarray/list)",
                "items": {"type": "array"},
            },
            "top_k": {"type": "integer", "default": 8},
        },
        "required": ["features_list"],
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        predictor = ctx.get("predictor")
        if predictor is None:
            return ToolResult.error_result(
                "上下文中未找到 predictor 实例", code="PREDICTOR_NOT_FOUND"
            )

        features_list = kwargs.get("features_list")
        if not features_list or not isinstance(features_list, (list, tuple)):
            return ToolResult.error_result(
                "缺少或无效参数: features_list (需为非空列表)",
                code="INVALID_FEATURES_LIST",
            )

        top_k = kwargs.get("top_k", 8)
        batch_results = []
        uncertainties = []

        try:
            for idx, features in enumerate(features_list):
                if isinstance(features, list):
                    features = np.array(features, dtype=np.float64)

                single_result = predictor.predict(
                    features=features,
                    top_k=top_k,
                )
                batch_results.append(single_result)

                pos_uncertainties = [
                    single_result[p].get("uncertainty", 0.0)
                    for p in single_result
                    if isinstance(single_result[p], dict)
                ]
                if pos_uncertainties:
                    uncertainties.append(np.mean(pos_uncertainties))

            summary_stats = self._compute_batch_statistics(
                batch_results, uncertainties
            )

            ctx.set("last_batch_predictions", batch_results)
            ctx.record_metric("batch_predictor.count", len(batch_results))
            ctx.record_metric(
                "batch_predictor.avg_uncertainty",
                float(np.mean(uncertainties)) if uncertainties else 0.0,
            )

            return ToolResult.success_result(
                data={
                    "batch_results": batch_results,
                    "summary": summary_stats,
                },
                batch_size=len(batch_results),
                top_k=top_k,
            )

        except Exception as e:
            ctx.log.exception(f"[{self.name}] 批量预测异常")
            return ToolResult.error_result(
                f"批量预测执行失败: {str(e)}",
                code="BATCH_PREDICTION_ERROR",
            )

    @staticmethod
    def _compute_batch_statistics(
        batch_results: List[Dict],
        uncertainties: List[float],
    ) -> Dict:
        if not batch_results:
            return {"count": 0}

        all_top_ks = []
        for result in batch_results:
            for pos, info in result.items():
                if isinstance(info, dict) and "top_k" in info:
                    all_top_ks.extend(info["top_k"])

        freq_map: Dict[int, int] = {}
        for num in all_top_ks:
            freq_map[num] = freq_map.get(num, 0) + 1

        sorted_freq = sorted(
            freq_map.items(), key=lambda x: x[1], reverse=True
        )
        most_common = [(int(k), v) for k, v in sorted_freq[:15]]

        return {
            "count": len(batch_results),
            "avg_uncertainty": (
                round(float(np.mean(uncertainties)), 4)
                if uncertainties
                else 0.0
            ),
            "min_uncertainty": (
                round(float(min(uncertainties)), 4) if uncertainties else 0.0
            ),
            "max_uncertainty": (
                round(float(max(uncertainties)), 4) if uncertainties else 0.0
            ),
            "std_uncertainty": (
                round(float(np.std(uncertainties)), 4)
                if len(uncertainties) > 1
                else 0.0
            ),
            "most_recommended_numbers": most_common,
        }


@register_tool(tags=["feature", "engineering", "core"])
class FeatureEngineerTool(BaseTool):
    """特征工程工具 - 封装 FeatureEngineerV9 特征工程能力

    对原始数据进行全量特征提取，支持可选的特征选择后处理。
    """

    name = "feature_engineer"
    description = "V10.0 特征工程工具：输入原始DataFrame，输出特征矩阵(X, feature_cols)及特征统计信息"
    layer = ToolLayer.CORE
    tags = ["feature", "engineering", "core", "v9"]
    input_schema = {
        "type": "object",
        "properties": {
            "raw_data": {"type": "object"},
            "enable_selection": {"type": "boolean", "default": False},
            "select_top": {"type": "integer", "default": 100},
            "enable_scaler": {"type": "boolean", "default": False},
        },
        "required": ["raw_data"],
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        from src.core.features.engineer import FeatureEngineerV9

        raw_data = kwargs.get("raw_data")
        if raw_data is None:
            return ToolResult.error_result(
                "缺少必填参数: raw_data", code="MISSING_RAW_DATA"
            )
        if not isinstance(raw_data, pd.DataFrame):
            return ToolResult.error_result(
                f"raw_data 类型错误: 期望 DataFrame, 实际 {type(raw_data).__name__}",
                code="INVALID_RAW_DATA_TYPE",
            )

        enable_selection = kwargs.get("enable_selection", False)
        select_top = kwargs.get("select_top", 100)
        enable_scaler = kwargs.get("enable_scaler", False)

        try:
            engineer = FeatureEngineerV9()

            df_featured = engineer.extract_all_features(
                df=raw_data,
                select_top=select_top if enable_selection else None,
                enable_scaler=enable_scaler,
            )

            basic_cols = [
                "period",
                "full_number",
                "wan",
                "qian",
                "bai",
                "shi",
                "ge",
            ]
            feature_cols = [
                c for c in df_featured.columns if c not in basic_cols
            ]

            X = df_featured[feature_cols].fillna(0).values

            feature_stats = {
                "original_columns": len(raw_data.columns),
                "total_feature_columns": len(df_featured.columns),
                "engineered_feature_count": len(feature_cols),
                "sample_count": len(df_featured),
                "feature_shape": list(X.shape),
                "has_missing": int(
                    pd.isna(df_featured[feature_cols]).sum().sum() > 0
                ),
                "selection_applied": enable_selection,
                "scaler_applied": enable_scaler,
                "cache_stats": getattr(engineer.cache, "stats", {}),
            }

            ctx.set("feature_matrix_X", X)
            ctx.set("feature_cols", feature_cols)
            ctx.set("featured_dataframe", df_featured)
            ctx.record_metric(
                "feature_engineer.feature_count", len(feature_cols)
            )
            ctx.record_metric(
                "feature_engineer.sample_count", len(df_featured)
            )

            if enable_selection:
                selector_result = self._run_feature_selector(
                    ctx, df_featured, select_top
                )
                return ToolResult.success_result(
                    data={
                        "X": X.tolist(),
                        "feature_cols": feature_cols,
                        "feature_stats": feature_stats,
                        "selection_result": selector_result.get("data"),
                    },
                    tool_name=self.name,
                )

            return ToolResult.success_result(
                data={
                    "X": X.tolist(),
                    "feature_cols": feature_cols,
                    "feature_stats": feature_stats,
                },
                tool_name=self.name,
            )

        except Exception as e:
            ctx.log.exception(f"[{self.name}] 特征工程异常")
            return ToolResult.error_result(
                f"特征工程执行失败: {str(e)}",
                code="FEATURE_ENGINEERING_ERROR",
            )

    @staticmethod
    def _run_feature_selector(
        ctx: ToolContext,
        df_featured: pd.DataFrame,
        n_features: int,
    ) -> ToolResult:
        selector_tool = FeatureSelectorTool()
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        target_pos = POSITIONS[0]
        if target_pos in df_featured.columns:
            y = df_featured[target_pos].values.astype(int)
        else:
            y = np.zeros(len(df_featured), dtype=int)
        return selector_tool.execute(
            ctx, X=df_featured, y=y, n_features=n_features
        )


@register_tool(tags=["feature", "selection", "core"])
class FeatureSelectorTool(BaseTool):
    """特征选择工具 - 封装 MultiMethodFeatureSelector 多方法投票特征选择

    通过 RF/MI/RFE/Chi2 多方法投票机制智能选择最优特征子集。
    """

    name = "feature_selector"
    description = "V10.0 特征选择工具：多方法投票(RF/MI/RFE/Chi2)，输出选定特征索引、投票得分和最优特征数建议"
    layer = ToolLayer.CORE
    tags = ["feature", "selection", "core", "v9"]
    input_schema = {
        "type": "object",
        "properties": {
            "X": {"type": "object", "description": "特征矩阵 DataFrame"},
            "y": {"type": "array", "description": "目标变量数组"},
            "n_features": {
                "type": "integer",
                "description": "目标特征数量（可选）",
            },
        },
        "required": ["X", "y"],
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        from src.core.features.feature_selector import (
            MultiMethodFeatureSelector,
        )

        X = kwargs.get("X")
        y = kwargs.get("y")
        if X is None or y is None:
            return ToolResult.error_result(
                "缺少必填参数: X 和/或 y", code="MISSING_SELECTION_INPUT"
            )
        if not isinstance(X, pd.DataFrame):
            return ToolResult.error_result(
                f"X 类型错误: 期望 DataFrame, 实际 {type(X).__name__}",
                code="INVALID_X_TYPE",
            )

        n_features = kwargs.get("n_features")

        target_y = (
            pd.Series(y, index=X.index)
            if hasattr(y, "__len__") and len(y) == len(X)
            else (
                X.iloc[:, -1]
                if len(X.columns) > 0
                else pd.Series(np.zeros(len(X), dtype=int), index=X.index)
            )
        )

        try:
            selector = MultiMethodFeatureSelector()
            X_selected = selector.fit_transform(
                X, target_y, n_features=n_features
            )

            report = selector.get_feature_importance_report()
            selected_features = selector.selected_features
            optimal_n = selector.suggest_optimal_n_features()
            vote_scores = selector.vote_scores

            sorted_votes = sorted(
                vote_scores.items(), key=lambda x: x[1], reverse=True
            )
            top_features = [(f, round(s, 6)) for f, s in sorted_votes[:30]]

            selection_data = {
                "selected_features": selected_features,
                "selected_count": len(selected_features),
                "optimal_n_features_suggested": optimal_n,
                "vote_scores_top30": top_features,
                "methods_used": report.get("methods_used", []),
                "removed_correlated_pairs": report.get(
                    "removed_correlated_pairs", []
                ),
                "original_feature_count": report.get(
                    "total_original_features", 0
                ),
                "elbow_curve": report.get("elbow_curve", {}),
            }

            ctx.set("selected_features", selected_features)
            ctx.set("selector", selector)
            ctx.record_metric(
                "feature_selector.selected_count", len(selected_features)
            )
            ctx.record_metric("feature_selector.optimal_n", optimal_n)

            return ToolResult.success_result(data=selection_data)

        except Exception as e:
            ctx.log.exception(f"[{self.name}] 特征选择异常")
            return ToolResult.error_result(
                f"特征选择执行失败: {str(e)}",
                code="FEATURE_SELECTION_ERROR",
            )


@register_tool(tags=["model", "diagnosis", "core"])
class ModelAnalyzerTool(BaseTool):
    """模型诊断工具 - 输出模型健康报告

    从上下文获取或加载 EnhancedPL5Predictor 实例，
    输出版本号、维度信息、校验状态、训练时间、各组件状态等完整诊断报告。
    """

    name = "model_analyzer"
    description = "V10.0 模型诊断工具：输出版本/维度/校验状态/训练时间/各组件状态的完整健康报告"
    layer = ToolLayer.CORE
    tags = ["model", "diagnosis", "core", "v10"]
    input_schema = {
        "type": "object",
        "properties": {
            "load_model": {"type": "boolean", "default": True},
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        from src.core.models.enhanced_predictor import EnhancedPL5Predictor

        load_model = kwargs.get("load_model", True)
        predictor = ctx.get("predictor")

        if predictor is None and load_model:
            try:
                predictor = EnhancedPL5Predictor()
                loaded = predictor.load_models()
                if not loaded:
                    return ToolResult.success_result(
                        data={
                            "status": "no_model_file",
                            "message": "模型文件不存在或加载失败",
                            "model_info": None,
                        }
                    )
                ctx.set("predictor", predictor)
                ctx.log.info("[ModelAnalyzer] 模型已从文件加载到上下文")
            except Exception as e:
                return ToolResult.error_result(
                    f"模型加载失败: {str(e)}",
                    code="MODEL_LOAD_FAILED",
                )

        if predictor is None:
            return ToolResult.error_result(
                "上下文中无 predictor 且未启用自动加载",
                code="NO_PREDICTOR_AVAILABLE",
            )

        try:
            model_info = predictor.get_model_info()
            integrity_result = predictor.validate_model_integrity()

            components_status = {}
            components_status["stacking"] = {
                "loaded": bool(predictor.stacking),
                "positions": list(predictor.stacking.keys()),
                "count": len(predictor.stacking),
            }
            components_status["hmm_models"] = {
                "loaded": bool(predictor.hmm_models),
                "positions": list(predictor.hmm_models.keys()),
                "count": len(predictor.hmm_models),
            }
            components_status["copula_model"] = {
                "loaded": predictor.copula_model is not None,
            }
            components_status["bsts_models"] = {
                "loaded": bool(predictor.bsts_models),
                "positions": list(predictor.bsts_models.keys()),
                "count": len(predictor.bsts_models),
            }
            components_status["rl_optimizer"] = {
                "loaded": predictor.rl_optimizer is not None,
                "trained": (
                    getattr(predictor.rl_optimizer, "is_trained", False)
                    if predictor.rl_optimizer
                    else False
                ),
            }
            components_status["thompson_sampler"] = {
                "loaded": predictor.thompson_sampler is not None,
            }

            weight_info = dict(predictor.weights)

            health_report = {
                "model_info": model_info,
                "integrity_check": {
                    "valid": integrity_result.get("valid", False),
                    "version": integrity_result.get("version", "unknown"),
                    "checksum_match": integrity_result.get(
                        "checksum_match", True
                    ),
                    "errors": integrity_result.get("errors", []),
                    "warnings": integrity_result.get("warnings", []),
                },
                "components": components_status,
                "current_weights": weight_info,
                "is_trained": predictor.is_trained,
                "feature_dim": predictor.trained_feature_dim,
                "feature_cols_count": len(predictor.feature_cols),
                "performance_history_samples": {
                    m: len(h)
                    for m, h in predictor._model_performance_history.items()
                },
                "prediction_cache_size": len(
                    predictor._prediction_results_cache
                ),
                "rewards_history_length": len(predictor._rewards_history),
            }

            ctx.set("model_health_report", health_report)
            ctx.record_metric(
                "model_analyzer.is_trained", int(predictor.is_trained)
            )
            ctx.record_metric(
                "model_analyzer.feature_dim", predictor.trained_feature_dim
            )

            return ToolResult.success_result(data=health_report)

        except Exception as e:
            ctx.log.exception(f"[{self.name}] 模型诊断异常")
            return ToolResult.error_result(
                f"模型诊断执行失败: {str(e)}",
                code="MODEL_DIAGNOSIS_ERROR",
            )


@register_tool(tags=["weight", "analysis", "core"])
class WeightAnalyzerTool(BaseTool):
    """权重分析工具 - 分析当前权重配置并提供不确定性区间和建议

    调用 EnhancedPL5Predictor 的权重相关方法：
    - get_adaptive_weights(): 获取自适应权重
    - _get_bayesian_weights_with_uncertainty(): 贝叶斯不确定性量化
    - adjust_weights_by_history(): 基于历史的EMA权重调整
    """

    name = "weight_analyzer"
    description = "V10.0 权重分析工具：当前权重分析 + 不确定性区间(95%/80%/50% CI) + 权重调整建议"
    layer = ToolLayer.CORE
    tags = ["weight", "analysis", "core", "v10", "bayesian"]
    input_schema = {
        "type": "object",
        "properties": {
            "history": {
                "type": "array",
                "description": "历史预测结果列表 (可选)",
            },
            "n_samples": {
                "type": "integer",
                "description": "Thompson采样次数",
                "default": 1000,
            },
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        predictor = ctx.get("predictor")
        if predictor is None:
            return ToolResult.error_result(
                "上下文中未找到 predictor 实例", code="PREDICTOR_NOT_FOUND"
            )

        history = kwargs.get("history")
        n_samples = kwargs.get("n_samples", 1000)

        try:
            adaptive_weights, uncertainty_info = (
                predictor.get_adaptive_weights(include_uncertainty=True)
            )

            mean_weights, bayesian_uncertainty = (
                predictor._get_bayesian_weights_with_uncertainty(
                    n_samples=n_samples
                )
            )

            current_weights = dict(predictor.weights)

            ci_summary = {}
            model_names = ["stacking", "hmm", "copula", "bayesian"]
            for mname in model_names:
                if mname in bayesian_uncertainty:
                    bi = bayesian_uncertainty[mname]
                    ci_summary[mname] = {
                        "mean": round(bi["mean"], 4),
                        "median": round(bi["median"], 4),
                        "std": round(bi["std"], 4),
                        "ci_95": [
                            round(bi["ci_95"]["lower"], 4),
                            round(bi["ci_95"]["upper"], 4),
                        ],
                        "ci_80": [
                            round(bi["ci_80"]["lower"], 4),
                            round(bi["ci_80"]["upper"], 4),
                        ],
                        "ci_50": [
                            round(bi["ci_50"]["lower"], 4),
                            round(bi["ci_50"]["upper"], 4),
                        ],
                        "cv": round(bi.get("cv", 0.0), 4),
                        "skewness": round(bi.get("skewness", 0.0), 4),
                    }

            global_info = bayesian_uncertainty.get("_global", {})
            adjustment_result = None
            if history and len(history) > 0:
                adjustment_result = predictor.adjust_weights_by_history(
                    history
                )

            weight_suggestions = self._generate_weight_suggestions(
                current_weights, ci_summary, global_info, adjustment_result
            )

            analysis_data = {
                "current_weights": current_weights,
                "adaptive_weights": {
                    m: round(float(adaptive_weights[i]), 4)
                    for i, m in enumerate(model_names)
                },
                "uncertainty_intervals": ci_summary,
                "global_uncertainty": {
                    "total_entropy": round(
                        global_info.get("total_entropy", 0.0), 4
                    ),
                    "effective_dimensions": round(
                        global_info.get("effective_dimensions", 0.0), 4
                    ),
                    "overall_confidence": global_info.get(
                        "overall_confidence", "unknown"
                    ),
                    "most_certain_model": global_info.get(
                        "most_certain_model", ""
                    ),
                    "least_certain_model": global_info.get(
                        "least_certain_model", ""
                    ),
                    "uncertainty_ratio": round(
                        global_info.get("uncertainty_ratio", 0.0), 4
                    ),
                    "n_samples": global_info.get("n_samples", n_samples),
                },
                "history_adjustment": adjustment_result,
                "weight_suggestions": weight_suggestions,
            }

            ctx.set("weight_analysis", analysis_data)
            ctx.record_metric(
                "weight_analyzer.effective_dims",
                global_info.get("effective_dimensions", 0.0),
            )
            ctx.record_metric(
                "weight_analyzer.confidence",
                (
                    1.0
                    if global_info.get("overall_confidence") == "high"
                    else 0.5
                ),
            )

            return ToolResult.success_result(data=analysis_data)

        except Exception as e:
            ctx.log.exception(f"[{self.name}] 权重分析异常")
            return ToolResult.error_result(
                f"权重分析执行失败: {str(e)}",
                code="WEIGHT_ANALYSIS_ERROR",
            )

    @staticmethod
    def _generate_weight_suggestions(
        current_weights: Dict[str, float],
        ci_summary: Dict,
        global_info: Dict,
        adjustment_result: Optional[Dict],
    ) -> List[Dict]:
        suggestions = []
        confidence = global_info.get("overall_confidence", "unknown")

        if confidence == "low":
            suggestions.append(
                {
                    "type": "warning",
                    "message": "整体置信度低，建议增加历史数据积累以降低权重不确定性",
                    "priority": "high",
                }
            )

        for mname, ci in ci_summary.items():
            cv = ci.get("cv", 0.0)
            if cv > 0.5:
                suggestions.append(
                    {
                        "type": "adjustment",
                        "model": mname,
                        "message": f"{mname} 权重变异系数较高(CV={cv:.2f})，建议关注该模型稳定性",
                        "priority": "medium",
                        "current_value": current_weights.get(mname, 0.25),
                        "suggested_range": [ci["ci_95"][0], ci["ci_95"][1]],
                    }
                )

        if adjustment_result:
            adj_mag = adjustment_result.get("adjustment_magnitude", 0.0)
            if adj_mag > 0.15:
                suggestions.append(
                    {
                        "type": "action",
                        "message": f"基于EMA的历史权重调整幅度较大({adj_mag:.4f})，建议审查近期模型表现变化",
                        "priority": "important",
                        "adjusted_weights": adjustment_result.get(
                            "weights", {}
                        ),
                    }
                )

        if not suggestions:
            suggestions.append(
                {
                    "type": "info",
                    "message": "权重配置合理，无需立即调整",
                    "priority": "low",
                }
            )

        return suggestions


@register_tool(tags=["evaluation", "history", "core"])
class HistoryEvaluatorTool(BaseTool):
    """历史评估工具 - 利用 SelfLearningSystem 的评估能力

    对预测历史和实际结果进行全面评估：
    准确率、命中率、趋势分析、Mann-Kendall检验结果等。
    """

    name = "history_evaluator"
    description = (
        "V10.0 历史评估工具：准确率/命中率/趋势分析/Mann-Kendall检验结果"
    )
    layer = ToolLayer.CORE
    tags = ["evaluation", "history", "core", "v10", "mann-kendall"]
    input_schema = {
        "type": "object",
        "properties": {
            "predictions_history": {
                "type": "array",
                "description": "预测历史记录列表",
            },
            "actual_results": {
                "type": "array",
                "description": "实际开奖结果列表",
            },
        },
        "required": ["predictions_history", "actual_results"],
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        from src.core.self_learning import SelfLearningSystem

        predictions_history = kwargs.get("predictions_history")
        actual_results = kwargs.get("actual_results")

        if not predictions_history or not actual_results:
            return ToolResult.error_result(
                "缺少必填参数: predictions_history 和 actual_results",
                code="MISSING_HISTORY_DATA",
            )
        if len(predictions_history) != len(actual_results):
            return ToolResult.error_result(
                f"predictions_history({len(predictions_history)}) 与 actual_results({len(actual_results)}) 长度不匹配",
                code="HISTORY_LENGTH_MISMATCH",
            )

        try:
            sl_system = SelfLearningSystem()

            accuracies = []
            hit_rates = []
            for pred, actual in zip(predictions_history, actual_results):
                accuracy = self._compute_accuracy(pred, actual)
                hit_rate = self._compute_hit_rate(pred, actual)
                accuracies.append(accuracy)
                hit_rates.append(hit_rate)
                sl_system.record_evaluation(
                    accuracy=accuracy, extra={"hit_rate": hit_rate}
                )

            mk_result = SelfLearningSystem.mann_kendall_test(accuracies)
            comprehensive_score = sl_system.compute_comprehensive_score()
            performance_alert = sl_system.check_performance_alert()
            dynamic_threshold = sl_system.calculate_dynamic_threshold()
            should_retrain, retrain_reason = sl_system.should_trigger_retrain()

            eval_data = {
                "basic_metrics": {
                    "total_evaluations": len(accuracies),
                    "avg_accuracy": round(float(np.mean(accuracies)), 6),
                    "max_accuracy": round(float(np.max(accuracies)), 6),
                    "min_accuracy": round(float(np.min(accuracies)), 6),
                    "std_accuracy": round(float(np.std(accuracies)), 6),
                    "avg_hit_rate": round(float(np.mean(hit_rates)), 6),
                    "latest_accuracy": (
                        round(accuracies[-1], 6) if accuracies else 0.0
                    ),
                },
                "trend_analysis": mk_result,
                "comprehensive_score": comprehensive_score,
                "performance_alert": performance_alert,
                "dynamic_threshold": dynamic_threshold,
                "retrain_decision": {
                    "should_retrain": should_retrain,
                    "reason": retrain_reason,
                },
                "accuracy_series": [round(a, 6) for a in accuracies[-50:]],
                "hit_rate_series": [round(h, 6) for h in hit_rates[-50:]],
            }

            ctx.set("evaluator_result", eval_data)
            ctx.set("self_learning_system", sl_system)
            ctx.record_metric(
                "history_evaluator.avg_accuracy", float(np.mean(accuracies))
            )
            ctx.record_metric(
                "history_evaluator.trend", mk_result.get("trend", "unknown")
            )
            ctx.record_metric(
                "history_evaluator.should_retrain", int(should_retrain)
            )

            return ToolResult.success_result(data=eval_data)

        except Exception as e:
            ctx.log.exception(f"[{self.name}] 历史评估异常")
            return ToolResult.error_result(
                f"历史评估执行失败: {str(e)}",
                code="EVALUATION_ERROR",
            )

    @staticmethod
    def _compute_accuracy(prediction: Dict, actual: Dict) -> float:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        hits = 0
        total = 0
        for pos in POSITIONS:
            if pos in prediction and pos in actual:
                total += 1
                pred_info = prediction[pos]
                if isinstance(pred_info, dict):
                    top_k = pred_info.get("top_k", [])
                    if actual[pos] in top_k:
                        hits += 1
        return hits / max(total, 1)

    @staticmethod
    def _compute_hit_rate(prediction: Dict, actual: Dict) -> float:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        hits = 0
        total = 0
        for pos in POSITIONS:
            if pos in prediction and pos in actual:
                total += 1
                pred_info = prediction[pos]
                if isinstance(pred_info, dict):
                    top_k = pred_info.get("top_k", [])
                    if actual[pos] in top_k[:3]:
                        hits += 1
        return hits / max(total, 1)


@register_tool(tags=["optimization", "advisor", "core"])
class OptimizationAdvisorTool(BaseTool):
    """优化建议工具 - 封装 SelfLearningSystem.generate_structured_suggestions()

    输出 V10.0 格式的结构化优化建议：
    - 优先级分类 (紧急/重要/常规)
    - 参数建议值与合理范围
    - 效果预估 (基于历史反馈的置信区间)
    """

    name = "optimization_advisor"
    description = "V10.0 优化建议工具：生成结构化优化建议(优先级/参数建议/效果预估/V10.0格式)"
    layer = ToolLayer.CORE
    tags = ["optimization", "advisor", "core", "v10", "suggestion"]
    input_schema = {
        "type": "object",
        "properties": {
            "performance_data": {
                "type": "object",
                "description": "性能数据字典 (可选，用于自定义评估)",
            },
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        from src.core.self_learning import SelfLearningSystem

        performance_data = kwargs.get("performance_data")

        try:
            sl_system = SelfLearningSystem()

            if performance_data and isinstance(performance_data, dict):
                custom_accuracies = performance_data.get("accuracies", [])
                if custom_accuracies:
                    for acc in custom_accuracies:
                        extra = {}
                        if "hit_rate" in performance_data:
                            extra["hit_rate"] = performance_data["hit_rate"]
                        if "confidence" in performance_data:
                            extra["confidence"] = performance_data[
                                "confidence"
                            ]
                        sl_system.record_evaluation(
                            accuracy=float(acc),
                            extra=extra if extra else None,
                        )

            structured_suggestions = (
                sl_system.generate_structured_suggestions()
            )
            suggestion_statistics = sl_system.get_suggestion_statistics()
            alert_status = sl_system.check_performance_alert()
            comprehensive_score = sl_system.compute_comprehensive_score()

            suggestions_output = [s.to_dict() for s in structured_suggestions]

            priority_breakdown = {
                "urgent": sum(
                    1 for s in structured_suggestions if s.priority.value == 3
                ),
                "important": sum(
                    1 for s in structured_suggestions if s.priority.value == 2
                ),
                "regular": sum(
                    1 for s in structured_suggestions if s.priority.value == 1
                ),
            }

            advisor_data = {
                "suggestions": suggestions_output,
                "summary": {
                    "total_suggestions": len(structured_suggestions),
                    "priority_breakdown": priority_breakdown,
                    "urgent_count": priority_breakdown["urgent"],
                    "has_urgent": priority_breakdown["urgent"] > 0,
                },
                "statistics": suggestion_statistics,
                "alert_status": alert_status,
                "comprehensive_score": comprehensive_score,
                "version": "V10.0",
            }

            ctx.set("optimization_suggestions", structured_suggestions)
            ctx.set("self_learning_system", sl_system)
            ctx.record_metric(
                "optimization_advisor.total_suggestions",
                len(structured_suggestions),
            )
            ctx.record_metric(
                "optimization_advisor.urgent_count",
                priority_breakdown["urgent"],
            )

            return ToolResult.success_result(data=advisor_data)

        except Exception as e:
            ctx.log.exception(f"[{self.name}] 优化建议生成异常")
            return ToolResult.error_result(
                f"优化建议生成失败: {str(e)}",
                code="OPTIMIZATION_ADVISOR_ERROR",
            )
