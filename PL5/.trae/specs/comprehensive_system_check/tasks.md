# PL5系统全面排查 - The Implementation Plan (Decomposed and Prioritized Task List)

## [ ] Task 1: 定时任务配置与运行状态验证
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 验证调度器正在运行且显示V10.0
  - 检查所有5个定时任务配置是否正确
  - 确认定时任务时间设置准确
- **Acceptance Criteria Addressed**: [AC-1]
- **Test Requirements**:
  - `programmatic` TR-1.1: 调度器进程正在运行
  - `programmatic` TR-1.2: 调度器日志显示V10.0
  - `programmatic` TR-1.3: 所有5个定时任务都显示[OK]
  - `programmatic` TR-1.4: 邮件发送时间设置为17:30
- **Notes**: 使用Get-Process检查进程状态，检查日志文件验证配置

## [ ] Task 2: 数据获取流程验证
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 验证数据收集器能正常工作
  - 检查数据版本管理机制
  - 验证数据更新功能
- **Acceptance Criteria Addressed**: [AC-2]
- **Test Requirements**:
  - `programmatic` TR-2.1: 数据收集器能成功初始化
  - `programmatic` TR-2.2: update_data()方法能正常执行
  - `programmatic` TR-2.3: data_version.json文件存在且内容正确
  - `programmatic` TR-2.4: 历史数据文件存在且格式正确
- **Notes**: 创建测试脚本验证数据获取流程

## [ ] Task 3: V10模块训练与保存验证
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 验证Mamba模块能正常训练
  - 验证iTransformer模块能正常训练
  - 验证Bayesian模块能正常初始化
  - 确认所有模块能正确保存到模型文件
- **Acceptance Criteria Addressed**: [AC-3]
- **Test Requirements**:
  - `programmatic` TR-3.1: Mamba预测器能成功初始化和训练
  - `programmatic` TR-3.2: iTransformer预测器能成功初始化和训练
  - `programmatic` TR-3.3: Bayesian量化器能成功初始化
  - `programmatic` TR-3.4: 所有V10模块都能正确保存到enhanced_predictor_v9.pkl
  - `programmatic` TR-3.5: 模型文件大小合理，包含所有6个模型
- **Notes**: 运行一次完整训练，检查模型文件内容

## [ ] Task 4: 预测功能与结果验证
- **Priority**: P0
- **Depends On**: Task 3
- **Description**: 
  - 验证模型能正确加载
  - 验证预测结果不是均匀分布
  - 验证所有6个模型权重都在使用中
- **Acceptance Criteria Addressed**: [AC-4]
- **Test Requirements**:
  - `programmatic` TR-4.1: load_models()能成功加载完整模型
  - `programmatic` TR-4.2: 所有V10模块正确恢复
  - `programmatic` TR-4.3: 预测概率分布不是均匀的[0.1]*10
  - `programmatic` TR-4.4: weights_used包含所有6个模型
  - `programmatic` TR-4.5: fallback为false，error字段正常
- **Notes**: 创建测试脚本加载模型并生成预测

## [ ] Task 5: 邮件发送功能验证
- **Priority**: P1
- **Depends On**: Task 4
- **Description**: 
  - 验证邮件配置正确
  - 验证邮件模板正确使用真实数据
  - 验证邮件能成功发送
- **Acceptance Criteria Addressed**: [AC-5]
- **Test Requirements**:
  - `programmatic` TR-5.1: email_config.json配置正确
  - `programmatic` TR-5.2: analyze_and_send.py能正确执行
  - `programmatic` TR-5.3: report_info.json包含真实数据
  - `human-judgement` TR-5.4: 邮件能成功发送到指定邮箱
  - `human-judgement` TR-5.5: 邮件内容包含真实预测结果
- **Notes**: 可使用测试邮件功能验证，不影响正式发送

## [ ] Task 6: 版本号统一验证
- **Priority**: P1
- **Depends On**: None
- **Description**: 
  - 全面搜索所有代码中的版本号引用
  - 确保所有地方都显示V10.0
- **Acceptance Criteria Addressed**: [AC-6]
- **Test Requirements**:
  - `programmatic` TR-6.1: main.py显示V10.0
  - `programmatic` TR-6.2: auto_scheduler_v8.py显示V10.0
  - `programmatic` TR-6.3: enhanced_predictor.py显示V10.0
  - `programmatic` TR-6.4: 训练信息中的model_version为V10.0
  - `programmatic` TR-6.5: 无任何V9.0或V8.0引用
- **Notes**: 使用Grep工具全面搜索代码库

## [ ] Task 7: 错误处理机制验证
- **Priority**: P1
- **Depends On**: None
- **Description**: 
  - 验证各种错误场景的处理
  - 检查日志记录完整性
  - 验证fallback机制
- **Acceptance Criteria Addressed**: [AC-7]
- **Test Requirements**:
  - `programmatic` TR-7.1: 模型缺失时正确返回fallback
  - `programmatic` TR-7.2: 训练失败时有完整错误日志
  - `programmatic` TR-7.3: 预测异常时有详细记录
  - `programmatic` TR-7.4: unified_error_handler能正常工作
- **Notes**: 创建测试脚本模拟各种错误场景

## [ ] Task 8: 日志完整性验证
- **Priority**: P1
- **Depends On**: None
- **Description**: 
  - 验证所有关键操作都有日志
  - 检查结构化日志格式
  - 验证日志轮转机制
- **Acceptance Criteria Addressed**: [AC-8]
- **Test Requirements**:
  - `programmatic` TR-8.1: 数据获取有完整日志
  - `programmatic` TR-8.2: 模型训练有详细进度
  - `programmatic` TR-8.3: 预测执行有记录
  - `programmatic` TR-8.4: 邮件发送有日志
  - `programmatic` TR-8.5: 日志按日期正确分割
- **Notes**: 检查日志文件内容和格式

## [ ] Task 9: 完整端到端流程测试
- **Priority**: P0
- **Depends On**: Tasks 1-8
- **Description**: 
  - 执行一次完整的端到端流程验证
  - 从数据获取到邮件发送完整测试
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8]
- **Test Requirements**:
  - `programmatic` TR-9.1: 端到端流程能完整执行
  - `programmatic` TR-9.2: 所有中间步骤成功
  - `human-judgement` TR-9.3: 最终邮件包含真实数据
- **Notes**: 使用--once选项执行单次完整流程
