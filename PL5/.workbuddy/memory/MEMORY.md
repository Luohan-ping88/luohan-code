# PL5 工作记忆

## 优化建议堆积修复 (2026-05-09)

### 根因分析
- **suggestion_history.json 实际记录**: 80条（非1816条），每类4种建议各重复20次
- **根因**: `_persist_suggestions()` 仅按 ID 去重，相同内容生成新 UUID 后重复追加
- **无 auto-apply 机制**: `apply_suggestion` 和 `auto_apply_suggestions` 方法不存在

### 修复项
1. **`src/core/self_learning.py` `_persist_suggestions()`** — 内容级去重（按 category+参数名+推荐值）
2. **`src/core/self_learning.py` 新增 `apply_suggestion()`** — 应用单条建议，更新 model_config.yaml
3. **`src/core/self_learning.py` 新增 `auto_apply_suggestions()`** — 批量自动应用（conf≥0.55, prio≤2）
4. **`src/core/self_learning.py` 新增 `_suggestion_key()`** — 内容唯一标识生成器
5. **`src/core/config.py` 验证器** — `max_depth` 验证从 `isinstance(v,int)` 改为 `isinstance(v,(int,float))`

### 执行结果（2026-05-09）
| 建议 | 原值 | 应用值 | 状态 |
|------|------|--------|------|
| max_depth | 3 | 10 | ✅ APPLIED |
| learning_rate | 0.1 | 0.06 | ✅ APPLIED |
| stability_regularization | — | — | ✅ APPLIED |
| performance_fine_tuning | — | — | ✅ APPLIED |

### suggestion_history.json 最终状态
- 总记录: 4条（去重后，原80条）
- applied: 4, pending: 0
- 备份: `backups/suggestion_cleanup/suggestion_history_backup_20260509_073344.json`

### model_config.yaml 最终参数
- `stacking.base_config.max_depth: 10` (原3)
- `stacking.base_config.learning_rate: 0.06` (原0.1)

### 注意事项
- `stability_regularization` 和 `performance_fine_tuning` 无具体参数，无实际配置变更
- `apply_suggestion` 使用 `ModelConfig.set("stacking.base_config.{param}", val)` + `save()` 写入 YAML
- `max_depth` 写入前 `round()` 取整，validator 已兼容 float



### 审计范围
`scripts/launcher.bat` / `start.bat` / `start_daemon.bat` / `start_pl5_foreground.bat` / `start_pl5_reliable.bat` / `scripts/deploy/deploy.bat`

### 修复项 (共9处)
| 文件 | 问题 | 修复 |
|------|------|------|
| `scripts/launcher.bat` | V10.0版本号、mkdir src\models错误、无监控文件检查 | V10.1、删除、添加exists检查 |
| `start.bat` | V10.0版本号 | V10.1 |
| `start_daemon.bat` | V10.0版本号、无监控文件检查 | V10.1、添加exists检查 |
| `start_pl5_foreground.bat` | 硬编码路径`E:\PL5` | 改为`%~dp0` |
| `start_pl5_reliable.bat` | 硬编码路径`E:\PL5` | 改为`%~dp0` |
| `scripts/deploy/deploy.bat` | `src\ai\api.py`不存在、`main.py --action status`格式错误、`pytest`非必须 | 替换为`_audit_startup.py`、正确命令`python main.py status` |
| `main.py` | 6处V10.0版本号 | 全部更新为V10.1 |
| `src/app/auto_scheduler_v8.py` | V8.0版本描述 | V10.1 |

### 验证结果
- 所有导入链测试通过 (IntelligentWorkflowOrchestrator / IntelligentTimeScheduler / EnhancedPL5Predictor / PL5DataCollector / FeatureEngineer)
- 核心路径正确 (BASE_DIR=E:\PL5)
- 所有监控模块文件存在
- 系统已重新部署，PID=11536，运行正常

