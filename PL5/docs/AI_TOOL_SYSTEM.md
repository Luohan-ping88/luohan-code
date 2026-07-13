# AI大模型工具系统文档

## 1. 系统概述

AI大模型工具系统是一个为PL5预测系统设计的智能执行框架，旨在让智能体拥有动手能力和自主探索能力。系统采用分层架构，包括模型层、记忆层、智能体层和工具系统，支持多种大模型和工具集成。

## 2. 系统架构

### 2.1 核心组件

- **模型层**：负责大模型的管理和调用，支持本地模型（如llama-cpp）、API模型（如OpenAI）和HuggingFace模型
- **记忆层**：管理智能体的记忆，包括对话记忆、执行记忆、长期记忆和向量记忆
- **智能体层**：实现不同类型的智能体，如ReAct模式、工具调用和对话专用智能体
- **工具系统**：提供各种工具，如搜索、计算、代码执行和PL5预测系统工具
- **工作流编排**：支持复杂任务的流程编排，包括线性、条件和并行工作流
- **API服务**：提供RESTful API接口，方便外部系统集成
- **安全系统**：提供输入验证、权限控制、敏感信息保护和防DoS保护

### 2.2 目录结构

```
src/
├── ai/              # AI工具系统
│   ├── models/      # 模型层
│   ├── memory/      # 记忆层
│   ├── agents/      # 智能体层
│   ├── tools/       # 工具系统
│   ├── api.py       # API服务
│   ├── orchestrator.py  # 工作流编排
│   ├── security.py  # 安全系统
│   ├── types.py     # 类型定义
│   └── registry.py  # 工具注册表
└── tools/           # 原始PL5工具系统
```

## 3. 快速开始

### 3.1 安装依赖

```bash
pip install -r requirements.txt
```

### 3.2 运行示例

```bash
python examples/ai_tool_system_example.py
```

### 3.3 启动API服务

```bash
python src/ai/api.py
```

## 4. 核心功能

### 4.1 模型管理

- **模型类型**：支持本地模型、OpenAI API模型和HuggingFace模型
- **模型配置**：可配置模型参数、API密钥和基础URL
- **模型切换**：可根据需要切换不同的模型

### 4.2 记忆系统

- **对话记忆**：存储和管理对话历史
- **长期记忆**：存储和检索长期知识
- **向量记忆**：支持语义搜索和相似度匹配
- **记忆管理**：提供记忆的添加、获取和清理功能

### 4.3 智能体系统

- **ReAct模式**：结合推理和行动的智能体实现
- **工具调用**：专门用于调用工具的智能体
- **对话专用**：优化对话体验的智能体
- **Agent编排**：管理多个智能体的协作

### 4.4 工具系统

- **内置工具**：搜索、计算、代码执行等
- **PL5工具**：集成PL5预测系统的工具
- **自定义工具**：支持添加自定义工具
- **工具发现**：自动发现和注册工具

### 4.5 工作流编排

- **线性工作流**：按顺序执行步骤
- **并行工作流**：并行执行多个步骤
- **条件工作流**：根据条件执行不同步骤
- **内置模板**：提供数据分析、预测和研究等工作流模板

### 4.6 API服务

- **RESTful接口**：提供标准的RESTful API
- **CORS支持**：支持跨域请求
- **健康检查**：提供系统健康状态检查
- **系统统计**：提供系统运行状态统计

### 4.7 安全系统

- **输入验证**：验证和清理用户输入
- **权限控制**：管理用户对工具的访问权限
- **敏感信息保护**：保护API密钥等敏感信息
- **安全审计**：记录安全相关事件
- **防DoS保护**：防止DoS攻击

## 5. 使用指南

### 5.1 模型使用

```python
from src.ai.models import LLMFactory
from src.ai.types import LLMConfig, LLMType

# 创建模型配置
config = LLMConfig(
    model_type=LLMType.LOCAL,
    model_name="test_model",
    max_tokens=1000,
    temperature=0.7
)

# 创建模型
model = LLMFactory.create(config)

# 生成文本
response = model.generate("Hello, AI!")

# 对话
messages = [{"role": "user", "content": "What is PL5?"}]
chat_response = model.chat(messages)
```

### 5.2 记忆系统使用

```python
from src.ai.memory import ConversationMemory
from src.ai.types import MemoryConfig, MemoryType

# 创建记忆配置
config = MemoryConfig(
    memory_type=MemoryType.CONVERSATION,
    max_size=100,
    ttl=3600
)

# 创建记忆实例
memory = ConversationMemory(config)

# 添加记忆
memory.add({"role": "user", "content": "Hello"})

# 获取记忆
history = memory.get_all()
```

### 5.3 Agent使用

