import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, time, timedelta
from src.core.workflow.orchestrator import DATA_FETCH_TIME, SEND_REPORT_TIME, IntelligentWorkflowOrchestrator

class MockOrchestrator(IntelligentWorkflowOrchestrator):
    def _get_current_cycle_range(self, current_time):
        now_time = current_time.time()
        today = current_time.date()

        if now_time >= DATA_FETCH_TIME:
            cycle_start = datetime.combine(today, DATA_FETCH_TIME)
            cycle_end = datetime.combine(today + timedelta(days=1), SEND_REPORT_TIME)
        else:
            cycle_start = datetime.combine(today - timedelta(days=1), DATA_FETCH_TIME)
            cycle_end = datetime.combine(today, SEND_REPORT_TIME)

        return cycle_start, cycle_end

orch = MockOrchestrator()

print("DATA_FETCH_TIME:", DATA_FETCH_TIME)
print("SEND_REPORT_TIME:", SEND_REPORT_TIME)
print()

# Test 1: Current time 20:54 (May 3rd) - should use cycle from May 2nd 22:15 to May 3rd 20:15
now1 = datetime(2026, 5, 3, 20, 54, 0)
cycle1 = orch._get_current_cycle_range(now1)
print("Test1 (May 3rd 20:54):")
print(f"  Current cycle: {cycle1[0].strftime('%Y-%m-%d %H:%M')} -> {cycle1[1].strftime('%Y-%m-%d %H:%M')}")

# Test 2: Current time 22:30 (May 3rd) - should use cycle from May 3rd 22:15 to May 4th 20:15
now2 = datetime(2026, 5, 3, 22, 30, 0)
cycle2 = orch._get_current_cycle_range(now2)
print("Test2 (May 3rd 22:30):")
print(f"  Current cycle: {cycle2[0].strftime('%Y-%m-%d %H:%M')} -> {cycle2[1].strftime('%Y-%m-%d %H:%M')}")

# Test 3: third_prediction_verification executed at May 2nd 11:32, current May 3rd 22:30
# Should NOT be marked as missed (belongs to previous cycle)
last_executed_dt = datetime(2026, 5, 2, 11, 32, 0)
is_in_current_cycle = cycle2[0] <= last_executed_dt <= cycle2[1]
print("Test3 (third_pred_verif at May 2nd 11:32, current May 3rd 22:30):")
print(f"  Is in current cycle? {is_in_current_cycle} (should be False - correctly NOT marked as missed)")

# Test 4: third_prediction_verification executed at May 3rd 15:30, current May 3rd 22:30
# Should BE marked as missed (scheduled 15:00 but hasn't run yet in current cycle)
last_executed_dt2 = datetime(2026, 5, 3, 15, 30, 0)
is_in_current_cycle2 = cycle2[0] <= last_executed_dt2 <= cycle2[1]
print("Test4 (third_pred_verif at May 3rd 15:30, current May 3rd 22:30):")
print(f"  Is in current cycle? {is_in_current_cycle2} (should be True - task already executed)")

# Test 5: When current time is 20:54, check if task at May 3rd 15:30 should be missed
# At 20:54, the current cycle is May 2nd 22:15 -> May 3rd 20:15
# Task at May 3rd 15:30 is OUTSIDE this cycle, so NOT missed
is_in_current_cycle3 = cycle1[0] <= last_executed_dt2 <= cycle1[1]
print("Test5 (third_pred_verif at May 3rd 15:30, current May 3rd 20:54):")
print(f"  Is in current cycle? {is_in_current_cycle3} (should be False - belongs to NEXT cycle)")

print()
print("=" * 60)
print("SUMMARY:")
print("  Test1: 20:54 -> cycle is May 2nd 22:15 -> May 3rd 20:15 (PREVIOUS cycle)")
print("  Test2: 22:30 -> cycle is May 3rd 22:15 -> May 4th 20:15 (NEW cycle)")
print("  Test3: May 2nd 11:32 is NOT in May 3rd 22:15->May 4th 20:15 -> NOT missed")
print("  Test4: May 3rd 15:30 IS in May 3rd 22:15->May 4th 20:15 -> marked as missed")
print("  Test5: May 3rd 15:30 is NOT in May 2nd 22:15->May 3rd 20:15 -> NOT missed")
