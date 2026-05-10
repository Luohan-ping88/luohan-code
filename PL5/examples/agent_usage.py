"""Agent使用示例

展示如何使用AI Agent来执行复杂任务。
"""

from src.ai.agents.base import AgentFactory
from src.ai.types import AgentConfig, LLMConfig, LLMType, AgentType
from src.ai.registry import get_registry, register_tool
from src.ai.tools.builtin import SearchTool, CalculatorTool, FileTool
from src.ai.types import ToolParameter


# 注册内置工具
def register_builtin_tools():
    """注册内置工具"""
    # 注册搜索工具
    @register_tool(
        name="search",
        description="在互联网上搜索信息",
        parameters=[
            ToolParameter(
                name="query",
                type="str",
                description="搜索查询词",
                required=True
            ),
            ToolParameter(
                name="max_results",
                type="int",
                description="最大结果数量",
                required=False,
                default=5
            )
        ]
    )
    def search_tool(params):
        tool = SearchTool()
        return tool.execute(params)
    
    # 注册计算器工具
    @register_tool(
        name="calculator",
        description="执行数学计算",
        parameters=[
            ToolParameter(
                name="expression",
                type="str",
                description="数学表达式",
                required=True
            )
        ]
    )
    def calculator_tool(params):
        tool = CalculatorTool()
        return tool.execute(params)
    
    # 注册文件工具
    @register_tool(
        name="file",
        description="文件操作工具",
        parameters=[
            ToolParameter(
                name="action",
                type="str",
                description="操作类型: read, write, list",
                required=True
            ),
            ToolParameter(
                name="path",
                type="str",
                description="文件路径",
                required=True
            ),
            ToolParameter(
                name="content",
                type="str",
                description="文件内容（仅write操作需要）",
                required=False
            ),
            ToolParameter(
                name="max_lines",
                type="int",
                description="最大读取行数（仅read操作需要）",
                required=False,
                default=100
            )
        ]
    )
    def file_tool(params):
        tool = FileTool()
        return tool.execute(params)


# 示例1：使用ReAct Agent
def example_react_agent():
    """使用ReAct Agent"""
    print("=== 示例1: 使用ReAct Agent ===")
    
    # 构建LLM配置
    llm_config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=1000
    )
    
    # 构建Agent配置
    agent_config = AgentConfig(
        agent_type=AgentType.REACT,
        llm_config=llm_config,
        max_steps=10,
        max_retries=3
    )
    
    # 创建Agent
    agent = AgentFactory.create(agent_config)
    
    # 执行任务
    task = "计算123 + 456，然后搜索相关的数学运算信息"
    result = agent.run(task)
    
    print(f"任务: {task}")
    print(f"执行成功: {result.success}")
    print(f"结果: {result.data['answer'] if 'answer' in result.data else result.data['result']}")
    print(f"执行步骤: {len(result.data['steps'])}")
    print()


# 示例2：使用ToolCalling Agent
def example_tool_calling_agent():
    """使用ToolCalling Agent"""
    print("=== 示例2: 使用ToolCalling Agent ===")
    
    # 构建LLM配置
    llm_config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=1000
    )
    
    # 构建Agent配置
    agent_config = AgentConfig(
        agent_type=AgentType.TOOL_CALLING,
        llm_config=llm_config,
        max_steps=10,
        max_retries=3
    )
    
    # 创建Agent
    agent = AgentFactory.create(agent_config)
    
    # 执行任务
    task = "计算234 * 567，然后创建一个文件保存结果"
    result = agent.run(task)
    
    print(f"任务: {task}")
    print(f"执行成功: {result.success}")
    print(f"结果: {result.data['answer']}")
    print(f"执行步骤: {len(result.data['steps'])}")
    print()


# 示例3：使用Agent进行对话
def example_agent_chat():
    """使用Agent进行对话"""
    print("=== 示例3: 使用Agent进行对话 ===")
    
    # 构建LLM配置
    llm_config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=1000
    )
    
    # 构建Agent配置
    agent_config = AgentConfig(
        agent_type=AgentType.REACT,
        llm_config=llm_config,
        max_steps=10,
        max_retries=3
    )
    
    # 创建Agent
    agent = AgentFactory.create(agent_config)
    
    # 对话历史
    messages = [
        {"role": "user", "content": "你好，我想了解一下AI工具系统"},
        {"role": "assistant", "content": "你好！我是一个AI助手，可以帮助你了解AI工具系统。请问你有什么具体的问题吗？"},
        {"role": "user", "content": "请计算123 + 456，然后告诉我结果"}
    ]
    
    # 执行对话
    result = agent.chat(messages)
    
    print(f"对话执行成功: {result.success}")
    print(f"回答: {result.data['answer'] if 'answer' in result.data else result.data['result']}")
    print()


# 示例4：查看Agent可用工具
def example_agent_tools():
    """查看Agent可用工具"""
    print("=== 示例4: 查看Agent可用工具 ===")
    
    # 构建LLM配置
    llm_config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="gpt-3.5-turbo"
    )
    
    # 构建Agent配置
    agent_config = AgentConfig(
        agent_type=AgentType.REACT,
        llm_config=llm_config
    )
    
    # 创建Agent
    agent = AgentFactory.create(agent_config)
    
    # 获取可用工具
    tools = agent.get_available_tools()
    print(f"Agent可用工具数量: {len(tools)}")
    print("可用工具:")
    for tool_name in tools:
        tool_info = agent.get_tool_info(tool_name)
        if tool_info:
            print(f"  - {tool_name}: {tool_info['description']}")
    print()


if __name__ == "__main__":
    # 注册内置工具
    register_builtin_tools()
    
    # 运行示例
    example_react_agent()
    example_tool_calling_agent()
    example_agent_chat()
    example_agent_tools()
    
    print("Agent使用示例完成！")