```python
from src.ai.agents import AgentFactory
from src.ai.types import AgentConfig, AgentType, LLMConfig, LLMType

# 创建LLM配置
llm_config = LLMConfig(
    model_type=LLMType.LOCAL,
    model_name="test_model"
)

# 创建Agent配置
agent_config = AgentConfig(
    agent_type=AgentType.CONVERSATION,
    llm_config=llm_config
)

# 创建Agent
agent = AgentFactory.create(agent_config)

# 运行Agent
result = agent.run("What is PL5?")
```

### 5.4 工具使用

```python
from src.ai.tools import SearchTool

# 创建工具实例
search_tool = SearchTool()

# 运行工具
result = search_tool.run({"query": "PL5 prediction model"})
```

### 5.5 工作流使用

```python
from src.ai.orchestrator import WorkflowEngine, BuiltInWorkflows
import asyncio

# 创建工作流引擎
workflow_engine = WorkflowEngine()

# 获取内置工作流
workflow = BuiltInWorkflows.research_workflow()

# 运行工作流
async def run_workflow():
    result = await workflow_engine.run_workflow(workflow)
    print(result)

asyncio.run(run_workflow())
```

## 6. API参考

### 6.1 工具相关接口

- **GET /api/tools**：列出所有可用工具
- **POST /api/tools/{tool_name}/execute**：执行工具

### 6.2 Agent相关接口

- **POST /api/agents/create**：创建Agent
- **POST /api/agents/run**：运行Agent

### 6.3 工作流相关接口

- **POST /api/workflows/create**：创建工作流
- **POST /api/workflows/run**：运行工作流
- **GET /api/workflows/running**：列出运行中的工作流

### 6.4 记忆相关接口

- **POST /api/memory/create**：创建记忆
- **POST /api/memory/{memory_name}/add**：添加记忆项
- **GET /api/memory/{memory_name}/get**：获取记忆项

### 6.5 系统相关接口

- **GET /api/system/stats**：获取系统统计信息
- **GET /api/health**：健康检查

## 7. 配置指南

### 7.1 环境变量

- **OPENAI_API_KEY**：OpenAI API密钥
- **OPENAI_BASE_URL**：OpenAI API基础URL（可选）
- **HUGGINGFACE_TOKEN**：HuggingFace令牌（可选）

### 7.2 配置文件

系统支持通过配置文件设置默认参数，配置文件路径为 `config/ai_config.json`。

## 8. 部署指南

### 8.1 本地部署

```bash
# 安装依赖
pip install -r requirements.txt

# 启动API服务
python src/ai/api.py
```

### 8.2 容器部署

```bash
# 构建镜像
docker build -t pl5-ai-tool-system .

# 运行容器
docker run -p 8000:8000 pl5-ai-tool-system
```

## 9. 扩展指南

### 9.1 添加自定义模型

```python
from src.ai.models.base import BaseLLM, LLMFactory
from src.ai.types import LLMConfig, LLMType

class CustomLLM(BaseLLM):
    def generate(self, prompt, **kwargs):
        # 实现文本生成逻辑
        pass

# 注册到工厂
LLMFactory.register(LLMType.OTHER, CustomLLM)
```

### 9.2 添加自定义工具

```python
from src.ai.tools.base import BaseTool
from src.ai.registry import register_tool
from src.ai.types import ToolResult

class CustomTool(BaseTool):
    name = "custom_tool"
    description = "自定义工具"
    
    def run(self, parameters):
        # 实现工具逻辑
        return ToolResult(success=True, data={"result": "Success"})

# 注册工具
register_tool(name="custom_tool", description="自定义工具")(CustomTool)
```

### 9.3 添加自定义工作流

```python
from src.ai.orchestrator import Workflow, WorkflowStep

custom_workflow = Workflow(
    name="custom_workflow",
    description="自定义工作流",
    steps=[
        WorkflowStep(
            name="step1",
            tool_name="calculator",
            parameters={"expression": "1 + 1"}
        ),
        WorkflowStep(
            name="step2",
            tool_name="search",
            parameters={"query": "PL5"}
        )
    ]
)
```

## 10. 故障排除

### 10.1 常见问题

- **模型初始化失败**：检查模型路径或API密钥是否正确
- **工具执行失败**：检查工具参数是否正确，权限是否足够
- **API服务启动失败**：检查端口是否被占用，依赖是否安装
- **记忆系统错误**：检查存储路径权限，内存容量是否足够

### 10.2 日志系统

系统使用Python标准日志模块，日志配置在 `config/logging.conf`。

### 10.3 监控系统

系统提供了监控接口 `/api/system/stats`，可用于监控系统状态。

## 11. 版本历史

- **v1.0.0**：初始版本，实现了基本功能
- **v1.1.0**：添加了llama-cpp集成
- **v1.2.0**：完善了OpenAI API集成
- **v1.3.0**：添加了工作流编排功能
- **v1.4.0**：完善了安全系统

## 12. 贡献指南

欢迎贡献代码、报告问题或提出建议。请遵循以下步骤：

1. Fork仓库
2. 创建分支
3. 提交更改
4. 提交Pull Request

## 13. 许可证

本项目采用MIT许可证。
