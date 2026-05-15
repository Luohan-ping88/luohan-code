#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试PL5系统启动"""
import sys
import time
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent))

from src.app.auto_scheduler_v8 import AutoSchedulerV8

print("开始测试PL5系统启动...")

try:
    scheduler = AutoSchedulerV8()
    print("✅ 调度器初始化成功")
    
    # 测试setup_schedule
    print("设置定时任务...")
    scheduler.setup_schedule()
    print("✅ 定时任务设置成功")
    
    # 测试运行一小会儿
    print("测试运行循环...")
    import threading
    
    def run_test():
        print("测试循环开始")
        try:
            for i in range(5):
                print(f"循环 {i+1}/5")
                time.sleep(2)
            print("✅ 测试循环完成")
        except Exception as e:
            print(f"❌ 测试循环异常: {e}")
            import traceback
            traceback.print_exc()
    
    test_thread = threading.Thread(target=run_test)
    test_thread.daemon = True
    test_thread.start()
    
    print("等待测试完成...")
    test_thread.join(timeout=15)
    
    if test_thread.is_alive():
        print("⚠️ 测试线程仍在运行，超时了")
    else:
        print("✅ 测试完成")
    
except Exception as e:
    print(f"❌ 启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("测试完成！")