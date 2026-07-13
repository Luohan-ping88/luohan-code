#!/usr/bin/env python
"""
PL5 训练后模型预测演示
展示训练后的模型预测效果
"""
import sys
import os
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def main():
    print('='*60)
    print('PL5 训练后模型预测演示')
    print('='*60)
    print()

    # 加载数据
    print('[1/3] 加载数据...')
    from src.core.data.collector import PL5DataCollectorV8
    collector = PL5DataCollectorV8()
    data = collector.load_processed_data()
    print(f'      已加载 {len(data)} 条历史记录')
    print(f'      最新期号: {data["period"].iloc[-1]}')
    print()

    # 特征工程
    print('[2/3] 特征工程...')
    from src.core.features.engineer import FeatureEngineer
    engineer = FeatureEngineer()
    features = engineer.extract_all_features(data)
    print(f'      提取了 {len(features.columns)} 个特征')
    
    # 获取特征列
    non_feature_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']
    feature_cols = [col for col in features.columns if col not in non_feature_cols]
    print(f'      特征列数量: {len(feature_cols)}')
    print()

    # 加载训练好的模型并预测
    print('[3/3] 加载模型并生成预测...')
    from src.core.models.predictor import PL5Predictor
    
    predictor = PL5Predictor()
    
    # 加载训练好的模型
    model_path = 'src/models/pl5_predictor_trained.pkl'
    if os.path.exists(model_path):
        with open(model_path, 'rb') as f:
            saved_models = pickle.load(f)
        predictor.models = saved_models
        predictor.feature_cols = feature_cols
        predictor.is_trained = True
        print('      已加载训练好的模型')
    else:
        print('      警告: 未找到训练好的模型')
        return
    
    # 使用最后一条数据进行预测
    latest_features = features.iloc[[-1]]
    predictions = predictor.predict(latest_features)
    
    print()
    print('      预测结果（训练后）:')
    print('      ' + '-'*50)
    for position in ['wan', 'qian', 'bai', 'shi', 'ge']:
        top_k = predictions[position]['top_k']
        probs = predictions[position]['probabilities']
        prob_str = ', '.join([f'{p:.1%}' for p in probs[:3]])
        print(f'        {position:6s}: {top_k[:5]} (概率: {prob_str}...)')
    print('      ' + '-'*50)
    print()

    print('='*60)
    print('训练后模型预测完成!')
    print('='*60)

if __name__ == '__main__':
    main()
