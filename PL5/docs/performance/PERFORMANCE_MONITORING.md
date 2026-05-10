# PL5系统性能监控与优化文档

## 概述

本文档描述PL5预测系统的性能监控与优化实现，包括：
- 性能监控模块
- 告警系统
- 性能报告生成
- 性能优化策略

## 性能目标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 训练流程 | < 5分钟 | 完整训练流程耗时 |
| 预测流程 | < 30秒 | 单次预测耗时 |
| CPU利用率 | < 80% | 系统CPU使用率 |
| 内存使用 | < 2GB | 系统内存占用 |
| 缓存命中率 | > 30% | 多级缓存命中率 |

## 监控模块

### 1. 性能监控器 (monitor/performance_monitor.py)

#### 功能特性
- **实时指标收集**：CPU、内存、磁盘I/O、网络
- **训练/预测耗时跟踪**：自动记录训练和预测时间
- **缓存命中率监控**：统计缓存命中和未命中次数
- **阈值告警检测**：自动检测性能指标是否超过阈值
- **数据持久化**：指标数据保存到 `logs/performance_metrics.jsonl`

#### 核心类

```python
class PerformanceMonitor:
    """性能监控器"""
    
    # 性能阈值配置
    THRESHOLDS = {
        'cpu_percent': 80.0,          # CPU使用率告警阈值
        'memory_percent': 85.0,       # 内存使用率告警阈值
        'memory_used_mb': 1800,       # 内存使用告警阈值 (1.8GB)
        'disk_percent': 90.0,         # 磁盘使用率告警阈值
        'training_duration_sec': 300, # 训练耗时告警阈值 (5分钟)
        'prediction_duration_sec': 30, # 预测耗时告警阈值 (30秒)
        'cache_hit_rate': 30.0,       # 缓存命中率警告阈值 (%)
    }
```

#### 使用方法

```python
from monitor.performance_monitor import (
    start_monitoring, 
    stop_monitoring,
    track_performance,
    record_cache_hit,
    record_cache_miss
)

# 启动监控
monitor = start_monitoring()

# 使用装饰器跟踪函数性能
@track_performance(operation_type='training')
def train_model():
    # 训练代码
    pass

@track_performance(operation_type='prediction')
def predict():
    # 预测代码
    pass

# 记录缓存操作
record_cache_hit()   # 缓存命中
record_cache_miss()  # 缓存未命中

# 停止监控
stop_monitoring()
```

#### 性能指标数据结构

```python
@dataclass
class PerformanceMetrics:
    timestamp: str              # 时间戳
    cpu_percent: float          # CPU使用率
    memory_percent: float       # 内存使用率
    memory_used_mb: float       # 内存使用(MB)
    memory_total_mb: float      # 总内存(MB)
    disk_io_read_mb: float      # 磁盘读取速率(MB/s)
    disk_io_write_mb: float     # 磁盘写入速率(MB/s)
    disk_percent: float         # 磁盘使用率
    training_duration_sec: float    # 训练耗时(秒)
    prediction_duration_sec: float  # 预测耗时(秒)
    cache_hit_rate: float       # 缓存命中率(%)
    cache_hits: int             # 缓存命中次数
    cache_misses: int           # 缓存未命中次数
    process_cpu_percent: float  # 进程CPU使用率
    process_memory_mb: float    # 进程内存使用(MB)
    thread_count: int           # 线程数
    open_files: int             # 打开文件数
    network_sent_mb: float      # 网络发送(MB)
    network_recv_mb: float      # 网络接收(MB)
```

### 2. 告警系统 (monitor/alert_system.py)

#### 功能特性
- **基于规则的告警检测**：支持多条件、多阈值告警
- **多渠道通知**：日志、邮件、Webhook、短信
- **告警抑制**：冷却期机制避免告警风暴
- **告警升级**：多级告警升级策略
- **告警历史**：完整的告警记录和统计

#### 告警规则配置 (config/alert_rules.json)

```json
{
  "rules": [
    {
      "id": "cpu_high",
      "name": "CPU使用率过高",
      "enabled": true,
      "severity": "warning",
      "condition": {
        "metric": "cpu_percent",
        "operator": ">",
        "threshold": 80,
        "duration_sec": 300
      },
      "actions": ["log", "email"],
      "cooldown_sec": 600
    }
  ]
}
```

#### 告警级别

