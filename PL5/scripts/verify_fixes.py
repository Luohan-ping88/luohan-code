#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证我们对 PL5 优化脚本的修复
"""

import sys
from pathlib import Path

# 添加项目根目录
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

print("="*80)
print("验证 PL5 检测审查优化脚本的修复")
print("="*80)

print("\n1. 测试 FeatureCacheManager 导入...")
try:
    from src.core.cache import FeatureCacheManager
    cache = FeatureCacheManager(max_size=100)
    print("   ✓ FeatureCacheManager 导入成功！")
    print(f"   缓存状态: {cache.stats}")
except Exception as e:
    print(f"   ✗ 导入失败: {e}")

print("\n2. 测试 SystemHealthMonitor 导入...")
try:
    from src.core.monitoring.health_monitor import SystemHealthMonitor
    monitor = SystemHealthMonitor()
    print("   ✓ SystemHealthMonitor 导入成功！")
except Exception as e:
    print(f"   ✗ 导入失败: {e}")

print("\n3. 检查特征工程窗口配置...")
try:
    from src.core.features.engineer_v10 import FeatureEngineerV10
    print("   ✓ FeatureEngineerV10 导入成功！")
    
    # 直接查看窗口配置
    with open(ROOT_DIR / 'src' / 'core' / 'features' / 'engineer_v10.py', 'r', encoding='utf-8') as f:
        content = f.read()
        import re
        # 查找时间序列特征的窗口
        ts_match = re.search(r'def _add_time_series_features.*?windows = (.*?)\n', content, re.DOTALL)
        if ts_match:
            print(f"   时间序列窗口配置: {ts_match.group(1)}")
        
        # 查找极值特征的窗口
        ext_match = re.search(r'def _add_extreme_features.*?windows = (.*?)\n', content, re.DOTALL)
        if ext_match:
            print(f"   极值特征窗口配置: {ext_match.group(1)}")
            
except Exception as e:
    print(f"   ✗ 检查失败: {e}")

print("\n" + "="*80)
print("验证完成！")
print("="*80)
