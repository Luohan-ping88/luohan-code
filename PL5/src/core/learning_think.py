"""三层思考模块 ThinkModule (Task 3).

对自学习与反馈分析结果进行三层思考：
1. 规则层：依据告警级别映射出候选动作；
2. 统计层：接入反馈分析，低准确率时追加诊断推理；
3. LLM 层：低准确率情况下借助大模型生成增强推理文本（异常静默降级）。
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.self_learning import SelfLearningSystem
from src.core.learning_decision import ActionType, RankedAction

logger = logging.getLogger(__name__)

# 告警级别 -> 候选动作类型映射
_ALERT_TO_ACTION = {
    "urgent": [ActionType.RETRAIN, ActionType.FIX_DATA],
    "warning": [ActionType.RETRAIN],
}

# 动作默认置信度
_ACTION_CONFIDENCE = {
    ActionType.RETRAIN: 0.9,
    ActionType.FIX_DATA: 0.7,
}


@dataclass
class ThinkContext:
    """三层思考的输出上下文。"""

    candidates: List[RankedAction] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


class ThinkModule:
    """三层思考模块。

    Attributes:
        self_learning: 自学习系统实例（默认 SelfLearningSystem()）。
        feedback_analyzer: 反馈分析器，可选。
        llm: 可调用对象（str -> str）或 None，用于 LLM 层增强。
    """

    def __init__(
        self,
        self_learning=None,
        feedback_analyzer=None,
        llm: Optional[callable] = None,
    ) -> None:
        self.self_learning = self_learning if self_learning is not None else SelfLearningSystem()
        self.feedback_analyzer = feedback_analyzer
        self.llm = llm

    def _think_metrics(self):
        """收集自学习指标，返回 (perf, comp)；comp 异常时兜底。"""
        perf = self.self_learning.evaluate_recent_performance()
        try:
            comp = self.self_learning.compute_comprehensive_score()
        except Exception as exc:  # noqa: BLE001 comp 失败兜底，不阻塞思考
            logger.warning("[ThinkModule] compute_comprehensive_score 失败，使用兜底: %s", exc)
            comp = {"comprehensive_score": 0.0, "metrics_available": []}
        return perf, comp

    def _think_parameter_suggestions(self) -> List[RankedAction]:
        """学以致用：把参数类结构化建议转成 UPDATE_PARAM 候选动作。

        从 SelfLearningSystem 的 pending 建议中筛选带 parameter 的记录，
        使用其持久化的稳定 id（内容级去重会复用旧 id），供 ActModule 应用。
        """
        actions: List[RankedAction] = []
        try:
            self.self_learning.generate_structured_suggestions()
        except Exception as exc:  # noqa: BLE001 建议生成失败不阻塞思考
            logger.warning("[ThinkModule] generate_structured_suggestions 失败: %s", exc)
            return actions

        history = getattr(self.self_learning, "suggestion_history", []) or []
        for rec in reversed(history):
            if not isinstance(rec, dict):
                continue
            if rec.get("status") != "pending":
                continue
            param = rec.get("parameter")
            if not isinstance(param, dict) or not param.get("name"):
                continue
            expected = rec.get("effect_estimation") or {}
            improvement_range = expected.get("improvement_range") or [0.0, 0.0, 0.0]
            mid = improvement_range[1] if len(improvement_range) > 1 else 0.0
            actions.append(RankedAction(
                action_type=ActionType.UPDATE_PARAM.value,
                priority=int(rec.get("priority", 1)),
                confidence=float(rec.get("confidence_level", 0.0)),
                estimated_improvement_mid=float(mid),
                name=rec.get("category", param.get("name", "update_param")),
                param_name=param.get("name"),
                recommended_value=param.get("recommended_value"),
                suggestion_id=rec.get("id"),
                reasoning=rec.get("reasoning", ""),
            ))
        return actions

    def think(self) -> ThinkContext:
        """执行三层思考，返回 ThinkContext。"""
        ctx = ThinkContext()
        perf, comp = self._think_metrics()

        # 第 1 层：规则层，依据告警级别生成候选动作
        try:
            alert = self.self_learning.check_performance_alert()
        except Exception as exc:  # noqa: BLE001 告警失败留空，不阻塞思考
            logger.warning("[ThinkModule] check_performance_alert 失败: %s", exc)
            alert = {"alert_level": "normal", "reasons": []}

        ctx.raw["alert"] = alert
        alert_level = alert.get("alert_level", "normal")
        action_types = _ALERT_TO_ACTION.get(alert_level, [])
        for index, action_type in enumerate(action_types, start=1):
            ctx.candidates.append(RankedAction(
                action_type=action_type.value,
                priority=index,
                confidence=_ACTION_CONFIDENCE[action_type],
                estimated_improvement_mid=0.0,
                name=action_type.value,
                reasoning=f"ALERT={alert_level}: {'; '.join(alert.get('reasons', []))}",
            ))
        if action_types:
            ctx.reasoning.append(
                f"规则层: 告警级别 '{alert_level}' 触发动作 {[a.value for a in action_types]}"
            )

        # 第 1.5 层：参数建议（学以致用），命中参数知识库规则则产出 UPDATE_PARAM 候选
        try:
            param_actions = self._think_parameter_suggestions()
        except Exception as exc:  # noqa: BLE001 参数建议失败不阻塞思考
            logger.warning("[ThinkModule] 参数建议生成失败: %s", exc)
            param_actions = []
        ctx.candidates.extend(param_actions)
        if param_actions:
            ctx.reasoning.append(f"参数层: 生成 {len(param_actions)} 个参数调整候选（学以致用）")

        # 第 2 层：统计层，接入反馈分析
        if self.feedback_analyzer is not None:
            try:
                analysis = self.feedback_analyzer.analyze_strategy_performance(window_size=20)
            except Exception as exc:  # noqa: BLE001 反馈分析失败不阻塞思考
                logger.warning("[ThinkModule] analyze_strategy_performance 失败: %s", exc)
                analysis = {}
            ctx.raw["feedback_analysis"] = analysis
            overall = analysis.get("overall_analysis", {}) if isinstance(analysis, dict) else {}
            top3_accuracy = overall.get("top3_accuracy")
            if top3_accuracy is not None and top3_accuracy < 0.15:
                ctx.reasoning.append(
                    f"统计层: 反馈显示 Top-3 准确率偏低 ({top3_accuracy:.4f})，需排查策略漂移与数据质量问题"
                )

        # 第 3 层：LLM 增强（异常静默降级）
        accuracy = perf.get("accuracy", 0.0) if isinstance(perf, dict) else 0.0
        if accuracy < 0.15 and self.llm is not None:
            reasoning_prompt = (
                f"三层思考: 准确率 {accuracy*100:.1f}%，告警级别 {alert_level}，"
                f"请给出可执行的诊断与改进建议。"
            )
            try:
                llm_output = self.llm(reasoning_prompt)
                if llm_output:
                    ctx.reasoning.append(f"LLM增强: {llm_output}")
            except Exception as exc:  # noqa: BLE001 LLM 异常静默降级
                logger.warning("[ThinkModule] LLM 增强失败，静默降级: %s", exc)

        return ctx