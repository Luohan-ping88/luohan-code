#!/usr/bin/env python3
"""
强制执行深度训练（约5小时）
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
    print("强制执行深度训练（约5小时）")
    print("=" * 80)
    print("\n⚠️  训练参数配置：")
    print("  - Mamba: 8层, 128维, 32状态, 60序列长度, 300轮")
    print("  - iTransformer: 6层, 128维, 8头, 60序列长度, 300轮")
    print("  - 使用全部数据，无样本数限制")
    
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
    
    print("\n[3/5] 强制全量深度训练（约5小时）...")
    print("⚠️  这会删除现有模型，重新训练所有6个模型！")
    
    predictor = EnhancedPL5Predictor()
    
    # 删除现有模型
    models_dir = Path(__file__).parent / "models"
    for model_file in models_dir.glob("*.pkl"):
        try:
            model_file.unlink()
            print(f"  删除旧模型: {model_file.name}")
        except Exception as e:
            print(f"  无法删除 {model_file.name}: {e}")
    
    # 强制全量训练
    print("\n开始深度训练...")
    predictor.fit(df_features, feature_cols, parallel=False)
    predictor.save_models()
    print("✓ 深度训练完成！")
    
    print("\n[4/5] 分析并预测...")
    print("调用 analyze_and_send_email()...")
    
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
    print("✓ 今日深度训练任务全部完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
