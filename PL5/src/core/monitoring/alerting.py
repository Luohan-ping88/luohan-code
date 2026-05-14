#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控和告警模块
实现系统异常检测和通知功能
"""

import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from src.core.utils.logger import setup_logging
from src.core.email.sender import EmailSender

logger = setup_logging(__name__)


@dataclass
class Alert:
    """告警信息"""

    level: str  # critical, error, warning, info
    message: str
    source: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None
    alert_id: Optional[str] = None
    resolved: bool = False

    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = (
                f"alert_{int(time.time())}_{hash(self.message) % 10000}"
            )
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class AlertManager:
    """告警管理器"""

    def __init__(self, alert_dir: Optional[Path] = None):
        """初始化告警管理器

        Args:
            alert_dir: 告警存储目录
        """
        self.alert_dir = alert_dir or Path("alerts")
        self.alert_dir.mkdir(parents=True, exist_ok=True)

        self.email_sender = EmailSender()
        self.alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
        self.resolved_alerts: List[Alert] = []

        # 告警阈值配置
        self.thresholds = {
            "cpu": 90,  # CPU使用率阈值
            "memory": 85,  # 内存使用率阈值
            "disk": 90,  # 磁盘使用率阈值
            "response_time": 5,  # 响应时间阈值（秒）
            "error_rate": 0.1,  # 错误率阈值
            "network_sent": 100,  # 网络发送速率阈值（MB/s）
            "network_recv": 100,  # 网络接收速率阈值（MB/s）
            "process_count": 500,  # 进程数量阈值
            "open_files": 1000,  # 打开文件数量阈值
            "model_performance": 0.1,  # 模型性能下降阈值
        }

        # 告警规则
        self.rules = {
            "system_health": self._check_system_health,
            "performance_anomalies": self._check_performance_anomalies,
            "error_detection": self._check_errors,
            "backup_status": self._check_backup_status,
            "network_monitoring": self._check_network,
            "process_monitoring": self._check_processes,
            "model_performance": self._check_model_performance,
        }

        # 告警聚合规则
        self.alert_aggregation = {
            "window": 60,  # 聚合窗口（秒）
            "threshold": 5,  # 同一类型告警阈值
            "group_by": ["level", "source"],  # 聚合维度
        }

        # 告警抑制规则
        self.alert_suppression = {
            "enabled": True,
            "duration": 300,
            "rules": [],
        }  # 抑制持续时间（秒）  # 抑制规则

        # 告警优先级映射
        self.priority_map = {
            "critical": 1,
            "error": 2,
            "warning": 3,
            "info": 4,
        }

        logger.info("告警管理器初始化完成")

    def check_alerts(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查告警

        Args:
            metrics: 系统指标

        Returns:
            新产生的告警列表
        """
        new_alerts = []

        for rule_name, rule_func in self.rules.items():
            try:
                alerts = rule_func(metrics)
                new_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"执行告警规则 {rule_name} 失败: {str(e)}")

        # 聚合告警
        aggregated_alerts = self._aggregate_alerts(new_alerts)

        # 处理新告警
        for alert in aggregated_alerts:
            self._process_alert(alert)

        return aggregated_alerts

    def _check_system_health(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查系统健康状态"""
        alerts = []

        # 检查CPU使用率
        if "system" in metrics and "cpu_percent" in metrics["system"]:
            cpu_percent = metrics["system"]["cpu_percent"]
            if cpu_percent > self.thresholds["cpu"]:
                alerts.append(
                    Alert(
                        level="critical",
                        message=f"CPU使用率过高: {cpu_percent}%",
                        source="system_health",
                        details={
                            "cpu_percent": cpu_percent,
                            "threshold": self.thresholds["cpu"],
                        },
                    )
                )

        # 检查内存使用率
        if "system" in metrics and "memory_percent" in metrics["system"]:
            memory_percent = metrics["system"]["memory_percent"]
            if memory_percent > self.thresholds["memory"]:
                alerts.append(
                    Alert(
                        level="error",
                        message=f"内存使用率过高: {memory_percent}%",
                        source="system_health",
                        details={
                            "memory_percent": memory_percent,
                            "threshold": self.thresholds["memory"],
                        },
                    )
                )

        # 检查磁盘使用率
        if "system" in metrics and "disk_percent" in metrics["system"]:
            disk_percent = metrics["system"]["disk_percent"]
            if disk_percent > self.thresholds["disk"]:
                alerts.append(
                    Alert(
                        level="error",
                        message=f"磁盘使用率过高: {disk_percent}%",
                        source="system_health",
                        details={
                            "disk_percent": disk_percent,
                            "threshold": self.thresholds["disk"],
                        },
                    )
                )

        return alerts

    def _check_performance_anomalies(
        self, metrics: Dict[str, Any]
    ) -> List[Alert]:
        """检查性能异常"""
        alerts = []

        # 检查响应时间
        if "response_time" in metrics:
            response_time = metrics["response_time"]
            if response_time > self.thresholds["response_time"]:
                alerts.append(
                    Alert(
                        level="warning",
                        message=f"响应时间过长: {response_time}秒",
                        source="performance",
                        details={
                            "response_time": response_time,
                            "threshold": self.thresholds["response_time"],
                        },
                    )
                )

        # 检查错误率
        if "error_rate" in metrics:
            error_rate = metrics["error_rate"]
            if error_rate > self.thresholds["error_rate"]:
                alerts.append(
                    Alert(
                        level="error",
                        message=f"错误率过高: {error_rate*100}%",
                        source="performance",
                        details={
                            "error_rate": error_rate,
                            "threshold": self.thresholds["error_rate"],
                        },
                    )
                )

        return alerts

    def _check_errors(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查错误情况"""
        alerts = []

        # 检查系统错误
        if "errors" in metrics:
            errors = metrics["errors"]
            if errors:
                for error in errors:
                    alerts.append(
                        Alert(
                            level="error",
                            message=f"系统错误: {error.get('message', '未知错误')}",
                            source="error_detection",
                            details=error,
                        )
                    )

        return alerts

    def _check_backup_status(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查备份状态"""
        alerts = []

        # 检查备份状态
        if "backup_status" in metrics:
            backup_status = metrics["backup_status"]
            if not backup_status.get("success"):
                alerts.append(
                    Alert(
                        level="error",
                        message=f"备份失败: {backup_status.get('error', '未知错误')}",
                        source="backup",
                        details=backup_status,
                    )
                )

        # 检查备份时间
        if "last_backup" in metrics:
            last_backup = metrics["last_backup"]
            if last_backup:
                backup_time = datetime.fromisoformat(last_backup)
                time_since_backup = (
                    datetime.now() - backup_time
                ).total_seconds() / 3600  # 小时
                if time_since_backup > 24:  # 超过24小时没有备份
                    alerts.append(
                        Alert(
                            level="warning",
                            message=f"备份时间过长: {time_since_backup:.1f}小时",
                            source="backup",
                            details={"time_since_backup": time_since_backup},
                        )
                    )

        return alerts

    def _check_network(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查网络状态"""
        alerts = []

        # 检查网络发送速率
        if "system" in metrics and "network_sent_mb" in metrics["system"]:
            network_sent = metrics["system"]["network_sent_mb"]
            if network_sent > self.thresholds["network_sent"]:
                alerts.append(
                    Alert(
                        level="warning",
                        message=f"网络发送速率过高: {network_sent} MB/s",
                        source="network",
                        details={
                            "network_sent": network_sent,
                            "threshold": self.thresholds["network_sent"],
                        },
                    )
                )

        # 检查网络接收速率
        if "system" in metrics and "network_recv_mb" in metrics["system"]:
            network_recv = metrics["system"]["network_recv_mb"]
            if network_recv > self.thresholds["network_recv"]:
                alerts.append(
                    Alert(
                        level="warning",
                        message=f"网络接收速率过高: {network_recv} MB/s",
                        source="network",
                        details={
                            "network_recv": network_recv,
                            "threshold": self.thresholds["network_recv"],
                        },
                    )
                )

        return alerts

    def _check_processes(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查进程状态"""
        alerts = []

        # 检查进程数量
        if "process" in metrics and "threads" in metrics["process"]:
            thread_count = metrics["process"]["threads"]
            if thread_count > self.thresholds["process_count"]:
                alerts.append(
                    Alert(
                        level="warning",
                        message=f"进程线程数量过高: {thread_count}",
                        source="process",
                        details={
                            "thread_count": thread_count,
                            "threshold": self.thresholds["process_count"],
                        },
                    )
                )

        # 检查打开文件数量
        if "process" in metrics and "open_files" in metrics["process"]:
            open_files = metrics["process"]["open_files"]
            if open_files > self.thresholds["open_files"]:
                alerts.append(
                    Alert(
                        level="warning",
                        message=f"打开文件数量过高: {open_files}",
                        source="process",
                        details={
                            "open_files": open_files,
                            "threshold": self.thresholds["open_files"],
                        },
                    )
                )

        return alerts

    def _check_model_performance(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查模型性能"""
        alerts = []

        # 检查模型性能
        if "model_performance" in metrics:
            model_performance = metrics["model_performance"]
            if model_performance < self.thresholds["model_performance"]:
                alerts.append(
                    Alert(
                        level="warning",
                        message=f"模型性能下降: {model_performance}",
                        source="model",
                        details={
                            "model_performance": model_performance,
                            "threshold": self.thresholds["model_performance"],
                        },
                    )
                )

        return alerts

    def _aggregate_alerts(self, alerts: List[Alert]) -> List[Alert]:
        """聚合告警，避免告警风暴"""
        if not alerts:
            return alerts

        # 简单的告警聚合逻辑
        aggregated_alerts = []
        alert_groups = {}

        for alert in alerts:
            # 按级别和来源分组
            key = (alert.level, alert.source)
            if key not in alert_groups:
                alert_groups[key] = []
            alert_groups[key].append(alert)

        # 对每个组进行聚合
        for key, group in alert_groups.items():
            if len(group) > 1:
                # 聚合多个相同类型的告警
                aggregated_alert = Alert(
                    level=key[0],
                    message=f"[{len(group)}个] {group[0].message}",
                    source=key[1],
                    details={
                        "count": len(group),
                        "original_alerts": [alert.alert_id for alert in group],
                    },
                )
                aggregated_alerts.append(aggregated_alert)
            else:
                aggregated_alerts.extend(group)

        return aggregated_alerts

    def _should_suppress_alert(self, alert: Alert) -> bool:
        """判断是否应该抑制告警"""
        if not self.alert_suppression["enabled"]:
            return False

        # 检查是否有相同类型的告警在抑制期内
        current_time = time.time()
        for existing_alert in self.alerts:
            if (
                existing_alert.level == alert.level
                and existing_alert.source == alert.source
                and not existing_alert.resolved
            ):
                alert_time = datetime.fromisoformat(
                    existing_alert.timestamp
                ).timestamp()
                if (
                    current_time - alert_time
                    < self.alert_suppression["duration"]
                ):
                    return True

        return False

    def _process_alert(self, alert: Alert):
        """处理告警"""
        # 检查是否应该抑制告警
        if self._should_suppress_alert(alert):
            logger.info(f"告警已抑制: {alert.alert_id}")
            return

        # 添加到告警列表
        self.alerts.append(alert)
        self.alert_history.append(alert)

        # 保存告警
        self._save_alert(alert)

        # 发送通知
        self._notify_alert(alert)

        # 限制告警数量
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        if len(self.resolved_alerts) > 1000:
            self.resolved_alerts = self.resolved_alerts[-1000:]

    def _save_alert(self, alert: Alert):
        """保存告警到文件"""
        try:
            alert_file = self.alert_dir / f"alert_{alert.alert_id}.json"
            with open(alert_file, "w", encoding="utf-8") as f:
                alert_data = {
                    "alert_id": alert.alert_id,
                    "level": alert.level,
                    "message": alert.message,
                    "source": alert.source,
                    "timestamp": alert.timestamp,
                    "details": alert.details,
                    "resolved": alert.resolved,
                }
                json.dump(alert_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存告警失败: {str(e)}")

    def _notify_alert(self, alert: Alert):
        """发送告警通知"""
        try:
            # 日志通知
            if alert.level == "critical":
                logger.critical(
                    f"[告警] {alert.message} - 来源: {alert.source}"
                )
            elif alert.level == "error":
                logger.error(f"[告警] {alert.message} - 来源: {alert.source}")
            elif alert.level == "warning":
                logger.warning(
                    f"[告警] {alert.message} - 来源: {alert.source}"
                )
            else:
                logger.info(f"[告警] {alert.message} - 来源: {alert.source}")

            # 邮件通知（仅针对严重告警）
            if alert.level in ["critical", "error"]:
                report = {
                    "alert": {
                        "level": alert.level,
                        "message": alert.message,
                        "source": alert.source,
                        "timestamp": alert.timestamp,
                        "details": alert.details,
                    }
                }
                self.email_sender.send_email(report)
                logger.info(f"告警邮件已发送: {alert.alert_id}")

        except Exception as e:
            logger.error(f"发送告警通知失败: {str(e)}")

    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警

        Args:
            alert_id: 告警ID

        Returns:
            是否解决成功
        """
        try:
            for i, alert in enumerate(self.alerts):
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    self._save_alert(alert)
                    # 从活跃告警列表移到已解决告警列表
                    resolved_alert = self.alerts.pop(i)
                    self.resolved_alerts.append(resolved_alert)
                    logger.info(f"告警已解决: {alert_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"解决告警失败: {str(e)}")
            return False

    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return [alert for alert in self.alerts if not alert.resolved]

    def get_alerts_by_level(self, level: str) -> List[Alert]:
        """按级别获取告警"""
        return [alert for alert in self.alerts if alert.level == level]

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        return self.alert_history[-limit:]

    def get_alert_statistics(self) -> Dict[str, Any]:
        """获取告警统计信息"""
        stats = {
            "total_alerts": len(self.alert_history),
            "active_alerts": len(self.get_active_alerts()),
            "alerts_by_level": {
                "critical": 0,
                "error": 0,
                "warning": 0,
                "info": 0,
            },
            "alerts_by_source": {},
        }

        for alert in self.alert_history:
            stats["alerts_by_level"][alert.level] += 1
            if alert.source not in stats["alerts_by_source"]:
                stats["alerts_by_source"][alert.source] = 0
            stats["alerts_by_source"][alert.source] += 1

        return stats

    def clear_alerts(self):
        """清除所有告警"""
        try:
            self.alerts = []
            # 保留历史记录
            logger.info("所有活跃告警已清除")
        except Exception as e:
            logger.error(f"清除告警失败: {str(e)}")


# 全局告警管理器实例
_global_alert_manager = None


def get_alert_manager() -> AlertManager:
    """获取全局告警管理器实例"""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = AlertManager()
    return _global_alert_manager


def check_alerts(metrics: Dict[str, Any]) -> List[Alert]:
    """检查告警"""
    manager = get_alert_manager()
    return manager.check_alerts(metrics)


def get_active_alerts() -> List[Alert]:
    """获取活跃告警"""
    manager = get_alert_manager()
    return manager.get_active_alerts()


def resolve_alert(alert_id: str) -> bool:
    """解决告警"""
    manager = get_alert_manager()
    return manager.resolve_alert(alert_id)


def get_alert_statistics() -> Dict[str, Any]:
    """获取告警统计信息"""
    manager = get_alert_manager()
    return manager.get_alert_statistics()
