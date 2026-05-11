#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统健康监控模块
监控CPU/内存/任务执行时间/特征漂移等指标，提供预警机制
"""

import json
import time
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from src.core.config import LOGS_DIR
from src.core.utils.logger import get_logger

logger = get_logger(__name__)


class AlertLevel(Enum):
    """预警级别"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ALERT = "alert"


@dataclass
class AlertThreshold:
    """预警阈值配置"""

    cpu_warning: float = 70.0
    cpu_critical: float = 85.0
    memory_warning: float = 87.0  # V10.3+: 机器7.9GB，ML常态82-84%，调高阈值减少噪声
    memory_critical: float = 95.0  # V10.3+: 真正危险时才触发 CRITICAL
    task_time_warning: float = 3600.0  # 1小时
    task_time_critical: float = 7200.0  # 2小时
    disk_usage_warning: float = 80.0
    disk_usage_critical: float = 90.0


@dataclass
class HealthMetrics:
    """健康指标"""

    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_usage_percent: float
    disk_used_gb: float
    disk_total_gb: float
    task_count: int
    task_success_rate: float
    avg_task_time_sec: float
    feature_drift_score: Optional[float] = None


class SystemHealthMonitor:
    """系统健康监控器"""

    def __init__(self, thresholds: Optional[AlertThreshold] = None):
        self.thresholds = thresholds or AlertThreshold()
        self.metrics_file = LOGS_DIR / "health_metrics.json"
        self.alerts_file = LOGS_DIR / "alerts.json"

        self._init_files()

        # 任务执行记录
        self.task_executions: List[Dict] = []
        self._load_task_executions()

    def _init_files(self):
        """初始化文件"""
        if not self.metrics_file.exists():
            self._save_metrics([])
        if not self.alerts_file.exists():
            self._save_alerts([])

    def _load_metrics(self) -> List[Dict]:
        """加载历史指标"""
        try:
            with open(self.metrics_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def _save_metrics(self, metrics: List[Dict]):
        """保存指标"""
        # 只保留最近1000条记录
        metrics = metrics[-1000:]
        with open(self.metrics_file, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

    def _load_alerts(self) -> List[Dict]:
        """加载历史预警"""
        try:
            with open(self.alerts_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def _save_alerts(self, alerts: List[Dict]):
        """保存预警"""
        # 只保留最近500条记录
        alerts = alerts[-500:]
        with open(self.alerts_file, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)

    def _load_task_executions(self):
        """加载任务执行记录"""
        task_file = LOGS_DIR / "task_executions.json"
        if task_file.exists():
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    self.task_executions = json.load(f)
            except:
                self.task_executions = []

    def _save_task_executions(self):
        """保存任务执行记录"""
        task_file = LOGS_DIR / "task_executions.json"
        # 只保留最近100条记录
        self.task_executions = self.task_executions[-100:]
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(self.task_executions, f, indent=2, ensure_ascii=False)

    def collect_system_metrics(self) -> HealthMetrics:
        """收集系统指标"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)

        # 内存
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_gb = memory.used / (1024**3)
        memory_total_gb = memory.total / (1024**3)

        # 磁盘
        disk = psutil.disk_usage(str(Path.cwd()))
        disk_usage_percent = disk.percent
        disk_used_gb = disk.used / (1024**3)
        disk_total_gb = disk.total / (1024**3)

        # 任务统计
        task_count = len(self.task_executions)
        if task_count > 0:
            success_count = sum(1 for t in self.task_executions if t.get("success"))
            task_success_rate = success_count / task_count
            avg_task_time = sum(t.get("duration", 0) for t in self.task_executions) / task_count
        else:
            task_success_rate = 1.0
            avg_task_time = 0.0

        metrics = HealthMetrics(
            timestamp=datetime.now().isoformat(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_gb=round(memory_used_gb, 2),
            memory_total_gb=round(memory_total_gb, 2),
            disk_usage_percent=disk_usage_percent,
            disk_used_gb=round(disk_used_gb, 2),
            disk_total_gb=round(disk_total_gb, 2),
            task_count=task_count,
            task_success_rate=round(task_success_rate, 3),
            avg_task_time_sec=round(avg_task_time, 1),
        )

        # 保存指标
        history = self._load_metrics()
        history.append(asdict(metrics))
        self._save_metrics(history)

        # 检查预警
        self._check_alerts(metrics)

        return metrics

    def record_task_execution(
        self, task_name: str, start_time: datetime, end_time: datetime, success: bool, error_msg: Optional[str] = None
    ):
        """记录任务执行"""
        duration = (end_time - start_time).total_seconds()

        execution = {
            "task_name": task_name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": round(duration, 2),
            "success": success,
            "error_msg": error_msg,
        }

        self.task_executions.append(execution)
        self._save_task_executions()

        # 检查任务时间预警
        if duration > self.thresholds.task_time_warning:
            self._add_alert(
                level=AlertLevel.WARNING if duration < self.thresholds.task_time_critical else AlertLevel.CRITICAL,
                category="task_duration",
                message=f"任务 {task_name} 执行时间过长: {round(duration/60, 1)} 分钟",
                details={"task_name": task_name, "duration_sec": duration},
            )

    def _check_alerts(self, metrics: HealthMetrics):
        """检查预警条件"""
        # CPU预警
        if metrics.cpu_percent > self.thresholds.cpu_critical:
            self._add_alert(
                level=AlertLevel.CRITICAL,
                category="cpu",
                message=f"CPU使用率过高: {metrics.cpu_percent}%",
                details={"cpu_percent": metrics.cpu_percent},
            )
        elif metrics.cpu_percent > self.thresholds.cpu_warning:
            self._add_alert(
                level=AlertLevel.WARNING,
                category="cpu",
                message=f"CPU使用率偏高: {metrics.cpu_percent}%",
                details={"cpu_percent": metrics.cpu_percent},
            )

        # 内存预警
        if metrics.memory_percent > self.thresholds.memory_critical:
            self._add_alert(
                level=AlertLevel.CRITICAL,
                category="memory",
                message=f"内存使用率过高: {metrics.memory_percent}%",
                details={"memory_percent": metrics.memory_percent},
            )
        elif metrics.memory_percent > self.thresholds.memory_warning:
            self._add_alert(
                level=AlertLevel.WARNING,
                category="memory",
                message=f"内存使用率偏高: {metrics.memory_percent}%",
                details={"memory_percent": metrics.memory_percent},
            )

        # 磁盘预警
        if metrics.disk_usage_percent > self.thresholds.disk_usage_critical:
            self._add_alert(
                level=AlertLevel.CRITICAL,
                category="disk",
                message=f"磁盘使用率过高: {metrics.disk_usage_percent}%",
                details={"disk_percent": metrics.disk_usage_percent},
            )
        elif metrics.disk_usage_percent > self.thresholds.disk_usage_warning:
            self._add_alert(
                level=AlertLevel.WARNING,
                category="disk",
                message=f"磁盘使用率偏高: {metrics.disk_usage_percent}%",
                details={"disk_percent": metrics.disk_usage_percent},
            )

    def _add_alert(self, level: AlertLevel, category: str, message: str, details: Optional[Dict] = None):
        """添加预警"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "category": category,
            "message": message,
            "details": details or {},
        }

        # 检查是否10分钟内已有同类预警，避免重复
        alerts = self._load_alerts()
        ten_minutes_ago = (datetime.now() - timedelta(minutes=10)).isoformat()

        duplicate = False
        for a in alerts[-20:]:  # 只检查最近20条
            if a.get("category") == category and a.get("level") == level.value and a.get("timestamp") > ten_minutes_ago:
                duplicate = True
                break

        if not duplicate:
            alerts.append(alert)
            self._save_alerts(alerts)

            # 记录日志
            log_method = logger.warning if level == AlertLevel.WARNING else logger.error
            log_method(f"[系统预警][{level.value.upper()}] {message}")

    def get_health_summary(self, hours: int = 24) -> Dict:
        """获取健康摘要"""
        metrics = self._load_metrics()
        alerts = self._load_alerts()

        # 过滤时间范围内的数据
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        recent_metrics = [m for m in metrics if m.get("timestamp", "") > cutoff]
        recent_alerts = [a for a in alerts if a.get("timestamp", "") > cutoff]

        # 统计预警
        alert_counts = {
            "info": sum(1 for a in recent_alerts if a.get("level") == "info"),
            "warning": sum(1 for a in recent_alerts if a.get("level") == "warning"),
            "critical": sum(1 for a in recent_alerts if a.get("level") == "critical"),
            "alert": sum(1 for a in recent_alerts if a.get("level") == "alert"),
        }

        # 指标统计
        if recent_metrics:
            avg_cpu = sum(m.get("cpu_percent", 0) for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.get("memory_percent", 0) for m in recent_metrics) / len(recent_metrics)
            latest = recent_metrics[-1]
        else:
            avg_cpu = 0
            avg_memory = 0
            latest = {}

        return {
            "period_hours": hours,
            "alert_counts": alert_counts,
            "total_alerts": sum(alert_counts.values()),
            "average_cpu_percent": round(avg_cpu, 1),
            "average_memory_percent": round(avg_memory, 1),
            "latest_metrics": latest,
            "recent_alerts": recent_alerts[-10:],  # 最近10条预警
        }

    def get_current_status(self) -> Dict:
        """获取当前状态"""
        metrics = self.collect_system_metrics()
        alerts = self._load_alerts()

        # 最近5分钟的预警
        five_minutes_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
        recent_alerts = [a for a in alerts if a.get("timestamp", "") > five_minutes_ago]

        # 健康评分（简化版）
        score = 100
        if metrics.cpu_percent > 80:
            score -= 20
        elif metrics.cpu_percent > 70:
            score -= 10

        if metrics.memory_percent > 85:
            score -= 20
        elif metrics.memory_percent > 75:
            score -= 10

        if metrics.disk_usage_percent > 90:
            score -= 20
        elif metrics.disk_usage_percent > 80:
            score -= 10

        if recent_alerts:
            for alert in recent_alerts:
                if alert.get("level") == "critical":
                    score -= 15
                elif alert.get("level") == "warning":
                    score -= 5

        score = max(0, score)

        return {
            "health_score": score,
            "status": "healthy" if score >= 80 else "warning" if score >= 50 else "critical",
            "current_metrics": asdict(metrics),
            "recent_alerts": recent_alerts,
        }


# 全局实例
_health_monitor: Optional[SystemHealthMonitor] = None


def get_health_monitor() -> SystemHealthMonitor:
    """获取健康监控器全局实例"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SystemHealthMonitor()
    return _health_monitor
