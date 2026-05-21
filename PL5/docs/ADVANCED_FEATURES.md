# PL5排列五先进特征工程文档

**版本**: V11  
**日期**: 2026-05-21  
**状态**: ✅ 完成

---

## 1. 概述

本模块针对排列五彩票开奖数据的特点，开发了一套全面的先进特征工程系统。与传统的特征工程相比，本模块具有以下特点：

- **多维度**: 从时域、频域、信息论等多个维度提取特征
- **多尺度**: 在不同时间尺度上捕捉模式
- **智能化**: 支持深度学习自动特征学习
- **高效化**: 支持C++加速

---

## 2. 模块架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PL5先进特征工程架构                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                     输入层：原始开奖数据                               │  │
│  │                   wan, qian, bai, shi, ge (5个位置)                  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    综合特征提取器                                      │  │
│  │                  ComprehensiveFeatureExtractor                         │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │                                                                          │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │  │
│  │  │   基础位置特征   │  │   先进特征工程    │  │  深度学习特征    │   │  │
│  │  │  (18个特征)     │  │  (409个特征)     │  │  (可选)         │   │  │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │  │
│  │                                                                          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                     输出层：融合特征向量                              │  │
│  │                       (400+个特征)                                   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 特征类别详解

### 3.1 多尺度时序特征 (140个)

| 特征类型 | 窗口大小 | 特征名示例 | 说明 |
|---------|---------|-----------|------|
| 均值 | 3,5,7,10,15,20,30 | `{pos}_ms_mean_{window}` | 不同时间尺度的滚动均值 |
| 标准差 | 3,5,7,10,15,20,30 | `{pos}_ms_std_{window}` | 不同时间尺度的波动性 |
| 趋势 | 3,5,7,10,15,20,30 | `{pos}_ms_trend_{window}` | 线性回归斜率 |
| 波动率 | 3,5,7,10,15,20,30 | `{pos}_ms_volatility_{window}` | 标准差/均值 |

### 3.2 频域特征 (20个)

| 特征名 | 说明 |
|--------|------|
| `{pos}_dominant_freq` | 主频率 |
| `{pos}_dominant_power` | 主频率功率 |
| `{pos}_low_freq_ratio` | 低频功率比例 |
| `{pos}_mid_freq_ratio` | 中频功率比例 |
| `{pos}_high_freq_ratio` | 高频功率比例 |
| `{pos}_spectral_entropy` | 谱熵 |

**技术实现**:
- FFT变换
- Welch功率谱密度估计
- 谱熵计算

### 3.3 位置关联特征 (25个)

| 特征类型 | 特征名示例 | 说明 |
|---------|-----------|------|
| 两位置相关 | `{pos1}_{pos2}_corr` | 任意两位置间的相关系数 |
| 和特征 | `sum_all` | 所有位置数字之和 |
| 积特征 | `product_all` | 所有位置数字之积 |
| 统计量 | `mean_all`, `std_all`, `min_all`, `max_all` | 位置统计特征 |
| 差值 | `{pos}_corr_with_sum` | 单位置与总和的相关性 |

### 3.4 统计检验特征 (30个)

| 特征名 | 说明 |
|--------|------|
| `{pos}_normality_stat` | 正态性检验统计量 |
| `{pos}_normality_pval` | 正态性检验p值 |
| `{pos}_ks_stat` | Kolmogorov-Smirnov统计量 |
| `{pos}_ks_pval` | KS检验p值 |
| `{pos}_runs_stat` | 游程检验统计量 |
| `{pos}_anderson_stat` | Anderson-Darling统计量 |

### 3.5 信息论特征 (65个)

| 特征类型 | 窗口大小 | 特征名示例 | 说明 |
|---------|---------|-----------|------|
| 熵 | 10, 20, 50 | `{pos}_entropy_{window}` | Shannon熵 |
| 条件熵 | 10, 20, 50 | `{pos}_cond_entropy_{window}` | 条件熵 |
| 互信息 | 10, 20, 50 | `{pos}_mutual_info_{window}` | 互信息 |

### 3.6 混沌与分形特征 (25个)

| 特征名 | 说明 |
|--------|------|
| `{pos}_hurst` | Hurst指数 (R/S分析) |
| `{pos}_lyapunov` | Lyapunov指数 |
| `{pos}_corr_dim` | 关联维数 |
| `{pos}_approx_entropy` | 近似熵 |
| `{pos}_sample_entropy` | 样本熵 |

### 3.7 跨期预测特征 (45个)

| 特征类型 | 窗口大小 | 特征名示例 | 说明 |
|---------|---------|-----------|------|
| 滞后特征 | 1, 2, 3, 5 | `{pos}_lag_{lag}` | 历史数据 |
| 差分均值 | 3, 5, 10 | `{pos}_diff_mean_{window}` | 与均值偏差 |
| 动量 | - | `{pos}_momentum` | 3期变化 |
| 加速度 | - | `{pos}_acceleration` | 变化率变化 |

