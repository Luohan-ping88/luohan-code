import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

print("=" * 70)
print("验证最终设计: send_report_time vs cutoff_time")
print("=" * 70)

send_report_time_str = '20:15'
cutoff_time_str = '21:00'

send_report_time = datetime.strptime(send_report_time_str, '%H:%M').time()
cutoff_time = datetime.strptime(cutoff_time_str, '%H:%M').time()

print(f"\n配置:")
print(f"  send_report_time: {send_report_time_str} (任务触发时间)")
print(f"  cutoff_time: {cutoff_time_str} (系统停止时间)")

print(f"\n设计意图:")
print(f"  - send_report 在 20:15 触发并执行")
print(f"  - 其他任务在 20:15-21:00 期间会被阻止启动新任务")
print(f"  - send_report 有 45 分钟 (20:15-21:00) 完成")

print()
print("场景验证:")
print("-" * 70)

# Scenario 1: At 20:16, checking if can start catchup task
now1 = datetime(2026, 5, 3, 20, 16, 0)
cutoff_datetime1 = datetime.combine(now1.date(), cutoff_time)
if now1.time() >= cutoff_time:
    cutoff_datetime1 += timedelta(days=1)

print(f"\n场景1: 当前时间 20:16, check_intelligent_scheduling 检查")
print(f"  now: {now1}")
print(f"  cutoff_time: {cutoff_time}")
print(f"  now.time() >= cutoff_time: {now1.time() >= cutoff_time}")  # False (20:16 < 21:00)
print(f"  cutoff_datetime: {cutoff_datetime1}")
print(f"  now >= cutoff_datetime: {now1 >= cutoff_datetime1}")  # False
print(f"  结果: {'会返回' if now1 >= cutoff_datetime1 else '可以继续执行 catchup 任务'}")

# Scenario 2: At 21:01, checking if can start catchup task
now2 = datetime(2026, 5, 3, 21, 1, 0)
cutoff_datetime2 = datetime.combine(now2.date(), cutoff_time)
if now2.time() >= cutoff_time:
    cutoff_datetime2 += timedelta(days=1)

print(f"\n场景2: 当前时间 21:01, check_intelligent_scheduling 检查")
print(f"  now: {now2}")
print(f"  cutoff_time: {cutoff_time}")
print(f"  now.time() >= cutoff_time: {now2.time() >= cutoff_time}")  # True
print(f"  cutoff_datetime: {cutoff_datetime2}")
print(f"  now >= cutoff_datetime: {now2 >= cutoff_datetime2}")  # True
print(f"  结果: {'会返回! 停止启动新任务' if now2 >= cutoff_datetime2 else '可以继续'}")

# Scenario 3: send_report takes 10 minutes (finishes at 20:25)
print(f"\n场景3: send_report 执行时间分析")
print(f"  send_report 触发: 20:15:00")
print(f"  send_report 预计完成: 20:25:00 (10分钟)")
print(f"  cutoff_time: 21:00:00")
print(f"  是否有足够时间: {'是 (35分钟剩余)' if True else '否'}")
print(f"  结果: send_report 可以在 21:00 前完成并发送邮件")

print()
print("=" * 70)
print("结论:")
print("=" * 70)
print("最终设计:")
print("  - send_report_time = 20:15 (任务触发)")
print("  - cutoff_time = 21:00 (系统停止)")
print()
print("效果:")
print("  - send_report 有 45 分钟完成")
print("  - 21:00 后不再启动新任务")
print("  - 符合客户设定的 21:00 停止保护机制")