| 级别 | 说明 | 默认动作 |
|------|------|----------|
| info | 信息提示 | log |
| warning | 警告 | log, email |
| critical | 严重 | log, email, alert, notify_admin |

#### 使用方法

```python
from monitor.alert_system import (
    start_alert_system,
    stop_alert_system,
    get_active_alerts,
    acknowledge_alert,
    resolve_alert
)

# 启动告警系统
alert_manager = start_alert_system()

# 获取活跃告警
active_alerts = get_active_alerts()
critical_alerts = get_active_alerts(severity='critical')

# 确认告警
acknowledge_alert('alert_id', acknowledged_by='admin')

# 解决告警
resolve_alert('alert_id', resolved_by='admin')

# 停止告警系统
stop_alert_system()
```

### 3. 性能报告生成器 (scripts/utility/generate_performance_report.py)

#### 功能特性
- **多格式报告**：支持文本和HTML格式
- **趋势分析**：自动计算性能趋势
- **告警统计**：汇总告警数据
- **优化建议**：基于数据分析给出优化建议

#### 使用方法

```python
from scripts.utility.generate_performance_report import PerformanceReportGenerator

# 创建生成器
generator = PerformanceReportGenerator()

# 生成文本报告
text_report = generator.generate_text_report(hours=24)
print(text_report)

# 生成HTML报告
html_report = generator.generate_html_report(hours=24)

# 保存报告
saved_files = generator.save_report(hours=24, format='both')
# 返回: {'text': Path, 'html': Path}
```

#### 命令行使用

```bash
# 生成并打印文本报告
python scripts/utility/generate_performance_report.py --print --hours 24

# 生成文本和HTML报告
python scripts/utility/generate_performance_report.py --format both --hours 24

# 指定输出目录
python scripts/utility/generate_performance_report.py --output ./my_reports
```

## 性能优化策略

### 1. 特征工程优化

基于任务2的重构成果，特征工程已实现以下优化：

#### 并行计算
```python
# 使用joblib并行计算特征组
from joblib import Parallel, delayed

results = Parallel(n_jobs=-1, prefer='threads')(
    delayed(self._compute_feature_group)(df.copy(), method_name)
    for _, method_name in active_groups
)
```

#### 特征缓存
```python
# 基于hash的LRU缓存
cache_key = self.cache.get_key(df, (select_top, feature_selection_method, enable_scaler))
cached = self.cache.get(cache_key)
if cached is not None:
    return cached  # 缓存命中
```

#### 向量化计算
- 消除Python循环，使用numpy/pandas内置操作
- Rolling操作使用向量化实现
- 统计特征使用cumsum技巧加速

### 2. 模型训练优化

#### 并行训练
```python
# 预测器V9已实现并行训练
def train_position_models(self, data, feature_cols):
    def fit_single_position(pos):
        # 训练单个位置模型
        return self._fit_single_position(X, y, tscv, pos)
    
    results = self._parallel_executor.map(fit_single_position, POSITIONS)
```

#### 多级缓存
```python
# L1内存缓存 + L2磁盘缓存
from src.core.cache import get_global_cache

cache = get_global_cache()
cache.put(key, value, ttl=300)  # 5分钟TTL
value, level = cache.get(key)   # 返回缓存值和级别
```

### 3. 预测响应优化

#### 预测结果缓存
```python
# 预测结果缓存5分钟
cache_key = f"pred_{hash(features.tobytes())}_{top_k}"
cached, _ = self._cache.get(cache_key)
if cached is not None:
    return cached  # 缓存命中

# 执行预测后存入缓存
self._cache.put(cache_key, result, ttl=300)
```

## 监控数据文件

### 性能指标文件
- **路径**: `logs/performance_metrics.jsonl`
- **格式**: JSON Lines，每行一条记录
- **示例**:
```json
{
  "timestamp": "2026-04-06T10:30:00",
  "cpu_percent": 45.2,
  "memory_percent": 65.3,
  "memory_used_mb": 1200.5,
  "training_duration_sec": 180.5,
  "cache_hit_rate": 75.0
}
```

### 告警记录文件
- **路径**: `logs/alerts.jsonl`
- **格式**: JSON Lines，每行一条告警记录
- **示例**:
```json
{
  "id": "cpu_high_1712380000",
  "rule_id": "cpu_high",
  "name": "CPU使用率过高",
  "severity": "warning",
  "status": "active",
  "created_at": "2026-04-06T10:30:00",
  "metric_name": "cpu_percent",
  "metric_value": 85.5,
  "threshold": 80.0
}
```

