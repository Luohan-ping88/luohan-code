# PL5 系统全面审计、修复升级与端到端部署 Spec

## Why

当前 PL5 系统经过多轮优化后，存在以下关键一致性和部署问题：
1. **智能动态特征组机制一致性**：`DynamicFeatureValidator` 验证的最佳特征配置与 `auto_scheduler_v8`、`analyze_and_send`、`orchestrator` 等模块的预测/训练流程之间存在调用路径不一致，部分模块未实际应用动态验证结果。
2. **日循环佐证链实际执行问题**：`setup_schedule` 中注册了 14 步完整佐证链，但部分佐证任务（如 `second_prediction_verification`、`third_prediction_verification`）在 `task_map` 中映射到同一 handler，缺乏真正的独立执行逻辑；且 `analyze_and_send` 读取佐证结果文件时未与训练流程保持同步。
3. **进程守护误杀外部进程**：`process_guardian.py` 和 `start_system.py` 的进程匹配逻辑虽然已修复为精确匹配，但需审计所有启动/停止脚本是否统一应用了此修复。
4. **启动脚本与最新系统不一致**：`deploy.bat`、`setup_windows_service.bat`、`install_dependencies.bat` 等脚本中引用的路径（如 `config/requirements.txt`、`main.py status`、`_audit_startup.py`）与当前实际目录结构不一致，导致部署失败。

## What Changes

- **审计并修复动态特征组应用一致性**：确保 `DynamicFeatureValidator.validate_and_update_features()` 的结果被所有训练和预测流程统一读取和使用。
- **审计并修复日循环佐证链实际执行**：确保 `first/second/third_prediction_verification` 有独立的执行逻辑和结果文件，且 `analyze_and_send` 正确读取所有佐证结果。
- **审计并修复进程守护/启动脚本**：统一所有启动/停止脚本中的进程匹配逻辑，确保不误杀外部 Python 进程。
- **审计并修复部署脚本**：修正 `deploy.bat`、`setup_windows_service.bat`、`install_dependencies.bat` 等脚本中的路径和命令，使其与当前系统保持一致。
- **端到端重新部署与重启**：在修复完成后，执行完整的端到端部署流程，并重启系统以验证最新优化版正常运行。
- **全面测试验证**：运行冒烟测试和端到端测试，验证所有修复生效。

## Impact

- Affected specs: `model_comprehensive_optimization`, `scheduler_timing_fix`, `comprehensive_project_review`
- Affected code:
  - `src/core/features/dynamic_validator.py` - 动态特征验证
  - `src/app/auto_scheduler_v8.py` - 调度器佐证链
  - `src/app/analyze_and_send.py` - 报告生成
  - `src/core/orchestrator.py` - 编排器预测流程
  - `src/utils/process_guardian.py` - 进程守护
  - `start_system.py` - 启动脚本
  - `stop_service.bat` - 停止脚本
  - `scripts/deploy/deploy.bat` - 部署脚本
  - `scripts/deploy/setup_windows_service.bat` - 服务设置
  - `scripts/deploy/install_dependencies.bat` - 依赖安装
  - `main.py` - 主入口

## ADDED Requirements

### Requirement: 动态特征组一致性保障
系统 SHALL 确保 `DynamicFeatureValidator` 验证出的最佳特征配置被训练、预测、报告生成等所有流程一致应用。

#### Scenario: 训练时应用最佳特征配置
- **WHEN** `auto_scheduler_v8` 执行 `task_train` 或 `task_incremental_train`
- **THEN** 必须调用 `_get_best_feature_config()` 获取动态验证结果
- **AND** 将配置传递给 `FeatureEngineer.extract_all_features(select_top=..., feature_selection_method=...)`
- **AND** 保存配置到 `logs/best_feature_config.json` 供预测使用

#### Scenario: 预测时应用最佳特征配置
- **WHEN** `orchestrator.execute_prediction_pipeline` 或 `analyze_and_send` 执行预测
- **THEN** 优先读取 `logs/best_feature_config.json` 或 `models/best_feature_config.json`
- **AND** 使用与训练时一致的 `select_top` 和 `feature_selection_method`
- **AND** 若配置不存在，回退到全量特征（`select_top=None`）并使用 `predictor.feature_cols` 对齐

