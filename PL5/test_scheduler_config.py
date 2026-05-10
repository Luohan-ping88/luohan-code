#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试定时任务配置
验证定时任务时间顺序是否正确
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from src.app.auto_scheduler_v8 import AutoSchedulerV8

def test_scheduler_config():
    """测试定时任务配置"""
    print("=" * 80)
    print("测试定时任务配置")
    print("=" * 80)
    
    try:
        # 初始化调度器
        scheduler = AutoSchedulerV8()
        
        # 打印配置信息
        print("当前定时任务配置:")
        print(f"  数据获取时间: {scheduler.config.get('data_fetch_time')}")
        print(f"  评估时间: {scheduler.config.get('evaluation_time')}")
        print(f"  优化时间: {scheduler.config.get('optimization_start')}")
        print(f"  训练时间: {scheduler.config.get('training_start')}")
        print(f"  上午增量训练: {scheduler.config.get('incremental_training_morning')}")
        print(f"  首次预测验证: {scheduler.config.get('first_prediction_verification')}")
        print(f"  中午增量训练: {scheduler.config.get('incremental_training_noon')}")
        print(f"  下午增量训练: {scheduler.config.get('incremental_training_afternoon')}")
        print(f"  深度策略优化: {scheduler.config.get('deep_strategy_optimization')}")
        print(f"  预测预生成: {scheduler.config.get('prediction_preview')}")
        print(f"  最终预测: {scheduler.config.get('final_prediction_time')}")
        print(f"  最终预测验证: {scheduler.config.get('final_prediction_verification_time')}")
        print(f"  售前最终预测: {scheduler.config.get('pre_sale_prediction_time')}")
        print(f"  邮件发送时间: {scheduler.config.get('email_send_time')}")
        
        # 验证时间顺序
        print("\n验证时间顺序:")
        
        # 提取关键任务时间
        data_fetch = scheduler.config.get('data_fetch_time')
        evaluation = scheduler.config.get('evaluation_time')
        optimization = scheduler.config.get('optimization_start')
        training = scheduler.config.get('training_start')
        
        print(f"  1. 数据获取: {data_fetch}")
        print(f"  2. 评估分析: {evaluation}")
        print(f"  3. 策略优化: {optimization}")
        print(f"  4. 深度训练: {training}")
        
        # 验证时间顺序是否合理
        # 这里简化处理，只检查时间字符串的顺序
        # 注意：需要考虑跨天的情况
        def time_to_minutes(time_str):
            """将时间字符串转换为分钟数"""
            hour, minute = map(int, time_str.split(':'))
            return hour * 60 + minute
        
        data_fetch_min = time_to_minutes(data_fetch)
        evaluation_min = time_to_minutes(evaluation)
        optimization_min = time_to_minutes(optimization)
        training_min = time_to_minutes(training)
        
        # 检查时间顺序
        # 考虑跨天的情况，例如23:30到00:30
        if data_fetch_min <= evaluation_min <= optimization_min <= training_min:
            print("\n✓ 时间顺序正确")
        elif data_fetch_min <= evaluation_min <= optimization_min and training_min < data_fetch_min:
            print("\n✓ 时间顺序正确（跨天）")
        else:
            print("\n✗ 时间顺序错误")
        
        print("\n" + "=" * 80)
        print("测试完成")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        return False

if __name__ == "__main__":
    test_scheduler_config()
