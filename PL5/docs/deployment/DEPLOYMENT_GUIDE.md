# PL5 排列五高阶数理分析预测系统 - 端到端部署指南

## 📋 系统架构总览

### 1. 分层架构（V8.0）

```
┌─────────────────────────────────────────────────────────────────┐
│                        应用层 (Application)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │AutoScheduler │  │Analyze & Send│  │Email Sender  │          │
│  │  定时调度器   │  │ 分析发送模块 │  │ 邮件发送模块 │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                        智能体层 (Agents)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │Data      │ │Research  │ │Training │ │Evaluation│ │Optimization││
│  │Agent     │ │Agent     │ │Agent    │ │Agent     │ │Agent      ││
│  │数据智能体 │ │研究智能体 │ │训练智能体 │ │评估智能体 │ │优化智能体  ││
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘│
├─────────────────────────────────────────────────────────────────┤
│                        核心层 (Core)                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │Data      │ │Feature   │ │Models    │ │Self      │          │
│  │Collector │ │Engineer  │ │Predictor │ │Learning  │          │
│  │数据采集  │ │特征工程  │ │预测模型  │ │自学习    │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                        数据层 (Data)                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │       Vector Database (FAISS) + RAG Retrieval          │   │
│  │              向量数据库 + 检索增强生成                 │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                        监控层 (Monitor)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │System    │ │Perfect   │ │Prevent   │ │Immune    │          │
│  │Monitor   │ │Monitor   │ │Sleep     │ │System    │          │
│  │系统监控  │ │完美监控  │ │防睡眠    │ │免疫系统  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                        加速层 (Acceleration)                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              C++ Core (Feature Calculator)              │   │
│  │                 C++ 特征计算加速模块                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2. 数据流架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   数据源     │ --> │  数据采集   │ --> │  数据清洗   │
│ lecai.com   │     │  Collector  │     │  Cleaner    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                       ┌────────────────────────┘
                       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  向量存储    │ <-- │  特征工程   │ <-- │ 智能体分析  │
│  Vector DB  │     │  Features   │     │  Agents     │
└──────┬──────┘     └─────────────┘     └─────────────┘
       │                                      │
       │                                      │
       ▼                                      │
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   预测输出   │ <-- │  模型推理   │ <-- │  RAG增强    │
│  Predictions│     │  Inference  │     │  RAG        │
└─────────────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   效果评估   │ --> │  策略优化   │ --> │  模型更新   │
│  Evaluation │     │ Optimization│     │  Update     │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 3. 定时任务工作流

```
00:00 ┌─────────────────┐
      │  获取开奖数据    │
      │  Fetch Data     │
      └────────┬────────┘
               ▼
00:30 ┌─────────────────┐
      │  评估预测准确性  │
      │   Evaluate      │
      └────────┬────────┘
               ▼
01:00 ┌─────────────────┐
      │  策略优化学习    │
      │   Optimize      │
      └────────┬────────┘
               ▼
02:00 ┌─────────────────┐      15小时
      │  智能体训练     │────────────────┐
      │   Agent Train   │                │
      └────────┬────────┘                │
               │                         │
               ▼                         │
17:00 ┌─────────────────┐                │
      │  训练完成截止    │<───────────────┘
      │   Deadline      │
      └────────┬────────┘
               ▼
17:30 ┌─────────────────┐
      │  发送分析报告    │
      │  Send Report    │
      └─────────────────┘
```

---

## 🚀 端到端部署步骤

### 阶段一：环境准备

#### 1.1 系统要求
- **操作系统**: Windows 10/11 (64位)
- **Python**: 3.8+ (推荐 3.12)
- **内存**: 16GB+ (推荐 32GB)
- **磁盘**: 20GB+ 可用空间
- **网络**: 稳定的互联网连接

#### 1.2 安装依赖
```bash
# 安装Python依赖
pip install -r config/requirements.txt

# 主要依赖包
# - pandas, numpy, scipy (数据处理)
# - scikit-learn, hmmlearn (机器学习)
# - schedule (定时任务)
# - requests (网络请求)
# - psutil (系统监控)
# - faiss-cpu (向量数据库)
# - transformers (RAG增强)
```

#### 1.3 配置邮件
```bash
# 复制邮件配置模板
copy email_config.example.json email_config.json

# 编辑 email_config.json
{
  "smtp_server": "smtp.qq.com",
  "smtp_port": 465,
  "from_email": "your_email@qq.com",
  "to_email": "your_email@qq.com",
  "auth_code": "your_auth_code"
}
```

---

### 阶段二：系统初始化

#### 2.1 目录结构初始化
```bash
# 系统自动创建以下目录
- data/raw/          # 原始数据
- data/processed/    # 处理后数据
- models/            # 模型文件
- models/vector_index/ # 向量索引
- logs/              # 日志文件
- results/           # 结果输出
- config/            # 配置文件
```

#### 2.2 数据初始化
```bash
# 运行数据初始化
python pl5_intelligent_system.py

# 这将:
# 1. 从 lecai.com 下载历史数据
# 2. 解析并清洗数据
# 3. 计算基础特征
# 4. 构建向量索引
# 5. 保存到 data/processed/ 和 models/vector_index/
```

#### 2.3 模型初始化
```bash
# 训练初始模型
python pl5_intelligent_system.py

# 这将:
# 1. 加载处理后的数据
# 2. 提取高阶特征
# 3. 训练 HMM/Copula/BSTS/EVT 模型
# 4. 初始化智能体
# 5. 保存到 models/
```

---

### 阶段三：部署运行

#### 3.1 方式一：前台运行（调试）
```bash
# 运行完整流程
python pl5_intelligent_system.py

