#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V10.3 优化后的系统状态检查工具
"""

import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import LOGS_DIR, MODELS_DIR, DATA_DIR
from src.core.features.feature_version_manager import get_feature_version_manager
from src.core.monitoring.health_monitor import get_health_monitor

def print_section(title: str):
    """打印分隔标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def check_directories():
    """检查目录"""
    print_section("目录结构检查")
    
    dirs = [
        ("日志目录", LOGS_DIR),
        ("模型目录", MODELS_DIR),
        ("数据目录", DATA_DIR),
        ("特征版本目录", MODELS_DIR / "feature_versions")
    ]
    
    for name, path in dirs:
        exists = path.exists()
        status = "✓ 存在" if exists else "✗ 不存在"
        print(f"{name}: {path}")
        print(f"  状态: {status}")

def check_feature_versions():
    """检查特征版本"""
    print_section("特征版本检查")
    
    manager = get_feature_version_manager()
    versions = manager.list_versions()
    
    if versions:
        print(f"特征版本数: {len(versions)}")
        print("\n最近5个版本:")
        for v in versions[:5]:
            print(f"  - {v['version_id']} ({v['timestamp'][:19]})")
            print(f"    特征数: {v['feature_count']}")
        
        latest = manager.get_latest_version_info()
        if latest:
            print(f"\n最新版本: {latest['version_id']}")
    else:
        print("尚无特征版本（首次训练时会创建）")

def check_health_monitoring():
    """检查健康监控"""
    print_section("系统健康检查")
    
    monitor = get_health_monitor()
    status = monitor.get_current_status()
    
    print(f"健康评分: {status['health_score']} / 100")
    print(f"状态: {status['status']}")
    
    metrics = status['current_metrics']
    print(f"\n当前指标:")
    print(f"  CPU使用率: {metrics['cpu_percent']}%")
    print(f"  内存使用率: {metrics['memory_percent']}%")
    print(f"  磁盘使用率: {metrics['disk_usage_percent']}%")
    print(f"  任务成功率: {metrics['task_success_rate'] * 100:.1f}%")
    
    if status['recent_alerts']:
        print(f"\n最近预警 ({len(status['recent_alerts'])} 条):")
        for alert in status['recent_alerts']:
            level = alert['level'].upper()
            print(f"  [{level}] {alert['message']}")
    else:
        print("\n无近期预警")

def check_health_summary():
    """检查健康摘要"""
    print_section("24小时健康摘要")
    
    monitor = get_health_monitor()
    summary = monitor.get_health_summary(hours=24)
    
    print(f"总预警数: {summary['total_alerts']}")
    print(f"预警分类:")
    for level, count in summary['alert_counts'].items():
        if count > 0:
            print(f"  {level.upper()}: {count}")
    
    print(f"\n平均CPU使用率: {summary['average_cpu_percent']}%")
    print(f"平均内存使用率: {summary['average_memory_percent']}%")

def main():
    """主函数"""
    print("\n" + "#" * 80)
    print("#" + " " * 78 + "#")
    print("#" + "  PL5 V10.3 优化系统状态检查".ljust(78) + "#")
    print("#" + " " * 78 + "#")
    print("#" * 80)
    
    try:
        check_directories()
        check_feature_versions()
        check_health_monitoring()
        check_health_summary()
        
        print_section("检查完成")
        print("✓ V10.3 优化系统状态检查完成")
        print("\n详细优化文档请参考: V10_OPTIMIZATION_SUMMARY.md")
        
    except Exception as e:
        print(f"\n✗ 检查出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
