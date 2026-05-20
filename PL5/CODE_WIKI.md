# PL5 智能预测系统 Code Wiki

## 项目概述

PL5 智能预测系统是一个功能强大的排列五（PL5）号码预测系统，采用多模型融合策略，集成了机器学习、深度学习、强化学习等多种算法，提供端到端的预测服务。

**项目版本**: V10.3  
**编程语言**: Python 3.8+  
**项目路径**: `/workspace/PL5`

---

## 目录结构

```
PL5/
├── main.py                      # 主入口文件（CLI）
├── pl5_intelligent_system.py    # 智能系统主类
├── requirements.txt             # 依赖列表
│
├── core/                        # 核心模块代理
│   ├── __init__.py
│   ├── config.py               # 配置代理
│   └── utils.py
│
├── src/
│   ├── core/                   # 核心功能模块
│   │   ├── config.py           # 统一配置管理
│   │   ├── data/               # 数据处理
│   │   │   ├── collector.py    # 数据采集器
│   │   │   └── validator.py    # 数据验证器
│   │   ├── features/           # 特征工程
│   │   │   ├── engineer.py     # 特征工程核心
│   │   │   ├── feature_selector.py
│   │   │   └── feature_version_manager.py
│   │   ├── models/             # 模型模块
│   │   │   ├── enhanced_predictor.py    # V10增强预测器
│   │   │   ├── advanced_sequence.py     # HMM/Copula模型
│   │   │   ├── predictor.py
│   │   │   ├── mamba_predictor.py       # Mamba模型
│   │   │   ├── itransonformer_predictor.py
│   │   │   └── model_version_manager.py
│   │   ├── utils/              # 工具函数
│   │   │   ├── errors.py       # 统一错误处理
│   │   │   ├── logger.py       # 日志管理
│   │   │   ├── resource_manager.py
│   │   │   └── parallel.py
│   │   ├── monitoring/         # 监控模块
│   │   ├── evaluation/         # 评估模块
│   │   ├── training/           # 训练模块
│   │   ├── workflow/           # 工作流编排
│   │   ├── automation/         # 自动化
│   │   ├── policies/           # 策略管理
│   │   ├── cache/              # 缓存管理
│   │   ├── curriculum/         # 课程学习
│   │   ├── knowledge/          # 知识管理
│   │   ├── rl/                 # 强化学习
│   │   └── events/             # 事件总线
│   │
│   ├── agents/                 # Agent系统
│   │   ├── orchestrator.py     # Agent编排器
│   │   ├── base_agent.py       # Agent基类
│   │   ├── data_agent.py       # 数据Agent
│   │   ├── training_agent.py   # 训练Agent
│   │   ├── evaluation_agent.py # 评估Agent
│   │   ├── research_agent.py   # 研究Agent
│   │   ├── optimization_agent.py
│   │   ├── monitor.py          # 免疫系统
│   │   ├── coordination/       # 协作机制
│   │   └── model_registry.py
│   │
│   ├── ai/                     # AI工具系统
│   │   ├── api.py              # API服务
│   │   ├── agents/             # AI Agent
│   │   ├── models/             # 模型管理
│   │   ├── tools/              # 工具系统
│   │   └── memory/             # 记忆系统
│   │
│   └── app/                    # 应用层
│       ├── auto_scheduler_v8.py  # 自动调度器
│       ├── analyze_and_send.py
│       └── email_sender.py
│
├── config/                      # 配置文件
│   ├── model_config.yaml       # 模型配置
│   ├── config.json
│   └── scheduler_config_v8.json
│
├── data/                       # 数据目录
│   ├── raw/                    # 原始数据
│   └── processed/              # 处理后数据
│
├── models/                     # 模型文件
├── results/                    # 预测结果
├── logs/                       # 日志文件
├── docs/                       # 文档
├── scripts/                    # 脚本工具
│   ├── deploy/                 # 部署脚本
│   ├── test/                   # 测试脚本
│   └── utility/                # 工具脚本
├── tests/                      # 测试用例
├── examples/                   # 示例代码
└── frontend/                   # 前端界面
```

---

## 核心架构

