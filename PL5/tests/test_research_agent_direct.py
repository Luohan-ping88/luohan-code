#!/usr/bin/env python
"""
直接测试Research Agent
"""

import asyncio
import pandas as pd

from src.agents.research_agent import ResearchAgent
from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer


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
    feature_cols = [
        c for c in df_features.columns if c not in ["period", "full_number", "wan", "qian", "bai", "shi", "ge"]
    ]
    print(f"特征提取完成，特征数: {len(feature_cols)}")

    # 3. 初始化研究智能体
    print("3. 初始化研究智能体...")
    agent = ResearchAgent()

    # 4. 执行研究分析
    print("4. 执行研究分析...")
    result = await agent.analyze(df_features, feature_cols)
    print(f"分析结果: {result}")

    print("\nResearch Agent直接测试完成！")


if __name__ == "__main__":
    asyncio.run(test_research_agent_direct())
