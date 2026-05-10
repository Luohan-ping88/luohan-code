#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试能否从网络获取最新数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.data.collector import PL5DataCollectorV8
from datetime import datetime

col = PL5DataCollectorV8()

print("=" * 60)
print("测试从网络获取最新 PL5 数据")
print("=" * 60)
print()

current_latest = col.get_latest_period()
print(f"当前本地最新期号: {current_latest}")
print(f"当前本地数据总量: {len(col.load_local_data())} 条")
print()

print("尝试从网络获取最新数据...")
print("-" * 60)

try:
    # 调用 update_data 方法（会自动联网并合并到本地）
    updated_df = col.update_data()
    
    if updated_df is not None and not updated_df.empty:
        # 获取最新几期
        latest_rows = updated_df.tail(5)
        print(f"[OK] 成功更新，总数据量: {len(updated_df)} 条")
        print(f"最新 5 期数据:")
        for idx, row in latest_rows.iterrows():
            period = str(row['period'])
            draw_date = str(row.get('draw_date', 'N/A'))
            nums = f"{int(row['wan'])}-{int(row['qian'])}-{int(row['bai'])}-{int(row['shi'])}-{int(row['ge'])}"
            print(f"   期号={period}, 日期={draw_date}, 号码={nums}")
    else:
        print("[INFO] 未获取到新数据（可能原因：）")
        print("   - 网络数据源尚未更新最新期次")
        print("   - 本地数据已是最新")
        print("   - 网络请求失败（限流/超时）")
        
except Exception as e:
    print(f"[ERROR] 获取失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
