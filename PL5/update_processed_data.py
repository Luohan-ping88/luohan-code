#!/usr/bin/env python3
"""
更新处理后的数据文件
"""
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from src.core.data.collector import PL5DataCollectorV8

def main():
    collector = PL5DataCollectorV8()

    # 加载本地原始数据
    print("加载本地原始数据...")
    df = collector.load_local_data()

    if df is None or df.empty:
        print("错误：无法加载本地原始数据")
        return

    print(f"加载数据: {len(df)} 条")
    print(f"最新期号: {df['period'].iloc[-1]}")
    print(f"最后5期: {df['period'].tail(5).values}")

    # 保存处理后的数据
    output_path = Path("c:/Users/Administrator/Desktop/PL5/data/processed/pl5_processed.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"处理后的数据已保存到: {output_path}")

    # 验证
    df_check = pd.read_csv(output_path)
    print(f"\n验证: 读取 {len(df_check)} 条记录")
    print(f"最新期号: {df_check['period'].iloc[-1]}")

if __name__ == "__main__":
    main()
