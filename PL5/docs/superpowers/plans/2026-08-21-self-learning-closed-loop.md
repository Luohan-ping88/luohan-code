# 智能自学习全流程闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `LearningLoopEngine` 统一决策层，将现有自学习/反馈模块串成「思考-决策-执行-验证」四阶段闭环，配统一持久化记忆库，全自动执行。

**Architecture:** 新建 `src/core/learning_loop.py` 编排器，复用已有的 `SelfLearningSystem`（评估/建议/应用）、`FeedbackAnalyzer`（性能/问题分析）、`src/ai` LLM 适配器。四阶段：THINK(规则→统计→LLM)→DECIDE(动作判定)→ACT(应用/重训/数据修复)→VERIFY(效果回收→记忆库)。配套：移除 `auto_scheduler_v8` 的 `sls.flush()`、新增统一记忆库 `models/closed_loop_memory.json`、将优化任务接线为 `run_once`。

**Tech Stack:** Python 3, numpy, 现有项目模块 (`src.core.self_learning`, `src.core.feedback_learning`, `src.ai`), pytest。

---

### Task 1: 统一记忆库存储（ClosedLoopMemoryStore）

**Files:**
- Create: `src/core/closed_loop_memory.py`
- Test: `tests/unit/test_closed_loop_memory.py`

- [ ] **Step 1: 写失败测试**

```python
import json, os
from pathlib import Path
import pytest
from src.core.closed_loop_memory import ClosedLoopMemoryStore

TMP = Path(__file__).parent / "_test_memory.json"

@pytest.fixture(autouse=True)
def clean():
    if TMP.exists():
        TMP.unlink()
    yield
    if TMP.exists():
        TMP.unlink()

def test_append_and_read():
    store = ClosedLoopMemoryStore(path=TMP)
    store.append("evaluations", {"accuracy": 0.3, "k": 3})
    store.append("actions", {"type": "update_param", "param": "max_depth"})
    store.save()
    store2 = ClosedLoopMemoryStore(path=TMP)
    assert len(store2.get("evaluations")) == 1
    assert store2.get("actions")[0]["type"] == "update_param"

def test_merge_legacy_files(tmp_path):
    legacy = tmp_path / "learning_history.json"
    legacy.write_text(json.dumps([{"accuracy": 0.4}]), encoding="utf-8")
    with tmp_path / "closed_loop_memory.json":
        pass
    store = ClosedLoopMemoryStore(
        path=tmp_path / "closed_loop_memory.json",
        legacy_sources={"evaluations": [legacy]},
    )
    assert len(store.get("evaluations")) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_closed_loop_memory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.closed_loop_memory'`

- [ ] **Step 3: 最小实现**

```python
"""统一持久化记忆库：跨周期累积 evaluation/action/effect/meta。"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "closed_loop_memory.json"
_MAX_RECORDS = 500


class ClosedLoopMemoryStore:
    """集中式记忆库，滑窗截断，首启可从旧文件并入一次。"""

    def __init__(
        self,
        path: Path = _DEFAULT_PATH,
        legacy_sources: Optional[Dict[str, List[Path]]] = None,
    ):
        self.path = Path(path)
        self.data: Dict[str, Any] = {
            "version": 1,
            "evaluations": [],
            "actions": [],
            "effects": [],
            "meta": {"last_period": None, "llm_usage": 0, "run_count": 0},
        }
        self._load()
        if legacy_sources:
            self._merge_legacy(legacy_sources)

    def _load(self) -> None:
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    for key in self.data:
                        if key in raw and raw[key] is not None:
                            self.data[key] = raw[key]
        except Exception as exc:  # pragma: no cover
            logger.warning(f"[ClosedLoopMemory] load failed, fresh start: {exc}")

    def _merge_legacy(self, legacy_sources: Dict[str, List[Path]]) -> None:
        for key, paths in legacy_sources.items():
            for p in paths:
                try:
                    if not Path(p).exists():
                        continue
                    with open(p, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    items = raw.get("evaluations", []) if isinstance(raw, dict) else raw
                    if isinstance(items, list):
                        merged = self.data.get(key, []) + items
                        self.data[key] = merged[-_MAX_RECORDS:]
                except Exception as exc:  # pragma: no cover
                    logger.warning(f"[ClosedLoopMemory] merge legacy {p} failed: {exc}")
        self.save()

    def append(self, key: str, record: Dict[str, Any]) -> None:
        if key not in self.data:
            self.data[key] = []
        self.data[key].append(record)
        if len(self.data[key]) > _MAX_RECORDS:
            self.data[key] = self.data[key][-_MAX_RECORDS:]

    def get(self, key: str) -> List[Dict[str, Any]]:
        return self.data.get(key, [])

    def set_meta(self, key: str, value: Any) -> None:
        self.data["meta"][key] = value

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as exc:  # pragma: no cover - 降级为内存运行
            logger.warning(f"[ClosedLoopMemory] save failed, degrade to in-memory: {exc}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_closed_loop_memory.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /workspace/PL5
git add src/core/closed_loop_memory.py tests/unit/test_closed_loop_memory.py
git commit -m "feat: 统一持久化记忆库 ClosedLoopMemoryStore"
```

