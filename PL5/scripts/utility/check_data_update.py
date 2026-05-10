#!/usr/bin/env python
"""检查数据更新状态"""
import sys
sys.path.insert(0, '.')

from src.core.data.collector import PL5DataCollectorV8

collector = PL5DataCollectorV8()

# 检查本地数据
print('=== 本地数据检查 ===')
data = collector.load_processed_data()
print(f'本地数据条数: {len(data)}')
print(f'最新期号: {data["period"].iloc[-1]}')
print(f'最新日期: {data["date"].iloc[-1]}')
print()

# 检查是否需要更新
print('=== 检查数据更新 ===')
latest = collector.get_latest_period()
print(f'版本管理器最新期号: {latest}')

# 尝试更新数据
print()
print('=== 尝试更新数据 ===')
result = collector.update_data()
if result is not None:
    print(f'更新成功，数据条数: {len(result)}')
    print(f'最新期号: {result["period"].iloc[-1]}')
else:
    print('更新失败或无需更新')