# 查看系统状态
python -c "from pl5_intelligent_system import PL5IntelligentSystem; import asyncio; asyncio.run(PL5IntelligentSystem().start()); print(PL5IntelligentSystem().get_system_status())"
```

#### 3.2 方式二：后台运行（生产）
```bash
# 使用启动器（推荐）
scripts\run_automation.py

# 或使用Python模块
python run_automation.py
```

#### 3.3 方式三：Windows任务计划（最佳）
```bash
# 1. 配置电源唤醒设置（管理员权限）
scripts\setup_auto_wake.bat

# 2. 创建定时任务（管理员权限）
PowerShell -ExecutionPolicy Bypass -File scripts\create_scheduled_tasks.ps1

# 这将创建以下任务:
# - PL5_DataFetch:   00:00 获取数据
# - PL5_Evaluate:    00:30 评估预测
# - PL5_Optimize:    01:00 策略优化
# - PL5_Train:       02:00 智能体训练
# - PL5_SendReport:  17:30 发送报告
```

---

### 阶段四：监控维护

#### 4.1 系统状态检查
```bash
# 检查系统状态
python -m monitor.system_checker

# 检查智能体状态
python -c "from pl5_intelligent_system import PL5IntelligentSystem; import asyncio; asyncio.run(PL5IntelligentSystem().start()); print(PL5IntelligentSystem().get_system_status())"

# 检查向量数据库状态
python -c "from src.agents.orchestrator import AgentOrchestrator; orchestrator = AgentOrchestrator(); print(orchestrator.get_vector_db_status())"
```

#### 4.2 日志监控
```bash
# 实时查看日志
tail -f logs/pl5_system.log

# 查看智能体日志
type logs/agent.log

# 查看免疫系统日志
type logs/immune_system.log
```

#### 4.3 性能监控
```bash
# 启动系统监控
python -m monitor.perfect_monitor

# 启动免疫系统监控
python -m monitor.immune_system

# 后台监控
python -m monitor.system_monitor --watch
```

---

## 📊 系统状态总览

### 当前系统状态

| 组件 | 状态 | 说明 |
|------|------|------|
| **数据** | ✅ 正常 | 7538条历史记录，最新2026073期 |
| **模型** | ✅ 已训练 | HMM/Copula/BSTS/EVT模型已就绪 |
| **智能体** | ✅ 已初始化 | 5个智能体已就绪 |
| **向量数据库** | ✅ 已构建 | FAISS向量索引已就绪 |
| **调度器** | ✅ 运行中 | PID: 12228，定时任务正常 |
| **评估历史** | ⚠️ 滞后 | 最后评估2026030期，落后43期 |
| **C++加速** | ✅ 可用 | pl5_core.cp312-win_amd64.pyd |
| **邮件** | ✅ 已配置 | lhp871096134@qq.com |
| **免疫系统** | ✅ 运行中 | 实时监控系统性能 |

### 定时任务状态

| 时间 | 任务 | 状态 |
|------|------|------|
| 00:00 | 获取开奖数据 | ⏰ 等待执行 |
| 00:30 | 评估预测准确性 | ⏰ 等待执行 |
| 01:00 | 策略优化学习 | ⏰ 等待执行 |
| 02:00 | 智能体训练 | ⏰ 等待执行 |
| 17:30 | 发送分析报告 | ⏰ 等待执行 |

---

## 🔧 故障排除

### 常见问题

#### Q1: 系统无法启动
```bash
# 检查Python环境
python --version

# 检查依赖
python -c "import pandas, numpy, scipy, sklearn, schedule, faiss"

# 运行系统检查
python -m monitor.system_checker
```

#### Q2: 邮件发送失败
- 检查邮箱授权码是否正确
- 确认SMTP服务已开启
- 检查网络连接

#### Q3: 数据获取失败
- 检查网络连接
- 确认 lecai.com 可访问
- 查看日志 logs/pl5_system.log

#### Q4: 定时任务不执行
- 检查系统是否处于睡眠状态
- 运行 scripts\setup_auto_wake.bat 配置唤醒
- 检查Windows任务计划程序

#### Q5: 智能体初始化失败
- 检查Python环境和依赖
- 查看日志 logs/agent.log
- 运行系统检查工具

#### Q6: 向量数据库构建失败
- 检查内存是否足够（至少16GB）
- 查看日志 logs/vector_db.log
- 重新运行数据初始化

---

## 📈 性能优化

### C++加速模块
```python
# 使用C++加速特征计算
from cpp_core import FeatureCalculator

fc = FeatureCalculator()
mean = fc.calculate_mean(data)
rolling_mean = fc.rolling_mean(data, window=20)
```

### 内存优化
- 限制特征数量: FEATURE_CONFIG["max_features"] = 200
- 定期清理日志文件
- 使用增量学习而非全量训练
- 优化向量索引大小

### 智能体优化
- 调整智能体并行度
- 优化智能体通信效率
- 合理配置智能体资源占用

---

## 🔒 安全注意事项

1. **邮箱授权码**: 不要泄露，使用环境变量或配置文件
2. **数据备份**: 定期备份 models/learning_history.json 和 models/vector_index/
3. **日志清理**: 定期清理 logs/ 目录，避免磁盘满
4. **向量数据库安全**: 保护向量索引文件，避免未授权访问

---

## 📞 技术支持

- **系统检查**: `python -m monitor.system_checker`
- **查看日志**: `logs/pl5_system.log`
- **实时监控**: `python -m monitor.perfect_monitor`
- **智能体状态**: `python -m monitor.agent_monitor`

---

**部署完成！系统已准备就绪，可以开始24/7自动化运行。**
