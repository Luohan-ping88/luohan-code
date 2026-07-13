#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重新获取最新数据"""

import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("更新最新数据")
print("=" * 80)

# 1. 显示当前数据状态
print(f"\n[1] 当前数据状态")
try:
    from src.core.data.collector import PL5DataCollector
    collector = PL5DataCollector()
    df = collector.load_processed_data()
    
    if df is not None and len(df) > 0:
        print(f"✓ 当前记录数: {len(df)}")
        if 'period' in df.columns:
            print(f"✓ 最新期号: {df['period'].iloc[-1]}")
        if 'date' in df.columns:
            print(f"✓ 最新日期: {df['date'].iloc[-1]}")
        print(f"\n最新5条记录:")
        print(df.tail())
    else:
        print("✗ 无数据")
        
except Exception as e:
    print(f"✗ 检查数据失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 尝试更新数据
print(f"\n[2] 尝试从数据源更新")
print("  注意：之前遇到HTTP 429错误，可能需要等待...")

try:
    # 先等待一下
    print("\n等待5秒避免请求过快...")
    time.sleep(5)
    
    print("\n开始更新数据...")
    new_df = collector.update_data()
    
    if new_df is not None and len(new_df) > 0:
        print(f"\n✓ 数据更新成功!")
        print(f"✓ 新记录数: {len(new_df)}")
        if 'period' in new_df.columns:
            print(f"✓ 最新期号: {new_df['period'].iloc[-1]}")
        if 'date' in new_df.columns:
            print(f"✓ 最新日期: {new_df['date'].iloc[-1]}")
        
        print(f"\n最新5条记录:")
        print(new_df.tail())
        
        # 检查是否有新期号
        if df is not None and len(df) > 0:
            old_latest = df['period'].iloc[-1]
            new_latest = new_df['period'].iloc[-1]
            if str(old_latest) != str(new_latest):
                print(f"\n✅ 发现新数据! 从 {old_latest} 更新到 {new_latest}")
                added_count = len(new_df) - len(df)
                print(f"   新增 {added_count} 条记录")
            else:
                print(f"\n⚠️  数据已是最新，没有新期号")
    else:
        print(f"\n✗ 更新失败，返回空数据")
        
except Exception as e:
    print(f"\n✗ 更新数据失败: {e}")
    import traceback
    traceback.print_exc()
    
    print(f"\n[3] 提示: 如果遇到HTTP 429错误")
    print("    1. 可以稍后再试")
    print("    2. 或者检查数据源是否有其他访问方式")

print("\n" + "=" * 80)
print("完成")
print("=" * 80)