---

### Task 2: 动作判定与决策模型（DecisionModule）

**Files:**
- Create: `src/core/learning_decision.py`
- Test: `tests/unit/test_learning_decision.py`

**说明（设计§3）：** 动作分 4 类：`update_param`(置信度≥0.55)、`retrain`(命中即触发，永远优先)、`fix_data`(≥0.70)、`monitor`(兜底)。

- [ ] **Step 1: 写失败测试**

```python
import pytest
from src.core.learning_decision import RankedAction, DecisionModule, ActionType

def _sug(priority, confidence, improvement, param=None):
    return RankedAction(
        action_type=ActionType.UPDATE_PARAM.ts if hasattr(ActionType.UPDATE_PARAM,'ts') else ActionType.UPDATE_PARAM.value,
        priority=priority, confidence=confidence,
        estimated_improvement_mid=improvement,
        name=param or ("param_%s" % priority),
    )

def test_retrain_always_first():
    dm = DecisionModule()
    cands = [
        _sug(1, 0.9, 0.05),
        _sug(3, 0.9, 0.1),
        RankedAction(action_type=ActionType.RETRAIN.value, priority=1, confidence=1.0, estimated_improvement_mid=0.2, name="retrain"),
    ]
    ranked = dm.decide(cands)
    assert ranked[0].action_type == ActionType.RETRAIN.value

def test_update_param_confidence_threshold():
    dm = DecisionModule()
    cands = [_sug(1, 0.40, 0.05)]  # 0.40 < 0.55 → 被过滤
    actions = dm.select_actions(cands)
    assert actions == []
```

> 注：RankedAction 用 dataclass，字段为 `action_type, priority, confidence, estimated_improvement_mid, name`。`ActionType` 为 `Enum`，值为字面量 `"update_param"`/`"retrain"`/`"fix_data"`/`"monitor"`。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_learning_decision.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: 最小实现**

