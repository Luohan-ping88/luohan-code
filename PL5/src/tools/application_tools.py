"""
PL5 应用工具层 (Layer 3 - APPLICATION)

面向业务场景的高层编排工具，内部调用基础设施层和核心层工具:
1. DailyReportTool      - 每日完整分析报告生成
2. QuickPredictTool     - 快速简化预测（非技术用户）
3. BacktestTool         - 策略历史回测
4. ComparisonTool       - 多模型/A/B对比
5. AlertTool            - 异常检测与告警
6. ExportTool           - 多格式结果导出
"""

import os
import json
import time
import io
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import numpy as np
import pandas as pd

from .base import (
    BaseTool,
    ToolResult,
    ToolContext,
    ToolLayer,
    register_tool,
    get_registry,
)

# ================================================================
# 统计辅助函数
# ================================================================


def _approx_normal_cdf(x: float) -> float:
    """标准正态分布CDF近似计算（模块级函数）"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ================================================================
# 1. DailyReportTool — 每日完整分析报告生成
# ================================================================


@register_tool(tags=["report", "application", "orchestration"])
class DailyReportTool(BaseTool):
    """每日完整分析报告生成工具 (Layer 3 - APPLICATION)

    编排底层核心工具，完成从数据加载到最终报告输出的完整流水线：
        DataLoader → FeatureEngineer → Predictor → ModelAnalyzer → OptimizationAdvisor → 格式化报告

    输出内容包含：
        - 预测推荐号码（各位置 Top-K）
        - 模型健康状态与组件信息
        - 性能指标（准确率/不确定性/置信度）
        - 结构化优化建议（按优先级分类）
        - 置信度分析与风险提示

    Args:
        period: 目标期号字符串（如 "2026080"），用于数据定位和报告标识
        data_source: 数据源路径或 DataFrame，默认自动获取最近数据
        top_k: 预测推荐数量，默认 8
        include_model_analysis: 是否包含模型诊断分析，默认 True
        include_optimization: 是否包含优化建议，默认 True
    """

    name = "daily_report"
    description = (
        "每日完整分析报告：数据加载→特征工程→预测→诊断→优化建议→格式化输出"
    )
    layer = ToolLayer.APPLICATION
    tags = ["report", "application", "orchestration", "daily"]

    input_schema = {
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "description": "目标期号（如 '2026080'）",
            },
            "data_source": {
                "type": ["string", "object"],
                "description": "数据源路径(str/Path) 或 DataFrame",
            },
            "top_k": {
                "type": "integer",
                "description": "预测推荐号码数量",
                "default": 8,
            },
            "include_model_analysis": {
                "type": "boolean",
                "description": "是否包含模型诊断分析",
                "default": True,
            },
            "include_optimization": {
                "type": "boolean",
                "description": "是否包含优化建议",
                "default": True,
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "report": {"type": "object", "description": "完整日报数据"},
            "summary": {"type": "object", "description": "报告摘要"},
            "metadata": {"type": "object", "description": "报告元信息"},
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        period = kwargs.get("period")
        data_source = kwargs.get("data_source")
        top_k = kwargs.get("top_k", 8)
        include_model_analysis = kwargs.get("include_model_analysis", True)
        include_optimization = kwargs.get("include_optimization", True)

        registry = get_registry()
        report_sections = {}
        pipeline_errors = []
        start_time = time.time()

        try:
            dl_tool_cls = registry.get("data_loader")
            if dl_tool_cls is None:
                return ToolResult.error_result(
                    "未找到 data_loader 工具，请确认 infrastructure 层已注册",
                    code="TOOL_NOT_FOUND_DATA_LOADER",
                )
            dl_tool = dl_tool_cls()

            if data_source is None:
                default_paths = [
                    "data/pl5_history.csv",
                    "data/latest.csv",
                    "pl5_data.csv",
                ]
                for p in default_paths:
                    if os.path.exists(p):
                        data_source = p
                        break

            if data_source is None:
                return ToolResult.error_result(
                    "未指定 data_source 且未找到默认数据文件",
                    code="DATA_SOURCE_MISSING",
                )

            dl_result = dl_tool.execute(ctx, path_or_data=data_source)
            if not dl_result.success:
                pipeline_errors.append(f"数据加载失败: {dl_result.errors}")
                return ToolResult.error_result(
                    f"数据加载阶段失败: {dl_result.errors[0].message if dl_result.errors else 'unknown'}",
                    code="PIPELINE_DATA_LOAD_FAILED",
                )

            raw_data = dl_result.data.get("data")
            if not isinstance(raw_data, pd.DataFrame) or raw_data.empty:
                return ToolResult.error_result(
                    "加载的数据为空或格式不正确", code="EMPTY_RAW_DATA"
                )

            report_sections["data_loading"] = {
                "status": "success",
                "rows": len(raw_data),
                "cols": len(raw_data.columns),
                "stats": dl_result.data.get("stats", {}),
            }
            ctx.set("raw_data", raw_data)

        except Exception as e:
            ctx.log.exception("[daily_report] 数据加载阶段异常")
            return ToolResult.error_result(
                f"数据加载阶段异常: {str(e)}", code="DATA_LOADING_EXCEPTION"
            )

        try:
            fe_tool_cls = registry.get("feature_engineer")
            if fe_tool_cls is None:
                return ToolResult.error_result(
                    "未找到 feature_engineer 工具",
                    code="TOOL_NOT_FOUND_FEATURE_ENGINEER",
                )
            fe_tool = fe_tool_cls()

            fe_result = fe_tool.execute(ctx, raw_data=raw_data)
            if not fe_result.success:
                pipeline_errors.append(f"特征工程失败: {fe_result.errors}")

            feature_cols = fe_result.data.get("feature_cols", [])
            X_list = fe_result.data.get("X", [])
            feature_stats = fe_result.data.get("feature_stats", {})

            report_sections["feature_engineering"] = {
                "status": "success" if fe_result.success else "failed",
                "feature_count": len(feature_cols),
                "sample_count": feature_stats.get("sample_count", 0),
                "stats": feature_stats,
            }

            if not X_list or len(X_list) == 0:
                return ToolResult.error_result(
                    "特征矩阵为空，无法继续预测流程",
                    code="EMPTY_FEATURE_MATRIX",
                )

            latest_features = (
                np.array(X_list[-1], dtype=np.float64)
                if isinstance(X_list, list)
                else np.array(X_list[-1:], dtype=np.float64).flatten()
            )
            if latest_features.ndim == 2 and latest_features.shape[0] == 1:
                latest_features = latest_features.flatten()

            recent_original = self._extract_recent_original(raw_data)
            ctx.set("latest_features", latest_features)

        except Exception as e:
            ctx.log.exception("[daily_report] 特征工程阶段异常")
            return ToolResult.error_result(
                f"特征工程阶段异常: {str(e)}",
                code="FEATURE_ENGINEERING_EXCEPTION",
            )

        try:
            pred_tool_cls = registry.get("predictor")
            if pred_tool_cls is None:
                return ToolResult.error_result(
                    "未找到 predictor 工具", code="TOOL_NOT_FOUND_PREDICTOR"
                )
            pred_tool = pred_tool_cls()

            pred_result = pred_tool.execute(
                ctx,
                features=(
                    latest_features.tolist()
                    if isinstance(latest_features, np.ndarray)
                    else latest_features
                ),
                recent_original_data=recent_original,
                top_k=top_k,
            )
            if not pred_result.success:
                pipeline_errors.append(f"预测失败: {pred_result.errors}")
                predictions_data = None
                prediction_summary = None
            else:
                predictions_data = pred_result.data.get("predictions")
                prediction_summary = pred_result.data.get("summary")

            report_sections["prediction"] = {
                "status": "success" if pred_result.success else "failed",
                "top_k": top_k,
                "predictions": predictions_data,
                "summary": prediction_summary,
            }

        except Exception as e:
            ctx.log.exception("[daily_report] 预测阶段异常")
            pipeline_errors.append(f"预测异常: {str(e)}")
            report_sections.setdefault("prediction", {})["status"] = "error"

        if include_model_analysis:
            try:
                ma_tool_cls = registry.get("model_analyzer")
                if ma_tool_cls is not None:
                    ma_tool = ma_tool_cls()
                    ma_result = ma_tool.execute(ctx, load_model=True)
                    report_sections["model_analysis"] = {
                        "status": "success" if ma_result.success else "failed",
                        "health_report": (
                            ma_result.data if ma_result.success else None
                        ),
                    }

            except Exception as e:
                ctx.log.warning(f"[daily_report] 模型诊断跳过: {e}")
                report_sections["model_analysis"] = {
                    "status": "skipped",
                    "reason": str(e),
                }

        if include_optimization:
            try:
                oa_tool_cls = registry.get("optimization_advisor")
                if oa_tool_cls is not None:
                    oa_tool = oa_tool_cls()
                    oa_result = oa_tool.execute(ctx)
                    report_sections["optimization"] = {
                        "status": "success" if oa_result.success else "failed",
                        "suggestions": (
                            oa_result.data if oa_result.success else None
                        ),
                    }

            except Exception as e:
                ctx.log.warning(f"[daily_report] 优化建议跳过: {e}")
                report_sections["optimization"] = {
                    "status": "skipped",
                    "reason": str(e),
                }

        elapsed_ms = (time.time() - start_time) * 1000

        confidence_analysis = self._build_confidence_analysis(report_sections)
        risk_alerts = self._generate_risk_alerts(report_sections)

        final_report = {
            "period": period
            or f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "sections": report_sections,
            "confidence_analysis": confidence_analysis,
            "risk_alerts": risk_alerts,
            "pipeline_errors": pipeline_errors,
        }

        summary = self._build_report_summary(final_report)

        ctx.set("last_daily_report", final_report)
        ctx.record_metric("daily_report.elapsed_ms", elapsed_ms)
        ctx.record_metric("daily_report.sections_count", len(report_sections))
        ctx.record_metric(
            "daily_report.has_errors", int(len(pipeline_errors) > 0)
        )

        return ToolResult.success_result(
            data={
                "report": final_report,
                "summary": summary,
                "metadata": {
                    "period": period,
                    "generated_at": final_report["generated_at"],
                    "elapsed_ms": round(elapsed_ms, 2),
                    "tool_version": "V10.0-APPLICATION",
                },
            },
            tool_name=self.name,
        )

    @staticmethod
    def _extract_recent_original(raw_data: pd.DataFrame) -> Dict[str, Any]:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        recent_original = {}
        window = min(30, len(raw_data))
        tail_df = raw_data.tail(window)
        for pos in POSITIONS:
            if pos in tail_df.columns:
                recent_original[pos] = tail_df[pos].values.astype(float)
        return recent_original

    @staticmethod
    def _build_confidence_analysis(sections: Dict) -> Dict:
        pred_section = sections.get("prediction", {})
        summary = (
            pred_section.get("summary")
            if isinstance(pred_section.get("summary"), dict)
            else {}
        )
        avg_uncertainty = summary.get("avg_uncertainty", 0.5)

        if avg_uncertainty < 0.2:
            level = "high"
            description = "模型对本次预测具有较高置信度"
        elif avg_uncertainty < 0.4:
            level = "medium"
            description = "模型置信度中等，建议参考优化建议调整策略"
        elif avg_uncertainty < 0.6:
            level = "low"
            description = "模型置信度偏低，建议关注近期数据变化趋势"
        else:
            level = "very_low"
            description = "模型置信度很低，强烈建议人工复核后决策"

        model_status = sections.get("model_analysis", {}).get(
            "status", "unknown"
        )
        has_urgent_suggestions = False
        opt_section = sections.get("optimization", {})
        if isinstance(opt_section.get("suggestions"), dict):
            has_urgent_suggestions = (
                opt_section["suggestions"]
                .get("summary", {})
                .get("has_urgent", False)
            )

        overall_confidence = level
        if model_status in ("failed", "error"):
            overall_confidence = (
                min(
                    level,
                    "low",
                    key=lambda x: ["high", "medium", "low", "very_low"].index(
                        x
                    ),
                )
                if level != "very_low"
                else "very_low"
            )
        if has_urgent_suggestions and level == "high":
            overall_confidence = "medium"

        return {
            "prediction_confidence": level,
            "avg_uncertainty": round(avg_uncertainty, 4),
            "model_health_status": model_status,
            "has_urgent_suggestions": has_urgent_suggestions,
            "overall_confidence": overall_confidence,
            "description": description,
        }

    @staticmethod
    def _generate_risk_alerts(sections: Dict) -> List[Dict]:
        alerts = []
        pred_section = sections.get("prediction", {})
        if pred_section.get("status") != "success":
            alerts.append(
                {
                    "level": "urgent",
                    "category": "prediction_failure",
                    "message": "预测环节未成功完成，报告中可能缺少关键推荐数据",
                }
            )

        summary = (
            pred_section.get("summary")
            if isinstance(pred_section.get("summary"), dict)
            else {}
        )
        avg_unc = summary.get("avg_uncertainty", 0)
        if avg_unc > 0.6:
            alerts.append(
                {
                    "level": "warning",
                    "category": "high_uncertainty",
                    "message": f"平均不确定性过高({avg_unc:.4f})，预测可靠性存疑",
                }
            )

        ma_section = sections.get("model_analysis", {})
        health = (
            ma_section.get("health_report")
            if isinstance(ma_section.get("health_report"), dict)
            else {}
        )
        integrity = health.get("integrity_check", {})
        if isinstance(integrity, dict) and not integrity.get("valid", True):
            alerts.append(
                {
                    "level": "urgent",
                    "category": "model_integrity",
                    "message": "模型完整性校验未通过，建议重新训练或检查模型文件",
                }
            )

        components = health.get("components", {})
        if isinstance(components, dict):
            unloaded = [
                name
                for name, info in components.items()
                if isinstance(info, dict) and not info.get("loaded", True)
            ]
            if unloaded:
                alerts.append(
                    {
                        "level": "warning",
                        "category": "component_missing",
                        "message": f"以下模型组件未正常加载: {', '.join(unloaded)}",
                    }
                )

        opt_section = sections.get("optimization", {})
        suggestions = (
            opt_section.get("suggestions")
            if isinstance(opt_section.get("suggestions"), dict)
            else {}
        )
        if isinstance(suggestions.get("summary", dict), dict) and suggestions[
            "summary"
        ].get("has_urgent"):
            alerts.append(
                {
                    "level": "important",
                    "category": "optimization_needed",
                    "message": "系统生成了紧急级优化建议，请查看优化建议部分",
                }
            )

        if not alerts:
            alerts.append(
                {
                    "level": "info",
                    "category": "all_clear",
                    "message": "所有检测项通过，未发现显著风险",
                }
            )

        return alerts

    @staticmethod
    def _build_report_summary(report: Dict) -> Dict:
        sections = report.get("sections", {})
        pred_sec = sections.get("prediction", {})
        summary = (
            pred_sec.get("summary")
            if isinstance(pred_sec.get("summary"), dict)
            else {}
        )
        positions_detail = (
            summary.get("positions", {})
            if isinstance(summary.get("positions"), dict)
            else {}
        )

        top_recommendations = {}
        for pos, detail in positions_detail.items():
            if isinstance(detail, dict):
                top_recommendations[pos] = detail.get(
                    "top_k_recommendations", []
                )

        conf = report.get("confidence_analysis", {})
        alert_count = sum(
            1
            for a in report.get("risk_alerts", [])
            if a.get("level") in ("urgent", "warning")
        )

        return {
            "period": report.get("period"),
            "overall_status": (
                "healthy" if alert_count == 0 else "attention_required"
            ),
            "alert_count": alert_count,
            "confidence_level": conf.get("overall_confidence", "unknown"),
            "top_recommendations": top_recommendations,
            "sections_completed": [
                k for k, v in sections.items() if v.get("status") == "success"
            ],
            "sections_failed_or_skipped": [
                k
                for k, v in sections.items()
                if v.get("status") not in ("success",)
            ],
        }


# ================================================================
# 2. QuickPredictTool — 快速简化预测
# ================================================================


@register_tool(tags=["prediction", "application", "quick"])
class QuickPredictTool(BaseTool):
    """快速简化预测工具 (Layer 3 - APPLICATION)

    面向非技术用户的一键式预测入口。
    支持两种输入模式：
        1. 通过期号自动加载数据并预测
        2. 直接提供最近开奖号码列表，自动构建特征向量

    输出为简化的、易读的预测结果：
        - 各位置最佳推荐号码（Top-K）
        - 每个位置的最佳单一推荐
        - 整体置信度评估
        - 简要的风险提示

    Args:
        period: 目标期号（可选，与 recent_numbers 二选一）
        recent_numbers: 最近一期开奖号码列表 [wan, qian, bai, shi, ge]
        top_k: 推荐号码数量，默认 8
        auto_load: 是否自动加载数据（当提供了 period 时），默认 True
    """

    name = "quick_predict"
    description = (
        "快速简化预测：输入期号或最近号码→自动构建特征→输出Top-N推荐+置信度"
    )
    layer = ToolLayer.APPLICATION
    tags = ["prediction", "application", "quick", "user_friendly"]

    input_schema = {
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "description": "目标期号（如 '2026080'）",
            },
            "recent_numbers": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "最近开奖号码列表 [wan, qian, bai, shi, ge]",
            },
            "top_k": {
                "type": "integer",
                "description": "推荐号码数量",
                "default": 8,
            },
            "auto_load": {
                "type": "boolean",
                "description": "是否自动加载数据",
                "default": True,
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "recommendations": {"type": "object"},
            "best_pick": {"type": "object"},
            "confidence": {"type": "object"},
            "quick_summary": {"type": "string"},
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        period = kwargs.get("period")
        recent_numbers = kwargs.get("recent_numbers")
        top_k = kwargs.get("top_k", 8)
        auto_load = kwargs.get("auto_load", True)

        if not period and not recent_numbers:
            return ToolResult.error_result(
                "必须提供 period 或 recent_numbers 中的至少一个参数",
                code="MISSING_INPUT",
            )

        if recent_numbers is not None:
            if not isinstance(recent_numbers, (list, tuple)):
                return ToolResult.error_result(
                    f"recent_numbers 必须是列表类型，实际: {type(recent_numbers).__name__}",
                    code="INVALID_RECENT_NUMBERS_TYPE",
                )
            if len(recent_numbers) != 5:
                return ToolResult.error_result(
                    f"recent_numbers 需要恰好 5 个元素 [万,千,百,十,个]，实际 {len(recent_numbers)} 个",
                    code="INVALID_RECENT_NUMBERS_LENGTH",
                )
            for i, num in enumerate(recent_numbers):
                if not isinstance(num, int) or num < 0 or num > 9:
                    return ToolResult.error_result(
                        f"recent_numbers[{i}]={num} 无效，每个元素必须是 0-9 的整数",
                        code="INVALID_NUMBER_VALUE",
                    )

        registry = get_registry()

        try:
            features = self._resolve_features(
                ctx, registry, period, recent_numbers, auto_load
            )
            if features is None:
                return ToolResult.error_result(
                    "特征构建失败，无法进行预测",
                    code="FEATURE_RESOLUTION_FAILED",
                )

            pred_tool_cls = registry.get("predictor")
            if pred_tool_cls is None:
                return ToolResult.error_result(
                    "未找到 predictor 工具", code="TOOL_NOT_FOUND_PREDICTOR"
                )
            pred_tool = pred_tool_cls()

            recent_original = (
                self._build_recent_from_numbers(recent_numbers)
                if recent_numbers
                else None
            )
            pred_result = pred_tool.execute(
                ctx,
                features=(
                    features.tolist()
                    if isinstance(features, np.ndarray)
                    else features
                ),
                recent_original_data=recent_original,
                top_k=top_k,
            )

            if not pred_result.success:
                return ToolResult.error_result(
                    f"预测执行失败: {pred_result.errors[0].message if pred_result.errors else 'unknown'}",
                    code="PREDICTION_FAILED",
                )

            predictions = pred_result.data.get("predictions", {})
            summary = pred_result.data.get("summary", {})

            recommendations, best_pick, confidence = self._format_quick_output(
                predictions, summary, top_k
            )
            quick_summary = self._generate_quick_summary(best_pick, confidence)

            ctx.set(
                "last_quick_prediction",
                {
                    "recommendations": recommendations,
                    "best_pick": best_pick,
                    "confidence": confidence,
                },
            )
            ctx.record_metric("quick_predict.top_k", top_k)
            ctx.record_metric(
                "quick_predict.confidence_level",
                confidence.get("level", "unknown"),
            )

            return ToolResult.success_result(
                data={
                    "recommendations": recommendations,
                    "best_pick": best_pick,
                    "confidence": confidence,
                    "quick_summary": quick_summary,
                    "period": period,
                    "input_mode": (
                        "numbers" if recent_numbers else "period_auto"
                    ),
                },
                tool_name=self.name,
            )

        except Exception as e:
            ctx.log.exception("[quick_predict] 执行异常")
            return ToolResult.error_result(
                f"快速预测执行异常: {str(e)}", code="QUICK_PREDICT_EXCEPTION"
            )

    def _resolve_features(
        self,
        ctx: ToolContext,
        registry,
        period: Optional[str],
        recent_numbers: Optional[List[int]],
        auto_load: bool,
    ) -> Optional[np.ndarray]:
        if recent_numbers is not None:
            return self._features_from_numbers(ctx, registry, recent_numbers)
        if period and auto_load:
            return self._features_from_period(ctx, registry, period)
        return None

    def _features_from_numbers(
        self, ctx: ToolContext, registry, numbers: List[int]
    ) -> Optional[np.ndarray]:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        row = {"period": "manual_input"}
        for i, pos in enumerate(POSITIONS):
            row[pos] = numbers[i]

        df = pd.DataFrame([row])

        fe_tool_cls = registry.get("feature_engineer")
        if fe_tool_cls is None:
            ctx.log.warning(
                "[quick_predict] feature_engineer 未注册，使用零向量作为特征"
            )
            return np.zeros(100, dtype=np.float64)

        fe_tool = fe_tool_cls()
        fe_result = fe_tool.execute(ctx, raw_data=df)
        if not fe_result.success or fe_result.data.get("X") is None:
            ctx.log.warning("[quick_predict] 特征工程失败，使用零向量")
            return np.zeros(100, dtype=np.float64)

        X_list = fe_result.data["X"]
        if isinstance(X_list, list) and len(X_list) > 0:
            arr = np.array(X_list[-1], dtype=np.float64)
            return arr.flatten() if arr.ndim >= 1 else arr
        return (
            np.array(X_list, dtype=np.float64).flatten()
            if hasattr(X_list, "__len__")
            else np.zeros(100, dtype=np.float64)
        )

    def _features_from_period(
        self, ctx: ToolContext, registry, period: str
    ) -> Optional[np.ndarray]:
        dl_tool_cls = registry.get("data_loader")
        if dl_tool_cls is None:
            return None

        dl_tool = dl_tool_cls()
        default_paths = [
            "data/pl5_history.csv",
            "data/latest.csv",
            "pl5_data.csv",
        ]
        data_source = None
        for p in default_paths:
            if os.path.exists(p):
                data_source = p
                break
        if data_source is None:
            return None

        dl_result = dl_tool.execute(ctx, path_or_data=data_source)
        if not dl_result.success:
            return None

        raw_data = dl_result.data.get("data")
        if not isinstance(raw_data, pd.DataFrame) or raw_data.empty:
            return None

        fe_tool_cls = registry.get("feature_engineer")
        if fe_tool_cls is None:
            return None

        fe_tool = fe_tool_cls()
        fe_result = fe_tool.execute(ctx, raw_data=raw_data)
        if not fe_result.success or fe_result.data.get("X") is None:
            return None

        X_list = fe_result.data["X"]
        if isinstance(X_list, list) and len(X_list) > 0:
            arr = np.array(X_list[-1], dtype=np.float64)
            return arr.flatten() if arr.ndim >= 1 else arr
        return None

    @staticmethod
    def _build_recent_from_numbers(numbers: List[int]) -> Dict[str, Any]:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        result = {}
        for i, pos in enumerate(POSITIONS):
            result[pos] = np.array([float(numbers[i])])
        return result

    @staticmethod
    def _format_quick_output(
        predictions: Dict, summary: Dict, top_k: int
    ) -> Tuple[Dict, Dict, Dict]:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        recommendations = {}
        best_pick = {}

        positions_detail = (
            summary.get("positions", {})
            if isinstance(summary.get("positions"), dict)
            else {}
        )
        avg_uncertainty = summary.get("avg_uncertainty", 0.5)

        for pos in POSITIONS:
            if pos in predictions and isinstance(predictions[pos], dict):
                top_k_list = predictions[pos].get("top_k", [])
                recommendations[pos] = {
                    "top_k": top_k_list[:top_k],
                    "uncertainty": round(
                        predictions[pos].get("uncertainty", 0.0), 4
                    ),
                }
                if top_k_list:
                    best_pick[pos] = top_k_list[0]
                else:
                    best_pick[pos] = None
            elif pos in positions_detail:
                detail = positions_detail[pos]
                recs = detail.get("top_k_recommendations", [])
                recommendations[pos] = {
                    "top_k": recs[:top_k],
                    "uncertainty": detail.get("uncertainty", 0.0),
                }
                best_pick[pos] = recs[0] if recs else None
            else:
                recommendations[pos] = {"top_k": [], "uncertainty": 1.0}
                best_pick[pos] = None

        if avg_uncertainty < 0.25:
            conf_level = "high"
            conf_desc = "模型对该次预测具有较高的可信度"
        elif avg_uncertainty < 0.45:
            conf_level = "medium"
            conf_desc = "预测置信度适中，建议结合其他参考"
        elif avg_uncertainty < 0.65:
            conf_level = "low"
            conf_desc = "预测置信度较低，仅供参考"
        else:
            conf_level = "very_low"
            conf_desc = "预测置信度很低，强烈建议人工复核"

        confidence = {
            "level": conf_level,
            "avg_uncertainty": round(avg_uncertainty, 4),
            "description": conf_desc,
        }

        return recommendations, best_pick, confidence

    @staticmethod
    def _generate_quick_summary(best_pick: Dict, confidence: Dict) -> str:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        POS_NAMES = ["万位", "千位", "百位", "十位", "个位"]
        parts = [f"【PL5快速预测】"]
        number_str = ""
        valid_count = 0
        for pos, name in zip(POSITIONS, POS_NAMES):
            val = best_pick.get(pos)
            if val is not None:
                number_str += str(val)
                valid_count += 1
            else:
                number_str += "?"
        parts.append(f"推荐号码: {number_str}")
        parts.append(f"置信度: {confidence.get('level', 'unknown')}")
        if confidence.get("level") in ("low", "very_low"):
            parts.append(f"⚠️ {confidence.get('description', '')}")
        return " | ".join(parts)


# ================================================================
# 3. BacktestTool — 策略历史回测
# ================================================================


@register_tool(tags=["backtest", "application", "evaluation"])
class BacktestTool(BaseTool):
    """策略历史回测工具 (Layer 3 - APPLICATION)

    对指定的历史时间段进行逐期模拟预测，对比实际开奖结果，
    全面评估预测策略的历史表现。

    流程：
        加载历史数据 → 按时间窗口逐期特征工程 → 逐期预测 → 对比实际 → 计算指标

    输出的回测报告包含：
        - 总期数 / 有效预测期数
        - 各位置命中率 / 整体命中率
        - Top-3 / Top-5 准确率
        - 趋势图数据（准确率时间序列）
        - 最优参数建议（基于回测统计）

    Args:
        start_period: 起始期号（如 "2026001"）
        end_period: 结束期号（如 "2026079"）
        strategy_config: 策略配置字典，可包含:
            - top_k: 推荐 K 值（默认 8）
            - window_size: 特征构建窗口大小（默认 50）
            - step: 步进间隔（默认 1，即每期都预测）
        data_source: 数据源路径（可选，默认自动查找）
    """

    name = "backtest"
    description = (
        "策略历史回测：逐期预测+实际对比→命中率/TopN准确率/趋势图/最优参数建议"
    )
    layer = ToolLayer.APPLICATION
    tags = ["backtest", "application", "evaluation", "history"]

    input_schema = {
        "type": "object",
        "properties": {
            "start_period": {
                "type": "string",
                "description": "起始期号（如 '2026001'）",
            },
            "end_period": {
                "type": "string",
                "description": "结束期号（如 '2026079'）",
            },
            "strategy_config": {
                "type": "object",
                "description": "策略配置字典 {top_k, window_size, step}",
            },
            "data_source": {
                "type": ["string", "object"],
                "description": "数据源路径或 DataFrame",
            },
        },
        "required": ["start_period", "end_period"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "backtest_report": {
                "type": "object",
                "description": "完整回测报告",
            },
            "summary": {"type": "object", "description": "回测摘要"},
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        start_period = kwargs.get("start_period")
        end_period = kwargs.get("end_period")
        strategy_config = kwargs.get("strategy_config") or {}
        data_source = kwargs.get("data_source")

        if not start_period or not end_period:
            return ToolResult.error_result(
                "start_period 和 end_period 为必填参数",
                code="MISSING_PERIOD_RANGE",
            )

        top_k = strategy_config.get("top_k", 8)
        window_size = strategy_config.get("window_size", 50)
        step = strategy_config.get("step", 1)

        registry = get_registry()
        start_time = time.time()

        try:
            dl_tool_cls = registry.get("data_loader")
            if dl_tool_cls is None:
                return ToolResult.error_result(
                    "未找到 data_loader 工具",
                    code="TOOL_NOT_FOUND_DATA_LOADER",
                )
            dl_tool = dl_tool_cls()

            if data_source is None:
                for p in [
                    "data/pl5_history.csv",
                    "data/latest.csv",
                    "pl5_data.csv",
                ]:
                    if os.path.exists(p):
                        data_source = p
                        break
            if data_source is None:
                return ToolResult.error_result(
                    "未找到数据源文件", code="DATA_SOURCE_NOT_FOUND"
                )

            dl_result = dl_tool.execute(ctx, path_or_data=data_source)
            if not dl_result.success:
                return ToolResult.error_result(
                    f"数据加载失败: {dl_result.errors[0].message if dl_result.errors else 'unknown'}",
                    code="DATA_LOAD_FAILED",
                )

            full_data = dl_result.data.get("data")
            if not isinstance(full_data, pd.DataFrame) or full_data.empty:
                return ToolResult.error_result(
                    "数据为空或格式错误", code="EMPTY_DATA"
                )

        except Exception as e:
            ctx.log.exception("[backtest] 数据加载异常")
            return ToolResult.error_result(
                f"数据加载异常: {str(e)}", code="DATA_LOAD_EXCEPTION"
            )

        try:
            filtered_data = self._filter_by_period_range(
                full_data, start_period, end_period
            )
            if filtered_data.empty:
                return ToolResult.error_result(
                    f"在 [{start_period}, {end_period}] 范围内未找到有效数据",
                    code="NO_DATA_IN_RANGE",
                )

            total_periods = len(filtered_data)
            ctx.log.info(
                f"[backtest] 回测范围: {total_periods} 期 ({start_period} ~ {end_period})"
            )

        except Exception as e:
            return ToolResult.error_result(
                f"期间筛选失败: {str(e)}", code="PERIOD_FILTER_FAILED"
            )

        backtest_results = []
        prediction_records = []
        actual_records = []

        try:
            pred_tool_cls = registry.get("predictor")
            fe_tool_cls = registry.get("feature_engineer")
            if pred_tool_cls is None or fe_tool_cls is None:
                return ToolResult.error_result(
                    "predictor 或 feature_engineer 工具未注册",
                    code="CORE_TOOLS_NOT_FOUND",
                )
            pred_tool = pred_tool_cls()
            fe_tool = fe_tool_cls()

            periods_list = filtered_data["period"].tolist()
            predict_indices = list(range(window_size, total_periods, step))

            for idx in predict_indices:
                current_period = periods_list[idx]
                train_slice = filtered_data.iloc[
                    max(0, idx - window_size) : idx
                ]

                if train_slice.empty:
                    continue

                try:
                    fe_result = fe_tool.execute(ctx, raw_data=train_slice)
                    if (
                        not fe_result.success
                        or fe_result.data.get("X") is None
                    ):
                        continue

                    X_list = fe_result.data["X"]
                    if not X_list:
                        continue

                    latest_features = np.array(X_list[-1], dtype=np.float64)
                    if latest_features.ndim == 2:
                        latest_features = latest_features.flatten()

                    recent_original = self._extract_backtest_recent(
                        train_slice
                    )

                    pred_result = pred_tool.execute(
                        ctx,
                        features=latest_features.tolist(),
                        recent_original_data=recent_original,
                        top_k=top_k,
                    )

                    if pred_result.success:
                        pred_data = pred_result.data.get("predictions", {})
                        actual_row = filtered_data.iloc[idx]
                        actual_dict = {
                            "wan": int(actual_row.get("wan", -1)),
                            "qian": int(actual_row.get("qian", -1)),
                            "bai": int(actual_row.get("bai", -1)),
                            "shi": int(actual_row.get("shi", -1)),
                            "ge": int(actual_row.get("ge", -1)),
                        }

                        period_metrics = self._compute_period_metrics(
                            pred_data, actual_dict, top_k
                        )
                        period_metrics["period"] = str(current_period)
                        backtest_results.append(period_metrics)
                        prediction_records.append(pred_data)
                        actual_records.append(actual_dict)

                except Exception as loop_e:
                    ctx.log.debug(
                        f"[backtest] 期号 {current_period} 回测跳过: {loop_e}"
                    )
                    continue

        except Exception as e:
            ctx.log.exception("[backtest] 回测循环异常")
            return ToolResult.error_result(
                f"回测过程异常: {str(e)}", code="BACKTEST_LOOP_EXCEPTION"
            )

        if not backtest_results:
            return ToolResult.success_result(
                data={
                    "backtest_report": {
                        "status": "no_valid_results",
                        "message": "回测过程中未产生任何有效的预测结果",
                        "range": {"start": start_period, "end": end_period},
                        "strategy": strategy_config,
                    },
                    "summary": {"total_periods_tested": 0},
                },
                tool_name=self.name,
            )

        report = self._build_backtest_report(
            backtest_results,
            prediction_records,
            actual_records,
            start_period,
            end_period,
            strategy_config,
            total_periods,
            time.time() - start_time,
        )

        ctx.set("last_backtest_report", report)
        ctx.record_metric("backtest.total_periods", total_periods)
        ctx.record_metric("backtest.valid_predictions", len(backtest_results))
        ctx.record_metric(
            "backtest.overall_hit_rate", report["summary"]["overall_hit_rate"]
        )

        return ToolResult.success_result(
            data={
                "backtest_report": report,
                "summary": report["summary"],
            },
            tool_name=self.name,
        )

    @staticmethod
    def _filter_by_period_range(
        df: pd.DataFrame, start_p: str, end_p: str
    ) -> pd.DataFrame:
        if "period" not in df.columns:
            return df.head(0)
        period_col = df["period"].astype(str)
        mask = (period_col >= str(start_p)) & (period_col <= str(end_p))
        return df.loc[mask].reset_index(drop=True)

    @staticmethod
    def _extract_backtest_recent(train_slice: pd.DataFrame) -> Dict[str, Any]:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        recent = {}
        for pos in POSITIONS:
            if pos in train_slice.columns:
                recent[pos] = train_slice[pos].tail(30).values.astype(float)
        return recent

    @staticmethod
    def _compute_period_metrics(
        prediction: Dict, actual: Dict, top_k: int
    ) -> Dict:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        position_hits = {}
        position_top3_hits = {}
        position_top5_hits = {}
        total_hits = 0
        total_top3_hits = 0
        total_top5_hits = 0
        valid_positions = 0

        for pos in POSITIONS:
            if pos not in prediction or pos not in actual:
                continue
            actual_val = actual[pos]
            if actual_val < 0:
                continue
            valid_positions += 1
            pred_info = prediction[pos]
            if not isinstance(pred_info, dict):
                continue
            top_k_list = pred_info.get("top_k", [])

            hit = 1 if actual_val in top_k_list else 0
            top3_hit = 1 if actual_val in top_k_list[:3] else 0
            top5_hit = 1 if actual_val in top_k_list[:5] else 0

            position_hits[pos] = hit
            position_top3_hits[pos] = top3_hit
            position_top5_hits[pos] = top5_hit
            total_hits += hit
            total_top3_hits += top3_hit
            total_top5_hits += top5_hit

        return {
            "position_hits": position_hits,
            "position_top3_hits": position_top3_hits,
            "position_top5_hits": position_top5_hits,
            "total_hits": total_hits,
            "total_top3_hits": total_top3_hits,
            "total_top5_hits": total_top5_hits,
            "valid_positions": valid_positions,
            "hit_rate": total_hits / max(valid_positions, 1),
            "top3_rate": total_top3_hits / max(valid_positions, 1),
            "top5_rate": total_top5_hits / max(valid_positions, 1),
        }

    @classmethod
    def _build_backtest_report(
        cls,
        results: List[Dict],
        preds: List[Dict],
        actuals: List[Dict],
        start_p: str,
        end_p: str,
        strategy: Dict,
        total_periods: int,
        elapsed: float,
    ) -> Dict:
        n = len(results)
        hit_rates = [r["hit_rate"] for r in results]
        top3_rates = [r["top3_rate"] for r in results]
        top5_rates = [r["top5_rate"] for r in results]

        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        position_stats = {}
        for pos in POSITIONS:
            pos_hits = [r["position_hits"].get(pos, 0) for r in results]
            pos_total = sum(
                1
                for r in results
                if r["valid_positions"] > 0 and pos in r["position_hits"]
            )
            position_stats[pos] = {
                "hits": sum(pos_hits),
                "total": pos_total,
                "hit_rate": round(sum(pos_hits) / max(pos_total, 1), 6),
            }

        trend_data = [
            {
                "period": r.get("period", ""),
                "hit_rate": round(r["hit_rate"], 6),
                "top3_rate": round(r["top3_rate"], 6),
                "top5_rate": round(r["top5_rate"], 6),
            }
            for r in results
        ]

        moving_avg_window = min(10, n)
        trend_with_ma = []
        for i, t in enumerate(trend_data):
            entry = dict(t)
            if i >= moving_avg_window - 1:
                ma_vals = [
                    trend_data[j]["hit_rate"]
                    for j in range(i - moving_avg_window + 1, i + 1)
                ]
                entry["ma_hit_rate"] = round(np.mean(ma_vals), 6)
            else:
                entry["ma_hit_rate"] = None
            trend_with_ma.append(entry)

        optimal_params = cls._suggest_optimal_params(results, strategy)

        report = {
            "status": "completed",
            "range": {"start": start_p, "end": end_p},
            "strategy_applied": strategy,
            "overview": {
                "total_periods_in_range": total_periods,
                "valid_predictions": n,
                "prediction_coverage": round(n / max(total_periods, 1), 4),
                "elapsed_seconds": round(elapsed, 2),
            },
            "metrics": {
                "overall_hit_rate": round(float(np.mean(hit_rates)), 6),
                "overall_top3_rate": round(float(np.mean(top3_rates)), 6),
                "overall_top5_rate": round(float(np.mean(top5_rates)), 6),
                "max_hit_rate": round(float(np.max(hit_rates)), 6),
                "min_hit_rate": round(float(np.min(hit_rates)), 6),
                "std_hit_rate": (
                    round(float(np.std(hit_rates)), 6) if n > 1 else 0.0
                ),
                "median_hit_rate": round(float(np.median(hit_rates)), 6),
            },
            "position_breakdown": position_stats,
            "trend_data": trend_with_ma,
            "optimal_parameters": optimal_params,
        }

        report["summary"] = {
            "total_periods_tested": total_periods,
            "valid_predictions": n,
            "overall_hit_rate": report["metrics"]["overall_hit_rate"],
            "overall_top3_rate": report["metrics"]["overall_top3_rate"],
            "overall_top5_rate": report["metrics"]["overall_top5_rate"],
            "best_position": (
                max(position_stats.items(), key=lambda x: x[1]["hit_rate"])[0]
                if position_stats
                else "N/A"
            ),
            "worst_position": (
                min(position_stats.items(), key=lambda x: x[1]["hit_rate"])[0]
                if position_stats
                else "N/A"
            ),
            "recommended_top_k": optimal_params.get(
                "recommended_top_k", strategy.get("top_k", 8)
            ),
        }

        return report

    @staticmethod
    def _suggest_optimal_params(
        results: List[Dict], current_strategy: Dict
    ) -> Dict:
        suggestions = {
            "current_top_k": current_strategy.get("top_k", 8),
            "current_window_size": current_strategy.get("window_size", 50),
            "analysis": {},
        }

        hit_rates = [r["hit_rate"] for r in results]
        avg_hr = float(np.mean(hit_rates))

        if avg_hr >= 0.5:
            suggestions["analysis"]["hit_rate_assessment"] = "excellent"
            suggestions["recommended_top_k"] = current_strategy.get("top_k", 8)
            suggestions["note"] = "当前策略表现优秀，建议保持现有参数"
        elif avg_hr >= 0.3:
            suggestions["analysis"]["hit_rate_assessment"] = "good"
            suggested_tk = min(current_strategy.get("top_k", 8) + 2, 10)
            suggestions["recommended_top_k"] = suggested_tk
            suggestions["note"] = (
                f"表现良好，可尝试增大 top_k 到 {suggested_tk} 以提升覆盖率"
            )
        elif avg_hr >= 0.15:
            suggestions["analysis"]["hit_rate_assessment"] = "moderate"
            suggested_tk = min(current_strategy.get("top_k", 8) + 3, 10)
            suggestions["recommended_top_k"] = suggested_tk
            suggestions["recommended_window_size"] = max(
                current_strategy.get("window_size", 50) + 20, 80
            )
            suggestions["note"] = (
                "表现一般，建议增大窗口和 top_k 以获得更多参考信息"
            )
        else:
            suggestions["analysis"][
                "hit_rate_assessment"
            ] = "needs_improvement"
            suggestions["recommended_top_k"] = 10
            suggestions["recommended_window_size"] = 100
            suggestions["note"] = "表现较低，建议全面审查数据和模型配置"

        std_hr = float(np.std(hit_rates)) if len(hit_rates) > 1 else 0.0
        if std_hr > 0.2:
            suggestions["stability_note"] = (
                f"命中率波动较大(std={std_hr:.4f})，建议关注数据稳定性"
            )

        half_point = len(results) // 2
        if half_point > 5:
            first_half = np.mean([r["hit_rate"] for r in results[:half_point]])
            second_half = np.mean(
                [r["hit_rate"] for r in results[half_point:]]
            )
            if second_half > first_half + 0.05:
                suggestions["trend_observation"] = (
                    "后半段表现优于前半段，模型可能正在改善"
                )
            elif second_half < first_half - 0.05:
                suggestions["trend_observation"] = (
                    "后半段表现下降，可能存在数据漂移"
                )

        return suggestions


# ================================================================
# 4. ComparisonTool — 多模型/A/B对比
# ================================================================


@register_tool(tags=["comparison", "application", "analysis"])
class ComparisonTool(BaseTool):
    """多模型/A/B对比工具 (Layer 3 - APPLICATION)

    对两组或多组预测结果进行全面对比分析：
        - 各模型基本准确率对比
        - 位置级别命中差异
        - 统计显著性检验（配对检验近似）
        - 胜率统计（A vs B 逐期比较谁更好）
        - 综合结论与推荐

    Args:
        predictions_a: A组预测记录列表（每条为一个位置预测字典）
        predictions_b: B组预测记录列表
        actuals: 实际开奖结果列表（每条为 {pos: value} 字典）
        labels: 标签配置字典，可选:
            - label_a: A组名称（默认 "Model_A"）
            - label_b: B组名称（默认 "Model_B"）
            - top_n: 用于计算准确率的 N 值（默认 5）
    """

    name = "comparison"
    description = "多模型A/B对比：准确率对比/显著性检验/胜率统计/综合推荐结论"
    layer = ToolLayer.APPLICATION
    tags = ["comparison", "application", "analysis", "ab_test"]

    input_schema = {
        "type": "object",
        "properties": {
            "predictions_a": {
                "type": "array",
                "description": "A组预测记录列表",
            },
            "predictions_b": {
                "type": "array",
                "description": "B组预测记录列表",
            },
            "actuals": {
                "type": "array",
                "description": "实际结果列表",
            },
            "labels": {
                "type": "object",
                "description": "标签配置 {label_a, label_b, top_n}",
            },
        },
        "required": ["predictions_a", "predictions_b", "actuals"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "comparison_report": {
                "type": "object",
                "description": "完整对比报告",
            },
            "conclusion": {"type": "string", "description": "文字结论"},
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        predictions_a = kwargs.get("predictions_a")
        predictions_b = kwargs.get("predictions_b")
        actuals = kwargs.get("actuals")
        labels = kwargs.get("labels") or {}

        if not predictions_a or not predictions_b or not actuals:
            return ToolResult.error_result(
                "predictions_a, predictions_b 和 actuals 均为必填且不能为空",
                code="MISSING_COMPARISON_DATA",
            )

        n_a = len(predictions_a)
        n_b = len(predictions_b)
        n_actual = len(actuals)

        if n_a != n_b or n_a != n_actual:
            return ToolResult.error_result(
                f"数据长度不一致: A={n_a}, B={n_b}, actual={n_actual}，三者必须相等",
                code="LENGTH_MISMATCH",
            )

        label_a = labels.get("label_a", "Model_A")
        label_b = labels.get("label_b", "Model_B")
        top_n = labels.get("top_n", 5)

        start_time = time.time()

        try:
            metrics_a = self._compute_group_metrics(
                predictions_a, actuals, top_n
            )
            metrics_b = self._compute_group_metrics(
                predictions_b, actuals, top_n
            )

            position_comparison = self._compare_positions(
                predictions_a, predictions_b, actuals, top_n
            )

            significance = self._significance_test(
                metrics_a["per_period_accuracies"],
                metrics_b["per_period_accuracies"],
            )

            win_loss = self._compute_win_loss(
                predictions_a, predictions_b, actuals, top_n
            )

            conclusion_text = self._generate_conclusion(
                label_a, label_b, metrics_a, metrics_b, win_loss, significance
            )

            elapsed = time.time() - start_time

            report = {
                "meta": {
                    "label_a": label_a,
                    "label_b": label_b,
                    "sample_size": n_a,
                    "top_n": top_n,
                    "generated_at": datetime.now().isoformat(),
                    "elapsed_seconds": round(elapsed, 4),
                },
                "accuracy_comparison": {
                    label_a: {
                        "overall_accuracy": metrics_a["overall_accuracy"],
                        "top_n_accuracy": metrics_a["top_n_accuracy"],
                        "avg_position_hits": metrics_a["avg_position_hits"],
                        "std_accuracy": metrics_a["std_accuracy"],
                    },
                    label_b: {
                        "overall_accuracy": metrics_b["overall_accuracy"],
                        "top_n_accuracy": metrics_b["top_n_accuracy"],
                        "avg_position_hits": metrics_b["avg_position_hits"],
                        "std_accuracy": metrics_b["std_accuracy"],
                    },
                    "diff": round(
                        metrics_a["overall_accuracy"]
                        - metrics_b["overall_accuracy"],
                        6,
                    ),
                    "diff_pct": self._safe_pct_diff(
                        metrics_a["overall_accuracy"],
                        metrics_b["overall_accuracy"],
                    ),
                },
                "position_comparison": position_comparison,
                "significance_test": significance,
                "win_loss_statistics": win_loss,
                "conclusion": conclusion_text,
                "recommendation": self._make_recommendation(
                    label_a,
                    label_b,
                    metrics_a,
                    metrics_b,
                    win_loss,
                    significance,
                ),
            }

            ctx.set("last_comparison_report", report)
            ctx.record_metric("comparison.sample_size", n_a)
            ctx.record_metric(
                "comparison.winner", win_loss.get("winner", "tie")
            )

            return ToolResult.success_result(
                data={
                    "comparison_report": report,
                    "conclusion": conclusion_text,
                },
                tool_name=self.name,
            )

        except Exception as e:
            ctx.log.exception("[comparison] 对比分析异常")
            return ToolResult.error_result(
                f"对比分析异常: {str(e)}", code="COMPARISON_EXCEPTION"
            )

    @staticmethod
    def _compute_group_metrics(
        predictions: List[Dict], actuals: List[Dict], top_n: int
    ) -> Dict:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        per_period_acc = []
        per_period_pos_hits = []

        for pred, actual in zip(predictions, actuals):
            hits = 0
            pos_hits = 0
            total_pos = 0
            for pos in POSITIONS:
                if pos not in pred or pos not in actual:
                    continue
                actual_val = actual[pos]
                pred_info = pred[pos]
                if not isinstance(pred_info, dict):
                    continue
                total_pos += 1
                top_k = pred_info.get("top_k", [])
                if actual_val in top_k:
                    hits += 1
                    pos_hits += 1
                elif actual_val in top_k[:top_n]:
                    pos_hits += 1

            acc = hits / max(total_pos, 1)
            per_period_acc.append(acc)
            per_period_pos_hits.append(pos_hits)

        arr = np.array(per_period_acc) if per_period_acc else np.array([0.0])
        return {
            "overall_accuracy": round(float(np.mean(arr)), 6),
            "top_n_accuracy": (
                round(float(np.mean(per_period_pos_hits)) / 5.0, 6)
                if per_period_pos_hits
                else 0.0
            ),
            "avg_position_hits": (
                round(float(np.mean(per_period_pos_hits)), 4)
                if per_period_pos_hits
                else 0.0
            ),
            "std_accuracy": (
                round(float(np.std(arr)), 6) if len(arr) > 1 else 0.0
            ),
            "per_period_accuracies": per_period_acc,
        }

    @staticmethod
    def _compare_positions(
        preds_a: List[Dict],
        preds_b: List[Dict],
        actuals: List[Dict],
        top_n: int,
    ) -> Dict:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        comparison = {}
        for pos in POSITIONS:
            hits_a = 0
            hits_b = 0
            total = 0
            for pa, pb, act in zip(preds_a, preds_b, actuals):
                if pos not in pa or pos not in pb or pos not in act:
                    continue
                actual_val = act[pos]
                total += 1
                info_a = pa[pos] if isinstance(pa[pos], dict) else {}
                info_b = pb[pos] if isinstance(pb[pos], dict) else {}
                topka = info_a.get("top_k", [])
                topkb = info_b.get("top_k", [])
                if actual_val in topka:
                    hits_a += 1
                if actual_val in topkb:
                    hits_b += 1

            comparison[pos] = {
                "a_hits": hits_a,
                "b_hits": hits_b,
                "total": total,
                "a_rate": round(hits_a / max(total, 1), 6),
                "b_rate": round(hits_b / max(total, 1), 6),
                "diff": round(
                    hits_a / max(total, 1) - hits_b / max(total, 1), 6
                ),
                "better": (
                    "A"
                    if hits_a > hits_b
                    else ("B" if hits_b > hits_a else "tie")
                ),
            }
        return comparison

    @staticmethod
    def _significance_test(acc_a: List[float], acc_b: List[float]) -> Dict:
        n = len(acc_a)
        if n < 5:
            return {
                "test": "insufficient_sample",
                "n": n,
                "significant": None,
                "p_value": None,
                "message": f"样本量不足(n={n}<5)，无法进行显著性检验",
            }

        diff_arr = np.array(acc_a) - np.array(acc_b)
        mean_diff = float(np.mean(diff_arr))
        std_diff = float(np.std(diff_arr, ddof=1)) if n > 1 else 0.0

        if std_diff < 1e-10:
            return {
                "test": "paired_approximation",
                "n": n,
                "mean_diff": round(mean_diff, 6),
                "std_diff": round(std_diff, 6),
                "significant": False,
                "p_value": 1.0,
                "message": "两组完全相同，无显著差异",
            }

        t_stat = mean_diff / (std_diff / math.sqrt(n))
        p_value = 2.0 * (1.0 - _approx_normal_cdf(abs(t_stat)))

        alpha = 0.05
        significant = p_value < alpha

        if abs(t_stat) >= 2.576:
            strength = "strong"
        elif abs(t_stat) >= 1.96:
            strength = "moderate"
        elif abs(t_stat) >= 1.645:
            strength = "weak"
        else:
            strength = "none"

        return {
            "test": "paired_t_approximation",
            "n": n,
            "mean_diff": round(mean_diff, 6),
            "std_diff": round(std_diff, 6),
            "t_statistic": round(t_stat, 4),
            "p_value": round(p_value, 6),
            "alpha": alpha,
            "significant": significant,
            "effect_strength": strength,
            "interpretation": (
                f"{'有' if significant else '无'}统计学显著差异 (p={p_value:.4f}, "
                f"t={t_stat:.2f}, 强度={strength})"
            ),
        }

    @staticmethod
    def _compute_win_loss(
        preds_a: List[Dict],
        preds_b: List[Dict],
        actuals: List[Dict],
        top_n: int,
    ) -> Dict:
        POSITIONS = ["wan", "qian", "bai", "shi", "ge"]
        wins_a = 0
        wins_b = 0
        ties = 0

        for pa, pb, act in zip(preds_a, preds_b, actuals):
            score_a = 0
            score_b = 0
            for pos in POSITIONS:
                if pos not in pa or pos not in pb or pos not in act:
                    continue
                actual_val = act[pos]
                info_a = pa[pos] if isinstance(pa[pos], dict) else {}
                info_b = pb[pos] if isinstance(pb[pos], dict) else {}
                topka = info_a.get("top_k", [])
                topkb = info_b.get("top_k", [])

                rank_a = (
                    topka.index(actual_val) if actual_val in topka else 999
                )
                rank_b = (
                    topkb.index(actual_val) if actual_val in topkb else 999
                )
                score_a += top_n - min(rank_a, top_n)
                score_b += top_n - min(rank_b, top_n)

            if score_a > score_b:
                wins_a += 1
            elif score_b > score_a:
                wins_b += 1
            else:
                ties += 1

        total = wins_a + wins_b + ties
        winner = (
            "A" if wins_a > wins_b else ("B" if wins_b > wins_a else "tie")
        )

        return {
            "wins_a": wins_a,
            "wins_b": wins_b,
            "ties": ties,
            "total": total,
            "win_rate_a": round(wins_a / max(total, 1), 4),
            "win_rate_b": round(wins_b / max(total, 1), 4),
            "tie_rate": round(ties / max(total, 1), 4),
            "winner": winner,
        }

    @staticmethod
    def _generate_conclusion(
        label_a: str, label_b: str, m_a: Dict, m_b: Dict, wl: Dict, sig: Dict
    ) -> str:
        parts = []
        acc_diff = m_a["overall_accuracy"] - m_b["overall_accuracy"]

        parts.append(f"[{label_a} vs {label_b}] 对比分析:")
        parts.append(
            f"  整体准确率: {label_a}={m_a['overall_accuracy']:.4f}, {label_b}={m_b['overall_accuracy']:.4f} (差值={acc_diff:+.4f})"
        )

        winner = wl.get("winner", "tie")
        if winner == "A":
            parts.append(
                f"  逐期胜率: {label_a}胜 {wl['wins_a']}期 ({wl['win_rate_a']:.1%}), {label_b}胜 {wl['wins_b']}期 ({wl['win_rate_b']:.1%}), 平局{wl['ties']}期 → {label_a}更优"
            )
        elif winner == "B":
            parts.append(
                f"  逐期胜率: {label_a}胜 {wl['wins_a']}期 ({wl['win_rate_a']:.1%}), {label_b}胜 {wl['wins_b']}期 ({wl['win_rate_b']:.1%}), 平局{wl['ties']}期 → {label_b}更优"
            )
        else:
            parts.append(
                f"  逐期胜率: 双方势均力敌 (平局{wl['ties']}/{wl['total']}期)"
            )

        sig_msg = sig.get("interpretation", "")
        if sig_msg:
            parts.append(f"  显著性检验: {sig_msg}")

        return "\n".join(parts)

    @staticmethod
    def _make_recommendation(
        label_a: str, label_b: str, m_a: Dict, m_b: Dict, wl: Dict, sig: Dict
    ) -> Dict:
        winner = wl.get("winner", "tie")
        acc_diff = m_a["overall_accuracy"] - m_b["overall_accuracy"]
        significant = sig.get("significant", False)

        if winner == "A" and significant:
            rec = f"推荐使用 {label_a}，其在统计上显著优于 {label_b}"
            confidence = "high"
        elif winner == "B" and significant:
            rec = f"推荐使用 {label_b}，其在统计上显著优于 {label_a}"
            confidence = "high"
        elif winner == "A":
            rec = f"{label_a} 略优于 {label_b}，但差异不具有统计显著性，两者均可考虑"
            confidence = "low"
        elif winner == "B":
            rec = f"{label_b} 略优于 {label_a}，但差异不具有统计显著性，两者均可考虑"
            confidence = "low"
        else:
            rec = f"{label_a} 与 {label_b} 表现相当，建议根据具体使用场景选择或组合使用"
            confidence = "neutral"

        return {
            "recommended": winner if winner != "tie" else "either",
            "text": rec,
            "confidence": confidence,
            "accuracy_advantage": round(acc_diff, 6),
            "statistically_significant": significant,
        }

    @staticmethod
    def _safe_pct_diff(a: float, b: float) -> Optional[float]:
        if abs(b) < 1e-10:
            return None
        return round((a - b) / abs(b) * 100, 2)


# ================================================================
# 7. PL5FixTool — 错误分析与修复工具
# ================================================================


@register_tool(tags=["fix", "error_handling", "application"])
class PL5FixTool(BaseTool):
    """PL5错误分析与修复工具 (Layer 3 - APPLICATION)

    分析PL5系统中的错误信息，提供详细的错误分析和修复建议：
        - 错误类型识别和分类
        - 错误原因分析
        - 具体的修复步骤
        - 预防措施建议
        - 相关工具推荐

    Args:
        error_info: 错误信息字典，包含 code、message、details 等字段
        context: 错误发生的上下文信息（可选）
        include_prevention: 是否包含预防措施建议（默认 True）
        include_related_tools: 是否包含相关工具推荐（默认 True）
    """

    name = "pl5_fix_tool"
    description = (
        "PL5错误分析与修复：识别错误类型→分析原因→提供修复步骤和预防措施"
    )
    layer = ToolLayer.APPLICATION
    tags = ["fix", "error_handling", "application", "diagnostic"]

    input_schema = {
        "type": "object",
        "properties": {
            "error_info": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "错误代码"},
                    "message": {"type": "string", "description": "错误消息"},
                    "details": {
                        "type": "object",
                        "description": "错误详细信息",
                    },
                },
                "required": ["code", "message"],
            },
            "context": {
                "type": "object",
                "description": "错误发生的上下文信息",
            },
            "include_prevention": {
                "type": "boolean",
                "description": "是否包含预防措施建议",
                "default": True,
            },
            "include_related_tools": {
                "type": "boolean",
                "description": "是否包含相关工具推荐",
                "default": True,
            },
        },
        "required": ["error_info"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "analysis": {"type": "object", "description": "错误分析结果"},
            "fix_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "integer", "description": "步骤编号"},
                        "description": {
                            "type": "string",
                            "description": "步骤描述",
                        },
                        "action": {
                            "type": "string",
                            "description": "具体操作",
                        },
                    },
                },
            },
            "prevention": {
                "type": "array",
                "items": {"type": "string", "description": "预防措施"},
            },
            "related_tools": {
                "type": "array",
                "items": {"type": "string", "description": "相关工具名称"},
            },
            "severity": {"type": "string", "description": "错误严重程度"},
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        error_info = kwargs.get("error_info")
        context = kwargs.get("context")
        include_prevention = kwargs.get("include_prevention", True)
        include_related_tools = kwargs.get("include_related_tools", True)

        if not error_info:
            return ToolResult.error_result(
                "缺少 error_info 参数", code="MISSING_ERROR_INFO"
            )

        error_code = error_info.get("code", "UNKNOWN_ERROR")
        error_message = error_info.get("message", "未知错误")
        error_details = error_info.get("details", {})

        try:
            analysis = self._analyze_error(
                error_code, error_message, error_details, context
            )
            fix_steps = self._generate_fix_steps(analysis)
            prevention = (
                self._generate_prevention(analysis)
                if include_prevention
                else []
            )
            related_tools = (
                self._get_related_tools(analysis)
                if include_related_tools
                else []
            )

            result_data = {
                "analysis": analysis,
                "fix_steps": fix_steps,
                "prevention": prevention,
                "related_tools": related_tools,
                "severity": analysis.get("severity", "medium"),
            }

            ctx.set("last_error_analysis", analysis)
            ctx.record_metric("pl5_fix_tool.error_code", error_code)
            ctx.record_metric(
                "pl5_fix_tool.severity", analysis.get("severity", "medium")
            )

            return ToolResult.success_result(
                data=result_data, tool_name=self.name
            )

        except Exception as e:
            ctx.log.exception("[pl5_fix_tool] 执行异常")
            return ToolResult.error_result(
                f"错误分析工具执行异常: {str(e)}", code="FIX_TOOL_EXCEPTION"
            )

    def _analyze_error(
        self,
        error_code: str,
        error_message: str,
        error_details: dict,
        context: dict,
    ) -> dict:
        """分析错误类型和原因"""
        analysis = {
            "error_code": error_code,
            "error_message": error_message,
            "error_details": error_details,
            "context": context,
            "severity": "medium",
            "category": "general",
            "root_cause": "未知原因",
            "impact": "中等影响",
        }

        # 错误类型分类和分析
        if error_code.startswith("DATA_"):
            analysis["category"] = "data"
            analysis["root_cause"] = "数据相关问题"
            analysis["impact"] = "高影响"
            if "MISSING" in error_code or "EMPTY" in error_code:
                analysis["severity"] = "high"
                analysis["root_cause"] = "数据缺失或为空"
            elif "LOAD" in error_code:
                analysis["root_cause"] = "数据加载失败"
            elif "FORMAT" in error_code:
                analysis["root_cause"] = "数据格式错误"

        elif error_code.startswith("PREDICTION_"):
            analysis["category"] = "prediction"
            analysis["root_cause"] = "预测相关问题"
            analysis["impact"] = "高影响"
            analysis["severity"] = "high"

        elif error_code.startswith("MODEL_"):
            analysis["category"] = "model"
            analysis["root_cause"] = "模型相关问题"
            analysis["impact"] = "高影响"
            analysis["severity"] = "high"
            if "INTEGRITY" in error_code:
                analysis["root_cause"] = "模型完整性问题"
            elif "LOAD" in error_code:
                analysis["root_cause"] = "模型加载失败"

        elif error_code.startswith("VALIDATION_"):
            analysis["category"] = "validation"
            analysis["root_cause"] = "输入验证失败"
            analysis["impact"] = "中等影响"
            analysis["severity"] = "medium"

        elif error_code.startswith("TOOL_NOT_FOUND"):
            analysis["category"] = "tool"
            analysis["root_cause"] = "工具未找到"
            analysis["impact"] = "高影响"
            analysis["severity"] = "high"

        elif error_code == "EXECUTION_ERROR":
            analysis["category"] = "execution"
            analysis["root_cause"] = "工具执行异常"
            analysis["impact"] = "高影响"
            analysis["severity"] = "high"

        # 基于错误消息的进一步分析
        if "数据加载" in error_message:
            analysis["root_cause"] = "数据加载失败"
            analysis["category"] = "data"
        elif "预测" in error_message:
            analysis["root_cause"] = "预测执行失败"
            analysis["category"] = "prediction"
        elif "模型" in error_message:
            analysis["root_cause"] = "模型相关问题"
            analysis["category"] = "model"

        return analysis

    def _generate_fix_steps(self, analysis: dict) -> list:
        """生成修复步骤"""
        fix_steps = []
        category = analysis.get("category", "general")
        error_code = analysis.get("error_code", "UNKNOWN_ERROR")

        if category == "data":
            if "MISSING" in error_code or "EMPTY" in error_code:
                fix_steps = [
                    {
                        "step": 1,
                        "description": "检查数据源路径",
                        "action": "确认数据文件是否存在，路径是否正确",
                    },
                    {
                        "step": 2,
                        "description": "验证数据文件格式",
                        "action": "检查CSV/JSON文件格式是否正确，是否包含必要的列",
                    },
                    {
                        "step": 3,
                        "description": "查看数据内容",
                        "action": "打开数据文件，确认数据是否为空或格式错误",
                    },
                    {
                        "step": 4,
                        "description": "使用默认数据",
                        "action": "如果自定义数据有问题，尝试使用系统默认数据文件",
                    },
                ]
            elif "LOAD" in error_code:
                fix_steps = [
                    {
                        "step": 1,
                        "description": "检查文件权限",
                        "action": "确认应用程序有读取数据文件的权限",
                    },
                    {
                        "step": 2,
                        "description": "验证文件格式",
                        "action": "使用文本编辑器打开文件，确认格式正确",
                    },
                    {
                        "step": 3,
                        "description": "尝试其他数据源",
                        "action": "使用不同的数据源或文件格式",
                    },
                ]

        elif category == "prediction":
            fix_steps = [
                {
                    "step": 1,
                    "description": "检查特征向量",
                    "action": "确认输入特征向量的长度和格式正确",
                },
                {
                    "step": 2,
                    "description": "验证模型状态",
                    "action": "使用 model_analyzer 工具检查模型健康状态",
                },
                {
                    "step": 3,
                    "description": "检查数据质量",
                    "action": "确保输入数据干净，没有异常值",
                },
                {
                    "step": 4,
                    "description": "调整参数",
                    "action": "尝试调整预测参数，如 top_k 值",
                },
            ]

        elif category == "model":
            fix_steps = [
                {
                    "step": 1,
                    "description": "检查模型文件",
                    "action": "确认模型文件是否存在且完整",
                },
                {
                    "step": 2,
                    "description": "验证模型版本",
                    "action": "确保使用的是兼容的模型版本",
                },
                {
                    "step": 3,
                    "description": "重新加载模型",
                    "action": "使用 model_analyzer 工具重新加载模型",
                },
                {
                    "step": 4,
                    "description": "检查依赖项",
                    "action": "确认所有必要的依赖项都已安装",
                },
            ]

        elif category == "validation":
            fix_steps = [
                {
                    "step": 1,
                    "description": "检查输入参数",
                    "action": "确认所有必填参数都已提供且格式正确",
                },
                {
                    "step": 2,
                    "description": "验证参数类型",
                    "action": "确保参数类型符合工具要求",
                },
                {
                    "step": 3,
                    "description": "查看工具文档",
                    "action": "参考工具的 input_schema 了解正确的参数格式",
                },
            ]

        elif category == "tool":
            fix_steps = [
                {
                    "step": 1,
                    "description": "检查工具注册",
                    "action": "确认所需工具已正确注册到 ToolRegistry",
                },
                {
                    "step": 2,
                    "description": "验证工具依赖",
                    "action": "确保工具的所有依赖项都已满足",
                },
                {
                    "step": 3,
                    "description": "检查工具版本",
                    "action": "确保使用的是兼容的工具版本",
                },
            ]

        else:
            # 通用修复步骤
            fix_steps = [
                {
                    "step": 1,
                    "description": "查看错误详情",
                    "action": "仔细阅读错误消息和详细信息",
                },
                {
                    "step": 2,
                    "description": "检查日志",
                    "action": "查看系统日志以获取更多上下文信息",
                },
                {
                    "step": 3,
                    "description": "验证输入",
                    "action": "确认所有输入参数都正确无误",
                },
                {
                    "step": 4,
                    "description": "重启服务",
                    "action": "尝试重启应用程序或服务",
                },
                {
                    "step": 5,
                    "description": "寻求帮助",
                    "action": "如果问题持续存在，联系技术支持",
                },
            ]

        return fix_steps

    def _generate_prevention(self, analysis: dict) -> list:
        """生成预防措施建议"""
        prevention = []
        category = analysis.get("category", "general")

        if category == "data":
            prevention = [
                "定期检查数据源的可用性和完整性",
                "建立数据备份机制，确保数据安全",
                "使用数据验证工具定期检查数据质量",
                "设置数据监控告警，及时发现数据异常",
                "保持数据格式的一致性和标准化",
            ]

        elif category == "prediction":
            prevention = [
                "定期评估模型性能，及时发现性能下降",
                "建立预测结果的监控机制",
                "使用历史数据进行定期回测，验证预测准确性",
                "保持特征工程流程的稳定性",
                "建立模型更新和维护的定期计划",
            ]

        elif category == "model":
            prevention = [
                "定期备份模型文件",
                "建立模型版本控制机制",
                "定期运行模型健康检查",
                "监控模型依赖项的更新情况",
                "建立模型部署和回滚的标准流程",
            ]

        elif category == "validation":
            prevention = [
                "在调用工具前进行输入参数验证",
                "建立参数验证的标准流程",
                "使用统一的参数格式和命名规范",
                "为工具调用添加错误处理机制",
                "定期检查工具的输入输出格式是否有变化",
            ]

        elif category == "tool":
            prevention = [
                "建立工具依赖关系的文档",
                "定期检查工具注册状态",
                "确保工具版本的兼容性",
                "建立工具更新和测试的标准流程",
                "监控工具的使用情况和性能",
            ]

        else:
            prevention = [
                "建立全面的错误监控和告警机制",
                "定期进行系统健康检查",
                "保持系统组件的更新和维护",
                "建立标准化的错误处理流程",
                "定期备份系统配置和数据",
            ]

        return prevention

    def _get_related_tools(self, analysis: dict) -> list:
        """获取相关工具推荐"""
        related_tools = []
        category = analysis.get("category", "general")

        if category == "data":
            related_tools = [
                "data_loader",
                "validation_tool",
                "feature_engineer",
            ]

        elif category == "prediction":
            related_tools = [
                "predictor",
                "model_analyzer",
                "optimization_advisor",
            ]

        elif category == "model":
            related_tools = [
                "model_analyzer",
                "weight_analyzer",
                "optimization_advisor",
            ]

        elif category == "validation":
            related_tools = ["validation_tool", "config_tool"]

        elif category == "tool":
            related_tools = ["config_tool", "logger_tool"]

        else:
            related_tools = ["logger_tool", "config_tool", "model_analyzer"]

        return related_tools


# ================================================================
# 5. AlertTool — 异常检测与告警
# ================================================================


@register_tool(tags=["alert", "application", "monitoring"])
class AlertTool(BaseTool):
    """异常检测与告警工具 (Layer 3 - APPLICATION)

    监控当前系统/模型的各项指标，检测异常情况并生成告警。

    检测维度：
        1. **准确率骤降**: 当前准确率低于历史均值超过阈值比例
        2. **模型异常**: 模型完整性校验失败、组件缺失
        3. **数据漂移**: 特征分布偏移检测（基于简单统计量）
        4. **系统资源异常**: 可扩展的通用资源监控接口

    输出：
        - 告警状态: normal / warning / urgent
        - 触发条件详情列表
        - 建议操作步骤
        - 历史告警趋势（基于上下文累积）

    Args:
        current_metrics: 当前性能指标字典，支持:
            - accuracy: 当前准确率 (0~1)
            - hit_rate: 当前命中率 (0~1)
            - uncertainty: 平均不确定性 (0~1)
            - model_status: 模型状态字符串
            - feature_drift_score: 特征漂移分数 (0~1, 越高越严重)
            - custom: 自定义指标子字典
        thresholds: 自定义阈值字典（可选，覆盖默认阈值）
        history_window: 历史滑动窗口大小（用于趋势判断），默认 20
    """

    name = "alert"
    description = "异常检测与告警：准确率骤降/模型异常/数据漂移/资源异常→状态+触发条件+建议操作"
    layer = ToolLayer.APPLICATION
    tags = ["alert", "application", "monitoring", "anomaly_detection"]

    input_schema = {
        "type": "object",
        "properties": {
            "current_metrics": {
                "type": "object",
                "description": "当前性能指标字典 {accuracy, hit_rate, uncertainty, ...}",
            },
            "thresholds": {
                "type": "object",
                "description": "自定义阈值字典（覆盖默认值）",
            },
            "history_window": {
                "type": "integer",
                "description": "历史滑动窗口大小",
                "default": 20,
            },
        },
        "required": ["current_metrics"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["normal", "warning", "urgent"],
            },
            "alerts": {"type": "array", "description": "告警条目列表"},
            "summary": {"type": "object", "description": "告警摘要"},
            "actions": {"type": "array", "description": "建议操作列表"},
        },
    }

    _DEFAULT_THRESHOLDS = {
        "accuracy_drop_ratio": 0.3,
        "accuracy_absolute_min": 0.1,
        "uncertainty_max": 0.7,
        "drift_threshold": 0.5,
        "consecutive_failures_max": 3,
        "warning_score_min": 1,
        "urgent_score_min": 3,
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        current_metrics = kwargs.get("current_metrics")
        thresholds = kwargs.get("thresholds") or {}
        history_window = kwargs.get("history_window", 20)

        if not current_metrics or not isinstance(current_metrics, dict):
            return ToolResult.error_result(
                "current_metrics 必须是非空字典", code="INVALID_METRICS"
            )

        effective_thresholds = {**self._DEFAULT_THRESHOLDS, **thresholds}

        triggered_alerts = []
        alert_scores = {"accuracy": 0, "model": 0, "drift": 0, "custom": 0}

        accuracy_alerts = self._check_accuracy_drop(
            current_metrics, effective_thresholds, ctx
        )
        triggered_alerts.extend(accuracy_alerts)
        alert_scores["accuracy"] = sum(
            1
            for a in accuracy_alerts
            if a.get("severity") in ("warning", "urgent")
        )

        model_alerts = self._check_model_health(
            current_metrics, effective_thresholds
        )
        triggered_alerts.extend(model_alerts)
        alert_scores["model"] = sum(
            1
            for a in model_alerts
            if a.get("severity") in ("warning", "urgent")
        )

        drift_alerts = self._check_data_drift(
            current_metrics, effective_thresholds
        )
        triggered_alerts.extend(drift_alerts)
        alert_scores["drift"] = sum(
            1
            for a in drift_alerts
            if a.get("severity") in ("warning", "urgent")
        )

        custom_alerts = self._check_custom_metrics(
            current_metrics, effective_thresholds
        )
        triggered_alerts.extend(custom_alerts)
        alert_scores["custom"] = sum(
            1
            for a in custom_alerts
            if a.get("severity") in ("warning", "urgent")
        )

        total_score = sum(alert_scores.values())
        urgent_min = effective_thresholds.get("urgent_score_min", 3)
        warning_min = effective_thresholds.get("warning_score_min", 1)

        urgent_count = sum(
            1 for a in triggered_alerts if a.get("severity") == "urgent"
        )
        warning_count = sum(
            1 for a in triggered_alerts if a.get("severity") == "warning"
        )

        if urgent_count >= 1 or total_score >= urgent_min:
            status = "urgent"
        elif warning_count >= 1 or total_score >= warning_min:
            status = "warning"
        else:
            status = "normal"

        actions = self._generate_actions(
            triggered_alerts, status, effective_thresholds
        )

        alert_history = ctx.get("alert_history") or []
        alert_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "score": total_score,
                "alert_count": len(triggered_alerts),
            }
        )
        if len(alert_history) > history_window:
            alert_history = alert_history[-history_window:]
        ctx.set("alert_history", alert_history)

        result = {
            "status": status,
            "alerts": triggered_alerts,
            "score": {
                "total": total_score,
                "breakdown": alert_scores,
                "urgent_count": urgent_count,
                "warning_count": warning_count,
                "info_count": len(triggered_alerts)
                - urgent_count
                - warning_count,
            },
            "thresholds_used": effective_thresholds,
            "actions": actions,
            "summary": {
                "status": status,
                "total_alerts": len(triggered_alerts),
                "urgent_alerts": urgent_count,
                "warning_alerts": warning_count,
                "trend": self._summarize_trend(alert_history),
            },
            "checked_at": datetime.now().isoformat(),
        }

        ctx.set("last_alert_result", result)
        ctx.record_metric("alert.status", status)
        ctx.record_metric("alert.total_score", total_score)
        ctx.record_metric("alert.alert_count", len(triggered_alerts))

        return ToolResult.success_result(data=result, tool_name=self.name)

    @staticmethod
    def _check_accuracy_drop(
        metrics: Dict, thresh: Dict, ctx: ToolContext
    ) -> List[Dict]:
        alerts = []
        accuracy = metrics.get("accuracy")
        historical_accuracies = ctx.get("historical_accuracies") or []

        if accuracy is not None:
            if len(historical_accuracies) >= 5:
                hist_mean = float(np.mean(historical_accuracies[-20:]))
                drop_ratio = (hist_mean - accuracy) / max(hist_mean, 1e-10)
                if drop_ratio > thresh["accuracy_drop_ratio"]:
                    alerts.append(
                        {
                            "detector": "accuracy_drop",
                            "severity": (
                                "urgent" if drop_ratio > 0.5 else "warning"
                            ),
                            "metric": "accuracy",
                            "current": round(accuracy, 6),
                            "historical_mean": round(hist_mean, 6),
                            "drop_ratio": round(drop_ratio, 4),
                            "message": f"准确率骤降: 当前 {accuracy:.4f}, 历史均值 {hist_mean:.4f}, 降幅 {drop_ratio:.1%}",
                        }
                    )

            if accuracy < thresh["accuracy_absolute_min"]:
                alerts.append(
                    {
                        "detector": "accuracy_too_low",
                        "severity": "urgent",
                        "metric": "accuracy",
                        "current": round(accuracy, 6),
                        "threshold": thresh["accuracy_absolute_min"],
                        "message": f"准确率过低: {accuracy:.4f} < {thresh['accuracy_absolute_min']}",
                    }
                )

        uncertainty = metrics.get("uncertainty")
        if uncertainty is not None and uncertainty > thresh["uncertainty_max"]:
            alerts.append(
                {
                    "detector": "high_uncertainty",
                    "severity": "warning" if uncertainty < 0.85 else "urgent",
                    "metric": "uncertainty",
                    "current": round(uncertainty, 4),
                    "threshold": thresh["uncertainty_max"],
                    "message": f"不确定性偏高: {uncertainty:.4f} > {thresh['uncertainty_max']}",
                }
            )

        return alerts

    @staticmethod
    def _check_model_health(metrics: Dict, thresh: Dict) -> List[Dict]:
        alerts = []
        model_status = metrics.get("model_status")

        if model_status is not None:
            error_statuses = [
                "error",
                "failed",
                "corrupted",
                "not_loaded",
                "integrity_failed",
            ]
            warn_statuses = ["degraded", "partial", "stale", "warning"]

            if any(s in str(model_status).lower() for s in error_statuses):
                alerts.append(
                    {
                        "detector": "model_error",
                        "severity": "urgent",
                        "metric": "model_status",
                        "value": str(model_status),
                        "message": f"模型状态异常: {model_status}",
                    }
                )
            elif any(s in str(model_status).lower() for s in warn_statuses):
                alerts.append(
                    {
                        "detector": "model_warning",
                        "severity": "warning",
                        "metric": "model_status",
                        "value": str(model_status),
                        "message": f"模型状态需关注: {model_status}",
                    }
                )

        consecutive_failures = metrics.get("consecutive_failures", 0)
        if consecutive_failures > thresh["consecutive_failures_max"]:
            alerts.append(
                {
                    "detector": "consecutive_failures",
                    "severity": (
                        "urgent" if consecutive_failures > 5 else "warning"
                    ),
                    "metric": "consecutive_failures",
                    "value": consecutive_failures,
                    "threshold": thresh["consecutive_failures_max"],
                    "message": f"连续失败次数过多: {consecutive_failures} 次 (阈值: {thresh['consecutive_failures_max']})",
                }
            )

        return alerts

    @staticmethod
    def _check_data_drift(metrics: Dict, thresh: Dict) -> List[Dict]:
        alerts = []
        drift_score = metrics.get("feature_drift_score")
        hit_rate = metrics.get("hit_rate")

        if drift_score is not None and drift_score > thresh["drift_threshold"]:
            alerts.append(
                {
                    "detector": "feature_drift",
                    "severity": "warning" if drift_score < 0.75 else "urgent",
                    "metric": "feature_drift_score",
                    "current": round(drift_score, 4),
                    "threshold": thresh["drift_threshold"],
                    "message": f"特征分布漂移检测到: drift_score={drift_score:.4f} (阈值: {thresh['drift_threshold']})",
                }
            )

        if hit_rate is not None:
            hist_hits = metrics.get("historical_hit_rates") or []
            if len(hist_hits) >= 5:
                hist_mean_hit = float(np.mean(hist_hits[-20:]))
                if hist_mean_hit > 0.1 and hit_rate < hist_mean_hit * 0.5:
                    alerts.append(
                        {
                            "detector": "hit_rate_anomaly",
                            "severity": "warning",
                            "metric": "hit_rate",
                            "current": round(hit_rate, 4),
                            "historical_mean": round(hist_mean_hit, 4),
                            "message": f"命中率异常下降: 当前 {hit_rate:.4f}, 历史 {hist_mean_hit:.4f}",
                        }
                    )

        return alerts

    @staticmethod
    def _check_custom_metrics(metrics: Dict, thresh: Dict) -> List[Dict]:
        alerts = []
        custom = metrics.get("custom")
        if not isinstance(custom, dict):
            return alerts

        for key, value in custom.items():
            if isinstance(value, (int, float)):
                custom_thresh_key = f"custom_{key}_max"
                custom_thresh = thresh.get(custom_thresh_key)
                if custom_thresh is not None and value > custom_thresh:
                    alerts.append(
                        {
                            "detector": "custom_threshold",
                            "severity": "warning",
                            "metric": f"custom.{key}",
                            "current": value,
                            "threshold": custom_thresh,
                            "message": f"自定义指标 '{key}' 超阈: {value} > {custom_thresh}",
                        }
                    )

        return alerts

    @staticmethod
    def _generate_actions(
        alerts: List[Dict], status: str, thresh: Dict
    ) -> List[Dict]:
        actions = []
        detectors_seen = set()

        for alert in alerts:
            det = alert.get("detector", "")
            if det in detectors_seen:
                continue
            detectors_seen.add(det)

            action_map = {
                "accuracy_drop": {
                    "priority": (
                        "high"
                        if alert.get("severity") == "urgent"
                        else "medium"
                    ),
                    "action": "检查近期数据质量，确认是否输入数据存在异常；考虑增加训练样本或触发重训练",
                    "related_detector": det,
                },
                "accuracy_too_low": {
                    "priority": "urgent",
                    "action": "立即暂停自动化预测，人工介入排查；检查模型文件完整性及特征工程质量",
                    "related_detector": det,
                },
                "high_uncertainty": {
                    "priority": "medium",
                    "action": "查看权重分析报告，确认是否存在模型冲突；建议增加 ensemble 多样性",
                    "related_detector": det,
                },
                "model_error": {
                    "priority": "urgent",
                    "action": "运行 ModelAnalyzerTool 诊断模型状态；必要时重新加载或重训模型",
                    "related_detector": det,
                },
                "model_warning": {
                    "priority": "medium",
                    "action": "安排计划性维护窗口，检查模型组件健康度",
                    "related_detector": det,
                },
                "consecutive_failures": {
                    "priority": "high",
                    "action": "检查上游数据管道和服务可用性；启用备用方案或降级服务",
                    "related_detector": det,
                },
                "feature_drift": {
                    "priority": "medium",
                    "action": "收集最新数据更新特征分布；考虑增量训练或在线学习适配新分布",
                    "related_detector": det,
                },
                "hit_rate_anomaly": {
                    "priority": "medium",
                    "action": "分析近期开奖规律变化；检查是否有外部因素影响数据分布",
                    "related_detector": det,
                },
            }

            if det in action_map:
                actions.append(action_map[det])

        if status == "normal":
            actions.append(
                {
                    "priority": "info",
                    "action": "系统运行正常，无需额外操作。继续保持常规监控。",
                    "related_detector": "system_healthy",
                }
            )

        return actions

    @staticmethod
    def _summarize_trend(history: List[Dict]) -> Dict:
        if len(history) < 3:
            return {
                "status": "insufficient_data",
                "message": f"历史记录不足({len(history)}条)",
            }

        recent = history[-10:]
        statuses = [h.get("status", "normal") for h in recent]
        scores = [h.get("score", 0) for h in recent]

        urgent_ratio = statuses.count("urgent") / len(statuses)
        warning_ratio = statuses.count("warning") / len(statuses)
        avg_score = float(np.mean(scores))

        if urgent_ratio >= 0.5:
            trend = "deteriorating"
            desc = "近期频繁出现紧急告警，系统状况持续恶化"
        elif warning_ratio >= 0.6:
            trend = "unstable"
            desc = "警告频率较高，系统稳定性值得关注"
        elif urgent_ratio == 0 and warning_ratio <= 0.2:
            trend = "stable"
            desc = "系统运行稳定，告警频率低"
        else:
            trend = "fluctuating"
            desc = "告警情况有波动，建议持续观察"

        return {
            "trend": trend,
            "description": desc,
            "recent_urgent_ratio": round(urgent_ratio, 3),
            "recent_warning_ratio": round(warning_ratio, 3),
            "avg_score": round(avg_score, 2),
            "window_size": len(recent),
        }


# ================================================================
# 6. ExportTool — 多格式结果导出
# ================================================================


@register_tool(tags=["export", "application", "io"])
class ExportTool(BaseTool):
    """多格式结果导出工具 (Layer 3 - APPLICATION)

    将任意数据导出为多种标准格式，支持写入文件或返回内容字符串。

    支持的格式：
        - json:   JSON 格式（支持中文，缩进美化）
        - csv:    CSV 格式（适合表格数据）
        - excel:  Excel .xlsx 格式（需要 openpyxl）
        - markdown: Markdown 表格/文档格式
        - html:   HTML 表格/文档格式

    Args:
        data: 要导出的任意数据（dict/list/DataFrame/字符串等）
        format: 目标格式 (json/csv/excel/markdown/html)，默认 "json"
        output_path: 输出文件路径（str 或 Path），可选；
                     如果提供则写入文件并返回路径，
                     如果不提供则返回内容字符串
        options: 导出选项字典，格式相关:
            - indent: JSON 缩进（默认 2）
            - encoding: 文件编码（默认 utf-8）
            - sheet_name: Excel 工作表名（默认 Sheet1）
            - title: Markdown/HTML 标题
            - flatten: 是否展平嵌套结构（仅 CSV/Excel，默认 True）
    """

    name = "export"
    description = "多格式结果导出：支持 json/csv/excel/markdown/html，可写文件或返回字符串"
    layer = ToolLayer.APPLICATION
    tags = ["export", "application", "io", "serialization"]

    _SUPPORTED_FORMATS = {"json", "csv", "excel", "markdown", "html"}

    input_schema = {
        "type": "object",
        "properties": {
            "data": {
                "description": "要导出的数据（任意类型）",
            },
            "format": {
                "type": "string",
                "enum": ["json", "csv", "excel", "markdown", "html"],
                "description": "目标导出格式",
                "default": "json",
            },
            "output_path": {
                "type": ["string"],
                "description": "输出文件路径（可选，不提供则返回字符串）",
            },
            "options": {
                "type": "object",
                "description": "导出选项 {indent, encoding, sheet_name, title, flatten}",
            },
        },
        "required": ["data"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"description": "导出结果（文件路径或内容字符串)"},
            "format": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "path": {
                "type": "string",
                "description": "实际写入路径（如果写了文件）",
            },
        },
    }

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        data = kwargs.get("data")
        fmt = kwargs.get("format", "json").lower().strip()
        output_path = kwargs.get("output_path")
        options = kwargs.get("options") or {}

        if data is None:
            return ToolResult.error_result(
                "data 参数不能为 None", code="EXPORT_NO_DATA"
            )

        if fmt not in self._SUPPORTED_FORMATS:
            return ToolResult.error_result(
                f"不支持的导出格式: '{fmt}'，支持: {self._SUPPORTED_FORMATS}",
                code="UNSUPPORTED_FORMAT",
            )

        try:
            content = self._serialize(data, fmt, options)

            if output_path:
                path = Path(output_path)
                encoding = options.get("encoding", "utf-8")
                path.parent.mkdir(parents=True, exist_ok=True)

                if fmt == "excel":
                    self._write_excel(content, path, options)
                    written_path = str(path.resolve())
                    size = path.stat().st_size if path.exists() else 0
                else:
                    if isinstance(content, bytes):
                        mode = "wb"
                    else:
                        mode = "w"
                    with open(
                        path, mode, encoding=encoding if mode == "w" else None
                    ) as f:
                        f.write(content)
                    written_path = str(path.resolve())
                    size = (
                        path.stat().st_size
                        if path.exists()
                        else len(content.encode(encoding))
                    )

                ctx.log.info(
                    f"[export] 已导出到 {written_path} ({size} bytes, format={fmt})"
                )

                result_data = {
                    "output": written_path,
                    "format": fmt,
                    "size_bytes": size,
                    "path": written_path,
                    "mode": "file",
                }
            else:
                size = (
                    len(content.encode(options.get("encoding", "utf-8")))
                    if isinstance(content, str)
                    else len(content)
                )
                result_data = {
                    "output": content,
                    "format": fmt,
                    "size_bytes": size,
                    "path": None,
                    "mode": "string",
                }

            ctx.record_metric(f"export.format_{fmt}", 1)
            ctx.record_metric("export.size_bytes", size)
            ctx.record_metric("export.mode", result_data["mode"])

            return ToolResult.success_result(
                data=result_data,
                tool_name=self.name,
            )

        except Exception as e:
            ctx.log.exception(f"[export] 导出异常 (format={fmt})")
            return ToolResult.error_result(
                f"导出失败(format={fmt}): {str(e)}", code="EXPORT_ERROR"
            )

    def _serialize(self, data: Any, fmt: str, options: Dict) -> Any:
        serializers = {
            "json": lambda d, o: self._to_json(d, o),
            "csv": lambda d, o: self._to_csv(d, o),
            "excel": lambda d, o: self._to_excel_data(d, o),
            "markdown": lambda d, o: self._to_markdown(d, o),
            "html": lambda d, o: self._to_html(d, o),
        }
        serializer = serializers.get(fmt)
        if serializer is None:
            raise ValueError(f"无序列化器: {fmt}")
        return serializer(data, options)

    @staticmethod
    def _to_json(data: Any, options: Dict) -> str:
        indent = options.get("indent", 2)
        ensure_ascii = options.get("ensure_ascii", False)
        serializable = ToolResult._serialize_data(data)
        return json.dumps(
            serializable, indent=indent, ensure_ascii=ensure_ascii, default=str
        )

    @staticmethod
    def _to_csv(data: Any, options: Dict) -> str:
        flatten = options.get("flatten", True)
        df = ExportTool._convert_to_dataframe(data, flatten)
        output = io.StringIO()
        df.to_csv(output, index=False, encoding="utf-8")
        return output.getvalue()

    @staticmethod
    def _to_excel_data(data: Any, options: Dict) -> pd.DataFrame:
        flatten = options.get("flatten", True)
        return ExportTool._convert_to_dataframe(data, flatten)

    @staticmethod
    def _write_excel(df: pd.DataFrame, path: Path, options: Dict):
        try:
            pass
        except ImportError:
            raise ImportError(
                "Excel 导出需要 openpyxl 库，请执行: pip install openpyxl"
            )

        sheet_name = options.get("sheet_name", "Sheet1")
        df.to_excel(
            path, index=False, sheet_name=sheet_name, engine="openpyxl"
        )

    @staticmethod
    def _to_markdown(data: Any, options: Dict) -> str:
        title = options.get("title", "")
        flatten = options.get("flatten", True)
        lines = []
        if title:
            lines.append(f"# {title}")
            lines.append("")

        df = ExportTool._convert_to_dataframe(data, flatten)
        if df.empty:
            lines.append("*（无数据）*")
            return "\n".join(lines)

        lines.append(
            df.to_markdown(
                index=False, tablefmt="pipe", numalign="right", stralign="left"
            )
        )
        return "\n".join(lines)

    @staticmethod
    def _to_html(data: Any, options: Dict) -> str:
        title = options.get("title", "")
        flatten = options.get("flatten", True)
        html_parts = []
        html_parts.append("<!DOCTYPE html>")
        html_parts.append('<html lang="zh-CN"><head><meta charset="utf-8">')
        if title:
            html_parts.append(f"<title>{title}</title>")
        html_parts.append("""
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background-color: #f5f5f5; font-weight: 600; }
tr:nth-child(even) { background-color: #fafafa; }
</style>
</head><body>
""")
        if title:
            html_parts.append(f"<h1>{title}</h1>")

        df = ExportTool._convert_to_dataframe(data, flatten)
        if df.empty:
            html_parts.append("<p>（无数据）</p>")
        else:
            html_parts.append(
                df.to_html(index=False, escape=False, table_id="data_table")
            )
        html_parts.append("</body></html>")

        return "\n".join(html_parts)

    @staticmethod
    def _convert_to_dataframe(data: Any, flatten: bool = True) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data.copy()
        if isinstance(data, pd.Series):
            return data.to_frame().reset_index()

        if isinstance(data, dict):
            flat_records = (
                ExportTool._flatten_dict(data) if flatten else [data]
            )
            if flat_records and isinstance(flat_records[0], dict):
                return pd.DataFrame(flat_records)
            return pd.DataFrame([data])

        if isinstance(data, (list, tuple)):
            if not data:
                return pd.DataFrame()
            first_item = data[0]
            if isinstance(first_item, dict):
                records = []
                for item in data:
                    if isinstance(item, dict):
                        records.append(
                            ExportTool._flatten_dict(item) if flatten else item
                        )
                    else:
                        records.append({"value": item})
                return pd.DataFrame(records)
            return pd.DataFrame({"value": data})

        return pd.DataFrame({"value": [data]})

    @staticmethod
    def _flatten_dict(d: Dict, parent_key: str = "", sep: str = ".") -> Dict:
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict) and v:
                items.extend(ExportTool._flatten_dict(v, new_key, sep).items())
            elif (
                isinstance(v, (list, tuple))
                and v
                and isinstance(v[0], (dict,))
            ):
                for i, item in enumerate(v):
                    if isinstance(item, dict):
                        items.extend(
                            ExportTool._flatten_dict(
                                item, f"{new_key}[{i}]", sep
                            ).items()
                        )
                    else:
                        items.append((f"{new_key}[{i}]", item))
            else:
                items.append((new_key, v))
        return dict(items)
