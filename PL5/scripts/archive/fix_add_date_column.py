#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""为现有处理后的数据添加日期列"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("修复数据 - 添加日期列")
print("=" * 80)

# 1. 读取原始数据，获取日期映射
raw_data_path = Path("data/raw/pl5_history.txt")
processed_data_path = Path("data/processed/pl5_processed.csv")

print(f"\n[1] 读取原始数据: {raw_data_path}")
if not raw_data_path.exists():
    print("✗ 原始数据文件不存在")
    sys.exit(1)

with open(raw_data_path, 'r', encoding='utf-8') as f:
    raw_lines = f.readlines()

# 构建期号到日期的映射
period_to_date = {}
for line in raw_lines:
    line = line.strip()
    if not line:
        continue
    parts = line.split()
    if len(parts) >= 2:
        period = parts[0].strip()
        date = parts[1].strip()
        period_to_date[period] = date

print(f"✓ 从原始数据获取 {len(period_to_date)} 个期号的日期映射")
print(f"  示例: {list(period_to_date.items())[:5]}")

# 2. 读取处理后的数据
print(f"\n[2] 读取处理后的数据: {processed_data_path}")
if not processed_data_path.exists():
    print("✗ 处理后的数据文件不存在")
    sys.exit(1)

df = pd.read_csv(processed_data_path, encoding='utf-8')
print(f"✓ 读取成功，共 {len(df)} 条记录")
print(f"  当前列: {list(df.columns)}")

# 3. 检查是否已有date列
if 'date' in df.columns:
    print("✓ date列已存在，无需添加")
    # 检查date列是否有值
    if df['date'].isnull().all():
        print("  但date列全为空，需要填充")
    else:
        print("  date列已有数据，跳过")
        sys.exit(0)

# 4. 添加或填充date列
print(f"\n[3] 添加/填充date列")
if 'date' not in df.columns:
    df['date'] = ''

# 用映射填充date列
filled_count = 0
for idx, row in df.iterrows():
    period = str(row['period'])
    if period in period_to_date:
        df.at[idx, 'date'] = period_to_date[period]
        filled_count += 1

print(f"✓ 成功填充 {filled_count} 条记录的日期")

# 5. 重新排序列，确保date在period后面
print(f"\n[4] 重新排列列顺序")
new_columns = []
for col in df.columns:
    if col == 'period':
        new_columns.append('period')
        new_columns.append('date')
    elif col != 'date':
        new_columns.append(col)

df = df[new_columns]
print(f"✓ 新列顺序: {list(df.columns)}")

# 6. 保存备份
print(f"\n[5] 保存备份")
backup_path = processed_data_path.parent / f"{processed_data_path.stem}_backup_before_date.csv"
df.to_csv(backup_path, index=False, encoding='utf-8')
print(f"✓ 备份已保存到: {backup_path}")

# 7. 保存处理后的数据
print(f"\n[6] 保存处理后的数据")
df.to_csv(processed_data_path, index=False, encoding='utf-8')
print(f"✓ 数据已保存到: {processed_data_path}")

# 8. 显示结果
print(f"\n[7] 验证结果")
print(f"  记录数: {len(df)}")
print(f"  列数: {len(df.columns)}")
print(f"  列名: {list(df.columns)}")
print(f"\n  前5条记录:")
print(df.head())
print(f"\n  后5条记录:")
print(df.tail())

print("\n" + "=" * 80)
print("完成！")
print("=" * 80)
