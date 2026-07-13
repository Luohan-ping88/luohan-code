#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
告警系统模块 - PL5系统告警管理
功能：
1. 基于规则的告警检测
2. 多渠道告警通知（日志、邮件、Webhook）
3. 告警抑制和升级机制
4. 告警历史记录和统计
"""

import os
import sys
import time
import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 添加项目根目录到路径
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import BASE_DIR, LOGS_DIR
from monitor.performance_monitor import PerformanceMetrics, get_global_monitor

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """告警状态"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """告警数据类"""
    id: str
    rule_id: str
    name: str
    description: str
    severity: str
    status: str
    created_at: str
    updated_at: str
    metric_name: str
    metric_value: float
    threshold: float
    condition: str
    message: str
    actions_taken: List[str]
    notification_sent: bool
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Alert':
        return cls(**data)


class AlertRule:
    """告警规则类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.id = config['id']
        self.name = config['name']
        self.description = config.get('description', '')
        self.enabled = config.get('enabled', True)
        self.severity = config.get('severity', 'warning')
        self.condition = config['condition']
        self.actions = config.get('actions', ['log'])
        self.cooldown_sec = config.get('cooldown_sec', 300)
        
        # 运行时状态
        self.last_triggered: Optional[float] = None
        self.trigger_count = 0
        self.violation_start: Optional[float] = None
    
    def check_condition(self, metrics: PerformanceMetrics) -> bool:
        """检查是否满足告警条件"""
        if not self.enabled:
            return False
        
        metric_name = self.condition['metric']
        operator = self.condition['operator']
        threshold = self.condition['threshold']
        duration_sec = self.condition.get('duration_sec', 0)
        
        # 获取指标值
        metric_value = getattr(metrics, metric_name, None)
        if metric_value is None:
            return False
        
        # 检查条件
        condition_met = False
        if operator == '>':
            condition_met = metric_value > threshold
        elif operator == '>=':
            condition_met = metric_value >= threshold
        elif operator == '<':
            condition_met = metric_value < threshold
        elif operator == '<=':
            condition_met = metric_value <= threshold
        elif operator == '==':
            condition_met = metric_value == threshold
        elif operator == '!=':
            condition_met = metric_value != threshold
        
        current_time = time.time()
        
        if condition_met:
            if self.violation_start is None:
                self.violation_start = current_time
            
            # 检查持续时间
            if duration_sec > 0:
                violation_duration = current_time - self.violation_start
                if violation_duration < duration_sec:
                    return False  # 持续时间不足
            
            # 检查冷却期
            if self.last_triggered is not None:
                time_since_last = current_time - self.last_triggered
                if time_since_last < self.cooldown_sec:
                    return False  # 冷却期内
            
            self.last_triggered = current_time
            self.trigger_count += 1
            return True
        else:
            self.violation_start = None
            return False
    
    def get_message(self, metrics: PerformanceMetrics) -> str:
        """生成告警消息"""
        metric_value = getattr(metrics, self.condition['metric'], 'N/A')
        threshold = self.condition['threshold']
        operator = self.condition['operator']
        
        return (
            f"[{self.severity.upper()}] {self.name}\n"
            f"规则: {self.id}\n"
            f"指标: {self.condition['metric']} = {metric_value:.2f} {operator} {threshold}\n"
            f"描述: {self.description}\n"
            f"时间: {datetime.now().isoformat()}"
        )


