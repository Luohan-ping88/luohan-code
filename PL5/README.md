# AI核心服务系统

## 系统概述

AI核心服务系统是一个功能强大的AI工具系统，提供工作流编排、API服务、安全系统和性能优化等核心功能。系统采用模块化设计，支持复杂任务的流程编排，提供RESTful接口，确保系统安全，并优化性能。

## 核心功能

### 1. 工作流编排引擎
- 支持线性、条件和并行工作流
- 实现工作流持久化和恢复功能
- 增强条件表达式支持
- 工作流模板管理

### 2. API服务
- 实现RESTful接口
- JWT认证和授权系统
- 速率限制和错误处理
- WebSocket支持（实时更新）
- 安全策略配置和漏洞扫描接口
- 性能相关接口（负载均衡和自动扩展）

### 3. 安全系统
- 输入验证和清理
- 细粒度权限控制
- 密钥管理和数据加密
- 安全审计和日志记录
- 防DoS保护
- 漏洞扫描（输入验证、配置、文件系统）

### 4. 性能优化
- 智能缓存策略
- 性能监控和分析
- 自动扩展和负载均衡
- 异步操作优化

## 系统架构

系统采用分层架构设计：

1. **核心层**：包含核心类型定义、工具注册、工作流引擎等
2. **服务层**：提供API服务、安全服务、性能服务等
3. **工具层**：包含各种AI工具和功能
4. **存储层**：负责数据持久化和缓存

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
python -m src.ai.api
```

服务将在 `http://localhost:8000` 启动。

## API接口

### 认证接口
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户信息

### 工具接口
- `GET /api/tools` - 列出所有可用工具
- `POST /api/tools/{tool_name}/execute` - 执行工具

### Agent接口
- `POST /api/agents/create` - 创建Agent
- `POST /api/agents/run` - 运行Agent

### 工作流接口
- `POST /api/workflows/create` - 创建工作流
- `POST /api/workflows/{workflow_id}/run` - 运行工作流
- `GET /api/workflows/{workflow_id}/status` - 获取工作流状态
- `POST /api/workflows/{workflow_id}/pause` - 暂停工作流
- `POST /api/workflows/{workflow_id}/resume` - 恢复工作流
- `DELETE /api/workflows/{workflow_id}` - 删除工作流

### 安全接口
- `GET /api/security/config` - 获取安全配置
- `POST /api/security/config` - 更新安全配置
- `POST /api/security/scan` - 运行安全扫描
- `GET /api/security/vulnerabilities` - 获取漏洞列表

### 性能接口
- `GET /api/performance/load-balancer/services` - 列出负载均衡器服务
- `POST /api/performance/load-balancer/services` - 注册服务到负载均衡器
- `DELETE /api/performance/load-balancer/services/{service_id}` - 从负载均衡器注销服务
- `GET /api/performance/auto-scaler/instances` - 列出自动扩展器实例
- `POST /api/performance/auto-scaler/scale` - 执行自动扩展决策

### 健康检查
- `GET /api/health` - 健康检查

## 示例代码

### 1. 工作流编排示例

```python
from src.ai.orchestrator import WorkflowEngine, Workflow
from src.ai.types import WorkflowStep

# 创建工作流步骤
steps = [
    WorkflowStep(
        name="step1",
        tool_name="echo",
        parameters={"message": "Hello"}
    ),
    WorkflowStep(
        name="step2",
        tool_name="echo",
        parameters={"message": "Hello"},
        condition_expr="{{step1.output}} == 'Hello'"
    )
]

# 创建工作流
workflow = Workflow(name="test-workflow", description="Test workflow", steps=steps)

# 运行工作流
engine = WorkflowEngine()
result = await engine.run_workflow(workflow)
print(result)
```

### 2. API调用示例

```python
import requests

# 登录获取token
response = requests.post("http://localhost:8000/api/auth/login", params={"username": "admin", "password": "admin123"})
token = response.json()["access_token"]

# 执行工具
headers = {"Authorization": f"Bearer {token}"}
data = {"parameters": {"message": "Hello World"}}
response = requests.post("http://localhost:8000/api/tools/echo/execute", json=data, headers=headers)
print(response.json())
```

### 3. 安全扫描示例

```python
import requests

# 登录获取token
response = requests.post("http://localhost:8000/api/auth/login", params={"username": "admin", "password": "admin123"})
token = response.json()["access_token"]

# 运行安全扫描
headers = {"Authorization": f"Bearer {token}"}
data = {"input_data": {"name": "test", "age": "not-a-number"}, "config": {"debug": True}}
response = requests.post("http://localhost:8000/api/security/scan", json=data, headers=headers)
print(response.json())
```

## 配置选项

### 安全配置

安全配置可以通过 `SecurityConfig` 类进行管理，主要配置项包括：
- `MAX_STRING_LENGTH` - 最大字符串长度
- `MAX_REQUESTS_PER_MINUTE` - 每分钟最大请求数
- `PASSWORD_MIN_LENGTH` - 密码最小长度
- `ENABLE_RATE_LIMITING` - 是否启用速率限制
- `ENABLE_XSS_PROTECTION` - 是否启用XSS保护

### 性能配置

性能配置可以通过相应的组件进行管理：
- 缓存配置：通过 `SimpleCache` 类设置
- 负载均衡配置：通过 `LoadBalancer` 类设置
- 自动扩展配置：通过 `AutoScaler` 类设置

## 安全最佳实践

1. 使用强密码和定期密码更换
2. 启用所有安全防护措施
3. 定期运行漏洞扫描
4. 限制API访问频率
5. 加密敏感数据
6. 实施细粒度权限控制

## 性能优化建议

1. 合理设置缓存策略
2. 监控系统性能指标
3. 根据负载自动调整资源
4. 使用负载均衡分散流量
5. 优化异步操作

## 故障排除

### 常见问题

1. **API认证失败**：检查用户名和密码是否正确，确保JWT密钥配置正确。
2. **工作流执行失败**：检查工作流步骤配置是否正确，确保工具存在且可用。
3. **性能问题**：检查缓存配置，考虑启用自动扩展。
4. **安全漏洞**：运行漏洞扫描，根据报告修复问题。

### 日志和监控

- 安全日志：`./security_audit.log`
- 性能日志：`./performance.log`
- 工作流历史：`./workflows/` 目录

## 贡献指南

1. 克隆代码库
2. 创建新分支
3. 实现功能或修复bug
4. 编写测试用例
5. 提交PR

## 许可证

MIT License

---

## 📚 文档索引

查看 [docs/DOCUMENTATION_INDEX.md](docs/DOCUMENTATION_INDEX.md) 获取完整的文档导航和索引。
