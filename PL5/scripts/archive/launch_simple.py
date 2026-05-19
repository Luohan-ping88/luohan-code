#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单启动脚本 - 直接启动PL5系统
"""
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 启动PL5系统
from src.app.auto_scheduler_v8 import AutoSchedulerV8


def main():
    print("="*80)
    print("排列五智能自动化学习分析系统 V10.0 启动")
    print("="*80)
    
    # 创建调度器
    scheduler = AutoSchedulerV8()
    
    # 运行
    scheduler.run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n系统已停止")
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")
