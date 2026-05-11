#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据备份与恢复模块
实现系统数据的自动备份和恢复功能
"""

import os
import shutil
import json
import time
import logging
import hashlib
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.core.utils.logger import setup_logging

logger = setup_logging(__name__)


class BackupManager:
    """备份管理器"""

    def __init__(
        self,
        backup_dir: Optional[Path] = None,
        max_backups: int = 10,
        encryption: bool = False,
        encryption_password: Optional[str] = None,
    ):
        """初始化备份管理器

        Args:
            backup_dir: 备份目录
            max_backups: 最大备份数量
            encryption: 是否启用备份加密
            encryption_password: 加密密码
        """
        self.backup_dir = backup_dir or Path("backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.max_backups = max_backups
        self.encryption = encryption
        self.encryption_password = encryption_password

        # 定义需要备份的目录和文件
        self.backup_items = {
            "models": Path("models"),
            "data": Path("data"),
            "config": Path("config"),
            "logs": Path("logs"),
        }

        # 自动备份策略
        self.auto_backup = {"enabled": True, "interval": 24, "last_backup": None}  # 小时

        logger.info(f"备份管理器初始化完成，备份目录: {self.backup_dir}")
        if self.encryption:
            logger.info("备份加密功能已启用")

    def create_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """创建备份

        Args:
            backup_name: 备份名称

        Returns:
            备份结果
        """
        try:
            # 生成备份名称
            if backup_name:
                backup_id = backup_name
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_id = f"backup_{timestamp}"

            backup_path = self.backup_dir / backup_id
            backup_path.mkdir(parents=True, exist_ok=True)

            backup_info = {
                "backup_id": backup_id,
                "timestamp": datetime.now().isoformat(),
                "items": {},
                "status": "success",
            }

            # 备份各个项目
            for item_name, item_path in self.backup_items.items():
                if item_path.exists():
                    dest_path = backup_path / item_name
                    try:
                        if item_path.is_dir():
                            shutil.copytree(item_path, dest_path)
                        else:
                            shutil.copy2(item_path, dest_path)
                        backup_info["items"][item_name] = "success"
                        logger.info(f"备份 {item_name} 成功")
                    except Exception as e:
                        backup_info["items"][item_name] = f"失败: {str(e)}"
                        logger.error(f"备份 {item_name} 失败: {str(e)}")
                else:
                    backup_info["items"][item_name] = "不存在"
                    logger.warning(f"备份项目 {item_name} 不存在")

            # 保存备份信息
            info_file = backup_path / "backup_info.json"
            with open(info_file, "w", encoding="utf-8") as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=2)

            # 验证备份完整性
            if not self._verify_backup_integrity(backup_path):
                logger.error("备份完整性验证失败")
                backup_info["status"] = "failed"
                backup_info["error"] = "备份完整性验证失败"
                return backup_info

            # 压缩备份
            backup_path = self._compress_backup(backup_path)

            # 如果启用了加密，加密备份
            if self.encryption:
                backup_path = self._encrypt_backup(backup_path)

            # 清理旧备份
            self._cleanup_old_backups()

            logger.info(f"备份创建成功: {backup_id}")
            return backup_info

        except Exception as e:
            logger.error(f"创建备份失败: {str(e)}")
            return {"backup_id": "error", "timestamp": datetime.now().isoformat(), "status": "failed", "error": str(e)}

    def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """恢复备份

        Args:
            backup_id: 备份ID

        Returns:
            恢复结果
        """
        try:
            backup_path = self.backup_dir / backup_id
            if not backup_path.exists():
                # 尝试查找压缩文件
                zip_path = Path(f"{backup_path}.zip")
                if zip_path.exists():
                    backup_path = zip_path
                else:
                    error_msg = f"备份 {backup_id} 不存在"
                    logger.error(error_msg)
                    return {"status": "failed", "error": error_msg}

            # 如果是压缩文件，解压缩
            if backup_path.suffix == ".zip":
                backup_path = self._decompress_backup(backup_path)

            # 如果启用了加密，解密备份
            if self.encryption:
                backup_path = self._decrypt_backup(backup_path)

            # 验证备份完整性
            if not self._verify_backup_integrity(backup_path):
                logger.error("备份完整性验证失败")
                return {"status": "failed", "error": "备份完整性验证失败"}

            # 读取备份信息
            info_file = backup_path / "backup_info.json"
            if info_file.exists():
                with open(info_file, "r", encoding="utf-8") as f:
                    backup_info = json.load(f)
            else:
                backup_info = {"items": {}}

            restore_result = {
                "backup_id": backup_id,
                "timestamp": datetime.now().isoformat(),
                "items": {},
                "status": "success",
            }

            # 恢复各个项目
            for item_name, item_path in self.backup_items.items():
                backup_item_path = backup_path / item_name
                if backup_item_path.exists():
                    try:
                        # 先备份当前数据（以防恢复失败）
                        temp_backup = Path(f"{item_path}_temp_{int(time.time())}")
                        if item_path.exists():
                            if item_path.is_dir():
                                shutil.copytree(item_path, temp_backup)
                            else:
                                shutil.copy2(item_path, temp_backup)

                        # 恢复数据
                        if item_path.exists():
                            if item_path.is_dir():
                                shutil.rmtree(item_path)
                            else:
                                item_path.unlink()

                        if backup_item_path.is_dir():
                            shutil.copytree(backup_item_path, item_path)
                        else:
                            shutil.copy2(backup_item_path, item_path)

                        # 清理临时备份
                        if temp_backup.exists():
                            if temp_backup.is_dir():
                                shutil.rmtree(temp_backup)
                            else:
                                temp_backup.unlink()

                        restore_result["items"][item_name] = "success"
                        logger.info(f"恢复 {item_name} 成功")

                    except Exception as e:
                        # 恢复失败，尝试恢复临时备份
                        if temp_backup.exists():
                            try:
                                if item_path.exists():
                                    if item_path.is_dir():
                                        shutil.rmtree(item_path)
                                    else:
                                        item_path.unlink()

                                if temp_backup.is_dir():
                                    shutil.copytree(temp_backup, item_path)
                                else:
                                    shutil.copy2(temp_backup, item_path)
                                logger.info(f"恢复临时备份成功")
                            except Exception as restore_e:
                                logger.error(f"恢复临时备份失败: {str(restore_e)}")

                        restore_result["items"][item_name] = f"失败: {str(e)}"
                        logger.error(f"恢复 {item_name} 失败: {str(e)}")
                else:
                    restore_result["items"][item_name] = "备份中不存在"
                    logger.warning(f"备份中 {item_name} 不存在")

            logger.info(f"备份恢复成功: {backup_id}")
            return restore_result

        except Exception as e:
            logger.error(f"恢复备份失败: {str(e)}")
            return {"status": "failed", "error": str(e)}

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份

        Returns:
            备份列表
        """
        backups = []
        try:
            for backup_item in self.backup_dir.iterdir():
                if backup_item.is_dir():
                    # 处理目录形式的备份
                    info_file = backup_item / "backup_info.json"
                    if info_file.exists():
                        try:
                            with open(info_file, "r", encoding="utf-8") as f:
                                backup_info = json.load(f)
                            backups.append(backup_info)
                        except Exception as e:
                            logger.error(f"读取备份信息失败: {str(e)}")
                elif backup_item.suffix == ".zip":
                    # 处理压缩文件形式的备份
                    backup_id = backup_item.stem
                    # 尝试从压缩文件中读取备份信息
                    try:
                        with zipfile.ZipFile(backup_item, "r") as zipf:
                            if "backup_info.json" in zipf.namelist():
                                with zipf.open("backup_info.json") as f:
                                    backup_info = json.load(f)
                                backups.append(backup_info)
                    except Exception as e:
                        logger.error(f"读取压缩备份信息失败: {str(e)}")

            # 按时间排序
            backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return backups

        except Exception as e:
            logger.error(f"列出备份失败: {str(e)}")
            return []

    def get_latest_backup(self) -> Optional[Dict[str, Any]]:
        """获取最新的备份

        Returns:
            最新备份信息
        """
        backups = self.list_backups()
        return backups[0] if backups else None

    def delete_backup(self, backup_id: str) -> bool:
        """删除备份

        Args:
            backup_id: 备份ID

        Returns:
            是否删除成功
        """
        try:
            # 尝试删除目录形式的备份
            backup_path = self.backup_dir / backup_id
            if backup_path.exists():
                shutil.rmtree(backup_path)
                logger.info(f"备份 {backup_id} 删除成功")
                return True

            # 尝试删除压缩文件形式的备份
            zip_path = Path(f"{backup_path}.zip")
            if zip_path.exists():
                zip_path.unlink()
                logger.info(f"压缩备份 {backup_id} 删除成功")
                return True

            logger.warning(f"备份 {backup_id} 不存在")
            return False
        except Exception as e:
            logger.error(f"删除备份失败: {str(e)}")
            return False

    def _cleanup_old_backups(self):
        """清理旧备份，保持备份数量在最大限制内"""
        try:
            backups = self.list_backups()
            if len(backups) > self.max_backups:
                backups_to_delete = backups[self.max_backups :]
                for backup in backups_to_delete:
                    backup_id = backup.get("backup_id")
                    if backup_id:
                        self.delete_backup(backup_id)

        except Exception as e:
            logger.error(f"清理旧备份失败: {str(e)}")

    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件的哈希值

        Args:
            file_path: 文件路径

        Returns:
            文件的哈希值
        """
        try:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(65536)  # 64KB chunks
                    if not data:
                        break
                    hasher.update(data)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败: {str(e)}")
            return ""

    def _verify_backup_integrity(self, backup_path: Path) -> bool:
        """验证备份的完整性

        Args:
            backup_path: 备份路径

        Returns:
            备份是否完整
        """
        try:
            info_file = backup_path / "backup_info.json"
            if not info_file.exists():
                logger.error("备份信息文件不存在")
                return False

            with open(info_file, "r", encoding="utf-8") as f:
                backup_info = json.load(f)

            # 验证备份项目
            for item_name, status in backup_info.get("items", {}).items():
                if status == "success":
                    item_path = backup_path / item_name
                    if not item_path.exists():
                        logger.error(f"备份项目 {item_name} 不存在")
                        return False

            logger.info("备份完整性验证通过")
            return True
        except Exception as e:
            logger.error(f"验证备份完整性失败: {str(e)}")
            return False

    def _compress_backup(self, backup_path: Path) -> Path:
        """压缩备份

        Args:
            backup_path: 备份路径

        Returns:
            压缩文件路径
        """
        try:
            zip_path = Path(f"{backup_path}.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(backup_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(backup_path)
                        zipf.write(file_path, arcname)

            # 删除原始备份目录
            shutil.rmtree(backup_path)
            logger.info(f"备份已压缩: {zip_path}")
            return zip_path
        except Exception as e:
            logger.error(f"压缩备份失败: {str(e)}")
            return backup_path

    def _decompress_backup(self, zip_path: Path) -> Path:
        """解压缩备份

        Args:
            zip_path: 压缩文件路径

        Returns:
            解压后的备份路径
        """
        try:
            backup_path = zip_path.with_suffix("")
            backup_path.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zipf:
                zipf.extractall(backup_path)

            logger.info(f"备份已解压: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"解压缩备份失败: {str(e)}")
            return zip_path

    def _encrypt_backup(self, backup_path: Path) -> Path:
        """加密备份

        Args:
            backup_path: 备份路径

        Returns:
            加密后的备份路径
        """
        # 这里可以实现备份加密功能
        # 由于加密实现比较复杂，这里暂时返回原路径
        logger.info("备份加密功能暂未实现")
        return backup_path

    def _decrypt_backup(self, backup_path: Path) -> Path:
        """解密备份

        Args:
            backup_path: 备份路径

        Returns:
            解密后的备份路径
        """
        # 这里可以实现备份解密功能
        # 由于解密实现比较复杂，这里暂时返回原路径
        logger.info("备份解密功能暂未实现")
        return backup_path

    def check_auto_backup(self) -> bool:
        """检查是否需要执行自动备份

        Returns:
            是否需要执行自动备份
        """
        if not self.auto_backup["enabled"]:
            return False

        last_backup = self.auto_backup["last_backup"]
        if not last_backup:
            return True

        last_backup_time = datetime.fromisoformat(last_backup)
        time_since_last_backup = (datetime.now() - last_backup_time).total_seconds() / 3600  # 小时

        return time_since_last_backup >= self.auto_backup["interval"]

    def run_auto_backup(self) -> Dict[str, Any]:
        """执行自动备份

        Returns:
            备份结果
        """
        if self.check_auto_backup():
            logger.info("执行自动备份")
            result = self.create_backup("auto_backup")
            if result.get("status") == "success":
                self.auto_backup["last_backup"] = datetime.now().isoformat()
            return result
        else:
            logger.info("不需要执行自动备份")
            return {"status": "skipped", "message": "自动备份间隔未到"}

    def backup_models(self) -> Dict[str, Any]:
        """仅备份模型"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_id = f"models_backup_{timestamp}"
            backup_path = self.backup_dir / backup_id
            backup_path.mkdir(parents=True, exist_ok=True)

            model_path = self.backup_items["models"]
            if model_path.exists():
                dest_path = backup_path / "models"
                shutil.copytree(model_path, dest_path)
                logger.info("模型备份成功")
                return {"status": "success", "backup_id": backup_id}
            else:
                logger.warning("模型目录不存在")
                return {"status": "failed", "error": "模型目录不存在"}
        except Exception as e:
            logger.error(f"模型备份失败: {str(e)}")
            return {"status": "failed", "error": str(e)}

    def restore_models(self, backup_id: str) -> Dict[str, Any]:
        """仅恢复模型"""
        try:
            backup_path = self.backup_dir / backup_id
            model_backup_path = backup_path / "models"

            if not model_backup_path.exists():
                return {"status": "failed", "error": "模型备份不存在"}

            model_path = self.backup_items["models"]
            # 先备份当前模型
            temp_backup = Path(f"models_temp_{int(time.time())}")
            if model_path.exists():
                shutil.copytree(model_path, temp_backup)

            # 恢复模型
            if model_path.exists():
                shutil.rmtree(model_path)
            shutil.copytree(model_backup_path, model_path)

            # 清理临时备份
            if temp_backup.exists():
                shutil.rmtree(temp_backup)

            logger.info("模型恢复成功")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"模型恢复失败: {str(e)}")
            return {"status": "failed", "error": str(e)}


# 全局备份管理器实例
_global_backup_manager = None


def get_backup_manager() -> BackupManager:
    """获取全局备份管理器实例"""
    global _global_backup_manager
    if _global_backup_manager is None:
        _global_backup_manager = BackupManager(encryption=False)
    return _global_backup_manager


def create_backup(backup_name: Optional[str] = None) -> Dict[str, Any]:
    """创建备份"""
    manager = get_backup_manager()
    return manager.create_backup(backup_name)


def restore_backup(backup_id: str) -> Dict[str, Any]:
    """恢复备份"""
    manager = get_backup_manager()
    return manager.restore_backup(backup_id)


def list_backups() -> List[Dict[str, Any]]:
    """列出所有备份"""
    manager = get_backup_manager()
    return manager.list_backups()


def get_latest_backup() -> Optional[Dict[str, Any]]:
    """获取最新的备份"""
    manager = get_backup_manager()
    return manager.get_latest_backup()


def backup_models() -> Dict[str, Any]:
    """备份模型"""
    manager = get_backup_manager()
    return manager.backup_models()


def restore_models(backup_id: str) -> Dict[str, Any]:
    """恢复模型"""
    manager = get_backup_manager()
    return manager.restore_models(backup_id)
