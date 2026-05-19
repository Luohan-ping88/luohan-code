#!/usr/bin/env python3
"""
测试 PL5FixTool 功能

验证错误分析与修复工具是否能够正确处理各种类型的错误，并提供合理的修复建议。
"""

from src.tools import get_registry, ToolContext


def test_pl5_fix_tool():
    """测试 PL5FixTool 功能"""
    print("=== 测试 PL5FixTool ===")
    
    # 获取工具实例
    registry = get_registry()
    fix_tool_cls = registry.get("pl5_fix_tool")
    
    if not fix_tool_cls:
        print("❌ 未找到 pl5_fix_tool")
        return False
    
    fix_tool = fix_tool_cls()
    ctx = ToolContext()
    
    # 测试用例1: 数据缺失错误
    print("\n1. 测试数据缺失错误:")
    error_info_1 = {
        "code": "DATA_MISSING",
        "message": "数据文件不存在或路径错误",
        "details": {"path": "data/pl5_history.csv", "exists": False}
    }
    result_1 = fix_tool.execute(ctx, error_info=error_info_1)
    print(f"   成功: {result_1.success}")
    if result_1.success:
        print(f"   错误类别: {result_1.data['analysis']['category']}")
        print(f"   严重程度: {result_1.data['severity']}")
        print(f"   修复步骤数量: {len(result_1.data['fix_steps'])}")
        print(f"   预防措施数量: {len(result_1.data['prevention'])}")
        print(f"   相关工具: {result_1.data['related_tools']}")
    
    # 测试用例2: 模型加载错误
    print("\n2. 测试模型加载错误:")
    error_info_2 = {
        "code": "MODEL_LOAD_FAILED",
        "message": "模型文件加载失败，可能是文件损坏或路径错误",
        "details": {"model_path": "models/pl5_model.pkl", "error": "FileNotFoundError"}
    }
    result_2 = fix_tool.execute(ctx, error_info=error_info_2)
    print(f"   成功: {result_2.success}")
    if result_2.success:
        print(f"   错误类别: {result_2.data['analysis']['category']}")
        print(f"   严重程度: {result_2.data['severity']}")
        print(f"   修复步骤数量: {len(result_2.data['fix_steps'])}")
        print(f"   预防措施数量: {len(result_2.data['prevention'])}")
        print(f"   相关工具: {result_2.data['related_tools']}")
    
    # 测试用例3: 输入验证错误
    print("\n3. 测试输入验证错误:")
    error_info_3 = {
        "code": "VALIDATION_REQUIRED",
        "message": "缺少必填参数 'period'",
        "details": {"missing_fields": ["period"]}
    }
    result_3 = fix_tool.execute(ctx, error_info=error_info_3)
    print(f"   成功: {result_3.success}")
    if result_3.success:
        print(f"   错误类别: {result_3.data['analysis']['category']}")
        print(f"   严重程度: {result_3.data['severity']}")
        print(f"   修复步骤数量: {len(result_3.data['fix_steps'])}")
        print(f"   预防措施数量: {len(result_3.data['prevention'])}")
        print(f"   相关工具: {result_3.data['related_tools']}")
    
    # 测试用例4: 工具未找到错误
    print("\n4. 测试工具未找到错误:")
    error_info_4 = {
        "code": "TOOL_NOT_FOUND_PREDICTOR",
        "message": "未找到 predictor 工具，请确认 infrastructure 层已注册",
        "details": {"tool_name": "predictor"}
    }
    result_4 = fix_tool.execute(ctx, error_info=error_info_4)
    print(f"   成功: {result_4.success}")
    if result_4.success:
        print(f"   错误类别: {result_4.data['analysis']['category']}")
        print(f"   严重程度: {result_4.data['severity']}")
        print(f"   修复步骤数量: {len(result_4.data['fix_steps'])}")
        print(f"   预防措施数量: {len(result_4.data['prevention'])}")
        print(f"   相关工具: {result_4.data['related_tools']}")
    
    # 测试用例5: 执行异常错误
    print("\n5. 测试执行异常错误:")
    error_info_5 = {
        "code": "EXECUTION_ERROR",
        "message": "工具执行异常: division by zero",
        "details": {"exception_type": "ZeroDivisionError", "traceback": "..."}
    }
    result_5 = fix_tool.execute(ctx, error_info=error_info_5)
    print(f"   成功: {result_5.success}")
    if result_5.success:
        print(f"   错误类别: {result_5.data['analysis']['category']}")
        print(f"   严重程度: {result_5.data['severity']}")
        print(f"   修复步骤数量: {len(result_5.data['fix_steps'])}")
        print(f"   预防措施数量: {len(result_5.data['prevention'])}")
        print(f"   相关工具: {result_5.data['related_tools']}")
    
    print("\n=== 测试完成 ===")
    return all([result_1.success, result_2.success, result_3.success, result_4.success, result_5.success])


if __name__ == "__main__":
    success = test_pl5_fix_tool()
    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败！")
