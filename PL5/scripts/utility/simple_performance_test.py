#!/usr/bin/env python3
"""
简单的系统性能测试脚本
测试PL5系统的关键组件性能
"""

import time
import sys
import os
sys.path.insert(0, '.')

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.predictor import PL5Predictor
from src.core.orchestrator import PL5Orchestrator
import asyncio


def test_data_collection():
    """测试数据采集性能"""
    print("\n=== 数据采集性能测试 ===")
    start_time = time.time()
    
    collector = PL5DataCollector()
    df = collector.update_data()
    
    execution_time = time.time() - start_time
    print(f"数据采集完成，记录数: {len(df)}")
    print(f"数据采集耗时: {execution_time:.2f}秒")
    
    return execution_time, len(df)


def test_feature_engineering(df):
    """测试特征工程性能"""
    print("\n=== 特征工程性能测试 ===")
    start_time = time.time()
    
    engineer = FeatureEngineer()
    df_features = engineer.extract_all_features(df)
    
    execution_time = time.time() - start_time
    feature_cols = [c for c in df_features.columns if c not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
    print(f"特征工程完成，特征数: {len(feature_cols)}")
    print(f"特征工程耗时: {execution_time:.2f}秒")
    
    return execution_time, len(feature_cols), df_features, feature_cols


def test_model_training(df_features, feature_cols):
    """测试模型训练性能"""
    print("\n=== 模型训练性能测试 ===")
    start_time = time.time()
    
    predictor = PL5Predictor()
    predictor.fit(df_features, feature_cols)
    predictor.save_models()
    
    execution_time = time.time() - start_time
    print(f"模型训练完成")
    print(f"模型训练耗时: {execution_time:.2f}秒")
    
    return execution_time


def test_prediction():
    """测试预测性能"""
    print("\n=== 预测性能测试 ===")
    start_time = time.time()
    
    async def run_prediction():
        orchestrator = PL5Orchestrator()
        result = await orchestrator.execute_prediction_pipeline()
        orchestrator.shutdown()
        return result
    
    result = asyncio.run(run_prediction())
    execution_time = time.time() - start_time
    
    if result['success']:
        print(f"预测完成，期号: {result['next_period']}")
        print(f"预测耗时: {execution_time:.2f}秒")
    else:
        print(f"预测失败: {result['error']}")
    
    return execution_time, result['success']


def test_full_training():
    """测试完整训练流程性能"""
    print("\n=== 完整训练流程测试 ===")
    start_time = time.time()
    
    async def run_training():
        orchestrator = PL5Orchestrator()
        result = await orchestrator.execute_training_pipeline()
        orchestrator.shutdown()
        return result
    
    result = asyncio.run(run_training())
    execution_time = time.time() - start_time
    
    if result['success']:
        accuracy = result['results']['model_evaluation']['evaluation']['overall_accuracy']
        print(f"训练完成，准确率: {accuracy:.4f}")
        print(f"训练总耗时: {execution_time:.2f}秒")
    else:
        print(f"训练失败: {result['error']}")
    
    return execution_time, result['success'], result.get('results', {}).get('model_evaluation', {}).get('evaluation', {}).get('overall_accuracy', 0)


def analyze_model_files():
    """分析模型文件大小"""
    print("\n=== 模型文件分析 ===")
    models_dir = "models"
    if os.path.exists(models_dir):
        for file in os.listdir(models_dir):
            if file.endswith('.pkl'):
                file_path = os.path.join(models_dir, file)
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"{file}: {size_mb:.2f} MB")


def main():
    """主函数"""
    print("PL5系统简单性能测试")
    print("=" * 60)
    
    # 测试数据采集
    data_time, record_count = test_data_collection()
    
    # 重新获取数据用于后续测试
    collector = PL5DataCollector()
    df = collector.update_data()
    
    # 测试特征工程
    feature_time, feature_count, df_features, feature_cols = test_feature_engineering(df)
    
    # 测试模型训练
    train_time = test_model_training(df_features, feature_cols)
    
    # 测试预测
    predict_time, predict_success = test_prediction()
    
    # 测试完整训练流程
    full_train_time, train_success, accuracy = test_full_training()
    
    # 分析模型文件
    analyze_model_files()
    
    print("\n" + "=" * 60)
    print("性能测试结果汇总")
    print("=" * 60)
    print(f"数据采集: {data_time:.2f}秒, {record_count}条记录")
    print(f"特征工程: {feature_time:.2f}秒, {feature_count}个特征")
    print(f"模型训练: {train_time:.2f}秒")
    print(f"预测: {predict_time:.2f}秒, {'成功' if predict_success else '失败'}")
    print(f"完整训练: {full_train_time:.2f}秒, 准确率: {accuracy:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
