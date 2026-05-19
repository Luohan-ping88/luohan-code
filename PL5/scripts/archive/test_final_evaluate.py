#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终评估脚本
"""

import numpy as np
import pandas as pd
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import ModelConfig
from src.core.features.engineer import FeatureEngineerV9
from src.core.data.collector import PL5DataCollector

def main():
    """主函数"""
    print("开始评估模型性能...")
    
    # 加载数据
    print("1. 加载数据...")
    collector = PL5DataCollector()
    data = collector.load_processed_data()
    
    # 只使用最近的100期数据
    data = data.iloc[-100:]
    
    # 划分训练集和测试集（使用最近的20期作为测试集）
    test_size = 20
    train_data = data.iloc[:-test_size]
    test_data = data.iloc[-test_size:]
    
    print(f"训练集大小: {len(train_data)}")
    print(f"测试集大小: {len(test_data)}")
    
    # 生成特征
    print("2. 生成特征...")
    engineer = FeatureEngineerV9(enable_parallel=False)
    
    # 生成训练集特征（只使用前10个特征）
    train_features = engineer.extract_all_features(train_data, select_top=10, detect_drift=False, enable_scaler=False)
    feature_cols = [col for col in train_features.columns if col not in ['date', 'wan', 'qian', 'bai', 'shi', 'ge']]
    
    # 生成测试集特征
    test_features = engineer.extract_all_features(test_data, select_top=10, detect_drift=False, enable_scaler=False)
    
    print(f"特征数量: {len(feature_cols)}")
    print(f"特征列: {feature_cols}")
    
    # 训练模型
    print("3. 训练模型...")
    model_config = ModelConfig()
    model = EnhancedPL5Predictor(model_config)
    
    print(f"训练前 - is_trained: {model.is_trained}")
    
    try:
        model.fit(train_features, feature_cols=feature_cols)
        print(f"训练后 - is_trained: {model.is_trained}")
    except Exception as e:
        print(f"训练失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 测试预测
    print("4. 测试预测...")
    test_row = test_features.iloc[0]
    features = test_row[feature_cols].values.astype(float)
    
    # 提取最近的原始数据
    recent_data = {}
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    for pos in positions:
        recent_data[pos] = train_features[pos].iloc[-10:].values
    
    print(f"实际值: {test_row[['wan', 'qian', 'bai', 'shi', 'ge']].to_dict()}")
    
    prediction = model.predict(features, recent_data, top_k=8)
    print("预测结果:")
    for pos, data in prediction.items():
        print(f"  {pos}: {data['top_k']}")
        print(f"  概率: {data['probabilities']}")
        print()
    
    # 检查预测是否包含实际值
    print("5. 检查预测是否包含实际值...")
    hits = {}
    for pos in positions:
        actual = test_row[pos]
        predicted = prediction[pos]['top_k']
        hit = actual in predicted
        hits[pos] = hit
        print(f"  {pos}: 实际值={actual}, 预测值={predicted}, 命中={hit}")
    
    print(f"总命中率: {sum(hits.values())/len(hits)}")
    
    print("\n评估完成！")

if __name__ == "__main__":
    main()