### BUG修复：rollback.py 误杀所有 Python 进程 (2026-04-22)
- **文件**: `scripts/deploy/rollback.py` 第361行
- **问题**: `subprocess.run(['taskkill', '/F', '/IM', 'python.exe'])` 无差别杀死系统上所有 python.exe 进程（包括 IDE、Jupyter 等）
- **修复**: 新增 `_kill_pl5_processes()` 方法，精确识别 PL5 进程（工作目录+关键词双重过滤），仅杀死目标进程
- **主路径**（有 psutil）: `cwd.startswith(PROJECT_ROOT)` + 关键词匹配
- **Fallback**（无 psutil）: `wmic process` 获取命令行，精确过滤后 `taskkill /PID`

## 系统基本信息

- **系统名称**: PL5 排列五高阶数理分析预测系统
- **版本**: V10.3 (2026-05-01 第四轮全面审计 + 11项修复)
- **工作目录**: `e:\PL5`
- **用户**: Administrator (Windows)

## 2026-05-01 第四轮全面审计 — 修复11项BUG

### BUG-1（中）：setup_schedule 默认时间与配置文件不一致
- `optimization_start` 默认 "02:30"，配置实际 "22:45"
- `training_start` 默认 "04:00"，配置实际 "00:30"
- **修复**：改为与配置文件一致

### BUG-2（中）：_dynamic_task_adjustment 默认 evaluation_time 错误
- 默认 "21:30"，配置实际 "22:15"
- **修复**：改为 "22:15"

### BUG-3（高）：main.py 版本号 V10.1 未更新
- 文件头、5处输出、`model_version`、parser description 均为 V10.1
- **修复**：全部更新为 V10.3

### BUG-4（中）：src/core/orchestrator.py 使用旧 PL5Predictor
- 默认组件使用旧版 Predictor，系统其他部分使用 EnhancedPL5Predictor
- **修复**：改为 EnhancedPL5Predictor

### BUG-5（脚本版本不一致）：8个启动/部署脚本版本号
- 全部 V10.0/V10.1/V3.0 → 统一 V10.3

### BUG-6（低）：DynamicFeatureValidator 使用 load_processed_data
- **修复**：改为 update_data()，确保最新数据验证

### BUG-7（进程误杀已确认安全）
- 所有进程管理脚本（rollback/stop_pl5/process_guardian/process_watchdog）均使用严格三重匹配
- 无裸 taskkill /IM python.exe 调用
- ✅ 安全

## 智能机制和日循环一致性审计

### 动态特征组应用 ✅
- best_feature_config.json 双目录保存，统一读取
- select_top=None（全量特征最优，2026-05-01验证）

### 佐证链执行 ✅
- 三个佐证独立 handler，独立输出文件
- setup_schedule 完整注册 10:00/13:00/15:00 三次佐证
- task_send_report 集成所有验证结果

## 当前数据状态 (2026-05-08)

- **最新期号**: 2026118（2026-05-08开奖）
- **历史数据量**: 7593 条
- **数据文件**: `data/raw/pl5_history.txt`, `data/processed/pl5_processed.csv`
- **版本文件**: `models/data_version.json`（`latest_period: "2026118"`, `record_count: 7593`）
- **best_feature_config**: select_top=None（全量特征最优）
- **模型文件**: `enhanced_predictor_v10.pkl`（2026-05-08 14:14更新，5.6MB）

### 遗留优化建议（需人工决策）
- 4条优化建议长期pending，共1816条历史记录堆积
  - max_depth: 12 → 9.6（重要，置信50%）
  - learning_rate: 0.1 → 0.06（重要，置信50%）
  - 正则化增强（重要，置信55%）
  - 模型微调（常规，置信60%）



## 技术栈

- Python 3.12, NumPy 2.4.3, Pandas 2.2.2, SciPy 1.17.1
- scikit-learn 1.8.0, hmmlearn 0.3.3, joblib 1.4.2
- 加速: C++模块使用Python fallback (pl5_core.py), C++ .pyd有Access Violation风险已禁用

