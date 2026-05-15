#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查数据源是否有新数据"""

import sys
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("检查数据源和数据更新情况")
print("=" * 80)

# 1. 检查数据源
url = "http://data.17500.cn/pl5_asc.txt"
print(f"\n[1] 尝试获取数据源: {url}")
try:
    response = requests.get(url, timeout=30)
    print(f"✓ 网络请求成功: 状态码 {response.status_code}")
    print(f"  内容大小: {len(response.content)} 字节")
    
    content = response.text
    lines = content.split('\n')
    print(f"  总行数: {len(lines)}")
    
    if len(lines) > 10:
        print(f"\n  最新10行数据:")
        for i, line in enumerate(lines[-10:], 1):
            if line.strip():
                print(f"    [{len(lines)-10+i}] {line[:80]}")
                
except Exception as e:
    print(f"✗ 网络请求失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 检查本地数据
print("\n" + "=" * 80)
print("[2] 检查本地处理后的数据")
print("=" * 80)

try:
    from src.core.data.collector import PL5DataCollector
    collector = PL5DataCollector()
    df = collector.load_processed_data()
    
    if df is not None and len(df) > 0:
        print(f"\n✓ 本地数据加载成功")
        print(f"  记录数: {len(df)}")
        print(f"  列名: {list(df.columns)}")
        
        if 'period' in df.columns:
            latest_period_local = df['period'].iloc[-1]
            print(f"\n  本地最新期号: {latest_period_local}")
            
            if len(lines) > 0:
                # 尝试从网络数据解析最新期号
                try:
                    # 查找最后一条有效数据
                    last_valid_line = None
                    for line in reversed(lines):
                        line = line.strip()
                        if line and len(line) >= 7:  # 期号至少7位
                            last_valid_line = line
                            break
                    
                    if last_valid_line:
                        print(f"\n  网络最新行: {last_valid_line}")
                        # 尝试解析期号（通常是前7位）
                        if len(last_valid_line) >= 7:
                            network_period = last_valid_line[:7]
                            print(f"  网络最新期号: {network_period}")
                            
                            if str(network_period) != str(latest_period_local):
                                print(f"\n⚠️  警告: 网络期号 ({network_period}) 与本地期号 ({latest_period_local}) 不一致!")
                                print("   需要更新数据!")
                            else:
                                print(f"\n✓ 数据已是最新!")
                except Exception as e:
                    print(f"  解析网络数据失败: {e}")
                    
        print(f"\n  本地最新5条:")
        print(df.tail())
        
except Exception as e:
    print(f"✗ 检查本地数据失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)
