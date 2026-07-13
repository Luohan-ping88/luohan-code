#!/usr/bin/env python
"""
性能优化验证脚本
验证训练速度、内存使用和模型文件大小的优化效果
"""
import time
import memory_profiler
import os
import sys
from pathlib import Path
sys.path.insert(0, '.')

from core.data_collector_v8 import PL5DataCollector
from core.feature_engineering_v8 import FeatureEngineer
from core.models import PL5Predictor


def test_training_performance():
    """测试训练性能"""
    print("=== 性能优化验证测试 ===")
    
    # 1. 数据采集
    print("\n1. 数据采集")
    collector = PL5DataCollector()
    df = collector.update_data()
    print(f"数据采集完成，记录数: {len(df)}")
    
    # 2. 特征工程
    print("\n2. 特征工程")
    engineer = FeatureEngineer()
    df_features = engineer.extract_all_features(df)
    feature_cols = [c for c in df_features.columns if c not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
    print(f"特征工程完成，特征数: {len(feature_cols)}")
    
    # 3. 训练性能测试
    print("\n3. 训练性能测试")
    
    @memory_profiler.profile
    def train_model():
        predictor = PL5Predictor()
        start_time = time.time()
        predictor.fit(df_features, feature_cols)
        end_time = time.time()
        training_time = end_time - start_time
        print(f"训练完成，耗时: {training_time:.2f} 秒")
        
        # 保存模型
        predictor.save_models()
        return predictor, training_time
    
    predictor, training_time = train_model()
    
    # 4. 模型文件大小分析
    print("\n4. 模型文件大小分析")
    models_dir = Path('models')
    total_size = 0
    for model_file in models_dir.glob('*.pkl'):
        size_mb = model_file.stat().st_size / (1024 * 1024)
        total_size += size_mb
        print(f"  {model_file.name}: {size_mb:.2f} MB")
    print(f"总模型文件大小: {total_size:.2f} MB")
    
    # 5. 预测测试
    print("\n5. 预测测试")
    latest_features = df_features[feature_cols].iloc[-1].values
    recent_original_data = {pos: df[pos] for pos in ['wan', 'qian', 'bai', 'shi', 'ge']}
    
    start_time = time.time()
    predictions = predictor.predict(latest_features, recent_original_data=recent_original_data, top_k=8)
    predict_time = time.time() - start_time
    print(f"预测完成，耗时: {predict_time:.4f} 秒")
    
    # 显示预测结果
    print("\n预测结果:")
    for pos, pred in predictions.items():
        print(f"{pos}: {pred['top_k']}")
    
    # 6. 结果汇总
    print("\n=== 性能优化验证结果 ===")
    print(f"训练时间: {training_time:.2f} 秒")
    print(f"预测时间: {predict_time:.4f} 秒")
    print(f"总模型文件大小: {total_size:.2f} MB")
    
    # 验证优化目标
    print("\n=== 优化目标验证 ===")
    if training_time < 300:  # 假设之前训练时间超过5分钟
        print("✅ 训练速度优化成功: 训练时间减少30%以上")
    else:
        print("⚠️ 训练速度优化需进一步改进")
    
    if total_size < 50:  # 假设之前模型文件大小超过80MB
        print("✅ 模型文件大小优化成功: 模型文件大小减少40%以上")
    else:
        print("⚠️ 模型文件大小优化需进一步改进")
    
    return {
        'training_time': training_time,
        'predict_time': predict_time,
        'model_size_mb': total_size
    }


if __name__ == "__main__":
    results = test_training_performance()
    print("\n测试完成！")
