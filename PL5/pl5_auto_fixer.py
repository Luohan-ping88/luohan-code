#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PL5 自动优化和修复系统
在检测到问题时自动尝试修复和优化
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


@dataclass
class FixResult:
    """修复结果"""
    issue: str
    fixed: bool
    action_taken: str
    result: str
    details: Optional[str] = None


class PL5AutoFixer:
    """PL5自动修复器"""

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.fix_history: List[FixResult] = []
        self.fixes_applied = 0

    def fix_import_errors(self, errors: List[str]) -> List[FixResult]:
        """修复导入错误"""
        results = []
        logger.info(f"尝试修复 {len(errors)} 个导入错误...")

        for error in errors[:10]:  # 限制处理数量
            try:
                # 提取模块名
                if ":" in error:
                    module_name = error.split(":")[0].strip()
                else:
                    module_name = error.split(" ")[0].strip()

                logger.info(f"检查导入问题: {module_name}")

                # 检查模块是否存在
                module_path = self.project_root / "src" / module_name.replace(".", os.sep) + ".py"
                init_path = self.project_root / "src" / module_name.replace(".", os.sep) / "__init__.py"

                if module_path.exists() or init_path.exists():
                    results.append(FixResult(
                        issue=error,
                        fixed=True,
                        action_taken="模块已存在",
                        result="模块路径正确"
                    ))
                else:
                    results.append(FixResult(
                        issue=error,
                        fixed=False,
                        action_taken="未处理",
                        result="模块不存在，需要手动创建"
                    ))

            except Exception as e:
                results.append(FixResult(
                    issue=error,
                    fixed=False,
                    action_taken="处理失败",
                    result=str(e)
                ))

        return results

    def fix_log_rotation(self) -> FixResult:
        """修复日志轮转问题"""
        try:
            # 检查日志目录
            log_dir = self.project_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            # 检查日志文件大小
            large_logs = []
            for log_file in log_dir.glob("*.log"):
                if log_file.stat().st_size > 100 * 1024 * 1024:  # > 100MB
                    large_logs.append(log_file)

            if large_logs:
                logger.warning(f"发现 {len(large_logs)} 个大型日志文件需要清理")

                # 备份并清理
                for log_file in large_logs:
                    backup_name = log_file.stem + f"_old_{datetime.now().strftime('%Y%m%d')}" + log_file.suffix
                    backup_path = log_dir / backup_name
                    log_file.rename(backup_path)
                    logger.info(f"已备份日志: {backup_path.name}")

                return FixResult(
                    issue="日志文件过大",
                    fixed=True,
                    action_taken="日志备份清理",
                    result=f"已清理 {len(large_logs)} 个日志文件"
                )

            return FixResult(
                issue="日志轮转",
                fixed=True,
                action_taken="无需操作",
                result="日志文件大小正常"
            )

        except Exception as e:
            return FixResult(
                issue="日志轮转修复",
                fixed=False,
                action_taken="失败",
                result=str(e)
            )

    def fix_data_collector(self) -> FixResult:
        """修复数据采集器"""
        try:
            # 检查数据目录
            raw_dir = self.project_root / "data" / "raw"
            processed_dir = self.project_root / "data" / "processed"

            raw_dir.mkdir(parents=True, exist_ok=True)
            processed_dir.mkdir(parents=True, exist_ok=True)

            # 检查数据文件
            raw_file = raw_dir / "pl5_history.txt"
            processed_file = processed_dir / "pl5_processed.csv"

            if not raw_file.exists():
                logger.warning("原始数据文件不存在，尝试从网络获取...")
                # 尝试运行数据更新
                try:
                    from src.core.data.collector import PL5DataCollectorV8
                    collector = PL5DataCollectorV8()
                    df = collector.update_data()
                    if df is not None and not df.empty:
                        return FixResult(
                            issue="原始数据缺失",
                            fixed=True,
                            action_taken="数据更新",
                            result=f"成功获取 {len(df)} 条数据"
                        )
                except Exception as e:
                    return FixResult(
                        issue="原始数据缺失",
                        fixed=False,
                        action_taken="数据更新失败",
                        result=str(e)
                    )

            return FixResult(
                issue="数据采集器",
                fixed=True,
                action_taken="目录检查",
                result="数据目录正常"
            )

        except Exception as e:
            return FixResult(
                issue="数据采集器修复",
                fixed=False,
                action_taken="失败",
                result=str(e)
            )

    def fix_config_issues(self) -> List[FixResult]:
        """修复配置问题"""
        results = []

        # 检查配置文件
        config_files = {
            "config/config.json": {
                "required_keys": ["data_fetch_time", "email_send_time", "training_schedule"]
            },
            "config/email_config.json": {
                "required_keys": ["smtp_server", "smtp_port", "from_email", "to_email"]
            }
        }

        for config_file, requirements in config_files.items():
            config_path = self.project_root / config_file
            try:
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                    missing_keys = [k for k in requirements["required_keys"] if k not in config]

                    if missing_keys:
                        logger.warning(f"{config_file} 缺少配置项: {missing_keys}")
                        results.append(FixResult(
                            issue=f"{config_file} 配置不完整",
                            fixed=False,
                            action_taken="需要手动补充",
                            result=f"缺少: {missing_keys}"
                        ))
                    else:
                        results.append(FixResult(
                            issue=f"{config_file} 配置",
                            fixed=True,
                            action_taken="验证通过",
                            result="所有必需配置项存在"
                        ))
                else:
                    # 创建默认配置
                    logger.info(f"配置文件不存在，将使用默认值: {config_file}")

            except Exception as e:
                results.append(FixResult(
                    issue=f"{config_file} 读取错误",
                    fixed=False,
                    action_taken="读取失败",
                    result=str(e)
                ))

        return results

    def optimize_performance(self) -> List[FixResult]:
        """优化性能"""
        results = []

        # 1. 清理缓存
        try:
            cache_dir = self.project_root / "models" / "cache"
            if cache_dir.exists():
                cache_files = list(cache_dir.glob("**/*.cache"))
                if len(cache_files) > 100:
                    logger.info(f"清理 {len(cache_files)} 个缓存文件...")
                    for cf in cache_files[100:]:
                        cf.unlink()

                    results.append(FixResult(
                        issue="模型缓存过多",
                        fixed=True,
                        action_taken="缓存清理",
                        result=f"清理了 {len(cache_files) - 100} 个缓存文件"
                    ))
        except Exception as e:
            results.append(FixResult(
                issue="缓存清理",
                fixed=False,
                action_taken="失败",
                result=str(e)
            ))

        # 2. 清理旧备份
        try:
            backup_dir = self.project_root / "models" / "model_backups"
            if backup_dir.exists():
                backups = sorted(backup_dir.glob("backup_*.pkl"), key=lambda x: x.stat().st_mtime)
                if len(backups) > 10:
                    for old_backup in backups[:-10]:
                        old_backup.unlink()
                        logger.info(f"删除旧备份: {old_backup.name}")

                    results.append(FixResult(
                        issue="旧模型备份过多",
                        fixed=True,
                        action_taken="备份清理",
                        result=f"保留了最近10个备份"
                    ))
        except Exception as e:
            results.append(FixResult(
                issue="备份清理",
                fixed=False,
                action_taken="失败",
                result=str(e)
            ))

        # 3. 清理旧日志
        try:
            log_dir = self.project_root / "logs"
            if log_dir.exists():
                old_logs = list(log_dir.glob("*.log"))
                if len(old_logs) > 50:
                    for old_log in old_logs[50:]:
                        try:
                            old_log.unlink()
                        except:
                            pass

                    results.append(FixResult(
                        issue="日志文件过多",
                        fixed=True,
                        action_taken="日志清理",
                        result=f"清理后保留50个日志文件"
                    ))
        except Exception as e:
            results.append(FixResult(
                issue="日志清理",
                fixed=False,
                action_taken="失败",
                result=str(e)
            ))

        return results

    def fix_dependency_issues(self) -> List[FixResult]:
        """修复依赖问题"""
        results = []

        required_packages = [
            "numpy", "pandas", "scipy", "scikit-learn",
            "requests", "psutil", "joblib"
        ]

        missing = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)

        if missing:
            results.append(FixResult(
                issue="缺少依赖包",
                fixed=False,
                action_taken="需要安装",
                result=f"缺少: {', '.join(missing)}",
                details="运行: pip install " + " ".join(missing)
            ))
        else:
            results.append(FixResult(
                issue="依赖包检查",
                fixed=True,
                action_taken="全部安装",
                result="所有必需依赖已安装"
            ))

        return results

    def run_auto_fix(self, issues: List[Dict]) -> Dict[str, Any]:
        """运行自动修复"""
        logger.info(f"开始自动修复，发现 {len(issues)} 个问题...")

        all_results = []

        for issue in issues:
            issue_type = issue.get("type", "unknown")
            issue_desc = issue.get("description", "")

            if issue_type == "import_error":
                results = self.fix_import_errors([issue_desc])
                all_results.extend(results)
            elif issue_type == "log_size":
                result = self.fix_log_rotation()
                all_results.append(result)
            elif issue_type == "data_missing":
                result = self.fix_data_collector()
                all_results.append(result)
            elif issue_type == "config_error":
                results = self.fix_config_issues()
                all_results.extend(results)
            elif issue_type == "performance":
                results = self.optimize_performance()
                all_results.extend(results)
            elif issue_type == "dependency":
                results = self.fix_dependency_issues()
                all_results.extend(results)

        # 统计
        fixed_count = sum(1 for r in all_results if r.fixed)
        self.fixes_applied += fixed_count

        report = {
            "total_issues": len(issues),
            "total_fixes_attempted": len(all_results),
            "fixed": fixed_count,
            "failed": len(all_results) - fixed_count,
            "results": [
                {
                    "issue": r.issue,
                    "fixed": r.fixed,
                    "action": r.action_taken,
                    "result": r.result,
                    "details": r.details
                }
                for r in all_results
            ]
        }

        logger.info(f"自动修复完成: {fixed_count}/{len(all_results)} 成功")

        return report


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='PL5自动修复系统')
    parser.add_argument('--fix-type', choices=['all', 'logs', 'data', 'config', 'performance', 'deps'],
                        default='all', help='修复类型')
    args = parser.parse_args()

    fixer = PL5AutoFixer()

    if args.fix_type == 'all':
        issues = [{"type": "performance", "description": "全面优化"}]
    elif args.fix_type == 'logs':
        issues = [{"type": "log_size", "description": "日志过大"}]
    elif args.fix_type == 'data':
        issues = [{"type": "data_missing", "description": "数据缺失"}]
    elif args.fix_type == 'config':
        issues = [{"type": "config_error", "description": "配置错误"}]
    elif args.fix_type == 'performance':
        issues = [{"type": "performance", "description": "性能优化"}]
    else:
        issues = [{"type": "dependency", "description": "依赖检查"}]

    report = fixer.run_auto_fix(issues)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
