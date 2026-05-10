import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

# Simulate the check_intelligent_scheduling logic
data_fetch_time_str = '22:15'
cutoff_time_str = '21:00'
send_report_time_str = '20:15'

data_fetch_time = datetime.strptime(data_fetch_time_str, '%H:%M').time()
cutoff_time = datetime.strptime(cutoff_time_str, '%H:%M').time()
send_report_time = datetime.strptime(send_report_time_str, '%H:%M').time()

# Test case: Now is May 3rd 01:09:48 (the log shows this)
now = datetime(2026, 5, 3, 1, 9, 48)

# Calculate cycle boundaries (same as scheduler does)
today_22 = datetime.combine(now.date(), data_fetch_time)
tomorrow_2015 = datetime.combine(now.date() + timedelta(days=1), send_report_time)
yesterday_22 = datetime.combine(now.date() - timedelta(days=1), data_fetch_time)
today_2015 = datetime.combine(now.date(), send_report_time)

print(f"Current time: {now}")
print()

if now >= today_22:
    print("Branch: now >= today_22")
    cycle_start = today_22
    cycle_end = tomorrow_2015
    cutoff_datetime = datetime.combine(now.date() + timedelta(days=1), cutoff_time)
    in_daily_cycle = True
elif now > today_2015:
    print("Branch: now > today_2015 (dead zone 20:15-22:00)")
    cycle_start = None
    cycle_end = None
    cutoff_datetime = None
    in_daily_cycle = False
elif now >= yesterday_22:
    print("Branch: now >= yesterday_22")
    cycle_start = yesterday_22
    cycle_end = today_2015
    cutoff_datetime = datetime.combine(now.date(), cutoff_time)
    in_daily_cycle = True
else:
    print("Branch: else")
    cycle_start = None
    cycle_end = None
    cutoff_datetime = None
    in_daily_cycle = False

print(f"  in_daily_cycle: {in_daily_cycle}")
if cycle_start:
    print(f"  cycle_start: {cycle_start}")
    print(f"  cycle_end: {cycle_end}")
if cutoff_datetime:
    print(f"  cutoff_datetime: {cutoff_datetime}")
    available_minutes = (cutoff_datetime - now).total_seconds() / 60
    print(f"  available_minutes (from current logic): {available_minutes:.0f}")

    # Check if past cutoff
    if now >= cutoff_datetime:
        print(f"  STATUS: PAST CUTOFF - should stop and wait for next cycle")
    else:
        print(f"  STATUS: Within cutoff window - should continue")

print()
print("=" * 60)
print("EXPECTED BEHAVIOR:")
print("  At 01:09 on May 3rd, we are in cycle May 2nd 22:15 -> May 3rd 20:15")
print("  Cutoff is 21:00 today (May 3rd)")
print("  Time remaining = 21:00 - 01:09 = 19 hours 51 min = 1191 minutes")
print("  BUT THE LOG SHOWED 1190 minutes - this is CORRECT!")
print()
print("  So the cutoff protection IS working - it's calculating ~1190 minutes")
print("  correctly. The issue is that the 21:00 cutoff is for the SAME DAY")
print("  (May 3rd), not the current cycle end (May 3rd 20:15).")
print()
print("  Actually WAIT - cutoff is 21:00 but cycle ends at 20:15!")
print("  So after 20:15, the cycle ends but cutoff is still 21:00!")
print("  This means from 20:15 to 21:00, we are in a weird state:")
print("    - Cycle has ended (20:15)")
print("    - But cutoff hasn't reached yet (21:00)")
print("  This is likely a bug in the logic!")
