#!/usr/bin/env python3
"""
AI大模型工具系统使用示例

这个文件展示了如何使用AI大模型工具系统的核心功能，包括：
1. 模型管理
2. 记忆系统
3. Agent系统
4. 工具系统
5. 工作流编排
"""

import sys
import os

# 添加项目路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ai.models import get_model_manager, LLMFactory
from src.ai.types import LLMConfig, LLMType
from src.ai.memory import MemoryManager, ConversationMemory, LongTermMemory, VectorMemory
from src.ai.types import MemoryConfig, MemoryType
from src.ai.agents import AgentFactory, AgentOrchestrator
from src.ai.types import AgentConfig, AgentType
from src.ai.tools import SearchTool, CodeTool, CalculatorTool, PL5ToolAdapter
from src.ai.registry import get_registry
from src.ai.orchestrator import WorkflowEngine, Workflow, BuiltInWorkflows


def example_model_usage():
    """模型使用示例"""
    print("\n=== 模型使用示例 ===")
    
    # 创建模型配置
    config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="test_model",
        max_tokens=1000,
        temperature=0.7
    )
    
    # 创建模型
    model = LLMFactory.create(config)
    print(f"模型创建成功: {model.model_name}")
    
    # 测试文本生成
    response = model.generate("Hello, AI! Tell me about PL5 prediction model")
    print(f"文本生成结果: {response[:100]}...")
    
    # 测试对话
    messages = [
        {"role": "user", "content": "What is PL5?"},
        {"role": "assistant", "content": "PL5 is a prediction model for permutation five lottery."},
        {"role": "user", "content": "How does it work?"}
    ]
    chat_response = model.chat(messages)
    print(f"对话结果: {chat_response['content'][:100]}...")


def example_memory_usage():
    """记忆系统使用示例"""
    print("\n=== 记忆系统使用示例 ===")
    
    # 创建记忆配置
    conversation_config = MemoryConfig(
        memory_type=MemoryType.CONVERSATION,
        max_size=100,
        ttl=3600,
        embedding_dim=128
    )
    
    long_term_config = MemoryConfig(
        memory_type=MemoryType.LONG_TERM,
        max_size=1000,
        ttl=86400,
        embedding_dim=128
    )
    
    vector_config = MemoryConfig(
        memory_type=MemoryType.VECTOR,
        max_size=500,
        ttl=3600,
        embedding_dim=128
    )
    
    # 创建记忆实例
    conversation_memory = ConversationMemory(conversation_config)
    long_term_memory = LongTermMemory(long_term_config)
    vector_memory = VectorMemory(vector_config)
    
    # 添加对话记忆
    conversation_memory.add({"role": "user", "content": "Hello"})
    conversation_memory.add({"role": "assistant", "content": "Hi! How can I help?"})
    history = conversation_memory.get_all()
    print(f"对话记忆数量: {len(history)}")
    
    # 添加长期记忆
    long_term_memory.add({"type": "fact", "content": "PL5 is a prediction model for permutation five lottery."})
    fact = long_term_memory.get("fact")
    print(f"长期记忆: {fact}")
    
    # 添加向量记忆
    vector_memory.add("PL5 prediction model")
    vector_memory.add("Lottery prediction")
    vector_memory.add("Machine learning")
    results = vector_memory.search_by_text("prediction")
    print(f"向量记忆搜索结果数量: {len(results)}")


def example_agent_usage():
    """Agent系统使用示例"""
    print("\n=== Agent系统使用示例 ===")
    
    # 创建LLM配置
    llm_config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="test_model",
        max_tokens=1000,
        temperature=0.7
    )
    
    # 创建Agent配置
    agent_config = AgentConfig(
        agent_type=AgentType.CONVERSATION,
        llm_config=llm_config,
        max_steps=10,
        max_retries=3,
        timeout=60
    )
    
    # 创建Agent
    agent = AgentFactory.create(agent_config)
    print(f"Agent创建成功: {agent.agent_type.value}")
    
    # 测试Agent运行
    result = agent.run("What is PL5 and how does it work?")
    print(f"Agent运行结果: {result.data.get('reply', {}).content[:100]}...")
    
    # 测试Agent编排器
    orchestrator = AgentOrchestrator()
    orchestrator.create_agent("conversation_agent", agent_config)
    
    # 测试编排器运行
    orchestrator_result = orchestrator.run_task("Tell me about PL5 prediction model and how to use it")
    print(f"Agent编排器运行成功")


def example_tool_usage():
    """工具系统使用示例"""
    print("\n=== 工具系统使用示例 ===")
    
    # 获取工具注册表
    registry = get_registry()
    print(f"工具数量: {registry.count}")
    
    # 创建工具实例
    search_tool = SearchTool()
    code_tool = CodeTool()
    calculator_tool = CalculatorTool()
    
    # 测试搜索工具
    search_result = search_tool.run({"query": "PL5 prediction model", "max_results": 3})
    print(f"搜索结果数量: {len(search_result.data.get('results', []))}")
    
    # 测试计算工具
    calc_result = calculator_tool.run({"operation": "evaluate", "expression": "2 + 2 * 3"})
    print(f"计算结果: {calc_result.data.get('result')}")
    
    # 测试代码工具
    code_result = code_tool.run({"code": "print('Hello from code tool')", "language": "python", "action": "execute"})
    print(f"代码执行成功: {code_result.success}")


def example_workflow_usage():
    """工作流编排示例"""
    print("\n=== 工作流编排示例 ===")
    
    # 创建工作流引擎
    workflow_engine = WorkflowEngine()
    
    # 使用内置工作流模板
    research_workflow = BuiltInWorkflows.research_workflow()
    print(f"工作流名称: {research_workflow.name}")
    print(f"工作流步骤数量: {len(research_workflow.steps)}")
    
    # 运行工作流
    import asyncio
    async def run_workflow():
        result = await workflow_engine.run_workflow(research_workflow)
        print(f"工作流执行状态: {result['status']}")
    
    asyncio.run(run_workflow())


def main():
    """主函数"""
    print("AI大模型工具系统使用示例")
    print("=" * 60)
    
    try:
        example_model_usage()
        example_memory_usage()
        example_agent_usage()
        example_tool_usage()
        example_workflow_usage()
        
        print("\n" + "=" * 60)
        print("示例执行完成！")
    except Exception as e:
        print(f"示例执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
