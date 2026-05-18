#!/usr/bin/env python3
"""
检查特征工程结果，找出包含字符串/日期的列
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer

print("开始加载数据...")
collector = PL5DataCollector()
df = collector.update_data()

print(f"数据加载完成，共 {len(df)} 条记录")

print("\n开始特征工程...")
engineer = FeatureEngineer()
df_features = engineer.extract_all_features(df, select_top=None)

print(f"\n特征工程完成，共 {len(df_features.columns)} 列")

print("\n查找非数值类型的列...")
non_numeric_cols = []
for col in df_features.columns:
    dtype = str(df_features[col].dtype)
    if dtype == 'object' or 'datetime' in dtype:
        non_numeric_cols.append((col, dtype))
        # 查看该列的前几个值
        sample = df_features[col].dropna().head(5)
        print(f"\n列名: {col}, 类型: {dtype}")
        print(f"样本值: {list(sample)}")

print(f"\n找到 {len(non_numeric_cols)} 个非数值列")

print("\n打印所有列及其类型...")
for col in df_features.columns:
    print(f"{col}: {df_features[col].dtype}")
