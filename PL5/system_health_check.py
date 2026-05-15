#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, 'e:/PL5')

print('=' * 80)
print('系统健康检查报告')
print('=' * 80)
print()

# 1. 配置文件检查
print('【1. 配置文件检查】')
config_file = Path('e:/PL5/src/config/scheduler_config_v8.json')
try:
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    print(f'✓ 配置文件语法正确: {config_file}')
    print(f'✓ 任务序列数量: {len(config.get("task_sequence", []))} 个任务')
    print()
except Exception as e:
    print(f'✗ 配置文件错误: {e}')
    print()

# 2. 任务方法完整性检查
print('【2. 任务方法完整性检查】')
task_methods = [
    'task_fetch_data',
    'task_evaluate',
    'task_optimize',
    'task_incremental_train',
    'task_train',
    'task_send_report',
    'task_final_prediction',
    'task_final_prediction_verification',
    'task_pre_sale_prediction',
    'task_first_prediction_verification',
    'task_deep_strategy_optimization',
    'task_prediction_preview'
]

scheduler_file = Path('e:/PL5/src/app/auto_scheduler_v8.py')
with open(scheduler_file, 'r', encoding='utf-8') as f:
    scheduler_code = f.read()

for method in task_methods:
    if f'def {method}' in scheduler_code:
        print(f'✓ {method} - 已实现')
    else:
        print(f'✗ {method} - 缺失')
print()

# 3. 调度时间点检查
print('【3. 调度时间点配置检查】')
time_keys = [
    'data_fetch_time',
    'evaluation_time',
    'optimization_start',
    'training_start',
    'incremental_training_morning',
    'first_prediction_verification',
    'incremental_training_noon',
    'incremental_training_afternoon',
    'deep_strategy_optimization',
    'prediction_preview',
    'final_prediction_time',
    'final_prediction_verification_time',
    'pre_sale_prediction_time',
    'email_send_time'
]

for key in time_keys:
    if key in config:
        print(f'✓ {key}: {config[key]}')
    else:
        print(f'✗ {key}: 缺失')
print()

# 4. 智能调度器检查
print('【4. 智能调度器检查】')
scheduler_file = Path('e:/PL5/src/core/workflow/intelligent_time_scheduler.py')
try:
    with open(scheduler_file, 'r', encoding='utf-8') as f:
        scheduler_code = f.read()

    critical_methods = [
        'get_current_strategy',
        'calculate_task_execution_window',
        'should_delay_task',
        'get_dynamic_schedule',
        'ensure_task_chain_completion',
        'get_optimal_task_sequence'
    ]

    for method in critical_methods:
        if f'def {method}' in scheduler_code:
            print(f'✓ {method} - 已实现')
        else:
            print(f'✗ {method} - 缺失')
    print()
except Exception as e:
    print(f'✗ 智能调度器检查失败: {e}')
    print()

# 5. 语法检查
print('【5. 语法检查】')
import py_compile

# 检查 auto_scheduler_v8.py
try:
    py_compile.compile('e:/PL5/src/app/auto_scheduler_v8.py', doraise=True)
    print('✓ auto_scheduler_v8.py 语法正确')
except py_compile.PyCompileError as e:
    print(f'✗ auto_scheduler_v8.py 语法错误: {e}')

# 检查 intelligent_time_scheduler.py
try:
    py_compile.compile('e:/PL5/src/core/workflow/intelligent_time_scheduler.py', doraise=True)
    print('✓ intelligent_time_scheduler.py 语法正确')
except py_compile.PyCompileError as e:
    print(f'✗ intelligent_time_scheduler.py 语法错误: {e}')
print()

print('=' * 80)
print('系统健康检查完成！')
print('=' * 80)