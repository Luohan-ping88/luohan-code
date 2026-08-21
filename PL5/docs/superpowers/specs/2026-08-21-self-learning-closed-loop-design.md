# 智能自学习模型全面升级：全流程闭环设计

- 日期：2026-08-21
- 状态：已批准
- 目标：让智能自学习模型具备「学会思考、决策、学以致用」，形成四阶段全流程闭环；打通现有零散模块，引入统一决策层与统一持久化记忆库。

## 背景与现状

现有自学习能力分散在多个模块，但闭环未真正打通：

1. `src/core/self_learning.py`：`SelfLearningSystem`（V10.0/V10.3/V10.6）已实现评估记录、结构化建议生成、`apply_suggestion`/`auto_apply_suggestions` 参数应用、重训阈值判断。但 `auto_apply_suggestions` **从未被主流程调用**——建议"生成即止"，学以致用环节缺失。
2. `src/core/feedback_learning.py`：`FeedbackAnalyzer` 具备位置级性能分析、整体分析、问题识别、改进建议生成、反馈应用回 predictor。独立运行，结果未回写自学习系统。
3. `src/app/auto_scheduler_v8.py` 优化任务末尾调用 `sls.flush()` **清空内存历史**，自学习状态无法跨周期累积。
4. `src/core/orchestrator.py` 评估任务中写入 `record_evaluation`，但只打印前 5 条建议、仅日志提示重训，无实际执行动作。

**已修复前置缺陷**：`self_learning.py` 曾存在两个同名 `get_suggestion_statistics` 方法导致无限递归与遮蔽，已改名为 `generate_suggestion_report` 并在本地 HEAD（`f24577e`）与远程 main 同步。

## 升级范围（已确认）

- 打通现有闭环 + 重构为统一决策层（编排器）
- 引入外部 LLM 增强推理（规则为主 + LLM 增强，无 key 静默降级）
- 全自动执行：凡建议即采纳执行
- 统一持久化记忆库，去除 flush 清空，跨周期累积

## 架构

新增编排器 `LearningLoopEngine`（`src/core/learning_loop.py`），作为统一决策层入口，将现有模块串成可执行闭环。`learning_loop.py` 为新增；其余模块以复用为主、最小侵入。

```
┌─思考 THINK────────────────────────────────────────┐
│ 输入: 最新评估数据(accuracy/hit_rate/置信度)          │
│ 复用: FeedbackAnalyzer(位置性能/整体/问题识别)         │
│       SelfLearningSystem.generate_structured_suggestions │
│       LLM增强(可选,规则优先) → 生成结构化建议+理由     │
├─决策 DECIDE───────────────────────────────────────┤
│ 统一策略: 按优先级(紧急>重要>常规) + 置信度 + 预期收益     │
│ 全自动采纳 → 判定动作类型[改参数/重训/数据修复/监控]      │
├─执行 ACT──────────────────────────────────────────┤
│ 调 apply_suggestion(已具备) 落参到 model_config       │
│ 或 触发重训 → 交给深度训练子流程                       │
├─验证 VERIFY───────────────────────────────────────┤
│ 下一周期重算指标 → 记录实际收益(effect)                │
│ 回写统一记忆库(closed_loop_memory)                   │
└──→ 回到 THINK(读记忆库修正阈值/权重) ────────────────┘
```

### 配套改造（本设计范围内）

1. 移除优化任务末尾的 `sls.flush()` 清空（`auto_scheduler_v8.py`），保留历史累积，改为持久化后保留内存。
2. 统一持久化记忆库 `models/closed_loop_memory.json`，合并 evaluation + action + effect 三类记录，供跨周期回溯。
3. 接线：在 `auto_scheduler_v8` 优化任务处将零散调用收敛为 `LearningLoopEngine.run_once(cycle_data)` 一次闭环。

## 阶段设计

### §2 思考阶段（THINK）——规则 → 统计 → LLM 三层推理

**数据源（多源聚合）**：
- `FeedbackAnalyzer.analyze_strategy_performance(window=20)` → 位置级命中、整体性能、问题识别
- `SelfLearningSystem.evaluate_recent_performance()` → 近期准确率/趋势/波动
- `SelfLearningSystem.compute_comprehensive_score()` → 多维综合分
- `check_performance_alert()` → 告警级别
- `should_trigger_retrain()` → 重训信号

