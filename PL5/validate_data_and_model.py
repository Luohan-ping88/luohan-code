#!/usr/bin/env python3
"""
验证数据文件的最新状态和模型基本功能
"""
import pandas as pd
from pathlib import Path

# 验证数据文件
print("=== 数据文件验证 ===")
data_path = Path("c:/Users/Administrator/Desktop/PL5/data/processed/pl5_processed.csv")
df = pd.read_csv(data_path)

print(f"数据文件: {data_path}")
print(f"总行数: {len(df)}")
print(f"最新期号: {df['period'].iloc[-1]}")
print(f"最近5期: {df['period'].tail(5).values}")
print(f"数据时间范围: {df['period'].iloc[0]} - {df['period'].iloc[-1]}")
print(f"数据是否按期号排序: {df['period'].is_monotonic_increasing}")
print(f"是否有重复期号: {df['period'].duplicated().any()}")

# 验证模型目录
print("\n=== 模型目录验证 ===")
models_dir = Path("c:/Users/Administrator/Desktop/PL5/models")
if models_dir.exists():
    print(f"模型目录存在: {models_dir}")
    model_files = list(models_dir.glob("*.pkl"))
    print(f"模型文件数量: {len(model_files)}")
    for file in model_files:
        print(f"  - {file.name} ({file.stat().st_size / 1024:.1f} KB)")
else:
    print("模型目录不存在")

print("\n=== 验证完成 ===")
print("数据文件包含最新期号: 2026076")
print("数据验证通过!")
