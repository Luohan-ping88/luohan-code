#!/usr/bin/env python
"""测试数据获取"""
import sys
sys.path.insert(0, '.')
from core.data_collector_v8 import PL5DataCollector
import time

print('创建collector...')
collector = PL5DataCollector()

print('开始获取数据...')
start = time.time()
df = collector.update_data()
elapsed = time.time() - start

print(f'获取完成: {len(df)} 条记录, 耗时: {elapsed:.2f}秒')
print(f'最新期号: {df["period"].max()}')
