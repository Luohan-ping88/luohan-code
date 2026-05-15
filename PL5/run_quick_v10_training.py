#!/usr/bin/env python3
"""
执行快速但完整的V10训练（约30-60分钟）
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.app.analyze_and_send import analyze_and_send


def main():
    print("=" * 80)
    print("执行快速完整的V10训练（约30-60分钟）")
    print("=" * 80)

    print(f"\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    collector = PL5DataCollector()
    df = collector.update_data()
    print(f"✓ 数据加载完成: {len(df)} 条记录")

    # 2. 特征工程
    print("\n[2/4] 特征工程...")
    engineer = FeatureEngineer()
    df_features = engineer.extract_all_features(df)
    feature_cols = [
        col for col in df_features.columns
        if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']
    ]
    print(f"✓ 特征工程完成: {len(feature_cols)} 个特征")

    # 3. 强制全量训练
    print("\n[3/4] 开始完整训练...")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"特征维度: {len(feature_cols)}")
    print(f"数据量: {len(df_features)}")
    
    predictor = EnhancedPL5Predictor()

    try:
        # 强制全量训练（会训练所有模型包括V10模块）
        start_train = datetime.now()
        print(f"训练开始时间: {start_train.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 使用串行训练避免卡住
        print("使用串行训练模式...")
        predictor.fit(df_features, feature_cols, parallel=False)
        
        end_train = datetime.now()
        print(f"训练完成时间: {end_train.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"训练耗时: {(end_train - start_train).total_seconds():.2f} 秒")
        
        predictor.save_models()
        print("✓ 模型训练完成！")
    except Exception as e:
        print(f"✗ 训练失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 发送邮件
    print("\n[4/4] 发送邮件...")
    try:
        analyze_and_send()
        print("✓ 邮件发送完成！")
    except Exception as e:
        print(f"✗ 邮件发送失败: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "=" * 80)
    print("✓ V10训练任务完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