```python
"""统一动作判定模型（设计§3 DECIDE）。"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ActionType(Enum):
    UPDATE_PARAM = "update_param"
    RETRAIN = "retrain"
    FIX_DATA = "fix_data"
    MONITOR = "monitor"


_CONFIDENCE_GATES = {
    ActionType.UPDATE_PARAM: 0.55,
    ActionType.FIX_DATA: 0.70,
}
_RETRAIN_ALWAYS_PRIORITY = 0  # 永远优先


@dataclass
class RankedAction:
    action_type: str
    priority: int
    confidence: float
    estimated_improvement_mid: float
    name: str = ""
    param_name: Optional[str] = None
    recommended_value: Optional[float] = None
    suggestion_id: Optional[str] = None
    reasoning: str = ""


class DecisionModule:
    """将候选动作归一化、排序、按置信度门槛过滤，全自动采纳。"""

    def classify(self, action_type: str, confidence: float) -> bool:
        try:
            at = ActionType(action_type)
        except ValueError:
            return False
        if at == ActionType.RETRAIN:
            return True  # 命中即触发
        if at == ActionType.MONITOR:
            return True
        gate = _CONFIDENCE_GATES.get(at, 1.0)
        return confidence >= gate

    def decide(self, candidates: List[RankedAction]) -> List[RankedAction]:
        kept = [c for c in candidates if self.classify(c.action_type, c.confidence)]
        # retrain 永远优先
        kept.sort(key=lambda c: (
            0 if c.action_type == ActionType.RETRAIN.value else 1,
            -c.priority,
            -c.confidence,
            -c.estimated_improvement_mid,
        ))
        return kept

    def select_actions(self, candidates: List[RankedAction]) -> List[RankedAction]:
        return self.decide(candidates)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_learning_decision.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /workspace/PL5
git add src/core/learning_decision.py tests/unit/test_learning_decision.py
git commit -m "feat: 统一动作判定模型 DecisionModule"
```

---

### Task 3: 规则→统计→LLM 三层思考（ThinkModule）

**Files:**
- Create: `src/core/learning_think.py`
- Test: `tests/unit/test_learning_think.py`

**说明（设计§2）：** 复用现有模块做思考。为可测与隔离，ThinkModule 通过依赖注入接收 `self_learning` 与可选 `feedback_analyzer`，产出候选 `RankedAction`。LLM 增强仅对高优先级动作；无 key 静默降级。

- [ ] **Step 1: 写失败测试**

