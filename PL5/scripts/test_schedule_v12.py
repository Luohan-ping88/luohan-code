"""
测试V12工作流调度表
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.workflow.prefect_workflow_v12 import get_time_coordinator

def main():
    print('='*80)
    print('PL5 V12 - 多智能体时间协调系统')
    print('='*80)

    coord = get_time_coordinator()

    print('\n📋 时间窗口配置:')
    window = coord.get_time_window()
    print(f'   开始: {window.start.strftime("%Y-%m-%d %H:%M")}')
    print(f'   结束: {window.end.strftime("%Y-%m-%d %H:%M")}')
    print(f'   可用: {window.available_minutes} 分钟')

    print('\n📊 智能任务调度表:')
    print('='*80)

    schedule = coord.calculate_schedule()

    print(f'{"#":<3} {"任务":<35} {"开始":<10} {"结束":<10} {"优先级":<6} {"Agent":<15}')
    print('-'*80)

    for i, slot in enumerate(schedule, 1):
        print(
            f"{i:<3} {slot.task_name:<35} "
            f"{slot.start_time.strftime('%H:%M'):<10} "
            f"{slot.end_time.strftime('%H:%M'):<10} "
            f"{slot.priority:<6} "
            f"{slot.agent_assigned:<15}"
        )

    print('='*80)
    print(f'\n✅ 共调度 {len(schedule)} 个任务')
    print('   - 任务周期: 22:00 -> 次日 20:30')
    print('   - 时间协调: 多智能体智能分配')
    print('   - 好处: 充分的时间执行，避免空等')


if __name__ == '__main__':
    main()
