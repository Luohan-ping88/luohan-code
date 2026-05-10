#!/usr/bin/env python3
"""
测试动态特征验证器
"""

import sys
import os
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.features.dynamic_validator import DynamicFeatureValidator
from src.core.utils.logger import setup_logging

# 设置日志
setup_logging('test_dynamic_feature_validator')
logger = logging.getLogger(__name__)


def test_dynamic_feature_validator():
    """测试动态特征验证器"""
    print("=" * 80)
    print("测试动态特征验证器")
    print("=" * 80)
    
    start_time = datetime.now()
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 创建动态特征验证器
        validator = DynamicFeatureValidator()
        
        # 验证并更新特征配置
        result = validator.validate_and_update_features()
        
        print(f"\n验证结果: {result}")
        
        if result['success']:
            best_config = result['best_config']
            print(f"\n最佳特征配置: {best_config}")
            
            # 获取最佳特征配置
            current_best = validator.get_best_feature_config()
            print(f"当前最佳特征配置: {current_best}")
        else:
            print(f"\n验证失败: {result['error']}")
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        print(f"\n结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"执行时间: {elapsed:.2f} 秒")
        
        return True
        
    except Exception as e:
        logger.error(f"测试动态特征验证器失败: {e}")
        return False


if __name__ == "__main__":
    test_dynamic_feature_validator()