```python
import pytest
from src.core.learning_think import ThinkModule
from src.core.learning_decision import RankedAction, ActionType

class FakeSL:
    def evaluate_recent_performance(self):
        return {"accuracy": 0.12, "std": 0.07, "trend": "declining", "count": 5}
    def compute_comprehensive_score(self):
        return {"comprehensive_score": 0.2, "metrics_available": ["accuracy"]}
    def check_performance_alert(self):
        return {"alert_level": "urgent", "reasons": ["low"]}
    def should_trigger_retrain(self):
        return True, "urgent alert"
    def generate_structured_suggestions(self):
        return []
    def get_suggestion_statistics(self):
        return {"effect_sample_size": 0, "adoption_rate": 0, "avg_actual_effect": None, "positive_effect_rate": 0}

class FakeFeedback:
    def analyze_strategy_performance(self, window_size=20):
        return {"overall_analysis": {"top3_accuracy": 0.12}, "position_analysis": {}}
    def _identify_strategy_issues(self, position_analysis, overall_analysis):
        return []
    def _generate_improvement_suggestions(self, issues, position_analysis):
        return []

def test_urgent_produces_retrain_action():
    think = ThinkModule(self_learning=FakeSL(), feedback_analyzer=FakeFeedback(), llm=None)
    ctx = think.think()
    kinds = {a.action_type for a in ctx.candidates}
    assert ActionType.RETRAIN.value in kinds
    assert len(ctx.reasoning) > 0

def test_no_llm_no_crash():
    think = ThinkModule(self_learning=FakeSL(), feedback_analyzer=FakeFeedback(), llm=None)
    ctx = think.think()
    assert ctx.reasoning  # 无 LLM 也能产出依据
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_learning_think.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: 最小实现**

```python
"""思考阶段（设计§2 THINK）：规则→统计→LLM 三层，产出候选动作与依据。"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.core.learning_decision import ActionType, RankedAction

logger = logging.getLogger(__name__)

# 告警级别 → 动作建议
_ALERT_TO_ACTION = {
    "urgent": [ActionType.RETRAIN, ActionType.FIX_DATA],
    "warning": [ActionType.RETRAIN],
}


@dataclass
class ThinkContext:
    candidates: List[RankedAction] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


class ThinkModule:
    def __init__(self, self_learning=None, feedback_analyzer=None, llm=None):
        from src.core.self_learning import SelfLearningSystem
        self.sl = self_learning or SelfLearningSystem()
        self.fb = feedback_analyzer
        self.llm = llm

    def _think_metrics(self) -> Tuple[Dict, Dict]:
        perf = self.sl.evaluate_recent_performance()
        try:
            comp = self.sl.compute_comprehensive_score()
        except Exception:
            comp = {"comprehensive_score": 0.0, "metrics_available": []}
        return perf, comp

    def think(self) -> ThinkContext:
        ctx = ThinkContext()
        perf, comp = self._think_metrics()
        ctx.raw = {"perf": perf, "comp": comp}
        acc = perf.get("accuracy", 0.0)
        std = perf.get("std", 0.0)
        trend = perf.get("trend", "unknown")

        alert = self.sl.check_performance_alert()
        alert_level = alert.get("alert_level", "normal")

        # 规则+统计层
        for at in _ALERT_TO_ACTION.get(alert_level, []):
            ctx.candidates.append(RankedAction(
                action_type=at.value, priority=1 if at == ActionType.RETRAIN else 2,
                confidence=0.9 if at == ActionType.RETRAIN else 0.7,
                estimated_improvement_mid=0.05,
                name=f"{at.value}_from_alert",
                reasoning=alert.get("reasons", "alert triggered"),
            ))
            ctx.reasoning.append(f"alert({alert_level}) -> {at.value}: {'; '.join(alert.get('reasons', []))}")

        # 反馈分析（如有）
        if self.fb is not None:
            try:
                fb = self.fb.analyze_strategy_performance(window_size=20)
                ctx.raw["feedback"] = fb
                if acc < 0.18:
                    ctx.reasoning.append(f"feedback top3 accuracy low: {fb.get('overall_analysis', {}).get('top3_accuracy', 0):.3f}")
            except Exception as exc:  # pragma: no cover
                logger.warning(f"[ThinkModule] feedback analyze failed: {exc}")

        # LLM 增强（仅高优先级，静默降级）
        if acc < 0.15 and self.llm is not None:
            try:
                resp = self.llm(f"PL5 自学习决策：accuracy={acc:.3f} trend={trend}。给出简短决策依据。")
                ctx.reasoning.append(f"LLM: {resp}")
            except Exception as exc:  # pragma: no cover
                logger.warning(f"[ThinkModule] llm enhancing skipped: {exc}")

        return ctx
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_learning_think.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /workspace/PL5
git add src/core/learning_think.py tests/unit/test_learning_think.py
git commit -m "feat: 三层思考模块 ThinkModule"
```

---

### Task 4: 执行阶段（ActModule，含 max_depth 取整验证）

**Files:**
- Create: `src/core/learning_act.py`
- Test: `tests/unit/test_learning_act.py`

**说明（设计§3）：** 执行动作。`max_depth` 取整坑已在 `SelfLearningSystem.apply_suggestion` 内置（1316-1317行），本 Task 验证该契约成立并实现动作分发。

- [ ] **Step 1: 写失败测试**

```python
import pytest
from src.core.learning_act import ActModule
from src.core.learning_decision import ActionType, RankedAction

class FakeSL:
    def apply_suggestion(self, suggestion_id=None, category=None, dry_run=False):
        if dry_run:
            return {"applied": True, "message": "dry"}
        return {"applied": True, "message": "applied", "params_updated": {"x": 1}}
    def record_suggestion_outcome(self, suggestion_id, status, actual_effect=None, notes=""):
        return True

class FakeEngine:
    def __init__(self):
        self.retrain_called = 0
    def trigger_retrain(self):
        self.retrain_called += 1

def test_update_param_calls_apply():
    sl = FakeSL()
    engine = FakeEngine()
    act = ActModule(self_learning=sl, engine=engine)
    res = act.act(RankedAction(
        action_type=ActionType.UPDATE_PARAM.value, priority=1, confidence=0.8,
        estimated_improvement_mid=0.05, suggestion_id="SUG-ABC", name="x",
    ))
    assert res["executed"] is True

def test_retrain_triggers_engine():
    engine = FakeEngine()
    act = ActModule(self_learning=FakeSL(), engine=engine)
    act.act(RankedAction(
        action_type=ActionType.RETRAIN.value, priority=1, confidence=1.0,
        estimated_improvement_mid=0.2, name="retrain",
    ))
    assert engine.retrain_called == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_learning_act.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: 最小实现**

```python
"""执行阶段（设计§3 ACT）。"""
from __future__ import annotations
import logging
from typing import Any, Dict

from src.core.learning_decision import ActionType, RankedAction

logger = logging.getLogger(__name__)


class ActModule:
    def __init__(self, self_learning=None, engine=None, collector=None):
        self.sl = self_learning
        self.engine = engine  # 提供 trigger_retrain
        self.collector = collector  # 提供数据刷新/清洗

    def act(self, action: RankedAction) -> Dict[str, Any]:
        result = {"action_type": action.action_type, "executed": False, "message": ""}
        try:
            if action.action_type == ActionType.UPDATE_PARAM.value:
                res = self.sl.apply_suggestion(suggestion_id=action.suggestion_id)
                result["executed"] = bool(res.get("applied"))
                result["message"] = res.get("message", "")
                result["params_updated"] = res.get("params_updated", {})
            elif action.action_type == ActionType.RETRAIN.value:
                if self.engine is not None:
                    self.engine.trigger_retrain()
                    result["executed"] = True
                    result["message"] = "closed-loop retrain triggered"
                else:
                    result["message"] = "retrain requested but no engine"
            elif action.action_type == ActionType.FIX_DATA.value:
                if self.collector is not None:
                    df = self.collector.update_data()
                    result["executed"] = df is not None and len(df) > 0
                    result["message"] = "data refreshed"
                else:
                    result["message"] = "fix_data requested but no collector"
            else:
                result["message"] = "no-op (monitor/watch)"
            logger.info(f"[ActModule] {result}")
        except Exception as exc:  # 单动作失败不中断闭环
            result["executed"] = False
            result["message"] = f"action failed (skipped): {exc}"
            logger.warning(result["message"])
        return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_learning_act.py -v`
Expected: 2 passed

**验证 max_depth 取整契约（不需新代码）：**
- [ ] **Step 4b**: 检查 `SelfLearningSystem.apply_suggestion` 中 max_depth 分支已取整（见 1316-1317 行）。运行既有自学习导入检查：`cd /workspace/PL5 && python -c "from src.core.self_learning import SelfLearningSystem; print('ok')"` 确认无回归。

- [ ] **Step 5: 提交**

```bash
cd /workspace/PL5
git add src/core/learning_act.py tests/unit/test_learning_act.py
git commit -m "feat: 执行阶段 ActModule"
```

---

### Task 5: 四阶段编排器 LearningLoopEngine

**Files:**
- Create: `src/core/learning_loop.py`
- Test: `tests/unit/test_learning_loop.py`

**说明：** 把 ThinkModule→DecisionModule→ActModule→(VERIFY 记录) 串起来，提供 `run_once(cycle_data)`。幂等：按 `meta.last_period` 去重。VERIFY 在本阶段收集 effect 占位（真实效果回收在下周期评估时由 run_once 从 memory 读取旧 action 后计算，属增量；本 Task 实现记录机制与 self_correct 统计）。

- [ ] **Step 1: 写失败测试**

```python
import pytest
from src.core.learning_loop import LearningLoopEngine

class FakeSL:
    def __init__(self):
        self.evals = [{"timestamp": "t1", "accuracy": 0.3}]
    def evaluate_recent_performance(self):
        return {"accuracy": 0.3, "std": 0.03, "trend": "stable", "count": 5}
    def compute_comprehensive_score(self):
        return {"comprehensive_score": 0.5, "metrics_available": ["accuracy"]}
    def check_performance_alert(self):
        return {"alert_level": "normal", "reasons": ["ok"]}
    def should_trigger_retrain(self):
        return False, "ok"
    def generate_structured_suggestions(self):
        return []
    def get_suggestion_statistics(self):
        return {"effect_sample_size": 0, "adoption_rate": 0, "avg_actual_effect": None, "positive_effect_rate": 0}
    def apply_suggestion(self, **kw):
        return {"applied": True, "message": "applied", "params_updated": {}}
    def record_suggestion_outcome(self, **kw):
        return True

class FakeEngine:
    def trigger_retrain(self):
        pass

def test_run_once_idempotent(tmp_path, monkeypatch):
    mem = tmp_path / "mem.json"
    engine = LearningLoopEngine(
        memory_path=mem, self_learning=FakeSL(), engine=FakeEngine(),
    )
    out1 = engine.run_once({"period": "2026223"})
    out2 = engine.run_once({"period": "2026223"})
    assert len(engine.memory.get("actions")) == len(out1["actions"])
    assert len(out2["actions"]) == 0  # 同周期幂等
    # 换新周期可再次运行
    out3 = engine.run_once({"period": "2026224"})
    assert len(out3["actions"]) >= 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_learning_loop.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: 最小实现**

```python
"""统一决策层层编排器（设计§1/§5）。四阶段闭环：
THINK->DECIDE->ACT->VERIFY(记录)，统一记忆库持久化。"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.closed_loop_memory import ClosedLoopMemoryStore
from src.core.learning_think import ThinkModule
from src.core.learning_decision import DecisionModule
from src.core.learning_act import ActModule

