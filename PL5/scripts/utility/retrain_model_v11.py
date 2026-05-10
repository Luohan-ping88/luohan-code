#!/usr/bin/env python
"""
PL5 模型重新训练脚本 V11
使用当前 V10.0 特征工程提取的特征重新训练模型
解决特征-模型不匹配问题
"""
import os
import sys
import time
import pickle
import joblib
from pathlib import Path

# 设置路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, '.')

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.predictor import PL5Predictor
from src.core.monitoring.performance_monitor import track_performance

print("=" * 70)
print("PL5 模型重新训练 V11")
print("使用 V10.0 特征工程，修复特征-模型不匹配问题")
print("=" * 70)
print()

# 1. 加载数据
print("[1/5] 加载数据...")
start_time = time.time()
collector = PL5DataCollector()
data = collector.load_processed_data()
if data is None or len(data) == 0:
    print("错误: 无法加载数据")
    sys.exit(1)
print(f"  数据加载完成: {len(data)} 条记录")
print(f"  最新期号: {data['period'].iloc[-1]}")
print(f"  时间范围: {data['date'].iloc[0]} 至 {data['date'].iloc[-1]}")

# 2. 特征工程
print("\n[2/5] 特征工程...")
engineer = FeatureEngineer()
features = engineer.extract_all_features(data, select_top=76)  # 提取76个特征以匹配模型
print(f"  特征提取完成: {len(features.columns)} 列")

# 获取特征列（排除元数据列）
non_feature_cols = {'period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date'}
feature_cols = [col for col in features.columns if col not in non_feature_cols]
print(f"  特征列数: {len(feature_cols)}")

# 3. 训练模型
print("\n[3/5] 训练模型...")
predictor = PL5Predictor()
try:
    predictor.train(features, feature_cols)
    print(f"  训练完成!")
    print(f"  模型状态: is_trained={predictor.is_trained}")
except Exception as e:
    print(f"  训练错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 保存模型
print("\n[4/5] 保存模型...")
models_dir = Path('models')
models_dir.mkdir(exist_ok=True)

# 备份旧模型
old_model_path = models_dir / 'pl5_predictor_v8.joblib'
backup_path = models_dir / f'pl5_predictor_v8_backup_{time.strftime("%Y%m%d_%H%M%S")}.joblib'
if old_model_path.exists():
    print(f"  备份旧模型到: {backup_path}")
    import shutil
    shutil.copy2(old_model_path, backup_path)

# 保存新模型
new_model_state = {
    'stacking': predictor.stacking,
    'hmm_models': predictor.hmm_models,
    'bsts_models': predictor.bsts_models,
    'evm_models': predictor.evm_models,
    'copula': predictor.copula,
    'feature_cols': feature_cols,
    'weights': predictor.weights if hasattr(predictor, 'weights') else {},
    'is_trained': predictor.is_trained,
    'version': '11.0',
    'trained_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    'n_features': len(feature_cols),
}
joblib.dump(new_model_state, old_model_path)
print(f"  模型已保存到: {old_model_path}")
print(f"  模型大小: {old_model_path.stat().st_size / 1024 / 1024:.2f} MB")

# 5. 验证模型
print("\n[5/5] 验证模型...")
try:
    # 重新加载模型
    loaded_predictor = PL5Predictor()
    if loaded_predictor.load_models():
        print(f"  模型加载成功!")
        print(f"  特征数量: {len(loaded_predictor.feature_cols)}")
        print(f"  模型版本: {loaded_predictor.feature_cols is not None}")

        # 测试预测
        test_features = features[feature_cols].iloc[-1].values.reshape(1, -1)
        recent_data = {
            pos: data[pos].values[-10:].astype(float)
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']
        }
        predictions = loaded_predictor.predict(test_features[0], recent_data, top_k=8)
        print("\n  预测结果 (Top 8):")
        for pos, pred in predictions.items():
            if isinstance(pred, dict) and 'top_k' in pred:
                print(f"    {pos}: {pred['top_k']}")
            else:
                print(f"    {pos}: {pred}")
        print("\n  ✅ 验证通过!")
    else:
        print("  ⚠️ 模型加载失败，但仍已保存")
except Exception as e:
    print(f"  ⚠️ 验证错误: {e}")

elapsed = time.time() - start_time
print("\n" + "=" * 70)
print(f"训练完成! 总耗时: {elapsed:.2f} 秒")
print("=" * 70)
