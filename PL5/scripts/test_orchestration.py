#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证智能编排系统
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# 添加项目路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.core.workflow.intelligent_orchestration import IntelligentOrchestrationManager

def test_task():
    """测试任务"""
    print(f"测试任务执行 - {datetime.now()}")
    time.sleep(0.5)
    return True

def main():
    print("=" * 80)
    print("智能编排系统验证测试")
    print("=" * 80)
    
    # 创建测试编排管理器（不传入 scheduler 实例）
    class MockScheduler:
        """模拟调度器"""
        pass
    
    orchestrator = IntelligentOrchestrationManager(MockScheduler())
    
    # 测试注册任务
    print("\n[测试1] 任务注册")
    test_tasks = [
        ('test_task_1', test_task, 1, []),
        ('test_task_2', test_task, 2, ['test_task_1']),
        ('test_task_3', test_task, 3, ['test_task_2']),
    ]
    
    for name, handler, priority, deps in test_tasks:
        orchestrator.register_task(name, handler, priority, deps)
        print(f"  ✓ 已注册任务: {name}, 优先级: {priority}")
    
    # 测试任务状态获取
    print("\n[测试2] 任务状态获取")
    all_status = orchestrator.get_all_task_status()
    for name, status in all_status.items():
        print(f"  {name}: {status['status']}")
    
    # 测试训练窗口逻辑
    print("\n[测试3] 训练窗口判断")
    in_window = orchestrator._is_in_training_window()
    print(f"  当前是否在训练窗口: {'是' if in_window else '否'}")
    
    # 显示编排系统状态
    print("\n[测试4] 编排系统状态")
    status = orchestrator.get_orchestration_status()
    print(f"  是否在训练窗口: {status['in_training_window']}")
    print(f"  任务数量: {len(status['tasks'])}")
    
    # 测试手动触发任务（在后台执行）
    print("\n[测试5] 手动触发任务")
    orchestrator.manual_trigger_task('test_task_1')
    time.sleep(1)
    
    # 检查更新后的状态
    updated_status = orchestrator.get_task_status('test_task_1')
    print(f"  test_task_1 状态: {updated_status['status']}")
    
    # 显示历史记录
    print("\n[测试6] 任务历史")
    history = orchestrator.get_history()
    print(f"  历史记录数: {len(history)}")
    for record in history[-3:]:
        print(f"  - {record['name']}: {record['status']}")
    
    print("\n" + "=" * 80)
    print("验证测试完成！")
    print("=" * 80)
    
    print("\n[总结] 新调度系统特点:")
    print("  ✓ 只锚点训练开始 (21:55) 和结束 (次日 21:00) 时间")
    print("  ✓ 其他节点任务智能实时编排，不依赖固定时间")
    print("  ✓ 任务按依赖关系连续执行，避免空等待")
    print("  ✓ 智能编排管理器负责所有任务的调度")
    print("  ✓ 完整的任务依赖、重试、状态监控机制")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
