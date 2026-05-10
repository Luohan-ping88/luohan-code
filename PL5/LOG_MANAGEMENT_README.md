# PL5 日志管理系统

## 概述

本系统提供了完整的日志管理功能，包括：
- 日志轮换（自动按天轮转，保留7天）
- 日志清理（临时文件清理）
- 日志归档（旧文件归档）
- 日志整理（按类型分类）

## 目录结构

```
logs/
├── app.log                          # 当前日志文件（自动轮换）
├── log_config.json                  # 日志配置文件
├── scheduler_v8_status.json        # 调度器状态文件
├── task_history_v8.pkl           # 任务历史文件
├── workflow_state.pkl             # 工作流状态文件
│
├── predictions/                     # 预测相关文件
│   ├── final_prediction.json
│   ├── pre_sale_prediction.json
│   ├── first_prediction_verification.json
│   └── prediction_verification.json
│
├── reports/                       # 报告文件
│   ├── report_info.json
│   └── training_info.json
│
├── performance/                   # 性能文件
│   ├── performance_20260419.jsonl
│   └── performance_20260420.jsonl
│
├── sentinel/                      # 哨兵日志
│   ├── sentinel_status.json
│   └── sentinel_20260419.log
│
└── archive/                      # 归档目录（旧文件）
    ├── app_*.jsonl
    ├── *.log
    └── ...
```

## 快速开始

### 1. 运行完整日志清理

```bash
python run_log_cleanup.py
```

### 2. 单独运行日志管理器

```bash
# 方式1：直接运行模块
python -m src.core.utils.log_manager --full-cleanup

# 方式2：查看日志摘要
python -m src.core.utils.log_manager --summary

# 方式3：仅清理临时文件
python -m src.core.utils.log_manager --clean-temp
```

### 3. 日志轮换说明

日志系统已升级为自动轮换：
- 当前日志：`app.log`
- 自动轮换：每天午夜自动创建新文件
- 保留天数：7天
- 旧文件格式：`app.log.YYYYMMDD`

## 配置文件

`logs/log_config.json` 包含日志管理配置：

```json
{
  "retention_days": {
    "app_logs": 7,
    "performance_logs": 7,
    "temp_files": 3,
    "archive_files": 30
  },
  "archive_threshold": 7,
  "max_file_size_mb": 50,
  "compression_enabled": true,
  "rotation_config": {
    "when": "midnight",
    "interval": 1,
    "backupCount": 7
  },
  "critical_files": [...],
  "temp_patterns": [...]
}
```

## 可用命令

### log_manager.py 命令

```bash
# 查看摘要
python -m src.core.utils.log_manager --summary

# 清理临时文件
python -m src.core.utils.log_manager --clean-temp

# 清理旧日志（指定天数）
python -m src.core.utils.log_manager --clean-old 14

# 整理目录结构
python -m src.core.utils.log_manager --organize

# 完整清理（推荐）
python -m src.core.utils.log_manager --full-cleanup
```

### 其他脚本

```bash
# 快速清理旧的 app_*.jsonl 日志
python clean_old_logs.py

# 完整清理和整理
python run_log_cleanup.py
```

## 关键文件保护

以下文件被保护，不会被清理或归档：
- `scheduler_v8_status.json`
- `task_history_v8.pkl`
- `workflow_state.pkl`
- `app.log`
- `sentinel_status.json`
- `log_config.json`

## 日志清理流程

1. **清理临时文件**：删除所有测试相关文件
2. **归档旧日志**：将超过7天的文件归档
3. **整理目录**：按类型分类
4. **保留关键**：保留系统状态文件

## 性能统计（已完成整理）

**整理前：75个文件，8.29 MB
**整理后：清洁的目录结构
**已归档：48个旧文件
**已清理：12个临时文件

## 定时维护建议

建议每周运行一次完整清理：

```bash
python run_log_cleanup.py
```

## 故障排查

### 日志文件正在被使用

如果遇到 `PermissionError`，说明文件正在被系统使用，会自动跳过。

### 查看日志状态

```bash
ls -la logs/
```

### 查看归档文件

```bash
ls -la logs/archive/
```
