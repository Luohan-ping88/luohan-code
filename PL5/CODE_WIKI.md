# PL5 预测系统 Code Wiki

## 1. 项目概述

PL5 是一个智能预测系统，采用先进的人工智能技术实现精准预测。系统支持多种预测模式，包括增量训练、深度训练、售前预测等核心功能。

### 1.1 核心特性

- **多模式预测引擎**：支持 V10、V11_advanced、V11_full 三种预测模式
- **自动化调度**：基于时间规则的自动化任务调度系统
- **特征工程**：先进的特征提取和选择机制
- **模型集成**：多模型融合的预测策略
- **容错机制**：完善的错误处理和恢复机制
- **邮件通知**：预测结果自动邮件推送

---

## 2. 整体架构

### 2.1 架构分层

```
┌─────────────────────────────────────────────────────┐
│                    表示层 (UI)                        │
│         frontend/ | API endpoints                     │
├─────────────────────────────────────────────────────┤
│                    应用层 (App)                       │
│    auto_scheduler_v8.py | email_sender.py           │
├─────────────────────────────────────────────────────┤
│                    核心层 (Core)                      │
│  features/ | models/ | evaluation/ | monitoring/   │
├─────────────────────────────────────────────────────┤
│                    智能层 (AI/Agents)                 │
│    agents/ | ai/ | knowledge/ | rl/                 │
├─────────────────────────────────────────────────────┤
│                    工具层 (Tools)                      │
│      tools/ | utils/ | infrastructure/             │
└─────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
数据源 → 数据收集 → 特征工程 → 模型训练 → 预测输出
           ↓           ↓          ↓          ↓
      collector.py  engineer.py predictor.py email_sender.py
```

---

## 3. 目录结构

```
PL5/
├── main.py                          # 系统入口
├── requirements.txt                 # 依赖清单
├── config/                          # 配置文件目录
│   ├── scheduler_config_v8.json     # 调度器配置
│   ├── model_config_v2.yaml         # 模型配置
│   └── system_config.json           # 系统配置
├── src/                             # 源代码目录
│   ├── app/                         # 应用层
│   │   ├── auto_scheduler_v8.py   # 自动化调度器V8
│   │   └── email_sender.py         # 邮件发送器
│   ├── core/                        # 核心功能层
│   │   ├── features/               # 特征工程模块
│   │   ├── models/                 # 预测模型模块
│   │   ├── evaluation/             # 模型评估模块
│   │   ├── monitoring/             # 系统监控模块
│   │   ├── automation/             # 自动化模块
│   │   ├── workflow/               # 工作流模块
│   │   ├── data/                   # 数据处理模块
│   │   ├── email/                  # 邮件模块
│   │   ├── cache/                  # 缓存模块
│   │   ├── backup/                 # 备份模块
│   │   ├── recovery/               # 恢复模块
│   │   ├── policies/                # 策略模块
│   │   ├── curriculum/             # 课程学习模块
│   │   ├── rl/                     # 强化学习模块
│   │   ├── knowledge/              # 知识库模块
│   │   └── utils/                  # 工具函数
│   ├── agents/                      # 智能体层
│   │   ├── training_agent.py       # 训练智能体
│   │   ├── evaluation_agent.py      # 评估智能体
│   │   ├── optimization_agent.py   # 优化智能体
│   │   ├── data_agent.py           # 数据智能体
│   │   ├── research_agent.py       # 研究智能体
│   │   ├── orchestrator.py         # 编排器
│   │   └── coordination/           # 协作模块
│   ├── ai/                         # AI系统
│   │   ├── agents/                 # AI代理
│   │   ├── memory/                 # 记忆系统
│   │   ├── models/                 # 模型管理
│   │   └── tools/                  # AI工具
│   ├── tools/                      # 工具层
│   │   ├── core_tools.py          # 核心工具
│   │   ├── application_tools.py   # 应用工具
│   │   └── infrastructure.py       # 基础设施工具
│   └── models/                     # 模型存储
├── scripts/                         # 脚本目录
│   ├── deploy/                     # 部署脚本
│   ├── utility/                    # 实用工具
│   └── test/                       # 测试脚本
├── tests/                          # 测试目录
├── logs/                           # 日志目录
├── models/                         # 模型文件目录
│   ├── feature_versions/           # 特征版本历史
│   └── model_backups/              # 模型备份
└── docs/                          # 文档目录
```

