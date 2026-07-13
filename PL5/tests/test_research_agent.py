#!/usr/bin/env python
"""
Research Agent测试脚本
"""

import asyncio
import pandas as pd

from agent_framework.orchestrator import AgentOrchestrator


async def test_research_agent():
    """测试Research Agent"""
    print("开始测试Research Agent...")
    
    # 初始化编排器
    orchestrator = AgentOrchestrator()
    
    # 执行完整流水线
    result = await orchestrator.execute_full_pipeline()
    
    print(f"流水线执行结果: {'成功' if result['success'] else '失败'}")
    
    if result['success']:
        # 检查研究分析结果
        research_result = result['results'].get('research_analysis', {})
        if research_result.get('success'):
            print("\n研究分析成功！")
            print(f"报告路径: {research_result.get('report_path')}")
            print(f"基本统计信息: {research_result['report_summary'].get('basic_statistics', {})}")
        else:
            print("\n研究分析失败:")
            print(f"错误: {research_result.get('error')}")
    else:
        print(f"流水线执行失败: {result.get('error')}")
    
    # 关闭编排器
    orchestrator.shutdown()
    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(test_research_agent())
