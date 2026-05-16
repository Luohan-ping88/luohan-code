"""
磁盘空间自动清理工具 - V10.5
自动清理旧的日志文件、备份文件和模型文件
"""

import time
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DiskCleaner:
    """磁盘空间清理器"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.cwd()
        self.stats = {
            'files_removed': 0,
            'size_freed': 0,  # bytes
            'errors': []
        }
    
    def get_file_size(self, filepath: Path) -> int:
        """获取文件大小（字节）"""
        try:
            return filepath.stat().st_size
        except Exception:
            return 0
    
    def clean_logs(self, days_old: int = 7, logs_dir: Optional[Path] = None) -> Tuple[int, int]:
        """
        清理旧的日志文件
        
        Args:
            days_old: 保留最近N天的日志
            logs_dir: 日志目录，默认查找logs/目录
            
        Returns:
            (文件数量, 释放字节数)
        """
        logs_dir = logs_dir or self.base_dir / "logs"
        if not logs_dir.exists():
            logger.warning(f"日志目录不存在: {logs_dir}")
            return 0, 0
        
        cutoff = datetime.now() - timedelta(days=days_old)
        removed_count = 0
        freed_bytes = 0
        
        logger.info(f"开始清理日志（保留最近{days_old}天）: {logs_dir}")
        
        try:
            log_patterns = [
                "*.log", "*.log.*", "training_*.txt", 
                "automation_report_*.txt", "*.txt"
            ]
            
            for pattern in log_patterns:
                for filepath in logs_dir.glob(pattern):
                    if filepath.is_file():
                        try:
                            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                            if mtime < cutoff:
                                size = self.get_file_size(filepath)
                                filepath.unlink()
                                removed_count += 1
                                freed_bytes += size
                                logger.debug(f"已删除日志: {filepath.name} ({size/1024/1024:.2f}MB)")
                        except Exception as e:
                            self.stats['errors'].append(f"{filepath.name}: {str(e)}")
            
            logger.info(f"日志清理完成: 删除{removed_count}个文件，释放{freed_bytes/1024/1024:.2f}MB")
            
        except Exception as e:
            logger.error(f"日志清理失败: {e}")
        
        self.stats['files_removed'] += removed_count
        self.stats['size_freed'] += freed_bytes
        return removed_count, freed_bytes
    
    def clean_backups(self, days_old: int = 14, backup_dirs: Optional[List[Path]] = None) -> Tuple[int, int]:
        """
        清理旧的备份文件
        
        Args:
            days_old: 保留最近N天的备份
            backup_dirs: 备份目录列表
            
        Returns:
            (文件数量, 释放字节数)
        """
        if backup_dirs is None:
            backup_dirs = [
                self.base_dir / "data" / "raw" / "backups",
                self.base_dir / "data" / "processed" / "backups",
                self.base_dir / "models" / "backups"
            ]
        
        cutoff = datetime.now() - timedelta(days=days_old)
        removed_count = 0
        freed_bytes = 0
        
        for backup_dir in backup_dirs:
            if not backup_dir.exists():
                continue
                
            logger.info(f"开始清理备份（保留最近{days_old}天）: {backup_dir}")
            
            try:
                for filepath in backup_dir.rglob("*"):
                    if filepath.is_file():
                        try:
                            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                            if mtime < cutoff:
                                size = self.get_file_size(filepath)
                                filepath.unlink()
                                removed_count += 1
                                freed_bytes += size
                                logger.debug(f"已删除备份: {filepath.name} ({size/1024/1024:.2f}MB)")
                        except Exception as e:
                            self.stats['errors'].append(f"{filepath.name}: {str(e)}")
            except Exception as e:
                logger.error(f"备份清理失败 [{backup_dir}]: {e}")
        
        logger.info(f"备份清理完成: 删除{removed_count}个文件，释放{freed_bytes/1024/1024:.2f}MB")
        
        self.stats['files_removed'] += removed_count
        self.stats['size_freed'] += freed_bytes
        return removed_count, freed_bytes
    
    def clean_old_models(self, days_old: int = 30, models_dir: Optional[Path] = None) -> Tuple[int, int]:
        """
        清理旧的模型文件（保留最新版本）
        
        Args:
            days_old: 保留最近N天的模型
            models_dir: 模型目录
            
        Returns:
            (文件数量, 释放字节数)
        """
        models_dir = models_dir or self.base_dir / "models"
        if not models_dir.exists():
            logger.warning(f"模型目录不存在: {models_dir}")
            return 0, 0
        
        cutoff = datetime.now() - timedelta(days=days_old)
        removed_count = 0
        freed_bytes = 0
        
        logger.info(f"开始清理旧模型（保留最近{days_old}天）: {models_dir}")
        
        try:
            model_patterns = [
                "*.pkl", "*.h5", "*.pt", "*.pth", 
                "*.model", "*.ckpt", "*.safetensors"
            ]
            
            for pattern in model_patterns:
                for filepath in models_dir.glob(pattern):
                    if filepath.is_file():
                        try:
                            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                            if mtime < cutoff:
                                size = self.get_file_size(filepath)
                                filepath.unlink()
                                removed_count += 1
                                freed_bytes += size
                                logger.debug(f"已删除旧模型: {filepath.name} ({size/1024/1024:.2f}MB)")
                        except Exception as e:
                            self.stats['errors'].append(f"{filepath.name}: {str(e)}")
            
            logger.info(f"旧模型清理完成: 删除{removed_count}个文件，释放{freed_bytes/1024/1024:.2f}MB")
            
        except Exception as e:
            logger.error(f"旧模型清理失败: {e}")
        
        self.stats['files_removed'] += removed_count
        self.stats['size_freed'] += freed_bytes
        return removed_count, freed_bytes
    
    def get_disk_usage(self, path: Optional[Path] = None) -> dict:
        """获取磁盘使用情况"""
        path = path or self.base_dir
        try:
            usage = shutil.disk_usage(str(path))
            return {
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'used_percent': usage.used / usage.total * 100
            }
        except Exception as e:
            logger.error(f"获取磁盘使用情况失败: {e}")
            return {}
    
    def auto_clean(self, force: bool = False, emergency_threshold: float = 85.0) -> dict:
        """
        自动清理 - 根据磁盘使用情况智能决定清理策略
        
        Args:
            force: 强制清理，无论使用情况
            emergency_threshold: 紧急清理阈值（百分比）
            
        Returns:
            清理统计信息
        """
        self.stats = {
            'files_removed': 0,
            'size_freed': 0,
            'errors': [],
            'cleaned_types': []
        }
        
        usage = self.get_disk_usage()
        if not usage:
            logger.warning("无法获取磁盘使用情况")
            return self.stats
        
        used_percent = usage.get('used_percent', 0)
        logger.info(f"当前磁盘使用率: {used_percent:.1f}%")
        
        if force or used_percent >= emergency_threshold:
            logger.info("开始自动清理...")
            
            if used_percent >= emergency_threshold:
                logger.warning("磁盘空间紧急！执行深度清理")
                # 紧急模式：更激进的清理策略
                self.clean_logs(days_old=3)
                self.clean_backups(days_old=7)
                self.clean_old_models(days_old=14)
            else:
                # 常规清理
                self.clean_logs(days_old=7)
                self.clean_backups(days_old=14)
                self.clean_old_models(days_old=30)
            
            self.stats['cleaned_types'] = ['logs', 'backups', 'old_models']
        else:
            logger.info("磁盘空间充足，跳过自动清理")
        
        # 输出最终统计
        freed_mb = self.stats['size_freed'] / 1024 / 1024
        logger.info(f"清理完成: 删除{self.stats['files_removed']}个文件，释放{freed_mb:.2f}MB")
        
        if self.stats['errors']:
            logger.warning(f"清理过程中有{len(self.stats['errors'])}个错误")
        
        return self.stats
    
    def get_report(self) -> str:
        """生成清理报告"""
        freed_mb = self.stats['size_freed'] / 1024 / 1024
        report = [
            "=== 磁盘清理报告 ===",
            f"删除文件数: {self.stats['files_removed']}",
            f"释放空间: {freed_mb:.2f}MB",
            f"错误数: {len(self.stats['errors'])}"
        ]
        
        if self.stats['cleaned_types']:
            report.append(f"清理类型: {', '.join(self.stats['cleaned_types'])}")
        
        if self.stats['errors']:
            report.append("\n错误详情:")
            for err in self.stats['errors'][:10]:  # 只显示前10个错误
                report.append(f"  - {err}")
            if len(self.stats['errors']) > 10:
                report.append(f"  ... 还有{len(self.stats['errors'])-10}个错误")
        
        return '\n'.join(report)


def run_auto_clean(force: bool = False) -> dict:
    """运行自动清理的便捷函数"""
    cleaner = DiskCleaner()
    result = cleaner.auto_clean(force=force)
    print(cleaner.get_report())
    return result


if __name__ == "__main__":
    # 测试清理功能
    logging.basicConfig(level=logging.INFO)
    run_auto_clean(force=False)
