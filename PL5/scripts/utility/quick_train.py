#!/usr/bin/env python
"""快速训练模型"""
import sys
sys.path.insert(0, '.')

from src.core.data.collector import PL5DataCollectorV8
from src.core.features.engineer import FeatureEngineer
from src.core.models.predictor import PL5Predictor
import pickle

print('开始训练模型...')

# 1. 先更新数据
collector = PL5DataCollectorV8()
print('检查数据更新...')
data = collector.update_data()
if data is None:
    print('没有新数据，使用现有数据')
    data = collector.load_processed_data()
print(f'数据加载完成: {len(data)} 条')
print(f'最新期号: {data["period"].iloc[-1]}')

# 特征工程
engineer = FeatureEngineer()
features = engineer.extract_all_features(data)
print(f'特征提取完成: {len(features.columns)} 个特征')

# 获取特征列
non_feature_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']
feature_cols = [col for col in features.columns if col not in non_feature_cols]
print(f'特征列: {len(feature_cols)} 个')

# 训练模型
predictor = PL5Predictor()
print('开始训练...')
predictor.train(features, feature_cols)
print('训练完成!')

# 保存模型
model_path = 'src/models/pl5_predictor_trained.pkl'
with open(model_path, 'wb') as f:
    # 保存所有训练好的模型组件
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
print(f'模型已保存到: {model_path}')
print(f'模型大小: {os.path.getsize(model_path) / 1024:.2f} KB')

# 测试预测
latest = features.iloc[[-1]]
preds = predictor.predict(latest)
print('\n预测结果:')
for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    print(f'  {pos}: {preds[pos]["top_k"][:3]}')
