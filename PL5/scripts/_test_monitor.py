import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "_monitor_test.txt")
try:
    from monitor.system_monitor import SystemMonitor
    msg = "OK: SystemMonitor imported"
except Exception as e:
    msg = "FAIL: " + traceback.format_exc()
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(msg + "\n")
print("done, see", OUT)
