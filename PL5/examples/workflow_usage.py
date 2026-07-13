"""工作流使用示例

展示如何使用工作流编排引擎来执行复杂的任务流程。
"""

import asyncio
from src.ai.orchestrator import WorkflowEngine, Workflow, BuiltInWorkflows
from src.ai.registry import get_registry, register_tool
from src.ai.tools.builtin import SearchTool, CalculatorTool, FileTool
from src.ai.types import ToolParameter, WorkflowStep


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


# 示例1：创建并运行自定义工作流
async def example_custom_workflow():
    """创建并运行自定义工作流"""
    print("=== 示例1: 创建并运行自定义工作流 ===")
    
    # 创建工作流引擎
    engine = WorkflowEngine()
    
    # 创建工作流
    workflow = Workflow(
        name="数据处理工作流",
        description="处理数据并生成报告",
        steps=[
            WorkflowStep(
                name="计算1",
                tool_name="calculator",
                parameters={"expression": "1 + 1"}
            ),
            WorkflowStep(
                name="计算2",
                tool_name="calculator",
                parameters={"expression": "2 + 2"}
            ),
            WorkflowStep(
                name="计算3",
                tool_name="calculator",
                parameters={"expression": "3 + 3"}
            ),
            WorkflowStep(
                name="汇总",
                tool_name="calculator",
                parameters={"expression": "$计算1 + $计算2 + $计算3"}
            ),
            WorkflowStep(
                name="保存结果",
                tool_name="file",
                parameters={
                    "action": "write",
                    "path": "workflow_result.txt",
                    "content": "计算结果: $汇总"
                }
            )
        ],
        variables={}
    )
    
    # 运行工作流
    result = await engine.run_workflow(workflow)
    
    print(f"工作流执行成功: {result['status'] == 'success'}")
    print(f"执行ID: {result['execution_id']}")
    print(f"结果: {result['results']}")
    print()


# 示例2：使用内置工作流模板
async def example_builtin_workflows():
    """使用内置工作流模板"""
    print("=== 示例2: 使用内置工作流模板 ===")
    
    # 创建工作流引擎
    engine = WorkflowEngine()
    
    # 使用研究工作流
    research_workflow = BuiltInWorkflows.research_workflow()
    research_workflow.variables = {
        "query": "AI大模型工具系统",
        "analysis_expression": "1 + 1",
        "report_file": "research_report.txt"
    }
    
    # 运行工作流
    result = await engine.run_workflow(research_workflow)
    
    print(f"研究工作流执行成功: {result['status'] == 'success'}")
    print(f"执行ID: {result['execution_id']}")
    print()


# 示例3：并行工作流
async def example_parallel_workflow():
    """并行工作流"""
    print("=== 示例3: 并行工作流 ===")
    
    # 创建工作流引擎
    engine = WorkflowEngine()
    
    # 创建并行工作流
    workflow = Workflow(
        name="并行计算工作流",
        description="并行执行多个计算任务",
        steps=[
            WorkflowStep(
                name="计算A",
                tool_name="calculator",
                parameters={"expression": "100 + 200"},
                parallel_group="group1"
            ),
            WorkflowStep(
                name="计算B",
                tool_name="calculator",
                parameters={"expression": "300 + 400"},
                parallel_group="group1"
            ),
            WorkflowStep(
                name="计算C",
                tool_name="calculator",
                parameters={"expression": "500 + 600"},
                parallel_group="group1"
            ),
            WorkflowStep(
                name="总计算",
                tool_name="calculator",
                parameters={"expression": "$计算A + $计算B + $计算C"}
            )
        ]
    )
    
    # 运行工作流
    result = await engine.run_workflow(workflow)
    
    print(f"并行工作流执行成功: {result['status'] == 'success'}")
    print(f"执行ID: {result['execution_id']}")
    print(f"并行组结果: {result['results']['group1']}")
    print(f"总计算结果: {result['results']['总计算']}")
    print()


# 示例4：工作流状态查询
async def example_workflow_status():
    """工作流状态查询"""
    print("=== 示例4: 工作流状态查询 ===")
    
    # 创建工作流引擎
    engine = WorkflowEngine()
    
    # 创建工作流
    workflow = Workflow(
        name="状态查询工作流",
        description="测试工作流状态查询",
        steps=[
            WorkflowStep(
                name="计算",
                tool_name="calculator",
                parameters={"expression": "1 + 1"}
            )
        ]
    )
    
    # 获取执行ID
    execution_id = workflow.execution_id
    print(f"工作流执行ID: {execution_id}")
    
    # 运行工作流
    result = await engine.run_workflow(workflow)
    
    # 列出运行中的工作流
    running_workflows = engine.list_running_workflows()
    print(f"运行中的工作流数量: {len(running_workflows)}")
    print()


if __name__ == "__main__":
    # 注册内置工具
    register_builtin_tools()
    
    # 运行示例
    asyncio.run(example_custom_workflow())
    asyncio.run(example_builtin_workflows())
    asyncio.run(example_parallel_workflow())
    asyncio.run(example_workflow_status())
    
    print("工作流使用示例完成！")
