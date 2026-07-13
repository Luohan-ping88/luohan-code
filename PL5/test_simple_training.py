#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试模型训练脚本
"""

import numpy as np
import pandas as pd
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import ModelConfig

# 创建简单的训练数据
print("1. 创建简单的训练数据...")
# 只创建50条数据
n_samples = 50
wan = np.random.randint(0, 10, n_samples)
qian = np.random.randint(0, 10, n_samples)
bai = np.random.randint(0, 10, n_samples)
shi = np.random.randint(0, 10, n_samples)
ge = np.random.randint(0, 10, n_samples)

# 创建特征
features = np.random.rand(n_samples, 3)  # 只有3个特征

# 创建DataFrame
data = pd.DataFrame({
    'wan': wan,
    'qian': qian,
    'bai': bai,
    'shi': shi,
    'ge': ge
})

# 添加特征列
for i in range(3):
    data[f'feature_{i}'] = features[:, i]

feature_cols = [f'feature_{i}' for i in range(3)]
print(f"特征列: {feature_cols}")
print(f"数据大小: {len(data)}")

# 训练模型
print("2. 训练模型...")
model_config = ModelConfig()
model = EnhancedPL5Predictor(model_config)

print(f"训练前 - is_trained: {model.is_trained}")

# 开始训练
try:
    print("开始训练...")
    model.fit(data, feature_cols=feature_cols)
    print("训练完成!")
except Exception as e:
    print(f"训练失败: {e}")
    import traceback
    traceback.print_exc()

# 检查训练后的状态
print(f"训练后 - is_trained: {model.is_trained}")

# 测试预测
if model.is_trained:
    print("3. 测试预测...")
    test_features = np.random.rand(3)  # 3个特征
    recent_data = {}
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        recent_data[pos] = np.random.randint(0, 10, 3)  # 3个随机数字
    
    prediction = model.predict(test_features, recent_data, top_k=8)
    print("预测结果:")
    for pos, data in prediction.items():
        print(f"  {pos}: {data['top_k']}")
else:
    print("模型未训练，无法预测")
