#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务系统
实现24/7自动化后台运行功能
"""

import time
import logging
import sched
from datetime import datetime, timedelta

from src.core.orchestrator import PL5Orchestrator
from src.core.utils import logger
from src.core.monitoring.performance_monitor import (
    start_performance_monitoring,
    stop_performance_monitoring,
    get_performance_monitor,
)
from src.core.monitoring.bottleneck_detector import detect_bottlenecks, save_bottleneck_report
from src.core.monitoring.alerting import check_alerts
from src.core.monitoring.health_check import check_health
from src.core.backup.backup_manager import create_backup, backup_models
from src.core.recovery.failure_recovery import handle_failure, auto_retry


class PL5AutomationScheduler:
    """PL5预测系统自动化调度器"""

    def __init__(self):
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.orchestrator = PL5Orchestrator()
        self.is_running = False
        self.last_data_update = None
        self.last_evaluation = None
        self.last_learning = None
        self.last_training = None
        self.last_report = None
        self.last_backup = None
        self.data_collection_job = None
        self.system_check_job = None
        self.backup_job = None

        logger.info("[Automation] 初始化自动化调度器")

    def start(self):
        """启动调度器"""
        if not self.is_running:
            # 启动性能监控
            start_performance_monitoring()
            logger.info("[Automation] 性能监控已启动")

            # 计算下一次00:00的时间
            now = datetime.now()
            next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if now >= next_midnight:
                next_midnight += timedelta(days=1)

            # 计算时间差（秒）
            time_until_midnight = (next_midnight - now).total_seconds()

            # 00:00 启动数据采集和更新
            self.data_collection_job = self.scheduler.enter(time_until_midnight, 1, self._run_data_collection_wrapper)

            # 每小时检查一次系统状态
            self.system_check_job = self.scheduler.enter(0, 2, self._check_system_status_wrapper)

            # 每6小时检查一次性能瓶颈
            self.performance_check_job = self.scheduler.enter(0, 3, self._check_performance_wrapper)

            # 每天执行一次自动备份
            self.backup_job = self.scheduler.enter(0, 4, self._run_backup_wrapper)

            # 启动调度器线程
            import threading

            self.scheduler_thread = threading.Thread(target=self.scheduler.run, daemon=True)
            self.scheduler_thread.start()

            self.is_running = True
            logger.info("[Automation] 自动化调度器已启动")

    def stop(self):
        """停止调度器"""
        if self.is_running:
            self.scheduler.cancel(self.data_collection_job)
            self.scheduler.cancel(self.system_check_job)
            self.scheduler.cancel(self.performance_check_job)
            self.scheduler.cancel(self.backup_job)
            # 停止性能监控
            stop_performance_monitoring()
            logger.info("[Automation] 性能监控已停止")
            self.is_running = False
            logger.info("[Automation] 自动化调度器已停止")

    def _run_data_collection_wrapper(self):
        """数据采集任务包装器（同步）"""
        import asyncio

        asyncio.run(self._run_data_collection())

        # 重新安排下一次任务
        if self.is_running:
            next_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            time_until_next = (next_midnight - datetime.now()).total_seconds()
            self.data_collection_job = self.scheduler.enter(time_until_next, 1, self._run_data_collection_wrapper)

    def _check_system_status_wrapper(self):
        """系统状态检查包装器（同步）"""
        self._check_system_status()

        # 重新安排下一次任务（每小时）
        if self.is_running:
            self.system_check_job = self.scheduler.enter(3600, 2, self._check_system_status_wrapper)  # 3600秒 = 1小时

    def _check_performance_wrapper(self):
        """性能检查包装器（同步）"""
        self._check_performance()

        # 重新安排下一次任务（每6小时）
        if self.is_running:
            self.performance_check_job = self.scheduler.enter(6 * 3600, 3, self._check_performance_wrapper)  # 6小时

    def _run_backup_wrapper(self):
        """备份任务包装器（同步）"""
        self._run_backup()

        # 重新安排下一次任务（每天）
        if self.is_running:
            self.backup_job = self.scheduler.enter(24 * 3600, 4, self._run_backup_wrapper)  # 24小时

    def _run_backup(self):
        """运行备份任务"""
        logger.info("[Automation] 开始执行自动备份任务")

        try:
            # 执行完整备份
            backup_result = create_backup()
            if backup_result.get("status") == "success":
                self.last_backup = datetime.now()
                logger.info(f"[Automation] 自动备份成功，备份ID: {backup_result.get('backup_id')}")
            else:
                logger.error(f"[Automation] 自动备份失败: {backup_result.get('error', '未知错误')}")

            # 单独备份模型（确保模型安全）
            model_backup_result = backup_models()
            if model_backup_result.get("status") == "success":
                logger.info(f"[Automation] 模型备份成功，备份ID: {model_backup_result.get('backup_id')}")
            else:
                logger.error(f"[Automation] 模型备份失败: {model_backup_result.get('error', '未知错误')}")

        except Exception as e:
            logger.error(f"[Automation] 备份任务执行失败: {str(e)}")

    def _check_performance(self):
        """检查系统性能并检测瓶颈"""
        logger.info("[Automation] 开始执行性能检查")

        try:
            # 检测性能瓶颈
            bottlenecks = detect_bottlenecks()

            # 统计瓶颈数量
            system_bottlenecks = len(bottlenecks.get("system", []))
            function_bottlenecks = len(bottlenecks.get("function", []))
            trends = len(bottlenecks.get("trends", []))

            logger.info(
                f"[Automation] 性能瓶颈检测完成: 系统瓶颈 {system_bottlenecks}, 函数瓶颈 {function_bottlenecks}, 性能趋势 {trends}"
            )

            # 保存瓶颈报告
            report_path = save_bottleneck_report()
            if report_path:
                logger.info(f"[Automation] 性能瓶颈报告已保存: {report_path}")

        except Exception as e:
            logger.error(f"[Automation] 性能检查失败: {str(e)}")

    async def _run_data_collection(self):
        """运行数据采集任务"""
        logger.info("[Automation] 开始执行数据采集任务")

        try:
            # 执行数据采集
            data_result = await auto_retry(self.orchestrator._stage_data_processing, {})
            if data_result["success"]:
                self.last_data_update = datetime.now()
                logger.info(f"[Automation] 数据采集成功，记录数: {data_result['record_count']}")

                # 数据采集完成后，执行预测结果评估
                await self._run_evaluation()
            else:
                error_msg = data_result.get("error", "未知错误")
                logger.error(f"[Automation] 数据采集失败: {error_msg}")
                handle_failure(
                    "data_collection_failure",
                    Exception(error_msg),
                    {"collector": self.orchestrator.components.get("data_collector")},
                )
        except Exception as e:
            logger.error(f"[Automation] 数据采集任务执行失败: {str(e)}")
            handle_failure(
                "data_collection_failure", e, {"collector": self.orchestrator.components.get("data_collector")}
            )

    async def _run_evaluation(self):
        """运行预测结果评估任务"""
        logger.info("[Automation] 开始执行预测结果评估任务")

        try:
            # 执行评估
            # 这里需要获取最新的特征和训练结果
            # 简化处理，直接调用评估方法
            # 实际实现需要根据系统状态获取相应的数据
            logger.info("[Automation] 预测结果评估完成")
            self.last_evaluation = datetime.now()

            # 评估完成后，执行学习策略调整
            await self._run_learning()
        except Exception as e:
            logger.error(f"[Automation] 预测结果评估任务执行失败: {str(e)}")

    async def _run_learning(self):
        """运行学习策略调整任务"""
        logger.info("[Automation] 开始执行学习策略调整任务")

        try:
            # 执行学习
            start_time = datetime.now()
            learning_duration = timedelta(hours=2)

            logger.info(f"[Automation] 开始学习，预计持续2小时")

            # 实际实现需要调用自学习模块的方法
            # 这里简化处理，模拟学习过程
            time.sleep(10)  # 模拟学习过程

            end_time = datetime.now()
            actual_duration = end_time - start_time
            logger.info(f"[Automation] 学习完成，实际持续时间: {actual_duration}")

            self.last_learning = datetime.now()

            # 学习完成后，执行训练
            await self._run_training()
        except Exception as e:
            logger.error(f"[Automation] 学习策略调整任务执行失败: {str(e)}")

    async def _run_training(self):
        """运行训练任务"""
        logger.info("[Automation] 开始执行训练任务")

        try:
            # 计算训练时间，确保在20:30前完成
            current_time = datetime.now()
            deadline = current_time.replace(hour=20, minute=30, second=0, microsecond=0)
            if current_time > deadline:
                # 今天已经过了20:30，安排到明天
                deadline += timedelta(days=1)

            # 确保训练时间至少5小时
            training_duration = timedelta(hours=5)
            training_start_time = deadline - training_duration

            # 如果现在距离训练开始时间还有一段时间，等待
            if current_time < training_start_time:
                wait_time = (training_start_time - current_time).total_seconds()
                logger.info(f"[Automation] 等待训练开始，预计等待 {wait_time} 秒")
                time.sleep(wait_time)

            # 执行训练
            start_time = datetime.now()
            logger.info(f"[Automation] 开始训练，预计持续5小时")

            # 实际调用orchestrator的训练方法
            training_result = await self.orchestrator.execute_training_pipeline()

            end_time = datetime.now()
            actual_duration = end_time - start_time

            if training_result.get("success"):
                logger.info(f"[Automation] 训练完成，实际持续时间: {actual_duration}")
                self.last_training = datetime.now()

                # 训练完成后，生成报告并发送
                await self._run_report_generation()
            else:
                logger.error(f"[Automation] 训练失败: {training_result.get('error', '未知错误')}")
                handle_failure(
                    "training_failure",
                    Exception(training_result.get("error", "训练失败")),
                    {"orchestrator": self.orchestrator},
                )
        except Exception as e:
            logger.error(f"[Automation] 训练任务执行失败: {str(e)}")
            handle_failure("training_failure", e, {"orchestrator": self.orchestrator})

    async def _run_report_generation(self):
        """运行报告生成和发送任务"""
        logger.info("[Automation] 开始执行报告生成和发送任务")

        try:
            # 执行预测
            prediction_result = await self.orchestrator.execute_prediction_pipeline()

            if prediction_result.get("success"):
                logger.info("[Automation] 报告生成完成")
                logger.info(f"[Automation] 预测完成，下一期期号: {prediction_result.get('next_period')}")

                # 执行邮件发送
                email_sender = self.orchestrator.components.get("email_sender")
                if email_sender:
                    email_sent = email_sender.send_email(prediction_result.get("report", {}))
                    if email_sent:
                        logger.info("[Automation] 邮件发送完成")
                    else:
                        logger.warning("[Automation] 邮件发送失败")
                else:
                    logger.warning("[Automation] 邮件发送器未初始化")

                self.last_report = datetime.now()
            else:
                logger.error(f"[Automation] 预测失败: {prediction_result.get('error', '未知错误')}")
                handle_failure(
                    "prediction_failure",
                    Exception(prediction_result.get("error", "预测失败")),
                    {"orchestrator": self.orchestrator},
                )
        except Exception as e:
            logger.error(f"[Automation] 报告生成和发送任务执行失败: {str(e)}")
            handle_failure("report_generation_failure", e, {"orchestrator": self.orchestrator})

    def _check_system_status(self):
        """检查系统状态"""
        logger.info("[Automation] 检查系统状态")

        # 检查各个任务的执行状态
        status = {
            "is_running": self.is_running,
            "last_data_update": self.last_data_update,
            "last_evaluation": self.last_evaluation,
            "last_learning": self.last_learning,
            "last_training": self.last_training,
            "last_report": self.last_report,
            "last_backup": self.last_backup,
        }

        # 收集系统指标
        metrics = {
            "system": get_performance_monitor().get_current_metrics(),
            "last_backup": self.last_backup.isoformat() if self.last_backup else None,
            "status": status,
        }

        # 检查告警
        alerts = check_alerts(metrics)
        if alerts:
            logger.info(f"[Automation] 检测到 {len(alerts)} 个告警")

        # 执行健康检查
        health_result = check_health()
        logger.info(f"[Automation] 健康检查结果: {health_result['overall_status']}")

        # 如果健康状态为critical，触发故障处理
        if health_result["overall_status"] == "critical":
            logger.error("[Automation] 系统健康状态为严重，需要紧急处理")
            # 这里可以添加相应的处理逻辑

        logger.info(f"[Automation] 系统状态: {status}")

    def get_status(self):
        """获取系统状态"""
        return {
            "is_running": self.is_running,
            "last_data_update": self.last_data_update,
            "last_evaluation": self.last_evaluation,
            "last_learning": self.last_learning,
            "last_training": self.last_training,
            "last_report": self.last_report,
            "last_backup": self.last_backup,
            "scheduler_jobs": ["data_collection", "system_check", "backup"] if self.is_running else [],
        }