### 系统分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      应用层 (App Layer)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ AutoScheduler│  │EmailSender   │  │AnalyzeSend    │      │
│  │     V8       │  │              │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│                    Agent系统层 (Agent Layer)                 │
│  ┌──────────────────────────────────────────────────┐      │
│  │              AgentOrchestrator                     │      │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │      │
│  │  │  Data   │ │Training │ │Evaluation│ │Research│ │      │
│  │  │  Agent  │ │  Agent  │ │  Agent  │ │ Agent │ │      │
│  │  └─────────┘ └─────────┘ └─────────┘ └────────┘ │      │
│  │                     ↓                            │      │
│  │  ┌──────────────────────────────────────────┐  │      │
│  │  │              ImmuneSystem                 │  │      │
│  │  │           (健康监控与自愈)               │  │      │
│  │  └──────────────────────────────────────────┘  │      │
│  └──────────────────────────────────────────────────┘      │
├─────────────────────────────────────────────────────────────┤
│                    核心功能层 (Core Layer)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │   Data   │ │ Features │ │  Models  │ │  Utils   │       │
│  │Collector │ │Engineer  │ │Predictor │ │ Errors   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────┤
│                    模型层 (Model Layer)                     │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │
│  │Stacking│ │  HMM   │ │ Copula │ │  BSTS  │ │ RL/TS  │    │
│  │Ensemble│ │        │ │        │ │        │ │Optimizer│    │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │
├─────────────────────────────────────────────────────────────┤
│                   基础设施层 (Infrastructure)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Config  │ │ Logging  │ │ Monitoring│ │ Cache    │       │
│  │ Manager  │ │ Manager  │ │          │ │ Manager  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 数据流架构

```
数据源 (lecai) 
       ↓
PL5DataCollector (数据采集)
       ↓
DataFrame (原始数据)
       ↓
FeatureEngineer (特征工程) ───→ 76+ 特征
       ↓
EnhancedPL5Predictor (模型训练/预测)
       ↓
多模型融合预测 (Stacking + HMM + Copula + BSTS + RL)
       ↓
预测结果 (Top-8 推荐)
       ↓
EmailSender (邮件发送)
```

---

## 核心模块详解

### 1. 配置管理 (`src/core/config.py`)

#### ModelConfig 类

统一配置管理器，支持YAML配置加载、嵌套键访问、环境变量覆盖。

**主要方法**:

| 方法 | 说明 |
|------|------|
| `load(config_path)` | 从YAML/JSON文件加载配置 |
| `get(key, default)` | 获取嵌套配置值 |
| `get_int/get_float/get_bool` | 类型安全的配置获取 |
| `set(key, value)` | 设置配置值 |
| `stacking_base_config()` | 获取Stacking基础配置 |
| `model_weights()` | 获取模型权重配置 |

**配置结构**:
```yaml
stacking:
  base_config: {n_estimators, max_depth, learning_rate...}
  meta_config: {type, C, cv_folds...}
  model_weights: {stacking, hmm, copula, bayesian}
hmm:
  n_states, n_mixtures, auto_select, criterion
copula:
  type, regularization
bsts:
  trend_window, n_posterior_samples
rl_optimizer:
  state_dim, actor_lr, gamma...
```

### 2. 数据采集 (`src/core/data/collector.py`)

#### PL5DataCollectorV8 类

数据采集器，支持多数据源、错误重试、数据验证。

**主要方法**:

| 方法 | 说明 |
|------|------|
| `update_data()` | 更新数据（网络+本地+备份） |
| `fetch_from_network()` | 从网络获取数据 |
| `load_local_data()` | 加载本地数据 |
| `parse_raw_data()` | 解析原始文本 |
| `get_latest_period()` | 获取最新期号 |

**数据源配置**:
```python
DATA_SOURCES = {
    'lecai': 'http://data.17500.cn/pl5_asc.txt',
    'local': 'data/raw/pl5_history.txt'
}
```

### 3. 特征工程 (`src/core/features/engineer.py`)

#### FeatureEngineer 类

高性能特征工程模块，支持向量化计算、并行处理、特征缓存。

**特征组**:

| 组名 | 说明 | 启用 |
|------|------|------|
| fibonacci | 斐波那契窗口特征 | ✓ |
| markov | 马尔可夫转移概率 | ✓ |
| fourier | 傅里叶变换特征 | ✓ |
| extreme | 极值统计特征 | ✓ |
| pattern | 模式识别特征 | ✓ |
| momentum | 动量特征 | ✓ |
| entropy | 熵特征 | ○ |
| chaos | 混沌理论特征 | ○ |
| garch | GARCH波动率 | ○ |