### 3.8 分布特征 (40个)

| 特征类型 | 特征名示例 | 说明 |
|---------|-----------|------|
| 众数 | `{pos}_digit_mode` | 最常见数字 |
| 众数频次 | `{pos}_digit_mode_count` | 众数出现次数 |
| 基尼系数 | `{pos}_gini_coefficient` | 分布不均匀度 |
| 奇偶比 | `{pos}_even_ratio`, `{pos}_odd_ratio` | 奇偶分布 |
| 大小比 | `{pos}_small_ratio`, `{pos}_large_ratio` | 0-4/5-9分布 |
| 质数比 | `{pos}_prime_ratio` | 质数出现比例 |

---

## 4. 深度学习特征 (可选)

当PyTorch可用时，还可以提取以下深度学习特征：

### 4.1 自编码器特征
- `ae_feat_0` ~ `ae_feat_31`: 32维潜在表示

### 4.2 时间卷积特征
- `conv_feat_0` ~ `conv_feat_31`: 32维卷积特征

### 4.3 注意力特征
- `attn_feat_0` ~ `attn_feat_31`: 32维注意力表示
- `attn_entropy`: 注意力熵
- `attn_max`: 最大注意力权重

---

## 5. 使用方法

### 5.1 基础使用

```python
from src.core.features.advanced_features import AdvancedFeatureEngineering
from src.core.features.comprehensive_features import ComprehensiveFeatureExtractor

# 方法1：使用先进特征提取器
extractor = AdvancedFeatureEngineering(use_cpp=True)
features = extractor.extract_all_features(df)

# 方法2：使用综合特征提取器
extractor = ComprehensiveFeatureExtractor(
    enable_advanced=True,
    enable_deep=False,  # 设为True以启用深度学习特征
    enable_cpp=True
)
features = extractor.extract_all(df)

# 方法3：使用便捷函数
from src.core.features.advanced_features import extract_advanced_features
features = extract_advanced_features(df, use_cpp=True)
```

### 5.2 特征选择

```python
# 获取特征摘要
summary = extractor.get_feature_summary(features)
print(f"总特征数: {summary['total_features']}")
print(f"先进特征数: {summary['advanced_features']}")

# 获取特征重要性
target = df['wan'].values  # 预测目标
importance = extractor.get_feature_importance(features, target)
print("Top 10重要特征:")
for feat, score in list(importance.items())[:10]:
    print(f"  {feat}: {score:.4f}")
```

### 5.3 特征缓存

```python
# 综合特征提取器支持缓存
extractor = ComprehensiveFeatureExtractor(
    use_cache=True,
    cache_dir='./feature_cache'
)

# 特征保存与加载
extractor.save_features(features, 'features.parquet')
features = extractor.load_features('features.parquet')

# 清除缓存
extractor.clear_cache()
```

---

## 6. 性能基准

### 6.1 特征数量对比

| 特征类型 | 数量 |
|---------|------|
| 基础特征 | 6 |
| 先进特征 | 409 |
| 综合特征 | 472 |
| 深度学习特征(可选) | +192 |

### 6.2 提取时间 (300期数据)

| 组件 | 时间 |
|------|------|
| 先进特征提取 | ~7.5秒 |
| 综合特征提取 | ~7.5秒 |
| C++加速 | ~2-3倍提速 |

---

## 7. 依赖

### 7.1 必需依赖

- numpy
- pandas
- scipy

### 7.2 可选依赖

- **C++加速**: pybind11, C++编译器
- **深度学习**: PyTorch (torch)

### 7.3 安装

```bash
# 必需依赖
pip install numpy pandas scipy

# 可选：C++加速
pip install pybind11
cd cpp_core && python setup.py build_ext --inplace

# 可选：深度学习
pip install torch
```

---

## 8. 文件结构

```
src/core/features/
├── advanced_features.py        # 先进特征工程 (核心)
├── deep_features.py           # 深度学习特征
├── comprehensive_features.py   # 综合特征提取器
└── config.py                  # 配置文件
```

---

## 9. 未来改进方向

1. **特征选择优化**: 自动化特征选择，减少冗余
2. **更多深度学习模型**: 集成LSTM、GRU等序列模型
3. **特征交互挖掘**: 自动发现高阶特征交互
4. **在线学习**: 支持流式特征更新
5. **可解释性增强**: 添加SHAP/LIME特征解释

---

## 10. 注意事项

1. **数据规模**: 建议至少100期数据进行特征提取
2. **C++加速**: 在生产环境建议启用C++加速
3. **深度学习**: 需要GPU加速以获得最佳性能
4. **特征冗余**: 高维特征可能导致过拟合，建议进行特征选择

---

**文档版本**: V1.0  
**更新日期**: 2026-05-21
