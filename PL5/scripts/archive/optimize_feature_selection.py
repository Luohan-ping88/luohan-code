#!/usr/bin/env python3
"""
特征选择优化脚本
分析新添加的排列五特定特征的重要性，并优化特征选择方法
"""

import pandas as pd
import numpy as np
import pickle
import os
from src.core.features.engineer import FeatureEngineerV9, FeatureImportanceAnalyzer
from src.core.data.collector import PL5DataCollector

# 加载数据
def load_data():
    """加载排列五数据"""
    collector = PL5DataCollector()
    df = collector.load_processed_data()
    return df

# 生成特征
def generate_features(df):
    """生成所有特征"""
    engineer = FeatureEngineerV9()
    df_features = engineer.extract_all_features(df, select_top=None, feature_selection_method='rfe', enable_scaler=False, detect_drift=False)
    return df_features, engineer

# 分析新特征的重要性
def analyze_new_features_importance(df):
    """分析新添加的排列五特定特征的重要性"""
    print("\n=== 分析新添加的排列五特定特征的重要性 ===")
    
    # 对每个位置分析特征重要性
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    importance_analyzer = FeatureImportanceAnalyzer()
    
    for pos in positions:
        print(f"\n分析位置 {pos} 的特征重要性:")
        
        # 准备特征和目标
        feature_cols = [col for col in df.columns if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']]
        # 只选择数值类型的特征
        numeric_feature_cols = []
        for col in feature_cols:
            try:
                # 尝试转换为数值类型
                df[col].astype(float)
                numeric_feature_cols.append(col)
            except:
                pass
        
        # 分离排列五特定特征
        pl5_specific_features = [col for col in numeric_feature_cols if 'freq_' in col or 'last_' in col or 'corr' in col or 'consecutive' in col or 'repeat' in col]
        other_features = [col for col in numeric_feature_cols if col not in pl5_specific_features]
        
        print(f"排列五特定特征数量: {len(pl5_specific_features)}")
        print(f"其他特征数量: {len(other_features)}")
        
        X = df[numeric_feature_cols].fillna(0)
        y = df[pos].values
        
        # 计算特征重要性
        importance = importance_analyzer.calculate_importance(X, y, method='random_forest')
        
        # 输出前20个最重要的特征
        print(f"前20个最重要的特征:")
        for i, (feature, score) in enumerate(list(importance.items())[:20]):
            print(f"{i+1}. {feature}: {score:.4f}")
        
        # 分析排列五特定特征的重要性
        print(f"\n排列五特定特征的重要性:")
        pl5_importance = {k: v for k, v in importance.items() if k in pl5_specific_features}
        sorted_pl5_importance = sorted(pl5_importance.items(), key=lambda x: x[1], reverse=True)
        for i, (feature, score) in enumerate(sorted_pl5_importance[:10]):
            print(f"{i+1}. {feature}: {score:.4f}")

# 优化特征选择方法
def optimize_feature_selection(df):
    """优化特征选择方法"""
    print("\n=== 优化特征选择方法 ===")
    
    # 对每个位置优化特征选择
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    importance_analyzer = FeatureImportanceAnalyzer()
    
    for pos in positions:
        print(f"\n优化位置 {pos} 的特征选择:")
        
        # 准备特征和目标
        feature_cols = [col for col in df.columns if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']]
        # 只选择数值类型的特征
        numeric_feature_cols = []
        for col in feature_cols:
            try:
                # 尝试转换为数值类型
                df[col].astype(float)
                numeric_feature_cols.append(col)
            except:
                pass
        
        X = df[numeric_feature_cols].fillna(0)
        y = df[pos].values
        
        # 计算特征重要性
        importance = importance_analyzer.calculate_importance(X, y, method='random_forest')
        
        # 选择最重要的特征
        n_features = min(75, len(importance))  # 控制特征数量在50-100之间
        selected_features = importance_analyzer.select_top_features(n_features=n_features, threshold=0.001)
        
        print(f"选择了 {len(selected_features)} 个特征")
        print(f"前10个选择的特征:")
        for i, feature in enumerate(selected_features[:10]):
            print(f"{i+1}. {feature}: {importance[feature]:.4f}")
        
        # 保存选择的特征
        import os
        os.makedirs('analysis', exist_ok=True)
        with open(f'analysis/selected_features_{pos}.pkl', 'wb') as f:
            pickle.dump(selected_features, f)
        print(f"选择的特征已保存到 analysis/selected_features_{pos}.pkl")

# 主函数
def main():
    print("开始优化特征选择方法...")
    
    # 加载数据
    print("1. 加载数据...")
    df = load_data()
    print(f"数据加载完成，共 {len(df)} 条记录")
    
    # 生成特征
    print("2. 生成特征...")
    df_features, engineer = generate_features(df)
    print(f"特征生成完成，共 {df_features.shape[1]} 列")
    
    # 分析新特征的重要性
    print("3. 分析新添加的排列五特定特征的重要性...")
    analyze_new_features_importance(df_features)
    
    # 优化特征选择方法
    print("4. 优化特征选择方法...")
    optimize_feature_selection(df_features)
    
    print("\n特征选择优化完成！")

if __name__ == "__main__":
    main()
