# 优化模块集成使用指南

## 概述

本指南说明如何将新开发的优化模块集成到现有的PL5预测系统中。

---

## 1. 快速开始

### 方式一: 使用适配器模式 (推荐)

```python
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.models.optimization_integration import OptimizedEnhancedPredictorAdapter

base_predictor = EnhancedPL5Predictor()

optimized = OptimizedEnhancedPredictorAdapter(base_predictor, config={
    'optimization': {
        'feature_selection': {'enabled': True},
        'fusion_strategy': {'enabled': True},
        'ensemble': {'enabled': True}
    }
})

optimized.fit(df, feature_cols, enable_optimization=True)
results = optimized.predict(features, use_optimization=True)

optimized.update_with_feedback(predictions, actual)
```

### 方式二: 混合类继承

```python
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.models.optimization_integration import OptimizationIntegrationMixin

class OptimizedPredictor(OptimizationIntegrationMixin, EnhancedPL5Predictor):
    def __init__(self, model_config=None, optimization_config=None):
        super().__init__(model_config)
        self.__init_optimization_modules__(optimization_config)
```

---

## 2. 配置说明

### model_config_v2.yaml

```yaml
optimization:
  feature_selection:
    enabled: true
    decay_factor: 0.95           # 指数衰减因子
    min_importance: 0.01          # 最小重要性阈值
    max_features_per_group: 3    # 每组最多特征数
    warmup_periods: 10          # 预热期数
    min_select: 20               # 最少选择特征数
    max_select: 100              # 最多选择特征数

  feature_interaction:
    enabled: true
    enable_position_cross: true  # 位置交叉特征
    enable_temporal_cross: true  # 跨期交互特征
    enable_frequency_cross: true # 频率交叉特征
    max_interaction_features: 50
    lag_windows: [1, 2, 3]

  fusion_strategy:
    type: context_aware
    context_dim: 32              # 上下文向量维度
    history_window: 30           # 历史窗口大小
    confidence_temperature: 1.0  # 置信度温度
    confidence_weighted: true

  ensemble:
    diversity_threshold: 0.7     # 多样性阈值
    use_calibration: true        # 概率校准
    cv_folds: 5

  copula:
    types: [gaussian, t, gumbel] # Copula类型
    tail_boost: true             # 尾部放大
    tail_threshold: 0.1
    em_max_iter: 50
    em_tolerance: 0.0001
```

---

## 3. 核心API

### OptimizationIntegrationMixin

#### 特征优化

```python
df_enhanced, selected_features = predictor.optimize_features(
    df,                    # 原始数据
    feature_cols,          # 基础特征列
    fit_stacking=True      # 是否训练增强Stacking
)
```

#### Copula训练

```python
success = predictor.fit_optimized_copula(df)
```

#### 预测

```python
results = predictor.predict_with_optimization(
    features,              # 特征向量
    recent_data=None,      # 最近数据
    top_k=8,               # 返回top-k
    use_optimized_fusion=True  # 使用优化的权重融合
)
```

#### 反馈更新

```python
predictor.update_optimization_with_feedback(
    predictions={'wan': [1,2,3], 'qian': [4,5,6]},
    actual={'wan': 2, 'qian': 5, 'bai': 3, 'shi': 1, 'ge': 9}
)
```

#### 状态摘要

```python
summary = predictor.get_optimization_summary()
# 返回:
# {
#     'enabled': True,
#     'is_fitted': True,
#     'selected_features_count': 50,
#     'weight_fusion': {...},
#     'thompson_sampling_weights': {...}
# }
```

---

## 4. 模块说明

### 4.1 自适应特征选择器 (AdaptiveFeatureSelector)

- **位置**: `src/core/features/adaptive_selector.py`
- **功能**: 在线特征重要性追踪、组约束选择、自动剪枝
- **状态保存**: `.save()` / `.load()`

### 4.2 特征交互提取器 (FeatureInteractionExtractor)

- **位置**: `src/core/features/interaction_extractor.py`
- **功能**: 位置交叉、跨期交互、频率交叉、统计交互
- **输出**: 50+ 交互特征

### 4.3 上下文感知权重融合 (ContextAwareWeightFusion)

- **位置**: `src/core/models/context_weight_fusion.py`
- **功能**: 32维上下文编码、置信度加权、在线更新
- **配合**: ThompsonSamplingOptimizer

### 4.4 增强Stacking (EnhancedStackingEnsemble)

- **位置**: `src/core/models/enhanced_stacking.py`
- **功能**: 多样性驱动选择、多类型基学习器、概率校准

### 4.5 尾部敏感Copula (TailAwareCopula)

- **位置**: `src/core/models/tail_aware_copula.py`
- **功能**: Gaussian + t + Gumbel 混合、EM权重估计、尾部放大

---

## 5. 工作流程

### 训练流程

```
1. 初始化优化模块
   ↓
2. 特征优化
   ├─ 提取交互特征
   ├─ 自适应特征选择
   └─ 训练增强Stacking
   ↓
3. Copula训练
   ├─ 准备边缘分布数据
   ├─ EM算法拟合
   └─ 尾部放大
   ↓
4. 权重融合初始化
```

### 预测流程

```
1. 增强Stacking预测
   ↓
2. 尾部Copula预测
   ↓
3. 上下文感知权重融合
   ├─ 提取上下文特征
   ├─ 预测动态权重
   └─ 置信度加权
   ↓
4. 输出Top-K推荐
```

### 更新流程

```
1. 记录预测结果
   ↓
2. 计算奖励
   ↓
3. 更新各模块
   ├─ 特征重要性追踪
   ├─ 权重融合器
   └─ Thompson采样器
   ↓
4. 保存状态
```

---

## 6. 性能指标

| 模块 | 指标 | 说明 |
|------|------|------|
| 特征选择 | 维度降低 | 76+ → 20-50 |
| 权重融合 | 状态空间 | 128 → 32 维 |
| Stacking | 模型多样性 | 3 → 5+ 种 |
| Copula | 尾部建模 | 单 → 3种混合 |

---

## 7. 故障排除

### 问题1: 优化模块导入失败

```
ModuleNotFoundError: No module named 'src.core.features.adaptive_selector'
```

**解决**: 检查 `__init__.py` 是否正确导出

### 问题2: 内存不足

**解决**: 减少 `max_interaction_features` 和 `cv_folds`

### 问题3: 预测结果全相同

**解决**: 检查 `fit()` 是否正确调用

---

## 8. 最佳实践

1. **渐进式启用**: 先启用特征优化，稳定后再启用模型优化
2. **定期保存**: 使用 `save_optimization_state()` 定期保存状态
3. **监控日志**: 关注 `[优化集成]` 前缀的日志输出
4. **回测验证**: 使用回测框架验证优化效果
5. **A/B测试**: 线上使用A/B测试对比优化效果
