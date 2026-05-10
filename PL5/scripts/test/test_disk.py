import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import psutil

paths_to_try = ['C:\\', 'C:/', '.', os.getcwd(), '/', '\\\\?\\C:\\']
for p in paths_to_try:
    try:
        du = psutil.disk_usage(p)
        print(f"  OK: disk_usage('{p}') = {du.percent}%")
    except Exception as e:
        print(f"  FAIL: disk_usage('{p}'): {e}")

# 使用 shutil
import shutil
try:
    total, used, free = shutil.disk_usage('C:\\')
    percent = used / total * 100 if total > 0 else 0
    print(f"  OK: shutil.disk_usage('C:\\\\') percent={percent:.1f}%")
except Exception as e:
    print(f"  FAIL: shutil: {e}")
