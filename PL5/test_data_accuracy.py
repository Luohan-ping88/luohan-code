#!/usr/bin/env python3
"""
测试数据清洗后的准确率
"""

from src.core.data.collector import PL5DataCollector, DataValidator

# 创建数据采集器
collector = PL5DataCollector()

# 更新数据
data = collector.update_data()

# 计算准确率
total_records = len(data)
valid_count = 0

for _, row in data.iterrows():
    record = {
        'period': row['period'],
        'wan': row['wan'],
        'qian': row['qian'],
        'bai': row['bai'],
        'shi': row['shi'],
        'ge': row['ge']
    }
    is_valid, _ = DataValidator.validate_record(record)
    if is_valid:
        valid_count += 1

accuracy = (valid_count / total_records) * 100

print('数据清洗后的准确率:', accuracy, '%')
print('有效记录数:', valid_count)
print('总记录数:', total_records)
