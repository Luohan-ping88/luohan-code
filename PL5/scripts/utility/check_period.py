#!/usr/bin/env python
import sys
sys.path.insert(0, '.')
from core.data_collector_v8 import PL5DataCollector

collector = PL5DataCollector()
df = collector.update_data()

print(f'数据记录数: {len(df)}')
print(f'最新期号: {df["period"].max()}')
print(f'最新一期数据:')
print(df.iloc[-1][['period', 'wan', 'qian', 'bai', 'shi', 'ge']])
print()
print(f'预测期号应该是: {int(df["period"].max()) + 1}')
