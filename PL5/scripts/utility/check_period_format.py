"""
检查期号格式
"""
import json

with open('models/learning_history.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 查看原始期号格式
print('原始期号格式检查:')
print('-' * 50)
for eval in data['evaluations'][-5:]:
    period = eval['period']
    print(f'原始期号: {period} (类型: {type(period).__name__})')

print()
print('历史数据中的期号:')
print('-' * 50)
with open('data/raw/pl5_history.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()[:5]
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 2:
            print(f'历史数据期号: {parts[0]}')
