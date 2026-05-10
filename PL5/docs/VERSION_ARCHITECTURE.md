# PL5 排列五预测系统 - 版本架构说明

## 版本演进路线图

```
V8.0 (Legacy) ──→ V9.0 (Deprecated) ──→ V10.0 (当前活跃版本)
   │                    │                        │
   │                    │                        ├── Mamba选择性状态空间模型
   │                    │                        ├── iTransformer变量维度注意力
   │                    │                        └── 增强贝叶斯不确定性量化
   │                    │
   │                    ├── EnhancedPL5Predictor
   │                    ├── 4模型融合(Stacking+HMM+Copula+BSTS)
   │                    └── RL权重优化 + 贝叶斯不确定性
   │
   ├── PL5Predictor
   ├── Stacking集成(RF+GB+ET)
   ├── 简化HMM/BSTS/Copula
   └── 固定权重融合
```

## 各版本详细对比

### V8.0 (Legacy) - 已弃用

**核心文件**: `src/core/models/predictor.py`

**预测器类**: `PL5Predictor`

**模型文件**: `models/pl5_predictor_v8.pkl` (~27.7MB)

**算法组成**:
| 模型 | 说明 |
|------|------|
| Stacking集成 | RandomForest + GradientBoosting + ExtraTrees |
| HMM | 简化版隐马尔可夫模型(lag-1条件频率) |
| BSTS | 简化版贝叶斯结构时序(EWMA) |
| Copula | 多元Copula联合分布 |

**特征工程**:
- 基础统计特征
- 简单滚动窗口特征
- 无漂移检测

**权重策略**:
- 固定权重: stacking=0.55, hmm=0.15, copula=0.20, bsts=0.10
- 无自适应调整

**入口文件**:
- ~~pl5_intelligent_system.py~~ (已更新为V10)
- ~~auto_scheduler_v8.py~~ (task_train已更新为V10)

**状态**: ⚠️ **已弃用，仅保留兼容性**

---

### V9.0 (Deprecated) - 已弃用

**核心文件**: `src/core/models/enhanced_predictor.py`

**预测器类**: `EnhancedPL5Predictor`

**模型文件**: `models/enhanced_predictor_v9.pkl` (~5.8MB)

**算法组成**:
| 模型 | 说明 |
|------|------|
| Stacking集成 | RF + GB + ET + AdaBoost (+LGBM/XGB可选) |
| HMM | GMM发射概率 + 自适应状态数选择(BIC/AIC) |
| BSTS | 局部线性趋势 + FFT季节检测 + 异常值处理 |
| Copula | Gaussian/Student-t/Clayton/Gumbel自动选择 |

**特征工程**:
- 16组特征(fibonacci/markov/fourier/extreme/pattern等)
- RFE递归特征消除
- PSI漂移检测
- LRU Hash缓存

**权重策略**:
- 默认: stacking=0.40, hmm=0.15, copula=0.25, bsts=0.20
- 三级优先级: RL优化 > EMA动态 > Thompson采样
- 128维RL状态空间

**新增功能**:
- 自学习系统V10.0(Mann-Kendall趋势检测)
- 强化学习模块(PPO/DQN/多臂老虎机)
- 贝叶斯权重不确定量化(Beta先验/Thompson采样)
- 性能监控与告警

**状态**: ⚠️ **已弃用，被V10取代**

---

### V10.0 (当前活跃版本) ✅

**核心文件**:
- `src/core/models/enhanced_predictor.py` (主预测器)
- `src/core/models/mamba_predictor.py` (Mamba SSM)
- `src/core/models/itransformer_predictor.py` (iTransformer)
- `src/core/models/bayesian_uncertainty.py` (不确定性量化)

**预测器类**: `EnhancedPL5Predictor` (6模型融合)

**算法组成** (6模型融合):
| 模型 | 权重 | 核心创新 |
|------|------|---------|
| **Stacking集成** | 0.25 | 6基学习器 + 元特征工程(分歧度/一致性) |
| **HMM** | 0.10 | GMM发射 + 选择性状态空间 |
| **Copula** | 0.15 | 4种Copula自动选择 + 尾部依赖系数 |
| **BSTS** | 0.10 | 趋势+季节+异常 + 增量学习 |
| **Mamba** 🆕 | 0.20 | O(L)线性复杂度 + 输入依赖选择性机制 |
| **iTransformer** 🆕 | 0.20 | 变量维度注意力 + FFN时序编码 |

**新增模块详情**:

