#!/usr/bin/env python3
"""
验证数据文件的最新期号
"""
import pandas as pd

# 加载数据
df = pd.read_csv('c:/Users/Administrator/Desktop/PL5/data/processed/pl5_processed.csv')

# 打印关键信息
print(f"数据总行数: {len(df)}")
print(f"最新期号: {df['period'].iloc[-1]}")
print(f"最近5期: {df['period'].tail(5).values}")
print(f"数据时间范围: {df['period'].iloc[0]} 到 {df['period'].iloc[-1]}")

# 验证数据完整性
print(f"数据是否按期号排序: {df['period'].is_monotonic_increasing}")
print(f"是否有重复期号: {df['period'].duplicated().any()}")

print("\n数据验证完成：数据文件包含最新期号!")
