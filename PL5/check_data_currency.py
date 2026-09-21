#!/usr/bin/env python3
"""
检查数据文件的最新期号
"""
import os
import pandas as pd
from pathlib import Path

# 基于脚本位置解析项目根目录（跨平台，兼容 Windows/Linux）
PROJECT_ROOT = Path(__file__).resolve().parent

# 加载数据
data_path = PROJECT_ROOT / "data" / "processed" / "pl5_processed.csv"
df = pd.read_csv(data_path)

# 打印数据信息
print(f"数据文件: {data_path}")
print(f"总行数: {len(df)}")
print(f"最新期号: {df['period'].iloc[-1]}")
print(f"最近5期: {df['period'].tail(5).values}")
print(f"最早期号: {df['period'].iloc[0]}")
print(f"数据时间范围: {df['period'].iloc[0]} - {df['period'].iloc[-1]}")

# 检查数据是否按期号排序
is_sorted = df['period'].is_monotonic_increasing
print(f"数据是否按期号排序: {is_sorted}")

# 检查是否有重复的期号
has_duplicates = df['period'].duplicated().any()
print(f"是否有重复的期号: {has_duplicates}")

print("\n数据检查完成!")
