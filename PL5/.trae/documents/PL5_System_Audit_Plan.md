# PL5系统全面审计与优化计划

## 一、审计目标

1. **智能机制一致性审计**：检查动态特征组在训练和预测中的使用是否一致
2. **日循环任务机制审计**：检查佐证链各步骤执行逻辑与实现是否正确
3. **进程守护机制审计**：修复误杀非PL5系统进程的问题
4. **启动脚本一致性审计**：确保所有启动脚本与最新系统同步
5. **系统端到端重新部署**：完成优化后进行全面测试

---

## 二、问题分析

### 2.1 动态特征组一致性问题（ISSUE-1）

**问题描述**：
- `DynamicFeatureValidator` 验证最佳特征配置并保存到 `logs/best_feature_config.json`
- 训练任务使用 `_get_best_feature_config()` 获取配置
- 预测任务也使用相同方法获取配置
- **潜在问题**：配置读取路径和时机可能存在不一致

**代码位置**：
- `src/core/features/dynamic_validator.py` - 动态特征验证器
- `src/app/auto_scheduler_v8.py` L892-924 - `_get_best_feature_config()` 方法
- `src/core/orchestrator.py` L481-550 - `execute_prediction_pipeline()` 方法

**涉及函数**：
| 函数 | 文件 | 问题 |
|------|------|------|
| `_get_best_feature_config()` | auto_scheduler_v8.py | 当配置文件不存在时，fallback逻辑可能导致不一致 |
| `execute_prediction_pipeline()` | orchestrator.py | 同时从LOGS_DIR和MODELS_DIR读取配置 |
| `validate_and_update_features()` | dynamic_validator.py | 同时保存到两个目录 |

### 2.2 日循环佐证链问题（ISSUE-2）

**问题描述**：
- 日循环包含14个任务，其中包含多次预测验证佐证
- 佐证任务：首次、二次、三次预测验证 + 深度策略优化 + 最终预测验证
- **潜在问题**：各佐证步骤实际执行可能存在逻辑不一致

**代码位置**：
- `src/app/auto_scheduler_v8.py` L1859-2012 - `_run_prediction_verification()` 统一验证执行器
- `src/app/analyze_and_send.py` L346-363 - 读取佐证链结果

### 2.3 进程误杀问题（ISSUE-3）

**问题描述**：
- `stop_pl5_processes.py` 和 `process_guardian.py` 使用 `PL5_IDENTIFIERS` 匹配进程
- 如果其他Python进程的命令行中恰好包含这些关键字，会被误杀

**当前标识符**：
```python
PL5_IDENTIFIERS = [
    'auto_scheduler_v8',
    'process_watchdog',
    'prevent_sleep',
    'pl5_intelligent_system',
    'start_system',
    'start_sentinel',
    'launch_simple',
]
```

**问题**：如 `start_system` 这样的通用词可能匹配到其他不相关的进程。

### 2.4 启动脚本一致性问题（ISSUE-4）

**涉及的启动脚本**：
| 脚本 | 启动方式 | 潜在问题 |
|------|----------|----------|
| `start_daemon.bat` | `pythonw -m src.app.auto_scheduler_v8` | 使用模块方式启动 |
| `start_pl5_reliable.bat` | `pythonw -m src.app.auto_scheduler_v8` | 相同 |
| `launch_system_reliable.py` | 直接调用 `auto_scheduler_v8` | 子进程启动 |
| `process_watchdog.py` | 直接启动 `auto_scheduler_v8.py` | 脚本方式 |

---

## 三、修复方案

### 3.1 修复动态特征组一致性问题

**修复内容**：
1. 统一配置读取逻辑，确保训练和预测使用完全相同的配置源
2. 在 `_get_best_feature_config()` 中增加配置缓存，避免重复读取
3. 确保配置保存和读取使用统一的格式

**修改文件**：`src/app/auto_scheduler_v8.py`

### 3.2 修复进程误杀问题

**修复内容**：
1. 将进程标识符改为更具体的组合条件
2. 增加额外验证逻辑：必须是Python进程 + 包含特定组合标识
3. 排除条件：包含外部项目路径的进程不应被杀死

**修改文件**：
- `src/utils/process_guardian.py`
- `scripts/deploy/stop_pl5_processes.py`

### 3.3 修复启动脚本一致性

**修复内容**：
1. 统一所有启动脚本使用模块方式启动 (`pythonw -m src.app.auto_scheduler_v8`)
2. 更新 `process_watchdog.py` 使用模块导入方式
3. 添加启动验证逻辑，确保进程启动成功

**修改文件**：
- `scripts/deploy/process_watchdog.py`
- `start_daemon.bat`
- 相关启动脚本

---

## 四、执行步骤

### 步骤1：创建审计文档
- 创建审计报告，记录所有发现的问题

### 步骤2：修复进程误杀问题
1. 修改 `process_guardian.py` 的 `_is_pl5_process()` 方法
2. 修改 `stop_pl5_processes.py` 的进程匹配逻辑
3. 测试验证修复效果

### 步骤3：修复动态特征组一致性问题
1. 检查 `DynamicFeatureValidator` 的配置保存逻辑
2. 统一 `auto_scheduler_v8.py` 中的配置读取逻辑
3. 确保 `orchestrator.py` 与调度器使用相同配置

### 步骤4：验证日循环佐证链
1. 检查各验证任务的配置读取是否一致
2. 验证佐证结果文件生成和读取逻辑

### 步骤5：统一启动脚本
1. 更新 `process_watchdog.py` 使用模块方式
2. 确保所有启动脚本使用一致的启动方式

### 步骤6：端到端重新部署
1. 停止所有现有PL5进程
2. 验证进程清理成功
3. 使用优化后的脚本重新启动系统
4. 检查系统运行状态
5. 执行冒烟测试验证

---

## 五、验证清单

- [ ] 进程守护不误杀非PL5进程
- [ ] 动态特征配置在训练和预测中一致
- [ ] 日循环佐证链各步骤正确执行
- [ ] 所有启动脚本使用一致的方式
- [ ] 系统成功启动并运行
- [ ] 冒烟测试通过
