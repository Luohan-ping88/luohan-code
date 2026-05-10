# PL5系统自动化测试文档

## 概述

本文档描述了PL5预测系统的自动化测试框架，包括单元测试、集成测试和端到端测试的实现和使用方法。

## 测试结构

```
tests/
├── conftest.py                    # 测试配置和共享夹具
├── pytest.ini                     # pytest配置文件
├── unit/                          # 单元测试
│   ├── test_data_collector.py     # 数据采集模块测试
│   ├── test_feature_engineer.py   # 特征工程模块测试
│   └── test_predictor.py          # 预测模块测试
├── integration/                   # 集成测试
│   ├── test_data_flow.py          # 数据流测试
│   └── test_workflow.py           # 工作流测试
├── e2e/                          # 端到端测试
│   └── test_full_pipeline.py      # 完整业务流程测试
└── fixtures/                      # 测试数据文件
```

## 测试类型

### 1. 单元测试 (Unit Tests)

单元测试针对单个组件进行测试，确保每个模块的功能正确性。

#### 覆盖模块

- **数据采集模块** (`test_data_collector.py`)
  - `DataValidator`: 数据验证器
  - `DataVersionManager`: 数据版本管理器
  - `PL5DataCollectorV8`: 数据采集器
  - `retry_on_failure`: 重试装饰器

- **特征工程模块** (`test_feature_engineer.py`)
  - `FeatureEngineerV9`: 特征工程器
  - `FeatureCacheManager`: 特征缓存管理器
  - `FeatureDriftDetector`: 特征漂移检测器
  - `FeatureScaler`: 特征标准化器
  - `FeatureImportanceAnalyzer`: 特征重要性分析器
  - `FeatureConfig`: 特征配置

- **预测模块** (`test_predictor.py`)
  - `PL5Predictor`: 主预测器
  - `HMMModel`: 隐马尔可夫模型
  - `CopulaModel`: Copula模型
  - `BSTSModel`: 贝叶斯结构时序模型
  - `ExtremeValueModel`: 极值模型
  - `StackingEnsemble`: Stacking集成模型

#### 运行单元测试

```bash
# 运行所有单元测试
pytest tests/unit/ -v

# 运行特定模块的单元测试
pytest tests/unit/test_data_collector.py -v
pytest tests/unit/test_feature_engineer.py -v
pytest tests/unit/test_predictor.py -v

# 运行带有特定标记的测试
pytest tests/unit/ -m "unit" -v
pytest tests/unit/ -m "data" -v
```

### 2. 集成测试 (Integration Tests)

集成测试验证模块间的协作和数据流。

#### 测试内容

- **数据流测试** (`test_data_flow.py`)
  - 数据采集到特征工程的流程
  - 特征工程到预测的流程
  - 端到端数据管道
  - 数据版本一致性
  - 模块间通信
  - 缓存集成

- **工作流测试** (`test_workflow.py`)
  - 训练工作流
  - 预测工作流
  - 数据更新工作流
  - 错误恢复工作流
  - 性能工作流

#### 运行集成测试

```bash
# 运行所有集成测试
pytest tests/integration/ -v

# 运行特定测试
pytest tests/integration/test_data_flow.py -v
pytest tests/integration/test_workflow.py -v

# 运行带有集成标记的测试
pytest tests/ -m "integration" -v
```

### 3. 端到端测试 (E2E Tests)

端到端测试验证完整的业务流程。

#### 测试内容

- **完整业务流程** (`test_full_pipeline.py`)
  - 完整预测流程
  - 模型持久化工作流
  - 错误处理流程
  - 数据漂移检测流程
  - 系统性能要求
  - 日常运营场景
  - 模型部署场景

#### 运行端到端测试

```bash
# 运行所有端到端测试
pytest tests/e2e/ -v

# 运行特定测试
pytest tests/e2e/test_full_pipeline.py -v

# 运行带有e2e标记的测试
pytest tests/ -m "e2e" -v
```

## 测试标记

测试使用以下标记进行分类：

| 标记 | 描述 | 使用场景 |
|------|------|----------|
| `unit` | 单元测试 | 测试单个组件 |
| `integration` | 集成测试 | 测试模块间协作 |
| `e2e` | 端到端测试 | 测试完整业务流程 |
| `performance` | 性能测试 | 测试系统性能 |
| `data` | 数据相关 | 数据模块测试 |
| `model` | 模型相关 | 模型模块测试 |
| `slow` | 慢速测试 | 执行时间>10秒 |
| `fast` | 快速测试 | 执行时间<1秒 |

### 使用标记运行测试

```bash
# 只运行单元测试
pytest tests/ -m "unit" -v

# 排除慢速测试
pytest tests/ -m "not slow" -v

# 运行数据相关的单元测试
pytest tests/ -m "unit and data" -v

# 运行集成测试和端到端测试
pytest tests/ -m "integration or e2e" -v
```

## 测试覆盖率

### 生成覆盖率报告

