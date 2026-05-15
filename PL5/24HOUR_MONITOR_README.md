# PL5 24小时持续监控系统使用说明

## 📋 概述

PL5 24小时持续监控系统是一个全面的自动化监控和优化工具，旨在确保PL5项目在云端沙箱中24小时不间断运行。该系统能够自动检测问题、优化性能并尝试修复错误。

## 🎯 主要功能

### 1. 训练推理性能及逻辑检测
- ✅ 运行 `src/core/models/predictor.py` 的预测功能测试
- ✅ 运行 `src/core/models/model_evaluator.py` 的模型评估
- ✅ 检查 `src/core/training/` 目录下的训练逻辑
- ✅ 验证数据处理流程 (`src/core/data/collector.py`)

### 2. 代码质量优化
- ✅ 检查 `src/` 目录下的Python代码语法
- ✅ 运行 pytest 测试套件检查测试覆盖率
- ✅ 检查代码导入依赖是否正常

### 3. 智能功能执行逻辑检测
- ✅ 检查 `src/ai/tools/pl5_tool.py` 的工具执行逻辑
- ✅ 检查 `src/ai/agents/agent_orchestrator.py` 的智能体编排
- ✅ 验证 `intelligent_scheduler_integration.py` 的集成功能

### 4. BUG修复和错误处理
- ✅ 检查日志文件 (`scheduler.log`, `crash.log`, `performance.log`)
- ✅ 运行 `scripts/utility/verify_all_fixes.py` 验证修复
- ✅ 运行 `monitor/system_checker.py` 检查系统状态
- ✅ 检查 `src/core/utils/unified_error_handler.py` 的错误处理

## 🚀 快速开始

### 方式一：使用交互式启动器（推荐）

```bash
cd /workspace/PL5
python run_monitor.py
```

系统会引导您选择运行模式：
- **单次审计模式**：运行一次完整审计并退出
- **持续监控模式**：24小时持续监控

### 方式二：后台运行（无交互）

```bash
cd /workspace/PL5
bash start_background_monitor.sh
```

### 方式三：直接运行

```bash
# 单次审计
python pl5_24hour_monitor.py

# 持续监控
python pl5_24hour_monitor.py --continuous
```

## 📁 日志和输出

### 日志目录结构
```
/workspace/PL5/logs/daily_audit/
├── daily_audit_YYYYMMDD_HHMMSS.log    # 主审计日志
├── audit_YYYYMMDD_HHMMSS.json          # 审计结果JSON
├── cycle_*.json                          # 每个周期的详细结果
├── summary_YYYYMMDD_HHMMSS.txt          # 12小时汇总报告
├── final_summary_*.txt                   # 最终汇总报告
├── nohup_*.log                           # 后台运行日志
└── monitor_*.pid                         # 进程PID文件
```

### 日志命名规范
- **daily_audit_YYYYMMDD_HHMMSS.log**: 日志文件，格式为 `daily_audit_年份月份日期_时分秒.log`

## ⚙️ 配置参数

### 审计周期配置

在 `pl5_24hour_monitor.py` 中可以修改：

```python
CYCLE_INTERVAL = 10 * 60  # 审计周期（秒），默认10分钟
TOTAL_CYCLES = int(24 * 60 * 60 / CYCLE_INTERVAL)  # 24小时内的审计次数
```

### 日志保留策略

系统会自动清理过旧的日志文件，您可以在 `pl5_24hour_monitor.py` 中配置：

```python
LOG_RETENTION_DAYS = 7  # 日志保留天数
```

## 📊 监控内容详解

### 1. 系统健康检查
- **模块导入检查**：验证所有核心模块是否可以正常导入
- **系统资源监控**：CPU、内存、磁盘使用率
- **日志文件检查**：扫描错误日志中的ERROR和CRITICAL

### 2. 训练推理性能测试
- **预测器测试**：验证 `PL5Predictor` 类的实例化和基本功能
- **模型评估器测试**：验证 `ModelEvaluator` 的功能
- **数据收集器测试**：验证 `DataCollector` 的功能
- **训练逻辑检查**：扫描训练模块目录

### 3. 代码质量检查
- **语法检查**：编译所有Python文件检查语法错误
- **pytest测试**：运行完整测试套件

### 4. 智能功能检查
- **PL5工具检查**：验证AI工具的功能完整性
- **智能体编排器检查**：验证多智能体协作系统
- **智能调度器检查**：验证调度系统的集成

