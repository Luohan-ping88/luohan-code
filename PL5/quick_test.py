#!/usr/bin/env python
"""快速验证脚本 - 测试修复是否有效"""
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 测试1: 检查数据是否可以加载
print("="*80)
print("测试1: 数据加载和特征工程")
print("="*80)

try:
    from src.core.data.collector import PL5DataCollector
    from src.core.features.engineer import FeatureEngineer
    
    collector = PL5DataCollector()
    df = collector.update_data()
    print(f"✅ 数据加载成功，{len(df)} 条记录")
    
    engineer = FeatureEngineer()
    df_features = engineer.extract_all_features(df, select_top=None)
    print(f"✅ 特征工程完成，{len(df_features.columns)} 列")
    
    # 检查是否还有问题列
    exclude_cols = ['period', 'date', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']
    feature_cols = [c for c in df_features.columns if c not in exclude_cols]
    print(f"✅ 可用特征数: {len(feature_cols)}")
    
    # 检查特征类型
    sample_features = df_features[feature_cols].head(1)
    types_ok = True
    for col in feature_cols:
        try:
            val = sample_features[col].values[0]
            float(val)  # 尝试转为float
        except:
            print(f"❌ 列 {col} 不是数值类型: {type(val)}")
            types_ok = False
    
    if types_ok:
        print("✅ 所有特征都是数值类型")
    
except Exception as e:
    print(f"❌ 测试1失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ 所有基础测试通过！现在可以进行完整训练了")
print("="*80)
print("\n你现在可以运行:")
print("  python main.py train")
print("  python main.py predict")
print("  python main.py analyze")
