#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试模型预测脚本
"""

import numpy as np
import pandas as pd
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import ModelConfig
from src.core.features.engineer import FeatureEngineerV9
from src.core.data.collector import PL5DataCollector

# 加载数据
print("1. 加载数据...")
collector = PL5DataCollector()
data = collector.load_processed_data()

# 生成特征
print("2. 生成特征...")
engineer = FeatureEngineerV9(enable_parallel=False)
features = engineer.extract_all_features(data, select_top=None, detect_drift=False, enable_scaler=False)
feature_cols = [col for col in features.columns if col not in ['date', 'wan', 'qian', 'bai', 'shi', 'ge']]
print(f"特征数量: {len(feature_cols)}")

# 训练模型
print("3. 训练模型...")
model_config = ModelConfig()
model = EnhancedPL5Predictor(model_config)
model.fit(features.iloc[:-100], feature_cols=feature_cols)
print(f"模型训练完成，is_trained: {model.is_trained}")

# 测试预测
print("4. 测试预测...")
test_row = features.iloc[-1]
features_array = test_row[feature_cols].values.astype(float)
recent_data = {}
for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    recent_data[pos] = features[pos].iloc[-11:-1].values

print(f"实际值: {test_row[['wan', 'qian', 'bai', 'shi', 'ge']].to_dict()}")

prediction = model.predict(features_array, recent_data, top_k=8)
print("预测结果:")
for pos, data in prediction.items():
    print(f"  {pos}: {data['top_k']}")
    print(f"  概率: {data['probabilities']}")
    print(f"  不确定性: {data['uncertainty']}")
    print()

# 检查预测是否包含实际值
print("5. 检查预测是否包含实际值...")
hits = {}
for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    actual = test_row[pos]
    predicted = prediction[pos]['top_k']
    hit = actual in predicted
    hits[pos] = hit
    print(f"  {pos}: 实际值={actual}, 预测值={predicted}, 命中={hit}")

print(f"总命中率: {sum(hits.values())/len(hits)}")
