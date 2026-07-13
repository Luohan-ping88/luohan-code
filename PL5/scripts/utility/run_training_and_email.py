#!/usr/bin/env python
"""
执行训练任务并检验邮件发送
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.app.auto_scheduler_v8 import AutoSchedulerV8

print('='*60)
print('PL5 系统训练与邮件发送测试')
print('='*60)
print()

scheduler = AutoSchedulerV8()

# 1. 执行数据获取
print('[1/5] 执行数据获取任务...')
result1 = scheduler.task_fetch_data()
print(f'      结果: {"成功" if result1 else "失败"}')
print()

# 2. 执行评估
print('[2/5] 执行评估分析任务...')
result2 = scheduler.task_evaluate()
print(f'      结果: {"成功" if result2 else "失败"}')
print()

# 3. 执行优化
print('[3/5] 执行策略优化任务...')
result3 = scheduler.task_optimize()
print(f'      结果: {"成功" if result3 else "失败"}')
print()

# 4. 执行训练
print('[4/5] 执行深度学习训练任务...')
print('      (训练可能需要几分钟时间...)')
result4 = scheduler.task_train()
print(f'      结果: {"成功" if result4 else "失败"}')
print()

# 5. 执行邮件发送
print('[5/5] 执行邮件发送任务...')
result5 = scheduler.task_send_report()
print(f'      结果: {"成功" if result5 else "失败"}')
print()

print('='*60)
print('任务执行完成!')
print('='*60)
print()
print('任务执行摘要:')
print(f'  数据获取: {"✓" if result1 else "✗"}')
print(f'  评估分析: {"✓" if result2 else "✗"}')
print(f'  策略优化: {"✓" if result3 else "✗"}')
print(f'  深度学习: {"✓" if result4 else "✗"}')
print(f'  邮件发送: {"✓" if result5 else "✗"}')
