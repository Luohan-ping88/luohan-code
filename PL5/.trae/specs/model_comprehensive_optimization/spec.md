# 全面优化模型 Spec

## Why
当前PL5预测系统V9.0存在多个影响预测准确率和稳定性的问题：特征维度不匹配导致预测失败、邮件配置路径错误、模型参数未充分优化、自学习系统阈值不合理、时序模型实现效率低。需要进行全面优化以提升系统性能和可靠性。

## What Changes
- 修复特征维度不匹配问题（当前模型期望66维，实际53维）
- 修复邮件配置路径错误（auto_scheduler_v8.py第205行）
- 优化Stacking集成模型参数（增加基学习器数量和树的数量）
- 改进HMM/Copula/BSTS时序模型实现，提升效率和准确性
- 优化特征工程流程，增加特征选择策略
- 调整自学习系统参数（重训练阈值、窗口大小）
- 增强模型融合权重自适应能力
- 优化RL优化器训练策略
- **BREAKING**: 模型文件格式可能需要重新生成

## Impact
- Affected specs: architecture_optimization, performance_optimization
- Affected code:
  - `src/core/models/enhanced_predictor.py` - 核心预测器
  - `src/core/models/advanced_sequence.py` - 时序模型
  - `src/core/features/engineer.py` - 特征工程
  - `src/core/self_learning.py` - 自学习系统
  - `src/app/auto_scheduler_v8.py` - 调度器（邮件配置修复）
  - `src/app/analyze_and_send.py` - 分析发送模块
  - `src/core/rl/` - RL优化模块

## ADDED Requirements

### Requirement: 特征维度自动适配
系统 SHALL自动检测并处理特征维度不匹配的情况，无需手动干预。

#### Scenario: 特征维度不匹配时自动重训练
- **WHEN** 模型加载时检测到特征维度与当前数据不匹配
- **THEN** 系统应自动触发全量重训练并保存新模型
- **AND** 记录维度变化日志以便追踪

#### Scenario: 特征选择动态优化
- **WHEN** 执行特征工程时
- **THEN** 系统应使用多种特征重要性评估方法（随机森林、互信息、RFE）综合选择最优特征子集
- **AND** 自动确定最优特征数量

### Requirement: 集成模型参数优化
系统 SHALL提供可配置的集成模型参数，支持动态调整基学习器类型和数量。

#### Scenario: 增强Stacking集成
- **WHEN** 训练集成模型时
- **THEN** 系统应支持至少5种基学习器（RF, GBM, ET, AdaBoost, LightGBM/XGBoost如果可用）
- **AND** 元学习器应使用更复杂的模型（如神经网络或深度森林）

#### Scenario: 权重自适应融合
- **WHEN** 执行预测时
- **THEN** 系统应根据近期预测表现动态调整各模型权重
- **AND** 使用贝叶斯优化或强化学习进行权重搜索

### Requirement: 时序模型增强
系统 SHALL改进HMM、Copula、BSTS时序模型的实现质量和效率。

#### Scenario: HMM状态数自适应
- **WHEN** 训练HMM模型时
- **THEN** 系统应使用BIC/AIC准则自动选择最优状态数（2-8之间）
- **AND** 使用更高效的Baum-Welch算法实现

#### Scenario: Copula类型选择
- **WHEN** 训练Copula模型时
- **THEN** 系统应支持多种Copula类型（Gaussian, t, Clayton, Gumbel）
- **AND** 使用似然准则自动选择最优Copula类型

### Requirement: 自学习系统智能优化
系统 SHALL改进自学习系统的判断逻辑和建议质量。

#### Scenario: 动态阈值调整
- **WHEN** 评估是否需要重训练时
- **THEN** 系统应根据历史数据波动性动态调整重训练阈值
- **AND** 结合多种指标（准确率趋势、命中率、置信度）综合判断

