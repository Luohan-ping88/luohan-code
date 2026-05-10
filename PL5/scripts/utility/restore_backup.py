#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 数据恢复脚本 V2.0
提供数据恢复功能，支持从备份恢复系统数据

功能特性：
- 从指定备份恢复数据
- 自动查找最新备份
- 选择性恢复（数据、模型、配置）
- 恢复前自动备份当前数据
- 恢复后验证
"""

import os
import sys
import shutil
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BackupRestorer:
    """备份恢复器"""

    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.daily_backup_dir = self.backup_dir / "daily"
        self.manual_backup_dir = self.backup_dir / "manual"

    def list_available_backups(self) -> List[Dict[str, Any]]:
        """列出所有可用备份"""
        backups = []

        # 扫描daily目录
        if self.daily_backup_dir.exists():
            for item in self.daily_backup_dir.iterdir():
                backup_info = self._get_backup_info(item)
                if backup_info:
                    backups.append(backup_info)

        # 扫描manual目录
        if self.manual_backup_dir.exists():
            for item in self.manual_backup_dir.iterdir():
                backup_info = self._get_backup_info(item)
                if backup_info:
                    backups.append(backup_info)

        # 按时间排序（最新的在前）
        backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return backups

    def _get_backup_info(self, backup_path: Path) -> Optional[Dict[str, Any]]:
        """获取备份信息"""
        try:
            # 如果是压缩文件
            if backup_path.suffix == '.zip':
                import zipfile
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    if 'backup_info.json' in zipf.namelist():
                        with zipf.open('backup_info.json') as f:
                            info = json.load(f)
                            info['path'] = str(backup_path)
                            info['is_compressed'] = True
                            return info
            else:
                # 如果是目录
                info_file = backup_path / 'backup_info.json'
                if info_file.exists():
                    with open(info_file, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                        info['path'] = str(backup_path)
                        info['is_compressed'] = False
                        return info

            return None
        except Exception as e:
            logger.error(f"读取备份信息失败 {backup_path}: {e}")
            return None

    def get_latest_backup(self) -> Optional[Dict[str, Any]]:
        """获取最新的备份"""
        backups = self.list_available_backups()
        return backups[0] if backups else None

    def find_backup(self, backup_id: str) -> Optional[Path]:
        """查找指定备份"""
        # 在daily目录查找
        daily_path = self.daily_backup_dir / backup_id
        if daily_path.exists():
            return daily_path

        daily_zip = Path(f"{daily_path}.zip")
        if daily_zip.exists():
            return daily_zip

        # 在manual目录查找
        manual_path = self.manual_backup_dir / backup_id
        if manual_path.exists():
            return manual_path

        manual_zip = Path(f"{manual_path}.zip")
        if manual_zip.exists():
            return manual_zip

        return None

    def restore(
        self,
        backup_id: Optional[str] = None,
        use_latest: bool = False,
        items: Optional[List[str]] = None,
        target_dir: Optional[str] = None,
        create_pre_backup: bool = True,
        verify_after_restore: bool = True
    ) -> Dict[str, Any]:
        """
        执行恢复

        Args:
            backup_id: 指定备份ID
            use_latest: 使用最新备份
            items: 要恢复的项目列表（None表示全部）
            target_dir: 目标目录
            create_pre_backup: 恢复前是否备份当前数据
            verify_after_restore: 恢复后是否验证

        Returns:
            恢复结果
        """
        try:
            # 确定要恢复的备份
            if use_latest:
                backup_info = self.get_latest_backup()
                if not backup_info:
                    return {"status": "failed", "error": "没有找到可用备份"}
                backup_id = backup_info['backup_id']
                backup_path = Path(backup_info['path'])
            elif backup_id:
                backup_path = self.find_backup(backup_id)
                if not backup_path:
                    return {"status": "failed", "error": f"备份 {backup_id} 不存在"}
                backup_info = self._get_backup_info(backup_path)
            else:
                return {"status": "failed", "error": "请指定备份ID或使用 --latest"}

            logger.info(f"开始恢复备份: {backup_id}")

            # 确定目标目录
            target = Path(target_dir) if target_dir else Path('.')

            # 恢复前备份当前数据
            pre_backup_path = None
            if create_pre_backup:
                pre_backup_path = self._create_pre_backup(items)
                logger.info(f"已创建恢复前备份: {pre_backup_path}")

            # 解压备份（如果是压缩文件）
            extracted_path = self._extract_backup(backup_path)
            if not extracted_path:
                return {"status": "failed", "error": "解压备份失败"}

            # 确定要恢复的项目
            if items is None:
                items = list(backup_info.get('items', {}).keys())

            # 执行恢复
            restore_results = {}
            for item_name in items:
                result = self._restore_item(extracted_path, item_name, target)
                restore_results[item_name] = result

            # 清理临时解压目录
            if extracted_path != backup_path and extracted_path.exists():
                shutil.rmtree(extracted_path)

            # 验证恢复
            verification_result = None
            if verify_after_restore:
                verification_result = self._verify_restore(target, items)

            # 生成恢复报告
            success_count = sum(1 for r in restore_results.values() if r.get('status') == 'success')
            total_count = len(restore_results)

            result = {
                "status": "success" if success_count == total_count else "partial",
                "backup_id": backup_id,
                "timestamp": datetime.now().isoformat(),
                "items_restored": restore_results,
                "success_count": success_count,
                "total_count": total_count,
                "pre_backup_path": str(pre_backup_path) if pre_backup_path else None,
                "verification": verification_result
            }

            logger.info(f"恢复完成: {success_count}/{total_count} 项成功")
            return result

        except Exception as e:
            logger.error(f"恢复失败: {e}")
            return {"status": "failed", "error": str(e)}

    def _create_pre_backup(self, items: Optional[List[str]] = None) -> Path:
        """创建恢复前备份"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pre_backup_dir = Path(f"backups/pre_restore_backup_{timestamp}")
        pre_backup_dir.mkdir(parents=True, exist_ok=True)

        items_to_backup = items or ['data', 'models', 'config']

        for item_name in items_to_backup:
            item_path = Path(item_name)
            if item_path.exists():
                dest_path = pre_backup_dir / item_name
                try:
                    if item_path.is_dir():
                        shutil.copytree(item_path, dest_path)
                    else:
                        shutil.copy2(item_path, dest_path)
                except Exception as e:
                    logger.warning(f"恢复前备份 {item_name} 失败: {e}")

        # 保存备份信息
        info = {
            "backup_id": f"pre_restore_backup_{timestamp}",
            "backup_type": "pre_restore",
            "timestamp": datetime.now().isoformat(),
            "items": items_to_backup
        }
        with open(pre_backup_dir / 'backup_info.json', 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        return pre_backup_dir

    def _extract_backup(self, backup_path: Path) -> Optional[Path]:
        """解压备份"""
        if backup_path.suffix == '.zip':
            try:
                import zipfile
                extract_dir = backup_path.with_suffix('')
                extract_dir.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(extract_dir)

                logger.info(f"备份已解压到: {extract_dir}")
                return extract_dir
            except Exception as e:
                logger.error(f"解压备份失败: {e}")
                return None
        else:
            return backup_path

    def _restore_item(self, backup_path: Path, item_name: str, target: Path) -> Dict[str, Any]:
        """恢复单个项目"""
        try:
            source_path = backup_path / item_name
            if not source_path.exists():
                return {"status": "skipped", "reason": "not_found_in_backup"}

            target_path = target / item_name

            # 如果目标存在，先删除
            if target_path.exists():
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()

            # 复制数据
            if source_path.is_dir():
                shutil.copytree(source_path, target_path)
            else:
                shutil.copy2(source_path, target_path)

            logger.info(f"恢复 {item_name} 成功")
            return {"status": "success"}

        except Exception as e:
            logger.error(f"恢复 {item_name} 失败: {e}")
            return {"status": "failed", "error": str(e)}

    def _verify_restore(self, target: Path, items: List[str]) -> Dict[str, Any]:
        """验证恢复结果"""
        verification = {
            "timestamp": datetime.now().isoformat(),
            "items": {},
            "overall_status": "success"
        }

        for item_name in items:
            item_path = target / item_name
            if item_path.exists():
                # 检查是否为空
                if item_path.is_dir():
                    is_empty = not any(item_path.iterdir())
                    status = "success" if not is_empty else "warning"
                    message = "目录存在且不为空" if not is_empty else "目录存在但为空"
                else:
                    status = "success"
                    message = "文件存在"

                verification["items"][item_name] = {
                    "status": status,
                    "message": message,
                    "path": str(item_path)
                }
            else:
                verification["items"][item_name] = {
                    "status": "failed",
                    "message": "项目不存在",
                    "path": str(item_path)
                }
                verification["overall_status"] = "partial"

        return verification

    def interactive_restore(self):
        """交互式恢复"""
        print("\n" + "="*60)
        print("PL5 数据恢复工具")
        print("="*60 + "\n")

        # 列出可用备份
        backups = self.list_available_backups()

        if not backups:
            print("没有找到可用备份！")
            return

        print("可用备份列表:")
        print("-" * 60)
        for i, backup in enumerate(backups[:10], 1):
            backup_id = backup.get('backup_id', 'unknown')
            timestamp = backup.get('timestamp', 'unknown')
            backup_type = backup.get('backup_type', 'unknown')
            size_mb = backup.get('size_bytes', 0) / 1024 / 1024
            print(f"{i}. {backup_id}")
            print(f"   类型: {backup_type} | 时间: {timestamp} | 大小: {size_mb:.2f} MB")
            print()

        # 选择备份
        while True:
            choice = input("请选择要恢复的备份 (输入序号或备份ID，输入q退出): ").strip()

            if choice.lower() == 'q':
                print("已取消恢复")
                return

            # 尝试解析为序号
            try:
                index = int(choice) - 1
                if 0 <= index < len(backups):
                    selected_backup = backups[index]
                    break
                else:
                    print("无效的序号，请重新选择")
            except ValueError:
                # 尝试作为备份ID查找
                backup_path = self.find_backup(choice)
                if backup_path:
                    selected_backup = self._get_backup_info(backup_path)
                    break
                else:
                    print("未找到指定的备份，请重新输入")

        backup_id = selected_backup['backup_id']
        print(f"\n已选择备份: {backup_id}")

        # 选择恢复项目
        available_items = list(selected_backup.get('items', {}).keys())
        if not available_items:
            print("备份中没有可恢复的项目")
            return

        print(f"\n备份中包含以下项目: {', '.join(available_items)}")
        items_input = input("请输入要恢复的项目（用逗号分隔，输入all恢复全部，输入q退出）: ").strip()

        if items_input.lower() == 'q':
            print("已取消恢复")
            return

        if items_input.lower() == 'all':
            items_to_restore = None  # None表示恢复全部
        else:
            items_to_restore = [item.strip() for item in items_input.split(',')]

        # 确认恢复
        print("\n" + "!"*60)
        print("警告: 恢复操作将覆盖当前数据！")
        print("!"*60)
        confirm = input(f"确认要恢复备份 {backup_id} 吗？输入 'yes' 确认: ").strip()

        if confirm != 'yes':
            print("已取消恢复")
            return

        # 执行恢复
        print("\n开始恢复...")
        result = self.restore(
            backup_id=backup_id,
            items=items_to_restore,
            create_pre_backup=True,
            verify_after_restore=True
        )

        # 显示结果
        print("\n" + "="*60)
        print("恢复结果")
        print("="*60)
        print(f"状态: {result.get('status', 'unknown')}")
        print(f"成功恢复: {result.get('success_count', 0)}/{result.get('total_count', 0)} 项")

        if result.get('pre_backup_path'):
            print(f"恢复前备份: {result['pre_backup_path']}")

        if 'items_restored' in result:
            print("\n详细结果:")
            for item, item_result in result['items_restored'].items():
                status = item_result.get('status', 'unknown')
                symbol = "✓" if status == 'success' else "✗" if status == 'failed' else "○"
                print(f"  {symbol} {item}: {status}")

        if result.get('verification'):
            print("\n验证结果:")
            verification = result['verification']
            for item, v in verification.get('items', {}).items():
                status = v.get('status', 'unknown')
                symbol = "✓" if status == 'success' else "!" if status == 'warning' else "✗"
                print(f"  {symbol} {item}: {v.get('message', status)}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PL5 数据恢复工具')
    parser.add_argument('--list', action='store_true', help='列出所有可用备份')
    parser.add_argument('--latest', action='store_true', help='使用最新备份')
    parser.add_argument('--backup-id', type=str, help='指定备份ID')
    parser.add_argument('--items', type=str, help='要恢复的项目，用逗号分隔')
    parser.add_argument('--target', type=str, help='目标目录')
    parser.add_argument('--no-pre-backup', action='store_true', help='恢复前不备份当前数据')
    parser.add_argument('--no-verify', action='store_true', help='恢复后不验证')
    parser.add_argument('--interactive', '-i', action='store_true', help='交互式恢复')

    args = parser.parse_args()

    restorer = BackupRestorer()

    if args.interactive:
        restorer.interactive_restore()

    elif args.list:
        backups = restorer.list_available_backups()
        print(json.dumps(backups, ensure_ascii=False, indent=2))

    elif args.latest or args.backup_id:
        items = None
        if args.items:
            items = [item.strip() for item in args.items.split(',')]

        result = restorer.restore(
            backup_id=args.backup_id,
            use_latest=args.latest,
            items=items,
            target_dir=args.target,
            create_pre_backup=not args.no_pre_backup,
            verify_after_restore=not args.no_verify
        )

        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        print("\n提示: 使用 --interactive 或 -i 启动交互式恢复向导")


if __name__ == "__main__":
    main()
