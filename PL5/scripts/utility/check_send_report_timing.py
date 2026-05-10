import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

print("=" * 70)
print("分析 send_report 在 20:15 截止时间下的问题")
print("=" * 70)

send_report_time_str = '20:15'
send_report_time = datetime.strptime(send_report_time_str, '%H:%M').time()

print(f"\n配置:")
print(f"  pre_sale_prediction_time: 20:00")
print(f"  send_report_time: 20:15")
print(f"  cutoff_time: 20:15 (刚刚修复为与 send_report_time 一致)")

print()
print("问题分析:")
print("-" * 70)

# Scenario 1: send_report starts at exactly 20:15
now1 = datetime(2026, 5, 3, 20, 15, 0)
cutoff_datetime1 = datetime.combine(now1.date(), send_report_time)
if now1.time() >= send_report_time:
    cutoff_datetime1 += timedelta(days=1)

print(f"\n场景1: send_report 在 20:15:00 准时开始")
print(f"  now: {now1}")
print(f"  cutoff_datetime: {cutoff_datetime1}")
print(f"  now >= cutoff_datetime: {now1 >= cutoff_datetime1}")
print(f"  结果: {'会返回停止!' if now1 >= cutoff_datetime1 else '可以继续执行'}")

# Scenario 2: send_report starts at 20:16 (1 minute late)
now2 = datetime(2026, 5, 3, 20, 16, 0)
cutoff_datetime2 = datetime.combine(now2.date(), send_report_time)
if now2.time() >= send_report_time:
    cutoff_datetime2 += timedelta(days=1)

print(f"\n场景2: send_report 在 20:16:00 开始（晚1分钟）")
print(f"  now: {now2}")
print(f"  cutoff_datetime: {cutoff_datetime2}")
print(f"  now >= cutoff_datetime: {now2 >= cutoff_datetime2}")
print(f"  结果: {'会返回停止! 邮件无法发送!' if now2 >= cutoff_datetime2 else '可以继续执行'}")

# Scenario 3: send_report starts at 20:17 (2 minutes late)
now3 = datetime(2026, 5, 3, 20, 17, 0)
cutoff_datetime3 = datetime.combine(now3.date(), send_report_time)
if now3.time() >= send_report_time:
    cutoff_datetime3 += timedelta(days=1)

print(f"\n场景3: send_report 在 20:17:00 开始（晚2分钟）")
print(f"  now: {now3}")
print(f"  cutoff_datetime: {cutoff_datetime3}")
print(f"  now >= cutoff_datetime: {now3 >= cutoff_datetime3}")
print(f"  结果: {'会返回停止! 邮件无法发送!' if now3 >= cutoff_datetime3 else '可以继续执行'}")

print()
print("=" * 70)
print("结论: send_report 在 20:15 之后开始会被截止机制阻止!")
print("=" * 70)
print()
print("解决方案: 截止时间应该是 20:15 + send_report 任务预计耗时")
print("  - send_report 任务通常需要 1-3 分钟")
print("  - 所以截止时间应该设置为 20:18 或 20:20")
