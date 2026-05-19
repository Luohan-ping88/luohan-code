#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统集成测试脚本

测试整个系统的集成，包括数据加载、特征生成、模型训练和预测的完整流程。
"""

import os
import sys
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineerV9
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import ModelConfig
from src.core.utils.resource_manager import get_resource_manager

def test_integration():
    """测试系统集成"""
    print("开始系统集成测试...")
    start_time = time.time()
    
    # 1. 测试数据加载
    print("\n1. 测试数据加载...")
    collector = PL5DataCollector()
    data = collector.load_processed_data()
    print(f"数据加载成功，共 {len(data)} 条记录")
    
    # 2. 测试特征生成
    print("\n2. 测试特征生成...")
    engineer = FeatureEngineerV9(enable_parallel=False)
    # 只使用前100条数据进行测试，加快测试速度
    test_data = data.iloc[-100:]
    features = engineer.extract_all_features(test_data)
    feature_cols = [col for col in features.columns if col not in ['date', 'wan', 'qian', 'bai', 'shi', 'ge']]
    print(f"特征生成成功，生成了 {len(feature_cols)} 个特征")
    
    # 3. 测试模型训练
    print("\n3. 测试模型训练...")
    model_config = ModelConfig()
    model = EnhancedPL5Predictor(model_config)
    # 只使用前50条数据进行训练，加快测试速度
    train_data = features.iloc[:50]
    model.fit(train_data, feature_cols=feature_cols)
    print("模型训练成功")
    
    # 4. 测试模型预测
    print("\n4. 测试模型预测...")
    # 使用最后一条数据进行预测
    test_sample = features.iloc[-1][feature_cols].values.astype(float)
    # 提取最近的原始数据
    recent_data = {}
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        recent_data[pos] = data[pos].iloc[-10:].values
    # 预测
    prediction = model.predict(test_sample, recent_data, top_k=8)
    print("模型预测成功")
    print("预测结果:")
    for pos, data in prediction.items():
        print(f"  {pos}: {data['top_k']}")
    
    # 5. 测试资源管理
    print("\n5. 测试资源管理...")
    rm = get_resource_manager()
    usage = rm.get_resource_usage()
    print(f"资源使用情况: {rm.get_resource_summary()}")
    optimal_workers = rm.get_optimal_workers()
    print(f"最优工作线程数: {optimal_workers}")
    batch_size = rm.suggest_batch_size()
    print(f"建议批处理大小: {batch_size}")
    
    # 6. 测试资源趋势分析
    print("\n6. 测试资源趋势分析...")
    trend = rm.get_resource_trend(window=10)
    print(f"CPU趋势斜率: {trend['cpu_slope']:.2f}")
    print(f"内存趋势斜率: {trend['memory_slope']:.2f}")
    print(f"磁盘趋势斜率: {trend['disk_slope']:.2f}")
    
    # 7. 测试资源预测
    print("\n7. 测试资源预测...")
    prediction = rm.predict_resource_usage(minutes=5)
    print(f"5分钟后预测CPU使用率: {prediction['predicted_cpu']:.1f}%")
    print(f"5分钟后预测内存使用率: {prediction['predicted_memory']:.1f}%")
    print(f"5分钟后预测磁盘使用率: {prediction['predicted_disk']:.1f}%")
    
    # 计算测试时间
    end_time = time.time()
    test_duration = end_time - start_time
    print(f"\n测试完成，耗时: {test_duration:.2f} 秒")
    
    return True

if __name__ == "__main__":
    try:
        success = test_integration()
        if success:
            print("\n🎉 系统集成测试成功！所有组件正常工作。")
        else:
            print("\n❌ 系统集成测试失败！")
    except Exception as e:
        print(f"\n❌ 系统集成测试失败: {e}")
        import traceback
        traceback.print_exc()
