"""
测试V12工作流调度表 - 自适应特征版本
15个核心任务，总计910分钟
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.agents.distributed.time_coordinator_v3 import TimeCoordinatorV3

def main():
    print('='*100)
    print('PL5 V12 - 自适应特征工作流调度表')
    print('='*100)
    print('⚠️  核心任务：15个，总计910分钟（约15.2小时）')
    print('='*100)

    coord = TimeCoordinatorV3(
        window_start_hour=22,
        window_end_hour=20,
        window_end_next_day=True
    )

    # 注册15个核心任务
    coord.register_task("数据采集", estimated_duration_minutes=30, priority=5,
                        is_core_task=True, estimated_actual_minutes=30)
    coord.register_task("自适应特征选择", estimated_duration_minutes=60, priority=4,
                        dependencies=["数据采集"], is_core_task=True, estimated_actual_minutes=60)
    coord.register_task("模型评估", estimated_duration_minutes=20, priority=4,
                        dependencies=["自适应特征选择"], is_core_task=True, estimated_actual_minutes=20)
    coord.register_task("策略优化", estimated_duration_minutes=60, priority=4,
                        dependencies=["模型评估"], is_core_task=True, estimated_actual_minutes=60)
    coord.register_task("模型训练", estimated_duration_minutes=180, priority=3,
                        dependencies=["策略优化"], is_core_task=True, estimated_actual_minutes=180)
    coord.register_task("增量训练", estimated_duration_minutes=150, priority=3,
                        dependencies=["模型训练"], is_core_task=True, estimated_actual_minutes=150)
    coord.register_task("第一次预测验证", estimated_duration_minutes=40, priority=2,
                        dependencies=["增量训练"], is_core_task=True, estimated_actual_minutes=40)
    coord.register_task("第二次预测验证", estimated_duration_minutes=40, priority=2,
                        dependencies=["增量训练"], is_core_task=True, estimated_actual_minutes=40)
    coord.register_task("第三次预测验证", estimated_duration_minutes=40, priority=2,
                        dependencies=["增量训练"], is_core_task=True, estimated_actual_minutes=40)
    coord.register_task("深度策略优化", estimated_duration_minutes=120, priority=2,
                        dependencies=["第一次预测验证", "第二次预测验证", "第三次预测验证"],
                        is_core_task=True, estimated_actual_minutes=120)
    coord.register_task("预测预览", estimated_duration_minutes=30, priority=1,
                        dependencies=["深度策略优化"], is_core_task=True, estimated_actual_minutes=30)
    coord.register_task("最终预测", estimated_duration_minutes=60, priority=1,
                        dependencies=["预测预览"], is_core_task=True, estimated_actual_minutes=60)
    coord.register_task("最终预测验证", estimated_duration_minutes=20, priority=1,
                        dependencies=["最终预测"], is_core_task=True, estimated_actual_minutes=20)
    coord.register_task("售前预测", estimated_duration_minutes=30, priority=1,
                        dependencies=["最终预测验证"], is_core_task=True, estimated_actual_minutes=30)
    coord.register_task("发送报告", estimated_duration_minutes=30, priority=1,
                        dependencies=["售前预测"], is_core_task=True, estimated_actual_minutes=30)

    # 注册智能体
    coord.register_agent("data_agent", ["数据", "采集", "fetch", "data"])
    coord.register_agent("feature_agent", ["特征", "自适应", "feature", "adaptive"])
    coord.register_agent("analysis_agent", ["评估", "优化", "策略", "evaluation", "optimization"])
    coord.register_agent("prediction_agent", ["预测", "训练", "prediction", "training"])
    coord.register_agent("report_agent", ["报告", "发送", "report", "send"])

    # 计算调度表
    schedule = coord.calculate_schedule()

    # 打印调度表
    coord.print_schedule(schedule)

    # 验证总时间
    core_tasks = [s for s in schedule if s.is_core_task]
    total_core_minutes = sum(s.duration_minutes for s in core_tasks)

    print()
    print('='*100)
    print('✅ 验证结果')
    print('='*100)
    print(f'核心任务数量: {len(core_tasks)} 个')
    print(f'核心任务总时间: {total_core_minutes} 分钟 ({total_core_minutes/60:.1f} 小时)')
    print(f'是否满足800分钟要求: {"✅ 是" if total_core_minutes >= 800 else "❌ 否"}')
    print('='*100)

if __name__ == '__main__':
    main()
