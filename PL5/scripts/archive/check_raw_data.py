#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查原始数据并重新更新"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("检查原始数据并重新更新")
print("=" * 80)

# 1. 检查原始数据
print("\n[1] 检查原始数据...")
raw_data_path = Path("data/raw/pl5_history.txt")

if raw_data_path.exists():
    with open(raw_data_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"✓ 原始数据存在")
    print(f"  总行数: {len(lines)}")
    
    # 查找最后有效数据
    last_valid_line = None
    for line in reversed(lines):
        line = line.strip()
        if line:
            last_valid_line = line
            break
    
    if last_valid_line:
        print(f"\n  最后一行原始数据: {last_valid_line}")
        parts = last_valid_line.split()
        if len(parts) >= 8:
            print(f"  期号: {parts[0]}")
            print(f"  日期: {parts[1]}")
            print(f"  号码: {parts[2]}{parts[3]}{parts[4]}{parts[5]}{parts[6]}")
else:
    print("✗ 原始数据不存在")
    sys.exit(1)

# 2. 重新更新数据
print("\n[2] 重新更新数据...")
try:
    from src.core.data.collector import PL5DataCollector
    collector = PL5DataCollector()
    
    # 解析原始数据
    print("  解析原始数据...")
    records = collector.parse_raw_data()
    print(f"✓ 解析完成: {len(records)} 条记录")
    
    # 保存处理后的数据
    print("  保存处理后的数据...")
    import pandas as pd
    df = pd.DataFrame(records)
    
    # 重新排序列
    new_columns = ['period', 'date', 'wan', 'qian', 'bai', 'shi', 'ge', 'full_number', 'parse_line']
    df = df[new_columns]
    
    processed_path = Path("data/processed/pl5_processed.csv")
    df.to_csv(processed_path, index=False, encoding='utf-8')
    print(f"✓ 数据已保存到: {processed_path}")
    
    print(f"\n  最新5条记录:")
    print(df.tail())
    
    print(f"\n  总记录数: {len(df)}")
    print(f"  最新期号: {df['period'].iloc[-1]}")
    print(f"  最新日期: {df['date'].iloc[-1]}")
    
except Exception as e:
    print(f"✗ 更新失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("完成")
print("=" * 80)
