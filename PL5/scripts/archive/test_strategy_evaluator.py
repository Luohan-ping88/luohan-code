#!/usr/bin/env python3
"""
测试策略评估器修复效果
"""

import sys
import logging
from src.core.strategy_evaluator import StrategyEvaluator

# 设置日志级别
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_strategy_evaluation():
    """测试策略评估器"""
    print("=" * 80)
    print("测试策略评估器修复效果")
    print("=" * 80)
    
    try:
        evaluator = StrategyEvaluator()
        
        # 使用小窗口进行测试，加快速度
        test_window = 5
        print(f"使用测试窗口: {test_window} 期")
        print()
        
        # 评估所有策略
        result = evaluator.evaluate_all_strategies(test_window=test_window)
        
        # 生成报告
        report = evaluator.get_strategy_comparison_report(result)
        print(report)
        
        # 检查是否有成功的策略
        strategies = result.get('strategies', {})
        success_count = sum(1 for s in strategies.values() if s.get('success', False))
        
        print(f"\n测试结果: 成功 {success_count}/{len(strategies)} 个策略")
        
        if success_count > 0:
            print("✅ 策略评估器修复成功！")
        else:
            print("❌ 所有策略评估失败，需要进一步检查")
            
        return success_count > 0
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_strategy_evaluation()
    sys.exit(0 if success else 1)
