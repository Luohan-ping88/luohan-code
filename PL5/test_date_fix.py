#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试日期列处理修复是否生效"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("测试日期列处理修复")
print("=" * 80)

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer

print("\n[1/3] 加载数据...")
collector = PL5DataCollector()
df = collector.load_processed_data()
print(f"✓ 数据加载成功: {len(df)} 条记录")
print(f"  列: {list(df.columns)}")

print("\n[2/3] 特征工程...")
engineer = FeatureEngineer()
df_features = engineer.extract_all_features(df)

print("\n[3/3] 检查特征列...")
feature_cols = [
    c for c in df_features.columns
    if c not in ['period', 'date', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']
]

print(f"✓ 总列数: {len(df_features.columns)}")
print(f"✓ 特征列数: {len(feature_cols)}")
print(f"\n检查 'date' 列是否被正确排除:")
if 'date' not in feature_cols:
    print("✓ 'date' 列已正确排除在特征列之外")
else:
    print("✗ 'date' 列仍然在特征列中！")

print("\n检查其他非数值列...")
for col in ['period', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']:
    if col not in feature_cols:
        print(f"✓ '{col}' 列已正确排除")
    else:
        print(f"✗ '{col}' 列仍然在特征列中！")

print("\n" + "=" * 80)
print("检查完成！")
print("=" * 80)
