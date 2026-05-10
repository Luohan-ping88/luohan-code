"""
快速预测 - 简化版
"""
import sys
sys.path.insert(0, '.')

import numpy as np
import pandas as pd
from core.data_collector import PL5DataCollector
from datetime import datetime, timedelta
import json
from pathlib import Path

print('='*70)
print('排列五高阶数理分析预测系统 - 快速预测')
print('='*70)
print()

# 加载数据
print('[1/2] 加载历史数据...')
collector = PL5DataCollector()
df = collector.load_processed_data()

# 获取最新期号
latest_period = df['period'].iloc[-1]
latest_date = df['date'].iloc[-1] if 'date' in df.columns else None

# 计算预测期号
if isinstance(latest_period, str):
    # 如果是字符串格式如 "2026073"
    next_period = str(int(latest_period) + 1)
else:
    next_period = str(int(latest_period) + 1)

# 计算预测日期
if latest_date:
    try:
        next_date = pd.to_datetime(latest_date) + timedelta(days=1)
        date_str = next_date.strftime('%Y-%m-%d')
    except:
        date_str = '明日'
else:
    date_str = '明日'

print(f'      最新期号: {latest_period}')
print(f'      历史记录: {len(df)} 条')
print(f'      预测期号: {next_period} ({date_str})')
print()

# 简单预测 - 基于历史频率
print('[2/2] 生成预测...')

predictions = {}
for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    # 计算每个数字的出现频率
    freq = df[pos].value_counts().sort_values(ascending=False)
    # 获取Top 8
    top_8 = freq.head(8).index.tolist()
    predictions[pos] = {
        'top_k': top_8,
        'probabilities': (freq.head(8).values / freq.sum()).tolist()
    }

print('      预测生成完成')
print()

# 显示结果
print('='*70)
print(f'第 {next_period} 期预测结果 ({date_str})')
print('='*70)
for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    nums = predictions[pos]['top_k']
    print(f'{pos:6s}: {nums}')
print('='*70)

# 保存预测结果
results_dir = Path('results')
results_dir.mkdir(exist_ok=True)

result = {
    'timestamp': datetime.now().isoformat(),
    'period': next_period,
    'date': date_str,
    'latest_period': str(latest_period),
    'predictions': predictions
}

output_file = results_dir / f'prediction_{next_period}.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print()
print(f'预测结果已保存到: {output_file}')
print()
print(f'第 {next_period} 期预测号码汇总:')
print(f'万位: {predictions["wan"]["top_k"]}')
print(f'千位: {predictions["qian"]["top_k"]}')
print(f'百位: {predictions["bai"]["top_k"]}')
print(f'十位: {predictions["shi"]["top_k"]}')
print(f'个位: {predictions["ge"]["top_k"]}')
print()
print(f'预测时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
