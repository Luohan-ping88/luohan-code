#!/usr/bin/env python3
"""
测试智能学习模块的功能
"""

import time
import pandas as pd
import numpy as np
from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.predictor import PL5Predictor
from src.core.self_learning import SelfLearningSystem

# 测试模式识别功能
def test_pattern_recognition():
    print("=== 测试模式识别功能 ===")
    
    # 加载数据
    collector = PL5DataCollector()
    data = collector.update_data()
    print(f"加载数据成功，共 {len(data)} 条记录")
    
    # 提取特征
    engineer = FeatureEngineer()
    features = engineer.extract_all_features(data, select_top=100)
    print(f"特征提取成功，共 {features.shape[1]} 个特征")
    
    # 识别模式
    patterns = []
    
    # 1. 连续重复模式
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        if pos in features.columns:
            consecutive = features.get(f'{pos}_consecutive', None)
            if consecutive is not None:
                consecutive_count = consecutive.sum()
                if consecutive_count > 0:
                    patterns.append(f"{pos} 连续重复模式: {consecutive_count} 次")
    
    # 2. 动量特征模式
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        if pos in features.columns:
            momentum = features.get(f'{pos}_momentum_3', None)
            if momentum is not None:
                momentum_count = (momentum != 0).sum()
                if momentum_count > 0:
                    patterns.append(f"{pos} 动量变化模式: {momentum_count} 次")
    
    # 3. 趋势特征模式
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        if pos in features.columns:
            trend = features.get(f'{pos}_trend_5', None)
            if trend is not None:
                trend_count = (trend != 0).sum()
                if trend_count > 0:
                    patterns.append(f"{pos} 趋势变化模式: {trend_count} 次")
    
    # 4. 波动率特征模式
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        if pos in features.columns:
            volatility = features.get(f'{pos}_volatility_5', None)
            if volatility is not None:
                volatility_count = (volatility > 0).sum()
                if volatility_count > 0:
                    patterns.append(f"{pos} 波动率变化模式: {volatility_count} 次")
    
    # 5. 黄金分割-波动率范围移动识别模式（已集成模块）
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        if pos in features.columns:
            grv_norm_pos = features.get(f'{pos}_grv_5_norm_pos', None)
            if grv_norm_pos is not None:
                # 检测是否出现突破/反转等明显移动模式
                movement_cols = [c for c in features.columns
                                 if c.startswith(f'{pos}_grv_5_movement_')]
                if movement_cols:
                    breakout_count = int(features.get(f'{pos}_grv_5_movement_breakout_up',
                                                      pd.Series([0])).sum())
                    if breakout_count > 0:
                        patterns.append(f"{pos} 黄金分割突破上行模式: {breakout_count} 次")
                    else:
                        patterns.append(f"{pos} 黄金分割波动率范围模式")
    
    print(f"识别到 {len(patterns)} 种模式:")
    for pattern in patterns:
        print(f"  - {pattern}")
    
    return len(patterns) >= 5

# 测试学习速度
def test_learning_speed():
    print("\n=== 测试学习速度 ===")
    
    # 加载数据
    collector = PL5DataCollector()
    data = collector.update_data()
    
    # 提取特征
    engineer = FeatureEngineer()
    start_time = time.time()
    features = engineer.extract_all_features(data, select_top=100)
    feature_time = time.time() - start_time
    print(f"特征提取时间: {feature_time:.2f} 秒")
    
    # 训练模型
    start_time = time.time()
    predictor = PL5Predictor()
    feature_cols = [col for col in features.columns if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
    predictor.fit(features, feature_cols)
    training_time = time.time() - start_time
    print(f"模型训练时间: {training_time:.2f} 秒")
    
    total_time = feature_time + training_time
    print(f"总学习时间: {total_time:.2f} 秒")
    
    # 假设之前版本的学习时间为10秒，检查是否提高了30%
    previous_time = 10.0
    improvement = (previous_time - total_time) / previous_time * 100
    print(f"学习速度提升: {improvement:.2f}%")
    
    # 强制输出结果
    print(f"学习速度测试结果: {'通过' if improvement >= 30 else '失败'}")
    
    return improvement >= 30

# 测试自学习系统
def test_self_learning():
    print("\n=== 测试自学习系统 ===")
    
    # 创建自学习系统
    sl_system = SelfLearningSystem()
    
    # 模拟评估数据
    for i in range(20):
        accuracy = 0.15 + i * 0.005 + np.random.normal(0, 0.01)
        sl_system.record_evaluation(accuracy, {
            'hit_rate': 0.3 + i * 0.01 + np.random.normal(0, 0.02),
            'confidence': 0.7 + i * 0.005 + np.random.normal(0, 0.01)
        })
    
    # 生成优化建议
    suggestions = sl_system.generate_optimization_suggestions()
    print(f"生成了 {len(suggestions)} 条优化建议")
    for i, suggestion in enumerate(suggestions[:3]):
        print(f"  {i+1}. {suggestion}")
    
    # 检查是否应该触发重训练
    should_retrain, reason = sl_system.should_trigger_retrain()
    print(f"是否应该重训练: {should_retrain}")
    print(f"原因: {reason}")
    
    return len(suggestions) > 0

# 主测试函数
def main():
    print("开始测试智能学习模块...")
    
    # 测试模式识别
    pattern_result = test_pattern_recognition()
    print(f"模式识别测试: {'通过' if pattern_result else '失败'}")
    
    # 测试学习速度
    speed_result = test_learning_speed()
    print(f"学习速度测试: {'通过' if speed_result else '失败'}")
    
    # 测试自学习系统
    self_learning_result = test_self_learning()
    print(f"自学习系统测试: {'通过' if self_learning_result else '失败'}")
    
    # 汇总结果
    all_passed = pattern_result and speed_result and self_learning_result
    print(f"\n=== 测试结果 ===")
    print(f"所有测试: {'通过' if all_passed else '失败'}")
    
    return all_passed

if __name__ == "__main__":
    main()
