
"""简化后的check_intelligent_scheduling逻辑"""

import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

def simplified_check_intelligent_scheduling(now, data_fetch_time, send_report_time):
    """
    简化后的智能调度逻辑
    
    日循环周期：22:15 - 第二天20:15
    待机时间：21:00-22:00
    完成标准：生成最终预测结果即代表任务完成
    """
    
    standby_start_time = datetime.strptime('21:00', '%H:%M').time()
    
    # 计算周期边界
    today_2215 = datetime.combine(now.date(), data_fetch_time)        # 今天22:15
    tomorrow_2015 = datetime.combine(now.date() + timedelta(days=1), send_report_time)  # 明天20:15
    yesterday_2215 = datetime.combine(now.date() - timedelta(days=1), data_fetch_time)  # 昨天22:15
    today_2015 = datetime.combine(now.date(), send_report_time)       # 今天20:15
    
    in_daily_cycle = False
    cycle_start = None
    cycle_end = None
    
    # 判断是否在日循环周期内
    if now >= today_2215:
        # 今天22:15之后 → 日循环周期: 今天22:15 → 明天20:15
        cycle_start = today_2215
        cycle_end = tomorrow_2015
        in_daily_cycle = True
    elif now <= today_2015:
        # 今天20:15之前 → 日循环周期: 昨天22:15 → 今天20:15
        cycle_start = yesterday_2215
        cycle_end = today_2015
        in_daily_cycle = True
    else:
        # 20:15-22:00之间
        if now.time() >= standby_start_time and now.time() < data_fetch_time:
            # 21:00-22:00: 待机
            print(f"[智能调度] 系统待机时间 (21:00-22:00)，距下一个日循环还有 {(today_2215 - now).seconds // 60} 分钟")
        else:
            # 20:15-21:00: 不在日循环周期
            print(f"[智能调度] 不在日循环周期内，距下一个日循环还有 {(today_2215 - now).seconds // 60} 分钟")
        return False
    
    # 在日循环周期内
    if in_daily_cycle:
        print(f"[智能调度] 在日循环周期内 [{cycle_start.strftime('%Y-%m-%d %H:%M')} → {cycle_end.strftime('%Y-%m-%d %H:%M')}]")
        return True
    
    return False

# 测试场景
print("=" * 70)
print("简化版日循环逻辑测试")
print("=" * 70)

data_fetch_time = datetime.strptime('22:15', '%H:%M').time()
send_report_time = datetime.strptime('20:15', '%H:%M').time()

test_times = [
    ("20:00", datetime(2026, 5, 3, 20, 0, 0)),
    ("20:15", datetime(2026, 5, 3, 20, 15, 0)),
    ("20:30", datetime(2026, 5, 3, 20, 30, 0)),
    ("21:00", datetime(2026, 5, 3, 21, 0, 0)),
    ("21:30", datetime(2026, 5, 3, 21, 30, 0)),
    ("22:00", datetime(2026, 5, 3, 22, 0, 0)),
    ("22:30", datetime(2026, 5, 3, 22, 30, 0)),
]

print("\n时间点  | 状态")
print("-" * 40)
for time_str, now in test_times:
    result = simplified_check_intelligent_scheduling(now, data_fetch_time, send_report_time)
    print(f"{time_str:8s} | {'在日循环周期内' if result else '待机/不在周期'}")

print()
print("=" * 70)
print("设计总结:")
print("=" * 70)
print("日循环周期：22:15 - 第二天20:15")
print("待机时间：21:00-22:00")
print("完成标准：生成最终预测结果即代表任务完成")
print("智能调度：仅在任务未完成或重启时保证任务完成")
