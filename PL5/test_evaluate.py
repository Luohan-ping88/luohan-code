#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单评估脚本
"""

import numpy as np
import pandas as pd
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import ModelConfig
from src.core.features.engineer import FeatureEngineerV9
from src.core.data.collector import PL5DataCollector

def evaluate_model(model, test_features, feature_cols, top_k=8):
    """评估模型性能
    
    Args:
        model: 训练好的模型
        test_features: 测试特征
        feature_cols: 特征列
        top_k: 预测的数字数量
        
    Returns:
        dict: 评估结果
    """
    results = {}
    all_metrics = []
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    
    for pos in positions:
        pos_metrics = []
        
        for i, row in test_features.iterrows():
            # 提取特征
            features = row[feature_cols].values.astype(float)
            
            # 提取最近的原始数据
            recent_data = {}
            for p in positions:
                recent_data[p] = test_features[p].iloc[max(0, i-10):i].values
            
            # 预测
            prediction = model.predict(features, recent_data, top_k=top_k)
            predicted = prediction[pos]['top_k']
            actual = row[pos]
            
            # 计算命中
            hit = actual in predicted
            pos_metrics.append(hit)
            all_metrics.append(hit)
        
        # 计算位置级别的统计
        pos_stats = {
            'hit_rate': np.mean(pos_metrics),
            'total_predictions': len(pos_metrics),
            'total_hits': sum(pos_metrics)
        }
        
        results[pos] = pos_stats
    
    # 计算整体统计
    overall_stats = {
        'hit_rate': np.mean(all_metrics),
        'total_predictions': len(all_metrics),
        'total_hits': sum(all_metrics)
    }
    
    results['overall'] = overall_stats
    return results

def evaluate_random_guess(test_data, positions=['wan', 'qian', 'bai', 'shi', 'ge'], top_k=8):
    """评估随机猜测的性能
    
    Args:
        test_data: 测试数据
        positions: 要评估的位置
        top_k: 预测的数字数量
        
    Returns:
        dict: 随机猜测的评估结果
    """
    results = {}
    all_metrics = []
    
    for pos in positions:
        pos_metrics = []
        
        for i, row in test_data.iterrows():
            # 随机生成8个数字
            predicted = np.random.choice(range(10), size=top_k, replace=False).tolist()
            actual = row[pos]
            
            # 计算命中
            hit = actual in predicted
            pos_metrics.append(hit)
            all_metrics.append(hit)
        
        # 计算位置级别的统计
        pos_stats = {
            'hit_rate': np.mean(pos_metrics),
            'total_predictions': len(pos_metrics),
            'total_hits': sum(pos_metrics)
        }
        
        results[pos] = pos_stats
    
    # 计算整体统计
    overall_stats = {
        'hit_rate': np.mean(all_metrics),
        'total_predictions': len(all_metrics),
        'total_hits': sum(all_metrics)
    }
    
    results['overall'] = overall_stats
    return results

def main():
    """主函数"""
    print("开始评估模型性能...")
    
    # 加载数据
    print("1. 加载数据...")
    collector = PL5DataCollector()
    data = collector.load_processed_data()
    
    # 划分训练集和测试集（使用最近的50期作为测试集）
    test_size = 50
    train_data = data.iloc[:-test_size]
    test_data = data.iloc[-test_size:]
    
    # 只使用最近的1000期作为训练集，加快训练速度
    train_data = train_data.iloc[-1000:]
    
    print(f"训练集大小: {len(train_data)}")
    print(f"测试集大小: {len(test_data)}")
    
    # 生成特征
    print("2. 生成特征...")
    engineer = FeatureEngineerV9(enable_parallel=False)
    
    # 生成训练集特征
    train_features = engineer.extract_all_features(train_data, select_top=None, detect_drift=False, enable_scaler=False)
    feature_cols = [col for col in train_features.columns if col not in ['date', 'wan', 'qian', 'bai', 'shi', 'ge']]
    
    # 生成测试集特征
    test_features = engineer.extract_all_features(test_data, select_top=None, detect_drift=False, enable_scaler=False)
    
    print(f"特征数量: {len(feature_cols)}")
    
    # 训练模型
    print("3. 训练模型...")
    model_config = ModelConfig()
    model = EnhancedPL5Predictor(model_config)
    
    print(f"训练前 - is_trained: {model.is_trained}")
    
    try:
        model.fit(train_features, feature_cols=feature_cols)
        print(f"训练后 - is_trained: {model.is_trained}")
    except Exception as e:
        print(f"训练失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 评估模型
    print("4. 评估模型...")
    model_results = evaluate_model(model, test_features, feature_cols)
    
    # 评估随机猜测
    print("5. 评估随机猜测...")
    random_results = evaluate_random_guess(test_features)
    
    # 打印结果
    print("6. 评估结果...")
    print("\n模型性能:")
    print(f"整体命中率: {model_results['overall']['hit_rate']:.4f}")
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        print(f"{pos}位命中率: {model_results[pos]['hit_rate']:.4f}")
    
    print("\n随机猜测性能:")
    print(f"整体命中率: {random_results['overall']['hit_rate']:.4f}")
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        print(f"{pos}位命中率: {random_results[pos]['hit_rate']:.4f}")
    
    print("\n评估完成！")

if __name__ == "__main__":
    main()
