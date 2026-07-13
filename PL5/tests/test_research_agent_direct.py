#!/usr/bin/env python
"""
直接测试Research Agent
"""

import asyncio
import pandas as pd

from agent_framework.research_agent import ResearchAgent
from core.data.collector import PL5DataCollector
from core.features.engineer import FeatureEngineer


async def test_research_agent_direct():
    """直接测试Research Agent"""
    print("开始直接测试Research Agent...")
    
    # 1. 采集数据
    print("1. 采集数据...")
    collector = PL5DataCollector()
    df = collector.update_data()
    print(f"数据采集完成，记录数: {len(df)}")
    
    # 2. 提取特征
    print("2. 提取特征...")
    engineer = FeatureEngineer()
    df_features = engineer.extract_all_features(df)
    feature_cols = [c for c in df_features.columns if c not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
    print(f"特征提取完成，特征数: {len(feature_cols)}")
    
    # 3. 初始化Research Agent
    print("3. 初始化Research Agent...")
    research_agent = ResearchAgent()
    
    # 4. 分析历史模式
    print("4. 分析历史模式...")
    analysis_result = await research_agent.analyze_historical_patterns(df, feature_cols)
    
    # 5. 生成研究报告
    print("5. 生成研究报告...")
    research_report = await research_agent.generate_research_report(analysis_result)
    
    # 6. 保存研究报告
    from datetime import datetime
    from pathlib import Path
    report_path = Path('results') / f"research_report_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(research_report, encoding='utf-8')
    
    print(f"\n研究报告已保存到: {report_path}")
    print("\n研究分析完成！")
    print(f"基本统计信息: {analysis_result['basic_statistics']}")
    
    # 7. 关闭智能体
    research_agent.shutdown()
    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(test_research_agent_direct())
