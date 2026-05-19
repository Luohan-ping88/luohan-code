#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PL5智能系统启动器"""

import os
import sys
import time
import subprocess
from pathlib import Path

# 设置编码环境
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# 切换到项目根目录
script_dir = Path(__file__).parent
os.chdir(script_dir)

print("=" * 80)
print("排列五智能分析系统 - 启动器")
print("=" * 80)
print()

# 启动防睡眠
print("[启动防睡眠保护...]")
try:
    subprocess.Popen([
        sys.executable,
        str(script_dir / "monitor" / "prevent_sleep.py")
    ],
    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
    print("[OK] 防睡眠保护已启动")
except Exception as e:
    print(f"[警告] 防睡眠启动失败: {e}")

print()
print("[启动主系统...]")
print()

# 启动主系统
from src.app.auto_scheduler_v8 import AutoSchedulerV8

try:
    scheduler = AutoSchedulerV8()
    scheduler.run()
except KeyboardInterrupt:
    print("\n系统已停止")
except Exception as e:
    print(f"\n系统异常: {e}")
    import traceback
    traceback.print_exc()
    input("\n按回车退出...")
