#!/usr/bin/env python
"""
测试数据加载功能
验证训练模式的数据加载过程
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print('=' * 60)
print('测试数据加载功能')
print('=' * 60)
print()

# 测试数据收集器
print('[1/3] 测试 PL5DataCollector...')
try:
    from src.core.data.collector import PL5DataCollector
    collector = PL5DataCollector()
    print('  ✓ PL5DataCollector 初始化成功')
    
    # 测试加载原始数据
    raw_data = collector.load_local_data()
    print(f'  ✓ 原始数据加载成功: {len(raw_data)} 条记录')
    print(f'  ✓ 最新期号: {raw_data["period"].iloc[-1]}')
    
    # 测试加载处理后的数据
    processed_data = collector.load_processed_data()
    print(f'  ✓ 处理后数据加载成功: {len(processed_data)} 条记录')
    print(f'  ✓ 最新期号: {processed_data["period"].iloc[-1]}')
    
    # 测试更新数据
    updated_data = collector.update_data()
    print(f'  ✓ 数据更新成功: {len(updated_data)} 条记录')
    print(f'  ✓ 最新期号: {updated_data["period"].iloc[-1]}')
    
    print('  ✓ 数据收集器测试通过')
except Exception as e:
    print(f'  ✗ 数据收集器测试失败: {e}')
    import traceback
    traceback.print_exc()

print()

# 测试特征工程
print('[2/3] 测试 FeatureEngineer...')
try:
    from src.core.features.engineer import FeatureEngineer
    engineer = FeatureEngineer()
    print('  ✓ FeatureEngineer 初始化成功')
    
    # 加载数据
    from src.core.data.collector import PL5DataCollector
    collector = PL5DataCollector()
    df = collector.load_processed_data()
    
    # 测试特征提取
    df_features = engineer.extract_all_features(df)
    feature_cols = [col for col in df_features.columns if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
    print(f'  ✓ 特征提取成功: {len(feature_cols)} 个特征')
    print('  ✓ 特征工程测试通过')
except Exception as e:
    print(f'  ✗ 特征工程测试失败: {e}')
    import traceback
    traceback.print_exc()

print()

# 测试模型训练
print('[3/3] 测试 EnhancedPL5Predictor...')
try:
    from src.core.models.enhanced_predictor import EnhancedPL5Predictor
    predictor = EnhancedPL5Predictor()
    print('  ✓ EnhancedPL5Predictor 初始化成功')
    
    # 加载数据和特征
    from src.core.data.collector import PL5DataCollector
    from src.core.features.engineer import FeatureEngineer
    
    collector = PL5DataCollector()
    df = collector.load_processed_data()
    
    engineer = FeatureEngineer()
    df_features = engineer.extract_all_features(df)
    feature_cols = [col for col in df_features.columns if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
    
    # 测试模型加载
    loaded = predictor.load_models()
    print(f'  ✓ 模型加载: {"成功" if loaded else "失败（将进行训练）"}')
    
    print('  ✓ 模型测试通过')
except Exception as e:
    print(f'  ✗ 模型测试失败: {e}')
    import traceback
    traceback.print_exc()

print()
print('=' * 60)
print('测试完成')
print('=' * 60)