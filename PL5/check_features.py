#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer

print("加载数据...")
collector = PL5DataCollector()
df = collector.update_data()
print(f"原始数据列: {list(df.columns)}")

print("\n运行特征工程...")
engineer = FeatureEngineer()
df_features = engineer.extract_all_features(df, select_top=None)
print(f"特征数据列数: {len(df_features.columns)}")

# 检查字符串类型的列
string_cols = []
for col in df_features.columns:
    if df_features[col].dtype == 'object':
        string_cols.append(col)
        print(f"字符串列: {col}, 样本值: {df_features[col].iloc[0] if len(df_features) > 0 else 'N/A'}")

print(f"\n找到 {len(string_cols)} 个字符串列")
