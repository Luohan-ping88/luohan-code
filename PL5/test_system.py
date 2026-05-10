#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统测试脚本
测试PL5预测系统的各个模块是否正常工作
"""

import asyncio
import logging
from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.predictor import PL5Predictor
from src.core.email.sender import EmailSender
from src.core.evaluation.evaluator import PredictionEvaluator
from src.core.self_learning import SelfLearningSystem

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_system():
    """测试整个系统"""
    print("=====================================")
    print("PL5预测系统测试")
    print("=====================================")
    
    # 测试数据采集模块
    print("\n[测试1] 数据采集模块")
    try:
        collector = PL5DataCollector()
        data = collector.update_data()
        if data['success']:
            print(f"✓ 数据采集成功，记录数: {data['record_count']}")
        else:
            print(f"✗ 数据采集失败: {data['error']}")
    except Exception as e:
        print(f"✗ 数据采集模块初始化失败: {e}")
    
    # 测试特征工程模块
    print("\n[测试2] 特征工程模块")
    try:
        engineer = FeatureEngineer()
        print(f"✓ 特征工程模块初始化成功")
    except Exception as e:
        print(f"✗ 特征工程模块初始化失败: {e}")
    
    # 测试预测器模块
    print("\n[测试3] 预测器模块")
    try:
        predictor = PL5Predictor()
        print(f"✓ 预测器模块初始化成功")
    except Exception as e:
        print(f"✗ 预测器模块初始化失败: {e}")
    
    # 测试邮件发送模块
    print("\n[测试4] 邮件发送模块")
    try:
        sender = EmailSender()
        print(f"✓ 邮件发送模块初始化成功")
    except Exception as e:
        print(f"✗ 邮件发送模块初始化失败: {e}")
    
    # 测试评估器模块
    print("\n[测试5] 评估器模块")
    try:
        evaluator = PredictionEvaluator()
        print(f"✓ 评估器模块初始化成功")
    except Exception as e:
        print(f"✗ 评估器模块初始化失败: {e}")
    
    # 测试自学习模块
    print("\n[测试6] 自学习模块")
    try:
        self_learning = SelfLearningSystem()
        print(f"✓ 自学习模块初始化成功")
    except Exception as e:
        print(f"✗ 自学习模块初始化失败: {e}")
    
    print("\n=====================================")
    print("测试完成")
    print("=====================================")

if __name__ == "__main__":
    asyncio.run(test_system())
