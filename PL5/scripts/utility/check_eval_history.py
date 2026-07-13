"""
检查评估历史详情
"""
import json
from datetime import datetime

with open('models/learning_history.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

evaluations = data.get('evaluations', [])
print('='*70)
print('评估历史详情检查')
print('='*70)
print(f'总评估记录数: {len(evaluations)}')
print()

# 显示最近10条记录
print('最近10条评估记录:')
print('-' * 70)
for eval in evaluations[-10:]:
    period = eval.get('period', '未知')
    # 转换期号格式 (26030 -> 2026030)
    # 原始格式: 2位年份缩写(26) + 3位期号(030)
    if isinstance(period, str) and len(period) == 5:
        year_short = period[:2]  # 26
        issue = period[2:]       # 030
        full_period = f"20{year_short}{issue}"  # 2026030
    else:
        full_period = period
    timestamp = eval.get('timestamp', '未知')[:19]
    accuracy = eval.get('accuracy', 0)
    print(f'期号: {full_period} | 时间: {timestamp} | 准确率: {accuracy:.2%}')

print()
print('='*70)
first_period = evaluations[0].get('period', '未知')
last_period = evaluations[-1].get('period', '未知')

# 正确转换期号
def convert_period(p):
    if isinstance(p, str) and len(p) == 5:
        return f"20{p[:2]}{p[2:]}"
    return p

first_full = convert_period(first_period)
last_full = convert_period(last_period)

print(f'最早评估: {first_full}')
print(f'最后评估: {last_full}')

# 获取最新数据期号
with open('data/raw/pl5_history.txt', 'r', encoding='utf-8') as f:
    last_line = f.readlines()[-1]
    latest_period = last_line.strip().split()[0]

print(f'最新数据: {latest_period}')

# 计算差距
try:
    gap = int(latest_period) - int(last_full)
    print(f'差距: {gap} 期')
except:
    print(f'差距: 无法计算')
print('='*70)

if gap > 10:
    print()
    print('⚠️ 警告: 评估记录落后最新数据较多!')
    print('建议运行: python main.py --full 进行完整评估')
