# V11 模式集成使用指南

## 概述

本文档介绍如何在PL5预测系统中启用和使用V11先进特征工程模式。V11模式包含更先进的特征提取方法，包括多尺度时序分析、频域特征、信息论特征和混沌分形特征等。

## 快速开始

### 方法一：通过命令行参数使用

在使用`main.py`时，添加`--v11`参数来启用V11模式：

```bash
# 使用V11高级模式进行训练
python main.py train --v11

# 使用V11高级模式进行预测
python main.py predict --v11

# 指定V11模式类型
python main.py train --v11 --v11-mode v11_advanced
python main.py train --v11 --v11-mode v11_full
```

### 方法二：通过调度器配置使用

编辑`config/scheduler_config_v8.json`文件，启用V11模式：

```json
{
  "v11_mode": {
    "enabled": true,
    "feature_mode": "v11_advanced"
  }
}
```

然后启动调度器：

```bash
python main.py schedule
```

## V11模式类型

V11支持三种不同的特征工程模式：

| 模式 | 描述 | 特征数量 |
|------|------|----------|
| `v10` | 仅使用V10原有特征 | ~100+ |
| `v11_advanced` | V10特征 + 先进特征（默认） | ~400+ |
| `v11_full` | V10特征 + 先进特征 + 深度学习特征 | ~500+ |

### 模式选择建议

- **v10模式**：保持与现有系统完全兼容，用于对比测试
- **v11_advanced模式**：推荐日常使用，平衡特征数量和计算效率
- **v11_full模式**：研究和开发使用，包含所有可用特征

## 配置说明

### 调度器配置

在`config/scheduler_config_v8.json`中：

```json
{
  "v11_mode": {
    "enabled": false,  // 设置为true启用V11模式
    "feature_mode": "v11_advanced"  // 可选: v10, v11_advanced, v11_full
  }
}
```

### 特征工程配置

V11特征工程的详细配置在`config/model_config_v2.yaml`中：

```yaml
v11:
  enabled: false
  device: cpu
  
  # Mamba模型配置（用于深度特征）
  mamba:
    d_model: 256
    n_layers: 6
    seq_len: 50
    d_state: 64
    expand: 2
    dropout: 0.1
    lr: 1e-4
```

## 主要特性

### V11先进特征包含

1. **多尺度时序特征**
   - 多窗口滑动统计
   - 指数加权移动平均
   - 时间序列分解（趋势/季节/残差）

2. **频域特征**
   - 傅里叶变换特征
   - 功率谱密度
   - 频域统计量

3. **信息论特征**
   - 样本熵
   - 近似熵
   - 排列熵
   - 互信息特征

4. **混沌分形特征**
   - Hurst指数（C++加速）
   - Lyapunov指数（C++加速）
   - 分形维数

5. **模式识别特征**
   - 连号检测
   - 重复模式
   - 趋势模式

### 向后兼容

V11模式完全向后兼容：
- V10模式仍然完全可用
- 现有模型无需重新训练
- 可以在V10和V11之间无缝切换

## 使用示例

### 完整流程示例（V11模式）

```bash
# 1. 启用V11配置
# 编辑 config/scheduler_config_v8.json，设置 v11_mode.enabled = true

# 2. 执行完整训练流程
python main.py train --v11 --v11-mode v11_advanced

# 3. 执行预测
python main.py predict --v11

# 4. 启动自动调度器（会使用配置文件中的V11设置）
python main.py schedule
```

### 在代码中直接使用V11特征工程

```python
from src.core.features.v11_engineer import V11FeatureEngineer
from src.core.data.collector import PL5DataCollector

# 初始化V11特征工程师
engineer = V11FeatureEngineer(mode='v11_advanced')

# 加载数据
collector = PL5DataCollector()
df = collector.load_processed_data()

# 提取特征
df_features = engineer.extract_all_features(df, select_top=None)

# 获取特征摘要
summary = engineer.get_feature_summary(df_features)
print(f"特征总数: {summary['total_features']}")
print(f"特征类别: {summary['feature_categories']}")
```

## 文件结构

### 新增文件

```
PL5/
├── src/core/features/
│   ├── v11_engineer.py          # V11特征工程主类
│   ├── advanced_features.py      # 先进特征提取模块
│   ├── comprehensive_features.py # 综合特征管理
│   └── deep_features.py          # 深度学习特征（可选）
├── config/
│   ├── model_config_v2.yaml      # V11模型配置
│   └── scheduler_config_v8.json  # 调度器配置（已更新）
├── scripts/
│   ├── test_v11_full_integration.py  # V11集成测试脚本
│   └── test_v11_quick.py         # V11快速测试
└── docs/
    └── V11_INTEGRATION_GUIDE.md  # 本文档
```

### 修改的文件

- `main.py` - 添加V11命令行参数支持
- `src/app/auto_scheduler_v8.py` - 调度器添加V11模式支持

## 验证和测试

### 运行V11集成测试

```bash
# 运行全面集成测试
python scripts/test_v11_full_integration.py

# 运行快速测试
python scripts/test_v11_quick.py
```

### 检查V11是否正常工作

1. 查看训练日志中的特征数量，V11模式应该有400+特征
2. 检查`logs/training_info.json`中的`model_version`是否为"V11"
3. 验证预测结果文件中是否包含`v11_enabled`字段

## 性能考虑

### 计算开销

- **v10模式**：与原有系统相同
- **v11_advanced模式**：特征提取时间增加约2-3倍
- **v11_full模式**：特征提取时间增加约5-10倍（包含深度学习）

### 内存使用

- V11特征矩阵会更大，建议确保有足够内存
- 如果内存不足，可以考虑使用`v11_advanced`模式

## 常见问题

### Q: 如何从V10迁移到V11？

A: 
1. 首先备份现有模型
2. 在配置中启用V11模式
3. 重新训练模型（推荐）
4. 逐步验证预测效果

### Q: V11模式需要重新训练模型吗？

A: 强烈建议重新训练以获得最佳效果。虽然系统会尝试兼容，但特征空间发生了变化。

### Q: 可以在V10和V11之间切换吗？

A: 可以，但需要确保对应模式的模型存在。建议为不同模式分别保存模型。

### Q: V11模式会提高预测准确率吗？

A: V11提供了更丰富的特征，通常可以提升模型性能，但具体提升取决于数据和模型配置。建议进行A/B测试对比。

### Q: 如何禁用V11回退到V10？

A: 将配置中的`v11_mode.enabled`设置为`false`，或不使用`--v11`参数即可。

## 故障排除

### 问题：特征提取失败

检查：
1. C++加速模块是否正确编译
2. 数据格式是否正确
3. 查看日志中的错误信息

### 问题：调度器没有使用V11

检查：
1. 配置文件路径是否正确
2. `v11_mode.enabled`是否设置为true
3. 调度器是否重启以加载新配置

### 问题：导入错误

确保所有依赖已安装：
```bash
pip install -r requirements.txt
```

## 技术支持

如遇到问题，请检查：
1. 日志文件：`logs/`目录
2. 测试脚本：运行`scripts/test_v11_full_integration.py`
3. 本文档的"常见问题"部分

## 更新日志

### v1.0 (当前版本)
- 完整的V11特征工程集成
- 支持三种模式切换
- 主流程和调度器完整支持
- 向后兼容保证
