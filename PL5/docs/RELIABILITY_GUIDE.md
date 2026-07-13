# PL5 系统可靠性指南

> 版本: 2.0  
> 更新日期: 2026-04-06  
> 目标可用性: 99.9%  
> 故障恢复时间目标: < 5分钟

---

## 目录

1. [概述](#概述)
2. [可靠性架构](#可靠性架构)
3. [错误处理系统](#错误处理系统)
4. [备份恢复机制](#备份恢复机制)
5. [故障恢复策略](#故障恢复策略)
6. [监控与告警](#监控与告警)
7. [运维指南](#运维指南)
8. [故障排查](#故障排查)

---

## 概述

### 可靠性目标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 系统可用性 | 99.9% | 年度停机时间 < 8.76小时 |
| 故障恢复时间 | < 5分钟 | 从故障检测到恢复完成 |
| 数据备份频率 | 每天 | 自动每日备份 |
| 备份保留期 | 30天 | 自动清理旧备份 |
| 错误恢复成功率 | > 95% | 自动恢复成功率 |

### 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                      PL5 可靠性系统                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  错误处理    │  │  备份系统    │  │  故障恢复    │      │
│  │  Error       │  │  Backup      │  │  Recovery    │      │
│  │  Handler     │  │  System      │  │  System      │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │              │
│         └─────────────────┼─────────────────┘              │
│                           │                                │
│                    ┌──────┴──────┐                        │
│                    │  监控系统   │                        │
│                    │  Monitor    │                        │
│                    └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 可靠性架构

### 架构设计原则

1. **故障隔离**: 各模块独立运行，故障不扩散
2. **优雅降级**: 核心功能故障时提供简化服务
3. **自动恢复**: 常见故障自动检测和恢复
4. **数据保护**: 多重备份机制确保数据安全

### 模块关系图

```
┌────────────────────────────────────────────────────────────┐
│                        应用层                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ 数据收集 │ │ 模型训练 │ │ 预测服务 │ │ 邮件服务 │      │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │
│       │            │            │            │             │
├───────┼────────────┼────────────┼────────────┼────────────┤
│       │            │            │            │   可靠性层   │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐      │
│  │ 错误处理 │ │ 自动重试 │ │ 熔断器   │ │ 回退策略 │      │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │
│       │            │            │            │             │
├───────┼────────────┼────────────┼────────────┼────────────┤
│       │            │            │            │   基础设施层 │
│  ┌────┴────────────┴────────────┴────────────┴─────┐      │
│  │              备份与恢复系统                      │      │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │      │
│  │  │ 每日备份 │ │ 手动备份 │ │ 恢复工具 │        │      │
│  │  └──────────┘ └──────────┘ └──────────┘        │      │
│  └────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────┘
```

---

## 错误处理系统

### 错误分类体系

```python
# 错误严重程度
class ErrorSeverity:
    LOW = "low"           # 轻微错误，不影响系统运行
    MEDIUM = "medium"     # 中等错误，可能影响部分功能
    HIGH = "high"         # 严重错误，影响核心功能
    CRITICAL = "critical" # 致命错误，系统可能无法运行

# 错误类别
class ErrorCategory:
    DATA = "data"       # 数据相关错误
    MODEL = "model"     # 模型相关错误
    CONFIG = "config"   # 配置相关错误
    NETWORK = "network" # 网络相关错误
    SYSTEM = "system"   # 系统相关错误
```

### 异常类型

| 异常类型 | 说明 | 严重程度 | 自动恢复 |
|----------|------|----------|----------|
| `DataLoadError` | 数据加载失败 | HIGH | 是 |
| `DataValidationError` | 数据验证失败 | MEDIUM | 否 |
| `ModelLoadError` | 模型加载失败 | HIGH | 是 |
| `ModelPredictionError` | 模型预测失败 | HIGH | 是 |
| `NetworkTimeoutError` | 网络超时 | HIGH | 是 |
| `ResourceExhaustedError` | 资源耗尽 | CRITICAL | 否 |
| `ServiceUnavailableError` | 服务不可用 | CRITICAL | 是 |

### 使用示例

```python
from src.core.utils.error_handler import (
    DataLoadError, ModelLoadError, NetworkError,
    retry_with_exponential_backoff, handle_errors,
    error_logger, get_error_stats
)

# 1. 使用重试装饰器
@retry_with_exponential_backoff(
    max_retries=3,
    base_delay=1.0,
    backoff_factor=2.0
)
def fetch_data_from_api():
    # 可能失败的网络操作
    response = requests.get("https://api.example.com/data")
    return response.json()

# 2. 使用错误处理装饰器
@handle_errors(fallback_value=[])
def process_data(data_path):
    # 可能失败的数据处理
    with open(data_path) as f:
        return json.load(f)

# 3. 手动记录错误
try:
    risky_operation()
except Exception as e:
    error_logger.log_error(
        e,
        operation="risky_operation",
        component="data_processor"
    )

# 4. 查看错误统计
stats = get_error_stats()
print(f"总错误数: {stats['total_errors']}")
print(f"按类别分布: {stats['errors_by_category']}")
```

### 错误日志

错误日志保存在 `logs/errors/` 目录下，按日期分割：

```
logs/errors/
├── errors_20260406.jsonl
├── errors_20260405.jsonl
└── ...
```

日志格式（JSON Lines）：
```json
{
  "error_id": "ERR_A1B2C3D4E5F6",
  "error_type": "DataLoadError",
  "severity": "high",
  "category": "data",
  "message": "无法加载数据文件",
  "timestamp": "2026-04-06T10:30:00",
  "operation": "load_training_data",
  "component": "data_loader",
  "recovered": true,
  "recovery_strategy": "retry_with_backoff"
}
```

---

## 备份恢复机制

### 备份策略

```
backups/
├── daily/                    # 每日自动备份
│   ├── daily_20260406_020000/
│   │   ├── data/
│   │   ├── models/
│   │   ├── config/
│   │   └── backup_info.json
│   └── ...
├── manual/                   # 手动备份
│   └── manual_pre_update_20260406_150000/
└── pre_restore/             # 恢复前自动备份
    └── pre_restore_backup_20260406_143000/
```

### 备份内容

| 项目 | 说明 | 必需 |
|------|------|------|
| `data/` | 数据文件 | 是 |
| `models/` | 模型文件 | 是 |
| `config/` | 配置文件 | 是 |
| `logs/` | 日志文件 | 否 |

### 自动备份配置

默认配置：
- **备份时间**: 每天 02:00
- **保留数量**: 30天
- **压缩**: 启用
- **完整性验证**: 启用

### 命令行工具

#### 创建备份

```bash
# 执行每日备份
python scripts/utility/auto_backup.py --daily

# 执行手动备份
python scripts/utility/auto_backup.py --manual --name "pre_update"

# 列出所有备份
python scripts/utility/auto_backup.py --list

# 查看备份统计
python scripts/utility/auto_backup.py --stats
```

#### 恢复备份

```bash
# 交互式恢复（推荐）
python scripts/utility/restore_backup.py --interactive

# 使用最新备份恢复
python scripts/utility/restore_backup.py --latest

# 指定备份ID恢复
python scripts/utility/restore_backup.py --backup-id daily_20260406_020000

# 只恢复特定项目
python scripts/utility/restore_backup.py --latest --items "data,models"

# 列出可用备份
python scripts/utility/restore_backup.py --list
```

### Python API

```python
from scripts.utility.auto_backup import BackupManager, BackupConfig
from scripts.utility.restore_backup import BackupRestorer

# 创建备份
config = BackupConfig(
    backup_dir="backups",
    max_daily_backups=30,
    compression_enabled=True
)
manager = BackupManager(config)
result = manager.create_backup(backup_type="daily")

# 恢复备份
restorer = BackupRestorer("backups")
result = restorer.restore(
    backup_id="daily_20260406_020000",
    create_pre_backup=True,
    verify_after_restore=True
)
```

---

## 故障恢复策略

### 自动恢复机制

```
┌─────────────────────────────────────────────────────────────┐
│                     故障检测流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   故障发生 ──→ 错误分类 ──→ 严重度评估 ──→ 恢复策略选择      │
│      │           │            │              │              │
│      ↓           ↓            ↓              ↓              │
│   捕获异常    确定类别    确定优先级    执行恢复            │
│                                                             │
│   恢复策略:                                                 │
│   ├── 自动重试 (指数退避)                                   │
│   ├── 使用缓存/上次成功结果                                 │
│   ├── 切换到备用服务                                        │
│   ├── 使用默认/简化策略                                     │
│   └── 人工介入                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 恢复策略详解

#### 1. 自动重试（指数退避）

```python
from src.core.utils.error_handler import retry_with_exponential_backoff

@retry_with_exponential_backoff(
    max_retries=3,           # 最大重试次数
    base_delay=1.0,          # 基础延迟（秒）
    max_delay=60.0,          # 最大延迟（秒）
    backoff_factor=2.0       # 退避因子
)
def unstable_network_call():
    # 可能失败的网络调用
    pass
```

**重试延迟计算**: `delay = min(base_delay * (backoff_factor ^ attempt), max_delay)`

| 尝试次数 | 延迟时间 |
|----------|----------|
| 1 | 1秒 |
| 2 | 2秒 |
| 3 | 4秒 |
| 4 | 8秒 |
| ... | ... |

#### 2. 熔断器模式

```python
from src.core.utils.error_handler import circuit_breaker

@circuit_breaker(
    failure_threshold=5,      # 失败阈值
    recovery_timeout=60.0     # 恢复超时（秒）
)
def external_service_call():
    # 调用外部服务
    pass
```

**熔断器状态**:
- **Closed**: 正常状态，允许请求通过
- **Open**: 熔断状态，快速失败
- **Half-Open**: 试探状态，允许部分请求测试服务恢复

#### 3. 优雅降级

```python
from src.core.utils.error_handler import safe_execute

# 主策略失败时使用备用策略
result = safe_execute(
    primary_prediction_strategy,
    fallback_value=simple_prediction_strategy(),
    log_errors=True
)
```

### 故障场景与恢复

| 故障场景 | 检测方式 | 恢复策略 | 预计恢复时间 |
|----------|----------|----------|--------------|
| 网络超时 | 异常捕获 | 指数退避重试 | 10-30秒 |
| 数据加载失败 | 异常捕获 | 重试+备份恢复 | 30-60秒 |
| 模型加载失败 | 异常捕获 | 使用备份模型 | 5-10秒 |
| 内存不足 | 资源监控 | 清理缓存+告警 | 5-10秒 |
| 磁盘空间不足 | 资源监控 | 清理日志+告警 | 10-20秒 |
| 服务崩溃 | 健康检查 | 自动重启 | 30-60秒 |

---

## 监控与告警

### 健康检查

```python
from src.core.monitoring.health_check import check_health, get_health_summary

# 执行健康检查
health = check_health()

# 检查结果示例
{
    "timestamp": "2026-04-06T10:30:00",
    "overall_status": "healthy",  # healthy/warning/critical
    "checks": {
        "system_resources": {"status": "healthy", ...},
        "disk_space": {"status": "healthy", ...},
        "backup_status": {"status": "healthy", ...},
        "component_health": {"status": "healthy", ...}
    }
}
```

### 监控指标

| 指标 | 警告阈值 | 严重阈值 | 检查频率 |
|------|----------|----------|----------|
| CPU使用率 | 75% | 90% | 1分钟 |
| 内存使用率 | 70% | 85% | 1分钟 |
| 磁盘使用率 | 75% | 90% | 5分钟 |
| 备份时间 | >24小时 | >48小时 | 1小时 |
| 错误率 | >5% | >10% | 5分钟 |

### 告警规则

```python
# 告警配置示例
ALERT_RULES = {
    "high_cpu": {
        "condition": "cpu_percent > 90",
        "level": "critical",
        "action": ["log", "email"]
    },
    "backup_overdue": {
        "condition": "hours_since_backup > 24",
        "level": "warning",
        "action": ["log", "email"]
    }
}
```

---

## 运维指南

### 日常检查清单

#### 每日检查

- [ ] 检查系统健康状态
- [ ] 确认备份已完成
- [ ] 查看错误日志
- [ ] 检查磁盘空间

#### 每周检查

- [ ] 检查备份完整性
- [ ] 清理旧日志文件
- [ ] 检查错误统计趋势
- [ ] 验证恢复流程

#### 每月检查

- [ ] 执行完整恢复演练
- [ ] 检查备份存储使用情况
- [ ] 更新恢复文档
- [ ] 评估可靠性指标

### 常用运维命令

```bash
# 检查系统健康
python run_health_check.py

# 查看错误统计
python -c "from src.core.utils.error_handler import get_error_stats; print(get_error_stats())"

# 手动创建备份
python scripts/utility/auto_backup.py --manual --name "pre_maintenance"

# 查看备份列表
python scripts/utility/auto_backup.py --list

# 运行故障恢复测试
python tests/test_fault_recovery.py
```

### 自动化脚本

#### 设置定时备份

```bash
# 使用 cron (Linux/Mac)
0 2 * * * cd /path/to/pl5 && python scripts/utility/auto_backup.py --daily

# 使用任务计划程序 (Windows)
# 创建任务：每天 02:00 运行
# 命令: python scripts/utility/auto_backup.py --daily
```

#### 监控脚本

```bash
#!/bin/bash
# health_monitor.sh

HEALTH=$(python -c "from src.core.monitoring.health_check import get_health_summary; import json; print(json.dumps(get_health_summary()))")
STATUS=$(echo $HEALTH | python -c "import sys, json; print(json.load(sys.stdin)['status'])")

if [ "$STATUS" = "critical" ]; then
    echo "系统状态严重，需要立即处理"
    # 发送告警
fi
```

---

## 故障排查

### 常见问题

#### Q1: 备份失败

**症状**: 备份任务报错或备份文件不完整

**排查步骤**:
1. 检查磁盘空间: `df -h` (Linux) 或查看磁盘属性 (Windows)
2. 检查日志: `logs/backup.log`
3. 验证备份目录权限
4. 手动执行备份测试: `python scripts/utility/auto_backup.py --manual`

**解决方案**:
- 清理磁盘空间
- 修复目录权限
- 检查备份配置

#### Q2: 模型加载失败

**症状**: 系统启动时无法加载模型

**排查步骤**:
1. 检查模型文件是否存在: `ls models/`
2. 检查模型文件完整性
3. 查看错误日志: `logs/errors/errors_*.jsonl`
4. 尝试从备份恢复模型

**解决方案**:
```bash
# 从最新备份恢复模型
python scripts/utility/restore_backup.py --latest --items "models"
```

#### Q3: 网络连接失败

**症状**: 数据获取或API调用失败

**排查步骤**:
1. 检查网络连接: `ping api.example.com`
2. 检查代理设置
3. 查看错误日志中的网络错误
4. 测试手动连接

**解决方案**:
- 检查网络配置
- 调整超时设置
- 使用备用数据源

#### Q4: 系统性能下降

**症状**: 响应变慢，CPU/内存使用率高

**排查步骤**:
1. 检查系统资源使用
2. 查看性能监控日志
3. 检查是否有内存泄漏
4. 分析慢操作日志

**解决方案**:
- 重启服务
- 清理缓存
- 优化配置
- 增加资源

### 紧急恢复流程

```
1. 确认故障范围
   └── 检查健康状态: python run_health_check.py

2. 收集诊断信息
   └── 查看错误日志: logs/errors/
   └── 查看系统日志: logs/system.log

3. 尝试自动恢复
   └── 重启服务
   └── 清理缓存

4. 数据恢复（如需要）
   └── 从备份恢复: python scripts/utility/restore_backup.py --latest

5. 验证恢复结果
   └── 运行健康检查
   └── 执行功能测试

6. 记录故障信息
   └── 更新故障记录
   └── 分析根本原因
```

### 联系支持

- **技术支持**: support@pl5-system.com
- **紧急热线**: +86-xxx-xxxx-xxxx
- **文档地址**: https://docs.pl5-system.com
- **问题跟踪**: https://issues.pl5-system.com

---

## 附录

### A. 配置文件示例

```json
{
  "reliability": {
    "error_handling": {
      "max_retries": 3,
      "base_delay": 1.0,
      "backoff_factor": 2.0
    },
    "backup": {
      "enabled": true,
      "schedule": "02:00",
      "retention_days": 30,
      "compression": true
    },
    "monitoring": {
      "health_check_interval": 300,
      "alert_threshold": {
        "cpu_percent": 90,
        "memory_percent": 85,
        "disk_percent": 90
      }
    }
  }
}
```

### B. 测试命令

```bash
# 运行所有可靠性测试
python tests/test_fault_recovery.py

# 运行特定测试
python -m unittest tests.test_fault_recovery.TestErrorHandling

# 生成测试报告
python tests/test_fault_recovery.py 2>&1 | tee test_report.txt
```

### C. 更新日志

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 2.0 | 2026-04-06 | 重构错误处理系统，增强备份功能 |
| 1.1 | 2026-03-15 | 添加熔断器模式 |
| 1.0 | 2026-03-01 | 初始版本 |

---

**文档维护**: PL5 开发团队  
**最后更新**: 2026-04-06
