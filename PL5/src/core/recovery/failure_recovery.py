#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
故障恢复模块
实现系统故障检测和自动恢复功能
"""

import os
import sys
import time
import logging
import threading
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from src.core.utils.logger import setup_logging
from src.core.backup.backup_manager import get_latest_backup, restore_backup

logger = setup_logging(__name__)


class FailureRecovery:
    """故障恢复管理器"""

    def __init__(self, max_retries: int = 3, retry_delay: int = 5):
        """初始化故障恢复管理器

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.failure_count = 0
        self.last_failure_time = None
        self.is_recovering = False
        self.recovery_lock = threading.Lock()

        # 故障类型映射
        self.failure_handlers = {
            "data_collection_failure": self._handle_data_collection_failure,
            "model_training_failure": self._handle_model_training_failure,
            "prediction_failure": self._handle_prediction_failure,
            "system_crash": self._handle_system_crash,
            "backup_failure": self._handle_backup_failure,
        }

        logger.info("故障恢复管理器初始化完成")

    def handle_failure(self, failure_type: str, error: Exception, context: Optional[Dict[str, Any]] = None):
        """处理故障

        Args:
            failure_type: 故障类型
            error: 错误对象
            context: 上下文信息
        """
        with self.recovery_lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            logger.error(f"[故障] 类型: {failure_type}, 错误: {str(error)}")
            logger.error(f"[故障] 上下文: {context}")
            logger.error(f"[故障] 堆栈: {traceback.format_exc()}")

            # 执行相应的故障处理
            if failure_type in self.failure_handlers:
                try:
                    self.failure_handlers[failure_type](error, context)
                except Exception as e:
                    logger.error(f"处理故障时发生错误: {str(e)}")
            else:
                self._handle_generic_failure(error, context)

    def _handle_data_collection_failure(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """处理数据采集失败"""
        logger.warning("[恢复] 处理数据采集失败")

        # 尝试重新执行数据采集
        if context and "collector" in context:
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"[恢复] 尝试重新采集数据 (尝试 {attempt + 1}/{self.max_retries})")
                    context["collector"].update_data()
                    logger.info("[恢复] 数据采集恢复成功")
                    return
                except Exception as e:
                    logger.error(f"[恢复] 重新采集数据失败: {str(e)}")
                    time.sleep(self.retry_delay)

        logger.error("[恢复] 数据采集多次尝试失败，需要人工干预")

    def _handle_model_training_failure(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """处理模型训练失败"""
        logger.warning("[恢复] 处理模型训练失败")

        # 尝试使用备份恢复模型
        latest_backup = get_latest_backup()
        if latest_backup:
            try:
                logger.info(f"[恢复] 尝试从备份恢复模型: {latest_backup.get('backup_id')}")
                restore_result = restore_backup(latest_backup.get("backup_id"))
                if restore_result.get("status") == "success":
                    logger.info("[恢复] 模型恢复成功")
                    return
                else:
                    logger.error(f"[恢复] 模型恢复失败: {restore_result.get('error')}")
            except Exception as e:
                logger.error(f"[恢复] 恢复模型时发生错误: {str(e)}")

        logger.error("[恢复] 模型训练失败且无法恢复，需要人工干预")

    def _handle_prediction_failure(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """处理预测失败"""
        logger.warning("[恢复] 处理预测失败")

        # 尝试使用备份模型
        latest_backup = get_latest_backup()
        if latest_backup:
            try:
                logger.info(f"[恢复] 尝试从备份恢复模型用于预测: {latest_backup.get('backup_id')}")
                restore_result = restore_backup(latest_backup.get("backup_id"))
                if restore_result.get("status") == "success":
                    logger.info("[恢复] 模型恢复成功，预测功能已恢复")
                    return
                else:
                    logger.error(f"[恢复] 模型恢复失败: {restore_result.get('error')}")
            except Exception as e:
                logger.error(f"[恢复] 恢复模型时发生错误: {str(e)}")

        logger.error("[恢复] 预测失败且无法恢复，需要人工干预")

    def _handle_system_crash(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """处理系统崩溃"""
        logger.critical("[恢复] 处理系统崩溃")

        # 记录崩溃信息
        crash_info = {
            "timestamp": datetime.now().isoformat(),
            "error": str(error),
            "stack": traceback.format_exc(),
            "context": context,
        }

        # 保存崩溃信息
        try:
            with open("crash.log", "a", encoding="utf-8") as f:
                f.write(f"\n=== 系统崩溃 {crash_info['timestamp']} ===\n")
                f.write(f"错误: {crash_info['error']}\n")
                f.write(f"堆栈: {crash_info['stack']}\n")
                f.write(f"上下文: {crash_info['context']}\n")
                f.write("=============================\n")
        except Exception as e:
            logger.error(f"保存崩溃信息失败: {str(e)}")

        # 尝试恢复系统
        logger.info("[恢复] 尝试恢复系统...")

        # 1. 尝试从备份恢复
        latest_backup = get_latest_backup()
        if latest_backup:
            try:
                logger.info(f"[恢复] 尝试从最新备份恢复系统: {latest_backup.get('backup_id')}")
                restore_result = restore_backup(latest_backup.get("backup_id"))
                if restore_result.get("status") == "success":
                    logger.info("[恢复] 系统恢复成功")
                else:
                    logger.error(f"[恢复] 系统恢复失败: {restore_result.get('error')}")
            except Exception as e:
                logger.error(f"[恢复] 恢复系统时发生错误: {str(e)}")

        # 2. 重启系统
        logger.info("[恢复] 准备重启系统...")
        # 注意：这里只是记录，实际重启需要根据运行环境调整

    def _handle_backup_failure(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """处理备份失败"""
        logger.warning("[恢复] 处理备份失败")

        # 尝试重新执行备份
        for attempt in range(self.max_retries):
            try:
                logger.info(f"[恢复] 尝试重新执行备份 (尝试 {attempt + 1}/{self.max_retries})")
                from src.core.backup.backup_manager import create_backup

                backup_result = create_backup()
                if backup_result.get("status") == "success":
                    logger.info("[恢复] 备份恢复成功")
                    return
                else:
                    logger.error(f"[恢复] 重新备份失败: {backup_result.get('error')}")
            except Exception as e:
                logger.error(f"[恢复] 重新执行备份失败: {str(e)}")
            time.sleep(self.retry_delay)

        logger.error("[恢复] 备份多次尝试失败，需要人工干预")

    def _handle_generic_failure(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """处理通用故障"""
        logger.warning("[恢复] 处理通用故障")

        # 尝试简单的重试机制
        if context and "retry_func" in context:
            retry_func = context["retry_func"]
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"[恢复] 尝试重新执行操作 (尝试 {attempt + 1}/{self.max_retries})")
                    retry_func()
                    logger.info("[恢复] 操作恢复成功")
                    return
                except Exception as e:
                    logger.error(f"[恢复] 重新执行操作失败: {str(e)}")
                    time.sleep(self.retry_delay)

        logger.error("[恢复] 操作多次尝试失败，需要人工干预")

    def auto_retry(self, func: Callable, *args, **kwargs) -> Any:
        """自动重试装饰器

        Args:
            func: 要执行的函数

        Returns:
            函数执行结果
        """
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"[自动重试] 尝试 {attempt + 1}/{self.max_retries} 失败: {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"[自动重试] 等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("[自动重试] 达到最大重试次数，操作失败")
                    raise

    def get_failure_stats(self) -> Dict[str, Any]:
        """获取故障统计信息

        Returns:
            故障统计信息
        """
        return {
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "is_recovering": self.is_recovering,
        }

    def reset_failure_stats(self):
        """重置故障统计信息"""
        self.failure_count = 0
        self.last_failure_time = None
        logger.info("故障统计信息已重置")


# 全局故障恢复管理器实例
_global_recovery_manager = None


def get_recovery_manager() -> FailureRecovery:
    """获取全局故障恢复管理器实例"""
    global _global_recovery_manager
    if _global_recovery_manager is None:
        _global_recovery_manager = FailureRecovery()
    return _global_recovery_manager


def handle_failure(failure_type: str, error: Exception, context: Optional[Dict[str, Any]] = None):
    """处理故障"""
    manager = get_recovery_manager()
    manager.handle_failure(failure_type, error, context)


def auto_retry(func: Callable, *args, **kwargs) -> Any:
    """自动重试装饰器"""
    manager = get_recovery_manager()
    return manager.auto_retry(func, *args, **kwargs)


def get_failure_stats() -> Dict[str, Any]:
    """获取故障统计信息"""
    manager = get_recovery_manager()
    return manager.get_failure_stats()


def reset_failure_stats():
    """重置故障统计信息"""
    manager = get_recovery_manager()
    manager.reset_failure_stats()
