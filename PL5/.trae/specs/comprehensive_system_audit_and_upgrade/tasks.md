# Tasks

## 阶段一：动态特征组一致性审计与修复
- [x] Task 1: 审计动态特征验证结果持久化路径一致性
  - [x] SubTask 1.1: 检查 `dynamic_validator.py` 的保存路径（`models/best_feature_config.json`）
  - [x] SubTask 1.2: 检查 `auto_scheduler_v8.py` 的保存路径（`logs/best_feature_config.json`）
  - [x] SubTask 1.3: 统一两个路径，确保训练和预测读取同一配置
- [x] Task 2: 修复各模块特征配置读取逻辑
  - [x] SubTask 2.1: 修复 `orchestrator.py` 中 `execute_prediction_pipeline` 的 `best_feature_config.json` 读取路径
  - [x] SubTask 2.2: 修复 `analyze_and_send.py` 中预测时的特征工程调用，确保使用与训练一致的 `select_top` 和 `feature_selection_method`
  - [x] SubTask 2.3: 验证 `auto_scheduler_v8.py` 的 `_get_best_feature_config()` 和 `_save_feature_config()` 方法正确工作
- [x] Task 3: 验证动态特征组在端到端流程中的应用
  - [x] SubTask 3.1: 运行 `main.py train` 并检查 `logs/best_feature_config.json` 是否正确生成
  - [x] SubTask 3.2: 运行 `main.py predict` 并验证是否读取了相同的配置
  - [x] SubTask 3.3: 检查 `analyze_and_send` 是否使用了正确的特征配置

## 阶段二：日循环佐证链一致性审计与修复
- [x] Task 4: 审计佐证链任务注册与执行一致性
  - [x] SubTask 4.1: 验证 `auto_scheduler_v8._build_task_map()` 中 `first/second/third_prediction_verification` 是否映射到独立 handler
  - [x] SubTask 4.2: 验证 `_run_prediction_verification` 是否为每个轮次生成独立的输出文件
  - [x] SubTask 4.3: 验证 `setup_schedule` 中注册的佐证任务时间与 `scheduler_config_v8.json` 一致
- [x] Task 5: 修复佐证链结果读取与报告生成
  - [x] SubTask 5.1: 修复 `analyze_and_send.py` 中 `_format_verification_report` 函数，确保读取所有佐证文件
  - [x] SubTask 5.2: 验证佐证结果文件路径（`logs/first_prediction_verification.json` 等）与生成路径一致
  - [x] SubTask 5.3: 确保 `task_send_report` 在发送报告前所有佐证任务结果已就绪
- [x] Task 6: 验证日循环完整流程
  - [x] SubTask 6.1: 运行 `main.py schedule --once` 执行完整流程
  - [x] SubTask 6.2: 检查所有佐证结果文件是否正确生成
  - [x] SubTask 6.3: 验证报告邮件中是否包含所有佐证结果

## 阶段三：进程守护与启动脚本审计修复
- [x] Task 7: 审计所有进程匹配逻辑
  - [x] SubTask 7.1: 检查 `process_guardian.py` 的 `PL5_PROCESS_IDENTIFIERS` 列表是否完整
  - [x] SubTask 7.2: 检查 `start_system.py` 的 `PL5_IDENTIFIERS` 是否与 `process_guardian.py` 一致
  - [x] SubTask 7.3: 检查 `stop_service.bat` 的进程匹配逻辑是否正确
  - [x] SubTask 7.4: 检查 `deploy_end_to_end.bat` 的进程验证逻辑是否正确
- [x] Task 8: 统一进程标识符并修复误杀问题
  - [x] SubTask 8.1: 统一所有脚本中的 `PL5_IDENTIFIERS` / `PL5_PROCESS_IDENTIFIERS` 列表
  - [x] SubTask 8.2: 修复 `setup_windows_service.bat` 中 `manage_service.bat` 的进程停止命令
  - [x] SubTask 8.3: 验证 `process_guardian.stop_all_pl5_processes()` 只停止 PL5 进程
- [x] Task 9: 验证进程守护功能
  - [x] SubTask 9.1: 运行 `start_system.py` 并验证能正确检测已有 PL5 进程
  - [x] SubTask 9.2: 运行 `stop_service.bat` 并验证只停止 PL5 进程
  - [x] SubTask 9.3: 启动一个无关 Python 进程，验证不会被误杀

## 阶段四：部署脚本审计与修复
- [x] Task 10: 审计部署脚本路径一致性
  - [x] SubTask 10.1: 检查 `deploy.bat` 中 `config/requirements.txt` 路径是否正确
  - [x] SubTask 10.2: 检查 `deploy.bat` 中 `_audit_startup.py` 引用，替换为实际存在的脚本
  - [x] SubTask 10.3: 检查 `deploy.bat` 中 `main.py status` 是否可用
  - [x] SubTask 10.4: 检查 `setup_windows_service.bat` 中路径引用是否正确
- [x] Task 11: 修复部署脚本
  - [x] SubTask 11.1: 修复 `deploy.bat` 中的错误引用
  - [x] SubTask 11.2: 修复 `setup_windows_service.bat` 中的路径问题
  - [x] SubTask 11.3: 验证 `install_dependencies.bat` 的 `config/requirements.txt` 路径
- [x] Task 12: 验证部署脚本可执行性
  - [x] SubTask 12.1: 运行 `install_dependencies.bat` 验证依赖安装
  - [x] SubTask 12.2: 运行 `scripts/utility/smoke_test_v8.py` 验证系统状态
  - [x] SubTask 12.3: 验证 `main.py status` 命令输出正确

## 阶段五：端到端重新部署与系统重启
- [x] Task 13: 执行端到端部署
  - [x] SubTask 13.1: 运行 `deploy_end_to_end.bat` 或等效部署流程
  - [x] SubTask 13.2: 验证所有依赖正确安装
  - [x] SubTask 13.3: 验证 Windows 服务/计划任务正确配置
- [x] Task 14: 重启系统并验证运行状态
  - [x] SubTask 14.1: 停止现有 PL5 服务（使用修复后的 `stop_service.bat`）
  - [x] SubTask 14.2: 启动最新优化版系统（使用修复后的启动脚本）
  - [x] SubTask 14.3: 验证调度器正常运行（检查 `logs/scheduler_v8_status.json`）
  - [x] SubTask 14.4: 验证定时任务已正确注册（检查 `scheduler.log`）

## 阶段六：全面测试与验证
- [x] Task 15: 运行冒烟测试
  - [x] SubTask 15.1: 运行 `scripts/utility/smoke_test_v8.py`
  - [x] SubTask 15.2: 验证所有核心模块可导入
  - [x] SubTask 15.3: 验证训练流程可正常执行
- [x] Task 16: 运行端到端测试
  - [x] SubTask 16.1: 运行 `tests/e2e/test_full_pipeline.py`（如果存在）
  - [x] SubTask 16.2: 手动执行一次完整日循环流程验证
  - [x] SubTask 16.3: 验证预测结果和报告生成正常
- [x] Task 17: 生成最终审计报告
  - [x] SubTask 17.1: 汇总所有修复点
  - [x] SubTask 17.2: 验证所有 checklist 项目通过
  - [x] SubTask 17.3: 输出系统运行状态确认

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 5 depends on Task 4
- Task 6 depends on Task 5
- Task 8 depends on Task 7
- Task 9 depends on Task 8
- Task 11 depends on Task 10
- Task 12 depends on Task 11
- Task 14 depends on Task 13
- Task 16 depends on Task 14
- Task 17 depends on Task 15, Task 16