---

## 4. 主要模块详解

### 4.1 特征工程模块 (src/core/features/)

**职责**：数据预处理、特征提取、特征选择、特征版本管理

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [v11_engineer.py](file:///workspace/PL5/src/core/features/v11_engineer.py) | V11先进特征工程 | `V11FeatureEngineer`, `create_feature_engineer()` |
| [engineer.py](file:///workspace/PL5/src/core/features/engineer.py) | 标准特征工程 | `FeatureEngineer` |
| [engineer_v10.py](file:///workspace/PL5/src/core/features/engineer_v10.py) | V10特征工程 | `V10FeatureEngineer` |
| [advanced_features.py](file:///workspace/PL5/src/core/features/advanced_features.py) | 高级特征提取 | `AdvancedFeatureEngineering` |
| [comprehensive_features.py](file:///workspace/PL5/src/core/features/comprehensive_features.py) | 综合特征提取 | `ComprehensiveFeatureExtractor` |
| [deep_features.py](file:///workspace/PL5/src/core/features/deep_features.py) | 深度学习特征 | `DeepFeatureExtractor` |
| [feature_config_manager.py](file:///workspace/PL5/src/core/features/feature_config_manager.py) | 配置管理 | `FeatureConfigManager`, `FeatureConfig` |
| [feature_version_manager.py](file:///workspace/PL5/src/core/features/feature_version_manager.py) | 版本管理 | `FeatureVersionManager` |
| [feature_selector.py](file:///workspace/PL5/src/core/features/feature_selector.py) | 特征选择 | `FeatureSelector` |
| [adaptive_selector.py](file:///workspace/PL5/src/core/features/adaptive_selector.py) | 自适应选择 | `AdaptiveFeatureSelector` |
| [interaction_extractor.py](file:///workspace/PL5/src/core/features/interaction_extractor.py) | 交互特征 | `InteractionExtractor` |
| [dynamic_validator.py](file:///workspace/PL5/src/core/features/dynamic_validator.py) | 动态验证 | `DynamicFeatureValidator` |

**V11FeatureEngineer 类**：

```python
class V11FeatureEngineer:
    """V11先进特征工程类"""
    
    def __init__(self, mode='v11_advanced'):
        """初始化
        - mode: 'v10', 'v11_advanced', 'v11_full'
        """
        
    def create_features(self, data):
        """创建特征
        - 返回: 包含新特征的DataFrame
        """
        
    def select_features(self, X, y):
        """特征选择
        - X: 特征矩阵
        - y: 目标变量
        - 返回: 选中的特征列表
        """
        
    def get_feature_summary(self):
        """获取特征摘要"""
```

---

### 4.2 模型模块 (src/core/models/)

**职责**：预测模型训练、模型评估、模型版本管理

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [predictor.py](file:///workspace/PL5/src/core/models/predictor.py) | 基础预测器 | `Predictor` |
| [v11_predictor.py](file:///workspace/PL5/src/core/models/v11_predictor.py) | V11预测器 | `V11Predictor` |
| [enhanced_predictor.py](file:///workspace/PL5/src/core/models/enhanced_predictor.py) | 增强预测器 | `EnhancedPredictor` |
| [optimized_predictor.py](file:///workspace/PL5/src/core/models/optimized_predictor.py) | 优化预测器 | `OptimizedPredictor` |
| [model_evaluator.py](file:///workspace/PL5/src/core/models/model_evaluator.py) | 模型评估 | `ModelEvaluator` |
| [model_version_manager.py](file:///workspace/PL5/src/core/models/model_version_manager.py) | 版本管理 | `ModelVersionManager` |
| [enhanced_stacking.py](file:///workspace/PL5/src/core/models/enhanced_stacking.py) | 堆叠集成 | `EnhancedStacking` |
| [multi_feature_fusion.py](file:///workspace/PL5/src/core/models/multi_feature_fusion.py) | 特征融合 | `MultiFeatureFusion` |
| [bayesian_uncertainty.py](file:///workspace/PL5/src/core/models/bayesian_uncertainty.py) | 贝叶斯不确定性 | `BayesianUncertainty` |
| [context_weight_fusion.py](file:///workspace/PL5/src/core/models/context_weight_fusion.py) | 上下文融合 | `ContextWeightFusion` |
| [incremental_learning.py](file:///workspace/PL5/src/core/models/incremental_learning.py) | 增量学习 | `IncrementalLearning` |

**Predictor 基类**：

```python
class Predictor:
    """预测器基类"""
    
    def __init__(self, config=None):
        """初始化预测器"""
        
    def train(self, X, y):
        """训练模型
        - X: 训练特征
        - y: 训练标签
        """
        
    def predict(self, X):
        """预测
        - X: 待预测特征
        - 返回: 预测结果
        """
        
    def evaluate(self, X_test, y_test):
        """评估模型
        - 返回: 评估指标字典
        """
        
    def save(self, path):
        """保存模型"""
        
    def load(self, path):
        """加载模型"""
```

---

### 4.3 调度器模块 (src/app/)

**职责**：自动化任务调度、任务执行协调

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [auto_scheduler_v8.py](file:///workspace/PL5/src/app/auto_scheduler_v8.py) | V8调度器 | `AutoSchedulerV8` |
| [email_sender.py](file:///workspace/PL5/src/app/email_sender.py) | 邮件发送 | `EmailSender` |
| [intelligent_scheduler_integration.py](file:///workspace/PL5/src/app/intelligent_scheduler_integration.py) | 智能调度集成 | `IntelligentScheduler` |

**AutoSchedulerV8 类**：

```python
class AutoSchedulerV8:
    """V8版本自动调度器"""
    
    def __init__(self, config_path=None):
        """初始化调度器"""
        
    def start(self):
        """启动调度器"""
        
    def stop(self):
        """停止调度器"""
        
    # 核心任务方法
    def task_incremental_train(self):
        """增量训练任务"""
        
    def task_train(self):
        """深度训练任务"""
        
    def task_final_prediction(self):
        """最终预测任务"""
        
    def task_pre_sale_prediction(self):
        """售前预测任务"""
        
    def task_prediction_preview(self):
        """预测预览任务"""
        
    # V11支持
    def _is_v11_enabled(self):
        """检查V11模式是否启用"""
        
    def _get_v11_feature_mode(self):
        """获取V11特征工程模式"""
```

---

### 4.4 评估模块 (src/core/evaluation/)

**职责**：模型性能评估、历史记录管理

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [evaluator.py](file:///workspace/PL5/src/core/evaluation/evaluator.py) | 模型评估 | `Evaluator` |

**Evaluator 类**：

```python
class Evaluator:
    """模型评估器"""
    
    def __init__(self):
        """初始化评估器"""
        
    def evaluate(self, model, X_test, y_test):
        """评估模型性能
        - 返回: 包含各种指标的字典
        """
        
    def save_evaluation(self, results):
        """保存评估结果到历史记录"""
        
    def get_evaluation_history(self):
        """获取评估历史"""
```

---

### 4.5 监控模块 (src/core/monitoring/)

**职责**：系统健康监控、性能监控、告警管理

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [performance_monitor.py](file:///workspace/PL5/src/core/monitoring/performance_monitor.py) | 性能监控 | `PerformanceMonitor`, `track_performance` |
| [health_monitor.py](file:///workspace/PL5/src/core/monitoring/health_monitor.py) | 健康监控 | `HealthMonitor` |
| [health_check.py](file:///workspace/PL5/src/core/monitoring/health_check.py) | 健康检查 | `HealthCheck` |
| [alerting.py](file:///workspace/PL5/src/core/monitoring/alerting.py) | 告警系统 | `AlertingSystem` |
| [bottleneck_detector.py](file:///workspace/PL5/src/core/monitoring/bottleneck_detector.py) | 瓶颈检测 | `BottleneckDetector` |

**PerformanceMonitor 类**：

```python
class PerformanceMonitor:
    """性能监控器"""
    
    def start_monitoring(self):
        """开始监控"""
        
    def stop_monitoring(self):
        """停止监控"""
        
    def get_metrics(self):
        """获取性能指标"""
        
    def detect_anomalies(self):
        """检测异常"""
```

---

### 4.6 智能体模块 (src/agents/)

**职责**：任务自动化执行、模型优化协调

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [training_agent.py](file:///workspace/PL5/src/agents/training_agent.py) | 训练智能体 | `TrainingAgent` |
| [evaluation_agent.py](file:///workspace/PL5/src/agents/evaluation_agent.py) | 评估智能体 | `EvaluationAgent` |
| [optimization_agent.py](file:///workspace/PL5/src/agents/optimization_agent.py) | 优化智能体 | `OptimizationAgent` |
| [data_agent.py](file:///workspace/PL5/src/agents/data_agent.py) | 数据智能体 | `DataAgent` |
| [research_agent.py](file:///workspace/PL5/src/agents/research_agent.py) | 研究智能体 | `ResearchAgent` |
| [orchestrator.py](file:///workspace/PL5/src/agents/orchestrator.py) | 任务编排 | `AgentOrchestrator` |
| [base_agent.py](file:///workspace/PL5/src/agents/base_agent.py) | 基础智能体 | `BaseAgent` |

**AgentOrchestrator 类**：

```python
class AgentOrchestrator:
    """智能体编排器"""
    
    def __init__(self):
        """初始化编排器"""
        self.agents = {}
        
    def register_agent(self, name, agent):
        """注册智能体"""
        
    def execute_task(self, task):
        """执行任务"""
        
    def coordinate(self, tasks):
        """协调多个任务"""
```

---

### 4.7 数据模块 (src/core/data/)

**职责**：数据收集、验证、增强

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [collector.py](file:///workspace/PL5/src/core/data/collector.py) | 数据收集 | `DataCollector` |
| [validator.py](file:///workspace/PL5/src/core/data/validator.py) | 数据验证 | `DataValidator` |
| [augmentation.py](file:///workspace/PL5/src/core/data/augmentation.py) | 数据增强 | `DataAugmentation` |
| [config.py](file:///workspace/PL5/src/core/data/config.py) | 数据配置 | `DataConfig` |

---

### 4.8 工作流模块 (src/core/workflow/)

**职责**：任务编排、依赖管理、智能调度

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [orchestrator.py](file:///workspace/PL5/src/core/workflow/orchestrator.py) | 工作流编排 | `WorkflowOrchestrator` |
| [task_dependency_manager.py](file:///workspace/PL5/src/core/workflow/task_dependency_manager.py) | 依赖管理 | `TaskDependencyManager` |
| [intelligent_time_scheduler.py](file:///workspace/PL5/src/core/workflow/intelligent_time_scheduler.py) | 智能调度 | `IntelligentTimeScheduler` |

---

### 4.9 自动化模块 (src/core/automation/)

**职责**：自动化规则管理、调度执行

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [manager.py](file:///workspace/PL5/src/core/automation/manager.py) | 自动化管理 | `AutomationManager` |
| [scheduler.py](file:///workspace/PL5/src/core/automation/scheduler.py) | 调度器 | `AutomationScheduler` |

---

### 4.10 工具模块 (src/core/utils/)

**职责**：通用工具函数、错误处理、日志管理

**核心文件**：

| 文件 | 功能 | 关键类/函数 |
|------|------|------------|
| [logger.py](file:///workspace/PL5/src/core/utils/logger.py) | 日志管理 | `Logger`, `get_logger()` |
| [error_handler.py](file:///workspace/PL5/src/core/utils/error_handler.py) | 错误处理 | `ErrorHandler` |
| [errors.py](file:///workspace/PL5/src/core/utils/errors.py) | 错误定义 | 自定义异常类 |
| [log_manager.py](file:///workspace/PL5/src/core/utils/log_manager.py) | 日志管理 | `LogManager` |
| [unified_error_handler.py](file:///workspace/PL5/src/core/utils/unified_error_handler.py) | 统一错误处理 | `UnifiedErrorHandler` |
| [parallel.py](file:///workspace/PL5/src/core/utils/parallel.py) | 并行处理 | `ParallelExecutor` |
| [resource_manager.py](file:///workspace/PL5/src/core/utils/resource_manager.py) | 资源管理 | `ResourceManager` |

---

## 5. 关键类与函数

### 5.1 系统入口 (main.py)

```python
# 训练命令
python main.py train [--v11] [--v11-mode MODE]

# 预测命令  
python main.py predict [--v11] [--output OUTPUT]

# 评估命令
python main.py evaluate
```

### 5.2 核心函数

#### 特征工程

| 函数 | 位置 | 功能 |
|------|------|------|
| `create_feature_engineer()` | [v11_engineer.py](file:///workspace/PL5/src/core/features/v11_engineer.py) | 工厂函数，创建特征工程师 |
| `get_feature_config_manager()` | [feature_config_manager.py](file:///workspace/PL5/src/core/features/feature_config_manager.py) | 获取特征配置管理器 |

#### 模型操作

| 函数 | 位置 | 功能 |
|------|------|------|
| `train_model()` | [predictor.py](file:///workspace/PL5/src/core/models/predictor.py) | 训练模型 |
| `load_model()` | [predictor.py](file:///workspace/PL5/src/core/models/predictor.py) | 加载模型 |
| `predict()` | [predictor.py](file:///workspace/PL5/src/core/models/predictor.py) | 执行预测 |

#### 调度器

| 函数 | 位置 | 功能 |
|------|------|------|
| `start_scheduler()` | [auto_scheduler_v8.py](file:///workspace/PL5/src/app/auto_scheduler_v8.py) | 启动调度器 |
| `run_task()` | [auto_scheduler_v8.py](file:///workspace/PL5/src/app/auto_scheduler_v8.py) | 执行指定任务 |

---

## 6. 依赖关系

### 6.1 核心依赖

```
# requirements.txt

# 核心依赖
numpy==1.26.2          # 数值计算
pandas==2.1.4          # 数据处理
scikit-learn==1.3.2    # 机器学习

# Web框架
fastapi==0.104.1       # API框架
uvicorn==0.24.0        # ASGI服务器

# AI/模型
openai==1.3.5          # OpenAI API
llama-cpp-python==0.2.43  # 本地LLM
lightgbm==4.1.0        # 梯度提升
xgboost==2.0.3         # XGBoost

# 工具库
python-dotenv==1.0.0   # 环境变量
requests==2.31.0       # HTTP请求
beautifulsoup4==4.12.2 # 网页解析
lxml==4.9.3            # XML处理

# 测试
pytest==9.0.2          # 单元测试
pytest-asyncio==0.21.1 # 异步测试
allure-pytest==2.13.2  # 测试报告

# 开发工具
black==23.11.0         # 代码格式化
flake8==6.1.0          # 代码检查

# 可选依赖
torch==2.1.0           # PyTorch（用于RL模块）
torchvision==0.16.0
torchaudio==2.1.0
```

### 6.2 模块依赖图

```
main.py
  └── auto_scheduler_v8.py
        ├── FeatureEngineer (engineer.py)
        │     ├── V11FeatureEngineer (v11_engineer.py)
        │     └── FeatureConfigManager (feature_config_manager.py)
        ├── Predictor (predictor.py)
        │     └── V11Predictor (v11_predictor.py)
        ├── Evaluator (evaluation/evaluator.py)
        └── EmailSender (email_sender.py)

tools/
  └── core_tools.py
        ├── DataCollector (data/collector.py)
        └── Logger (utils/logger.py)
```

---

## 7. 配置说明

### 7.1 调度器配置 (config/scheduler_config_v8.json)

```json
{
  "schedule": {
    "incremental_training": "0 1 * * *",
    "deep_training": "0 3 * * 0",
    "final_prediction": "0 6 * * *",
    "pre_sale_prediction": "0 18 * * *"
  },
  "v11_mode": {
    "enabled": false,
    "feature_mode": "v11_advanced"
  },
  "monitoring": {
    "enabled": true,
    "interval": 300
  },
  "email": {
    "enabled": true,
    "on_success": true,
    "on_failure": true
  }
}
```

### 7.2 模型配置 (config/model_config_v2.yaml)

```yaml
models:
  predictor:
    type: "ensemble"
    ensemble_method: "stacking"
    base_models:
      - lightgbm
      - xgboost
      - catboost
    
  training:
    early_stopping: true
    patience: 10
    learning_rate: 0.05
    n_estimators: 1000
    
  features:
    v11_advanced:
      max_features: 400
      selection_method: "importance"
    v11_full:
      max_features: 500
      selection_method: "genetic"
```

### 7.3 系统配置 (config/system_config.json)

```json
{
  "system": {
    "log_level": "INFO",
    "data_dir": "./data",
    "model_dir": "./models",
    "backup_enabled": true
  },
  "features": {
    "cache_enabled": true,
    "versioning": true
  }
}
```

---

## 8. 运行方式

### 8.1 环境准备

```bash
# 1. 克隆项目
git clone <repository_url>
cd PL5

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 快速安装核心依赖
python scripts/quick_install_core.py
```

### 8.2 基本运行

```bash
# 训练模型
python main.py train

# 使用V11模式训练
python main.py train --v11 --v11-mode v11_advanced

# 执行预测
python main.py predict

# 使用V11模式预测
python main.py predict --v11

# 评估模型
python main.py evaluate
```

### 8.3 调度器运行

```bash
# 启动调度器（后台运行）
python main.py scheduler &

# 停止调度器
python main.py scheduler --stop

# 查看调度器状态
python main.py scheduler --status
```

### 8.4 诊断工具

```bash
# 系统诊断
python scripts/system_diagnostic.py

# V11集成测试
python scripts/test_v11_full_integration.py

# 烟雾测试
python scripts/smoke_test_v80.py

# 完整部署验证
python scripts/deploy/test_deployment.py
```

### 8.5 Windows特定

```bash
# 使用启动脚本
start.bat          # 启动系统
start_daemon.bat   # 启动守护进程

# 使用服务安装
install_dependencies.bat  # 安装依赖
setup_windows_service.bat # 安装Windows服务
```

---

## 9. 扩展指南

### 9.1 添加新的特征工程方法

1. 在 `src/core/features/` 创建新文件
2. 继承 `BaseFeatureExtractor` 类
3. 实现 `extract()` 方法
4. 在 `__init__.py` 中导出

```python
# src/core/features/my_features.py
from .base import BaseFeatureExtractor

class MyFeatureExtractor(BaseFeatureExtractor):
    def extract(self, data):
        # 实现特征提取逻辑
        return extracted_features
```

### 9.2 添加新的预测模型

1. 在 `src/core/models/` 创建新文件
2. 继承 `Predictor` 基类
3. 实现必要的方法
4. 在模型注册表中注册

```python
# src/core/models/my_predictor.py
from .predictor import Predictor

class MyPredictor(Predictor):
    def __init__(self, config=None):
        super().__init__(config)
        
    def _build_model(self):
        # 构建模型逻辑
        pass
```

### 9.3 添加新的调度任务

1. 在 `AutoSchedulerV8` 类中添加任务方法
2. 在配置文件中添加任务规则
3. 注册任务钩子

```python
def task_my_custom_task(self):
    """自定义任务"""
    self.logger.info("执行自定义任务")
    # 任务逻辑
```

---

## 10. 最佳实践

### 10.1 代码组织

- 保持模块独立性
- 使用依赖注入提高可测试性
- 遵循单一职责原则
- 编写清晰的文档字符串

### 10.2 错误处理

- 使用统一的错误处理机制
- 记录详细的错误日志
- 实现优雅的降级策略
- 提供用户友好的错误信息

### 10.3 性能优化

- 使用缓存减少重复计算
- 并行处理独立任务
- 懒加载非必要资源
- 监控关键性能指标

### 10.4 测试

- 为核心功能编写单元测试
- 集成测试验证模块交互
- 端到端测试验证完整流程
- 性能测试确保系统响应

---

## 11. 故障排除

### 11.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 导入错误 | 依赖未安装 | 运行 `pip install -r requirements.txt` |
| 模型加载失败 | 模型文件损坏 | 重新训练或恢复备份 |
| 调度器不运行 | 配置文件错误 | 检查 `scheduler_config_v8.json` |
| 邮件发送失败 | SMTP配置错误 | 验证 `email_config.json` |

### 11.2 日志查看

```bash
# 查看调度器日志
tail -f logs/scheduler.log

# 查看性能日志
tail -f performance.log

# 查看崩溃日志
cat crash.log

# 系统健康检查
python run_health_check.py
```

### 11.3 备份与恢复

```bash
# 创建备份
python scripts/utility/auto_backup.py

# 恢复备份
python scripts/utility/restore_backup.py --backup <backup_file>
```

---

## 12. 版本说明

### 12.1 V11特性

- **v11_advanced**：400+特征，适合日常使用
- **v11_full**：500+特征，适合研究开发
- **向后兼容**：完整支持V10模式

### 12.2 V8调度器特性

- 增强的错误处理
- V11模式集成
- 智能重试机制
- 详细的执行日志

---

## 13. 联系方式与支持

- **文档目录**：`docs/`
- **测试脚本**：`scripts/`
- **部署指南**：`docs/deployment/`
- **架构文档**：`docs/architecture/`

---

*本文档由 PL5 系统自动生成，最后更新于 2026-05-21*
