#!/usr/bin/env python
import cProfile
import pstats
import memory_profiler
import sys
import os
import pickle
from pathlib import Path
sys.path.insert(0, '.')

from core.data_collector_v8 import PL5DataCollector
from core.feature_engineering_v8 import FeatureEngineer
from core.models import PL5Predictor

def analyze_performance():
    """详细分析性能瓶颈"""
    print("=== 详细性能瓶颈分析开始 ===")
    
    # 1. 数据采集分析
    print("\n1. 数据采集详细分析")
    @memory_profiler.profile
    def collect_data():
        collector = PL5DataCollector()
        df = collector.update_data()
        return df
    df = collect_data()
    
    # 2. 特征工程分析
    print("\n2. 特征工程详细分析")
    @memory_profiler.profile
    def feature_engineering_task():
        engineer = FeatureEngineer()
        df_features = engineer.extract_all_features(df)
        return df_features
    df_features = feature_engineering_task()
    
    # 3. 模型训练分析
    print("\n3. 模型训练详细分析")
    def training_task():
        predictor = PL5Predictor()
        feature_cols = [c for c in df_features.columns if c not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        X_train = df_features[feature_cols].values
        y_train = df_features[['wan', 'qian', 'bai', 'shi', 'ge']].values
        predictor.fit(X_train, y_train)
    
    # 使用cProfile分析训练时间
    cProfile.run('training_task()', 'training_profile.out')
    
    # 分析cProfile结果
    print("\n4. 训练时间详细分析")
    p = pstats.Stats('training_profile.out')
    p.strip_dirs().sort_stats('cumulative').print_stats(20)
    
    # 5. 模型文件详细分析
    print("\n5. 模型文件详细分析")
    models_dir = Path('models')
    total_size = 0
    for model_file in models_dir.glob('*.pkl'):
        size_mb = os.path.getsize(model_file) / (1024 * 1024)
        total_size += size_mb
        print(f"{model_file.name}: {size_mb:.2f} MB")
    print(f"\n总模型文件大小: {total_size:.2f} MB")
    
    # 6. 分析大型模型文件的结构
    print("\n6. 大型模型文件结构分析")
    large_model_files = ['ensemble_position_models.pkl', 'stacker_models.pkl']
    for model_file in large_model_files:
        model_path = models_dir / model_file
        if model_path.exists():
            print(f"\n分析 {model_file}:")
            try:
                with open(model_path, 'rb') as f:
                    data = pickle.load(f)
                if isinstance(data, dict):
                    print(f"  数据类型: dict, 键数量: {len(data)}")
                    for key, value in data.items():
                        print(f"  - {key}: {type(value).__name__}")
                elif isinstance(data, list):
                    print(f"  数据类型: list, 长度: {len(data)}")
                else:
                    print(f"  数据类型: {type(data).__name__}")
            except Exception as e:
                print(f"  分析失败: {e}")
    
    print("\n=== 详细性能瓶颈分析完成 ===")

if __name__ == "__main__":
    analyze_performance()
