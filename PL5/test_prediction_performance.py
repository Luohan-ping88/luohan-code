#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试系统的预测性能，评估系统在不同场景下的表现
"""

import numpy as np
import pandas as pd
from src.core.models.predictor import PL5Predictor
from src.core.evaluation.evaluator import PredictionEvaluator

if __name__ == "__main__":
    print("正在测试系统预测性能...")
    
    # 初始化预测器和评估器
    predictor = PL5Predictor()
    evaluator = PredictionEvaluator()
    
    # 加载模型
    print("正在加载模型...")
    load_success = predictor.load_models()
    if not load_success:
        print("模型加载失败，无法进行预测测试")
        exit(1)
    
    print("模型加载成功，开始测试预测性能...")
    
    # 模拟不同场景的测试数据
    test_scenarios = [
        {
            "name": "正常场景",
            "features": np.random.rand(69)  # 模型期望69个特征
        },
        {
            "name": "特征值接近零",
            "features": np.random.rand(69) * 0.1  # 特征值较小
        },
        {
            "name": "特征值较大",
            "features": np.random.rand(69) * 10  # 特征值较大
        },
        {
            "name": "特征值全为零",
            "features": np.zeros(69)  # 特征值全为零
        }
    ]
    
    # 模拟实际开奖号码（用于评估）
    actual = {
        "wan": 5,
        "qian": 3,
        "bai": 8,
        "shi": 2,
        "ge": 9
    }
    
    # 测试每个场景
    results = []
    for scenario in test_scenarios:
        print(f"\n测试场景: {scenario['name']}")
        
        # 生成预测
        predictions = predictor.predict(scenario['features'])
        
        # 评估预测结果
        evaluation = evaluator.evaluate_predictions(actual, predictions)
        
        # 输出评估结果
        print(f"评估结果: {evaluation.get('metrics', {})}")
        print(f"摘要: {evaluation.get('summary', {})}")
        
        # 保存结果
        results.append({
            "scenario": scenario['name'],
            "evaluation": evaluation
        })
    
    # 生成性能报告
    print("\n性能测试完成，生成报告...")
    print("=" * 80)
    print("系统预测性能测试报告")
    print("=" * 80)
    
    for result in results:
        print(f"\n场景: {result['scenario']}")
        metrics = result['evaluation'].get('metrics', {})
        summary = result['evaluation'].get('summary', {})
        
        print("评估指标:")
        for key, value in metrics.items():
            print(f"  {key}: {value:.4f}")
        
        print("摘要:")
        print(f"  总位置数: {summary.get('total_positions', 0)}")
        print(f"  总命中数: {summary.get('total_hits', 0)}")
        print(f"  最佳准确率: {summary.get('best_accuracy', 0):.4f}")
        print(f"  最差准确率: {summary.get('worst_accuracy', 0):.4f}")
        print(f"  平均准确率: {summary.get('average_accuracy', 0):.4f}")
    
    print("\n" + "=" * 80)
    print("性能测试报告生成完成")
