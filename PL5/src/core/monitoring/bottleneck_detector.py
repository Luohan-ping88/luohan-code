#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能瓶颈自动检测模块
实现系统性能瓶颈的自动识别和分析
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.core.monitoring.performance_monitor import (
    get_performance_monitor,
    get_performance_tracker,
)
from src.core.utils.logger import setup_logging

logger = setup_logging(__name__)


class BottleneckDetector:
    """性能瓶颈检测器"""

    def __init__(self, history_window: int = 30):
        """初始化瓶颈检测器"""
        self.history_window = history_window  # 历史数据窗口大小
        self.performance_monitor = get_performance_monitor()
        self.performance_tracker = get_performance_tracker()
        self.bottlenecks_history = []
        self.thresholds = {
            "cpu": 80,  # CPU使用率阈值
            "memory": 85,  # 内存使用率阈值
            "disk": 90,  # 磁盘使用率阈值
            "execution_time": 5.0,  # 函数执行时间阈值（秒）
            "memory_growth": 100.0,  # 内存增长阈值（MB）
        }

        logger.info("性能瓶颈检测器初始化完成")

    def detect_system_bottlenecks(self) -> List[Dict[str, Any]]:
        """检测系统级瓶颈"""
        bottlenecks = []

        # 获取当前性能指标
        current_metrics = self.performance_monitor.get_current_metrics()
        if "error" in current_metrics:
            logger.error(f"获取性能指标失败: {current_metrics['error']}")
            return bottlenecks

        # 检查系统级指标
        if "system" in current_metrics:
            system = current_metrics["system"]

            # 检查CPU
            if system["cpu_percent"] > self.thresholds["cpu"]:
                bottlenecks.append(
                    {
                        "type": "system_cpu",
                        "severity": "high",
                        "message": f"CPU使用率过高: {system['cpu_percent']:.1f}%",
                        "value": system["cpu_percent"],
                        "threshold": self.thresholds["cpu"],
                        "timestamp": current_metrics["timestamp"],
                    }
                )

            # 检查内存
            if system["memory_percent"] > self.thresholds["memory"]:
                bottlenecks.append(
                    {
                        "type": "system_memory",
                        "severity": "high",
                        "message": f"内存使用率过高: {system['memory_percent']:.1f}%",
                        "value": system["memory_percent"],
                        "threshold": self.thresholds["memory"],
                        "timestamp": current_metrics["timestamp"],
                    }
                )

            # 检查磁盘
            if system["disk_percent"] > self.thresholds["disk"]:
                bottlenecks.append(
                    {
                        "type": "system_disk",
                        "severity": "medium",
                        "message": f"磁盘使用率过高: {system['disk_percent']:.1f}%",
                        "value": system["disk_percent"],
                        "threshold": self.thresholds["disk"],
                        "timestamp": current_metrics["timestamp"],
                    }
                )

        # 检查进程级指标
        if "process" in current_metrics:
            process = current_metrics["process"]

            # 检查进程CPU
            if process["cpu_percent"] > 50:
                bottlenecks.append(
                    {
                        "type": "process_cpu",
                        "severity": "medium",
                        "message": f"进程CPU使用率过高: {process['cpu_percent']:.1f}%",
                        "value": process["cpu_percent"],
                        "threshold": 50,
                        "timestamp": current_metrics["timestamp"],
                    }
                )

            # 检查进程内存
            if process["memory_mb"] > 500:
                bottlenecks.append(
                    {
                        "type": "process_memory",
                        "severity": "medium",
                        "message": f"进程内存使用过高: {process['memory_mb']:.1f} MB",
                        "value": process["memory_mb"],
                        "threshold": 500,
                        "timestamp": current_metrics["timestamp"],
                    }
                )

        return bottlenecks

    def detect_function_bottlenecks(self) -> List[Dict[str, Any]]:
        """检测函数级瓶颈"""
        bottlenecks = []

        # 获取所有函数的统计信息
        all_stats = self.performance_tracker.get_all_stats()

        for func_name, stats in all_stats.items():
            if not stats:
                continue

            # 检查执行时间
            if stats["avg_execution_time"] > self.thresholds["execution_time"]:
                bottlenecks.append(
                    {
                        "type": "function_execution_time",
                        "severity": (
                            "high"
                            if stats["avg_execution_time"]
                            > self.thresholds["execution_time"] * 2
                            else "medium"
                        ),
                        "message": f"函数 {func_name} 执行时间过长: {stats['avg_execution_time']:.2f} 秒",
                        "function": func_name,
                        "value": stats["avg_execution_time"],
                        "threshold": self.thresholds["execution_time"],
                        "calls": stats["calls"],
                        "timestamp": stats["last_execution"],
                    }
                )

            # 检查内存使用
            if stats["avg_memory_used"] > 50:
                bottlenecks.append(
                    {
                        "type": "function_memory",
                        "severity": "medium",
                        "message": f"函数 {func_name} 内存使用过高: {stats['avg_memory_used']:.2f} MB",
                        "function": func_name,
                        "value": stats["avg_memory_used"],
                        "threshold": 50,
                        "calls": stats["calls"],
                        "timestamp": stats["last_execution"],
                    }
                )

        return bottlenecks

    def detect_trends(self) -> List[Dict[str, Any]]:
        """检测性能趋势"""
        trends = []

        # 获取历史性能数据
        history = self.performance_monitor.get_history(self.history_window)
        if len(history) < 5:
            return trends

        # 分析CPU趋势
        cpu_values = [
            h["system"]["cpu_percent"] for h in history if "system" in h
        ]
        if cpu_values:
            cpu_trend = self._calculate_trend(cpu_values)
            if cpu_trend > 0.5:  # 上升趋势
                trends.append(
                    {
                        "type": "cpu_trend",
                        "severity": "medium",
                        "message": f"CPU使用率呈上升趋势，平均增长: {cpu_trend:.2f}%/样本",
                        "value": cpu_trend,
                        "timestamp": history[-1]["timestamp"],
                    }
                )

        # 分析内存趋势
        memory_values = [
            h["system"]["memory_percent"] for h in history if "system" in h
        ]
        if memory_values:
            memory_trend = self._calculate_trend(memory_values)
            if memory_trend > 0.3:  # 上升趋势
                trends.append(
                    {
                        "type": "memory_trend",
                        "severity": "medium",
                        "message": f"内存使用率呈上升趋势，平均增长: {memory_trend:.2f}%/样本",
                        "value": memory_trend,
                        "timestamp": history[-1]["timestamp"],
                    }
                )

        return trends

    def _calculate_trend(self, values: List[float]) -> float:
        """计算趋势值"""
        if len(values) < 2:
            return 0

        # 简单线性回归计算趋势
        n = len(values)
        x = list(range(n))
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        if n * sum_x2 - sum_x**2 == 0:
            return 0

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)
        return slope

    def detect_all_bottlenecks(self) -> Dict[str, List[Dict[str, Any]]]:
        """检测所有类型的瓶颈"""
        bottlenecks = {
            "system": self.detect_system_bottlenecks(),
            "function": self.detect_function_bottlenecks(),
            "trends": self.detect_trends(),
        }

        # 记录检测结果
        for category, items in bottlenecks.items():
            for item in items:
                self.bottlenecks_history.append(
                    {
                        **item,
                        "category": category,
                        "detection_time": datetime.now().isoformat(),
                    }
                )

        # 限制历史记录长度
        if len(self.bottlenecks_history) > 1000:
            self.bottlenecks_history = self.bottlenecks_history[-1000:]

        return bottlenecks

    def get_bottleneck_summary(self) -> Dict[str, Any]:
        """获取瓶颈摘要"""
        recent_bottlenecks = self.bottlenecks_history[-50:]  # 最近50条记录

        summary = {
            "total_bottlenecks": len(recent_bottlenecks),
            "by_category": {},
            "by_severity": {},
            "most_common": {},
            "last_detection": (
                recent_bottlenecks[-1]["detection_time"]
                if recent_bottlenecks
                else None
            ),
        }

        # 按类别统计
        for bottleneck in recent_bottlenecks:
            category = bottleneck.get("category", "unknown")
            summary["by_category"][category] = (
                summary["by_category"].get(category, 0) + 1
            )

            severity = bottleneck.get("severity", "unknown")
            summary["by_severity"][severity] = (
                summary["by_severity"].get(severity, 0) + 1
            )

            # 统计最常见的瓶颈类型
            bottleneck_type = bottleneck.get("type", "unknown")
            summary["most_common"][bottleneck_type] = (
                summary["most_common"].get(bottleneck_type, 0) + 1
            )

        return summary

    def generate_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """生成优化建议"""
        recommendations = []
        bottlenecks = self.detect_all_bottlenecks()

        # 系统级优化建议
        for bottleneck in bottlenecks["system"]:
            if bottleneck["type"] == "system_cpu":
                recommendations.append(
                    {
                        "type": "system_cpu",
                        "priority": (
                            "high"
                            if bottleneck["severity"] == "high"
                            else "medium"
                        ),
                        "recommendation": "考虑优化CPU密集型任务，或增加系统CPU资源",
                        "affected_area": "系统整体性能",
                        "bottleneck_details": bottleneck,
                    }
                )
            elif bottleneck["type"] == "system_memory":
                recommendations.append(
                    {
                        "type": "system_memory",
                        "priority": (
                            "high"
                            if bottleneck["severity"] == "high"
                            else "medium"
                        ),
                        "recommendation": "检查内存泄漏，优化内存使用，或增加系统内存",
                        "affected_area": "系统整体性能",
                        "bottleneck_details": bottleneck,
                    }
                )
            elif bottleneck["type"] == "system_disk":
                recommendations.append(
                    {
                        "type": "system_disk",
                        "priority": "medium",
                        "recommendation": "清理磁盘空间，考虑使用更快的存储设备",
                        "affected_area": "I/O性能",
                        "bottleneck_details": bottleneck,
                    }
                )

        # 函数级优化建议
        for bottleneck in bottlenecks["function"]:
            if bottleneck["type"] == "function_execution_time":
                recommendations.append(
                    {
                        "type": "function_execution_time",
                        "priority": (
                            "high"
                            if bottleneck["severity"] == "high"
                            else "medium"
                        ),
                        "recommendation": f'优化函数 {bottleneck["function"]} 的执行逻辑，考虑缓存、并行处理或算法优化',
                        "affected_area": f'函数 {bottleneck["function"]}',
                        "bottleneck_details": bottleneck,
                    }
                )
            elif bottleneck["type"] == "function_memory":
                recommendations.append(
                    {
                        "type": "function_memory",
                        "priority": "medium",
                        "recommendation": f'优化函数 {bottleneck["function"]} 的内存使用，避免不必要的对象创建',
                        "affected_area": f'函数 {bottleneck["function"]}',
                        "bottleneck_details": bottleneck,
                    }
                )

        # 趋势优化建议
        for trend in bottlenecks["trends"]:
            if trend["type"] == "cpu_trend":
                recommendations.append(
                    {
                        "type": "cpu_trend",
                        "priority": "medium",
                        "recommendation": "监控CPU使用趋势，预测资源需求，提前进行优化",
                        "affected_area": "系统整体性能",
                        "bottleneck_details": trend,
                    }
                )
            elif trend["type"] == "memory_trend":
                recommendations.append(
                    {
                        "type": "memory_trend",
                        "priority": "medium",
                        "recommendation": "检查内存使用增长原因，可能存在内存泄漏",
                        "affected_area": "系统整体性能",
                        "bottleneck_details": trend,
                    }
                )

        return recommendations

    def save_bottleneck_report(self, report_path: Optional[Path] = None):
        """保存瓶颈报告"""
        if report_path is None:
            report_path = (
                Path("logs")
                / "performance"
                / f"bottleneck_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": self.get_bottleneck_summary(),
            "bottlenecks": self.detect_all_bottlenecks(),
            "recommendations": self.generate_optimization_recommendations(),
            "system_metrics": self.performance_monitor.get_current_metrics(),
            "performance_summary": self.performance_monitor.get_performance_summary(),
        }

        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"瓶颈报告已保存到: {report_path}")
            return report_path
        except Exception as e:
            logger.error(f"保存瓶颈报告失败: {str(e)}")
            return None


# 全局瓶颈检测器实例
_global_detector = None


def get_bottleneck_detector() -> BottleneckDetector:
    """获取全局瓶颈检测器实例"""
    global _global_detector
    if _global_detector is None:
        _global_detector = BottleneckDetector()
    return _global_detector


def detect_bottlenecks() -> Dict[str, List[Dict[str, Any]]]:
    """检测性能瓶颈"""
    detector = get_bottleneck_detector()
    return detector.detect_all_bottlenecks()


def generate_optimization_recommendations() -> List[Dict[str, Any]]:
    """生成优化建议"""
    detector = get_bottleneck_detector()
    return detector.generate_optimization_recommendations()


def save_bottleneck_report(
    report_path: Optional[Path] = None,
) -> Optional[Path]:
    """保存瓶颈报告"""
    detector = get_bottleneck_detector()
    return detector.save_bottleneck_report(report_path)
