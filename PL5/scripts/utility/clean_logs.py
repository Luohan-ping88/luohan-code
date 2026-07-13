#!/usr/bin/env python3
"""
PL5 日志清理脚本 V2.0（统一日志结构版）
保留：logs/system.log(轮转), logs/system.json.log, logs/data/*, logs/*.pkl
清理：logs/archive/*（旧日志备份）
"""
import shutil
from pathlib import Path

BASE = Path(__file__).parent.parent.parent
LOGS = BASE / 'logs'
DATA = LOGS / 'data'
ARCHIVE = LOGS / 'archive'


def clean():
    print("=" * 50)
    print("PL5 日志清理")
    print("=" * 50)

    # 清理 archive 目录（旧日志备份）
    if ARCHIVE.exists():
        count = len(list(ARCHIVE.iterdir()))
        shutil.rmtree(ARCHIVE)
        print(f"  [清理] archive/ ({count} 文件)")

    # 清理空目录
    for d in [LOGS, DATA, ARCHIVE]:
        if d.exists():
            try:
                d.rmdir()  # 只删空目录
            except OSError:
                pass

    # 统计
    remaining = []
    remaining += list(LOGS.glob('*'))
    remaining += list(DATA.glob('*')) if DATA.exists() else []
    total_size = sum(f.stat().st_size for f in remaining if f.is_file())

    print(f"\n  剩余: {len(remaining)} 文件, {total_size / 1024:.0f} KB")
    print("  保留: system.log(轮转)  system.json.log  data/*  *.pkl")
    print("=" * 50)


if __name__ == '__main__':
    import sys
    clean()
