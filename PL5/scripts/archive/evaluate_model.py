#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型评估脚本 - 全面评估排列五预测模型性能

功能：
1. 加载训练好的模型
2. 使用测试数据评估模型性能
3. 计算各种评估指标
4. 与随机猜测进行比较
5. 生成详细的评估报告
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.features.engineer import FeatureEngineer
from src.core.data.collector import PL5DataCollector
from src.core.config import ModelConfig

# 评估指标计算函数
def calculate_metrics(predicted, actual, top_k=8):
    """计算评估指标
    
    Args:
        predicted: 预测的数字列表（前top_k个）
        actual: 实际数字
        top_k: 预测的数字数量
        
    Returns:
        dict: 评估指标
    """
    # 命中率：实际数字是否在预测列表中
    hit = actual in predicted
    
    # 位置命中率：实际数字在预测列表中的位置
    position = predicted.index(actual) + 1 if hit else top_k + 1
    
    # 前3命中率
    top_3_hit = actual in predicted[:3]
    
    # 前5命中率
    top_5_hit = actual in predicted[:5]
    
    # 平均排名
    avg_rank = position if hit else top_k + 1
    
    # 精度
    precision = 1.0 if hit else 0.0
    
    # 召回率
    recall = 1.0 if hit else 0.0
    
    # F1分数
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        'hit': hit,
        'top_3_hit': top_3_hit,
        'top_5_hit': top_5_hit,
        'position': position,
        'avg_rank': avg_rank,
        'precision': precision,
        'recall': recall,
        'f1': f1
    }

