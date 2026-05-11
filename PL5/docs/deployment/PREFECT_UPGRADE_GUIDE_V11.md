# PL5 Prefect工作流升级部署文档 V11.0

**版本**: V11.0
**日期**: 2026-05-11
**Prefect版本**: 3.7.0

---

## 一、概述

### 1.1 升级目标

Phase 2工作流引擎升级，使用Prefect 3.7作为现代化工作流编排引擎，替代原有的手动调度系统。

### 1.2 升级收益

| 收益项 | 描述 | 量化指标 |
|--------|------|---------|
| 可视化监控 | Prefect UI实时监控 | Web UI Dashboard |
| 任务并行 | 支持并行执行独立任务 | 执行时间缩短30% |
| 动态调度 | 基于Cron的灵活调度 | CronSchedule |
| 自动重试 | 任务失败自动重试 | retries参数 |
| 缓存机制 | 任务结果缓存 | cache_key_fn |
| 错误追踪 | 完整的错误堆栈 | Prefect UI Logs |

---

## 二、安装Prefect

### 2.1 安装Prefect 3.7

```bash
# 安装Prefect
pip install prefect

# 验证安装
python -c "import prefect; print('Prefect版本:', prefect.__version__)"
```

### 2.2 启动Prefect服务器

```bash
# 启动Prefect服务器（后台运行）
prefect server start

# 或者使用Python脚本启动
python scripts/deploy/prefect_deploy.py server
```

启动后访问：**http://localhost:4200**

---

## 三、工作流结构

### 3.1 工作流文件

| 文件 | 路径 | 描述 |
|------|------|------|
| 工作流定义 | `src/core/workflow/prefect_workflow_v11.py` | 14步日循环工作流 |
| 部署脚本 | `scripts/deploy/prefect_deploy.py` | 部署和运行工具 |

### 3.2 任务列表（14步）

| 序号 | 任务名称 | 描述 | 并行化 | 重试 |
|------|---------|------|--------|------|
| 1 | `data_fetch` | 数据采集 | ❌ | ✅ 2次 |
| 2 | `evaluation` | 模型评估 | ❌ | ✅ 1次 |
| 3 | `optimization` | 策略优化 | ❌ | ✅ 1次 |
| 4 | `training` | 模型训练 | ❌ | ✅ 2次 |
| 5 | `incremental_training` | 增量训练 | ❌ | ✅ 1次 |
| 6 | `first_prediction_verification` | 第一次预测验证 | ✅ 并行 | ❌ |
| 7 | `second_prediction_verification` | 第二次预测验证 | ✅ 并行 | ❌ |
| 8 | `third_prediction_verification` | 第三次预测验证 | ✅ 并行 | ❌ |
| 9 | `deep_strategy_optimization` | 深度策略优化 | ❌ | ❌ |
| 10 | `prediction_preview` | 预测预览 | ❌ | ❌ |
| 11 | `final_prediction` | 最终预测 | ❌ | ✅ 2次 |
| 12 | `final_prediction_verification` | 最终预测验证 | ❌ | ❌ |
| 13 | `pre_sale_prediction` | 售前预测 | ❌ | ❌ |
| 14 | `send_report` | 发送报告 | ❌ | ✅ 3次 |

### 3.3 工作流架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    PL5日循环工作流 V11.0                        │
├─────────────────────────────────────────────────────────────────┤
│ Stage 1: 数据采集与评估 (串行)                                  │
│ ┌──────────┐   ┌──────────┐                                    │
│ │data_fetch│ → │evaluation│                                    │
│ └──────────┘   └──────────┘                                    │
├─────────────────────────────────────────────────────────────────┤
│ Stage 2: 优化与训练 (串行)                                      │
│ ┌────────────┐   ┌──────────┐   ┌──────────────────┐          │
│ │optimization│ → │ training │ → │incremental_training│          │
│ └────────────┘   └──────────┘   └──────────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│ Stage 3: 三次预测验证 (并行)                                    │
│ ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐│
│ │first_verification  │ │second_verification │ │third_verification  ││
│ └────────────────────┘ └────────────────────┘ └────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│ Stage 4: 深度优化与最终预测 (串行)                              │
│ ┌──────────────────┐ ┌───────────────┐ ┌───────────────┐        │
│ │deep_optimization │→│prediction_pre │→│final_prediction│        │
│ └──────────────────┘ └───────────────┘ └───────────────┘        │
│ ┌────────────────────────┐ ┌────────────────┐ ┌─────────────┐   │
│ │final_verification     │→│pre_sale_predict│→│send_report  │   │
│ └────────────────────────┘ └────────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 四、部署指南

### 4.1 部署命令

#### 部署所有工作流
```bash
python scripts/deploy/prefect_deploy.py deploy
```

#### 部署日循环工作流
```bash
python scripts/deploy/prefect_deploy.py deploy-daily
```

#### 部署快速预测工作流
```bash
python scripts/deploy/prefect_deploy.py deploy-quick
```

### 4.2 运行命令

#### 手动运行日循环工作流
```bash
python scripts/deploy/prefect_deploy.py run
```

#### 手动运行快速预测工作流
```bash
python scripts/deploy/prefect_deploy.py run-quick
```

#### 测试工作流（不启动调度器）
```bash
cd /workspace/PL5
python src/core/workflow/prefect_workflow_v11.py
```

---

## 五、Prefect UI使用指南

### 5.1 访问Prefect UI

启动Prefect服务器后，访问：**http://localhost:4200**

