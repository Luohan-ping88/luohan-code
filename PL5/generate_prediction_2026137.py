#!/usr/bin/env python
"""
生成2026137期预测报告
"""

import sys
import os
from datetime import datetime
from pathlib import Path
import json
import pandas as pd

# 设置项目路径
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

LOG_DIR = PROJECT_DIR / 'logs'
RESULTS_DIR = PROJECT_DIR / 'results'
LOG_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
REPORT_PATH = LOG_DIR / f'prediction_report_2026137_{timestamp}.txt'
PREDICTION_PATH = RESULTS_DIR / f'prediction_2026137.json'


def load_data():
    """加载处理好的数据"""
    data_path = PROJECT_DIR / 'data/processed/pl5_processed.csv'
    if data_path.exists():
        df = pd.read_csv(data_path)
        print(f"✓ 数据加载成功，共 {len(df)} 条记录")
        print(f"  最新期号: {df['period'].iloc[-1]}")
        return df
    else:
        print("✗ 数据文件未找到")
        return None


def generate_prediction_report(df):
    """生成预测报告"""
    report = []
    report.append("=" * 80)
    report.append("PL5 预测报告 - 2026137期")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 1. 数据状态
    report.append("-" * 80)
    report.append("1. 数据状态")
    report.append("-" * 80)
    report.append(f"  ✓ 数据记录数: {len(df)}")
    report.append(f"  ✓ 最新期号: {df['period'].iloc[-1]}")
    report.append(f"  ✓ 下期预测: 2026137")
    
    # 2. 最近几期结果
    report.append("")
    report.append("-" * 80)
    report.append("2. 最近10期开奖结果")
    report.append("-" * 80)
    report.append("  期号      万  千  百  十  个")
    report.append("  " + "-" * 30)
    
    for i in range(min(10, len(df))):
        idx = len(df) - 1 - i
        row = df.iloc[idx]
        report.append(f"  {row['period']}  {int(row['wan'])}  {int(row['qian'])}  {int(row['bai'])}  {int(row['shi'])}  {int(row['ge'])}")
    
    # 3. 预测结果
    report.append("")
    report.append("-" * 80)
    report.append("3. 2026137期预测结果")
    report.append("-" * 80)
    
    # 基于历史数据的简单统计预测
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    position_names = ['万位', '千位', '百位', '十位', '个位']
    
    for pos, name in zip(positions, position_names):
        # 统计最近100期的数字频率
        recent_data = df[pos].tail(100)
        freq = recent_data.value_counts().sort_values(ascending=False)
        
        report.append(f"  {name}:")
        report.append(f"    高频数字 (Top 3): {list(freq.head(3).index)}")
        report.append(f"    出现次数: {list(freq.head(3).values)}")
        
        # 计算遗漏值
        all_numbers = set(range(10))
        recent_numbers = set(recent_data.tail(20).values)
        missing = sorted(all_numbers - recent_numbers)
        if missing:
            report.append(f"    遗漏数字 (近20期): {missing}")
    
    # 4. 综合建议
    report.append("")
    report.append("-" * 80)
    report.append("4. 综合建议")
    report.append("-" * 80)
    report.append("  建议关注最近5期的热门数字")
    report.append("  注意冷热数字的平衡")
    report.append("  可以考虑包含最近遗漏的数字")
    report.append("  建议小额投注，理性购彩")
    
    # 5. 生成预测JSON
    prediction_data = {
        'period': '2026137',
        'timestamp': datetime.now().isoformat(),
        'data': {
            'latest_period': int(df['period'].iloc[-1]),
            'total_records': len(df)
        },
        'predictions': {}
    }
    
    for pos, name in zip(positions, position_names):
        recent_data = df[pos].tail(100)
        freq = recent_data.value_counts().sort_values(ascending=False)
        top_8 = list(freq.head(8).index)
        
        prediction_data['predictions'][pos] = {
            'top_8': top_8,
            'top_3': top_8[:3],
            'position_name': name
        }
    
    # 保存预测JSON
    with open(PREDICTION_PATH, 'w', encoding='utf-8') as f:
        json.dump(prediction_data, f, indent=2, ensure_ascii=False)
    
    report.append("")
    report.append("-" * 80)
    report.append("5. 预测详情 (Top 8)")
    report.append("-" * 80)
    for pos, name in zip(positions, position_names):
        pred = prediction_data['predictions'][pos]
        report.append(f"  {name}: {pred['top_8']}")
    
    report.append("")
    report.append("=" * 80)
    report.append(f"预测结果已保存到: {PREDICTION_PATH}")
    report.append("=" * 80)
    
    return "\n".join(report), prediction_data


def main():
    print("=" * 80)
    print("PL5 预测报告生成器 - 2026137期")
    print("=" * 80)
    
    # 1. 加载数据
    df = load_data()
    if df is None:
        return 1
    
    # 2. 生成报告
    report_content, prediction_data = generate_prediction_report(df)
    print("\n" + report_content)
    
    # 3. 保存报告
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report_content)
    print(f"\n✓ 报告已保存到: {REPORT_PATH}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
