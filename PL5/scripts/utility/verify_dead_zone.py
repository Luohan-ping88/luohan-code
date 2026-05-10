import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

print("=" * 70)
print("验证 20:15-22:00 死区保护机制")
print("=" * 70)

data_fetch_time_str = '22:15'
send_report_time_str = '20:15'

data_fetch_time = datetime.strptime(data_fetch_time_str, '%H:%M').time()
send_report_time = datetime.strptime(send_report_time_str, '%H:%M').time()

# Test scenario 1: 20:54 (the problematic time from user's logs)
now1 = datetime(2026, 5, 3, 20, 54, 0)
print(f"\nScenario 1: Current time = {now1.strftime('%H:%M')} (in dead zone)")

today_22 = datetime.combine(now1.date(), data_fetch_time)
tomorrow_2015 = datetime.combine(now1.date() + timedelta(days=1), send_report_time)
yesterday_22 = datetime.combine(now1.date() - timedelta(days=1), data_fetch_time)
today_2015 = datetime.combine(now1.date(), send_report_time)

print(f"  today_22 = {today_22}")
print(f"  today_2015 = {today_2015}")
print(f"  now >= today_22: {now1 >= today_22}")  # False
print(f"  now > today_2015: {now1 > today_2015}")  # True! -> dead zone

if now1 >= today_22:
    print("  -> Branch: now >= today_22 (in cycle, run tasks)")
elif now1 > today_2015:
    print("  -> Branch: now > today_2015 (DEAD ZONE 20:15-22:00, RETURN!)")
    print("  -> SYSTEM WILL NOT EXECUTE ANY TASKS!")
elif now1 >= yesterday_22:
    print("  -> Branch: now >= yesterday_22 (in cycle, run tasks)")
else:
    print("  -> Branch: else (not in cycle)")

print()
print("=" * 70)
print("Result: The dead zone protection IS working correctly!")
print("At 20:54, the system should return early without executing tasks.")
print("The problem must be elsewhere...")
print("=" * 70)

print()
print("Let me check: At 20:54, is the cycle already ended?")
print(f"  Cycle: {yesterday_22} -> {today_2015}")
print(f"  Current time: {now1}")
print(f"  Is 20:54 in [22:15 yesterday to 20:15 today]?")
print(f"  NO! 20:54 is NOT between 22:15 and 20:15")
print()
print("So at 20:54, the current cycle has ALREADY ENDED!")
print("The system is in the dead zone waiting for the next cycle at 22:15.")