**主要方法**:

| 方法 | 说明 |
|------|------|
| `extract_all_features(df)` | 提取全部特征 |
| `compute_fibonacci_features()` | 斐波那契特征 |
| `compute_markov_features()` | 马尔可夫特征 |
| `compute_fourier_features()` | 傅里叶特征 |

### 4. 增强预测器 (`src/core/models/enhanced_predictor.py`)

#### EnhancedPL5Predictor 类 (V10.0)

核心预测器，集成多模型融合与强化学习优化。

**子模型组件**:

| 模型 | 权重 | 说明 |
|------|------|------|
| Stacking | 0.40 | Stacking集成 |
| HMM | 0.15 | 隐马尔可夫模型 |
| Copula | 0.25 | 多元Copula |
| Bayesian | 0.20 | 贝叶斯量化器 |

**主要方法**:

| 方法 | 说明 |
|------|------|
| `fit(df, feature_cols)` | 训练模型 |
| `predict(features)` | 预测 |
| `save_models()` | 保存模型 |
| `load_models()` | 加载模型 |
| `update_with_feedback()` | 反馈更新 |

**预测输出结构**:
```python
{
    'wan': {
        'top_k': [3, 7, 1, 9, 2, 5, 0, 8],
        'probabilities': [0.15, 0.12, 0.10, ...],
        'uncertainty': 0.45,
        'weights_used': {'stacking': 0.40, ...}
    },
    'qian': {...},
    ...
}
```

#### StackingEnsemble 类

Stacking集成模型，使用交叉验证生成元特征。

**配置**:
- 基学习器: RandomForest, LightGBM/XGBoost
- 元学习器: LogisticRegression / SGDClassifier
- CV折数: 5

### 5. 高级时序模型 (`src/core/models/advanced_sequence.py`)

#### HiddenMarkovModel 类

真正的隐马尔可夫模型，使用GMM发射概率。

```python
HiddenMarkovModel(
    n_states=4,           # 隐状态数
    n_mixtures=2,        # GMM混合数
    auto_select=False,   # 自动选择最优状态数
    criterion='bic'       # BIC/AIC准则
)
```

#### MultivariateCopula 类

多元Copula联合分布模型。

#### BayesianStructuralTimeSeries 类

贝叶斯结构时间序列模型。

### 6. Agent系统 (`src/agents/`)

#### AgentOrchestrator 类

协调多个Agent的协作，实现完整研发流程。

**执行流程**:
```
Stage 1: 数据采集与处理
    ├── fetch_data (数据获取)
    ├── clean_data (数据清洗)
    └── validate_data (数据验证)
    
Stage 2: 特征工程
Stage 3: 研究分析
Stage 4: 模型训练
Stage 5: 模型评估
Stage 6: 反馈优化
Stage 7: 报告生成
```

#### Agent类型

| Agent | 职责 | 并行度 |
|------|------|--------|
| DataAgent | 数据采集处理 | 8 |
| TrainingAgent | 模型训练优化 | 4 |
| EvaluationAgent | 模型评估反馈 | 4 |
| ResearchAgent | 研究分析 | 4 |
| OptimizationAgent | 策略优化 | 4 |

#### ImmuneSystem 类

免疫系统，监控系统健康并实现自愈。

- 健康检查
- 异常检测
- 自动恢复
- 预警机制

### 7. 自动调度器 (`src/app/auto_scheduler_v8.py`)

#### AutoSchedulerV8 类

定时任务调度器，支持完整流水线执行。

**调度配置** (`config/scheduler_config_v8.json`):
```json
{
    "training_schedule": {
        "enabled": true,
        "trigger_times": ["08:00", "20:00"]
    },
    "prediction_schedule": {
        "enabled": true,
        "trigger_times": ["09:00", "21:00"]
    },
    "report_schedule": {
        "enabled": true,
        "send_after_training": true
    }
}
```

### 8. 错误处理 (`src/core/utils/errors.py`)

#### 错误分类体系

```
PL5BaseError
├── DataError
│   ├── DataLoadError
│   ├── DataValidationError
│   └── DataParseError
├── ModelError
│   ├── ModelLoadError
│   ├── ModelSaveError
│   ├── ModelPredictionError
│   └── ModelTrainingError
├── ConfigError
│   ├── ConfigMissingKeyError
│   └── ConfigValueError
└── NetworkError
    ├── NetworkTimeoutError
    ├── NetworkConnectionError
    └── NetworkHTTPError
```

