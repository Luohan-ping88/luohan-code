#!/usr/bin/env python
"""测试数据更新逻辑"""
import sys
sys.path.insert(0, '.')

from src.core.data.collector import PL5DataCollectorV8

collector = PL5DataCollectorV8()

print('=== 更新前 ===')
df_before = collector.load_processed_data()
print(f'数据条数: {len(df_before)}')
print(f'最新期号: {df_before["period"].iloc[-1]}')
print()

print('=== 执行更新 ===')
df_updated = collector.update_data()
print(f'更新后数据条数: {len(df_updated)}')
print(f'最新期号: {df_updated["period"].iloc[-1]}')
print()

print('=== 重新加载验证 ===')
df_after = collector.load_processed_data()
print(f'重新加载数据条数: {len(df_after)}')
print(f'最新期号: {df_after["period"].iloc[-1]}')
