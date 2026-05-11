"""
测试V12工作流调度表 V2.0
充分利用22.5小时时间窗口
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.agents.distributed.time_coordinator_v2 import TimeCoordinatorV2

def main():
    print('='*100)
    print('PL5 V12 - 多智能体时间协调系统 V2.0')
    print('='*100)

    coord = TimeCoordinatorV2(
        window_start_hour=22,
        window_end_hour=20,
        window_end_next_day=True
    )

    # 注册核心任务
    coord.register_task("数据采集", estimated_duration_minutes=15, priority=5, is_core_task=True)
    coord.register_task("模型评估", estimated_duration_minutes=10, priority=4, dependencies=["数据采集"], is_core_task=True)
    coord.register_task("策略优化", estimated_duration_minutes=15, priority=4, dependencies=["模型评估"], is_core_task=True)
    coord.register_task("模型训练", estimated_duration_minutes=30, priority=3, dependencies=["策略优化"], is_core_task=True)
    coord.register_task("增量训练", estimated_duration_minutes=20, priority=3, dependencies=["模型训练"], is_core_task=True)
    coord.register_task("第一次预测验证", estimated_duration_minutes=10, priority=2, dependencies=["增量训练"], is_core_task=True)
    coord.register_task("第二次预测验证", estimated_duration_minutes=10, priority=2, dependencies=["增量训练"], is_core_task=True)
    coord.register_task("第三次预测验证", estimated_duration_minutes=10, priority=2, dependencies=["增量训练"], is_core_task=True)
    coord.register_task("深度策略优化", estimated_duration_minutes=20, priority=2, dependencies=["第一次预测验证", "第二次预测验证", "第三次预测验证"], is_core_task=True)
    coord.register_task("预测预览", estimated_duration_minutes=5, priority=1, dependencies=["深度策略优化"], is_core_task=True)
    coord.register_task("最终预测", estimated_duration_minutes=15, priority=1, dependencies=["预测预览"], is_core_task=True)
    coord.register_task("最终预测验证", estimated_duration_minutes=5, priority=1, dependencies=["最终预测"], is_core_task=True)
    coord.register_task("售前预测", estimated_duration_minutes=5, priority=1, dependencies=["最终预测验证"], is_core_task=True)
    coord.register_task("发送报告", estimated_duration_minutes=10, priority=1, dependencies=["售前预测"], is_core_task=True)

    # 注册智能体
    coord.register_agent("data_agent", ["数据", "采集", "fetch", "data"])
    coord.register_agent("analysis_agent", ["评估", "优化", "策略", "evaluation", "optimization"])
    coord.register_agent("prediction_agent", ["预测", "训练", "prediction", "training"])
    coord.register_agent("report_agent", ["报告", "发送", "report", "send"])

    # 计算调度表
    schedule = coord.calculate_schedule()

    # 打印调度表
    coord.print_schedule(schedule)

if __name__ == '__main__':
    main()
