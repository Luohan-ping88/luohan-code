#!/usr/bin/env python
"""
PL5 模型训练和预测完整流程
"""
import sys
import os
import time
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def main():
    print('='*60)
    print('PL5 模型训练与预测系统')
    print('='*60)
    print()

    # 1. 数据采集
    print('[1/5] 数据采集...')
    from src.core.data.collector import PL5DataCollectorV8
    collector = PL5DataCollectorV8()
    data = collector.load_processed_data()
    print(f'      已加载 {len(data)} 条历史记录')
    print(f'      最新期号: {data["period"].iloc[-1]}')
    print()

    # 2. 特征工程
    print('[2/5] 特征工程...')
    from src.core.features.engineer import FeatureEngineer
    
    engineer = FeatureEngineer()
    start = time.time()
    features = engineer.extract_all_features(data)
    elapsed = time.time() - start
    print(f'      提取了 {len(features.columns)} 个特征')
    print(f'      耗时: {elapsed:.2f}秒')
    print()

    # 3. 训练模型
    print('[3/5] 训练模型...')
    from src.core.models.predictor import PL5Predictor
    
    predictor = PL5Predictor()
    
    # 获取特征列（排除非特征列）
    non_feature_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']
    feature_cols = [col for col in features.columns if col not in non_feature_cols]
    print(f'      特征列数量: {len(feature_cols)}')
    
    # 检查是否已有训练好的模型
    model_path = 'src/models/pl5_predictor_trained.pkl'
    if os.path.exists(model_path):
        print('      发现已训练模型，加载中...')
        with open(model_path, 'rb') as f:
            saved_models = pickle.load(f)
        predictor.models = saved_models
        print('      模型加载完成!')
    else:
        print('      开始训练模型...')
        start = time.time()
        predictor.train(features, feature_cols)
        elapsed = time.time() - start
        print(f'      模型训练完成，耗时: {elapsed:.2f}秒')
        
        # 保存训练好的模型
        with open(model_path, 'wb') as f:
            pickle.dump(predictor.models, f)
        print(f'      模型已保存到: {model_path}')
    print()

    # 4. 生成预测
    print('[4/5] 生成预测...')
    # 使用最后一条数据进行预测
    latest_features = features.iloc[[-1]]
    predictions = predictor.predict(latest_features)
    
    print('      预测结果:')
    for position in ['wan', 'qian', 'bai', 'shi', 'ge']:
        top_k = predictions[position]['top_k']
        probs = predictions[position]['probabilities']
        print(f'        {position}: {top_k} (概率: {[f"{p:.2%}" for p in probs[:3]]}...)')
    print()

    # 5. 系统监控
    print('[5/5] 系统监控...')
    from monitor.perfect_monitor import PerfectSystemMonitor
    monitor = PerfectSystemMonitor()
    metrics = monitor.get_system_metrics()
    print(f'      CPU: {metrics["cpu"]["percent"]}%')
    print(f'      内存: {metrics["memory"]["percent"]}%')
    print(f'      磁盘: {metrics["disk"]["percent"]}%')
    print()

    print('='*60)
    print('模型训练与预测完成!')
    print('='*60)

if __name__ == '__main__':
    main()
