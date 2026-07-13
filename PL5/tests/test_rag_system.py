#!/usr/bin/env python
"""
RAG系统测试脚本
"""

import asyncio
import numpy as np
import pandas as pd

from core.knowledge.rag_system import PL5KnowledgeRAG
from core.data.collector import PL5DataCollector
from core.features.engineer import FeatureEngineer


async def test_rag_system():
    """测试RAG系统"""
    print("开始测试RAG系统...")
    
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
    
    # 3. 初始化RAG系统
    print("3. 初始化RAG系统...")
    rag = PL5KnowledgeRAG()
    
    # 4. 构建知识库
    print("4. 构建知识库...")
    await rag.build_knowledge_base(df_features, feature_cols)
    
    # 5. 查看知识库统计
    stats = rag.get_knowledge_stats()
    print(f"5. 知识库统计: {stats}")
    
    # 6. 测试知识检索
    print("6. 测试知识检索...")
    latest_features = df_features[feature_cols].iloc[-1].values
    similar_patterns = await rag.retrieve_relevant_knowledge(latest_features, k=10)
    print(f"检索到 {len(similar_patterns)} 个相似模式")
    
    if similar_patterns:
        print("\n前3个相似模式:")
        for i, pattern in enumerate(similar_patterns[:3]):
            metadata = pattern['metadata']
            print(f"模式 {i+1}: 期号={metadata['period']}, 号码={metadata['wan']}{metadata['qian']}{metadata['bai']}{metadata['shi']}{metadata['ge']}, 相似度={pattern['similarity']:.4f}")
    
    # 7. 测试模式分析
    print("\n7. 测试模式分析...")
    analysis = await rag.analyze_similar_patterns(similar_patterns)
    print(f"分析结果: {analysis['recommendation']}")
    
    print("\nRAG系统测试完成！")


if __name__ == "__main__":
    asyncio.run(test_rag_system())