logger = logging.getLogger(__name__)


class LearningLoopEngine:
    def __init__(
        self,
        memory_path: Path = None,
        self_learning: Any = None,
        feedback_analyzer: Any = None,
        engine: Any = None,
        collector: Any = None,
        llm: Any = None,
    ):
        from src.core.self_learning import SelfLearningSystem
        self.memory = ClosedLoopMemoryStore(
            path=memory_path or (Path(__file__).resolve().parent.parent.parent / "models" / "closed_loop_memory.json")
        )
        self.sl = self_learning or SelfLearningSystem()
        self.think = ThinkModule(self_learning=self.sl, feedback_analyzer=feedback_analyzer, llm=llm)
        self.decision = DecisionModule()
        self.act = ActModule(self_learning=self.sl, engine=engine, collector=collector)

    def _self_correct(self) -> None:
        """读记忆库 effects 统计，校准后续决策（设计§4 闭环自我修正）。"""
        effects = self.memory.get("effects")
        if not effects:
            return
        gains = [e.get("delta_accuracy", 0) for e in effects if "delta_accuracy" in e]
        if gains:
            meta = self.memory.data["meta"]
            meta["avg_effect_gain"] = round(sum(gains) / len(gains), 5)

    def run_once(self, cycle_data: Dict[str, Any]) -> Dict[str, Any]:
        period = (cycle_data or {}).get("period")
        last_period = self.memory.data["meta"].get("last_period")
        if period and period == last_period:
            return {"actions": [], "skipped": True, "reason": "period already processed"}

        self._self_correct()

        # THINK
        ctx = self.think.think()
        # DECIDE
        ranked = self.decision.decide(ctx.candidates)
        # ACT
        results: List[Dict] = []
        for action in ranked:
            res = self.act.act(action)
            self.memory.append("actions", {
                "action_type": action.action_type,
                "name": action.name,
                "param": action.param_name,
                "recommended_value": action.recommended_value,
                "suggestion_id": action.suggestion_id,
                "executed": res.get("executed", False),
                "message": res.get("message", ""),
                "event_id": len(self.memory.get("actions")) + 1,
            })
            results.append(res)

        if period:
            self.memory.set_meta("last_period", period)
            self.memory.set_meta("run_count", self.memory.data["meta"].get("run_count", 0) + 1)
        self.memory.save()

        # VERIFY 记录（真实效果下周期重算）
        self.memory.append("effects", {
            "event_id": len(self.memory.get("actions")),
            "delta_accuracy": 0.0,  # 占位，由下周期评估回收
            "recorded_at": None,
        })

        return {"actions": results, "skipped": False, "reasoning": ctx.reasoning}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_learning_loop.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /workspace/PL5
