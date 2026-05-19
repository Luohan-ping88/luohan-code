#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查数据获取状态"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("检查数据获取状态")
print("=" * 80)

# 检查数据文件
print("\n[1] 检查数据文件...")
processed_data = Path("data/processed/pl5_processed.csv")
raw_data = Path("data/raw/pl5_data.csv")

if processed_data.exists():
    print(f"✓ 处理后数据存在: {processed_data}")
    print(f"  文件大小: {processed_data.stat().st_size / 1024:.2f} KB")
    print(f"  最后修改: {processed_data.stat().st_mtime}")
else:
    print(f"✗ 处理后数据不存在")

if raw_data.exists():
    print(f"\n✓ 原始数据存在: {raw_data}")
    print(f"  文件大小: {raw_data.stat().st_size / 1024:.2f} KB")
    print(f"  最后修改: {raw_data.stat().st_mtime}")
else:
    print(f"\n✗ 原始数据不存在")

# 查看数据内容
print("\n[2] 加载并检查数据...")
try:
    from src.core.data.collector import PL5DataCollector
    collector = PL5DataCollector()
    df = collector.load_processed_data()
    
    if df is not None and len(df) > 0:
        print(f"\n✓ 数据加载成功")
        print(f"  记录数: {len(df)}")
        print(f"  列数: {len(df.columns)}")
        print(f"  列名: {list(df.columns)}")
        print(f"\n  最新5条记录:")
        print(df.tail())
        
        if 'period' in df.columns:
            latest_period = df['period'].iloc[-1]
            print(f"\n  最新期号: {latest_period}")
            print(f"  预测期号: {int(latest_period) + 1}")
            
            # 检查日期
            if 'date' in df.columns:
                latest_date = df['date'].iloc[-1]
                print(f"  最新日期: {latest_date}")
    else:
        print("\n✗ 无数据或数据为空")
        
except Exception as e:
    print(f"\n✗ 数据加载失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)
