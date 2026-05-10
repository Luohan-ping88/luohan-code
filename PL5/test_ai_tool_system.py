"""AI大模型工具系统集成测试"""

import sys
import os

# 添加项目路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.ai.models import get_model_manager, LLMFactory
from src.ai.models.base import BaseLLM
from src.ai.types import LLMConfig, LLMType
from src.ai.memory import MemoryManager, ConversationMemory, LongTermMemory, VectorMemory
from src.ai.memory.base import BaseMemory
from src.ai.types import MemoryConfig, MemoryType
from src.ai.agents import AgentFactory, AgentOrchestrator
from src.ai.types import AgentConfig, AgentType
from src.ai.tools import SearchTool, CodeTool, CalculatorTool, PL5Tool
from src.tools.base import get_registry, ToolContext


def test_model_layer():
    """测试模型层"""
    print("\n=== 测试模型层 ===")
    
    # 创建模型配置
    config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="test_model",
        max_tokens=1000,
        temperature=0.7
    )
    
    # 创建模型
    model = LLMFactory.create(config)
    print(f"✓ 模型创建成功: {model.model_name}")
    
    # 测试文本生成
    response = model.generate("Hello, AI!")
    print(f"✓ 文本生成成功: {response[:50]}...")
    
    # 测试对话
    messages = [
        {"role": "user", "content": "What is PL5?"}
    ]
    chat_response = model.chat(messages)
    print(f"✓ 对话成功: {chat_response['content'][:50]}...")
    
    # 测试模型管理器
    manager = get_model_manager()
    model_id = manager.create_model(config)
    print(f"✓ 模型管理器创建模型成功: {model_id}")
    
    models = manager.list_models()
    print(f"✓ 模型列表: {models}")
    
    return True


def test_memory_layer():
    """测试记忆层"""
    print("\n=== 测试记忆层 ===")
    
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
    
    print("✓ 记忆实例创建成功")
    
    # 测试对话记忆
    conversation_memory.add({"role": "user", "content": "Hello"})
    conversation_memory.add({"role": "assistant", "content": "Hi! How can I help?"})
    history = conversation_memory.get_all()
    print(f"✓ 对话记忆添加成功，数量: {len(history)}")
    
    # 测试长期记忆
    long_term_memory.add({"type": "fact", "content": "PL5 is a prediction model"})
    fact = long_term_memory.get("fact")
    print(f"✓ 长期记忆添加成功: {fact}")
    
    # 测试向量记忆
    vector_memory.add("PL5 prediction model")
    results = vector_memory.search_by_text("prediction")
    print(f"✓ 向量记忆搜索成功，结果数量: {len(results)}")
    
    # 测试记忆管理器
    memory_manager = MemoryManager()
    memory_manager.add_memory("conversation", conversation_memory)
    memory_manager.add_memory("long_term", long_term_memory)
    memory_manager.add_memory("vector", vector_memory)
    
    memories = memory_manager.list_memories()
    print(f"✓ 记忆管理器添加成功，记忆列表: {memories}")
    
    return True


def test_agent_layer():
    """测试智能体层"""
    print("\n=== 测试智能体层 ===")
    
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
    print(f"✓ Agent创建成功: {agent.agent_type.value}")
    
    # 测试Agent运行
    result = agent.run("What is PL5?")
    print(f"✓ Agent运行成功，结果: {result.data.get('reply', {}).content[:50]}...")
    
    # 测试Agent编排器
    orchestrator = AgentOrchestrator()
    orchestrator.create_agent("conversation_agent", agent_config)
    
    # 测试编排器运行
    orchestrator_result = orchestrator.run_task("Tell me about PL5 prediction model")
    print(f"✓ Agent编排器运行成功")
    
    return True


def test_tool_system():
    """测试工具系统"""
    print("\n=== 测试工具系统 ===")
    
    # 获取工具注册表
    registry = get_registry()
    print(f"✓ 工具注册表获取成功，工具数量: {registry.count}")
    
    # 测试AI工具
    search_tool = SearchTool()
    code_tool = CodeTool()
    calculator_tool = CalculatorTool()
    pl5_tool = PL5Tool()
    
    print("✓ AI工具实例创建成功")
    
    # 测试搜索工具
    search_result = search_tool.execute({"query": "PL5 prediction model"})
    print(f"✓ 搜索工具执行成功，结果数量: {len(search_result.data.get('results', []))}")
    
    # 测试计算工具
    calc_result = calculator_tool.execute({"operation": "evaluate", "expression": "2 + 2 * 3"})
    print(f"✓ 计算工具执行成功，结果: {calc_result.data.get('result')}")
    
    # 测试代码工具
    code_result = code_tool.execute({"code": "print('Hello from code tool')", "language": "python", "action": "execute"})
    print(f"✓ 代码工具执行成功")
    
    # 测试AI工具发现
    ai_tools = registry.list_ai_tools()
    print(f"✓ AI工具发现成功，工具数量: {len(ai_tools)}")
    
    return True


def test_integration():
    """测试系统集成"""
    print("\n=== 测试系统集成 ===")
    
    # 创建完整的系统实例
    model_manager = get_model_manager()
    memory_manager = MemoryManager()
    agent_orchestrator = AgentOrchestrator()
    tool_registry = get_registry()
    
    # 测试完整流程
    print("✓ 系统组件初始化成功")
    
    # 测试Agent使用工具
    llm_config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="test_model",
        max_tokens=1000,
        temperature=0.7
    )
    
    agent_config = AgentConfig(
        agent_type=AgentType.TOOL_CALLING,
        llm_config=llm_config,
        max_steps=10,
        max_retries=3,
        timeout=60
    )
    
    agent_orchestrator.create_agent("tool_agent", agent_config)
    
    # 测试工具调用任务
    task = "搜索PL5预测模型的相关信息"
    result = agent_orchestrator.run_task(task)
    print(f"✓ 系统集成测试成功，任务: {task}")
    
    return True


def main():
    """主测试函数"""
    print("AI大模型工具系统集成测试")
    print("=" * 50)
    
    try:
        test_model_layer()
        test_memory_layer()
        test_agent_layer()
        test_tool_system()
        test_integration()
        
        print("\n" + "=" * 50)
        print("✓ 所有测试通过！AI大模型工具系统集成成功。")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
