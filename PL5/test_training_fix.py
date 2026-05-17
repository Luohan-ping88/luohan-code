#!/usr/bin/env python
"""测试训练修复"""

import sys
import logging
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path.cwd()))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.enhanced_predictor import EnhancedPL5Predictor

print("="*60)
print("PL5 V10.5 训练测试 - 测试修复")
print("="*60)
print()

print("=== 1. 加载数据 ===")
collector = PL5DataCollector()
df = collector.update_data()
print(f"✓ 数据加载完成: {len(df)} 条记录")
print()

print("=== 2. 特征工程 ===")
engineer = FeatureEngineer()
df_features = engineer.extract_all_features(df, select_top=None)
positions = ['wan', 'qian', 'bai', 'shi', 'ge']
feature_cols = [c for c in df_features.columns 
              if c not in ['period', 'full_number', 'parse_line'] + positions]
print(f"✓ 特征工程完成: {len(feature_cols)} 个特征")
print(f"✓ 列检查: date列 {'存在' if 'date' in df_features.columns else '已移除'}")
print()

print("=== 3. 开始训练 ===")
predictor = EnhancedPL5Predictor()
start = datetime.now()
print(f"开始时间: {start.strftime('%H:%M:%S')}")
print()

try:
    # 训练（串行训练避免资源占用过高，避免并行造成的问题
    predictor.fit(df_features, feature_cols, parallel=False)
    elapsed = (datetime.now() - start).total_seconds()
    print()
    print(f"✓ 训练完成, 耗时: {elapsed:.1f}秒")
    print()

    print("=== 4. 保存模型 ===")
    predictor.save_models()
    print("✓ 模型已保存")
    
    print()
    print("="*60)
    print("训练测试成功完成！")
    print("="*60)
    
except Exception as e:
    print()
    print("="*60)
    print(f"训练失败: {e}")
    import traceback
    traceback.print_exc()
    print("="*60)
    sys.exit(1)
