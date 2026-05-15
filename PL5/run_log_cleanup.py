#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行日志清理脚本
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.utils.log_manager import LogManager


def main():
    manager = LogManager()
    
    # 1. 显示当前状态
    print("\n" + "="*80)
    print("开始日志清理和整理")
    print("="*80)
    
    summary_before = manager.get_log_files_summary()
    print(f"\n清理前状态:")
    print(f"  总文件数: {summary_before['total_files']}")
    print(f"  总大小: {summary_before['total_size_mb']:.2f} MB")
    
    print(f"\n按类型分类:")
    for ext, info in sorted(summary_before['files_by_type'].items()):
        print(f"  {ext}: {info['count']} 个文件, {info['size_mb']:.2f} MB")
    
    # 2. 清理临时文件
    print("\n" + "="*80)
    print("1. 清理临时文件")
    print("="*80)
    try:
        temp_result = manager.clean_temp_files(dry_run=False)
    except Exception as e:
        print(f"清理临时文件出错: {e}")
    
    # 3. 清理旧日志（保留最近7天）
    print("\n" + "="*80)
    print("2. 归档旧日志（保留最近7天）")
    print("="*80)
    try:
        old_logs_result = manager.clean_old_logs(days=7, dry_run=False)
    except Exception as e:
        print(f"归档旧日志出错: {e}")
    
    # 4. 整理目录结构
    print("\n" + "="*80)
    print("3. 整理日志目录结构")
    print("="*80)
    try:
        manager.organize_structure(dry_run=False)
    except Exception as e:
        print(f"整理目录结构出错: {e}")
    
    # 5. 显示最终状态
    summary_after = manager.get_log_files_summary()
    print("\n" + "="*80)
    print("最终状态")
    print("="*80)
    print(f"\n总文件数: {summary_after['total_files']}")
    print(f"总大小: {summary_after['total_size_mb']:.2f} MB")
    released_mb = summary_before['total_size_mb'] - summary_after['total_size_mb']
    print(f"释放空间: {released_mb:.2f} MB")
    
    print("\n" + "="*80)
    print("日志整理完成！")
    print("="*80)
    print("\n提示:")
    print("  - 临时文件已删除")
    print("  - 旧日志已归档到 logs/archive/")
    print("  - 日志已按类型分类整理")
    print("  - 关键状态文件已保留")
    print(f"\n总文件数从 {summary_before['total_files']} 减少到 {summary_after['total_files']}")


if __name__ == '__main__':
    main()
