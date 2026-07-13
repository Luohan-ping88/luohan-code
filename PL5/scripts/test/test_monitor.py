"""测试 PerfectSystemMonitor 的 get_system_metrics"""
import sys, os, io, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

out_lines = []
def out(msg):
    out_lines.append(msg)
    print(msg, flush=True)

out("=== 测试 PerfectSystemMonitor ===")

try:
    from monitor.perfect_monitor import PerfectSystemMonitor
    out("  [OK] import success")
    m = PerfectSystemMonitor()
    out("  [OK] instantiated")
    try:
        metrics = m.get_system_metrics()
        out(f"  [OK] get_system_metrics() returned keys: {list(metrics.keys())}")
        out(f"  cpu.percent = {metrics.get('cpu', {}).get('percent')}")
        out(f"  memory.percent = {metrics.get('memory', {}).get('percent')}")
        disk = metrics.get('disk', {})
        out(f"  disk type = {type(disk)}, keys = {list(disk.keys()) if isinstance(disk, dict) else disk}")
    except Exception as e:
        out(f"  [FAIL] get_system_metrics: {e}")
        out(traceback.format_exc())

    # 直接测试 psutil.disk_usage
    import psutil
    try:
        du = psutil.disk_usage('C:\\')
        out(f"  psutil.disk_usage('C:\\\\') = total={du.total}, used={du.used}, percent={du.percent}")
        d = du._asdict()
        out(f"  _asdict() = {d}")
    except Exception as e:
        out(f"  [FAIL] psutil.disk_usage: {e}")
        out(traceback.format_exc())

except Exception as e:
    out(f"  [FAIL] import: {e}")
    out(traceback.format_exc())

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_monitor_result.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines))
