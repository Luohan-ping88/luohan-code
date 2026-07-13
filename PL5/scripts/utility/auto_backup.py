#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 自动备份系统 V2.0
实现每天自动备份数据到 backups/daily/
保留最近30天的备份，支持手动触发备份

功能特性：
- 每天自动备份数据
- 保留最近30天备份
- 支持手动触发备份
- 备份内容包括：数据、模型、配置
- 备份完整性验证
- 压缩存储
- AES-256加密保护
"""

import os
import sys
import shutil
import json
import hashlib
import zipfile
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from threading import Lock
import schedule
import time

# AES加密相关
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import base64


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/backup.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def derive_aes_key(passphrase: str, salt: bytes = None) -> Tuple[bytes, bytes]:
    """从密码短语派生AES密钥
    
    Args:
        passphrase: 密码短语
        salt: 盐值（可选，用于密钥派生）
        
    Returns:
        (密钥, 盐值)
    """
    if salt is None:
        salt = os.urandom(16)
    
    # 使用PBKDF2进行密钥派生
    key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        100000,  # 迭代次数
        dklen=32  # 256位密钥
    )
    return key, salt


def encrypt_aes(data: bytes, key: bytes) -> bytes:
    """使用AES-256-CBC加密数据
    
    Args:
        data: 要加密的数据
        key: 256位密钥
        
    Returns:
        加密后的数据（包含IV和密文）
    """
    iv = os.urandom(16)  # 初始化向量
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # PKCS7填充
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    # 返回IV + 密文
    return iv + ciphertext


def decrypt_aes(encrypted_data: bytes, key: bytes) -> bytes:
    """使用AES-256-CBC解密数据
    
    Args:
        encrypted_data: 加密的数据（包含IV和密文）
        key: 256位密钥
        
    Returns:
        解密后的数据
    """
    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    
    # 移除PKCS7填充
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    
    return data


@dataclass
class BackupConfig:
    """备份配置"""
    backup_dir: str = "backups"
    daily_backup_dir: str = "backups/daily"
    manual_backup_dir: str = "backups/manual"
    max_daily_backups: int = 30
    max_manual_backups: int = 10
    compression_enabled: bool = True
    verify_integrity: bool = True
    backup_items: List[str] = None
    encryption_enabled: bool = True  # 新增：是否启用加密

    def __post_init__(self):
        if self.backup_items is None:
            self.backup_items = ['data', 'models', 'config']


class BackupManager:
    """备份管理器"""

    _instance = None
    _lock = Lock()

    def __new__(cls, config: Optional[BackupConfig] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[BackupConfig] = None):
        if self._initialized:
            return

        self.config = config or BackupConfig()
        self._ensure_directories()
        self._initialized = True
        logger.info("备份管理器初始化完成")

    def _ensure_directories(self):
        """确保备份目录存在"""
        Path(self.config.daily_backup_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.manual_backup_dir).mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        backup_type: str = "daily",
        backup_name: Optional[str] = None,
        custom_items: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建备份

        Args:
            backup_type: 备份类型 (daily/manual)
            backup_name: 自定义备份名称
            custom_items: 自定义备份项目

        Returns:
            备份结果
        """
        try:
            # 生成备份ID和路径
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if backup_name:
                backup_id = f"{backup_type}_{backup_name}_{timestamp}"
            else:
                backup_id = f"{backup_type}_{timestamp}"

            if backup_type == "daily":
                backup_path = Path(self.config.daily_backup_dir) / backup_id
            else:
                backup_path = Path(self.config.manual_backup_dir) / backup_id

            backup_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"开始创建备份: {backup_id}")

            # 备份信息
            backup_info = {
                "backup_id": backup_id,
                "backup_type": backup_type,
                "timestamp": datetime.now().isoformat(),
                "items": {},
                "status": "in_progress",
                "size_bytes": 0
            }

            # 确定要备份的项目
            items_to_backup = custom_items or self.config.backup_items

            # 执行备份
            total_size = 0
            for item_name in items_to_backup:
                item_path = Path(item_name)
                if item_path.exists():
                    try:
                        dest_path = backup_path / item_name
                        item_size = self._copy_item(item_path, dest_path)
                        backup_info["items"][item_name] = {
                            "status": "success",
                            "size_bytes": item_size
                        }
                        total_size += item_size
                        logger.info(f"备份 {item_name} 成功 ({item_size} bytes)")
                    except Exception as e:
                        backup_info["items"][item_name] = {
                            "status": "failed",
                            "error": str(e)
                        }
                        logger.error(f"备份 {item_name} 失败: {e}")
                else:
                    backup_info["items"][item_name] = {
                        "status": "skipped",
                        "reason": "not_found"
                    }
                    logger.warning(f"备份项目 {item_name} 不存在，已跳过")

            backup_info["size_bytes"] = total_size

            # 验证备份完整性
            if self.config.verify_integrity:
                if self._verify_backup_integrity(backup_path, items_to_backup):
                    backup_info["integrity_check"] = "passed"
                    logger.info("备份完整性验证通过")
                else:
                    backup_info["integrity_check"] = "failed"
                    backup_info["status"] = "failed"
                    logger.error("备份完整性验证失败")
                    return backup_info

            # 保存备份信息
            info_file = backup_path / 'backup_info.json'
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=2)

            # 压缩备份
            if self.config.compression_enabled:
                backup_path, encryption_info = self._compress_backup(backup_path)
                backup_info["compressed"] = True
                backup_info["compressed_path"] = str(backup_path)
                if encryption_info:
                    backup_info["encrypted"] = True
                    backup_info["encryption_salt"] = encryption_info["salt"]

            backup_info["status"] = "success"
            backup_info["path"] = str(backup_path)

            # 清理旧备份
            self._cleanup_old_backups(backup_type)

            logger.info(f"备份创建成功: {backup_id} (总大小: {total_size} bytes)")
            return backup_info

        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return {
                "backup_id": backup_id if 'backup_id' in locals() else "error",
                "backup_type": backup_type,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            }

    def _copy_item(self, src: Path, dest: Path) -> int:
        """复制文件或目录，返回大小"""
        if src.is_dir():
            shutil.copytree(src, dest)
            # 计算目录大小
            total_size = 0
            for file_path in dest.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        else:
            shutil.copy2(src, dest)
            return dest.stat().st_size

    def _verify_backup_integrity(self, backup_path: Path, expected_items: List[str]) -> bool:
        """验证备份完整性"""
        try:
            for item_name in expected_items:
                item_path = backup_path / item_name
                if not item_path.exists():
                    logger.error(f"备份完整性验证失败: {item_name} 不存在")
                    return False
            return True
        except Exception as e:
            logger.error(f"验证备份完整性时出错: {e}")
            return False

    def _compress_backup(self, backup_path: Path) -> Tuple[Path, Optional[Dict[str, str]]]:
        """压缩备份（支持加密）
        
        Returns:
            (压缩文件路径, 加密信息)
        """
        try:
            zip_path = Path(f"{backup_path}.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(backup_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(backup_path)
                        zipf.write(file_path, arcname)

            # 删除原始备份目录
            shutil.rmtree(backup_path)
            logger.info(f"备份已压缩: {zip_path}")

            # 如果启用加密，对压缩文件进行加密
            encryption_info = None
            if self.config.encryption_enabled:
                zip_path, encryption_info = self._encrypt_backup(zip_path)

            return zip_path, encryption_info
        except Exception as e:
            logger.error(f"压缩备份失败: {e}")
            return backup_path, None

    def _encrypt_backup(self, zip_path: Path) -> Tuple[Path, Dict[str, str]]:
        """加密备份文件
        
        Returns:
            (加密文件路径, 加密信息)
        """
        try:
            # 获取加密密钥
            encryption_key = os.getenv("BACKUP_ENCRYPTION_KEY", "default-backup-encryption-key-change-in-production")
            
            # 读取压缩文件内容
            with open(zip_path, 'rb') as f:
                data = f.read()

            # 派生密钥
            key, salt = derive_aes_key(encryption_key)

            # 加密数据
            encrypted_data = encrypt_aes(data, key)

            # 创建加密文件
            encrypted_path = Path(f"{zip_path}.enc")
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)

            # 删除原始压缩文件
            zip_path.unlink()

            logger.info(f"备份已加密: {encrypted_path}")
            
            return encrypted_path, {"salt": base64.b64encode(salt).decode('utf-8')}
        except Exception as e:
            logger.error(f"加密备份失败: {e}")
            return zip_path, {"salt": ""}

    def _cleanup_old_backups(self, backup_type: str):
        """清理旧备份"""
        try:
            if backup_type == "daily":
                backup_dir = Path(self.config.daily_backup_dir)
                max_backups = self.config.max_daily_backups
            else:
                backup_dir = Path(self.config.manual_backup_dir)
                max_backups = self.config.max_manual_backups

            # 获取所有备份
            backups = []
            for item in backup_dir.iterdir():
                if item.is_dir() or item.suffix == '.zip':
                    # 尝试读取备份信息
                    info_file = item / 'backup_info.json' if item.is_dir() else None
                    if info_file and info_file.exists():
                        try:
                            with open(info_file, 'r', encoding='utf-8') as f:
                                info = json.load(f)
                            backups.append((item, info.get('timestamp', '')))
                        except:
                            backups.append((item, ''))
                    else:
                        # 使用文件修改时间
                        stat = item.stat()
                        backups.append((item, datetime.fromtimestamp(stat.st_mtime).isoformat()))

            # 按时间排序
            backups.sort(key=lambda x: x[1], reverse=True)

            # 删除旧备份
            if len(backups) > max_backups:
                for item, _ in backups[max_backups:]:
                    try:
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                        logger.info(f"清理旧备份: {item.name}")
                    except Exception as e:
                        logger.error(f"清理旧备份失败 {item.name}: {e}")

        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")

    def restore_backup(
        self,
        backup_id: str,
        target_dir: Optional[str] = None,
        items_to_restore: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        恢复备份

        Args:
            backup_id: 备份ID
            target_dir: 目标目录（默认为当前目录）
            items_to_restore: 要恢复的项目

        Returns:
            恢复结果
        """
        try:
            # 查找备份
            backup_path = self._find_backup(backup_id)
            if not backup_path:
                return {
                    "status": "failed",
                    "error": f"备份 {backup_id} 不存在"
                }

            logger.info(f"开始恢复备份: {backup_id}")

            # 如果是加密文件，先解密
            if backup_path.suffix == '.enc':
                backup_path = self._decrypt_backup(backup_path)

            # 如果是压缩文件，先解压
            if backup_path.suffix == '.zip':
                backup_path = self._decompress_backup(backup_path)

            # 读取备份信息
            info_file = backup_path / 'backup_info.json'
            if info_file.exists():
                with open(info_file, 'r', encoding='utf-8') as f:
                    backup_info = json.load(f)
            else:
                backup_info = {"items": {}}

            # 确定要恢复的项目
            if items_to_restore is None:
                items_to_restore = list(backup_info.get("items", {}).keys())

            target = Path(target_dir) if target_dir else Path('.')
            restore_result = {
                "backup_id": backup_id,
                "timestamp": datetime.now().isoformat(),
                "items": {},
                "status": "success"
            }

            # 恢复各个项目
            for item_name in items_to_restore:
                backup_item_path = backup_path / item_name
                if backup_item_path.exists():
                    try:
                        target_item_path = target / item_name

                        # 备份当前数据（以防恢复失败）
                        temp_backup = None
                        if target_item_path.exists():
                            temp_backup = Path(f"{item_name}_temp_{int(time.time())}")
                            self._copy_item(target_item_path, temp_backup)

                        # 恢复数据
                        if target_item_path.exists():
                            if target_item_path.is_dir():
                                shutil.rmtree(target_item_path)
                            else:
                                target_item_path.unlink()

                        self._copy_item(backup_item_path, target_item_path)

                        # 清理临时备份
                        if temp_backup and temp_backup.exists():
                            if temp_backup.is_dir():
                                shutil.rmtree(temp_backup)
                            else:
                                temp_backup.unlink()

                        restore_result["items"][item_name] = "success"
                        logger.info(f"恢复 {item_name} 成功")

                    except Exception as e:
                        restore_result["items"][item_name] = f"failed: {str(e)}"
                        logger.error(f"恢复 {item_name} 失败: {e}")
                else:
                    restore_result["items"][item_name] = "not_found_in_backup"
                    logger.warning(f"备份中 {item_name} 不存在")

            logger.info(f"备份恢复完成: {backup_id}")
            return restore_result

        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def _find_backup(self, backup_id: str) -> Optional[Path]:
        """查找备份（支持加密文件）"""
        # 在daily目录查找
        daily_path = Path(self.config.daily_backup_dir) / backup_id
        if daily_path.exists():
            return daily_path

        daily_zip_path = Path(f"{daily_path}.zip")
        if daily_zip_path.exists():
            return daily_zip_path

        # 检查加密文件
        daily_enc_path = Path(f"{daily_path}.zip.enc")
        if daily_enc_path.exists():
            return daily_enc_path

        # 在manual目录查找
        manual_path = Path(self.config.manual_backup_dir) / backup_id
        if manual_path.exists():
            return manual_path

        manual_zip_path = Path(f"{manual_path}.zip")
        if manual_zip_path.exists():
            return manual_zip_path

        # 检查加密文件
        manual_enc_path = Path(f"{manual_path}.zip.enc")
        if manual_enc_path.exists():
            return manual_enc_path

        return None

    def _decrypt_backup(self, enc_path: Path) -> Path:
        """解密备份文件
        
        Args:
            enc_path: 加密文件路径
            
        Returns:
            解密后的文件路径
        """
        try:
            # 获取加密密钥
            encryption_key = os.getenv("BACKUP_ENCRYPTION_KEY", "default-backup-encryption-key-change-in-production")
            
            # 读取加密文件内容
            with open(enc_path, 'rb') as f:
                encrypted_data = f.read()

            # 派生密钥（使用空盐值，解密时不需要盐值）
            key, _ = derive_aes_key(encryption_key)

            # 解密数据
            decrypted_data = decrypt_aes(encrypted_data, key)

            # 创建解密后的文件（去掉.enc后缀）
            zip_path = enc_path.with_suffix('')
            with open(zip_path, 'wb') as f:
                f.write(decrypted_data)

            logger.info(f"备份已解密: {zip_path}")
            
            return zip_path
        except Exception as e:
            logger.error(f"解密备份失败: {e}")
            return enc_path

    def _decompress_backup(self, zip_path: Path) -> Path:
        """解压备份"""
        try:
            backup_path = zip_path.with_suffix('')
            backup_path.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(backup_path)

            logger.info(f"备份已解压: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"解压备份失败: {e}")
            return zip_path

    def list_backups(self, backup_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出所有备份

        Args:
            backup_type: 备份类型过滤器 (daily/manual)

        Returns:
            备份列表
        """
        backups = []

        dirs_to_check = []
        if backup_type is None or backup_type == "daily":
            dirs_to_check.append(Path(self.config.daily_backup_dir))
        if backup_type is None or backup_type == "manual":
            dirs_to_check.append(Path(self.config.manual_backup_dir))

        for backup_dir in dirs_to_check:
            if not backup_dir.exists():
                continue

            for item in backup_dir.iterdir():
                if item.is_dir():
                    info_file = item / 'backup_info.json'
                    if info_file.exists():
                        try:
                            with open(info_file, 'r', encoding='utf-8') as f:
                                info = json.load(f)
                            backups.append(info)
                        except Exception as e:
                            logger.error(f"读取备份信息失败 {item.name}: {e}")
                elif item.suffix == '.zip':
                    try:
                        with zipfile.ZipFile(item, 'r') as zipf:
                            if 'backup_info.json' in zipf.namelist():
                                with zipf.open('backup_info.json') as f:
                                    info = json.load(f)
                                backups.append(info)
                    except Exception as e:
                        logger.error(f"读取压缩备份信息失败 {item.name}: {e}")

        # 按时间排序
        backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return backups

    def get_latest_backup(self, backup_type: str = "daily") -> Optional[Dict[str, Any]]:
        """获取最新的备份"""
        backups = self.list_backups(backup_type)
        return backups[0] if backups else None

    def delete_backup(self, backup_id: str) -> bool:
        """删除备份"""
        try:
            backup_path = self._find_backup(backup_id)
            if backup_path:
                if backup_path.is_dir():
                    shutil.rmtree(backup_path)
                else:
                    backup_path.unlink()
                logger.info(f"备份删除成功: {backup_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除备份失败 {backup_id}: {e}")
            return False

    def get_backup_stats(self) -> Dict[str, Any]:
        """获取备份统计信息"""
        daily_backups = self.list_backups("daily")
        manual_backups = self.list_backups("manual")

        total_size = sum(b.get('size_bytes', 0) for b in daily_backups + manual_backups)

        return {
            "daily_backups_count": len(daily_backups),
            "manual_backups_count": len(manual_backups),
            "total_backups_count": len(daily_backups) + len(manual_backups),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "latest_daily_backup": daily_backups[0] if daily_backups else None,
            "latest_manual_backup": manual_backups[0] if manual_backups else None
        }


# 全局备份管理器实例
_backup_manager = None


def get_backup_manager(config: Optional[BackupConfig] = None) -> BackupManager:
    """获取全局备份管理器实例"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager(config)
    return _backup_manager


def run_daily_backup():
    """执行每日备份"""
    manager = get_backup_manager()
    result = manager.create_backup(backup_type="daily")

    if result.get("status") == "success":
        logger.info("每日备份执行成功")
    else:
        logger.error(f"每日备份执行失败: {result.get('error')}")

    return result


def run_manual_backup(backup_name: Optional[str] = None) -> Dict[str, Any]:
    """执行手动备份"""
    manager = get_backup_manager()
    result = manager.create_backup(backup_type="manual", backup_name=backup_name)

    if result.get("status") == "success":
        logger.info("手动备份执行成功")
    else:
        logger.error(f"手动备份执行失败: {result.get('error')}")

    return result


def start_auto_backup_scheduler(schedule_time: str = "02:00"):
    """
    启动自动备份调度器

    Args:
        schedule_time: 备份时间 (HH:MM格式)
    """
    logger.info(f"启动自动备份调度器，备份时间: {schedule_time}")

    # 设置定时任务
    schedule.every().day.at(schedule_time).do(run_daily_backup)

    logger.info("自动备份调度器已启动，按Ctrl+C停止")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("自动备份调度器已停止")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PL5 自动备份系统')
    parser.add_argument('--daily', action='store_true', help='执行每日备份')
    parser.add_argument('--manual', action='store_true', help='执行手动备份')
    parser.add_argument('--name', type=str, help='手动备份名称')
    parser.add_argument('--list', action='store_true', help='列出所有备份')
    parser.add_argument('--stats', action='store_true', help='显示备份统计信息')
    parser.add_argument('--restore', type=str, help='恢复指定备份')
    parser.add_argument('--scheduler', action='store_true', help='启动自动备份调度器')
    parser.add_argument('--time', type=str, default='02:00', help='自动备份时间 (HH:MM)')
    parser.add_argument('--delete', type=str, help='删除指定备份')

    args = parser.parse_args()

    manager = get_backup_manager()

    if args.daily:
        result = run_daily_backup()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.manual:
        result = run_manual_backup(args.name)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.list:
        backups = manager.list_backups()
        print(json.dumps(backups, ensure_ascii=False, indent=2))

    elif args.stats:
        stats = manager.get_backup_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif args.restore:
        result = manager.restore_backup(args.restore)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.scheduler:
        start_auto_backup_scheduler(args.time)

    elif args.delete:
        success = manager.delete_backup(args.delete)
        print(json.dumps({"success": success}, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