**三层推理**：
1. **规则层**：`_PARAMETER_KNOWLEDGE_BASE` 条件规则快速命中（低准确率→加树、高波动→降深度等），输出结构化建议。
2. **统计层**：Mann-Kendall 趋势 + 动态阈值 + 历史效果统计（`get_suggestion_statistics`）校准建议的优先级与置信度。
3. **LLM 增强层（可选）**：规则+统计产出候选后，仅对高优先级决策调用 `LLMFactory`（DeepSeek/OpenAI 适配器，已存在 `src/ai/`）生成自然语言决策依据；**无 key 时静默降级，绝不影响闭环**。

**输出**：统一的 `DecisionContext` 结构，包含候选动作列表 + 依据 + 置信度 + 优先级。

### §3 决策与执行（DECIDE + ACT）

**DECIDE——统一动作判定**：

| 动作类型 | 触发条件 | 置信度门槛 |
|---------|---------|-----------|
| `update_param` 改参数 | 命中参数规则建议 | ≥ 0.55 |
| `retrain` 触发重训 | URGENT 告警 / 显著下降趋势 / 特征维度不匹配 | 命中即触发 |
| `fix_data` 数据质量修复 | 数据异常(缺口/离群/过时) | ≥ 0.70 |
| `monitor` 仅监控 | 以上均不满足，性能正常 | 无 |

排序键：`(priority.value, confidence, estimated_improvement_mid)` 递减，但 **`retrain` 永远优先**（数据/模型根基问题优先解决）。

**ACT——执行落地**：
- `update_param` → 调用 `SelfLearningSystem.apply_suggestion(id)`，修正已知 **`max_depth` 取整坑**（建议值为 float 但配置需 int），写入 `model_config.yaml` 并标记建议 `applied`。
- `retrain` → 置闭环重训标志，驱动深度训练子任务，完成后重载模型。
- `fix_data` → 执行数据刷新/清洗（复用 collector）。
- 每次执行记录结构化日志：动作、参数、旧→新值、时间戳、依据 id。

**容错**：单个动作失败不中断闭环（记 `skipped`）。

### §4 验证与统一记忆库（VERIFY + 持久化）

**VERIFY——效果回收**：
- 动作执行后进入验证窗：下一批评估数据到达时重算指标。
- 对比动作前后：`Δaccuracy`、`Δhit_rate`、是否触发新告警。
- 产出 `effect` 记录（正/负/持平），写回记忆库，供下次 THINK 的统计层校准置信度与预期收益。

**统一记忆库 `models/closed_loop_memory.json`**：
```
{
  "version": 1,
  "evaluations": [...],      // 每次评估(accuracy/k/基线)
  "actions": [...],          // 每次执行的动作(类型/参数/旧新值/时间)
  "effects": [...],          // 每次验证回收的效果
  "meta": {"last_period", "llm_usage", "运行历史"}
}
```
- 兼容回读：若旧 `learning_history.json` / `suggestion_history.json` 存在，首启时并入一次。
- 移除 `sls.flush()` 清空逻辑，改为「持久化后保留内存」；容量用滑窗截断。

**闭环自我修正**：THINK 读记忆库的 `effects` 统计，动态校准 `_estimate_optimization_effect` 的置信度与预期收益区间——"越用越准"。

### §5 接线、错误处理与测试

**接线**：
- 在 `auto_scheduler_v8` 优化任务处收敛为 `LearningLoopEngine.run_once(cycle_data)`。
- 保留知识图谱落图（可选增强，不影响）。
- `run_once` 幂等：按 `last_period` 去重，同周期不重复执行。

**错误处理**：
- 四阶段各自 try/except；LLM 异常→静默降级为规则；动作失败→记 `skipped` 不中断。
- 记忆库写入失败→降级为内存运行，告警不崩溃。

**测试**：
- 单测：4 类动作判定、优先级排序、`max_depth` 取整修复、记忆库读写/合并、LLM 降级。
- 冒烟：`run_once` 跑一遍，断言生成 actions + 无异常。
- 现有日循环回归：确认新代码加载后闭环不破坏训练/预测。

**性能**：闭环为增量计算（聚合已有 stats，不做全量重训练外的重计算）；LLM 仅在重决策调用并加超时。

## 不做的事（YAGNI）

- 不引入外部向量/图数据库作为长期记忆（现有知识图谱已可为可选增强）。
- 不做纯 LLM 驱动（避免强外部依赖与费用）。
- 不改写已有 `FeedbackAnalyzer`/`SelfLearningSystem` 的既有能力，仅接线与补缺口。