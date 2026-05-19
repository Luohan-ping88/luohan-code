#!/usr/bin/env python3
"""
执行合理参数的训练（约1-2小时）
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
    print("执行合理参数的训练（约1-2小时）")
    print("=" * 80)
    print("\n⚠️  训练参数配置（优化版）：")
    print("  - Mamba: 4层, 64维, 16状态, 30序列长度, 100轮")
    print("  - iTransformer: 3层, 64维, 4头, 30序列长度, 100轮")
    print("  - 样本数限制: 500条")
    print("  - 并行训练: 开启")
    
    print(f"\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n[1/5] 加载数据...")
    collector = PL5DataCollector()
    df = collector.update_data()
    print(f"✓ 数据加载完成: {len(df)} 条记录")
    
    print("\n[2/5] 特征工程...")
    engineer = FeatureEngineer()
    df_features = engineer.extract_all_features(df)
    feature_cols = [
        col for col in df_features.columns
        if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']
    ]
    print(f"✓ 特征工程完成: {len(feature_cols)} 个特征")
    
    print("\n[3/5] 优化参数训练（约1-2小时）...")
    
    # 首先停止之前的训练进程
    print("\n[清理] 停止之前的训练进程...")
    import os
    import signal
    try:
        # 查找并停止Python进程
        import subprocess
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], 
                             capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'python.exe' in line:
                try:
                    pid = int(line.split()[1])
                    os.kill(pid, signal.SIGTERM)
                    print(f"  已停止进程: {pid}")
                except:
                    pass
    except Exception as e:
        print(f"  清理进程时出错: {e}")
    
    # 强制全量训练
    print("\n[训练] 开始优化参数训练...")
    predictor = EnhancedPL5Predictor()
    
    # 训练（使用优化参数）
    try:
        # 修改Mamba和iTransformer的训练参数
        # 注意：这里直接调用fit，参数已经在enhanced_predictor.py中设置
        predictor.fit(df_features, feature_cols, parallel=True)
        predictor.save_models()
        print("✓ 训练完成！")
    except Exception as e:
        print(f"✗ 训练失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n[4/5] 分析并预测...")
    
    print("\n[5/5] 发送邮件...")
    try:
        analyze_and_send()
        print("✓ 邮件发送完成！")
    except Exception as e:
        print(f"✗ 邮件发送失败: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "=" * 80)
    print("✓ 训练任务完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