#### Scenario: 动态验证结果持久化
- **WHEN** `DynamicFeatureValidator.validate_and_update_features()` 完成
- **THEN** 结果必须同时保存到 `models/best_feature_config.json` 和 `logs/best_feature_config.json`
- **AND** 两个路径的内容必须保持一致

### Requirement: 日循环佐证链独立执行
系统 SHALL 确保日循环中的首次、二次、三次预测验证有独立的执行逻辑和结果文件。

#### Scenario: 独立佐证任务执行
- **WHEN** `task_first_prediction_verification`、`task_second_prediction_verification`、`task_third_prediction_verification` 被调用
- **THEN** 每个任务必须调用 `_run_prediction_verification` 并传入独立的 `output_file`
- **AND** 每个任务生成独立的 JSON 结果文件（`first_prediction_verification.json`、`second_prediction_verification.json`、`third_prediction_verification.json`）

#### Scenario: 佐证结果被报告模块读取
- **WHEN** `analyze_and_send` 生成报告
- **THEN** 必须读取所有佐证结果文件（首次/二次/三次/最终/深度策略）
- **AND** 在报告中正确展示各轮次佐证结果

### Requirement: 进程守护精确匹配
系统 SHALL 确保所有启动/停止脚本只匹配并操作 PL5 系统进程，不误杀外部 Python 进程。

#### Scenario: 启动时检测已有进程
- **WHEN** `start_system.py` 或其他启动脚本运行
- **THEN** 使用 `is_pl5_process()` 精确匹配（必须同时包含 `python` 和 PL5 标识符）
- **AND** 只检测/停止属于 PL5 的进程

#### Scenario: 停止服务时安全终止
- **WHEN** `stop_service.bat` 或 `process_guardian.stop_all_pl5_processes()` 执行
- **THEN** 只终止命令行中包含 PL5 标识符的 Python 进程
- **AND** 外部 Python 进程（如 Jupyter、其他项目）不受影响

### Requirement: 部署脚本与当前系统一致
系统 SHALL 确保所有部署脚本中的路径和命令与当前实际目录结构一致。

#### Scenario: 依赖安装脚本
- **WHEN** `install_dependencies.bat` 执行
- **THEN** 正确查找 `config/requirements.txt` 或根目录 `requirements.txt`
- **AND** 安装命令正确执行

#### Scenario: 部署脚本
- **WHEN** `deploy.bat` 执行
- **THEN** 不引用不存在的文件（如 `_audit_startup.py`）
- **AND** `main.py status` 命令可用（或替换为正确的状态检查方式）
- **AND** 路径引用正确（`config/requirements.txt`）

## MODIFIED Requirements

### Requirement: 统一特征配置读取路径
所有模块 SHALL 从统一的路径读取最佳特征配置。

- **修改文件**: `src/app/auto_scheduler_v8.py`, `src/app/analyze_and_send.py`, `src/core/orchestrator.py`
- **配置路径**: 优先 `logs/best_feature_config.json`，其次 `models/best_feature_config.json`
- **向后兼容**: 若都不存在，使用默认配置 `{'select_top': 100, 'feature_selection_method': 'rfe'}`

### Requirement: 统一进程标识符列表
所有涉及进程检测/停止的脚本 SHALL 使用统一的 PL5 进程标识符列表。

- **统一标识符**: `['auto_scheduler_v8', 'process_watchdog', 'prevent_sleep', 'pl5_intelligent_system', 'start_system', 'start_sentinel', 'launch_simple']`
- **应用文件**: `src/utils/process_guardian.py`, `start_system.py`, `stop_service.bat`, `deploy_end_to_end.bat`

## REMOVED Requirements

### Requirement: 旧版启动脚本引用
**原因**: `deploy.bat` 中引用的 `_audit_startup.py` 不存在，`main.py status` 在当前环境中可能不可用。
**迁移**: 将 `_audit_startup.py` 替换为实际存在的冒烟测试脚本（如 `scripts/utility/smoke_test_v8.py`），或将 `main.py status` 替换为直接检查文件/进程状态。
