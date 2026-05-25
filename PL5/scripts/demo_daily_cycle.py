#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日循环工作流演示脚本
展示如何使用新的深度训练、增量训练和预测链路聚合功能。
"""
import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.utils.logger import get_logger
from src.core.training import DailyCycleOrchestrator

# 配置日志
logger = get_logger('demo')


def main():
    """运行日循环演示"""
    print("=" * 80)
    print("PL5 日循环工作流演示 - V11")
    print("=" * 80)
    
    # 1. 初始化日循环协调器
    logger.info("初始化日循环协调器...")
    orchestrator = DailyCycleOrchestrator()
    
    # 2. 运行完整日循环
    logger.info("开始运行完整日循环...")
    success = orchestrator.run_full_cycle()
    
    # 3. 打印总结
    print("\n" + "=" * 80)
    print("日循环执行总结")
    print("=" * 80)
    
    summary = orchestrator.get_summary()
    
    print(f"\n循环日期: {summary['cycle_date']}")
    print("\n阶段状态:")
    for phase, status in summary['phase_statuses'].items():
        status_icon = "✓" if status == 'completed' else "⚠" if status == 'in_progress' else "✗"
        print(f"  {status_icon} {phase}: {status}")
    
    if summary['errors']:
        print("\n错误信息:")
        for error in summary['errors']:
            print(f"  - {error['phase']}: {error['error']}")
    
    # 4. 检查结果
    final_prediction = summary.get('results', {}).get('final_prediction')
    if final_prediction:
        print("\n最终预测结果:")
        predictions = final_prediction.get('final_predictions', {})
        for pos, pred in predictions.items():
            print(f"  {pos} 位: Top 3 = {pred.get('top_3', [])}, 置信度 = {final_prediction.get('confidence_scores', {}).get(pos, 0):.2%}")
    
    print("\n" + "=" * 80)
    if success:
        print("日循环演示完成 ✓")
    else:
        print("日循环演示部分完成 ⚠")
    print("=" * 80)
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"演示失败: {e}", exc_info=True)
        print(f"\n错误: {e}")
        sys.exit(1)