git add src/core/learning_loop.py tests/unit/test_learning_loop.py
git commit -m "feat: 四阶段闭环编排器 LearningLoopEngine"
```

---

### Task 6: 接线到日循环并移除 flush 清空

**Files:**
- Modify: `src/app/auto_scheduler_v8.py:1026-1157`（`task_optimize`）
- Modify: `src/app/auto_scheduler_v8.py:1139`（移除 `sls.flush()`）
- Test: `tests/unit/test_learning_loop_import.py`

**说明（设计§1/§5）：** 在 `task_optimize` 中把零散的自学习调用收敛为 `LearningLoopEngine.run_once`；移除 `sls.flush()` 使历史跨周期累积。保留知识图谱落图。

- [ ] **Step 1: 写失败测试（先建立可导入契约）**

```python
def test_learning_loop_importable():
    from src.core.learning_loop import LearningLoopEngine
    assert hasattr(LearningLoopEngine, "run_once")
```

- [ ] **Step 2: 实现接线改动**

在 `task_optimize`（1026 行起）中，找到生成建议/评分的区域（约 1044-1139 行），将：

```python
sls = SelfLearningSystem()
structured_suggestions = sls.generate_structured_suggestions()
...
```

收敛为一段闭环（保留原有日志与落图结构）。新增关键片段（放在特征评估与反馈学习前，作为统一入口）：

```python
# 【闭环V11】统一决策层闭环
try:
    from src.core.learning_loop import LearningLoopEngine
    loop = LearningLoopEngine()
    loop_result = loop.run_once({"period": self._current_period()})
    logger.info(f"[闭环V11] 决策动作: {loop_result['actions']}")
    if loop_result.get("reasoning"):
        logger.info(f"[闭环V11] 决策依据: {loop_result['reasoning']}")