## 架构

7层: core(算法) / app(调度+邮件) / monitor(监控) / cpp_core(加速) / scripts(启动) / config(配置) / root proxy(core/)

## 最新数据状态 (2026-04-22 修正)

- **最新期号**: 2026101（2026-04-21开奖）
- **历史数据量**: 7576 条
- **数据文件**: `data/raw/pl5_history.txt`, `data/processed/pl5_processed.csv`
- **版本文件**: `models/data_version.json`（`latest_period: "2026101"`, `record_count: 7576`）
- **注意**: pl5_processed.csv 含 `parse_line` 列（顺序行号1~7576），**勿与 period 列混淆**

## 2026-04-22 深度专项审计 — 修复4项不一致

### ISSUE-D1（关键）：orchestrator 未读取 best_feature_config.json
- `DynamicFeatureValidator` 测试6种特征组配置，保存最优到 `best_feature_config.json`
- 但 `orchestrator.execute_prediction_pipeline` 从未读取 → 动态验证闭环未生效
- **修复**：在 `execute_prediction_pipeline` 和 `_stage_report_generation` 特征提取前新增读取逻辑

### ISSUE-D2（中等）：scheduler 任务函数特征处理不一致
- 任务函数用全量 `feature_cols` + `features[pos].iloc[-10:]`（非原始data）
- **修复**：重构为 `_run_prediction_verification()` 统一执行器，与 orchestrator 完全一致

### ISSUE-V1（高）：三次佐证共享同一handler互相覆盖
- `first/second/third_prediction_verification` 三个任务都指向同一 handler
- 都写入 `first_prediction_verification.json`，后两次覆盖前次
- **修复**：拆分为三个独立 handler，各写独立 JSON 文件

### ISSUE-V2（中等）：佐证链结果未纳入最终报告
- `analyze_and_send()` 独立执行，从不读取佐证链结果
- **修复**：新增 `_format_verification_report()`，在报告【三、佐证链验证结果】展示验证信息

### 特征提取路径（修复后已完全统一）
所有预测路径均使用 `extract_all_features(df, select_top=None)` + `predictor.feature_cols`（76个）：
- orchestrator `execute_prediction_pipeline` ✅
- orchestrator `_stage_report_generation` ✅
- main.py `cmd_predict` ✅
- scripts/utility/generate_prediction.py ✅
- strategy_evaluator.py ✅
- scheduler 任务函数（`_run_prediction_verification`等）✅

## 2026-04-22 深度全面审计 — 修复10项BUG

### auto_scheduler_v8.py（6项）
- BUG-1（高危）：`execute_with_retry` 重试退避逻辑 — increment_count移到sleep之前
- BUG-2（高危）：`__init__` 未初始化 `custom_tasks`/`task_map` → 新增 `_build_task_map()`
- BUG-3（高危）：`task_train` while循环无上界 → 增加 MAX_EXTRA_ROUNDS=3 + max_training_hours=10.0
- BUG-4（中）：`training_info` numpy.int64 JSON序列化失败 → `str(df['period'].iloc[-1])`
- BUG-5（高危）：`task_send_report` 同步阻塞调度线程 → 改为读取预生成JSON文件
- BUG-6（中）：`run_task_manually` 局部重定义task_map → 改用 `self.task_map`

### main.py（2项）
- BUG-7（中）：`cmd_schedule args.once` 调用不存在方法 → 改为 `scheduler.run_full_pipeline()`
- BUG-8（低）：`check_environment` 路径 `src/config` → 改为 `config`

### analyze_and_send.py（2项）
- BUG-A01（中）：`old_feature_count` UnboundLocalError → 增加默认值 `= 0`
- BUG-A02（中）：`recent_original_data` pandas Series导致KeyError → 改为 `.values`

## Bug历史：RFE特征选择导致30个特征缺失（已彻底修复）

