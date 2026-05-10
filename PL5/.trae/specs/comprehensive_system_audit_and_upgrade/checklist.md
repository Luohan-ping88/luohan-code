# Checklist - PL5 系统全面审计、修复升级与端到端部署

## 阶段一：动态特征组一致性
- [x] `DynamicFeatureValidator.validate_and_update_features()` 同时保存到 `models/best_feature_config.json` 和 `logs/best_feature_config.json`
- [x] 两个路径的 JSON 内容一致（`best_config` 字段相同）
- [x] `auto_scheduler_v8._get_best_feature_config()` 优先读取 `logs/best_feature_config.json`
- [x] `auto_scheduler_v8._save_feature_config()` 保存到 `logs/best_feature_config.json`
- [x] `orchestrator.execute_prediction_pipeline` 优先读取 `logs/best_feature_config.json`，其次 `models/best_feature_config.json`
- [x] `orchestrator.execute_prediction_pipeline` 正确解析 JSON 格式（处理 `best_config` 嵌套）
- [x] `analyze_and_send` 预测时使用与训练一致的 `select_top` 和 `feature_selection_method`
- [x] 所有模块在配置不存在时回退到默认配置

## 阶段二：日循环佐证链一致性
- [x] `auto_scheduler_v8._build_task_map()` 中 `first_prediction_verification` 映射到独立 handler
- [x] `auto_scheduler_v8._build_task_map()` 中 `second_prediction_verification` 映射到独立 handler
- [x] `auto_scheduler_v8._build_task_map()` 中 `third_prediction_verification` 映射到独立 handler
- [x] `_run_prediction_verification` 为每个轮次生成独立的输出文件
- [x] `first_prediction_verification.json` 文件正确生成
- [x] `second_prediction_verification.json` 文件正确生成
- [x] `third_prediction_verification.json` 文件正确生成
- [x] `setup_schedule` 中佐证任务时间与 `scheduler_config_v8.json` 完全一致
- [x] `analyze_and_send._format_verification_report` 读取所有佐证文件
- [x] 报告邮件中包含首次/二次/三次佐证结果

## 阶段三：进程守护与启动脚本
- [x] `process_guardian.py` 的 `PL5_PROCESS_IDENTIFIERS` 包含所有 PL5 相关标识符
- [x] `start_system.py` 的 `PL5_IDENTIFIERS` 与 `process_guardian.py` 完全一致
- [x] `stop_service.bat` 的进程匹配逻辑使用精确匹配（python + PL5标识符）
- [x] `deploy_end_to_end.bat` 的进程验证逻辑使用精确匹配
- [x] `setup_windows_service.bat` 生成的 `manage_service.bat` 使用精确匹配停止进程
- [x] 启动脚本检测到外部 Python 进程时不会误报为 PL5 进程
- [x] 停止脚本不会终止外部 Python 进程（如 Jupyter、其他项目）

## 阶段四：部署脚本一致性
- [x] `deploy.bat` 中 `config/requirements.txt` 路径正确
- [x] `deploy.bat` 不引用不存在的 `_audit_startup.py`
- [x] `deploy.bat` 中状态检查命令可用
- [x] `install_dependencies.bat` 正确查找 `config/requirements.txt`
- [x] `setup_windows_service.bat` 中路径引用正确
- [x] 所有部署脚本中的 Python 路径检测逻辑正确

## 阶段五：端到端部署与重启
- [x] 依赖安装成功完成
- [x] 冒烟测试通过
- [x] 系统状态检查正常
- [x] 停止现有服务成功
- [x] 启动新服务成功
- [x] 调度器状态文件正常更新
- [x] 定时任务正确注册

## 阶段六：全面测试验证
- [x] `scripts/utility/smoke_test_v8.py` 运行通过
- [x] 核心模块可正常导入（`src.app.auto_scheduler_v8`, `src.core.models.enhanced_predictor` 等）
- [x] `main.py train` 可正常执行
- [x] `main.py predict` 可正常执行
- [x] `main.py schedule --once` 可正常执行完整流程
- [x] 所有佐证结果文件在单次流程后生成
- [x] 系统日志无 ERROR 级别错误
- [x] 最终审计报告已生成
