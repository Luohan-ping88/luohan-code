"""
测试特征工程是否能够正常完成
"""

import pandas as pd
from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer

# 初始化数据采集器
collector = PL5DataCollector()
df = collector.update_data()
print(f"数据采集完成，记录数: {len(df)}")

# 初始化特征工程器
engineer = FeatureEngineer()

# 测试特征工程
try:
    print("开始特征工程...")
    df_features = engineer.extract_all_features(df)
    feature_cols = [
        c for c in df_features.columns if c not in ["period", "full_number", "wan", "qian", "bai", "shi", "ge"]
    ]
    print(f"特征工程完成，特征数: {len(feature_cols)}")
    print(f"特征列: {feature_cols[:10]}...")  # 只显示前10个特征
    print("测试成功！特征工程能够正常完成")
except Exception as e:
    print(f"测试失败！特征工程失败: {e}")
    import traceback

    traceback.print_exc()
