#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可靠的哨兵服务启动脚本
保持PL5系统和哨兵服务都在后台持续运行
"""
import os
import sys
import time
import subprocess
import threading
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_process_running(pid):
    """检查进程是否在运行"""
    try:
        os.kill(pid, 0)  # 发送信号0，不会杀死进程，但会检查是否存在
        return True
    except (OSError, ProcessLookupError):
        return False

def start_sentinel_and_pl5():
    """启动哨兵服务和PL5系统"""
    print("=" * 80)
    print("启动PL5智能分析系统 + 哨兵服务")
    print("=" * 80)
    
    # 先启动PL5主系统
    print("\n[1/2] 启动PL5主系统...")
    pl5_process = subprocess.Popen([
        sys.executable, '-m', 'src.app.auto_scheduler_v8'
    ], cwd=str(project_root))
    
    print(f"✅ PL5系统已启动，PID={pl5_process.pid}")
    
    # 等待PL5系统启动
    time.sleep(3)
    
    # 检查PL5系统是否在运行
    if pl5_process.poll() is not None:
        print(f"⚠️ PL5系统已退出，退出码={pl5_process.poll()}")
        return None, None
    
    print("\n[2/2] 启动哨兵服务...")
    # 启动哨兵服务
    sentinel_process = subprocess.Popen([
        sys.executable, str(project_root / 'start_sentinel.py'), '--start'
    ], cwd=str(project_root))
    
    print(f"✅ 哨兵服务已启动，PID={sentinel_process.pid}")
    
    print("\n" + "=" * 80)
    print("系统已完全启动！")
    print(f"  PL5主系统 PID: {pl5_process.pid}")
    print(f"  哨兵服务 PID: {sentinel_process.pid}")
    print("=" * 80)
    
    return pl5_process, sentinel_process

def monitor_processes(pl5_process, sentinel_process):
    """监控进程状态"""
    print("\n开始监控进程状态... (按 Ctrl+C 停止)")
    print("-" * 80)
    
    try:
        while True:
            # 检查PL5系统
            if pl5_process.poll() is not None:
                print(f"⚠️ PL5系统已退出！退出码={pl5_process.poll()}")
                print("尝试重新启动PL5系统...")
                
                # 重新启动PL5系统
                pl5_process = subprocess.Popen([
                    sys.executable, '-m', 'src.app.auto_scheduler_v8'
                ], cwd=str(project_root))
                
                print(f"✅ PL5系统已重新启动，新PID={pl5_process.pid}")
            
            # 检查哨兵服务
            if sentinel_process.poll() is not None:
                print(f"⚠️ 哨兵服务已退出！退出码={sentinel_process.poll()}")
                print("哨兵服务不会自动重启，请手动重新启动")
                break
            
            # 打印状态
            current_time = time.strftime('%Y-%m-%d %H:%M:%S')
            pl5_status = "✅ 运行中" if pl5_process.poll() is None else "❌ 已停止"
            sentinel_status = "✅ 运行中" if sentinel_process.poll() is None else "❌ 已停止"
            
            print(f"[{current_time}] PL5: {pl5_status} | 哨兵: {sentinel_status}", end='\r')
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n收到停止信号...")
    
    return pl5_process, sentinel_process

def stop_processes(pl5_process, sentinel_process):
    """停止所有进程"""
    print("\n正在停止系统...")
    
    if pl5_process and pl5_process.poll() is None:
        print(f"停止PL5系统 (PID={pl5_process.pid})...")
        try:
            pl5_process.terminate()
            time.sleep(2)
            if pl5_process.poll() is None:
                pl5_process.kill()
        except:
            pass
    
    if sentinel_process and sentinel_process.poll() is None:
        print(f"停止哨兵服务 (PID={sentinel_process.pid})...")
        try:
            sentinel_process.terminate()
            time.sleep(2)
            if sentinel_process.poll() is None:
                sentinel_process.kill()
        except:
            pass
    
    print("✅ 系统已完全停止")

if __name__ == '__main__':
    pl5_process = None
    sentinel_process = None
    
    try:
        pl5_process, sentinel_process = start_sentinel_and_pl5()
        
        if pl5_process and sentinel_process:
            pl5_process, sentinel_process = monitor_processes(pl5_process, sentinel_process)
    
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if pl5_process or sentinel_process:
            stop_processes(pl5_process, sentinel_process)
        
        print("\n再见！")