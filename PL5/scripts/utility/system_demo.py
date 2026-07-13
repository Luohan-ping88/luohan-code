#!/usr/bin/env python
"""
PL5 系统运行演示脚本
展示系统核心功能的完整运行流程
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def main():
    print('='*60)
    print('PL5 系统运行演示')
    print('='*60)
    print()

    # 1. 数据采集
    print('[1/4] 数据采集...')
    from src.core.data.collector import PL5DataCollectorV8
    collector = PL5DataCollectorV8()
    data = collector.load_processed_data()
    print(f'      已加载 {len(data)} 条历史记录')
    print(f'      最新期号: {data["period"].iloc[-1]}')
    print()

    # 2. 特征工程
    print('[2/4] 特征工程...')
    from src.core.features.engineer import FeatureEngineer
    
    engineer = FeatureEngineer()
    start = time.time()
    features = engineer.extract_all_features(data.tail(100))
    elapsed = time.time() - start
    print(f'      提取了 {len(features.columns)} 个特征')
    print(f'      耗时: {elapsed:.2f}秒')
    print()

    # 3. 系统监控
    print('[3/4] 系统监控...')
    from monitor.perfect_monitor import PerfectSystemMonitor
    monitor = PerfectSystemMonitor()
    metrics = monitor.get_system_metrics()
    print(f'      CPU: {metrics["cpu"]["percent"]}%')
    print(f'      内存: {metrics["memory"]["percent"]}%')
    print(f'      磁盘: {metrics["disk"]["percent"]}%')
    print()

    # 4. 生成预测
    print('[4/4] 生成预测...')
    from src.core.models.predictor import PL5Predictor
    predictor = PL5Predictor()
    # 使用最后一条数据进行预测
    latest_features = features.iloc[[-1]]
    predictions = predictor.predict(latest_features)
    print(f'      预测结果: {predictions}')
    print()

    print('='*60)
    print('系统运行完成!')
    print('='*60)

if __name__ == '__main__':
    main()
