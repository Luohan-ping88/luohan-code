# 工具系统分层架构 Spec

## Why
当前PL5预测系统V10.0已具备强大的核心预测能力（6种基学习器、4种Copula类型、HMM自适应、BSTS增量学习等），但缺乏对外提供标准化服务的能力。需要构建一个分层工具系统架构，将底层模型能力封装为可复用、可组合的工具层，支持多种上层应用场景（API服务、交互式分析、批量推理、策略回测等）。

## What Changes
- 新建 `src/tools/` 工具层，定义标准化的工具接口和实现
- 实现三层架构：基础设施层 → 核心能力层 → 应用工具层
- 每个工具遵循统一的输入/输出规范，支持链式调用
- 提供工具注册/发现机制，支持动态扩展
- 构建工具编排引擎，支持复杂工作流组合
- **BREAKING**: 需要新增依赖（可选：fastapi/pydantic用于API层）

## Impact
- Affected specs: model_comprehensive_optimization (基础能力)
- New code:
  - `src/tools/base.py` — 工具基类和接口定义
  - `src/tools/registry.py` — 工具注册与发现
  - `src/tools/predictor_tool.py` — 预测工具
  - `src/tools/analyzer_tool.py` — 分析工具
  - `src/tools/feature_tool.py` — 特征工程工具
  - `src/tools/model_tool.py` — 模型管理工具
  - `src/tools/orchestrator.py` — 工具编排引擎
  - `src/tools/api_layer.py` — API服务层（可选）

---

## ADDED Requirements

### Requirement: 工具接口标准化
所有工具 SHALL 实现统一的 `BaseTool` 接口，确保一致的行为模式。

#### Scenario: 工具基本生命周期
- **WHEN** 创建一个工具实例
- **THEN** 工具 SHALL 提供 `name`, `description`, `input_schema`, `output_schema` 属性
- **AND** 实现 `execute(ctx: ToolContext, **kwargs) -> ToolResult` 方法
- **AND** 支持 `validate(**kwargs)` 输入验证

#### Scenario: 工具结果统一格式
- **WHEN** 工具执行完成
- **THEN** 返回的 `ToolResult` SHALL 包含：
  - `success: bool` — 执行是否成功
  - `data: Any` — 结果数据
  - `metadata: Dict` — 执行元数据（耗时、版本等）
  - `errors: List[ErrorInfo]` — 错误信息列表

### Requirement: 三层工具架构
系统 SHALL 实现清晰的分层架构，每层职责明确。

#### Layer 1: 基础设施层 (Infrastructure)
提供通用的基础能力，不包含业务逻辑：

| 工具 | 功能 |
|------|------|
| `DataLoaderTool` | 数据加载与预处理 |
| `CacheTool` | 缓存管理（读写/失效/统计） |
| `ConfigTool` | 配置读取与环境变量解析 |
| `LoggerTool` | 结构化日志记录 |
| `ValidationTool` | 数据验证与清洗 |

#### Layer 2: 核心能力层 (Core Capabilities)
封装V10.0模型的各项核心能力为独立工具：

| 工具 | 功能 | 输入 → 输出 |
|------|------|-------------|
| `PredictorTool` | 单次预测 | 特征向量 → Top-K推荐+概率+不确定性 |
| `BatchPredictorTool` | 批量预测 | 多组特征 → 批量结果 |
| `FeatureEngineerTool` | 特征工程 | 原始数据 → 700+维特征矩阵 |
| `FeatureSelectorTool` | 特征选择 | 全量特征 → 最优子集 |
| `ModelAnalyzerTool` | 模型诊断 | 无输入 → 模型健康报告 |
| `WeightAnalyzerTool` | 权重分析 | 历史数据 → 权重建议+不确定性 |
| `HistoryEvaluatorTool` | 历史评估 | 预测历史 → 准确率/命中率/趋势 |
| `OptimizationAdvisorTool` | 优化建议 | 性能数据 → 结构化建议 |

#### Layer 3: 应用工具层 (Application Tools)
面向具体业务场景的高层工具：

| 工具 | 功能 |
|------|------|
| `DailyReportTool` | 生成每日分析报告（完整流程） |
| `QuickPredictTool` | 快速预测（简化输入） |
| `BacktestTool` | 策略回测（历史数据模拟） |
| `ComparisonTool` | 多模型对比（A/B测试） |
| `AlertTool` | 异常检测与告警 |
| `ExportTool` | 结果导出（多格式） |

### Requirement: 工具注册与发现机制
系统 SHALL 提供集中的工具注册表，支持动态发现和管理。

#### Scenario: 工具注册
- **WHEN** 模块导入时
- **THEN** 工具自动注册到 `ToolRegistry`
- **AND** 支持按名称、标签、层级查找工具
- **AND** 支持列出所有可用工具及其描述

#### Scenario: 工具发现
- **WHEN** 用户查询可用工具
- **THEN** `ToolRegistry.list_tools()` 返回所有已注册工具
- **AND** `ToolRegistry.get_tool(name)` 按名称获取工具实例
- **AND** `ToolRegistry.search(tags=["prediction", "batch"])` 按标签搜索

### Requirement: 工具编排引擎
系统 SHALL 提供工作流编排能力，支持多工具组合执行。

#### Scenario: 线性工作流
- **WHEN** 定义一个线性工作流（DAG）
- **THEN** 编排引擎按顺序执行每个步骤
- **AND** 上一步的输出自动传递给下一步作为输入
- **AND** 任一步骤失败时可配置重试或跳过策略

