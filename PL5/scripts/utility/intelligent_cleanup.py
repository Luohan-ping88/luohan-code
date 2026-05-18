#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能日志和缓存清理脚本
自动清理过期文件，释放磁盘空间
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


class IntelligentCleaner:
    """智能清理器"""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.cleanup_stats = {
            'files_deleted': 0,
            'bytes_freed': 0,
            'directories_scanned': []
        }

    def scan_directory(self, directory: Path, patterns: List[str] = None) -> List[Path]:
        """扫描目录下的文件"""
        if patterns is None:
            patterns = ['*.log', '*.json', '*.cache', '*.pkl', '*.bak']

        files = []
        for pattern in patterns:
            files.extend(directory.rglob(pattern))
        return files

    def get_file_age_days(self, file_path: Path) -> float:
        """获取文件年龄（天）"""
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        age = datetime.now() - mtime
        return age.total_seconds() / (24 * 3600)

    def get_directory_size(self, directory: Path) -> int:
        """获取目录大小（字节）"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception as e:
            print(f"  警告: 无法计算目录大小 {directory}: {e}")
        return total_size

    def cleanup_old_files(
        self,
        directory: Path,
        max_age_days: int = 7,
        patterns: List[str] = None,
        dry_run: bool = False
    ) -> Tuple[int, int]:
        """清理过期文件"""
        if not directory.exists():
            print(f"  目录不存在: {directory}")
            return 0, 0

        files_deleted = 0
        bytes_freed = 0
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        print(f"\n  扫描目录: {directory}")
        print(f"  过期时间: {max_age_days} 天前 (截止到 {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')})")

        all_files = []
        for root, dirs, files in os.walk(directory):
            for filename in files:
                filepath = Path(root) / filename

                # 检查是否匹配模式
                if patterns:
                    if not any(filepath.match(pattern) for pattern in patterns):
                        continue

                try:
                    mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                    if mtime < cutoff_date:
                        all_files.append((filepath, mtime, filepath.stat().st_size))
                except Exception as e:
                    print(f"  警告: 无法获取文件信息 {filepath}: {e}")

        # 按时间排序，最老的先删除
        all_files.sort(key=lambda x: x[1])

        for filepath, mtime, size in all_files:
            if dry_run:
                print(f"  [模拟] 将删除: {filepath} ({size:,} bytes, 修改于 {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
                files_deleted += 1
                bytes_freed += size
            else:
                try:
                    filepath.unlink()
                    print(f"  删除: {filepath} ({size:,} bytes)")
                    files_deleted += 1
                    bytes_freed += size
                except Exception as e:
                    print(f"  错误: 无法删除 {filepath}: {e}")

        return files_deleted, bytes_freed

    def cleanup_empty_directories(self, directory: Path, dry_run: bool = False) -> int:
        """清理空目录"""
        if not directory.exists():
            return 0

        empty_dirs = []
        for root, dirs, files in os.walk(directory, topdown=False):
            for dirname in dirs:
                dirpath = Path(root) / dirname
                try:
                    if not any(dirpath.iterdir()):  # 如果目录为空
                        empty_dirs.append(dirpath)
                except Exception as e:
                    print(f"  警告: 无法检查目录 {dirpath}: {e}")

        for dirpath in empty_dirs:
            if dry_run:
                print(f"  [模拟] 将删除空目录: {dirpath}")
            else:
                try:
                    dirpath.rmdir()
                    print(f"  删除空目录: {dirpath}")
                except Exception as e:
                    print(f"  错误: 无法删除空目录 {dirpath}: {e}")

        return len(empty_dirs)

    def cleanup_logs(
        self,
        max_age_days: int = 7,
        dry_run: bool = False
    ) -> Dict:
        """清理日志文件"""
        print("\n" + "=" * 80)
        print("开始清理日志文件")
        print("=" * 80)

        logs_dir = self.root_dir / 'logs'
        patterns = ['*.log', '*.json']

        files_deleted, bytes_freed = self.cleanup_old_files(
            logs_dir, max_age_days, patterns, dry_run
        )

        empty_dirs = self.cleanup_empty_directories(logs_dir, dry_run)

        return {
            'files_deleted': files_deleted,
            'bytes_freed': bytes_freed,
            'empty_dirs_removed': empty_dirs
        }

    def cleanup_cache(
        self,
        max_age_days: int = 3,
        dry_run: bool = False
    ) -> Dict:
        """清理缓存文件"""
        print("\n" + "=" * 80)
        print("开始清理缓存文件")
        print("=" * 80)

        cache_dirs = [
            self.root_dir / 'models' / 'cache',
            self.root_dir / 'cache',
        ]

        total_deleted = 0
        total_freed = 0

        for cache_dir in cache_dirs:
            if cache_dir.exists():
                files_deleted, bytes_freed = self.cleanup_old_files(
                    cache_dir, max_age_days, ['*.cache'], dry_run
                )
                total_deleted += files_deleted
                total_freed += bytes_freed

        return {
            'files_deleted': total_deleted,
            'bytes_freed': total_freed
        }

    def cleanup_models(
        self,
        keep_latest_n: int = 5,
        max_age_days: int = 30,
        dry_run: bool = False
    ) -> Dict:
        """清理旧模型文件"""
        print("\n" + "=" * 80)
        print("开始清理旧模型文件")
        print("=" * 80)

        models_dir = self.root_dir / 'models'
        if not models_dir.exists():
            return {'files_deleted': 0, 'bytes_freed': 0}

        # 扫描所有模型文件
        model_files = []
        for pattern in ['*.pkl', '*.joblib', '*.h5', '*.pt']:
            for model_file in models_dir.rglob(pattern):
                if 'backup' not in str(model_file):  # 排除备份目录
                    mtime = datetime.fromtimestamp(model_file.stat().st_mtime)
                    size = model_file.stat().st_size
                    model_files.append((model_file, mtime, size))

        # 按时间排序
        model_files.sort(key=lambda x: x[1], reverse=True)

        # 保留最新的N个
        files_to_keep = set([f[0] for f in model_files[:keep_latest_n]])
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        files_deleted = 0
        bytes_freed = 0

        for model_file, mtime, size in model_files[keep_latest_n:]:
            if mtime < cutoff_date or model_file not in files_to_keep:
                if dry_run:
                    print(f"  [模拟] 将删除: {model_file} ({size:,} bytes)")
                else:
                    try:
                        model_file.unlink()
                        print(f"  删除: {model_file} ({size:,} bytes)")
                        files_deleted += 1
                        bytes_freed += size
                    except Exception as e:
                        print(f"  错误: 无法删除 {model_file}: {e}")

        return {
            'files_deleted': files_deleted,
            'bytes_freed': bytes_freed
        }

    def cleanup_backups(
        self,
        keep_latest_n: int = 3,
        dry_run: bool = False
    ) -> Dict:
        """清理旧备份文件"""
        print("\n" + "=" * 80)
        print("开始清理旧备份文件")
        print("=" * 80)

        backup_dirs = [
            self.root_dir / 'models' / 'model_backups',
        ]

        total_deleted = 0
        total_freed = 0

        for backup_dir in backup_dirs:
            if not backup_dir.exists():
                continue

            # 获取所有备份文件
            backup_files = []
            for backup_file in backup_dir.glob('backup_*.pkl'):
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                size = backup_file.stat().st_size
                backup_files.append((backup_file, mtime, size))

            # 按时间排序，保留最新的N个
            backup_files.sort(key=lambda x: x[1], reverse=True)

            for i, (backup_file, mtime, size) in enumerate(backup_files):
                if i >= keep_latest_n:
                    if dry_run:
                        print(f"  [模拟] 将删除: {backup_file} ({size:,} bytes)")
                    else:
                        try:
                            backup_file.unlink()
                            print(f"  删除: {backup_file} ({size:,} bytes)")
                            total_deleted += 1
                            total_freed += size
                        except Exception as e:
                            print(f"  错误: 无法删除 {backup_file}: {e}")

        return {
            'files_deleted': total_deleted,
            'bytes_freed': total_freed
        }

    def cleanup_feature_versions(
        self,
        keep_latest_n: int = 10,
        dry_run: bool = False
    ) -> Dict:
        """清理旧特征版本文件"""
        print("\n" + "=" * 80)
        print("开始清理旧特征版本文件")
        print("=" * 80)

        versions_dir = self.root_dir / 'models' / 'feature_versions'
        if not versions_dir.exists():
            return {'files_deleted': 0, 'bytes_freed': 0}

        # 获取所有版本文件
        version_files = []
        for version_file in versions_dir.glob('v*.json'):
            mtime = datetime.fromtimestamp(version_file.stat().st_mtime)
            size = version_file.stat().st_size
            version_files.append((version_file, mtime, size))

        # 按时间排序，保留最新的N个
        version_files.sort(key=lambda x: x[1], reverse=True)

        files_deleted = 0
        bytes_freed = 0

        for i, (version_file, mtime, size) in enumerate(version_files):
            if i >= keep_latest_n:
                if dry_run:
                    print(f"  [模拟] 将删除: {version_file} ({size:,} bytes)")
                else:
                    try:
                        version_file.unlink()
                        print(f"  删除: {version_file} ({size:,} bytes)")
                        files_deleted += 1
                        bytes_freed += size
                    except Exception as e:
                        print(f"  错误: 无法删除 {version_file}: {e}")

        return {
            'files_deleted': files_deleted,
            'bytes_freed': bytes_freed
        }

    def run_full_cleanup(
        self,
        dry_run: bool = False,
        cleanup_config: Dict = None
    ) -> Dict:
        """执行完整清理"""
        if cleanup_config is None:
            cleanup_config = {
                'logs': {'max_age_days': 7},
                'cache': {'max_age_days': 3},
                'models': {'keep_latest_n': 5, 'max_age_days': 30},
                'backups': {'keep_latest_n': 3},
                'feature_versions': {'keep_latest_n': 10}
            }

        print("\n" + "=" * 80)
        print("PL5 智能清理系统")
        print(f"根目录: {self.root_dir}")
        print(f"模式: {'模拟运行' if dry_run else '实际清理'}")
        print("=" * 80)

        # 清理前磁盘使用情况
        disk_usage_before = self.get_disk_usage()

        results = {}

        # 清理日志
        results['logs'] = self.cleanup_logs(**cleanup_config['logs'], dry_run=dry_run)

        # 清理缓存
        results['cache'] = self.cleanup_cache(**cleanup_config['cache'], dry_run=dry_run)

        # 清理旧模型
        results['models'] = self.cleanup_models(**cleanup_config['models'], dry_run=dry_run)

        # 清理旧备份
        results['backups'] = self.cleanup_backups(**cleanup_config['backups'], dry_run=dry_run)

        # 清理旧特征版本
        results['feature_versions'] = self.cleanup_feature_versions(**cleanup_config['feature_versions'], dry_run=dry_run)

        # 清理后磁盘使用情况
        disk_usage_after = self.get_disk_usage()

        # 汇总结果
        total_files_deleted = sum(r['files_deleted'] for r in results.values())
        total_bytes_freed = sum(r['bytes_freed'] for r in results.values())

        summary = {
            'mode': 'dry_run' if dry_run else 'actual',
            'before': disk_usage_before,
            'after': disk_usage_after,
            'files_deleted': total_files_deleted,
            'bytes_freed': total_bytes_freed,
            'details': results
        }

        print("\n" + "=" * 80)
        print("清理完成摘要")
        print("=" * 80)
        print(f"模式: {'模拟运行' if dry_run else '实际清理'}")
        print(f"删除文件数: {total_files_deleted:,}")
        print(f"释放空间: {total_bytes_freed / (1024**2):.2f} MB")
        print(f"\n磁盘使用情况:")
        print(f"  清理前: {disk_usage_before['percent']:.1f}% (使用 {disk_usage_before['used_gb']:.2f} GB / 总计 {disk_usage_before['total_gb']:.2f} GB)")
        print(f"  清理后: {disk_usage_after['percent']:.1f}% (使用 {disk_usage_after['used_gb']:.2f} GB / 总计 {disk_usage_after['total_gb']:.2f} GB)")

        # 保存清理报告
        report_file = self.root_dir / 'logs' / f'cleanup_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n清理报告已保存: {report_file}")

        return summary

    def get_disk_usage(self) -> Dict:
        """获取磁盘使用情况"""
        import psutil
        disk = psutil.disk_usage(str(self.root_dir))
        return {
            'total_gb': disk.total / (1024**3),
            'used_gb': disk.used / (1024**3),
            'free_gb': disk.free / (1024**3),
            'percent': disk.percent
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='PL5智能清理系统')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不实际删除文件')
    parser.add_argument('--root-dir', type=str, default='/workspace/PL5', help='根目录')
    parser.add_argument('--logs-days', type=int, default=7, help='日志保留天数')
    parser.add_argument('--cache-days', type=int, default=3, help='缓存保留天数')
    parser.add_argument('--models-keep', type=int, default=5, help='保留最新模型数')

    args = parser.parse_args()

    cleaner = IntelligentCleaner(Path(args.root_dir))

    cleanup_config = {
        'logs': {'max_age_days': args.logs_days},
        'cache': {'max_age_days': args.cache_days},
        'models': {'keep_latest_n': args.models_keep, 'max_age_days': 30},
        'backups': {'keep_latest_n': 3},
        'feature_versions': {'keep_latest_n': 10}
    }

    cleaner.run_full_cleanup(dry_run=args.dry_run, cleanup_config=cleanup_config)


if __name__ == '__main__':
    main()
