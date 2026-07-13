import sys
sys.path.insert(0, 'e:/PL5')
from datetime import datetime, timedelta

print("=" * 70)
print("验证修复: _get_current_cycle_date() 死区返回明天")
print("=" * 70)

DATA_FETCH_TIME = datetime.strptime('22:15', '%H:%M').time()
SEND_REPORT_TIME = datetime.strptime('20:15', '%H:%M').time()

def fixed_get_current_cycle_date(now):
    current_time = now.time()
    if current_time >= DATA_FETCH_TIME:
        return (now + timedelta(days=1)).date()
    elif current_time <= SEND_REPORT_TIME:
        return now.date()
    else:
        return (now + timedelta(days=1)).date()

def old_get_current_cycle_date(now):
    current_time = now.time()
    if current_time >= DATA_FETCH_TIME:
        return (now + timedelta(days=1)).date()
    elif current_time <= SEND_REPORT_TIME:
        return now.date()
    else:
        return now.date()

test_times = [
    ("22:01 (刚启动)",     datetime(2026, 5, 3, 22, 1, 0),  "May 3"),
    ("22:30 (周期内)",     datetime(2026, 5, 3, 22, 30, 0), "May 3"),
    ("00:30 (深度训练)",   datetime(2026, 5, 4, 0, 30, 0),  "May 4"),
    ("12:00 (周期内)",     datetime(2026, 5, 4, 12, 0, 0),  "May 4"),
    ("20:30 (死区)",       datetime(2026, 5, 4, 20, 30, 0), "May 4"),
]

print("\n场景                     | 旧逻辑(错误) | 新逻辑(修复) | 保存状态 cycle_date | 是否重置")
print("-" * 100)

# Simulate: saved state has cycle_date = "2026-05-03" (previous cycle)
SAVED_CYCLE_DATE = datetime(2026, 5, 3).date()

for label, now, belongs_to_day in test_times:
    old_result = old_get_current_cycle_date(now)
    new_result = fixed_get_current_cycle_date(now)
    old_match = old_result == SAVED_CYCLE_DATE
    new_match = new_result == SAVED_CYCLE_DATE
    
    old_action = "不重置 ❌ (加载旧状态!)" if old_match else "重置 ✅"
    new_action = "不重置 ❌" if new_match else "重置 ✅"
    
    print(f"{label:25s} | {old_result} → {old_action:30s} | {new_result} → {new_action}")

print()
print("=" * 70)
print("结论:")
print("=" * 70)
print("旧逻辑: 22:01 (死区) 返回 May 3, 匹配保存的 May 3 → 加载旧状态 ❌")
print("新逻辑: 22:01 (死区) 返回 May 4, 不匹配保存的 May 3 → 重置状态 ✅")
print()
print("这解释了为什么 data_fetch 完成后 orchestrator 认为'工作流已全部完成'")
print("因为旧状态中所有14个任务都是 COMPLETED!")
