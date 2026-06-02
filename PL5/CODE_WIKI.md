# PL5 排列五高阶数理分析预测系统 - Code Wiki

## 目录

- [系统概述](#系统概述)
- [项目架构](#项目架构)
- [核心模块说明](#核心模块说明)
- [工作流程](#工作流程)
- [主要文件与类](#主要文件与类)
- [依赖关系](#依赖关系)
- [配置说明](#配置说明)
- [运行方式](#运行方式)
- [监控与维护](#监控与维护)

---

## 系统概述

PL5 是一个功能完善的排列五高阶数理分析预测系统，采用模块化设计，集成了多种先进的预测算法和智能优化机制。系统主要特点：

- **多模型融合预测**：集成 Stacking 集成、HMM、Mamba、iTransformer 等多种模型
- **智能 Agent 协作**：包含数据、研究、训练、评估、优化等多个智能体协同工作
- **完整的调度系统**：支持自动化定时任务、工作流编排和异常处理
- **自学习机制**：通过策略评估和优化持续提升预测准确率

---

## 项目架构

### 分层架构

```
┌───────────────────────────────────────────────────────────┐
│                   应用层 (Application)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │  AutoScheduler  │  │ Analyze & Send │  │ Email Sender │      │
│  │ 自动调度器 │  │ 分析发送模块 │  │ 邮件发送模块 │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
├───────────────────────────────────────────────────────────┤
│                    智能体层 (Agents)                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐│
│  │Data     │ │Research │ │Training │ │Evaluation│ │Optimi││
│  │Agent    │ │Agent    │ │Agent    │ │Agent    │ │zation││
│  │数据智能体 │ │研究智能体 │ │训练智能体 │ │评估智能体 │ │Agent ││
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────┘│
├───────────────────────────────────────────────────────────┤
│                     核心层 (Core)                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │Data     │ │Feature  │ │Models   │ │Self     │        │
│  │Collector│ │Engineer │ │Predictor│ │Learning │        │
│  │数据采集 │ │特征工程 │ │预测模型 │ │自学习   │        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
├───────────────────────────────────────────────────────────┤
│                     数据层 (Data)                         │
│  ┌─────────────────────────────────────────────────────┐  │
│  │         Vector DB + RAG + History Data              │  │
│  └─────────────────────────────────────────────────────┘  │
├───────────────────────────────────────────────────────────┤
│                    监控层 (Monitor)                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │System   │ │Perfect  │ │Prevent  │ │Immune   │        │
│  │Monitor  │ │Monitor  │ │Sleep    │ │System   │        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
└───────────────────────────────────────────────────────────┘
```

### 目录结构

```
PL5/
├── src/                              # 源代码主目录
│   ├── agents/                       # 智能体模块
│   ├── ai/                           # AI 工具系统与模型管理
│   ├── app/                          # 应用层模块
│   ├── core/                         # 核心算法模块
│   ├── tools/                        # 工具函数
│   └── utils/                        # 通用工具
├── config/                           # 配置文件
├── models/                           # 模型文件
├── data/                             # 数据文件
│   ├── raw/                          # 原始数据
│   └── processed/                    # 处理后的数据
├── logs/                             # 日志文件
├── results/                          # 预测结果
├── monitor/                          # 监控模块
├── tests/                            # 测试文件
├── docs/                             # 文档
└── main.py                           # 主入口文件
```

---

## 核心模块说明

### 1. 数据采集模块 ([src/core/data/collector.py](file:///workspace/PL5/src/core/data/collector.py))

**主要类**：`PL5DataCollector` (PL5DataCollectorV8)

**功能**：
- 从乐彩网 (`http://data.17500.cn/pl5_asc.txt`) 获取历史数据
- 解析原始文本数据，清洗和验证
- 本地数据备份与版本管理
- 支持缓存和恢复机制

**关键方法**：
- `fetch_from_network()` - 网络数据获取，带重试和错误处理
- `parse_raw_data()` - 解析原始文本数据
- `update_data()` - 完整的数据更新流程
- `get_latest_period()` - 获取最新期号

**设计特点**：
- 三级数据来源：网络 → 本地 → 备份
- 指数退避重试机制
- 数据验证与完整性检查
- 结构化日志记录

---

### 2. 特征工程模块 ([src/core/features/](file:///workspace/PL5/src/core/features/))

**主要类**：
- `FeatureEngineer` - 特征工程主类
- `DynamicFeatureValidator` - 动态特征验证
- `FeatureSelector` - 特征选择
- `FeatureVersionManager` - 特征版本管理

**功能**：
- 提取数百维统计特征（均值、方差、趋势、周期等）
- 特征重要性评估（RFE、模型特征重要性等）
- 动态特征组合优化
- 特征版本追踪与回滚

**特征类型**：
- 位置统计特征（各位置的历史分布）
- 趋势特征（移动平均、指数平滑）
- 周期特征（周期性模式识别）
- 相关性特征（位置间关联）

---

### 3. 预测模型模块 ([src/core/models/](file:///workspace/PL5/src/core/models/))

**主要模型**：

#### 3.1 Stacking 集成模型
- **基模型**：Random Forest、LightGBM/XGBoost、Gradient Boosting
- **元学习器**：Logistic Regression / ElasticNet
- **特点**：交叉验证训练，增强元特征

#### 3.2 序列模型
- **HMM** (Hidden Markov Model) - 隐藏马尔可夫模型
- **Mamba** - 最新的序列模型架构
- **iTransformer** - 改进的 Transformer 模型

#### 3.3 高级模型
- **MultivariateCopula** - 多元 Copula 模型
- **BayesianStructuralTimeSeries** - 贝叶斯结构时间序列
- **EnhancedBayesianQuantifier** - 贝叶斯不确定性量化

**增强预测器** (`EnhancedPL5Predictor`)
- 多模型融合预测
- 自适应权重优化
- 不确定性估计
- 并行训练支持

---

### 4. 自动调度器 ([src/app/auto_scheduler_v8.py](file:///workspace/PL5/src/app/auto_scheduler_v8.py))

**主要类**：`AutoSchedulerV8`

**功能**：
- 定时任务调度（数据获取、训练、预测等）
- 任务依赖管理与执行顺序
- 失败重试与异常报警
- 任务历史记录与状态追踪

**完整任务链**：
1. `data_fetch` - 数据获取
2. `evaluation` - 评估分析
3. `optimization` - 策略优化
4. `training` - 深度训练
5. `incremental_training` - 增量训练
6. `first_prediction_verification` - 首次预测验证
7. `second_prediction_verification` - 二次预测验证
8. `third_prediction_verification` - 三次预测验证
9. `deep_strategy_optimization` - 深度策略优化
10. `prediction_preview` - 预测预生成
11. `final_prediction` - 最终预测
12. `final_prediction_verification` - 最终预测验证
13. `pre_sale_prediction` - 售前最终预测
14. `send_report` - 发送报告

---

### 5. 智能体系统 ([src/agents/](file:///workspace/PL5/src/agents/))

**主要智能体**：
- `DataAgent` - 数据智能体，负责数据管理
- `ResearchAgent` - 研究智能体，负责特征和模式研究
- `TrainingAgent` - 训练智能体，负责模型训练
- `EvaluationAgent` - 评估智能体，负责性能评估
- `OptimizationAgent` - 优化智能体，负责策略优化

**智能体协作**：
- 通过协议通信
- 共享记忆与知识
- 投票决策机制
- 协调器统一管理

---

### 6. 监控系统 ([monitor/](file:///workspace/PL5/monitor/))

**主要组件**：
- `SystemMonitor` - 系统监控
- `PerfectMonitor` - 完善监控
- `AgentMonitor` - 智能体监控
- `PerformanceMonitor` - 性能监控
- `ImmuneSystem` - 免疫系统（异常检测与恢复）

---

### 7. 自学习系统 ([src/core/self_learning.py](file:///workspace/PL5/src/core/self_learning.py))

**主要类**：`SelfLearningSystem`

**功能**：
- 持续评估预测准确率
- 自动调整模型权重
- 策略优化建议生成
- 性能历史追踪

---

### 8. AI 工具系统 ([src/ai/](file:///workspace/PL5/src/ai/))

**主要模块**：
- `agents/` - 各种 AI 智能体
- `tools/` - 工具库与注册中心
- `models/` - 模型管理（本地、OpenAI、Hugging Face）
- `memory/` - 记忆系统（对话、执行、向量记忆）
- `orchestrator.py` - 工作流编排
- `api.py` - REST API 服务

---

## 工作流程

### 完整预测流程

1. **数据获取阶段**
   - 从网络获取最新开奖数据
   - 解析和验证数据
   - 更新本地数据存储

2. **特征工程阶段**
   - 提取统计和时序特征
   - 特征选择与优化
   - 动态特征验证

3. **模型预测阶段**
   - 多模型并行预测
   - 权重融合
   - 不确定性估计

4. **结果生成阶段**
   - Top-K 推荐号码
   - 预测报告生成
   - 邮件发送

5. **学习优化阶段**
   - 新数据开奖后评估
   - 策略优化
   - 模型微调/重训练

---

### 定时调度流程

```
21:25 → 开奖时间
22:15 → 数据获取 + 评估分析
22:45 → 策略优化
00:30 → 深度训练
08:00 → 上午增量训练 + 首次预测验证
12:00 → 中午增量训练 + 二次预测验证
14:00 → 下午增量训练 + 三次预测验证
16:00 → 深度策略优化
17:00 → 预测预生成
18:00 → 最终预测
19:00 → 最终预测验证
20:00 → 售前最终预测
20:15 → 发送邮件报告
```

---

## 主要文件与类

### 核心入口文件

| 文件 | 说明 |
|------|------|
| [main.py](file:///workspace/PL5/main.py) | 系统主入口，命令行界面 |
| [pl5_intelligent_system.py](file:///workspace/PL5/pl5_intelligent_system.py) | 智能系统入口 |

### 核心模块文件

| 文件 | 主要类 | 功能 |
|------|--------|------|
| [src/core/data/collector.py](file:///workspace/PL5/src/core/data/collector.py) | `PL5DataCollector` | 数据采集 |
| [src/core/features/engineer.py](file:///workspace/PL5/src/core/features/engineer.py) | `FeatureEngineer` | 特征工程 |
| [src/core/models/enhanced_predictor.py](file:///workspace/PL5/src/core/models/enhanced_predictor.py) | `EnhancedPL5Predictor`, `StackingEnsemble` | 增强预测器 |
| [src/app/auto_scheduler_v8.py](file:///workspace/PL5/src/app/auto_scheduler_v8.py) | `AutoSchedulerV8` | 自动调度器 |
| [src/app/email_sender.py](file:///workspace/PL5/src/app/email_sender.py) | `EmailSender` | 邮件发送 |

### 配置文件

| 文件 | 说明 |
|------|------|
| [config/config.json](file:///workspace/PL5/config/config.json) | 系统主配置 |
| [config/scheduler_config_v8.json](file:///workspace/PL5/config/scheduler_config_v8.json) | 调度器配置 |
| [config/email_config.json](file:///workspace/PL5/config/email_config.json) | 邮件配置 |

---

## 依赖关系

### 主要依赖库

| 库 | 用途 |
|----|------|
| numpy | 数值计算 |
| pandas | 数据处理 |
| scikit-learn | 机器学习基础库 |
| lightgbm / xgboost | 梯度提升模型 |
| fastapi | API 服务 |
| requests | 网络请求 |
| schedule | 定时调度 |

### 可选依赖

| 库 | 用途 |
|----|------|
| torch | PyTorch (深度学习) |
| llama-cpp-python | 本地 LLM 支持 |
| openai | OpenAI API |
| faiss-cpu | 向量搜索 |

### 依赖安装

```bash
pip install -r requirements.txt
```

---

## 配置说明

### 系统配置 ([config/config.json](file:///workspace/PL5/config/config.json))

```json
{
  "system": {
    "name": "排列五高阶数理分析预测系统",
    "version": "5.3",
    "debug": false
  },
  "scheduler": {
    "data_fetch_time": "00:00",
    "evaluation_time": "00:30",
    "optimization_start": "01:00",
    "training_start": "02:00",
    "training_deadline": "17:00",
    "email_send_time": "17:30",
    "enabled": true
  },
  "prediction": {
    "top_k": 8,
    "confidence_threshold": 0.6,
    "generate_report": true
  }
}
```

### 邮件配置 ([config/email_config.json](file:///workspace/PL5/config/email_config.json))

```json
{
  "sender_email": "your-email@example.com",
  "auth_code": "your-auth-code",
  "smtp_server": "smtp.qq.com",
  "smtp_port": 465,
  "recipients": ["recipient1@example.com"]
}
```

---

## 运行方式

### 命令行方式

```bash
# 查看帮助
python main.py --help

# 执行训练
python main.py train

# 执行预测
python main.py predict

# 分析并发送邮件
python main.py analyze

# 启动调度器
python main.py schedule

# 单次执行完整流程
python main.py schedule --once

# 查看系统状态
python main.py status
```

### 完整脚本方式

```bash
# 启动完整系统
python launch_system.py

# 启动可靠模式
python launch_system_reliable.py
```

### 服务方式

```bash
# 启动 API 服务
python -m src.ai.api

# 启动哨兵监控
python start_sentinel.py
```

---

## 监控与维护

### 系统监控

- **日志目录**：`logs/`
- **任务历史**：`logs/task_history_v8.pkl` / `logs/task_history_v8.json`
- **预测日志**：`logs/predictions/`
- **调度器状态**：`logs/scheduler_v8_status.json`

### 健康检查

```bash
# 运行健康检查
python run_health_check.py

# 系统状态查看
python main.py status
```

### 常见问题排查

1. **数据获取失败**：检查网络连接，尝试加载本地备份
2. **模型训练失败**：检查数据完整性、特征维度
3. **邮件发送失败**：验证 SMTP 配置和认证信息
4. **调度器异常**：查看任务历史和日志，恢复从断点继续

---

## 测试

```bash
# 运行所有测试
pytest tests/

# 运行端到端测试
pytest tests/e2e/

# 运行单元测试
pytest tests/unit/
```

---

## 扩展开发

### 添加新模型

1. 在 `src/core/models/` 中创建新模型类
2. 在 `EnhancedPL5Predictor` 中集成
3. 添加相关配置

### 自定义任务

1. 在 `AutoSchedulerV8.task_map` 中注册
2. 实现任务处理函数
3. 在 `setup_schedule` 中添加定时

### 新增智能体

1. 继承 `BaseAgent`
2. 实现核心方法
3. 在协调器中注册

---

## 相关文档

- [架构文档](file:///workspace/PL5/docs/architecture/ARCHITECTURE.md)
- [部署指南](file:///workspace/PL5/docs/deployment/DEPLOYMENT_GUIDE.md)
- [API 文档](file:///workspace/PL5/docs/API_DOCUMENTATION.md)
- [系统维护指南](file:///workspace/PL5/docs/SYSTEM_MAINTENANCE_GUIDE.md)
- [可靠性指南](file:///workspace/PL5/docs/RELIABILITY_GUIDE.md)

---

*最后更新：2026-06-02*
