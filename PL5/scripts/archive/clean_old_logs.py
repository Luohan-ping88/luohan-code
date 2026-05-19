#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理旧的日志文件
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta


def main():
    log_dir = Path("logs")
    
    # 查找所有 app_*.jsonl 文件
    print("="*80)
    print("查找旧的日志文件")
    print("="*80)
    
    # 创建归档目录
    archive_dir = log_dir / "archive"
    archive_dir.mkdir(exist_ok=True)
    
    cutoff_date = datetime.now() - timedelta(days=1)
    
    # 查找并移动旧的 app_*.jsonl 文件
    old_files = []
    for item in log_dir.glob("app_*.jsonl"):
        if item.is_file():
            # 从文件名中提取日期
            filename = item.name
            try:
                date_str = filename.replace("app_", "").replace(".jsonl", "")
                # 跳过无法识别日期的文件都归档
                old_files.append(item)
            except:
                old_files.append(item)
    
    print(f"\n找到 {len(old_files)} 个旧日志文件")
    
    # 移动到 archive
    moved_count = 0
    for file_path in old_files:
        try:
            dest_path = archive_dir / file_path.name
            # 如果目标文件已存在，添加时间戳
            if dest_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = archive_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"
            
            os.rename(str(file_path), str(dest_path))
            print(f"Moved: {file_path.name} -> archive/")
            moved_count += 1
        except PermissionError:
            print(f"Skipped: {file_path.name} (文件正在使用)")
        except Exception as e:
            print(f"Error moving {file_path.name}: {e}")
    
    print("\n" + "="*80)
    print(f"完成: 移动了 {moved_count} 个旧日志文件")
    print("="*80)


if __name__ == '__main__':
    main()
