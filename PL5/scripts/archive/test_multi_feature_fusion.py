#!/usr/bin/env python
"""
测试智能动态多特征组合融合系统
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer_v10 import FeatureEngineerV10 as FeatureEngineer
from src.core.models.multi_feature_fusion import MultiFeatureFusionPredictor, create_multi_feature_predictor

print("=" * 70)
print("PL5 智能动态多特征组合融合系统测试 V11")
print("=" * 70)

# 1. 加载数据
print("\n[1/5] 加载数据...")
collector = PL5DataCollector()
data = collector.load_processed_data()
print(f"  数据量: {len(data)} 期")
print(f"  最新期号: {data['period'].iloc[-1]}")

# 2. 特征工程
print("\n[2/5] 特征工程...")
engineer = FeatureEngineer()
features_df = engineer.extract_all_features(data, select_top=0)  # 先不使用特征选择，避免无穷大值问题
print(f"  提取特征数: {len(features_df.columns)}")

# 获取特征列
non_feature_cols = {'period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date'}
feature_cols = [c for c in features_df.columns if c not in non_feature_cols]
print(f"  有效特征数: {len(feature_cols)}")

# 3. 训练多特征融合模型
print("\n[3/5] 训练智能多特征组合模型...")
predictor = create_multi_feature_predictor()
predictor.fit(features_df, feature_cols, recent_periods=500)

# 4. 查看特征组合
print("\n[4/5] 特征组合摘要...")
summary = predictor.get_intelligent_summary()
print(f"  生成的特征组合数: {summary['n_combinations']}")
for combo in summary['combinations']:
    print(f"  - {combo['name']}: {combo['n_features']} 特征, 命中率={combo['hit_rate']:.2%}")

# 5. 预测测试
print("\n[5/5] 多特征融合预测...")
predictions = predictor.predict(features_df, top_k=8)

print("\n  预测结果 (Top 8):")
for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    if pos in predictions:
        pred = predictions[pos]
        top_k = pred['top_k']
        probs = pred['probabilities']
        n_combos = pred.get('n_combinations_used', 0)
        print(f"\n  {pos}位: {top_k}")
        print(f"    概率: {[f'{p:.3f}' for p in probs]}")
        print(f"    使用特征组合数: {n_combos}")

        # 显示组合详情
        details = pred.get('combination_details', {})
        if details:
            print(f"    组合权重:")
            for combo_name, info in details.items():
                print(f"      - {combo_name}: weight={info['weight']:.3f}, hit_rate={info['hit_rate']:.2%}")

print("\n" + "=" * 70)
print("智能多特征组合融合测试完成！")
print("=" * 70)
