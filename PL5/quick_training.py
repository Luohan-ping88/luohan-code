#!/usr/bin/env python3
"""
快速训练脚本 - 快速验证训练流程
"""

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path("/workspace/PL5")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

def main():
    print("=" * 80)
    print("PL5 快速训练验证")
    print("=" * 80)
    print()

    start_time = time.time()

    # 1. 加载数据
    print("[1/5] 加载数据...")
    from src.core.data.collector import PL5DataCollectorV8
    collector = PL5DataCollectorV8()
    data = collector.load_processed_data()
    if data is None:
        print("  ✗ 数据加载失败")
        return
    print(f"  ✓ 数据加载完成: {len(data)} 条记录")
    print(f"  最新期号: {data['period'].iloc[-1]}")

    # 2. 特征工程
    print("\n[2/5] 提取特征...")
    from src.core.features.engineer import FeatureEngineer
    engineer = FeatureEngineer()
    features = engineer.extract_all_features(data)
    non_feature_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']
    feature_cols = [col for col in features.columns if col not in non_feature_cols]
    print(f"  ✓ 特征提取完成: {len(feature_cols)} 个特征")

    # 3. 训练模型（简化版本）
    print("\n[3/5] 训练模型（简化版本）...")
    from src.core.models.predictor import PL5Predictor
    predictor = PL5Predictor()

    # 使用较小的数据集进行快速训练
    train_size = min(1000, len(features))
    train_data = features.iloc[:train_size]
    print(f"  训练样本数: {train_size}")

    predictor.train(train_data, feature_cols)
    print(f"  ✓ 模型训练完成")

    # 4. 评估模型
    print("\n[4/5] 评估模型...")
    if len(features) > train_size:
        test_data = features.iloc[train_size:train_size+100]
        correct = 0
        total = 0
        for idx in range(len(test_data)):
            sample = test_data.iloc[[idx]]
            true_label = test_data.iloc[idx]['wan']
            pred = predictor.predict(sample)
            if pred and 'wan' in pred:
                predicted_label = pred['wan']['top_k'][0]
                if predicted_label == true_label:
                    correct += 1
                total += 1

        accuracy = correct / total if total > 0 else 0
        print(f"  ✓ 准确率: {accuracy * 100:.2f}%")
        print(f"  正确预测: {correct}/{total}")

    # 5. 生成预测
    print("\n[5/5] 生成预测...")
    latest = features.iloc[[-1]]
    predictions = predictor.predict(latest)
    print("  ✓ 预测结果:")
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        if pos in predictions:
            top_k = predictions[pos]['top_k'][:5]
            print(f"    {pos}: {top_k}")

    elapsed = time.time() - start_time
    print()
    print("=" * 80)
    print(f"训练完成！总耗时: {elapsed:.2f}秒")
    print("=" * 80)

if __name__ == "__main__":
    main()