### 5. BUG修复验证
- **修复验证脚本**：运行 `verify_all_fixes.py`
- **错误处理器检查**：验证统一错误处理机制
- **系统检查器**：运行 `system_checker.py`

## 🔧 自动化修复

### 已实现的自动修复功能

1. **依赖自动安装**：检测到缺失依赖时自动安装
2. **模块导入修复**：尝试修复常见的导入错误
3. **日志清理**：自动清理过旧的日志文件

### 手动修复工具

```bash
# 安装依赖
python install_dependencies_fix.py

# 自动修复问题
python auto_fix_issues.py
```

## 📈 监控报告

### 实时查看日志

```bash
# 查看主审计日志
tail -f logs/daily_audit/daily_audit_*.log

# 查看后台运行日志
tail -f logs/daily_audit/nohup_*.log
```

### 查看审计结果

```bash
# 查看最新的审计结果
cat logs/daily_audit/audit_*.json | python -m json.tool | less

# 查看汇总报告
cat logs/daily_audit/summary_*.txt
```

## 🛑 停止监控

### 停止后台监控进程

```bash
# 方法1：使用PID文件
kill $(cat logs/daily_audit/monitor_*.pid)

# 方法2：查找并杀死进程
ps aux | grep pl5_24hour_monitor
kill <PID>

# 方法3：使用pkill
pkill -f pl5_24hour_monitor
```

### 优雅停止

如果使用 `run_monitor.py` 启动，可以按 `Ctrl+C` 优雅停止。

## 🔍 故障排查

### 常见问题

#### 1. 依赖缺失
**症状**：`No module named 'xxx'`

**解决**：
```bash
python install_dependencies_fix.py
```

#### 2. 模块导入失败
**症状**：核心模块无法导入

**解决**：
```bash
python auto_fix_issues.py
```

#### 3. 磁盘空间不足
**症状**：日志写入失败

**解决**：
```bash
# 清理旧日志
python -c "
from pathlib import Path
log_dir = Path('logs/daily_audit')
for f in log_dir.glob('*.log'):
    if f.stat().st_mtime < time.time() - 7*86400:
        f.unlink()
"
```

#### 4. pytest测试失败
**症状**：pytest返回非零退出码

**解决**：
```bash
# 查看详细错误
python -m pytest tests/ -v

# 单独运行失败的测试
python -m pytest tests/test_predictor.py -v
```

## 📝 审计日志格式

### 主日志格式
```
2026-05-15 14:00:03,957 - INFO - ================================================================================
2026-05-15 14:00:03,957 - INFO -   开始审计周期 #1
2026-05-15 14:00:03,957 - INFO - ================================================================================
```

### JSON结果格式
```json
{
  "timestamp": "2026-05-15T14:00:03.957188",
  "cycle_id": 1,
  "checks": {
    "predictor": {"status": "success"},
    "evaluator": {"status": "success"},
    "syntax": true
  },
  "elapsed_seconds": 7.72
}
```

## 🎓 高级用法

### 自定义审计周期

修改 `pl5_24hour_monitor.py`：

```python
# 更短的周期（5分钟）
CYCLE_INTERVAL = 5 * 60

# 更长的周期（30分钟）
CYCLE_INTERVAL = 30 * 60
```

### 添加自定义检查

在 `Continuous24HourMonitor.run_full_audit_cycle()` 方法中添加新的检查：

```python
def run_full_audit_cycle(self):
    # ... 现有代码 ...

    # 添加自定义检查
    self.logger.log_section("6. 自定义检查")
    # 您的检查代码...

```

### 集成告警系统

修改 `EnhancedAuditLogger` 以集成邮件或Slack告警：

```python
def send_alert(self, message: str):
    # 发送告警
    import requests
    requests.post('https://slack.com/api/chat.postMessage', json={
        'text': f"⚠️ PL5监控告警: {message}"
    })
```

## 📚 相关文件

- **主监控脚本**: `pl5_24hour_monitor.py`
- **启动器**: `run_monitor.py`
- **后台启动**: `start_background_monitor.sh`
- **依赖安装**: `install_dependencies_fix.py`
- **问题修复**: `auto_fix_issues.py`
- **依赖配置**: `config/requirements.txt`

## 🤝 技术支持

如遇问题，请：
1. 查看日志文件定位问题
2. 运行 `python run_single_audit.py` 进行诊断
3. 检查审计结果JSON文件
4. 查看系统汇总报告

## 📄 许可

本监控系统是PL5项目的一部分，随PL5项目一起发布。

---

**版本**: 1.0
**最后更新**: 2026-05-15
**维护者**: PL5开发团队
