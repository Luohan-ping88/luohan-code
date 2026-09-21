import os
import sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
from src.core.workflow.orchestrator import DATA_FETCH_TIME, SEND_REPORT_TIME, TASK_SCHEDULED_TIMES

print('验证时间配置一致性:')
print(f'  DATA_FETCH_TIME: {DATA_FETCH_TIME}')
print(f'  SEND_REPORT_TIME: {SEND_REPORT_TIME}')
print(f'  TASK_SCHEDULED_TIMES["data_fetch"]: {TASK_SCHEDULED_TIMES["data_fetch"]}')
print(f'  TASK_SCHEDULED_TIMES["send_report"]: {TASK_SCHEDULED_TIMES["send_report"]}')
print()
print(f'  一致性检查:')
print(f'    DATA_FETCH_TIME == TASK_SCHEDULED_TIMES["data_fetch"]: {DATA_FETCH_TIME == TASK_SCHEDULED_TIMES["data_fetch"]}')
print(f'    SEND_REPORT_TIME == TASK_SCHEDULED_TIMES["send_report"]: {SEND_REPORT_TIME == TASK_SCHEDULED_TIMES["send_report"]}')