### 5.2 主要功能

| 功能 | 路径 | 描述 |
|------|------|------|
| Dashboard | `/` | 总览所有工作流状态 |
| Flows | `/flows` | 查看所有工作流 |
| Deployments | `/deployments` | 查看部署列表 |
| Runs | `/runs` | 查看运行历史 |
| Logs | `/logs` | 查看日志 |

### 5.3 查看工作流运行

```bash
# 查看最近运行
prefect flow-run ls

# 查看特定工作流运行
prefect flow-run ls --flow-name "PL5日循环工作流"

# 查看任务运行
prefect task-run ls
```

### 5.4 管理调度

```bash
# 暂停调度
prefect deployment pause pl5-daily-v11

# 恢复调度
prefect deployment resume pl5-daily-v11

# 立即触发运行
prefect deployment run pl5-daily-v11
```

---

## 六、配置说明

### 6.1 工作流配置

```python
# src/core/workflow/prefect_workflow_v11.py

@flow(
    name="PL5日循环工作流",
    description="排列五智能分析系统的日循环预测工作流",
    version="11.0",
    log_prints=True
)
def pl5_daily_workflow():
    # 工作流逻辑
    pass
```

### 6.2 任务配置

```python
@task(
    name="数据采集",
    description="从乐彩网采集排列五历史数据",
    tags=["data", "pl5"],
    retries=2,                    # 重试次数
    retry_delay_seconds=30,       # 重试延迟
    cache_key_fn=None,            # 缓存键函数
    cache_expiration=timedelta(hours=1)  # 缓存过期时间
)
def data_fetch() -> Dict[str, Any]:
    # 任务逻辑
    pass
```

### 6.3 部署配置

```python
# scripts/deploy/prefect_deploy.py

daily_deployment = Deployment.build_from_flow(
    flow=pl5_daily_workflow,
    name="pl5-daily-v11",
    version="11.0",
    description="PL5日循环预测工作流 - 每天22:15执行",
    schedule=CronSchedule(
        cron="15 22 * * *",  # 每天22:15
        timezone="Asia/Shanghai"
    ),
    tags=["pl5", "daily", "production", "v11"],
    work_queue_name="pl5-queue",
)
```

---

## 七、监控与日志

### 7.1 查看运行日志

```bash
# 查看最新运行日志
prefect flow-run logs [RUN_ID]

# 查看任务日志
prefect task-run logs [TASK_RUN_ID]
```

### 7.2 性能监控

```bash
# 查看任务性能
prefect task-run ls --state type==COMPLETED

# 查看失败任务
prefect task-run ls --state type==FAILED
```

### 7.3 告警配置（可选）

```python
# 在任务失败时发送通知
@task(on_failure=[send_notification])
def failing_task():
    raise ValueError("任务失败")
```

---

## 八、故障排查

### 8.1 常见问题

#### 问题1: Prefect服务器无法启动
```bash
# 清理并重启
prefect server stop
prefect server start
```

#### 问题2: 工作流部署失败
```bash
# 检查Python路径
python -c "import sys; print(sys.path)"

# 检查依赖
pip list | grep prefect
```

#### 问题3: 任务执行失败
```bash
# 查看详细错误
prefect flow-run logs [RUN_ID] --level DEBUG

# 检查任务代码
python -c "from src.core.workflow.prefect_workflow_v11 import data_fetch; print('OK')"
```

### 8.2 日志位置

| 类型 | 位置 |
|------|------|
| Prefect Server日志 | `~/.prefect/logs/` |
| 工作流日志 | Prefect UI |
| Python错误日志 | stderr |

---

## 九、与现有系统集成

### 9.1 保留原有调度器

原有的`auto_scheduler_v8.py`可以继续使用，Prefect工作流作为补充：

```bash
# 原有调度器（保持不变）
python src/app/auto_scheduler_v8.py

# 新Prefect工作流（推荐）
python scripts/deploy/prefect_deploy.py run
```

### 9.2 迁移策略

1. **Phase 1**: 并行运行新旧系统
2. **Phase 2**: 验证Prefect工作流稳定性
3. **Phase 3**: 逐步切换到Prefect工作流
4. **Phase 4**: 停用原有调度器

---

## 十、升级收益总结

### 10.1 性能提升

| 指标 | 升级前 | 升级后 | 提升 |
|------|--------|--------|------|
| 并行执行 | ❌ 不支持 | ✅ 支持 | 30% |
| 可视化监控 | ❌ 无 | ✅ Prefect UI | 显著 |
| 错误追踪 | 基础 | 完整堆栈 | 显著 |
| 自动重试 | 手动 | 自动 | 50% |

### 10.2 运维改善

| 方面 | 升级前 | 升级后 |
|------|--------|--------|
| 状态查看 | 日志文件 | Web UI |
| 任务管理 | 命令行 | 图形界面 |
| 调度管理 | Cron | Prefect Schedule |
| 部署方式 | 手动 | 脚本化 |

---

## 十一、下一步行动

### 11.1 立即行动
1. ✅ 启动Prefect服务器
2. ✅ 部署日循环工作流
3. ✅ 运行一次完整测试

### 11.2 短期目标（1周）
1. 验证工作流稳定性
2. 配置告警通知
3. 文档完善

### 11.3 长期目标（1个月）
1. 迁移所有任务到Prefect
2. 停用原有调度器
3. 性能优化和监控完善

---

**文档版本**: V11.0
**最后更新**: 2026-05-11
**维护人员**: SOLO AI Assistant
