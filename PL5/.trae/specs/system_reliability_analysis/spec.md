# 系统可靠性分析 - Product Requirement Document

## Overview
- **Summary**: 分析和优化系统的容错机制，确保定时任务在系统出现问题时仍能有效运行
- **Purpose**: 解决用户关于"系统出现问题时，定时任务是否无效了"的疑问
- **Target Users**: 系统管理员和用户

## Goals
- 分析当前系统的容错机制和可靠性
- 识别可能导致定时任务失效的问题
- 修复配置不一致问题
- 验证定时任务的可靠性

## Non-Goals (Out of Scope)
- 重构整个系统架构
- 新增大规模新功能
- 修改核心预测算法

## Background & Context
系统目前有多重容错机制：
1. TaskRetryManager - 任务失败自动重试（3次，指数退避）
2. TaskHistoryManager - 任务历史持久化
3. StructuredLogger - 结构化错误日志
4. ProcessGuardian - 进程守护，自动重启崩溃进程
5. ConfigSafeLoader - 配置安全加载

但发现配置不一致问题：
- guardian_config.json 配置的 main_script: "pl5_intelligent_system.py"
- 实际使用的主程序: "auto_scheduler_v8.py"

## Functional Requirements
- **FR-1**: 验证当前系统的容错机制是否正常工作
- **FR-2**: 修复 ProcessGuardian 配置指向正确的主程序
- **FR-3**: 确保定时任务在单个任务失败时不会中断整个流程
- **FR-4**: 提供系统可靠性状态检查工具

## Non-Functional Requirements
- **NFR-1**: 配置文件必须保持一致
- **NFR-2**: 任务失败时应有明确的错误日志
- **NFR-3**: 自动重启机制应在可配置的范围内工作

## Constraints
- **Technical**: 保持现有代码结构，只修复必要部分
- **Business**: 不影响现有定时任务的运行
- **Dependencies**: 依赖现有的 ProcessGuardian 和 auto_scheduler_v8

## Assumptions
- 系统使用 auto_scheduler_v8.py 作为主调度器
- 定时任务通过 schedule 库实现
- ProcessGuardian 可以被正常启用

## Acceptance Criteria

### AC-1: ProcessGuardian 配置修复
- **Given**: 系统存在 guardian_config.json
- **When**: 检查配置中的 main_script
- **Then**: 应该指向 "auto_scheduler_v8.py" 而非 "pl5_intelligent_system.py"
- **Verification**: `programmatic`

### AC-2: 任务重试机制验证
- **Given**: TaskRetryManager 已初始化
- **When**: 某个任务执行失败
- **Then**: 应该自动重试最多3次，使用指数退避策略
- **Verification**: `programmatic`

### AC-3: 定时任务独立性
- **Given**: 多个定时任务配置
- **When**: 单个任务失败
- **Then**: 不应影响其他任务的执行
- **Verification**: `programmatic`

### AC-4: 守护进程验证
- **Given**: ProcessGuardian 已配置正确
- **When**: 主进程意外崩溃
- **Then**: 守护进程应该在配置的时间内自动重启主进程
- **Verification**: `programmatic`

## Open Questions
- [ ] 用户是否需要启用 ProcessGuardian 守护进程？
- [ ] 是否需要创建一个简单的启动脚本来同时启动主程序和守护进程？
