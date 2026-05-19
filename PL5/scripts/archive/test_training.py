#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试模型训练过程脚本
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
print(f"数据大小: {len(data)}")

# 生成特征
print("2. 生成特征...")
engineer = FeatureEngineerV9(enable_parallel=False)
features = engineer.extract_all_features(data, select_top=None, detect_drift=False, enable_scaler=False)
feature_cols = [col for col in features.columns if col not in ['date', 'wan', 'qian', 'bai', 'shi', 'ge']]
print(f"特征数量: {len(feature_cols)}")
print(f"特征列: {feature_cols[:10]}...")  # 只显示前10个特征

# 划分训练集和测试集
test_size = 100
train_data = features.iloc[:-test_size]
test_data = features.iloc[-test_size:]
print(f"训练集大小: {len(train_data)}")
print(f"测试集大小: {len(test_data)}")

# 训练模型
print("3. 训练模型...")
model_config = ModelConfig()
model = EnhancedPL5Predictor(model_config)

# 检查训练前的状态
print(f"训练前 - is_trained: {model.is_trained}")
print(f"训练前 - stacking: {len(model.stacking) if hasattr(model, 'stacking') else 'N/A'}")
print(f"训练前 - hmm_models: {len(model.hmm_models) if hasattr(model, 'hmm_models') else 'N/A'}")
print(f"训练前 - bsts_models: {len(model.bsts_models) if hasattr(model, 'bsts_models') else 'N/A'}")
print(f"训练前 - copula_model: {'Yes' if hasattr(model, 'copula_model') and model.copula_model is not None else 'No'}")

# 开始训练
try:
    print("开始训练...")
    model.fit(train_data, feature_cols=feature_cols)
    print("训练完成!")
except Exception as e:
    print(f"训练失败: {e}")
    import traceback
    traceback.print_exc()

# 检查训练后的状态
print(f"训练后 - is_trained: {model.is_trained}")
print(f"训练后 - stacking: {len(model.stacking) if hasattr(model, 'stacking') else 'N/A'}")
print(f"训练后 - hmm_models: {len(model.hmm_models) if hasattr(model, 'hmm_models') else 'N/A'}")
print(f"训练后 - bsts_models: {len(model.bsts_models) if hasattr(model, 'bsts_models') else 'N/A'}")
print(f"训练后 - copula_model: {'Yes' if hasattr(model, 'copula_model') and model.copula_model is not None else 'No'}")

# 测试预测
if model.is_trained:
    print("4. 测试预测...")
    test_row = test_data.iloc[0]
    features_array = test_row[feature_cols].values.astype(float)
    recent_data = {}
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        recent_data[pos] = train_data[pos].iloc[-10:].values
    
    print(f"实际值: {test_row[['wan', 'qian', 'bai', 'shi', 'ge']].to_dict()}")
    
    prediction = model.predict(features_array, recent_data, top_k=8)
    print("预测结果:")
    for pos, data in prediction.items():
        print(f"  {pos}: {data['top_k']}")
        print(f"  概率: {data['probabilities']}")
        print()
else:
    print("模型未训练，无法预测")
