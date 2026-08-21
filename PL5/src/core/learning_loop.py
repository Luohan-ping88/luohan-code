"""四阶段闭环编排器 LearningLoopEngine (Task 5)。

将自学习、思考、决策、执行串成完整的四阶段闭环：
1. 自校正 (_self_correct)：从记忆库 effects 计算平均效果增益写入 meta。
2. 思考 (think)：基于自学习与反馈生成候选动作。
3. 决策 (decision)：过滤、排序候选动作。
4. 执行 (act)：逐个执行动作并记录到记忆库。

记忆库写入失败由 ClosedLoopMemoryStore.save 降级处理，绝不中断闭环。
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.core.closed_loop_memory import ClosedLoopMemoryStore
from src.core.self_learning import SelfLearningSystem
from src.core.learning_think import ThinkModule
from src.core.learning_decision import DecisionModule
from src.core.learning_act import ActModule

logger = logging.getLogger(__name__)

# 默认记忆文件
_DEFAULT_MEMORY_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "closed_loop_memory.json"


class LearningLoopEngine:
    """四阶段闭环编排器。

    Attributes:
        memory: 统一持久化记忆库。
        think: 三层思考模块。
        decision: 统一动作判定模块。
        act: 执行模块。
    """

    def __init__(
        self,
        memory_path: Optional[Union[str, Path]] = None,
        self_learning: Optional[SelfLearningSystem] = None,
        feedback_analyzer=None,
        engine=None,
        collector=None,
        llm: Optional[callable] = None,
    ) -> None:
        self.self_learning = self_learning if self_learning is not None else SelfLearningSystem()
        path = Path(memory_path) if memory_path else _DEFAULT_MEMORY_PATH
        self.memory = ClosedLoopMemoryStore(path=path)
        self.think = ThinkModule(
            self_learning=self.self_learning,
            feedback_analyzer=feedback_analyzer,
            llm=llm,
        )
        self.decision = DecisionModule()
        self.act = ActModule(
            self_learning=self.self_learning,
            engine=engine,
            collector=collector,
        )

    def _backfill_pending_effects(self, current_accuracy: Optional[float]) -> None:
        """用本轮实测准确率回填上一轮动作的 delta_accuracy（真实效果，非占位 0.0）。

        上轮执行动作时只记录 baseline_accuracy，本轮拿到最新准确率后，
        计算 delta_accuracy = 当前准确率 - baseline_accuracy 并回填 recorded_at，
        形成"执行 → 验证 → 回填"的真实效果闭环。
        """
        if current_accuracy is None:
            return
        for effect in self.memory.get("effects"):
            if not isinstance(effect, dict):
                continue
            if effect.get("delta_accuracy") is not None:
                continue
            baseline = effect.get("baseline_accuracy")
            if baseline is None:
                continue
            effect["delta_accuracy"] = float(current_accuracy) - float(baseline)
            effect["recorded_at"] = datetime.now().isoformat()

    def _self_correct(self) -> None:
        """读取记忆库 effects，若有 delta_accuracy 记录则计算均值写入 meta，并喂给决策模块。"""
        effects = self.memory.get("effects")
        deltas = [
            e.get("delta_accuracy")
            for e in effects
            if isinstance(e, dict) and e.get("delta_accuracy") is not None
        ]
        if deltas:
            avg_effect_gain = sum(deltas) / len(deltas)
            self.memory.set_meta("avg_effect_gain", avg_effect_gain)
            self.decision.set_avg_effect_gain(avg_effect_gain)

    def run_once(self, cycle_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行一轮完整闭环，返回 {"actions", "skipped", ...}。

        cycle_data: 循环数据，至少应包含可选的 "period" 键用于去重。
        """
        period = cycle_data.get("period")
        current_accuracy = cycle_data.get("current_accuracy")
        meta = self.memory.data.get("meta", {})
        if period is not None and period == meta.get("last_period"):
            return {"actions": [], "skipped": True, "reason": "period already processed"}

        # ① 效果回填：先用本轮准确率验证上一轮动作的真实效果
        self._backfill_pending_effects(current_accuracy)
        # ② 自校正：计算 avg_effect_gain 并喂给决策模块
        self._self_correct()
        ctx = self.think.think()
        decided = self.decision.decide(ctx.candidates)

        results: List[Dict[str, Any]] = []
        for action in decided:
            result = self.act.act(action)
            record = dict(result)
            record.setdefault("action_type", getattr(action, "action_type", None))
            record.setdefault("priority", getattr(action, "priority", None))
            self.memory.append("actions", record)
            results.append(record)

        if period is not None:
            self.memory.set_meta("last_period", period)
            self.memory.set_meta("run_count", int(meta.get("run_count", 0)) + 1)

        # 更新 LLM 使用计数：reasoning 中含 "LLM增强" 则该轮计一次
        if any(isinstance(r, str) and "LLM增强" in r for r in ctx.reasoning):
            self.memory.set_meta("llm_usage", int(meta.get("llm_usage", 0)) + 1)

        # 仅在确有动作执行时追加 effects 占位，避免无动作轮次用 0.0 稀释自校正信号
        if any(isinstance(res, dict) and res.get("executed") for res in results):
            self.memory.append("effects", {
                "event_id": len(self.memory.get("actions")),
                "baseline_accuracy": current_accuracy,
                "delta_accuracy": None,
                "recorded_at": None,
            })

        # 保存失败由 ClosedLoopMemoryStore.save 内部降级，不再中断
        self.memory.save()

        return {"actions": results, "skipped": False, "reasoning": ctx.reasoning}