#### Mamba选择性状态空间模型
- **来源**: Gu & Dao (2023), Wang et al. (2024)
- **核心优势**: O(L)线性复杂度 vs Transformer的O(L²)
- **关键特性**:
  - 输入依赖的B/C矩阵和Δt参数
  - 零阶保持(ZOH)离散化
  - 并行扫描算法(训练) / 循环更新(推理)
  - MC-Dropout风格不确定性量化

#### iTransformer变量维度注意力
- **来源**: 清华&蚂蚁 ICLR 2024
- **核心创新**: 注意力从时间维度转向变量维度
- **关键特性**:
  - 变量标记化(每个位置完整历史序列作为token)
  - FFN沿时间维度操作(提取周期/趋势)
  - 位置间相关性注意力图
  - 正确层归一化(解决非平稳性)

#### 增强贝叶斯不确定性量化
- **来源**: Wilson & Izmailov (2024), Angelopoulos & Bates (2024)
- **核心能力**:
  - Temperature Scaling概率校准
  - 认知/偶然不确定性分解
  - 共形预测(统计严格覆盖保证)
  - PSI/MMD/KS分布漂移检测

**特征工程** (继承V9):
- 16组特征 + RFE选择 + PSI漂移检测
- 新增: 特征重要性驱动的动态权重调整

**权重策略** (升级):
```
p_fused = 0.25*stacking + 0.10*hmm + 0.15*copula + 
          0.10*bsts + 0.20*mamba + 0.20*itransformer
```
- 不确定性感知权重调整
- 贝叶斯Thompson采样降级

**入口文件** (统一使用V10):
| 文件 | 用途 | 预测器版本 |
|------|------|-----------|
| `main.py` | 统一入口(train/predict/analyze/schedule/status) | ✅ V10.0 |
| `pl5_intelligent_system.py` | 智能体协作系统 | ✅ V10.0 |
| `auto_scheduler_v8.py` | 自动调度器(task_train等) | ✅ V10.0 |
| `analyze_and_send.py` | 分析与邮件发送 | ✅ V10.0 |

**命令行用法**:
```bash
# 训练(使用V10 6模型融合)
python main.py train

# 预测
python main.py predict

# 分析并发送邮件(V10报告格式)
python main.py analyze

# 启动调度器
python main.py schedule

# 查看系统状态(显示V10信息)
python main.py status
```

---

## 模型文件说明

| 文件名 | 版本 | 大小 | 状态 |
|--------|------|------|------|
| `pl5_predictor_v8.pkl` | V8.0 | ~27.7MB | Legacy, 可删除 |
| `enhanced_predictor_v9.pkl` | V9.0 | ~5.8MB | Deprecated, 可归档 |
| `enhanced_predictor_v10.pkl` | V10.0 | ~8-12MB | **当前活跃** |

> 注: V10训练后会生成新的模型文件，建议清理旧版本文件。

---

## 迁移指南

### 从V9升级到V10
1. 更新代码: 已通过本次统一完成
2. 重新训练: `python main.py train`
3. 验证: `python main.py status` 确认显示V10.0
4. 可选: 删除旧模型文件 `pl5_predictor_v8.pkl`, `enhanced_predictor_v9.pkl`

### 兼容性说明
- V10完全向后兼容V9的数据格式和配置
- V10的训练信息包含更多字段(models状态)，但基本结构不变
- 邮件报告格式升级为V10，包含6模型描述

---

## 架构图

```
┌─────────────────────────────────────────────────────┐
│                   main.py (统一入口)                  │
│         python main.py [train|predict|analyze|...]    │
└──────────────────────┬──────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   train     │ │   predict   │ │   analyze   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       ▼               ▼               ▼
┌─────────────────────────────────────────────────────┐
│           EnhancedPL5Predictor V10.0                 │
│                                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │Stacking │ │   HMM   │ │ Copula  │ │  BSTS   │  │
│  │  0.25   │ │  0.10   │ │  0.15   │ │  0.10   │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│                                                     │
│  ┌─────────┐ ┌─────────────┐                      │
│  │ Mamba   │ │iTransformer │                      │
│  │  0.20   │ │   0.20      │                      │
│  └─────────┘ └─────────────┘                      │
│                                                     │
│  ┌─────────────────────────────────┐               │
│  │   Bayesian Uncertainty Quantifier │              │
│  │   (Calibration + Decomposition)  │              │
│  └─────────────────────────────────┘               │
└─────────────────────────────────────────────────────┘
```

---

**文档版本**: 1.0  
**最后更新**: 2026-04-09  
**适用版本**: PL5 V10.0