#### Scenario: 多维度优化建议
- **WHEN** 生成优化建议时
- **THEN** 系统应提供具体可操作的优化方案（包含参数建议值）
- **AND** 区分紧急优化和常规优化建议

## MODIFIED Requirements

### Requirement: 邮件配置路径统一
所有模块 SHALL从统一的配置目录读取邮件配置文件。

- **修改文件**: `src/app/auto_scheduler_v8.py` (第205行), `src/app/analyze_and_send.py` (第320行)
- **配置路径**: `config/email_config.json`
- **向后兼容**: 同时检查旧路径和新路径

### Requirement: 模型版本管理
系统 SHALL在模型文件中记录完整的版本信息和元数据。

- **新增字段**: feature_count, training_data_hash, model_params_hash, performance_metrics
- **版本格式**: V10.0 (主版本.次版本)
- **兼容性**: 保持对V9.0模型文件的读取兼容

### Requirement: 错误处理增强
系统 SHALL提供更详细的错误信息和恢复机制。

- **错误分类**: 数据错误、模型错误、配置错误、网络错误
- **恢复策略**: 不同错误类型采用不同的重试和恢复机制
- **日志级别**: 关键操作必须记录详细日志

## REMOVED Requirements

### Requirement: 固定参数硬编码
**原因**: 当前系统中多处使用硬编码的模型参数，不利于优化和调整。
**迁移**: 将所有关键参数提取到配置文件或类属性中，支持运行时修改。

- 移除位置: 
  - `enhanced_predictor.py` 第28-31行 (BASE_MODELS固定定义)
  - `self_learning.py` 第22-24行 (RETRAIN_THRESHOLD等常量)
  - `advanced_sequence.py` 第20行 (n_states=4固定值)

---

## 技术实现要点

### 1. 特征工程优化
```python
# 新增多方法特征选择
class MultiMethodFeatureSelector:
    methods = ['random_forest', 'mutual_info', 'rfe', 'chi2']
    # 综合评分选择最优特征子集
```

### 2. 集成模型增强
```python
# 扩展基学习器列表
BASE_MODELS = {
    "rf": RandomForestClassifier(n_estimators=100, max_depth=12),
    "gbm": GradientBoostingClassifier(n_estimators=100, max_depth=6),
    "et": ExtraTreesClassifier(n_estimators=100, max_depth=12),
    "adaboost": AdaBoostClassifier(n_estimators=50),
    "lightgbm": LGBMClassifier() if available else None,
}
```

### 3. 时序模型改进
```python
# HMM自动状态数选择
def select_optimal_states(data, max_states=8):
    # 使用BIC准则选择最优状态数
    pass

# Copula类型自动选择
def select_best_copula(data):
    # 测试多种Copula类型，选择最优
    copulas = ['gaussian', 't', 'clayton', 'gumbel']
    pass
```

### 4. 自学习系统升级
```python
# 动态阈值计算
def calculate_dynamic_threshold(history):
    # 基于历史数据波动性计算自适应阈值
    volatility = np.std(history['accuracy'])
    base_threshold = 0.02
    return base_threshold * (1 + volatility * 10)
```

## 验证标准

### 性能指标
- 预测准确率提升 ≥ 5%（Top-3命中率）
- Top-8推荐覆盖率 ≥ 90%
- 模型训练时间 ≤ 30分钟（全量训练）
- 内存使用峰值 ≤ 4GB
- 特征维度稳定性（连续训练不出现维度跳变）

### 稳定性指标
- 连续7天无崩溃运行
- 邮件发送成功率 ≥ 95%
- 任务执行成功率 ≥ 98%
- 日志无ERROR级别错误

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 模型重构导致短期性能下降 | 预测准确率临时降低 | 保留旧模型作为回退方案 |
| 参数过多导致过拟合 | 泛化能力下降 | 使用交叉验证和正则化 |
| 特征维度增加 | 训练时间增长 | 使用特征选择和降维 |
| 配置变更 | 兼容性问题 | 向后兼容旧配置格式 |
