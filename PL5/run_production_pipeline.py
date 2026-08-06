#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产模式日循环任务启动脚本
完整执行 14 步完整佐证链，无时限、不跳过任何子任务
执行完成后自动调用收尾脚本生成摘要+Top-8报告
"""
import sys
import os
import json
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))

LOGS_DIR = SCRIPT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

CYCLE_LOG = LOGS_DIR / "current_cycle_log.txt"
CYCLE_PID = LOGS_DIR / "current_cycle_pid.txt"


def tee_output(proc, log_fh):
    """将子进程 stdout 同时输出到控制台和日志文件"""
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        log_fh.write(line)
        log_fh.flush()


def main():
    print("=" * 80, flush=True)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PL5 生产模式日循环任务启动", flush=True)
    print(f"Python: {sys.version.split()[0]}", flush=True)
    print(f"Working Dir: {SCRIPT_DIR}", flush=True)
    print("=" * 80, flush=True)

    # 记录 PID
    with open(CYCLE_PID, 'w') as f:
        f.write(str(os.getpid()))

    # 打开日志
    log_fh = open(CYCLE_LOG, 'w', encoding='utf-8')
    log_fh.write(f"[{datetime.now()}] PRODUCTION PIPELINE START\n")
    log_fh.flush()

    # 主流程
    from src.app.auto_scheduler_v8 import AutoSchedulerV8

    pipeline_start = datetime.now()
    success = False
    try:
        scheduler = AutoSchedulerV8()
        success = scheduler.run_full_pipeline()
    except Exception as e:
        print(f"\n[FATAL] 主流程异常: {e}", flush=True)
        import traceback
        traceback.print_exc()
        log_fh.write(f"[FATAL] {e}\n")
        log_fh.write(traceback.format_exc())
    finally:
        pipeline_end = datetime.now()
        total_sec = (pipeline_end - pipeline_start).total_seconds()

    print("\n" + "=" * 80, flush=True)
    if success:
        print(f"[OK] 日循环管线 SUCCESS, 总耗时: {total_sec/3600:.2f} 小时", flush=True)
    else:
        print(f"[WARN] 日循环管线部分失败, 总耗时: {total_sec/3600:.2f} 小时", flush=True)
        print("       仍将尝试调用收尾脚本生成已有报告", flush=True)
    print("=" * 80, flush=True)

    log_fh.write(f"\n[{datetime.now()}] PIPELINE EXIT success={success} total_sec={total_sec:.0f}\n")
    log_fh.flush()

    # ── 调用自动收尾脚本 ──
    print("\n[启动收尾脚本] 生成摘要+Top-8报告+git提交推送", flush=True)
    ac_script = SCRIPT_DIR / "scripts" / "utility" / "auto_complete_daily_cycle.py"
    try:
        ac_proc = subprocess.Popen(
            [sys.executable, str(ac_script), str(os.getpid()), str(CYCLE_LOG)],
            cwd=str(SCRIPT_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        for line in ac_proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log_fh.write(line)
        ac_rc = ac_proc.wait(timeout=600)
        print(f"[收尾脚本] exit_code={ac_rc}", flush=True)
    except Exception as e:
        print(f"[收尾脚本调用失败] {e}", flush=True)

    log_fh.close()

    # 打印 done marker
    done_marker = LOGS_DIR / "auto_complete_done.json"
    if done_marker.exists():
        with open(done_marker, 'r', encoding='utf-8') as f:
            done = json.load(f)
        print("\n======= FINAL SUMMARY =======")
        print(json.dumps(done, indent=2, ensure_ascii=False))
    else:
        print(f"\n[WARN] 未找到 auto_complete_done.json: {done_marker}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
