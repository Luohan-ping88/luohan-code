"""测试工具系统"""

from src.ai.tools import tool_registry


def test_tool_registry():
    """测试工具注册表"""
    print("=== 测试工具注册表 ===")
    
    # 列出所有工具
    tools = tool_registry.list_tools()
    print(f"已注册的工具: {tools}")
    
    # 按分类列出工具
    from src.ai.types import ToolCategory
    for category in ToolCategory:
        category_tools = tool_registry.list_tools_by_category(category)
        print(f"{category.value} 分类的工具: {category_tools}")
    
    # 获取工具信息
    for tool_name in tools:
        tool_info = tool_registry.get_tool_info(tool_name)
        print(f"\n工具: {tool_name}")
        print(f"描述: {tool_info.description}")
        print(f"分类: {tool_info.category.value}")
        print(f"标签: {tool_info.tags}")
        print(f"参数: {[p.name for p in tool_info.parameters]}")


def test_search_tool():
    """测试搜索工具"""
    print("\n=== 测试搜索工具 ===")
    
    search_tool = tool_registry.get_tool_instance("search")
    
    # 测试网页搜索
    web_search_params = {
        "query": "PL5预测模型",
        "type": "web",
        "max_results": 3
    }
    result = search_tool.execute(web_search_params)
    print(f"网页搜索结果: {result}")
    
    # 测试文档搜索
    doc_search_params = {
        "query": "PL5预测模型",
        "type": "document",
        "max_results": 3
    }
    result = search_tool.execute(doc_search_params)
    print(f"文档搜索结果: {result}")


def test_code_tool():
    """测试代码工具"""
    print("\n=== 测试代码工具 ===")
    
    code_tool = tool_registry.get_tool_instance("code")
    
    # 测试执行Python代码
    python_code_params = {
        "code": "print('Hello, PL5!')\nprint('2 + 2 =', 2 + 2)",
        "language": "python",
        "action": "execute"
    }
    result = code_tool.execute(python_code_params)
    print(f"Python代码执行结果: {result}")
    
    # 测试代码生成
    code_gen_params = {
        "code": "生成一个计算斐波那契数列的函数",
        "language": "python",
        "action": "generate"
    }
    result = code_tool.execute(code_gen_params)
    print(f"代码生成结果: {result}")


def test_calculator_tool():
    """测试计算工具"""
    print("\n=== 测试计算工具 ===")
    
    calculator_tool = tool_registry.get_tool_instance("calculator")
    
    # 测试数学表达式计算
    eval_params = {
        "expression": "2 + 2 * 3",
        "operation": "evaluate"
    }
    result = calculator_tool.execute(eval_params)
    print(f"数学表达式计算结果: {result}")
    
    # 测试数据统计
    data = [1, 2, 3, 4, 5]
    sum_params = {
        "data": data,
        "operation": "sum"
    }
    result = calculator_tool.execute(sum_params)
    print(f"数据求和结果: {result}")
    
    mean_params = {
        "data": data,
        "operation": "mean"
    }
    result = calculator_tool.execute(mean_params)
    print(f"数据均值结果: {result}")


def test_pl5_tool():
    """测试PL5工具"""
    print("\n=== 测试PL5工具 ===")
    
    pl5_tool = tool_registry.get_tool_instance("pl5")
    
    # 测试预测功能
    predict_params = {
        "action": "predict",
        "model_name": "pl5-default",
        "input_data": {"features": [1.0, 2.0, 3.0]},
        "params": {"confidence_threshold": 0.8}
    }
    result = pl5_tool.execute(predict_params)
    print(f"PL5预测结果: {result}")
    
    # 测试分析功能
    analyze_params = {
        "action": "analyze",
        "model_name": "pl5-default",
        "input_data": {"features": [1.0, 2.0, 3.0]},
        "params": {"detailed": True}
    }
    result = pl5_tool.execute(analyze_params)
    print(f"PL5分析结果: {result}")


if __name__ == "__main__":
    test_tool_registry()
    test_search_tool()
    test_code_tool()
    test_calculator_tool()
    test_pl5_tool()
    print("\n=== 所有测试完成 ===")
