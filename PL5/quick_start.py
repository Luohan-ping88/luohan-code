#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 系统快速启动脚本
直接启动优化后的系统
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.orchestrator_optimized import PL5OrchestratorOptimized
from src.core.events import get_event_bus


async def main():
    """主函数"""
    print("=" * 70)
    print("  PL5 排列五高阶数理分析预测系统 V8.0 (优化版)")
    print("=" * 70)
    print()

    # 打印系统信息
    event_bus = get_event_bus()
    print(f"事件总线统计: {event_bus.get_statistics()}")
    print()

    # 创建编排器
    print("初始化编排器...")
    orchestrator = PL5OrchestratorOptimized(
        workflow_dir="./workflows",
        default_timeout=3600
    )

    # 打印状态
    print("\n编排器状态:")
    status = orchestrator.get_status()
    for key, value in status.items():
        if key != "event_bus_stats":
            print(f"  {key}: {value}")

    print()

    # 执行预测
    print("执行预测流程...")
    print("-" * 70)

    result = await orchestrator.execute_prediction_pipeline()

    print("-" * 70)
    print()

    if result['success']:
        print("✅ 预测执行成功!")
        print(f"  执行ID: {result['execution_id']}")
        print(f"  执行时间: {result['execution_time']:.2f}秒")
        print(f"  下一期: {result['next_period']}")
        print()

        if 'predictions' in result:
            print("预测结果:")
            predictions = result['predictions']
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                if pos in predictions:
                    top_k = predictions[pos].get('top_k', [])
                    print(f"  {pos}: {', '.join(map(str, top_k[:5]))}")
    else:
        print("❌ 预测执行失败!")
        print(f"  错误: {result.get('error')}")
        print(f"  类型: {result.get('error_type')}")

    print()
    return result


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result['success'] else 1)
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 系统错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