def evaluate_model(model, test_data, feature_cols, positions=['wan', 'qian', 'bai', 'shi', 'ge'], top_k=8):
    """评估模型性能
    
    Args:
        model: 训练好的模型
        test_data: 测试数据
        feature_cols: 特征列
        positions: 要评估的位置
        top_k: 预测的数字数量
        
    Returns:
        dict: 评估结果
    """
    results = {}
    all_metrics = []
    
    for pos in positions:
        pos_metrics = []
        
        for i, row in test_data.iterrows():
            # 提取特征
            features = row[feature_cols].values.astype(float)
            
            # 提取最近的原始数据
            recent_data = {}
            for p in positions:
                recent_data[p] = test_data[p].iloc[max(0, i-10):i].values
            
            # 预测
            prediction = model.predict(features, recent_data, top_k=top_k)
            predicted = prediction[pos]['top_k']
            actual = row[pos]
            
            # 计算指标
            metrics = calculate_metrics(predicted, actual, top_k)
            pos_metrics.append(metrics)
            all_metrics.append(metrics)
        
        # 计算位置级别的统计
        pos_stats = {
            'hit_rate': np.mean([m['hit'] for m in pos_metrics]),
            'top_3_hit_rate': np.mean([m['top_3_hit'] for m in pos_metrics]),
            'top_5_hit_rate': np.mean([m['top_5_hit'] for m in pos_metrics]),
            'avg_position': np.mean([m['position'] for m in pos_metrics]),
            'avg_rank': np.mean([m['avg_rank'] for m in pos_metrics]),
            'avg_precision': np.mean([m['precision'] for m in pos_metrics]),
            'avg_recall': np.mean([m['recall'] for m in pos_metrics]),
            'avg_f1': np.mean([m['f1'] for m in pos_metrics]),
            'total_predictions': len(pos_metrics),
            'total_hits': sum([m['hit'] for m in pos_metrics])
        }
        
        results[pos] = pos_stats
    
    # 计算整体统计
    overall_stats = {
        'hit_rate': np.mean([m['hit'] for m in all_metrics]),
        'top_3_hit_rate': np.mean([m['top_3_hit'] for m in all_metrics]),
        'top_5_hit_rate': np.mean([m['top_5_hit'] for m in all_metrics]),
        'avg_position': np.mean([m['position'] for m in all_metrics]),
        'avg_rank': np.mean([m['avg_rank'] for m in all_metrics]),
        'avg_precision': np.mean([m['precision'] for m in all_metrics]),
        'avg_recall': np.mean([m['recall'] for m in all_metrics]),
        'avg_f1': np.mean([m['f1'] for m in all_metrics]),
        'total_predictions': len(all_metrics),
        'total_hits': sum([m['hit'] for m in all_metrics])
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
            
            # 计算指标
            metrics = calculate_metrics(predicted, actual, top_k)
            pos_metrics.append(metrics)
            all_metrics.append(metrics)
        
        # 计算位置级别的统计
        pos_stats = {
            'hit_rate': np.mean([m['hit'] for m in pos_metrics]),
            'top_3_hit_rate': np.mean([m['top_3_hit'] for m in pos_metrics]),
            'top_5_hit_rate': np.mean([m['top_5_hit'] for m in pos_metrics]),
            'avg_position': np.mean([m['position'] for m in pos_metrics]),
            'avg_rank': np.mean([m['avg_rank'] for m in pos_metrics]),
            'avg_precision': np.mean([m['precision'] for m in pos_metrics]),
            'avg_recall': np.mean([m['recall'] for m in pos_metrics]),
            'avg_f1': np.mean([m['f1'] for m in pos_metrics]),
            'total_predictions': len(pos_metrics),
            'total_hits': sum([m['hit'] for m in pos_metrics])
        }
        
        results[pos] = pos_stats
    
    # 计算整体统计
    overall_stats = {
        'hit_rate': np.mean([m['hit'] for m in all_metrics]),
        'top_3_hit_rate': np.mean([m['top_3_hit'] for m in all_metrics]),
        'top_5_hit_rate': np.mean([m['top_5_hit'] for m in all_metrics]),
        'avg_position': np.mean([m['position'] for m in all_metrics]),
        'avg_rank': np.mean([m['avg_rank'] for m in all_metrics]),
        'avg_precision': np.mean([m['precision'] for m in all_metrics]),
        'avg_recall': np.mean([m['recall'] for m in all_metrics]),
        'avg_f1': np.mean([m['f1'] for m in all_metrics]),
        'total_predictions': len(all_metrics),
        'total_hits': sum([m['hit'] for m in all_metrics])
    }
    
    results['overall'] = overall_stats
    return results

def generate_report(model_results, random_results, output_dir='reports'):
    """生成评估报告
    
    Args:
        model_results: 模型评估结果
        random_results: 随机猜测评估结果
        output_dir: 报告输出目录
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成时间戳
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 生成文本报告
    report_path = os.path.join(output_dir, f'evaluation_report_{timestamp}.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"排列五预测模型评估报告\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n")
        
        # 整体性能
        f.write("\n整体性能对比:\n")
        f.write("-" * 60 + "\n")
        f.write(f"{'指标':<20} {'模型':<10} {'随机猜测':<10} {'提升':<10}\n")
        f.write("-" * 60 + "\n")
        
        metrics = ['hit_rate', 'top_3_hit_rate', 'top_5_hit_rate', 'avg_f1']
        metric_names = {'hit_rate': '命中率', 'top_3_hit_rate': '前3命中率', 'top_5_hit_rate': '前5命中率', 'avg_f1': 'F1分数'}
        
        for metric in metrics:
            model_value = model_results['overall'][metric]
            random_value = random_results['overall'][metric]
            improvement = (model_value - random_value) / random_value * 100 if random_value > 0 else float('inf')
            f.write(f"{metric_names[metric]:<20} {model_value:.4f}    {random_value:.4f}    {improvement:+.2f}%\n")
        
        # 各位置性能
        f.write("\n各位置性能:\n")
        f.write("-" * 60 + "\n")
        f.write(f"{'位置':<10} {'模型命中率':<12} {'随机命中率':<12} {'提升':<10}\n")
        f.write("-" * 60 + "\n")
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        position_names = {'wan': '万位', 'qian': '千位', 'bai': '百位', 'shi': '十位', 'ge': '个位'}
        
        for pos in positions:
            model_value = model_results[pos]['hit_rate']
            random_value = random_results[pos]['hit_rate']
            improvement = (model_value - random_value) / random_value * 100 if random_value > 0 else float('inf')
            f.write(f"{position_names[pos]:<10} {model_value:.4f}        {random_value:.4f}        {improvement:+.2f}%\n")
        
        # 详细统计
        f.write("\n详细统计:\n")
        f.write("-" * 60 + "\n")
        f.write(f"模型总预测次数: {model_results['overall']['total_predictions']}\n")
        f.write(f"模型总命中次数: {model_results['overall']['total_hits']}\n")
        f.write(f"随机总预测次数: {random_results['overall']['total_predictions']}\n")
        f.write(f"随机总命中次数: {random_results['overall']['total_hits']}\n")
    
    # 生成JSON报告
    json_path = os.path.join(output_dir, f'evaluation_results_{timestamp}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'model_results': model_results,
            'random_results': random_results,
            'timestamp': datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    print(f"评估报告已生成: {report_path}")
    print(f"评估结果已保存: {json_path}")

def plot_performance_comparison(model_results, random_results, output_dir='reports'):
    """绘制性能对比图
    
    Args:
        model_results: 模型评估结果
        random_results: 随机猜测评估结果
        output_dir: 图表输出目录
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成时间戳
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 准备数据
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    position_names = ['万位', '千位', '百位', '十位', '个位']
    
    model_hit_rates = [model_results[pos]['hit_rate'] for pos in positions]
    random_hit_rates = [random_results[pos]['hit_rate'] for pos in positions]
    
    # 绘制命中率对比图
    plt.figure(figsize=(12, 6))
    x = np.arange(len(positions))
    width = 0.35
    
    plt.bar(x - width/2, model_hit_rates, width, label='模型预测')
    plt.bar(x + width/2, random_hit_rates, width, label='随机猜测')
    
    plt.xlabel('位置')
    plt.ylabel('命中率')
    plt.title('各位置命中率对比')
    plt.xticks(x, position_names)
    plt.ylim(0, 1)
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    
    # 保存图表
    plot_path = os.path.join(output_dir, f'performance_comparison_{timestamp}.png')
    plt.savefig(plot_path)
    plt.close()
    
    print(f"性能对比图已生成: {plot_path}")

def main():
    """主函数"""
    print("开始评估模型性能...")
    
    # 加载数据
    print("1. 加载数据...")
    collector = PL5DataCollector()
    data = collector.load_processed_data()
    
    # 划分训练集和测试集（使用最近的100期作为测试集）
    test_size = 100
    train_data = data.iloc[:-test_size]
    test_data = data.iloc[-test_size:]
    
    print(f"训练集大小: {len(train_data)}")
    print(f"测试集大小: {len(test_data)}")
    
    # 生成特征
    print("2. 生成特征...")
    # 使用默认的FeatureEngineerV9
    from src.core.features.engineer import FeatureEngineerV9
    
    # 创建FeatureEngineerV9实例，禁用并行计算以避免脚本卡住
    engineer = FeatureEngineerV9(enable_parallel=False)
    
    # 生成训练集特征（禁用特征选择和漂移检测）
    train_features = engineer.extract_all_features(train_data, select_top=None, detect_drift=False, enable_scaler=False)
    feature_cols = [col for col in train_features.columns if col not in ['date', 'wan', 'qian', 'bai', 'shi', 'ge']]
    
    # 生成测试集特征（禁用特征选择和漂移检测）
    test_features = engineer.extract_all_features(test_data, select_top=None, detect_drift=False, enable_scaler=False)
    
    print(f"特征数量: {len(feature_cols)}")
    
    # 训练模型
    print("3. 训练模型...")
    model_config = ModelConfig()
    model = EnhancedPL5Predictor(model_config)
    model.fit(train_features, feature_cols=feature_cols)
    
    # 评估模型
    print("4. 评估模型...")
    model_results = evaluate_model(model, test_features, feature_cols)
    
    # 评估随机猜测
    print("5. 评估随机猜测...")
    random_results = evaluate_random_guess(test_features)
    
    # 生成报告
    print("6. 生成评估报告...")
    generate_report(model_results, random_results)
    
    # 绘制性能对比图
    print("7. 绘制性能对比图...")
    plot_performance_comparison(model_results, random_results)
    
    print("评估完成！")

if __name__ == "__main__":
    main()
