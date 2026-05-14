#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理模块
提供日志清理、轮换和归档功能
"""

import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json


class LogManager:
    """日志管理器"""

    def __init__(self, log_dir: Optional[Path] = None):
        """初始化日志管理器

        Args:
            log_dir: 日志目录路径
        """
        self.log_dir = log_dir or Path("logs")
        self.archive_dir = self.log_dir / "archive"
        self.temp_dir = self.log_dir / "temp"

        # 创建目录结构
        self._ensure_directories()

        # 加载配置
        self.config = self._load_config()

    def _ensure_directories(self):
        """确保所需目录存在"""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict:
        """加载日志管理配置

        Returns:
            配置字典
        """
        default_config = {
            "retention_days": {
                "app_logs": 7,
                "performance_logs": 7,
                "temp_files": 3,
                "test_files": 3,
            },
            "archive_threshold": 7,
            "max_file_size_mb": 50,
            "compression_enabled": True,
        }

        config_file = self.log_dir / "log_config.json"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Failed to load log config: {e}")

        return default_config

    def save_config(self, config: Optional[Dict] = None):
        """保存配置

        Args:
            config: 配置字典，如果为None则保存当前配置
        """
        config_file = self.log_dir / "log_config.json"
        config_to_save = config or self.config
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=2)
            print(f"Config saved to {config_file}")
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_log_files_summary(self) -> Dict:
        """获取日志文件摘要信息

        Returns:
            摘要字典
        """
        summary = {
            "total_files": 0,
            "total_size_mb": 0,
            "files_by_type": {},
            "directories": [],
        }

        for item in self.log_dir.rglob("*"):
            if item.is_file():
                summary["total_files"] += 1
                size_mb = item.stat().st_size / (1024 * 1024)
                summary["total_size_mb"] += size_mb

                # 按类型分类
                ext = item.suffix.lower()
                if ext in summary["files_by_type"]:
                    summary["files_by_type"][ext]["count"] += 1
                    summary["files_by_type"][ext]["size_mb"] += size_mb
                else:
                    summary["files_by_type"][ext] = {
                        "count": 1,
                        "size_mb": size_mb,
                    }
            elif item.is_dir():
                summary["directories"].append(
                    str(item.relative_to(self.log_dir))
                )

        return summary

    def list_old_files(self, days: int = 7) -> List[Path]:
        """列出超过指定天数的文件

        Args:
            days: 天数

        Returns:
            旧文件列表
        """
        cutoff = datetime.now() - timedelta(days=days)
        old_files = []

        for item in self.log_dir.rglob("*"):
            if item.is_file():
                try:
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    if mtime < cutoff:
                        old_files.append(item)
                except Exception:
                    pass

        return old_files

    def list_temp_files(self) -> List[Path]:
        """列出临时文件

        Returns:
            临时文件列表
        """
        temp_patterns = [
            r"test_output",
            r"_monitor_test",
            r"deployment_test",
            r"data_load_test",
            r"error_handling_test",
            r"smoke_",
            r"e2e_",
        ]

        temp_files = []

        for item in self.log_dir.rglob("*"):
            if item.is_file():
                for pattern in temp_patterns:
                    if re.search(pattern, item.name, re.IGNORECASE):
                        temp_files.append(item)
                        break

        return temp_files

    def delete_files(
        self, files: List[Path], dry_run: bool = False
    ) -> Tuple[int, float]:
        """删除文件

        Args:
            files: 要删除的文件列表
            dry_run: 仅显示要删除的文件，不实际删除

        Returns:
            (删除的文件数量, 释放的空间MB)
        """
        deleted_count = 0
        freed_space_mb = 0

        for file_path in files:
            if not file_path.exists():
                continue

            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)

                if dry_run:
                    print(
                        f"[Dry Run] Would delete: {file_path} ({size_mb:.2f} MB)"
                    )
                else:
                    file_path.unlink()
                    print(f"Deleted: {file_path} ({size_mb:.2f} MB)")

                deleted_count += 1
                freed_space_mb += size_mb
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

        return deleted_count, freed_space_mb

    def archive_files(
        self, files: List[Path], dry_run: bool = False
    ) -> Tuple[int, float]:
        """归档文件

        Args:
            files: 要归档的文件列表
            dry_run: 仅显示要归档的文件，不实际归档

        Returns:
            (归档的文件数量, 归档的空间MB)
        """
        archived_count = 0
        archived_space_mb = 0

        for file_path in files:
            if not file_path.exists():
                continue

            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)

                # 保持相对目录结构
                rel_path = file_path.relative_to(self.log_dir)
                dest_path = self.archive_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                if dry_run:
                    print(
                        f"[Dry Run] Would archive: {file_path} -> {dest_path}"
                    )
                else:
                    shutil.move(str(file_path), str(dest_path))
                    print(f"Archived: {file_path} -> {dest_path}")

                archived_count += 1
                archived_space_mb += size_mb
            except Exception as e:
                print(f"Error archiving {file_path}: {e}")

        return archived_count, archived_space_mb

    def clean_old_logs(
        self, days: Optional[int] = None, dry_run: bool = False
    ) -> Dict:
        """清理旧日志

        Args:
            days: 保留天数，如果为None则使用配置
            dry_run: 仅显示要清理的文件，不实际清理

        Returns:
            清理结果
        """
        days = days or self.config["retention_days"]["app_logs"]

        print(f"\n{'=' * 80}")
        print(f"清理旧日志 (保留最近 {days} 天)")
        print(f"{'=' * 80}")

        old_files = self.list_old_files(days=days)

        if not old_files:
            print("没有找到需要清理的旧日志")
            return {"count": 0, "freed_mb": 0}

        # 排除关键状态文件
        critical_files = [
            "scheduler_v8_status.json",
            "task_history_v8.pkl",
            "workflow_state.pkl",
            "sentinel_status.json",
        ]

        files_to_clean = []
        for f in old_files:
            if f.name not in critical_files and "archive" not in f.parts:
                files_to_clean.append(f)

        print(f"\n找到 {len(files_to_clean)} 个旧文件需要清理")

        count, freed_mb = self.archive_files(files_to_clean, dry_run=dry_run)

        print(f"\n{'=' * 80}")
        print(f"清理完成: {count} 个文件, 释放 {freed_mb:.2f} MB")
        print(f"{'=' * 80}")

        return {"count": count, "freed_mb": freed_mb}

    def clean_temp_files(self, dry_run: bool = False) -> Dict:
        """清理临时文件

        Args:
            dry_run: 仅显示要清理的文件，不实际清理

        Returns:
            清理结果
        """
        print(f"\n{'=' * 80}")
        print("清理临时文件")
        print(f"{'=' * 80}")

        temp_files = self.list_temp_files()

        if not temp_files:
            print("没有找到临时文件")
            return {"count": 0, "freed_mb": 0}

        print(f"\n找到 {len(temp_files)} 个临时文件需要清理")

        count, freed_mb = self.delete_files(temp_files, dry_run=dry_run)

        print(f"\n{'=' * 80}")
        print(f"清理完成: {count} 个文件, 释放 {freed_mb:.2f} MB")
        print(f"{'=' * 80}")

        return {"count": count, "freed_mb": freed_mb}

    def organize_structure(self, dry_run: bool = False):
        """整理日志目录结构

        Args:
            dry_run: 仅显示要移动的文件，不实际移动
        """
        print(f"\n{'=' * 80}")
        print("整理日志目录结构")
        print(f"{'=' * 80}")

        # 将根目录下的非状态文件移动到适当目录
        root_files = []
        for item in self.log_dir.iterdir():
            if item.is_file():
                # 跳过关键状态文件、配置和正在使用的日志文件
                critical_files = [
                    "scheduler_v8_status.json",
                    "task_history_v8.pkl",
                    "workflow_state.pkl",
                    "log_config.json",
                    "pl5.log",
                    "watchdog.log",
                    "deploy.log",
                    "sentinel_status.json",
                    "app.log",
                    "sentinel.log",
                ]
                if item.name not in critical_files:
                    root_files.append(item)

        if not root_files:
            print("根目录没有需要整理的文件")
            return

        print(f"\n找到 {len(root_files)} 个文件需要整理")

        organized_count = 0
        for file_path in root_files:
            # 根据文件名分类
            dest_dir = None

            if (
                "prediction" in file_path.name.lower()
                or "verification" in file_path.name.lower()
            ):
                dest_dir = self.log_dir / "predictions"
            elif (
                "report" in file_path.name.lower()
                or "training" in file_path.name.lower()
            ):
                dest_dir = self.log_dir / "reports"
            elif "performance" in file_path.name.lower():
                dest_dir = self.log_dir / "performance"
            elif "sentinel" in file_path.name.lower():
                dest_dir = self.log_dir / "sentinel"
            elif "error" in file_path.name.lower():
                dest_dir = self.log_dir / "errors"
            elif file_path.suffix in [".md", ".txt"]:
                dest_dir = self.log_dir / "docs"
            else:
                dest_dir = self.log_dir / "misc"

            if dest_dir:
                dest_dir.mkdir(exist_ok=True)
                dest_path = dest_dir / file_path.name

                if dry_run:
                    print(
                        f"[Dry Run] Would move: {file_path.name} -> {dest_dir.name}/"
                    )
                else:
                    try:
                        # 先尝试重命名
                        if dest_path.exists():
                            # 如果目标文件已存在，添加时间戳
                            timestamp = datetime.now().strftime(
                                "%Y%m%d_%H%M%S"
                            )
                            dest_path = (
                                dest_dir
                                / f"{file_path.stem}_{timestamp}{file_path.suffix}"
                            )

                        shutil.move(str(file_path), str(dest_path))
                        print(f"Moved: {file_path.name} -> {dest_dir.name}/")
                        organized_count += 1
                    except PermissionError:
                        print(f"Skipped: {file_path.name} (文件正在使用中)")
                    except Exception as e:
                        print(f"Error moving {file_path.name}: {e}")

        print(f"\n{'=' * 80}")
        print(f"整理完成: {organized_count} 个文件")
        print(f"{'=' * 80}")

    def full_cleanup(self, dry_run: bool = False) -> Dict:
        """执行完整的日志清理

        Args:
            dry_run: 仅显示要清理的内容，不实际执行

        Returns:
            清理结果汇总
        """
        print(f"\n{'=' * 80}")
        print("开始完整的日志清理")
        print(f"{'=' * 80}")

        # 显示当前状态
        summary_before = self.get_log_files_summary()
        print(f"\n清理前状态:")
        print(f"  总文件数: {summary_before['total_files']}")
        print(f"  总大小: {summary_before['total_size_mb']:.2f} MB")

        results = {}

        # 1. 清理临时文件
        results["temp_cleanup"] = self.clean_temp_files(dry_run=dry_run)

        # 2. 整理目录结构
        results["organization"] = {"organized": True}
        self.organize_structure(dry_run=dry_run)

        # 3. 清理旧日志
        results["old_logs"] = self.clean_old_logs(dry_run=dry_run)

        # 显示清理后状态
        if not dry_run:
            summary_after = self.get_log_files_summary()
            print(f"\n{'=' * 80}")
            print(f"清理后状态:")
            print(f"  总文件数: {summary_after['total_files']}")
            print(f"  总大小: {summary_after['total_size_mb']:.2f} MB")
            print(
                f"  释放空间: {summary_before['total_size_mb'] - summary_after['total_size_mb']:.2f} MB"
            )
            print(f"{'=' * 80}")

        return results


def main():
    """主函数 - 命令行工具"""
    import argparse

    parser = argparse.ArgumentParser(description="PL5系统日志管理工具")
    parser.add_argument(
        "--dry-run", action="store_true", help="仅显示要执行的操作，不实际执行"
    )
    parser.add_argument(
        "--summary", action="store_true", help="显示日志文件摘要"
    )
    parser.add_argument(
        "--clean-temp", action="store_true", help="仅清理临时文件"
    )
    parser.add_argument(
        "--clean-old", type=int, help="清理超过指定天数的旧日志"
    )
    parser.add_argument(
        "--organize", action="store_true", help="整理日志目录结构"
    )
    parser.add_argument(
        "--full-cleanup", action="store_true", help="执行完整的日志清理"
    )

    args = parser.parse_args()

    manager = LogManager()

    if args.summary:
        summary = manager.get_log_files_summary()
        print(f"\n{'=' * 80}")
        print("日志文件摘要")
        print(f"{'=' * 80}")
        print(f"\n总文件数: {summary['total_files']}")
        print(f"总大小: {summary['total_size_mb']:.2f} MB")

        print(f"\n按类型分类:")
        for ext, info in sorted(summary["files_by_type"].items()):
            print(f"  {ext}: {info['count']} 个文件, {info['size_mb']:.2f} MB")

        print(f"\n目录: {', '.join(summary['directories'])}")

    elif args.clean_temp:
        manager.clean_temp_files(dry_run=args.dry_run)

    elif args.clean_old is not None:
        manager.clean_old_logs(days=args.clean_old, dry_run=args.dry_run)

    elif args.organize:
        manager.organize_structure(dry_run=args.dry_run)

    elif args.full_cleanup:
        manager.full_cleanup(dry_run=args.dry_run)

    else:
        # 默认显示摘要
        print(
            "请指定操作: --summary, --clean-temp, --clean-old N, --organize, --full-cleanup"
        )


if __name__ == "__main__":
    main()
