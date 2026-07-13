#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小化评估脚本
"""

import numpy as np
import pandas as pd
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import ModelConfig

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
                recent_data[p] = test_features[p].iloc[max(0, i-3):i].values
            
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

def main():
    """主函数"""
    print("开始评估模型性能...")
    
    # 创建非常简单的训练数据
    print("1. 创建简单的训练数据...")
    # 只创建100条数据
    n_samples = 100
    wan = np.random.randint(0, 10, n_samples)
    qian = np.random.randint(0, 10, n_samples)
    bai = np.random.randint(0, 10, n_samples)
    shi = np.random.randint(0, 10, n_samples)
    ge = np.random.randint(0, 10, n_samples)
    
    # 创建特征（只使用3个特征）
    features = np.random.rand(n_samples, 3)
    
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
    
    # 划分训练集和测试集
    test_size = 20
    train_data = data.iloc[:-test_size]
    test_data = data.iloc[-test_size:]
    
    feature_cols = [f'feature_{i}' for i in range(3)]
    
    print(f"训练集大小: {len(train_data)}")
    print(f"测试集大小: {len(test_data)}")
    print(f"特征数量: {len(feature_cols)}")
    
    # 训练模型
    print("2. 训练模型...")
    model_config = ModelConfig()
    model = EnhancedPL5Predictor(model_config)
    
    print(f"训练前 - is_trained: {model.is_trained}")
    
    try:
        model.fit(train_data, feature_cols=feature_cols)
        print(f"训练后 - is_trained: {model.is_trained}")
    except Exception as e:
        print(f"训练失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 评估模型
    print("3. 评估模型...")
    model_results = evaluate_model(model, test_data, feature_cols)
    
    # 打印结果
    print("4. 评估结果...")
    print("\n模型性能:")
    print(f"整体命中率: {model_results['overall']['hit_rate']:.4f}")
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        print(f"{pos}位命中率: {model_results[pos]['hit_rate']:.4f}")
    
    print("\n评估完成！")

if __name__ == "__main__":
    main()
