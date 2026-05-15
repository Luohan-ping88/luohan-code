#!/usr/bin/env python3
"""
PL5 24小时持续监控系统 - 启动器
支持交互式和后台运行模式
"""

import os
import sys
import time
import signal
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path("/workspace/PL5")
sys.path.insert(0, str(PROJECT_ROOT))

def print_banner():
    """打印横幅"""
    print("=" * 80)
    print(" PL5 24小时持续监控系统")
    print("=" * 80)
    print(f" 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" 日志目录: {PROJECT_ROOT / 'logs' / 'daily_audit'}")
    print("=" * 80)
    print()

def check_dependencies():
    """检查依赖"""
    print("[1/4] 检查依赖...")

    required_modules = [
        'numpy', 'pandas', 'sklearn', 'requests',
        'psutil', 'pytest'
    ]

    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)

    if missing:
        print(f"  ✗ 缺少依赖: {', '.join(missing)}")
        print("  正在安装...")
        os.system("python install_dependencies_fix.py")
        return check_dependencies()  # 重新检查

    print("  ✓ 所有依赖已安装")
    return True

def check_prerequisites():
    """检查前置条件"""
    print("[2/4] 检查前置条件...")

    # 检查日志目录
    log_dir = PROJECT_ROOT / "logs" / "daily_audit"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 检查关键文件
    required_files = [
        'src/core/models/predictor.py',
        'src/core/models/model_evaluator.py',
        'src/core/data/collector.py',
        'pl5_24hour_monitor.py'
    ]

    missing = []
    for file_path in required_files:
        if not (PROJECT_ROOT / file_path).exists():
            missing.append(file_path)

    if missing:
        print(f"  ✗ 缺少文件: {', '.join(missing)}")
        return False

    print("  ✓ 所有前置条件满足")
    return True

def run_single_audit():
    """运行单次审计"""
    print("[3/4] 运行单次审计...")
    print()

    os.system("python pl5_24hour_monitor.py")

def run_continuous_monitoring():
    """运行持续监控"""
    print("[3/4] 启动持续监控...")
    print()

    print("=" * 80)
    print(" 监控配置:")
    print("   - 审计周期: 10分钟")
    print("   - 预计周期数: 144 (24小时)")
    print("   - 日志保存: logs/daily_audit/")
    print("=" * 80)
    print()

    print("提示: 按 Ctrl+C 停止监控")
    print()

    os.system("python pl5_24hour_monitor.py --continuous")

def signal_handler(sig, frame):
    """信号处理器"""
    print("\n")
    print("=" * 80)
    print(" 接收到停止信号，正在保存监控数据...")
    print("=" * 80)
    sys.exit(0)

def main():
    """主函数"""
    print_banner()

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)

    # 检查依赖
    if not check_dependencies():
        print("\n✗ 依赖检查失败")
        return 1

    # 检查前置条件
    if not check_prerequisites():
        print("\n✗ 前置条件检查失败")
        return 1

    # 选择运行模式
    print("[4/4] 选择运行模式:")
    print()
    print("  1) 单次审计模式 - 运行一次完整审计并退出")
    print("  2) 持续监控模式 - 24小时持续监控并自动修复问题")
    print()

    try:
        choice = input("请选择 [1/2]: ").strip()
    except EOFError:
        choice = "2"  # 非交互模式默认持续监控

    print()

    if choice == "1":
        print(">>> 进入单次审计模式")
        run_single_audit()
    elif choice == "2":
        print(">>> 进入持续监控模式")
        run_continuous_monitoring()
    else:
        print("无效选择，默认进入单次审计模式")
        run_single_audit()

    print()
    print("=" * 80)
    print(" 监控结束")
    print(f" 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    return 0

if __name__ == "__main__":
    sys.exit(main())
