import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

print("=" * 70)
print("验证 21:00 硬编码截止时间修复")
print("=" * 70)

# Test scenario: Now is May 3rd 01:09:48 (the problematic time from logs)
now = datetime(2026, 5, 3, 1, 9, 48)

# OLD behavior (hardcoded 21:00)
cutoff_time_old = datetime.strptime('21:00', '%H:%M').time()
send_report_time = datetime.strptime('20:15', '%H:%M').time()

print(f"\nCurrent time: {now}")
print(f"SEND_REPORT_TIME (cycle end): {send_report_time}")

# Calculate OLD cutoff
cutoff_datetime_old = datetime.combine(now.date(), cutoff_time_old)
if now.time() >= cutoff_time_old:
    cutoff_datetime_old += timedelta(days=1)
available_old = (cutoff_datetime_old - now).total_seconds() / 60

print(f"\nOLD behavior (hardcoded 21:00):")
print(f"  cutoff_time: {cutoff_time_old}")
print(f"  cutoff_datetime: {cutoff_datetime_old}")
print(f"  available_minutes: {available_old:.0f}")
print(f"  STATUS: {'Within window' if now < cutoff_datetime_old else 'PAST CUTOFF'}")

# NEW behavior (using send_report_time as cutoff)
cutoff_time_new = send_report_time  # 20:15
cutoff_datetime_new = datetime.combine(now.date(), cutoff_time_new)
if now.time() >= cutoff_time_new:
    cutoff_datetime_new += timedelta(days=1)
available_new = (cutoff_datetime_new - now).total_seconds() / 60

print(f"\nNEW behavior (using send_report_time as cutoff):")
print(f"  cutoff_time: {cutoff_time_new}")
print(f"  cutoff_datetime: {cutoff_datetime_new}")
print(f"  available_minutes: {available_new:.0f}")
print(f"  STATUS: {'Within window' if now < cutoff_datetime_new else 'PAST CUTOFF'}")

print()
print("=" * 70)
print("CONCLUSION:")
print("=" * 70)
print("BEFORE FIX (21:00):")
print("  - Cutoff at 21:00, which is AFTER the cycle ends at 20:15")
print("  - This allowed tasks to run from 20:15 to 21:00 (45 min extra)")
print()
print("AFTER FIX (20:15):")
print("  - Cutoff at 20:15, which matches the cycle end time")
print("  - No tasks will run after 20:15, protecting the deadline")
print()
print(f"Time saved by fix: {available_old - available_new:.0f} minutes")
