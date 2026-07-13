# PL5系统全面审计与优化 Spec

## Why
用户对系统进行全面审计，发现三大类问题：(1) 工作流程、训练逻辑、代码质量及一致性存在多处缺陷；(2) 智能机制和日循环机制的一致性存在问题（动态特征组应用不一致、佐证步骤执行不完整、进程保护误杀外部进程）；(3) 启动脚本与最新系统不完全一致。需要全面修复升级并重新部署。

## What Changes

### 修复 BUG-F01: 进程保护误杀外部Python进程
**严重性: 高**
- `stop_service.bat` 验证代码（第37-52行）只检查 `has_path` 但不检查 `has_module_mode`，导致模块方式启动的PL5进程无法被正确识别
- `start_daemon.bat` 初始检查（第25-46行）和验证检查（第131-159行）只检查标识符但不验证项目路径，可能误判外部Python进程

### 修复 BUG-F02: 日循环佐证步骤结果未正确传递
**严重性: 高**
- `task_send_report` 中读取了佐证文件到 `all_verification_results`，但该变量从未被使用，`analyze_and_send()` 自行从磁盘读取，存在竞态条件
- `task_send_report` 中 `verification_files` 定义的结果 key 与 `analyze_and_send` 中 `_format_verification_report` 期望的 key 不一致

### 修复 BUG-F03: 预测任务特征引擎不一致
**严重性: 中**
- `task_prediction_preview` 使用 `FeatureEngineerV9` 而训练和其他任务使用 `FeatureEngineer`，导致特征不一致

### 修复 BUG-F04: 配置时间不一致
**严重性: 低**
- `scheduler_config_v8.json` 中 `evaluation_time: "21:30"` 但 `setup_schedule()` 默认 `22:15`
- 部署脚本中的定时任务列表与实际配置不一致

### 修复 BUG-F05: `task_send_report` 佐证结果未实际存储
**严重性: 中**
- `task_send_report` 第1311-1331行循环读取佐证文件，但 `_res` 变量赋值后未存入 `all_verification_results` 字典

### 修复 BUG-F06: `deploy_end_to_end.bat` 验证逻辑不完整
**严重性: 中**
- 内联Python验证代码（第71-107行）只检查 `has_path` 不检查 `has_module_mode`

## Impact
- 受影响模块: 进程管理、日循环佐证链、特征工程、调度配置、部署脚本
- 受影响文件: `stop_service.bat`, `start_daemon.bat`, `deploy_end_to_end.bat`, `auto_scheduler_v8.py`
- **非BREAKING**：所有修复向后兼容

## MODIFIED Requirements

### Requirement: 进程保护机制
系统 SHALL 使用三重匹配规则（Python进程 + PL5标识符 + 项目路径或模块模式）来识别PL5进程，确保不误杀外部Python进程。

#### Scenario: 停止PL5进程
- **WHEN** 用户执行 stop_service.bat
- **THEN** 所有PL5进程被安全终止，外部Python进程不受影响
- **AND** 验证逻辑同时支持文件路径模式和模块启动模式

### Requirement: 日循环佐证链
系统 SHALL 在 send_report 任务中正确收集并传递所有佐证步骤的结果，确保报告包含完整的佐证链数据。

#### Scenario: 发送报告
- **WHEN** send_report 任务执行
- **THEN** 所有佐证结果（首次/二次/三次验证、最终预测验证、深度策略优化）被正确收集
- **AND** 佐证结果被传递给 analyze_and_send() 函数

### Requirement: 特征工程一致性
系统 SHALL 在所有预测和训练任务中使用相同的特征引擎，确保特征维度一致。

#### Scenario: 预测预生成
- **WHEN** prediction_preview 任务执行
- **THEN** 使用与训练一致的 FeatureEngineer（而非 FeatureEngineerV9）

## REMOVED Requirements
**无**
