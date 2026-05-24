"""
生成本期排列五预测 - 完整展示每个位置的8/5/3码预测
"""
import sys
sys.path.insert(0, '.')

print('='*70)
print('🎯 排列五智能预测系统 - 本期预测')
print('='*70)
print()

# 加载数据
print('[1/4] 加载历史数据...')
from core.data_collector import PL5DataCollector
collector = PL5DataCollector()
df = collector.load_processed_data()
print(f'      成功加载 {len(df)} 条记录')
print()

# 特征工程
print('[2/4] 特征工程...')
from core.feature_engineering import FeatureEngineer
fe = FeatureEngineer()
# 【关键修复】predict 时用全量特征，保证模型训练特征全部存在
df_features = fe.extract_all_features(df, select_top=None)
print(f'      特征维度: {len(df_features.columns)}')
print()

# 加载模型，确定特征列
from core.models import PL5Predictor
predictor = PL5Predictor()
loaded = predictor.load_models()
if loaded and predictor.feature_cols:
    # 【关键修复】使用模型训练时的特征列，避免维度不匹配
    feature_cols = predictor.feature_cols
    print(f'      使用模型特征列: {len(feature_cols)} 个')
else:
    if not loaded:
        print('      未找到保存的模型，将重新训练...')
    # 退回到全量特征
    feature_cols = [col for col in df_features.columns
                   if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
print(f'      使用特征: {len(feature_cols)} 个')
print()

# 加载模型或训练
print('[3/4] 加载预测模型...')
if not loaded:
    print('      未找到保存的模型，正在训练...')
    predictor.fit(df_features, feature_cols)
    predictor.save_models()
    print('      模型训练并保存完成')
else:
    print('      已加载保存的模型')
print()

# 生成预测
print('[4/4] 生成预测...')
latest = df_features[feature_cols].iloc[-1].values
predictions = predictor.predict(latest, top_k=8)
print('      预测生成完成')
print()

# 提取预测结果
position_names = {
    'wan': '万位',
    'qian': '千位',
    'bai': '百位',
    'shi': '十位',
    'ge': '个位'
}

top_8 = {}
top_5 = {}
top_3 = {}
top_1 = {}

for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    pred = predictions.get(pos, {})
    top_k = pred.get('top_k', [])
    top_8[pos] = top_k[:8]
    top_5[pos] = top_k[:5]
    top_3[pos] = top_k[:3]
    top_1[pos] = top_k[:1]

# 显示结果 - 完整展示每个位置的8/5/3码
print('='*70)
print('🎯 本期预测结果 (Top 8 / 5 / 3)')
print('='*70)

for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
    pos_name = position_names.get(pos, pos)
    print(f"\n{pos_name}:")
    print(f"  Top 8: {top_8.get(pos, [])}")
    print(f"  Top 5: {top_5.get(pos, [])}")
    print(f"  Top 3: {top_3.get(pos, [])}")
    print(f"  Top 1: {top_1.get(pos, [])}")

print()
print('='*70)

# 保存预测结果
import json
from datetime import datetime
from pathlib import Path

# 确保results目录存在
results_dir = Path('results')
results_dir.mkdir(exist_ok=True)

result = {
    'timestamp': datetime.now().isoformat(),
    'predictions': predictions
}

output_file = results_dir / 'latest_prediction.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print()
print(f'✅ 预测结果已保存到: {output_file}')
print()
print('📋 预测号码汇总:')
print(f'万位: {predictions["wan"]["top_k"]}')
print(f'千位: {predictions["qian"]["top_k"]}')
print(f'百位: {predictions["bai"]["top_k"]}')
print(f'十位: {predictions["shi"]["top_k"]}')
print(f'个位: {predictions["ge"]["top_k"]}')
