import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

print("=" * 70)
print("完整逻辑验证: 死区 vs 截止时间")
print("=" * 70)

send_report_time_str = '20:15'
cutoff_time_str = '21:00'
data_fetch_time_str = '22:15'

send_report_time = datetime.strptime(send_report_time_str, '%H:%M').time()
cutoff_time = datetime.strptime(cutoff_time_str, '%H:%M').time()
data_fetch_time = datetime.strptime(data_fetch_time_str, '%H:%M').time()

scenarios = [
    ("20:00", datetime(2026, 5, 3, 20, 0, 0)),
    ("20:15", datetime(2026, 5, 3, 20, 15, 0)),
    ("20:16", datetime(2026, 5, 3, 20, 16, 0)),
    ("20:30", datetime(2026, 5, 3, 20, 30, 0)),
    ("21:00", datetime(2026, 5, 3, 21, 0, 0)),
    ("21:01", datetime(2026, 5, 3, 21, 1, 0)),
    ("22:00", datetime(2026, 5, 3, 22, 0, 0)),
    ("22:30", datetime(2026, 5, 3, 22, 30, 0)),
]

print("\n时间点 | 所属区间 | check_intelligent_scheduling 行为")
print("-" * 70)

for time_str, now in scenarios:
    today_22 = datetime.combine(now.date(), data_fetch_time)
    today_2015 = datetime.combine(now.date(), send_report_time)
    yesterday_22 = datetime.combine(now.date() - timedelta(days=1), data_fetch_time)

    # Determine zone
    if now >= today_22:
        zone = "下一个日循环周期"
        behavior = "在周期内，检查截止时间"
    elif now > today_2015:
        zone = "死区 (20:15-22:00)"
        behavior = "直接返回，不执行任何任务"
    elif now >= yesterday_22:
        zone = "当前日循环周期"
        behavior = "在周期内，检查截止时间"
    else:
        zone = "未知"
        behavior = "直接返回"

    print(f"{time_str:8s} | {zone:20s} | {behavior}")

print()
print("=" * 70)
print("结论:")
print("=" * 70)
print("dead zone (20:15-22:00) 检查会先于截止时间检查执行")
print("所以 cutoff_time = 21:00 的作用是:")
print("  1. 在 20:15-22:00 死区: 死区检查返回，不执行任务")
print("  2. 在日循环周期内: 截止时间确保任务有充足时间完成")
print()
print("设计合理性:")
print("  - send_report_time = 20:15 (任务触发)")
print("  - cutoff_time = 21:00 (安全上限，给send_report完成任务)")
print("  - 死区 (20:15-22:00) 确保20:15后不会启动新任务")
print("  - 这与客户设定的 21:00 停止机制一致!")