```bash
# 安装pytest-cov
pip install pytest-cov

# 生成覆盖率报告
pytest tests/ --cov=src --cov-report=term-missing

# 生成HTML覆盖率报告
pytest tests/ --cov=src --cov-report=html:tests/coverage_html

# 生成XML覆盖率报告（用于CI/CD）
pytest tests/ --cov=src --cov-report=xml:tests/coverage.xml

# 设置覆盖率阈值
pytest tests/ --cov=src --cov-fail-under=80
```

### 覆盖率目标

- **单元测试覆盖率**: ≥80%
- **集成测试覆盖率**: ≥70%
- **端到端测试覆盖率**: ≥60%
- **总体覆盖率**: ≥80%

## 测试数据

测试数据通过 `conftest.py` 中的 fixtures 提供：

### 可用Fixtures

| Fixture | 描述 |
|---------|------|
| `sample_pl5_data` | 样本PL5数据（50条记录） |
| `sample_large_dataset` | 大样本数据集（500条记录） |
| `sample_invalid_data` | 包含无效值的数据 |
| `sample_duplicate_data` | 包含重复数据 |
| `sample_feature_data` | 样本特征数据 |
| `sample_raw_text` | 原始文本格式数据 |
| `test_config` | 测试配置 |
| `test_logger` | 测试日志器 |
| `temp_directory` | 临时目录 |
| `mock_data_collector` | Mock数据采集器 |
| `mock_feature_engineer` | Mock特征工程器 |
| `mock_predictor` | Mock预测器 |

### TestDataGenerator

`TestDataGenerator` 类提供以下静态方法：

```python
# 生成PL5序列数据
TestDataGenerator.generate_pl5_sequence(n_records=100, start_period=2026001)

# 生成特征数据
TestDataGenerator.generate_features(n_samples=100, n_features=50)

# 生成原始文本数据
TestDataGenerator.generate_raw_text_data(n_records=50)

# 生成无效数据
TestDataGenerator.generate_invalid_data(invalid_type='mixed')
```

## 运行测试

### 基本用法

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定目录的测试
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v

# 运行特定文件
pytest tests/unit/test_data_collector.py -v

# 运行特定测试类
pytest tests/unit/test_data_collector.py::TestDataValidator -v

# 运行特定测试方法
pytest tests/unit/test_data_collector.py::TestDataValidator::test_validate_period_valid -v
```

### 高级用法

```bash
# 并行运行测试（需要pytest-xdist）
pytest tests/ -n auto

# 失败时停止
pytest tests/ -x

# 失败时重新运行（需要pytest-rerunfailures）
pytest tests/ --reruns 3

# 显示最慢的10个测试
pytest tests/ --durations=10

# 生成JUnit XML报告
pytest tests/ --junitxml=tests/results.xml

# 只运行上次失败的测试
pytest tests/ --lf

# 先运行上次失败的测试，然后运行其他测试
pytest tests/ --ff
```

## 持续集成

### GitHub Actions 配置示例

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run unit tests
      run: pytest tests/unit/ -v --cov=src --cov-report=xml
    
    - name: Run integration tests
      run: pytest tests/integration/ -v
    
    - name: Run e2e tests
      run: pytest tests/e2e/ -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        file: ./coverage.xml
```

## 测试报告

### 生成测试报告

```bash
# 生成HTML测试报告（需要pytest-html）
pytest tests/ --html=tests/report.html --self-contained-html

# 生成Allure报告（需要allure-pytest）
pytest tests/ --alluredir=tests/allure-results
allure serve tests/allure-results
```

## 最佳实践

1. **测试命名**: 使用描述性的测试名称，如 `test_validate_period_valid`
2. **测试独立性**: 每个测试应该独立运行，不依赖其他测试
3. **使用Fixtures**: 使用fixtures提供测试数据和资源
4. **标记测试**: 使用适当的标记分类测试
5. **清理资源**: 使用临时目录和自动清理机制
6. **Mock外部依赖**: 使用Mock隔离外部依赖
7. **测试边界条件**: 测试正常、异常和边界情况

## 故障排除

### 常见问题

1. **导入错误**: 确保项目根目录在Python路径中
2. **Fixtures未找到**: 检查 `conftest.py` 位置
3. **标记未注册**: 在 `pytest.ini` 中注册标记
4. **覆盖率不准确**: 确保测试了所有代码路径

### 调试测试

```bash
# 使用pdb调试
pytest tests/ --pdb

# 在失败时进入pdb
pytest tests/ --pdb-failures

# 显示详细的fixture信息
pytest tests/ --fixtures-per-test

# 显示详细的输出
pytest tests/ -v -s
```

## 更新日志

### 2026-04-06
- 初始版本
- 创建完整的测试框架
- 实现单元测试、集成测试和端到端测试
- 添加测试文档

## 参考

- [pytest官方文档](https://docs.pytest.org/)
- [pytest-cov文档](https://pytest-cov.readthedocs.io/)
- [pytest-mock文档](https://pytest-mock.readthedocs.io/)