class AlertManager:
    """告警管理器"""
    
    def __init__(self, 
                 rules_file: Optional[Path] = None,
                 alerts_file: Optional[Path] = None,
                 check_interval: int = 60):
        """
        初始化告警管理器
        
        Args:
            rules_file: 告警规则配置文件路径
            alerts_file: 告警记录文件路径
            check_interval: 告警检查间隔（秒）
        """
        self.rules_file = rules_file or BASE_DIR / "config" / "alert_rules.json"
        self.alerts_file = alerts_file or LOGS_DIR / "alerts.jsonl"
        self.alerts_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.check_interval = check_interval
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.max_history = 1000
        
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # 通知渠道配置
        self.notification_config: Dict[str, Any] = {}
        
        # 加载规则
        self._load_rules()
        
        logger.info(f"告警管理器初始化完成，规则文件: {self.rules_file}")
    
    def _load_rules(self):
        """加载告警规则"""
        try:
            if self.rules_file.exists():
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                for rule_config in config.get('rules', []):
                    rule = AlertRule(rule_config)
                    self.rules[rule.id] = rule
                
                self.notification_config = config.get('notification_channels', {})
                logger.info(f"已加载 {len(self.rules)} 条告警规则")
            else:
                logger.warning(f"告警规则文件不存在: {self.rules_file}")
        except Exception as e:
            logger.error(f"加载告警规则失败: {e}")
    
    def start(self):
        """启动告警检查"""
        if self.is_running:
            logger.warning("告警管理器已经在运行")
            return
        
        self.is_running = True
        self._stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._check_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("告警管理器已启动")
    
    def stop(self):
        """停止告警检查"""
        if not self.is_running:
            return
        
        self.is_running = False
        self._stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("告警管理器已停止")
    
    def _check_loop(self):
        """告警检查主循环"""
        monitor = get_global_monitor()
        
        while not self._stop_event.is_set():
            try:
                # 获取最新指标
                if monitor.metrics_history:
                    latest_metrics = monitor.metrics_history[-1]
                    self.check_metrics(latest_metrics)
                
            except Exception as e:
                logger.error(f"告警检查异常: {e}")
            
            self._stop_event.wait(self.check_interval)
    
    def check_metrics(self, metrics: PerformanceMetrics):
        """检查指标是否触发告警"""
        for rule in self.rules.values():
            try:
                if rule.check_condition(metrics):
                    self._trigger_alert(rule, metrics)
            except Exception as e:
                logger.error(f"检查规则 {rule.id} 失败: {e}")
    
    def _trigger_alert(self, rule: AlertRule, metrics: PerformanceMetrics):
        """触发告警"""
        alert_id = f"{rule.id}_{int(time.time())}"
        
        # 检查是否已有相同规则的活跃告警
        existing_alert = None
        for alert in self.active_alerts.values():
            if alert.rule_id == rule.id and alert.status == AlertStatus.ACTIVE.value:
                existing_alert = alert
                break
        
        if existing_alert:
            # 更新现有告警
            existing_alert.updated_at = datetime.now().isoformat()
            existing_alert.metric_value = getattr(metrics, rule.condition['metric'], 0)
            logger.debug(f"更新告警: {existing_alert.id}")
            return
        
        # 创建新告警
        alert = Alert(
            id=alert_id,
            rule_id=rule.id,
            name=rule.name,
            description=rule.description,
            severity=rule.severity,
            status=AlertStatus.ACTIVE.value,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            metric_name=rule.condition['metric'],
            metric_value=getattr(metrics, rule.condition['metric'], 0),
            threshold=rule.condition['threshold'],
            condition=f"{rule.condition['operator']} {rule.condition['threshold']}",
            message=rule.get_message(metrics),
            actions_taken=[],
            notification_sent=False
        )
        
        self.active_alerts[alert_id] = alert
        
        # 执行告警动作
        self._execute_actions(alert, rule)
        
        # 保存告警记录
        self._save_alert(alert)
        
        logger.warning(f"告警触发: [{rule.severity.upper()}] {rule.name}")
    
    def _execute_actions(self, alert: Alert, rule: AlertRule):
        """执行告警动作"""
        for action in rule.actions:
            try:
                if action == 'log':
                    self._action_log(alert)
                elif action == 'email':
                    self._action_email(alert)
                elif action == 'alert':
                    self._action_alert(alert)
                elif action == 'notify_admin':
                    self._action_notify_admin(alert)
                
                alert.actions_taken.append(action)
            except Exception as e:
                logger.error(f"执行告警动作 {action} 失败: {e}")
    
    def _action_log(self, alert: Alert):
        """记录日志"""
        log_message = f"[ALERT] {alert.message}"
        if alert.severity == 'critical':
            logger.critical(log_message)
        elif alert.severity == 'warning':
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def _action_email(self, alert: Alert):
        """发送邮件通知"""
        email_config = self.notification_config.get('email', {})
        if not email_config.get('enabled', False):
            return
        
        try:
            # 这里简化处理，实际应该使用邮件发送模块
            recipients = email_config.get('recipients', [])
            if recipients:
                logger.info(f"发送告警邮件到: {recipients}")
                # TODO: 实现实际邮件发送逻辑
                alert.notification_sent = True
        except Exception as e:
            logger.error(f"发送告警邮件失败: {e}")
    
    def _action_alert(self, alert: Alert):
        """系统级告警"""
        # 可以集成到系统通知、短信等
        logger.warning(f"系统告警: {alert.name}")
    
    def _action_notify_admin(self, alert: Alert):
        """通知管理员"""
        logger.critical(f"管理员通知: {alert.message}")
        # TODO: 实现管理员通知逻辑（如短信、电话等）
    
    def _save_alert(self, alert: Alert):
        """保存告警记录"""
        try:
            with open(self.alerts_file, 'a', encoding='utf-8') as f:
                json.dump(alert.to_dict(), f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            logger.error(f"保存告警记录失败: {e}")
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """确认告警"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.updated_at = datetime.now().isoformat()
        
        logger.info(f"告警已确认: {alert_id} by {acknowledged_by}")
        return True
    
    def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """解决告警"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.RESOLVED.value
        alert.updated_at = datetime.now().isoformat()
        alert.resolved_at = datetime.now().isoformat()
        alert.resolved_by = resolved_by
        
        # 移到历史记录
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        del self.active_alerts[alert_id]
        
        logger.info(f"告警已解决: {alert_id} by {resolved_by}")
        return True
    
    def get_active_alerts(self, severity: Optional[str] = None) -> List[Alert]:
        """获取活跃告警"""
        alerts = list(self.active_alerts.values())
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts
    
    def get_alert_history(self, 
                         start_time: Optional[str] = None,
                         end_time: Optional[str] = None,
                         severity: Optional[str] = None,
                         limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        alerts = self.alert_history.copy()
        
        if start_time:
            alerts = [a for a in alerts if a.created_at >= start_time]
        if end_time:
            alerts = [a for a in alerts if a.created_at <= end_time]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return alerts[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取告警统计"""
        all_alerts = list(self.active_alerts.values()) + self.alert_history
        
        stats = {
            'total_alerts': len(all_alerts),
            'active_alerts': len(self.active_alerts),
            'by_severity': {
                'info': 0,
                'warning': 0,
                'critical': 0
            },
            'by_status': {
                'active': 0,
                'acknowledged': 0,
                'resolved': 0
            },
            'by_rule': {}
        }
        
        for alert in all_alerts:
            stats['by_severity'][alert.severity] = stats['by_severity'].get(alert.severity, 0) + 1
            stats['by_status'][alert.status] = stats['by_status'].get(alert.status, 0) + 1
            
            if alert.rule_id not in stats['by_rule']:
                stats['by_rule'][alert.rule_id] = 0
            stats['by_rule'][alert.rule_id] += 1
        
        return stats
    
    def suppress_rule(self, rule_id: str, duration_minutes: int = 60):
        """临时抑制告警规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            logger.info(f"告警规则 {rule_id} 已抑制 {duration_minutes} 分钟")
            
            # 设置定时恢复
            def restore_rule():
                time.sleep(duration_minutes * 60)
                if rule_id in self.rules:
                    self.rules[rule_id].enabled = True
                    logger.info(f"告警规则 {rule_id} 已恢复")
            
            threading.Thread(target=restore_rule, daemon=True).start()
    
    def enable_rule(self, rule_id: str):
        """启用告警规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            logger.info(f"告警规则 {rule_id} 已启用")


# 全局告警管理器实例
_global_alert_manager: Optional[AlertManager] = None


def get_global_alert_manager() -> AlertManager:
    """获取全局告警管理器实例"""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = AlertManager()
    return _global_alert_manager


def start_alert_system():
    """启动告警系统"""
    manager = get_global_alert_manager()
    manager.start()
    return manager


def stop_alert_system():
    """停止告警系统"""
    global _global_alert_manager
    if _global_alert_manager:
        _global_alert_manager.stop()


def check_alerts(metrics: PerformanceMetrics):
    """手动检查告警"""
    manager = get_global_alert_manager()
    manager.check_metrics(metrics)


def get_active_alerts(severity: Optional[str] = None) -> List[Alert]:
    """获取活跃告警"""
    manager = get_global_alert_manager()
    return manager.get_active_alerts(severity)


def acknowledge_alert(alert_id: str, acknowledged_by: str = "system") -> bool:
    """确认告警"""
    manager = get_global_alert_manager()
    return manager.acknowledge_alert(alert_id, acknowledged_by)


def resolve_alert(alert_id: str, resolved_by: str = "system") -> bool:
    """解决告警"""
    manager = get_global_alert_manager()
    return manager.resolve_alert(alert_id, resolved_by)


# 如果直接运行此模块，启动告警系统测试
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 启动告警系统
    manager = start_alert_system()
    
    print("告警系统已启动，按Ctrl+C停止...")
    print(f"规则文件: {manager.rules_file}")
    print(f"告警记录: {manager.alerts_file}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止告警系统...")
        stop_alert_system()
        
        # 打印统计
        stats = manager.get_statistics()
        print("\n告警统计:")
        print(json.dumps(stats, indent=2, ensure_ascii=False))
