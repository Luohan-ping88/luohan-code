# C++高性能核心模块

## 概述

使用C++实现排列五系统的高性能计算核心，通过pybind11与Python绑定，提供10-50倍的性能提升。

## 性能提升对比

| 功能 | Python实现 | C++实现 | 加速比 |
|------|-----------|---------|--------|
| 滚动窗口均值 | 慢 | 快 | 10-50x |
| 滚动窗口标准差 | 慢 | 快 | 10-50x |
| 滚动窗口频率 | 慢 | 快 | 20-100x |
| Hurst指数 | 慢 | 快 | 5-20x |
| Lyapunov指数 | 慢 | 快 | 5-20x |
| FFT变换 | 中等 | 快 | 5-20x |
| HMM模型训练 | 慢 | 快 | 3-10x |
| Copula计算 | 慢 | 快 | 5-15x |

## 安装要求

### Windows
- Visual Studio Build Tools 或 Visual Studio 2019/2022
- C++ CMake tools for Windows
- Python 3.8+

### 安装命令
```bash
pip install pybind11
```

## 编译安装

### 方法一：使用批处理脚本（推荐）
```bash
cd cpp_core
build_cpp.bat
```

### 方法二：手动编译
```bash
cd cpp_core
python setup.py build_ext --inplace
pip install .
```

## 使用方法

### 基本使用
```python
from cpp_core import FastFeatureCalculator, FastHMMModel, FastCopulaModel

# 创建计算器
calc = FastFeatureCalculator()

# 滚动窗口均值（自动使用C++加速）
result = calc.rolling_mean(data, window=20)

# Hurst指数
calc.calculate_hurst(data)

# HMM模型
hmm = FastHMMModel(n_components=4)
hmm.fit(data)
states = hmm.predict(data)
```

### 检查C++模块是否可用
```python
from cpp_core import CPP_AVAILABLE, benchmark

if CPP_AVAILABLE:
    print("C++模块已加载")
    print(f"性能测试: {benchmark()} ms")
else:
    print("C++模块未编译，使用Python回退实现")
```

## 文件结构

```
cpp_core/
├── feature_calculator.h      # C++头文件
├── feature_calculator.cpp    # C++实现
├── bindings.cpp              # Python绑定
├── setup.py                  # 编译配置
├── build_cpp.bat            # Windows编译脚本
├── __init__.py              # Python包装器
└── README.md                # 说明文档
```

## 核心类说明

### FeatureCalculator
- `rolling_mean(data, window)` - 滚动窗口均值
- `rolling_std(data, window)` - 滚动窗口标准差
- `rolling_frequency(data, window, num_digits)` - 滚动窗口频率
- `calculate_hurst(data)` - Hurst指数
- `calculate_lyapunov(data)` - Lyapunov指数
- `fft_transform(data)` - FFT变换

### HMMModel
- `fit(data)` - 训练HMM模型
- `predict(data)` - 预测隐藏状态
- `predict_proba(data)` - 预测状态概率

### CopulaModel
- `fit(data)` - 训练Copula模型
- `calculate_kendall_tau(i, j)` - 计算Kendall's tau
- `get_correlation_matrix()` - 获取相关矩阵

## 回退机制

如果C++模块未编译或加载失败，系统会自动使用Python回退实现，确保功能可用。

## 注意事项

1. C++模块需要编译后才能使用
2. 编译需要安装Visual Studio Build Tools
3. 如果编译失败，系统会自动使用Python实现
4. 建议在训练大量数据时使用C++模块

## 故障排除

### 编译失败
- 确保安装了Visual Studio Build Tools
- 确保安装了pybind11: `pip install pybind11`

### 导入失败
- 检查是否成功编译: `python -c "from cpp_core import pl5_core"`
- 查看错误日志

### 性能没有提升
- 检查C++模块是否成功加载: `from cpp_core import CPP_AVAILABLE; print(CPP_AVAILABLE)`
- 确保数据量足够大（小数据量差异不明显）
