"""
检查数据状态 - 验证最新数据
"""
from pathlib import Path
from datetime import datetime

print('='*70)
print('数据状态检查')
print('='*70)
print()

# 读取历史数据
raw_file = Path('data/raw/pl5_history.txt')
if not raw_file.exists():
    print('❌ 历史数据文件不存在')
    exit(1)

with open(raw_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

total_records = len(lines)
print(f'总记录数: {total_records} 条')
print()

# 获取最新一期
latest_line = lines[-1].strip()
parts = latest_line.split()
latest_period = parts[0]
latest_date = parts[1]
latest_numbers = parts[2:7]

print('最新一期数据:')
print(f'  期号: {latest_period}')
print(f'  日期: {latest_date}')
print(f'  开奖号码: {" ".join(latest_numbers)}')
print()

# 获取最近5期
print('最近5期数据:')
print('-'*70)
for line in lines[-5:]:
    parts = line.strip().split()
    period = parts[0]
    date = parts[1]
    numbers = parts[2:7]
    print(f'  {period} | {date} | {" ".join(numbers)}')

print()
print('='*70)

# 计算下一期
if len(latest_period) == 7:
    next_period = str(int(latest_period) + 1)
    print(f'最新期号: {latest_period}')
    print(f'预测期号: {next_period}')
else:
    print(f'最新期号: {latest_period}')

print('='*70)
