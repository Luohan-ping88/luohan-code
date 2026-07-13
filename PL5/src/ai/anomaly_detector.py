"""异常流量检测模块
使用统计分析和机器学习方法检测异常流量模式
"""

import os
import time
import logging
from collections import defaultdict
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from threading import Lock
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TrafficPattern:
    """流量模式"""
    ip_address: str
    request_count: int
    request_types: Dict[str, int]
    status_codes: Dict[int, int]
    avg_response_time: float
    first_request_time: float
    last_request_time: float


@dataclass
class AnomalyAlert:
    """异常告警"""
    alert_id: str
    alert_type: str
    severity: str
    message: str
    details: Dict[str, Any]
    timestamp: float
    ip_address: Optional[str] = None
    user: Optional[str] = None


class AnomalyDetector:
    """异常流量检测器"""
    
    def __init__(self):
        self.traffic_patterns = defaultdict(lambda: TrafficPattern(
            ip_address="",
            request_count=0,
            request_types=defaultdict(int),
            status_codes=defaultdict(int),
            avg_response_time=0.0,
            first_request_time=0.0,
            last_request_time=0.0
        ))
        self.alerts = []
        self.lock = Lock()
        self.learning_period = 3600  # 学习周期（秒）
        self.thresholds = {
            "request_rate": int(os.getenv("ANOMALY_REQUEST_RATE", "100")),  # 每分钟最大请求数
            "error_rate": float(os.getenv("ANOMALY_ERROR_RATE", "0.3")),  # 错误率阈值
            "response_time_spike": float(os.getenv("ANOMALY_RESPONSE_TIME_SPIKE", "2.0")),  # 响应时间突增倍数
            "concurrent_users": int(os.getenv("ANOMALY_CONCURRENT_USERS", "100")),  # 并发用户数阈值
            "unusual_method_ratio": float(os.getenv("ANOMALY_UNUSUAL_METHOD_RATIO", "0.1"))  # 异常请求方法比例
        }
        self.baseline = {}
        self.last_baseline_update = 0
    
    def record_request(self, ip_address: str, request_type: str, status_code: int, response_time: float):
        """记录请求信息"""
        with self.lock:
            pattern = self.traffic_patterns[ip_address]
            pattern.ip_address = ip_address
            pattern.request_count += 1
            pattern.request_types[request_type] += 1
            pattern.status_codes[status_code] += 1
            pattern.last_request_time = time.time()
            
            if pattern.first_request_time == 0:
                pattern.first_request_time = pattern.last_request_time
            
            # 更新平均响应时间
            pattern.avg_response_time = (pattern.avg_response_time * (pattern.request_count - 1) + response_time) / pattern.request_count
    
    def detect_anomalies(self) -> List[AnomalyAlert]:
        """检测异常流量模式"""
        alerts = []
        now = time.time()
        
        with self.lock:
            # 更新基线
            self._update_baseline()
            
            for ip, pattern in self.traffic_patterns.items():
                # 检查是否在学习周期内（跳过新IP）
                if now - pattern.first_request_time < 300:  # 前5分钟跳过
                    continue
                
                # 检测请求速率异常
                time_window = pattern.last_request_time - pattern.first_request_time
                if time_window > 0:
                    requests_per_minute = (pattern.request_count / time_window) * 60
                    if requests_per_minute > self.thresholds["request_rate"]:
                        alerts.append(self._create_alert(
                            alert_type="request_rate_anomaly",
                            severity="high",
                            message=f"IP {ip} 请求速率异常: {requests_per_minute:.2f}/分钟",
                            details={
                                "ip_address": ip,
                                "request_count": pattern.request_count,
                                "requests_per_minute": requests_per_minute,
                                "threshold": self.thresholds["request_rate"]
                            },
                            ip_address=ip
                        ))
                
                # 检测错误率异常
                total_requests = pattern.request_count
                error_requests = sum(count for code, count in pattern.status_codes.items() if code >= 400)
                if total_requests > 0:
                    error_rate = error_requests / total_requests
                    if error_rate > self.thresholds["error_rate"]:
                        alerts.append(self._create_alert(
                            alert_type="error_rate_anomaly",
                            severity="medium",
                            message=f"IP {ip} 错误率异常: {error_rate:.2%}",
                            details={
                                "ip_address": ip,
                                "error_rate": error_rate,
                                "error_count": error_requests,
                                "total_requests": total_requests,
                                "status_codes": dict(pattern.status_codes)
                            },
                            ip_address=ip
                        ))
                
                # 检测响应时间突增
                if "avg_response_time" in self.baseline:
                    baseline_rt = self.baseline["avg_response_time"]
                    if baseline_rt > 0 and pattern.avg_response_time > baseline_rt * self.thresholds["response_time_spike"]:
                        alerts.append(self._create_alert(
                            alert_type="response_time_anomaly",
                            severity="medium",
                            message=f"IP {ip} 响应时间突增: {pattern.avg_response_time:.2f}ms",
                            details={
                                "ip_address": ip,
                                "current_response_time": pattern.avg_response_time,
                                "baseline_response_time": baseline_rt,
                                "increase_ratio": pattern.avg_response_time / baseline_rt
                            },
                            ip_address=ip
                        ))
                
                # 检测异常请求方法比例
                total_request_types = sum(pattern.request_types.values())
                if total_request_types > 0:
                    for method, count in pattern.request_types.items():
                        ratio = count / total_request_types
                        if method not in ["GET", "POST", "PUT", "DELETE"] and ratio > self.thresholds["unusual_method_ratio"]:
                            alerts.append(self._create_alert(
                                alert_type="unusual_method_anomaly",
                                severity="low",
                                message=f"IP {ip} 使用异常请求方法 {method}: {ratio:.2%}",
                                details={
                                    "ip_address": ip,
                                    "method": method,
                                    "ratio": ratio,
                                    "count": count
                                },
                                ip_address=ip
                            ))
            
            # 检测整体并发用户数
            concurrent_users = len(self.traffic_patterns)
            if concurrent_users > self.thresholds["concurrent_users"]:
                alerts.append(self._create_alert(
                    alert_type="concurrent_users_anomaly",
                    severity="high",
                    message=f"并发用户数异常: {concurrent_users}",
                    details={
                        "concurrent_users": concurrent_users,
                        "threshold": self.thresholds["concurrent_users"]
                    }
                ))
        
        # 添加告警到列表
        self.alerts.extend(alerts)
        
        # 清理旧告警（保留最近100条）
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        return alerts
    
    def _update_baseline(self):
        """更新流量基线"""
        now = time.time()
        if now - self.last_baseline_update < self.learning_period:
            return
        
        with self.lock:
            total_requests = sum(p.request_count for p in self.traffic_patterns.values())
            total_response_time = sum(p.avg_response_time * p.request_count for p in self.traffic_patterns.values())
            
            self.baseline = {
                "avg_request_rate": total_requests / self.learning_period if self.learning_period > 0 else 0,
                "avg_response_time": total_response_time / total_requests if total_requests > 0 else 0,
                "ip_count": len(self.traffic_patterns)
            }
            
            self.last_baseline_update = now
            logger.info(f"流量基线已更新: {self.baseline}")
    
    def _create_alert(self, alert_type: str, severity: str, message: str, details: Dict[str, Any], 
                     ip_address: str = None, user: str = None) -> AnomalyAlert:
        """创建告警"""
        return AnomalyAlert(
            alert_id=f"{alert_type}_{int(time.time())}_{hash(ip_address or 'unknown') % 1000}",
            alert_type=alert_type,
            severity=severity,
            message=message,
            details=details,
            timestamp=time.time(),
            ip_address=ip_address,
            user=user
        )
    
    def get_alerts(self, severity: Optional[str] = None, limit: int = 50) -> List[AnomalyAlert]:
        """获取告警列表"""
        alerts = self.alerts.copy()
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        # 按时间排序（最新的在前）
        alerts.sort(key=lambda x: x.timestamp, reverse=True)
        
        return alerts[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取流量统计信息"""
        with self.lock:
            total_requests = sum(p.request_count for p in self.traffic_patterns.values())
            total_errors = sum(
                sum(count for code, count in p.status_codes.items() if code >= 400)
                for p in self.traffic_patterns.values()
            )
            
            return {
                "total_ips": len(self.traffic_patterns),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate": total_errors / total_requests if total_requests > 0 else 0,
                "avg_response_time": sum(p.avg_response_time for p in self.traffic_patterns.values()) / len(self.traffic_patterns) if self.traffic_patterns else 0,
                "alert_count": len(self.alerts),
                "baseline": self.baseline,
                "last_baseline_update": self.last_baseline_update,
                "thresholds": self.thresholds
            }
    
    def cleanup_old_patterns(self, max_age_seconds: int = 3600):
        """清理旧的流量模式"""
        now = time.time()
        with self.lock:
            old_ips = [
                ip for ip, pattern in self.traffic_patterns.items()
                if now - pattern.last_request_time > max_age_seconds
            ]
            
            for ip in old_ips:
                del self.traffic_patterns[ip]
            
            if old_ips:
                logger.info(f"清理了 {len(old_ips)} 个过期的流量模式")
    
    def reset(self):
        """重置检测器"""
        with self.lock:
            self.traffic_patterns.clear()
            self.alerts.clear()
            self.baseline.clear()
            self.last_baseline_update = 0
            logger.info("异常检测器已重置")


# 全局异常检测器实例
_anomaly_detector = AnomalyDetector()


def get_anomaly_detector() -> AnomalyDetector:
    """获取全局异常检测器"""
    return _anomaly_detector


# 示例使用
if __name__ == "__main__":
    detector = get_anomaly_detector()
    
    # 模拟一些请求
    for i in range(100):
        detector.record_request("192.168.1.1", "GET", 200, 0.1)
        detector.record_request("192.168.1.2", "POST", 200, 0.2)
        if i % 10 == 0:
            detector.record_request("192.168.1.1", "GET", 500, 1.0)
    
    # 检测异常
    anomalies = detector.detect_anomalies()
    print(f"检测到 {len(anomalies)} 个异常")
    for alert in anomalies:
        print(f"[{alert.severity}] {alert.message}")
    
    # 输出统计信息
    stats = detector.get_statistics()
    print("\n流量统计:")
    print(stats)