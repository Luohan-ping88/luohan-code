#!/usr/bin/env python
import cProfile
import pstats
import memory_profiler
import sys
sys.path.insert(0, '.')

from core.data_collector_v8 import PL5DataCollector
from core.feature_engineering_v8 import FeatureEngineer
from core.models import PL5Predictor

def analyze_performance():
    """分析性能瓶颈"""
    print("=== 性能瓶颈分析开始 ===")
    
    # 1. 数据采集分析
    print("\n1. 数据采集分析")
    @memory_profiler.profile
    def collect_data():
        collector = PL5DataCollector()
        df = collector.update_data()
        return df
    df = collect_data()
    
    # 2. 特征工程分析
    print("\n2. 特征工程分析")
    @memory_profiler.profile
    def feature_engineering_task():
        engineer = FeatureEngineer()
        df_features = engineer.extract_all_features(df)
        return df_features
    df_features = feature_engineering_task()
    
    # 3. 模型训练分析
    print("\n3. 模型训练分析")
    def training_task():
        predictor = PL5Predictor()
        feature_cols = [c for c in df_features.columns if c not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        X_train = df_features[feature_cols].values
        y_train = df_features[['wan', 'qian', 'bai', 'shi', 'ge']].values
        predictor.fit(X_train, y_train)
    
    # 使用cProfile分析训练时间
    cProfile.run('training_task()', 'training_profile.out')
    
    # 分析cProfile结果
    print("\n4. 训练时间分析")
    p = pstats.Stats('training_profile.out')
    p.strip_dirs().sort_stats('cumulative').print_stats(10)
    
    # 5. 模型文件分析
    print("\n5. 模型文件分析")
    import os
    import pickle
    from pathlib import Path
    
    models_dir = Path('models')
    for model_file in models_dir.glob('*.pkl'):
        size_mb = os.path.getsize(model_file) / (1024 * 1024)
        print(f"{model_file.name}: {size_mb:.2f} MB")
    
    print("\n=== 性能瓶颈分析完成 ===")

if __name__ == "__main__":
    analyze_performance()
