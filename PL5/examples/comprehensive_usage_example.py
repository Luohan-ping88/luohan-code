#!/usr/bin/env python3
"""
AI大模型工具系统综合使用示例

这个文件展示了如何综合使用AI大模型工具系统的核心功能，包括：
1. 模型管理和使用
2. 记忆系统的综合应用
3. Agent系统的高级使用
4. 工具系统的实际应用
5. 工作流编排的复杂场景
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
from src.ai.tools import SearchTool, CodeTool, CalculatorTool, PL5Tool
from src.ai.registry import get_registry
from src.ai.orchestrator import WorkflowEngine, Workflow, WorkflowStep


def example_comprehensive_workflow():
    """综合工作流示例"""
    print("\n=== 综合工作流示例 ===")
    print("这个示例展示了如何创建一个完整的AI工作流，包括：")
    print("1. 初始化模型和记忆系统")
    print("2. 创建和配置Agent")
    print("3. 使用工具执行任务")
    print("4. 编排复杂工作流")
    
    # 1. 初始化模型
    print("\n1. 初始化模型...")
    llm_config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="test_model",
        max_tokens=1000,
        temperature=0.7
    )
    model = LLMFactory.create(llm_config)
    print(f"模型创建成功: {model.model_name}")
    
    # 2. 初始化记忆系统
    print("\n2. 初始化记忆系统...")
    conversation_memory = ConversationMemory(MemoryConfig(
        memory_type=MemoryType.CONVERSATION,
        max_size=100,
        ttl=3600,
        embedding_dim=128
    ))
    
    long_term_memory = LongTermMemory(MemoryConfig(
        memory_type=MemoryType.LONG_TERM,
        max_size=1000,
        ttl=86400,
        embedding_dim=128
    ))
    
    vector_memory = VectorMemory(MemoryConfig(
        memory_type=MemoryType.VECTOR,
        max_size=500,
        ttl=3600,
        embedding_dim=128
    ))
    
    # 添加一些初始记忆
    long_term_memory.add({"type": "fact", "content": "PL5是一个排列五彩票预测模型"})
    vector_memory.add("PL5 prediction model")
    vector_memory.add("Lottery prediction using machine learning")
    
    print("记忆系统初始化完成")
    
    # 3. 创建Agent
    print("\n3. 创建Agent...")
    agent_config = AgentConfig(
        agent_type=AgentType.REACT,
        llm_config=llm_config,
        max_steps=20,
        max_retries=3,
        timeout=120
    )
    agent = AgentFactory.create(agent_config)
    print(f"Agent创建成功: {agent.agent_type.value}")
    
    # 4. 测试工具使用
    print("\n4. 测试工具使用...")
    calculator_tool = CalculatorTool()
    search_tool = SearchTool()
    code_tool = CodeTool()
    
    # 测试计算器工具
    calc_result = calculator_tool.run({"operation": "evaluate", "expression": "100 * 2 + 50"})
    print(f"计算结果: {calc_result.data.get('result')}")
    
    # 测试搜索工具
    search_result = search_tool.run({"query": "PL5彩票预测模型", "max_results": 2})
    print(f"搜索结果数量: {len(search_result.data.get('results', []))}")
    
    # 5. 创建复杂工作流
    print("\n5. 创建复杂工作流...")
    workflow_steps = [
        WorkflowStep(
            name="calculate_step",
            tool_name="calculator",
            parameters={"operation": "evaluate", "expression": "100 * 5"}
        ),
        WorkflowStep(
            name="search_step",
            tool_name="search",
            parameters={"query": "PL5彩票预测", "max_results": 3},
            condition_expr="{{calculate_step.output}} > 400"
        ),
        WorkflowStep(
            name="code_step",
            tool_name="code",
            parameters={"code": "print('Workflow completed successfully!')", "language": "python", "action": "execute"},
            condition_expr="{{search_step.output.results.length}} > 0"
        )
    ]
    
    workflow = Workflow(
        name="comprehensive_workflow",
        description="综合工作流示例",
        steps=workflow_steps
    )
    
    # 6. 运行工作流
    print("\n6. 运行工作流...")
    workflow_engine = WorkflowEngine()
    
    import asyncio
    async def run_workflow():
        result = await workflow_engine.run_workflow(workflow)
        print(f"工作流执行状态: {result['status']}")
        if result['status'] == 'success':
            print("工作流执行成功！")
            for step_name, step_result in result['results'].items():
                print(f"  - {step_name}: {step_result['data']}")
        else:
            print(f"工作流执行失败: {result['error']}")
    
    asyncio.run(run_workflow())
    
    # 7. 测试Agent执行复杂任务
    print("\n7. 测试Agent执行复杂任务...")
    task = "计算123 * 456，然后搜索PL5彩票预测相关信息，最后生成一个简单的总结"
    result = agent.run(task)
    print(f"Agent任务执行状态: {result.success}")
    if result.success:
        print(f"Agent执行结果: {result.data.get('result', '')[:150]}...")
    else:
        print(f"Agent执行失败: {result.error}")


def example_memory_integration():
    """记忆系统集成示例"""
    print("\n=== 记忆系统集成示例 ===")
    print("这个示例展示了如何集成使用三种记忆系统：")
    print("1. 对话记忆 - 存储对话历史")
    print("2. 长期记忆 - 存储事实和知识")
    print("3. 向量记忆 - 存储和搜索语义信息")
    
    # 初始化三种记忆
    conversation_memory = ConversationMemory(MemoryConfig(
        memory_type=MemoryType.CONVERSATION,
        max_size=50,
        ttl=3600,
        embedding_dim=128
    ))
    
    long_term_memory = LongTermMemory(MemoryConfig(
        memory_type=MemoryType.LONG_TERM,
        max_size=500,
        ttl=86400,
        embedding_dim=128
    ))
    
    vector_memory = VectorMemory(MemoryConfig(
        memory_type=MemoryType.VECTOR,
        max_size=300,
        ttl=3600,
        embedding_dim=128
    ))
    
    # 添加对话记忆
    conversation_memory.add({"role": "user", "content": "什么是PL5？"})
    conversation_memory.add({"role": "assistant", "content": "PL5是一个排列五彩票预测模型，使用机器学习算法进行预测。"})
    conversation_memory.add({"role": "user", "content": "它是如何工作的？"})
    
    # 添加长期记忆
    long_term_memory.add({"type": "fact", "content": "PL5模型使用历史数据进行训练"})
    long_term_memory.add({"type": "fact", "content": "PL5模型支持多种预测算法"})
    long_term_memory.add({"type": "fact", "content": "PL5模型可以生成预测报告"})
    
    # 添加向量记忆
    vector_memory.add("PL5 prediction model")
    vector_memory.add("Machine learning for lottery prediction")
    vector_memory.add("Pattern recognition in lottery numbers")
    vector_memory.add("Statistical analysis of lottery data")
    
    # 测试记忆检索
    print("\n测试记忆检索:")
    
    # 获取对话历史
    conversation_history = conversation_memory.get_all()
    print(f"对话历史条数: {len(conversation_history)}")
    if conversation_history:
        print(f"最后一条对话: {conversation_history[-1]['content']}")
    else:
        print("对话历史为空")
    
    # 获取长期记忆
    facts = long_term_memory.get("fact")
    if facts:
        print(f"长期记忆事实条数: {len(facts)}")
        print(f"第一条事实: {facts[0]['content']}")
    else:
        print("长期记忆为空")
    
    # 搜索向量记忆
    search_results = vector_memory.search_by_text("lottery prediction")
    print(f"向量记忆搜索结果条数: {len(search_results)}")
    for i, result in enumerate(search_results[:2]):
        # 检查 result 的类型
        if isinstance(result, tuple):
            # 如果是元组，假设第一个元素是文本
            print(f"  搜索结果 {i+1}: {result[0]}")
        elif isinstance(result, dict) and 'text' in result:
            # 如果是字典，使用 text 键
            print(f"  搜索结果 {i+1}: {result['text']}")
        else:
            # 其他情况，直接打印
            print(f"  搜索结果 {i+1}: {result}")


def example_agent_orchestration():
    """Agent编排示例"""
    print("\n=== Agent编排示例 ===")
    print("这个示例展示了如何使用Agent编排器管理多个Agent：")
    print("1. 创建不同类型的Agent")
    print("2. 为不同任务分配合适的Agent")
    print("3. 协调多个Agent完成复杂任务")
    
    # 创建Agent编排器
    orchestrator = AgentOrchestrator()
    
    # 创建对话Agent
    conversation_config = AgentConfig(
        agent_type=AgentType.CONVERSATION,
        llm_config=LLMConfig(
            model_type=LLMType.LOCAL,
            model_name="test_model",
            max_tokens=1000,
            temperature=0.7
        ),
        max_steps=10,
        max_retries=3,
        timeout=60
    )
    
    # 创建React Agent
    react_config = AgentConfig(
        agent_type=AgentType.REACT,
        llm_config=LLMConfig(
            model_type=LLMType.LOCAL,
            model_name="test_model",
            max_tokens=1000,
            temperature=0.7
        ),
        max_steps=20,
        max_retries=3,
        timeout=120
    )
    
    # 注册Agent
    orchestrator.create_agent("conversation_agent", conversation_config)
    orchestrator.create_agent("react_agent", react_config)
    
    print("Agent注册完成")
    
    # 测试对话任务
    print("\n测试对话任务:")
    conversation_result = orchestrator.run_task("什么是PL5模型？请简要介绍一下。")
    print(f"对话任务执行状态: {conversation_result.success}")
    if conversation_result.success:
        print(f"对话结果: {conversation_result.data.get('reply', {}).content[:100]}...")
    
    # 测试复杂任务
    print("\n测试复杂任务:")
    complex_task = "计算1234 * 5678，然后搜索PL5彩票预测的最新方法，最后总结结果"
    complex_result = orchestrator.run_task(complex_task)
    print(f"复杂任务执行状态: {complex_result.success}")
    if complex_result.success:
        print(f"复杂任务结果: {complex_result.data.get('result', '')[:150]}...")


def main():
    """主函数"""
    print("AI大模型工具系统综合使用示例")
    print("=" * 70)
    
    try:
        example_comprehensive_workflow()
        example_memory_integration()
        example_agent_orchestration()
        
        print("\n" + "=" * 70)
        print("综合示例执行完成！")
        print("这个示例展示了AI大模型工具系统的核心功能和使用方法。")
        print("你可以根据自己的需求，灵活组合这些功能来构建复杂的AI应用。")
    except Exception as e:
        print(f"示例执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
