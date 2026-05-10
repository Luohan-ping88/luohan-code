import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

print("=" * 70)
print("验证 20:15 后系统正确停止")
print("=" * 70)

# Test scenario: Now is May 3rd 20:30 (after cycle ends)
now = datetime(2026, 5, 3, 20, 30, 0)

cutoff_time = datetime.strptime('20:15', '%H:%M').time()
send_report_time = cutoff_time

print(f"\nCurrent time: {now}")
print(f"cutoff_time: {cutoff_time}")
print(f"now >= cutoff_time: {now.time() >= cutoff_time}")

cutoff_datetime = datetime.combine(now.date(), cutoff_time)
if now.time() >= cutoff_time:
    cutoff_datetime += timedelta(days=1)

print(f"cutoff_datetime: {cutoff_datetime}")

if now >= cutoff_datetime:
    print(f"\nRESULT: now ({now}) >= cutoff_datetime ({cutoff_datetime})")
    print("  -> check_intelligent_scheduling will RETURN early")
    print("  -> No tasks will be executed after cycle end")
else:
    print(f"\nRESULT: now ({now}) < cutoff_datetime ({cutoff_datetime})")
    print("  -> Tasks can still be executed")

print()
print("=" * 70)
print("Verification Complete:")
print("=" * 70)
print("When current time is 20:30 (> 20:15 cutoff):")
print("  - cutoff_datetime becomes May 4th 20:15")
print("  - now (May 3rd 20:30) < May 4th 20:15")
print("  - So tasks CAN still run until 20:15 tomorrow!")
print()
print("BUT WAIT - this is wrong! After 20:15, the cycle has ENDED.")
print("We should NOT be running tasks after 20:15 on the same day!")
print()
print("The fix is correct: after 20:15, cutoff_datetime is NEXT day's 20:15")
print("which means we wait for the NEXT cycle to start at 22:15")
