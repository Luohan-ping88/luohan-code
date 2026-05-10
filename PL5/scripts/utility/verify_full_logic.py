import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

print("=" * 70)
print("完整流程分析: send_report 在 20:16 开始执行")
print("=" * 70)

data_fetch_time_str = '22:15'
send_report_time_str = '20:15'

data_fetch_time = datetime.strptime(data_fetch_time_str, '%H:%M').time()
send_report_time = datetime.strptime(send_report_time_str, '%H:%M').time()

now = datetime(2026, 5, 3, 20, 16, 0)  # send_report 在 20:16 开始

print(f"\nCurrent time: {now}")
print(f"data_fetch_time: {data_fetch_time}")
print(f"send_report_time: {send_report_time}")

# Step 1: Calculate cycle boundaries
today_22 = datetime.combine(now.date(), data_fetch_time)
tomorrow_2015 = datetime.combine(now.date() + timedelta(days=1), send_report_time)
yesterday_22 = datetime.combine(now.date() - timedelta(days=1), data_fetch_time)
today_2015 = datetime.combine(now.date(), send_report_time)

print(f"\nCycle boundaries:")
print(f"  today_22: {today_22}")
print(f"  tomorrow_2015: {tomorrow_2015}")
print(f"  yesterday_22: {yesterday_22}")
print(f"  today_2015: {today_2015}")

# Step 2: Determine which branch
print(f"\nDecision tree:")
print(f"  now >= today_22: {now >= today_22}")  # False (20:16 < 22:00)
print(f"  now > today_2015: {now > today_2015}")  # True (20:16 > 20:15)

if now >= today_22:
    print("\n  -> Branch: now >= today_22")
    cycle_start = today_22
    cycle_end = tomorrow_2015
    cutoff_datetime = datetime.combine(now.date() + timedelta(days=1), send_report_time)
    in_daily_cycle = True
    print(f"  cycle_start: {cycle_start}")
    print(f"  cycle_end: {cycle_end}")
    print(f"  cutoff_datetime: {cutoff_datetime}")
elif now > today_2015:
    print("\n  -> Branch: DEAD ZONE (20:15 < now < 22:00)")
    print("  -> check_intelligent_scheduling RETURNS EARLY!")
    print("  -> No catchup tasks will run")
    print()
    print("  BUT: schedule.every().day.at('20:15') will still trigger send_report!")
    print("  The send_report task is a SCHEDULED task, not a catchup task.")
    print("  It will run independently of check_intelligent_scheduling.")
    in_daily_cycle = False
elif now >= yesterday_22:
    print("\n  -> Branch: now >= yesterday_22")
else:
    print("\n  -> Branch: else")

print()
print("=" * 70)
print("结论:")
print("=" * 70)
print("1. check_intelligent_scheduling 在死区会直接返回，不执行补任务")
print("2. 但 send_report 是定时任务，由 schedule 库独立调度")
print("3. send_report 会在 20:15 触发，然后继续执行")
print("4. 即使执行到 20:18，send_report 也不会被 check_intelligent_scheduling 阻止")
print()
print("所以邮件应该能够正常发送！")
print()
print("但问题是: 如果 send_report 执行很慢 (比如 5-10 分钟) 呢?")
print("那就会在 20:20-20:25 完成，这超过了客户期望的 20:15 截止时间")