#### StructuredLogger 类

结构化日志记录器，支持操作追踪和性能监控。

**日志操作类型**:
- `OPERATION_DATA_FETCH`: 数据获取
- `OPERATION_DATA_PARSE`: 数据解析
- `OPERATION_FEATURE_ENGINEERING`: 特征工程
- `OPERATION_PREDICTION`: 预测
- `OPERATION_MODEL_TRAINING`: 模型训练
- `OPERATION_MODEL_SAVE/LOAD`: 模型保存/加载

---

## 关键类与函数速查

### 入口函数 (`main.py`)

```python
def main():
    # CLI命令解析
    # train: 训练流程
    # predict: 预测流程
    # analyze: 分析并发送邮件
    # schedule: 启动调度器
    # status: 查看系统状态
```

### 数据处理流程

```python
# 1. 数据采集
collector = PL5DataCollector()
df = collector.update_data()

# 2. 特征工程
engineer = FeatureEngineer()
df_features = engineer.extract_all_features(df)

# 3. 模型训练
predictor = EnhancedPL5Predictor()
predictor.fit(df_features, feature_cols)

# 4. 预测
predictions = predictor.predict(latest_features, recent_data, top_k=8)

# 5. 保存模型
predictor.save_models()
```

### Agent执行流程

```python
orchestrator = AgentOrchestrator()
result = await orchestrator.execute_full_pipeline()
# 返回: {success, execution_time, results, timestamp}
```

---

## 依赖关系图

```
                    ┌─────────────────┐
                    │   main.py       │
                    └────────┬────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                    src/app/                                 │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ AutoSchedulerV8  │  │ analyze_and_send │                 │
│  └────────┬─────────┘  └────────┬─────────┘                 │
└───────────┼─────────────────────┼───────────────────────────┘
            │                     │
            ▼                     ▼
┌──────────────────────────────────────────────────────────────┐
│                    src/agents/                               │
│  ┌──────────────────────┐  ┌──────────────────────┐         │
│  │  AgentOrchestrator   │  │   ImmuneSystem       │         │
│  └──────────┬───────────┘  └──────────────────────┘         │
│             │                                                     │
│  ┌──────────┼───────────┬───────────┬───────────┐              │
│  ▼          ▼           ▼           ▼           ▼              │
│ Data   Training   Evaluation   Research   Optimization         │
│ Agent   Agent       Agent       Agent       Agent             │
└──────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────┐
│                    src/core/                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐              │
│  │    Data    │  │  Features  │  │   Models   │              │
│  │  Collector │  │  Engineer  │  │ Predictor  │              │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘              │
│        │               │               │                       │
│        ▼               ▼               ▼                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐       │
│  │ Validator  │  │ Selector   │  │AdvancedSequence    │       │
│  │            │  │            │  │HMM/Copula/BSTS     │       │
│  └────────────┘  └────────────┘  └─────────┬──────────┘       │
│                                             │                  │
└─────────────────────────────────────────────┼──────────────────┘
                                              │
┌─────────────────────────────────────────────┼──────────────────┐
│                    src/core/utils/          ▼                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐       │
│  │   Errors   │  │  Logger    │  │ ResourceManager   │       │
│  └────────────┘  └────────────┘  └────────────────────┘       │
│  ┌────────────┐  ┌────────────┐                               │
│  │   Cache    │  │  Parallel  │                               │
│  └────────────┘  └────────────┘                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 运行方式

### 命令行使用

```bash
# 训练
python main.py train

# 预测
python main.py predict

# 分析并发送邮件
python main.py analyze

# 启动调度器
python main.py schedule

# 单次完整流程
python main.py schedule --once

# 查看状态
python main.py status
```

### Python API使用

```python
from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.enhanced_predictor import EnhancedPL5Predictor

# 完整流程
collector = PL5DataCollector()
df = collector.update_data()

engineer = FeatureEngineer()
df_features = engineer.extract_all_features(df)
feature_cols = [c for c in df_features.columns if c not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]

predictor = EnhancedPL5Predictor()
predictor.fit(df_features, feature_cols)
predictions = predictor.predict(df_features[feature_cols].iloc[-1].values, recent_data)