### 修复方案
所有预测路径用 `extract_all_features(df, select_top=None)` 生成全量 301 特征，保证 V8 模型的 76 个训练特征全部存在。

修改文件：orchestrator.py / main.py / scripts/utility/generate_prediction.py

## 2026-04-28 专项审计 V10.3 — 修复5项BUG + 1项关键遗漏

### BUG-1（严重）：task_map handler 路由错误
- `second/third_prediction_verification` 均指向 `task_first_prediction_verification`
- 修复：各指向独立 handler 函数

### BUG-2（特征组一致性）：设计合理，无需修复
- 训练存 feature_cols → 预测加载使用，自洽一致

### BUG-3（中等）：task_prediction_preview 特征列排除不完整
- 缺少 `period` 和 `full_number` 的排除
- 修复：添加到排除列表 + predictor.feature_cols 对齐

### BUG-4（中等）：scheduler_config.json 时间配置过时
- 使用旧版时间（22:00取数/17:30邮件），三个bat展示也错误
- 修复：更新为 22:15/20:15，新增 13:00/15:00 两条佐证时间

### BUG-5（用户报告进程误杀）：无复现
- V3.1代码已安全，三重匹配过滤，无裸taskkill

### 关键遗漏：setup_schedule 未注册二次/三次佐证验证
- 13:00 二次验证 和 15:00 三次验证 有handler但从未被调度
- 修复：setup_schedule 添加两个 schedule.every().day.at() 注册

### 完整日程表（修复后）
22:00取数 → 22:15评估 → 22:45优化 → 00:30训练 → 08:00增量训练 →
10:00首次佐证 → 12:00增量训练 → 13:00二次佐证 → 14:00增量训练 →
15:00三次佐证 → 16:00深度优化 → 17:00预生成 → 18:00最终预测 →
19:00验证 → 20:00售前 → 20:15发邮件

### IntelligentWorkflowOrchestrator 的真实路径
- `src.core.workflow.IntelligentWorkflowOrchestrator` 是工作流状态机（无 execute_prediction_pipeline）
- `execute_prediction_pipeline` 实际在 `src/core/orchestrator.py`（不在 workflow 子模块）

### 测试结果
Phase 7：18 PASS / 0 FAIL  
审计报告：`AUDIT_REPAIR_SUMMARY_V10_3.md`

## 代码审计完成状态

全面审计报告：`analysis_report_v10_full_audit.md`（第十～十二章）+ `AUDIT_REPAIR_SUMMARY_V10_3.md`（第三轮）
系统健康度：⭐⭐⭐⭐⭐

## 重要文件位置

- 模型目录: `models/` (ensemble/stacker/bayesian_weights/cv_scores/hmm/copula/bsts/evm/feature_cols)
- 数据: `data/raw/pl5_history.txt`, `data/processed/pl5_processed.csv`
- 结果: `results/`, `logs/`
- 配置: `config/scheduler_config.json`, `email_config.json`

## 踩坑记录

- C++ .pyd在Windows上存在Access Violation风险 → 纯Python fallback
- Python 3.12 中海象运算符 `:=` 在 sklearn 训练循环中不兼容 → 拆为独立赋值
- sklearn 1.8.0 移除了 `LogisticRegression.multi_class` 参数 → predictor.py 元学习器已修正
- **pandas Series iloc[-1]陷阱**: `seq[-1]` 在 pandas Series 上抛 `KeyError: -1`，必须用 `.iloc[-1]`
- **numpy.int64 JSON序列化**: `json.dump()` 不支持，需 `int()` 或 `str()`
- **调度线程阻塞**: schedule.run_pending() 单线程，耗时任务必须异步执行
- **重试退避顺序**: increment_count → get_delay → sleep，顺序颠倒首次无延迟
- **parse_line vs period**: pl5_processed.csv 的 `parse_line` 列是顺序行号（1~N），勿与 `period` 列（期号如2026101）混淆
