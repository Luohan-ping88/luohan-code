#!/usr/bin/env python
"""
快速训练模式 - 与定时任务不冲突
使用简化流程快速训练模型
"""
import sys
import os
import time
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

print('='*60)
print('PL5 快速训练模式')
print('（此模式与定时任务不冲突）')
print('='*60)
print()

# 1. 加载数据
print('[1/4] 加载数据...')
from src.core.data.collector import PL5DataCollectorV8
collector = PL5DataCollectorV8()
data = collector.load_processed_data()
print(f'      数据量: {len(data)} 条')
print(f'      最新期号: {data["period"].iloc[-1]}')
print()

# 2. 特征工程
print('[2/4] 特征工程...')
from src.core.features.engineer import FeatureEngineer

engineer = FeatureEngineer()
start = time.time()
features = engineer.extract_all_features(data)
elapsed = time.time() - start
print(f'      特征数: {len(features.columns)} 个')
print(f'      耗时: {elapsed:.2f}秒')

# 获取特征列
non_feature_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']
feature_cols = [col for col in features.columns if col not in non_feature_cols]
print(f'      训练特征: {len(feature_cols)} 个')
print()

# 3. 训练模型
print('[3/4] 训练模型...')
from src.core.models.predictor import PL5Predictor

predictor = PL5Predictor()
print('      开始训练...')
start = time.time()
predictor.train(features, feature_cols)
elapsed = time.time() - start
print(f'      训练完成，耗时: {elapsed:.2f}秒')

# 保存模型
model_path = 'src/models/pl5_predictor_trained.pkl'
with open(model_path, 'wb') as f:
    model_data = {
        'stacking': predictor.stacking,
        'hmm_models': predictor.hmm_models,
        'bsts_models': predictor.bsts_models,
        'evm_models': predictor.evm_models,
        'copula': predictor.copula,
        'is_trained': predictor.is_trained,
        'feature_cols': feature_cols
    }
    pickle.dump(model_data, f)
print(f'      模型已保存: {model_path}')
print(f'      模型大小: {os.path.getsize(model_path) / 1024:.2f} KB')
print()

# 4. 测试预测
print('[4/4] 测试预测...')
latest = features.iloc[[-1]]
preds = predictor.predict(latest)
print('      预测结果:')
for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    top3 = preds[pos]['top_k'][:3]
    probs = preds[pos]['probabilities'][:3]
    prob_str = ', '.join([f'{p:.1%}' for p in probs])
    print(f'        {pos}: {top3} (概率: {prob_str})')
print()

print('='*60)
print('快速训练完成!')
print('='*60)