# 保存/加载
predictor.save_models()
predictor.load_models()
```

### 异步使用

```python
import asyncio
from pl5_intelligent_system import PL5IntelligentSystem

async def main():
    system = PL5IntelligentSystem()
    await system.start()
    result = await system.execute_full_pipeline()
    await system.stop()

asyncio.run(main())
```

---

## 配置文件说明

### model_config.yaml

```yaml
stacking:
  base_config:
    n_estimators: 5      # 基学习器数量
    max_depth: 10       # 树最大深度
    learning_rate: 0.06   # 学习率
  
  meta_config:
    cv_folds: 2          # 交叉验证折数
    auto_select: false    # 自动选择元学习器

  model_weights:
    stacking: 0.40       # Stacking权重
    hmm: 0.15           # HMM权重
    copula: 0.25        # Copula权重
    bayesian: 0.20       # 贝叶斯权重

hmm:
  n_states: 4           # 隐状态数
  auto_select: false    # 自动选择

rl_optimizer:
  state_dim: 128        # RL状态维度
  gamma: 0.95           # 折扣因子
```

### scheduler_config_v8.json

```json
{
    "training_schedule": {
        "enabled": true,
        "trigger_times": ["08:00", "20:00"]
    },
    "prediction_schedule": {
        "enabled": true,
        "trigger_times": ["09:00", "21:00"]
    },
    "dead_zone": {
        "enabled": true,
        "start_hour": 22,
        "end_hour": 8
    }
}
```

---

## 环境要求

### Python版本
- Python 3.8+

### 核心依赖

```
pandas>=1.3.0
numpy>=1.20.0
scikit-learn>=0.24.0
scipy>=1.7.0
```

### 可选依赖

```
lightgbm>=3.0.0     # 加速Stacking
xgboost>=1.5.0      # 加速Stacking
joblib>=1.0.0       # 并行计算
pyyaml>=5.4.0       # 配置加载
requests>=2.25.0     # 网络请求
```

### 邮件依赖

```
# Windows (推荐)
pywin32>=300

# 跨平台
aiosmtpd>=1.4.0
```

---

## 目录规范

| 目录 | 用途 | 生命周期 |
|------|------|----------|
| `data/raw/` | 原始数据 | 持久 |
| `data/processed/` | 处理后数据 | 自动生成 |
| `models/` | 模型文件 | 持久 |
| `models/cache/` | 特征缓存 | 临时 |
| `models/model_backups/` | 模型备份 | 定期清理 |
| `results/` | 预测结果 | 持久 |
| `logs/` | 日志文件 | 定期清理 |
| `config/` | 配置文件 | 持久 |

---

## 开发指南

### 添加新特征组

1. 在 `FeatureEngineer` 类中添加方法:
```python
def compute_custom_features(self, df):
    # 实现特征计算逻辑
    return df
```

2. 在 `extract_all_features()` 中注册:
```python
if self.config.get('custom', {}).get('enabled'):
    df = self.compute_custom_features(df)
```

### 添加新模型

1. 在 `src/core/models/` 创建模型类
2. 在 `EnhancedPL5Predictor` 中集成
3. 更新 `model_weights()` 配置
4. 更新预测融合逻辑

### 添加新Agent

1. 继承 `BaseAgent` 类
2. 实现 `run_task()` 方法
3. 在 `AgentOrchestrator._init_agents()` 中注册

---

## 注意事项

1. **特征维度一致性**: 训练和预测时必须使用相同的特征列
2. **数据缓存**: 长时间运行后注意清理缓存避免内存溢出
3. **模型版本**: 定期备份模型，版本更新后验证兼容性
4. **调度时间**: 避开开奖后数据更新高峰时段
5. **邮件配置**: 确保SMTP配置正确，避免被识别为垃圾邮件

---

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| V10.3 | 2026-05 | 当前稳定版，多模型融合优化 |
| V10.0 | 2026-04 | 引入强化学习优化器 |
| V9.0 | 2026-03 | 基础Stacking集成 |
| V8.0 | 2026-02 | 错误处理增强 |

---

## 联系方式

如有问题，请查看:
- `docs/DOCUMENTATION_INDEX.md` - 文档索引
- `logs/` - 运行日志
- `results/latest_prediction.json` - 最新预测结果