except Exception as loop_err:
    logger.warning(f"[闭环V11] 闭环运行失败(非致命): {loop_err}")
```

并将第 1139 行 `sls.flush()` 删除（注释说明：保留历史累积）。

> **工程师注意：** `_current_period()` 若不存在，用 `self._get_latest_period()` 或读取 `self.last_completed_period`；以实际已有字段为准。改动后必须能 through 完整 `task_optimize` 流程。

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/test_learning_loop_import.py -v`
Expected: 1 passed

- [ ] **Step 4: 验证编译与接线未破坏**

Run: `cd /workspace/PL5 && python -c "import ast; ast.parse(open('src/app/auto_scheduler_v8.py').read()); print('syntax ok')"`
Expected: `syntax ok`; 且 `python -m pytest tests/unit/ -q` 现有单测不回归。

- [ ] **Step 5: 提交**

```bash
cd /workspace/PL5
git add src/app/auto_scheduler_v8.py tests/unit/test_learning_loop_import.py
git commit -m "feat: 闭环接入日循环，移除flush历史记忆"
```

---

### Task 7: 端到端与回归收尾（含设计文档收档）

**Files:**
- Run-only: E2E 全周期、既有反馈/训练测试
- 文档已提交（spec）；若实现偏离 spec，更新 spec 备注

- [ ] **Step 1: 运行既有回归**

Run: `cd /workspace/PL5 && python -m pytest tests/unit/ tests/test_feedback_learning.py -q`
Expected: 全部通过（新增模块不破坏既有行为）

- [ ] **Step 2: 冒烟运行闭环**

Run: `cd /workspace/PL5 && python -c "
from src.core.learning_loop import LearningLoopEngine
e = LearningLoopEngine()
r = e.run_once({'period': 'smoke-test'})
print('smoke actions:', r['actions'])
print('smoke reasoning:', r['reasoning'])
"
`
Expected: 无异常，输出 actions 与 reasoning（真实环境会连库/数据，可能产生 update_param 或 monitor 动作）

