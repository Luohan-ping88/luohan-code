# PL5 项目优化目录结构

## 优化后的目录结构

```
PL5/
├── core/              # 核心功能模块
│   ├── data/          # 数据处理模块
│   │   ├── __init__.py
│   │   ├── collector.py      # 数据采集器
│   │   ├── validator.py      # 数据验证器
│   │   └── config.py         # 数据模块配置
│   ├── features/      # 特征工程模块
│   │   ├── __init__.py
│   │   ├── engineer.py       # 特征工程师
│   │   └── config.py         # 特征模块配置
│   ├── models/        # 模型预测模块
│   │   ├── __init__.py
│   │   ├── predictor.py      # 预测器
│   │   └── config.py         # 模型模块配置
│   ├── utils/         # 工具函数
│   │   ├── __init__.py
│   │   ├── logger.py         # 日志系统
│   │   └── config.py         # 工具模块配置
│   ├── __init__.py
│   └── orchestrator.py        # 统一架构编排器
├── service/           # 服务层模块
│   ├── __init__.py
│   ├── scheduler.py          # 任务调度器
│   ├── monitor.py            # 系统监控
│   └── recovery.py           # 恢复管理器
├── scripts/           # 脚本文件
│   ├── setup/                # 安装脚本
│   ├── test/                 # 测试脚本
│   └── utility/              # 工具脚本
├── data/              # 数据文件
│   ├── raw/                  # 原始数据
│   │   └── backups/          # 数据备份
│   └── processed/            # 处理后的数据
├── models/            # 模型文件
├── logs/              # 日志文件
├── results/           # 结果文件
├── tests/             # 测试文件
│   ├── integration/          # 集成测试
│   └── performance/          # 性能测试
├── main.py            # 主入口文件
├── service.py         # 服务主程序
├── README.md          # 项目说明
└── requirements.txt   # 依赖库
```

## 模块划分说明

### 1. core/ - 核心功能模块
- **data/**: 负责数据的采集、验证和处理
- **features/**: 负责特征工程，提取和选择特征
- **models/**: 负责模型的训练、预测和评估
- **utils/**: 提供通用工具函数和配置
- **orchestrator.py**: 统一架构编排器，协调各个模块的工作流程

### 2. service/ - 服务层模块
- **scheduler.py**: 任务调度器，管理定时任务
- **monitor.py**: 系统监控，监控系统状态
- **recovery.py**: 恢复管理器，处理系统故障恢复

### 3. scripts/ - 脚本文件
- **setup/**: 安装和配置脚本
- **test/**: 测试脚本
- **utility/**: 工具脚本

### 4. 数据和结果目录
- **data/**: 存储原始数据和处理后的数据
- **models/**: 存储训练好的模型
- **logs/**: 存储系统日志
- **results/**: 存储预测结果和评估报告

### 5. 测试目录
- **tests/**: 存储测试文件，包括集成测试和性能测试

## 核心文件说明

### 保留的核心文件
- **main.py**: 主入口文件，提供训练和预测功能
- **service.py**: 服务主程序，管理系统运行
- **core/orchestrator.py**: 统一架构编排器
- **core/data/collector.py**: 数据采集器
- **core/features/engineer.py**: 特征工程师
- **core/models/predictor.py**: 预测器
- **core/utils/logger.py**: 日志系统

### 移除的冗余文件
- 重复的脚本文件（如多个版本的相同功能脚本）
- 过时的配置文件
- 测试用的临时文件
- 不再使用的备份文件

## 优势

1. **结构清晰**: 按功能模块划分，模块边界明确
2. **易于维护**: 代码组织合理，便于查找和修改
3. **性能保持**: 核心算法逻辑保持不变，确保训练性能不受影响
4. **扩展性强**: 模块化设计便于添加新功能
5. **测试友好**: 独立的测试目录便于单元测试和集成测试
