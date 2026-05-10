# 系统版本统一与架构清理 Spec

## Why
系统存在严重的版本混乱问题：V8/V9/V10三个版本的预测器共存，多个入口文件(main.py、pl5_intelligent_system.py、auto_scheduler_v8.py、analyze_and_send.py)调用不同版本的预测器，导致：
1. 用户不清楚系统实际使用的是哪个版本
2. 训练/预测/邮件发送可能使用不同的预测器，结果不一致
3. V10新增的Mamba/iTransformer/Bayesian模块可能未被实际调用
4. 模型文件(pl5_predictor_v8.pkl 27.7MB vs enhanced_predictor_v9.pkl 5.8MB)并存

## What Changes
- **明确版本体系**：定义V10为唯一主预测器，V8/V9标记为legacy
- **统一入口**：main.py作为唯一入口，所有子命令(train/predict/analyze/schedule/status)使用EnhancedPL5Predictor(V10)
- **清理冗余文件**：predictor_v9.py等重复实现文件标记为deprecated
- **更新调度器**：auto_scheduler_v8.py确保使用EnhancedPL5Predictor(V10)
- **更新邮件发送**：analyze_and_send.py确保使用EnhancedPL5Predictor(V10)
- **模型文件迁移**：训练后只保存V10模型文件

## Impact
- Affected specs: 无
- Affected code:
  - main.py (已优化)
  - pl5_intelligent_system.py (需确认预测器版本)
  - auto_scheduler_v8.py (需确认task_train使用的预测器)
  - analyze_and_send.py (已优化)
  - src/core/models/predictor_v9.py (标记deprecated)

## ADDED Requirements
### Requirement: 统一版本入口
系统SHALL提供唯一的入口main.py，所有操作(train/predict/analyze/schedule/status)均通过main.py执行。

#### Scenario: 用户执行训练
- **WHEN** 用户运行 `python main.py train`
- **THEN** 系统使用EnhancedPL5Predictor(V10)进行训练，包含Mamba+iTransformer+Bayesian新模块

#### Scenario: 用户查看状态
- **WHEN** 用户运行 `python main.py status`
- **THEN** 显示当前使用的预测器版本为V10.0，并列出6个模型的启用状态

### Requirement: 版本兼容性说明
系统SHALL在文档中清晰说明V8→V9→V10的演进关系，以及各版本的区别。

## MODIFIED Requirements
### Requirement: 调度器任务流程
auto_scheduler_v8.py的task_train()方法SHALL使用EnhancedPL5Predictor(V10)而非PL5Predictor(V8)。