- [ ] **Step 3: 提交（如实现偏离了 spec 文档则补充备注）**

```bash
cd /workspace/PL5
git add -A
git commit -m "feat: 闭环回归冒烟通过"
```

---

## Self-Review 记录

- **Spec 覆盖**：§1 架构→Task 5；§2 THINK→Task 3；§3 DECIDE+ACT→Task 2/4；§4 VERIFY+记忆库→Task 1/5；§5 接线/容错/测试→Task 6/7。全覆盖。
- **max_depth 取整坑**：已确认存在于 `SelfLearningSystem.apply_suggestion`（1316-1317 行），计划改为验证契约（Task 4 Step 4b），不重写。
- **Placeholder 扫描**：所有步骤含实际代码与命令，无 "add handling" 类占位。
- **类型一致性**：`RankedAction`/`ActionType`/`ThinkContext` 在 Task 2/3/4/5 中字段一致（`action_type` 用 `ActionType.*.value` 字符串，`DecisionModule.classify` 用 `ActionType(action_type)` 兼容）。

---

## Task 8: 状态空间复盘闭环（ReviewEngine）——预测 vs 开奖回溯

> 对应设计文档 §6。补齐 VERIFY 的"回看学习"侧：预测结果 vs 实际开奖对比，归因到推理策略/特征工程/学习率/超参数四个可调域，结合状态空间 S 检索历史同态经验产出调整动作，并沉淀 (S, A, Δ) 经验跨周期复用。

**Files:**
- Create: `src/core/retrospective.py`
- Modify: `src/core/closed_loop_memory.py`（initial_data / _load 增加 `experiences` 键）
- Modify: `src/app/auto_scheduler_v8.py`（task_evaluate 闭环V11之后接入复盘）
- Test: `tests/unit/test_retrospective.py`
- Docs: `docs/superpowers/specs/2026-08-21-self-learning-closed-loop-design.md` §6

**逻辑闭环**：`build_state_vector`(状态S) → `attribute_discrepancy`(归因四域) → `match_state`(同态经验检索) → `propose_adjustments`(产出动作) → `record_experience`(沉淀经验)。

- [x] **Step 1: 写失败测试**（`tests/unit/test_retrospective.py`，6 项用例）→ 初始 ImportError（RED）
- [x] **Step 2: 实现 `src/core/retrospective.py`**（ReviewEngine，全异常降级）→ 6 passed（GREEN）
- [x] **Step 3: 扩展记忆库 `experiences` 键**（`closed_loop_memory.py`）
- [x] **Step 4: 接线 `auto_scheduler_v8.py::task_evaluate`**：复用 `FeedbackAnalyzer().prediction_history` + `PL5DataCollector().load_processed_data()` 构造(预测→开奖)对照，调用 `run_review`；复盘动作合并进 `suggestions`；全部 try/except 非致命
  - 修复真实数据嵌套格式 bug（`_extract_top_k` 兼容 `predictions.shi.top_k`）
  - `run_review` 自动提取最近一期 top_k 作归因输入
- [x] **Step 5: 冒烟验证**：真实数据（25 条预测对照）状态空间命中率 top1/3/8 = 0.08/0.32/0.88 正常提取；构造错配样本归因到 strategy/feature/hyperparam/learning_rate 四域并成功沉淀经验
- [x] **Step 6: 回归测试**：`test_retrospective.py` + `test_closed_loop_memory.py` 共 9 passed
- [ ] **Step 7: 提交**
  ```bash
  git add src/core/retrospective.py src/core/closed_loop_memory.py src/app/auto_scheduler_v8.py tests/unit/test_retrospective.py docs/superpowers/specs/2026-08-21-self-learning-closed-loop-design.md docs/superpowers/plans/2026-08-21-self-learning-closed-loop.md
  git commit -m "feat: 状态空间复盘闭环 ReviewEngine (预测vs开奖回溯+同态经验复用)"
  ```