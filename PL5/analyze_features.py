#!/usr/bin/env python3
"""
特征分析脚本
分析现有特征的有效性，生成特征重要性报告
"""

import pandas as pd
import numpy as np
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

# 分析特征重要性
def analyze_feature_importance(df, engineer):
    """分析特征重要性"""
    print("\n=== 分析特征重要性 ===")
    
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
        X = df[numeric_feature_cols].fillna(0)
        y = df[pos].values
        
        # 计算特征重要性
        importance = importance_analyzer.calculate_importance(X, y, method='random_forest')
        
        # 输出前20个最重要的特征
        print(f"前20个最重要的特征:")
        for i, (feature, score) in enumerate(list(importance.items())[:20]):
            print(f"{i+1}. {feature}: {score:.4f}")
        
        # 保存特征重要性
        import pickle
        import os
        os.makedirs('analysis', exist_ok=True)
        with open(f'analysis/feature_importance_{pos}.pkl', 'wb') as f:
            pickle.dump(importance, f)
        print(f"特征重要性已保存到 analysis/feature_importance_{pos}.pkl")

# 分析特征相关性
def analyze_feature_correlation(df):
    """分析特征相关性"""
    print("\n=== 分析特征相关性 ===")
    
    # 选择特征列
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
    
    # 计算相关性矩阵
    corr_matrix = X.corr()
    
    # 找出高度相关的特征对
    high_corr_pairs = []
    threshold = 0.9
    
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            if abs(corr_matrix.iloc[i, j]) > threshold:
                high_corr_pairs.append((corr_matrix.columns[i], corr_matrix.columns[j], corr_matrix.iloc[i, j]))
    
    print(f"找到 {len(high_corr_pairs)} 对高度相关的特征 (相关性 > {threshold}):")
    for feat1, feat2, corr in high_corr_pairs[:20]:  # 只显示前20对
        print(f"{feat1} 与 {feat2}: {corr:.4f}")
    
    # 保存相关性矩阵
    import pickle
    import os
    os.makedirs('analysis', exist_ok=True)
    with open('analysis/feature_correlation.pkl', 'wb') as f:
        pickle.dump(corr_matrix, f)
    print("\n特征相关性矩阵已保存到 analysis/feature_correlation.pkl")

# 主函数
def main():
    print("开始分析现有特征的有效性...")
    
    # 加载数据
    print("1. 加载数据...")
    df = load_data()
    print(f"数据加载完成，共 {len(df)} 条记录")
    
    # 生成特征
    print("2. 生成特征...")
    df_features, engineer = generate_features(df)
    print(f"特征生成完成，共 {df_features.shape[1]} 列")
    
    # 分析特征重要性
    print("3. 分析特征重要性...")
    analyze_feature_importance(df_features, engineer)
    
    # 分析特征相关性
    print("4. 分析特征相关性...")
    analyze_feature_correlation(df_features)
    
    print("\n特征分析完成！")

if __name__ == "__main__":
    main()
