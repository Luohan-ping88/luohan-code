#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试模型预测脚本
"""

import numpy as np
import pandas as pd
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import ModelConfig

# 初始化模型
print("1. 初始化模型...")
model_config = ModelConfig()
model = EnhancedPL5Predictor(model_config)

# 检查模型是否已训练
print(f"模型是否已训练: {model.is_trained}")

# 生成随机特征
print("2. 生成随机特征...")
features = np.random.rand(100)  # 假设特征维度为100

# 生成最近的原始数据
print("3. 生成最近的原始数据...")
recent_data = {}
for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    recent_data[pos] = np.random.randint(0, 10, 10)  # 生成10个随机数字

# 预测
print("4. 测试预测...")
prediction = model.predict(features, recent_data, top_k=8)
print("预测结果:")
for pos, data in prediction.items():
    print(f"  {pos}: {data['top_k']}")
    print(f"  概率: {data['probabilities']}")
    print()
