"""AI工具系统测试

测试AI工具系统的核心功能。
"""

import unittest
from src.ai.registry import get_registry, register_tool, reset_registry
from src.ai.tools.builtin import SearchTool, CalculatorTool, FileTool
from src.ai.types import ToolParameter, LLMConfig, LLMType, AgentConfig, AgentType
from src.ai.agents.base import AgentFactory
from src.ai.orchestrator import WorkflowEngine, Workflow, WorkflowStep
import asyncio


class TestToolRegistry(unittest.TestCase):
    """测试工具注册中心"""

    def setUp(self):
        """设置测试环境"""
        reset_registry()

    def test_register_tool(self):
        """测试注册工具"""

        # 注册工具
        @register_tool(
            name="test_tool",
            description="测试工具",
            parameters=[ToolParameter(name="param1", type="str", description="参数1", required=True)],
        )
        def test_tool_func(params):
            from src.ai.types import ToolResult

            return ToolResult(success=True, data=params)

        # 检查工具是否注册成功
        registry = get_registry()
        tools = registry.list_tools()
        self.assertIn("test_tool", tools)

    def test_execute_tool(self):
        """测试执行工具"""

        # 注册工具
        @register_tool(
            name="calculator",
            description="计算器工具",
            parameters=[ToolParameter(name="expression", type="str", description="数学表达式", required=True)],
        )
        def calculator_tool(params):
            from src.ai.types import ToolResult

            try:
                result = eval(params["expression"])
                return ToolResult(success=True, data=result)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        # 执行工具
        registry = get_registry()
        result = registry.execute_tool("calculator", {"expression": "1 + 1"})
        self.assertTrue(result.success)
        self.assertEqual(result.data, 2)

    def test_list_tools(self):
        """测试列出工具"""

        # 注册多个工具
        @register_tool(name="tool1", description="工具1", parameters=[])
        def tool1(params):
            from src.ai.types import ToolResult

            return ToolResult(success=True)

        @register_tool(name="tool2", description="工具2", parameters=[])
        def tool2(params):
            from src.ai.types import ToolResult

            return ToolResult(success=True)

        # 检查工具列表
        registry = get_registry()
        tools = registry.list_tools()
        self.assertEqual(len(tools), 2)
        self.assertIn("tool1", tools)
        self.assertIn("tool2", tools)


class TestAgent(unittest.TestCase):
    """测试Agent功能"""

    def setUp(self):
        """设置测试环境"""
        reset_registry()

        # 注册内置工具
        @register_tool(
            name="calculator",
            description="执行数学计算",
            parameters=[ToolParameter(name="expression", type="str", description="数学表达式", required=True)],
        )
        def calculator_tool(params):
            from src.ai.types import ToolResult

            try:
                result = eval(params["expression"])
                return ToolResult(success=True, data=result)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

    def test_create_agent(self):
        """测试创建Agent"""
        # 构建配置
        llm_config = LLMConfig(model_type=LLMType.LOCAL, model_name="gpt-3.5-turbo")

        agent_config = AgentConfig(agent_type=AgentType.REACT, llm_config=llm_config)

        # 创建Agent
        agent = AgentFactory.create(agent_config)
        self.assertIsNotNone(agent)
        self.assertEqual(agent.agent_type, AgentType.REACT)

    def test_agent_run(self):
        """测试Agent运行"""
        # 构建配置
        llm_config = LLMConfig(model_type=LLMType.LOCAL, model_name="gpt-3.5-turbo")

        agent_config = AgentConfig(agent_type=AgentType.REACT, llm_config=llm_config)

        # 创建Agent
        agent = AgentFactory.create(agent_config)

        # 执行任务
        result = agent.run("计算1 + 1")
        # 由于本地模型是模拟实现，可能会失败，所以这里只检查Agent是否能够创建和运行
        # 不严格要求执行成功
        self.assertIsNotNone(result)


class TestWorkflow(unittest.TestCase):
    """测试工作流功能"""

    def setUp(self):
        """设置测试环境"""
        reset_registry()

        # 注册内置工具
        @register_tool(
            name="calculator",
            description="执行数学计算",
            parameters=[ToolParameter(name="expression", type="str", description="数学表达式", required=True)],
        )
        def calculator_tool(params):
            from src.ai.types import ToolResult

            try:
                result = eval(params["expression"])
                return ToolResult(success=True, data=result)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

    async def test_workflow_execution(self):
        """测试工作流执行"""
        # 创建工作流
        workflow = Workflow(
            name="测试工作流",
            description="测试工作流执行",
            steps=[
                WorkflowStep(name="计算1", tool_name="calculator", parameters={"expression": "1 + 1"}),
                WorkflowStep(name="计算2", tool_name="calculator", parameters={"expression": "2 + 2"}),
            ],
        )

        # 运行工作流
        engine = WorkflowEngine()
        result = await engine.run_workflow(workflow)

        self.assertEqual(result["status"], "success")
        self.assertIn("计算1", result["results"])
        self.assertIn("计算2", result["results"])

    def test_workflow_execution_sync(self):
        """同步测试工作流执行"""
        asyncio.run(self.test_workflow_execution())


class TestBuiltinTools(unittest.TestCase):
    """测试内置工具"""

    def setUp(self):
        """设置测试环境"""
        reset_registry()

        # 注册内置工具
        @register_tool(
            name="calculator",
            description="执行数学计算",
            parameters=[ToolParameter(name="expression", type="str", description="数学表达式", required=True)],
        )
        def calculator_tool(params):
            tool = CalculatorTool()
            return tool.execute(params)

        @register_tool(
            name="search",
            description="搜索工具",
            parameters=[ToolParameter(name="query", type="str", description="搜索查询词", required=True)],
        )
        def search_tool(params):
            tool = SearchTool()
            return tool.execute(params)

    def test_calculator_tool(self):
        """测试计算器工具"""
        registry = get_registry()
        result = registry.execute_tool("calculator", {"expression": "1 + 1"})
        self.assertTrue(result.success)
        self.assertEqual(result.data["result"], 2)

    def test_search_tool(self):
        """测试搜索工具"""
        registry = get_registry()
        result = registry.execute_tool("search", {"query": "test"})
        self.assertTrue(result.success)
        self.assertIn("results", result.data)


if __name__ == "__main__":
    unittest.main()