#### Scenario: 条件分支工作流
- **WHEN** 工作流中存在条件判断
- **THEN** 引擎根据前序步骤的结果决定后续路径
- **AND** 支持并行分支执行后合并结果

#### Scenario: 内置常用工作流模板
- **WHEN** 用户需要常见分析流程
- **THEN** 系统预置以下模板：
  - `daily_analysis`: 数据获取→特征工程→预测→生成报告
  - `model_training`: 数据加载→特征提取→训练→评估→保存
  - `evaluation`: 加载历史→对比预测→计算指标→生成报告
  - `full_pipeline`: 完整的每日自动化流程

### Requirement: ToolContext 上下文管理
每次工具执行 SHALL 携带完整的上下文信息。

#### Scenario: 上下文传递
- **WHEN** 工具被调用时
- **THEN** `ToolContext` 包含：
  - `config`: 当前配置（ModelConfig）
  - `cache`: 共享缓存引用
  - `logger`: 日志器
  - `metrics`: 性能指标收集器
  - `state`: 跨工具共享的状态字典
  - `user_id`: 用户标识（多租户场景）

### Requirement: 异步与并发支持
工具系统 SHALL 支持异步执行和并发控制。

#### Scenario: 异步工具执行
- **WHEN** 工具标记为 `async_capable=True`
- **THEN** 可通过 `await tool.execute_async(ctx, **kwargs)` 异步调用
- **AND** 编排引擎支持异步工作流

#### Scenario: 并发控制
- **WHEN** 多个工具同时执行
- **THEN** 系统通过信号量限制最大并发数
- **AND** 提供优先级队列调度

---

## MODIFIED Requirements

### Requirement: enhanced_predictor.py 工具化适配
现有的 `EnhancedPL5Predictor` SHALL 保持向后兼容，同时暴露工具友好的接口。

- 新增 `as_tool()` 类方法，返回包装后的 `PredictorTool`
- 新增 `get_capabilities()` 方法，返回模型能力描述
- 保持原有 `fit()`, `predict()`, `save_models()`, `load_models()` 接口不变

---

## 技术架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     应用层 (Application)                      │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ API服务   │ │ CLI命令行│ │ Web界面  │ │ 定时任务  │       │
│  └─────┬─────┘ └────┬────┘ └────┬────┘ └────┬────┘       │
├────────┼──────────┼──────────┼──────────┼───────────────────┤
│        │    编排引擎 (Orchestrator)      │                   │
│        │  ┌─────────────────────────┐   │                   │
│        │  │ DAG工作流 / 条件分支     │   │                   │
│        │  │ 重试 / 超时 / 缓存       │   │                   │
│        │  └────────────┬────────────┘   │                   │
├────────┼─────────────┼──────────────────┼───────────────────┤
│        │  应用工具层 (Layer 3)          │                   │
│  ┌─────▼─────┐ ┌────▼────┐ ┌────────▼────────┐           │
│  │日报工具    │ │回测工具  │ │ 对比/告警/导出     │           │
│  │快速预测    │ │         │ │                  │           │
│  └─────┬─────┘ └────┬────┘ └────────┬────────┘           │
├────────┼───────────┼──────────────────┼───────────────────┤
│        │  核心能力层 (Layer 2)          │                   │
│  ┌─────▼─────┐ ┌──▼──────┐ ┌─────────▼────────┐           │
│  │预测工具    │ │特征工具  │ │ 分析/权重/评估     │           │
│  │批量预测    │ │特征选择  │ │ 模型诊断/优化建议  │           │
│  └─────┬─────┘ └──┬──────┘ └─────────┬────────┘           │
├────────┼──────────┼──────────────────┼───────────────────┤
│        │  基础设施层 (Layer 1)          │                   │
│  ┌─────▼─────┐ ┌──▼──────┐ ┌─────────▼────────┐           │
│  │数据加载    │ │缓存/日志 │ │ 配置/验证/校验     │           │
│  └─────┬─────┘ └──┬──────┘ └─────────┬────────┘           │
├────────┼──────────┼──────────────────┼───────────────────┤
│        │  V10.0 核心模型层              │                   │
│  ┌─────▼─────┐ ┌──▼──────┐ ┌─────────▼────────┐           │
│  │Enhanced   │ │Advanced │ │ FeatureEng/Select │           │
│  │Predictor  │ │Sequence │ │ SelfLearning V10 │           │
│  │V10.0      │ │HMM/Cop  │ │ Config/VersionMgr │           │
│  └───────────┘ └─────────┘ └──────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

---

## 验证标准

### 功能验证
- [ ] 所有工具可独立实例化和执行
- [ ] 工具注册表能正确发现所有已注册工具
- [ ] 线性工作流正确传递数据
- [ ] 条件分支工作流根据条件正确路由
- [ ] 内置模板工作流端到端执行成功
- [ ] ToolContext 在工具间正确传递

### 设计质量
- [ ] 工具接口清晰，文档完善
- [ ] 分层合理，无循环依赖
- [ ] 易于扩展新工具（<50行代码添加新工具）
- [ ] 错误处理完善，失败有明确原因

### 性能要求
- [ ] 单个工具执行延迟 < 100ms（不含模型推理）
- [ ] 工作流编排开销 < 10ms
- [ ] 注册表查找 < 1ms
