#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试系统基本功能
"""

import numpy as np
import pandas as pd
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import ModelConfig
from src.core.features.engineer import FeatureEngineerV9
from src.core.data.collector import PL5DataCollector

def main():
    """主函数"""
    print("开始测试系统基本功能...")
    
    # 1. 测试数据加载
    print("\n1. 测试数据加载...")
    collector = PL5DataCollector()
    data = collector.load_processed_data()
    print(f"数据加载成功，共 {len(data)} 条记录")
    print(f"最新期号: {data.iloc[-1]['date']}")
    
    # 2. 测试特征生成
    print("\n2. 测试特征生成...")
    engineer = FeatureEngineerV9(enable_parallel=False)
    features = engineer.extract_all_features(data.iloc[-50:], select_top=5, detect_drift=False, enable_scaler=False)
    feature_cols = [col for col in features.columns if col not in ['date', 'wan', 'qian', 'bai', 'shi', 'ge']]
    print(f"特征生成成功，共 {len(feature_cols)} 个特征")
    print(f"特征列: {feature_cols}")
    
    # 3. 测试模型训练
    print("\n3. 测试模型训练...")
    model_config = ModelConfig()
    model = EnhancedPL5Predictor(model_config)
    
    # 只使用最近的30期数据进行训练
    train_data = features.iloc[:-10]
    model.fit(train_data, feature_cols=feature_cols)
    print(f"模型训练成功，is_trained: {model.is_trained}")
    
    # 4. 测试模型预测
    print("\n4. 测试模型预测...")
    test_row = features.iloc[-1]
    test_features = test_row[feature_cols].values.astype(float)
    
    # 提取最近的原始数据
    recent_data = {}
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    for pos in positions:
        recent_data[pos] = train_data[pos].iloc[-5:].values
    
    print(f"实际值: {test_row[['wan', 'qian', 'bai', 'shi', 'ge']].to_dict()}")
    
    prediction = model.predict(test_features, recent_data, top_k=8)
    print("预测结果:")
    for pos, data in prediction.items():
        print(f"  {pos}: {data['top_k']}")
    
    # 5. 检查预测是否包含实际值
    print("\n5. 检查预测是否包含实际值...")
    hits = {}
    for pos in positions:
        actual = test_row[pos]
        predicted = prediction[pos]['top_k']
        hit = actual in predicted
        hits[pos] = hit
        print(f"  {pos}: 实际值={actual}, 预测值={predicted}, 命中={hit}")
    
    print(f"总命中率: {sum(hits.values())/len(hits)}")
    
    print("\n系统基本功能测试完成！")

if __name__ == "__main__":
    main()
