#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5智能分析系统 - 哨兵服务启动脚本
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from monitor.sentinel_service import SentinelService
from src.core.utils import logger

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PL5智能分析系统 - 哨兵服务')
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--daemon', action='store_true', help='以守护进程模式运行')
    parser.add_argument('--status', action='store_true', help='查看当前状态')
    parser.add_argument('--start', action='store_true', help='启动服务')
    parser.add_argument('--stop', action='store_true', help='停止服务')
    
    args = parser.parse_args()
    
    sentinel = SentinelService(args.config)
    
    if args.status:
        # 查看状态
        status = sentinel.get_status()
        print("哨兵服务状态:")
        print(f"最后检查时间: {status.get('last_check', '未知')}")
        print(f"健康状态: {status.get('health_status', '未知')}")
        print(f"性能状态: {status.get('performance_status', '未知')}")
        print(f"告警数量: {len(status.get('alerts', []))}")
        print(f"恢复历史: {len(status.get('recovery_history', []))}")
        
        if status.get('alerts'):
            print("\n最近告警:")
            for alert in status['alerts'][-5:]:  # 只显示最近5条
                print(f"{alert.get('timestamp')} - {alert.get('level')}: {alert.get('message')}")
        
    elif args.start:
        # 启动服务
        print("启动哨兵服务...")
        sentinel.start()
        print("哨兵服务已启动！")
        
        # 如果不是守护进程模式，保持运行
        if not args.daemon:
            print("按 Ctrl+C 停止服务")
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n停止服务...")
                sentinel.stop()
                print("服务已停止")
        
    elif args.stop:
        # 停止服务
        print("停止哨兵服务...")
        sentinel.stop()
        print("服务已停止")
        
    else:
        # 默认启动
        print("启动哨兵服务...")
        sentinel.start()
        print("哨兵服务已启动！")
        print("按 Ctrl+C 停止服务")
        
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n停止服务...")
            sentinel.stop()
            print("服务已停止")


if __name__ == "__main__":
    main()