## 集成指南

### 1. 系统集成

在系统启动时初始化监控和告警：

```python
# main.py 或系统入口
from monitor.performance_monitor import start_monitoring
from monitor.alert_system import start_alert_system

def initialize_system():
    # 启动性能监控
    performance_monitor = start_monitoring()
    
    # 启动告警系统
    alert_manager = start_alert_system()
    
    # ... 其他初始化代码

def shutdown_system():
    from monitor.performance_monitor import stop_monitoring
    from monitor.alert_system import stop_alert_system
    
    stop_monitoring()
    stop_alert_system()
```

### 2. 训练流程集成

```python
from monitor.performance_monitor import track_performance

class TrainingPipeline:
    @track_performance(operation_type='training')
    def run_training(self):
        # 特征工程
        features = self.feature_engineer.extract_all_features(data)
        
        # 模型训练
        self.model.fit(features, targets)
        
        # 保存模型
        self.model.save()
```

### 3. 预测流程集成

```python
from monitor.performance_monitor import track_performance, record_cache_hit, record_cache_miss

class PredictionService:
    @track_performance(operation_type='prediction')
    def predict(self, features):
        # 检查缓存
        cache_key = self._get_cache_key(features)
        cached = self.cache.get(cache_key)
        
        if cached:
            record_cache_hit()
            return cached
        
        record_cache_miss()
        
        # 执行预测
        result = self.model.predict(features)
        
        # 存入缓存
        self.cache.put(cache_key, result)
        
        return result
```

## 性能调优建议

### CPU优化
1. **并行度调整**：根据CPU核心数调整`n_jobs`参数
2. **特征工程优化**：减少不必要的特征计算
3. **批处理**：使用批处理减少函数调用开销

### 内存优化
1. **数据类型优化**：使用更小的数据类型（如int32代替int64）
2. **分块处理**：大数据集分块处理
3. **及时释放**：使用`del`及时释放大对象
4. **垃圾回收**：定期调用`gc.collect()`

### 缓存优化
1. **预热策略**：系统启动时预热常用数据缓存
2. **TTL设置**：合理设置缓存过期时间
3. **缓存大小**：根据内存情况调整缓存大小

### I/O优化
1. **异步I/O**：使用异步方式处理文件和网络I/O
2. **批量读写**：减少I/O操作次数
3. **压缩存储**：使用压缩减少磁盘占用

## 故障排查

### 性能问题诊断

1. **查看性能指标**
```python
from monitor.performance_monitor import get_global_monitor

monitor = get_global_monitor()
summary = monitor.get_summary()
print(json.dumps(summary, indent=2))
```

2. **查看活跃告警**
```python
from monitor.alert_system import get_active_alerts

alerts = get_active_alerts()
for alert in alerts:
    print(f"[{alert.severity}] {alert.name}: {alert.message}")
```

3. **生成性能报告**
```bash
python scripts/utility/generate_performance_report.py --print
```

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 训练耗时过长 | 特征过多/并行度不足 | 减少特征数量/增加n_jobs |
| 内存使用过高 | 数据缓存过多/内存泄漏 | 清理缓存/检查内存泄漏 |
| 缓存命中率低 | 缓存策略不当/预热不足 | 调整缓存策略/增加预热 |
| CPU使用率过高 | 并行任务过多 | 减少并行度/优化算法 |

## 附录

### A. 监控模块文件列表

```
monitor/
├── __init__.py
├── performance_monitor.py    # 性能监控核心模块
├── alert_system.py           # 告警系统模块
└── system_monitor.py         # 系统监控工具

config/
└── alert_rules.json          # 告警规则配置

scripts/utility/
└── generate_performance_report.py  # 性能报告生成器

logs/
├── performance_metrics.jsonl # 性能指标数据
└── alerts.jsonl              # 告警记录数据
```

### B. 性能目标对比表

| 指标 | 目标值 | 当前状态 | 状态 |
|------|--------|----------|------|
| 训练流程 | < 5分钟 | 待测试 | - |
| 预测流程 | < 30秒 | 待测试 | - |
| CPU利用率 | < 80% | 待测试 | - |
| 内存使用 | < 2GB | 待测试 | - |
| 缓存命中率 | > 30% | 待测试 | - |

### C. 更新日志

- **2026-04-06**: 初始版本，实现基础监控和告警功能
