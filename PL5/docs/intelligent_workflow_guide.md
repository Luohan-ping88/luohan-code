# IntelligentWorkflowOrchestrator 使用指南

## 概述

IntelligentWorkflowOrchestrator 是一个智能工作流编排器，用于管理和调度 PL5 系统中的自动化任务流程。它提供了任务状态跟踪、依赖管理、智能调度和错误恢复等功能。

## 功能特性

- **任务状态管理**：实时跟踪任务执行状态（待处理、进行中、已完成、失败）
- **依赖管理**：自动处理任务间的依赖关系
- **智能时间调度**：检测可提前执行的任务和错过的任务补执行
- **状态持久化**：自动保存和加载工作流状态
- **错误恢复**：支持任务失败重试机制
- **配置灵活**：通过 JSON 配置文件自定义工作流行为

## 配置说明

### 配置文件位置

配置文件位于：`config/workflow_config.json`

### 配置选项

```json
{
  "enabled": true,
  "time_window": {
    "start": "00:00",
    "end": "17:30"
  },
  "retry": {
    "max_retries": 3,
    "base_delay": 1,
    "max_delay": 60,
    "backoff_factor": 2
  },
  "intelligent_scheduling": {
    "enabled": true,
    "check_interval": 60,
    "early_execution_enabled": true,
    "missed_task_catchup_enabled": true
  },
  "state": {
    "persistence_enabled": true,
    "state_file_path": "logs/workflow_state.pkl"
  },
  "tasks": {
    "data_fetch": {
      "enabled": true,
      "priority": 1
    },
    "evaluation": {
      "enabled": true,
      "priority": 2
    },
    "optimization": {
      "enabled": true,
      "priority": 3
    },
    "training": {
      "enabled": true,
      "priority": 4
    },
    "send_report": {
      "enabled": true,
      "priority": 5
    }
  }
}
```

### 配置项详解

#### 基础配置
- `enabled`: 布尔值，是否启用智能工作流编排器
- `time_window`: 对象，定义工作流执行的时间窗口
  - `start`: 时间窗口开始时间（HH:MM 格式）
  - `end`: 时间窗口结束时间（HH:MM 格式）

#### 重试配置
- `retry`: 对象，任务失败重试配置
  - `max_retries`: 最大重试次数
  - `base_delay`: 基础延迟时间（秒）
  - `max_delay`: 最大延迟时间（秒）
  - `backoff_factor`: 退避因子，用于指数退避计算

#### 智能调度配置
- `intelligent_scheduling`: 对象，智能调度功能配置
  - `enabled`: 是否启用智能调度
  - `check_interval`: 检查间隔（秒）
  - `early_execution_enabled`: 是否启用提前执行检测
  - `missed_task_catchup_enabled`: 是否启用错过任务补执行

#### 状态持久化配置
- `state`: 对象，状态持久化配置
  - `persistence_enabled`: 是否启用状态持久化
  - `state_file_path`: 状态文件保存路径

#### 任务配置
- `tasks`: 对象，各个任务的配置
  - `enabled`: 任务是否启用
  - `priority`: 任务优先级

## 使用方法

### 启用智能工作流

1. 编辑 `config/workflow_config.json` 文件
2. 将 `enabled` 设置为 `true`
3. 重启 AutoSchedulerV8

### 禁用智能工作流

1. 编辑 `config/workflow_config.json` 文件
2. 将 `enabled` 设置为 `false`
3. 重启 AutoSchedulerV8

### 查看工作流状态

通过 `get_task_monitoring_data()` 方法获取工作流状态信息：

```python
scheduler = AutoSchedulerV8()
monitoring_data = scheduler.get_task_monitoring_data()
print(monitoring_data)
```

返回数据包含：
- `workflow_enabled`: 工作流是否启用
- `workflow_state`: 工作流详细状态（如果启用）

### 手动重置工作流

如果需要重置工作流状态，可以通过以下方式：

```python
from src.core.workflow import IntelligentWorkflowOrchestrator

orchestrator = IntelligentWorkflowOrchestrator()
orchestrator.reset_workflow()
```

## 任务流程

系统包含以下任务，按顺序执行：

1. **data_fetch** - 自动获取开奖数据
2. **evaluation** - 评估预测逻辑与命中情况
3. **optimization** - 推理逻辑策略优化学习
4. **training** - 深度学习训练
5. **send_report** - 发送训练报告

## 依赖关系

任务间的依赖关系如下：
- `evaluation` 依赖 `data_fetch`
- `optimization` 依赖 `evaluation`
- `training` 依赖 `optimization`
- `send_report` 依赖 `training`

## 状态说明

### 工作流状态

- `idle`: 空闲状态
- `running`: 运行中
- `paused`: 暂停
- `completed`: 已完成
- `failed`: 失败

### 任务状态

- `pending`: 待处理
- `in_progress`: 进行中
- `completed`: 已完成
- `failed`: 失败

## 日志说明

智能工作流编排器会在系统日志中输出以下信息：

- `[WorkflowOrchestrator]` 前缀的日志表示工作流相关操作
- `[智能调度]` 前缀的日志表示智能调度检测结果

## 常见问题

### Q: 如何修改时间窗口？
A: 编辑 `config/workflow_config.json` 中的 `time_window` 配置项，修改 `start` 和 `end` 时间。

### Q: 任务失败后会自动重试吗？
A: 是的，系统会根据 `retry` 配置自动重试失败的任务，直到达到最大重试次数。

### Q: 如何查看工作流状态？
A: 使用 `--monitor` 命令行参数或调用 `get_task_monitoring_data()` 方法。

### Q: 状态文件损坏怎么办？
A: 删除 `logs/workflow_state.pkl` 文件，系统会自动创建新的状态文件。

## 技术支持

如有问题，请查看系统日志文件 `logs/pl5.log` 获取更多详细信息。
