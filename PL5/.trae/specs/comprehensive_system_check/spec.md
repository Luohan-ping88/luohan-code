# PL5系统全面排查 - Product Requirement Document

## Overview
- **Summary**: 对PL5 V10.0预测系统进行全面深入的排查，确保所有工作流程（数据获取、模型训练、预测分析、邮件发送）100%正常运行，无任何问题
- **Purpose**: 解决之前发现的邮件报告假数据、V10模块缺失、版本号不一致等问题，并全面验证系统的可靠性和稳定性
- **Target Users**: PL5预测系统的运维人员和最终用户

## Goals
- ✅ 验证所有定时任务正常配置和运行
- ✅ 确保数据获取流程完整无错误
- ✅ 验证模型训练流程（包含V10新模块）
- ✅ 确保预测生成真实结果（非均匀分布）
- ✅ 验证邮件发送功能正常
- ✅ 统一所有版本号为V10.0
- ✅ 确保错误处理机制完善
- ✅ 全面验证系统日志记录

## Non-Goals (Out of Scope)
- 开发新的预测算法
- 添加新的定时任务
- 修改用户界面
- 重构核心架构

## Background & Context
- 系统已升级到V10.0，新增了Mamba、iTransformer、Bayesian Uncertainty模块
- 之前发现的问题：邮件报告包含假数据、V10模块缺失、版本号不一致（V9.0/V8.0）
- 当前状态：调度器已重启，版本号已统一为V10.0，但需要全面验证

## Functional Requirements
- **FR-1**: 定时任务验证 - 确保所有定时任务（00:00数据获取、00:30评估、01:00优化、02:00训练、17:30邮件）正确配置
- **FR-2**: 数据获取验证 - 验证数据收集器能正确获取和更新历史数据
- **FR-3**: 模型训练验证 - 验证V10新模块（Mamba、iTransformer、Bayesian）能正常训练
- **FR-4**: 预测功能验证 - 验证预测器能生成真实的、非均匀分布的预测结果
- **FR-5**: 邮件发送验证 - 验证邮件能正常发送，包含真实数据
- **FR-6**: 版本号统一验证 - 确保所有模块显示V10.0
- **FR-7**: 错误处理验证 - 验证异常情况能正确处理并记录日志
- **FR-8**: 日志完整性验证 - 确保所有关键操作都有完整的日志记录

## Non-Functional Requirements
- **NFR-1**: 可靠性 - 系统能7x24小时稳定运行
- **NFR-2**: 可观测性 - 所有关键流程都有详细日志
- **NFR-3**: 可恢复性 - 出错后能自动或手动恢复
- **NFR-4**: 性能 - 模型训练时间控制在合理范围内

## Constraints
- **Technical**: 必须使用现有的代码库，不能引入重大架构变更
- **Business**: 不能影响17:30的定时邮件发送
- **Dependencies**: 依赖现有的配置文件和数据存储

## Assumptions
- 网络连接正常，能获取历史数据
- 邮件配置正确，能发送邮件
- 有足够的磁盘空间存储模型和日志
- Python环境和依赖包已正确安装

## Acceptance Criteria

### AC-1: 定时任务配置正确
- **Given**: 调度器已启动
- **When**: 检查调度器日志
- **Then**: 所有5个定时任务都显示[OK]且时间配置正确
- **Verification**: `programmatic`

### AC-2: 数据获取正常
- **Given**: 数据收集器已初始化
- **When**: 调用update_data()方法
- **Then**: 成功返回最新数据，data_version.json正确更新
- **Verification**: `programmatic`

### AC-3: V10模块训练成功
- **Given**: 有训练数据可用
- **When**: 执行模型训练
- **Then**: Mamba、iTransformer、Bayesian模块都成功训练并保存
- **Verification**: `programmatic`

### AC-4: 预测结果真实有效
- **Given**: 完整的V10模型已加载
- **When**: 执行预测
- **Then**: 预测结果不是均匀分布，权重包含所有6个模型
- **Verification**: `programmatic`

### AC-5: 邮件发送成功
- **Given**: 邮件配置正确
- **When**: 调用邮件发送功能
- **Then**: 邮件成功发送到指定邮箱，包含真实数据
- **Verification**: `human-judgment`

### AC-6: 版本号统一为V10.0
- **Given**: 系统已启动
- **When**: 检查所有版本号引用
- **Then**: 所有地方显示V10.0，无V9.0/V8.0
- **Verification**: `programmatic`

### AC-7: 错误处理完善
- **Given**: 模拟各种错误场景
- **When**: 错误发生
- **Then**: 系统能正确处理、记录日志并尽可能恢复
- **Verification**: `programmatic`

### AC-8: 日志记录完整
- **Given**: 系统运行中
- **When**: 执行各种操作
- **Then**: 所有关键操作都有详细的结构化日志
- **Verification**: `programmatic`

## Open Questions
- [ ] 是否需要立即执行一次完整的训练和预测验证？
- [ ] 是否需要检查备份机制是否正常？
- [ ] 是否需要验证性能监控功能？
