"""资源管理模块

监控和管理系统资源的使用情况，包括CPU、内存、磁盘等，确保系统高效运行。
"""

import os
import psutil
import time
from datetime import datetime
from typing import Dict, Optional, Any, List

from src.core.utils.logger import logger, log_performance_metric


class ResourceManager:
    """资源管理器"""

    def __init__(
        self,
        cpu_threshold: float = 80.0,  # CPU使用率阈值(%)
        memory_threshold: float = 80.0,  # 内存使用率阈值(%)
        disk_threshold: float = 90.0,  # 磁盘使用率阈值(%)
        check_interval: int = 60,  # 检查间隔(秒)
        history_size: int = 100,  # 历史记录大小
    ):
        """初始化资源管理器

        Args:
            cpu_threshold: CPU使用率阈值(%)
            memory_threshold: 内存使用率阈值(%)
            disk_threshold: 磁盘使用率阈值(%)
            check_interval: 检查间隔(秒)
            history_size: 历史记录大小
        """
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.disk_threshold = disk_threshold
        self.check_interval = check_interval
        self.history_size = history_size
        self.last_check_time = 0

        # 资源使用历史记录
        self.resource_history: List[Dict[str, Any]] = []

        # 尝试导入GPU监控库
        self.gpu_available = False
        try:
            import torch

            if torch.cuda.is_available():
                self.gpu_available = True
                logger.info("GPU监控已启用")
        except Exception as e:
            logger.info(f"GPU监控不可用: {e}")

    def get_resource_usage(self) -> Dict[str, Any]:
        """获取当前资源使用情况

        Returns:
            Dict: 资源使用情况
        """
        # 获取CPU使用情况
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=True)

        # 获取内存使用情况
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used / (1024 * 1024 * 1024)  # 转换为GB
        memory_total = memory.total / (1024 * 1024 * 1024)  # 转换为GB

        # 获取磁盘使用情况
        disk = psutil.disk_usage("/")
        disk_percent = disk.percent
        disk_used = disk.used / (1024 * 1024 * 1024)  # 转换为GB
        disk_total = disk.total / (1024 * 1024 * 1024)  # 转换为GB

        # 获取系统负载
        load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)

        # 构建资源使用情况字典
        usage = {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "threshold": self.cpu_threshold,
                "over_threshold": cpu_percent > self.cpu_threshold,
            },
            "memory": {
                "percent": memory_percent,
                "used": memory_used,
                "total": memory_total,
                "threshold": self.memory_threshold,
                "over_threshold": memory_percent > self.memory_threshold,
            },
            "disk": {
                "percent": disk_percent,
                "used": disk_used,
                "total": disk_total,
                "threshold": self.disk_threshold,
                "over_threshold": disk_percent > self.disk_threshold,
            },
            "load_avg": load_avg,
        }

        # 添加GPU使用情况（如果可用）
        if self.gpu_available:
            try:
                import torch

                gpu_count = torch.cuda.device_count()
                gpu_usage = []
                for i in range(gpu_count):
                    gpu_mem = torch.cuda.memory_allocated(i) / (1024 * 1024 * 1024)  # 转换为GB
                    gpu_total = torch.cuda.get_device_properties(i).total_memory / (1024 * 1024 * 1024)  # 转换为GB
                    gpu_percent = (gpu_mem / gpu_total) * 100
                    gpu_usage.append({"id": i, "percent": gpu_percent, "used": gpu_mem, "total": gpu_total})
                usage["gpu"] = {"count": gpu_count, "usage": gpu_usage}
            except Exception as e:
                logger.warning(f"GPU监控失败: {e}")

        # 记录历史数据
        self._add_to_history(usage)

        return usage

    def _add_to_history(self, usage: Dict[str, Any]):
        """添加资源使用情况到历史记录

        Args:
            usage: 资源使用情况
        """
        self.resource_history.append(usage)
        if len(self.resource_history) > self.history_size:
            self.resource_history.pop(0)

    def check_resources(self) -> bool:
        """检查资源使用情况

        Returns:
            bool: 是否所有资源都在安全范围内
        """
        current_time = time.time()
        if current_time - self.last_check_time < self.check_interval:
            return True

        self.last_check_time = current_time

        usage = self.get_resource_usage()

        # 记录资源使用情况
        log_performance_metric("CPU Usage", usage["cpu"]["percent"], "%")
        log_performance_metric("Memory Usage", usage["memory"]["percent"], "%")
        log_performance_metric("Disk Usage", usage["disk"]["percent"], "%")

        # 记录GPU使用情况（如果可用）
        if "gpu" in usage:
            for gpu in usage["gpu"]["usage"]:
                log_performance_metric(f'GPU {gpu["id"]} Usage', gpu["percent"], "%")

        # 自动调整阈值
        self._auto_adjust_thresholds()

        # 检查是否有资源超过阈值
        over_threshold = False
        if usage["cpu"]["over_threshold"]:
            logger.warning(f"CPU使用率超过阈值: {usage['cpu']['percent']}% > {self.cpu_threshold}%")
            over_threshold = True

        if usage["memory"]["over_threshold"]:
            logger.warning(f"内存使用率超过阈值: {usage['memory']['percent']}% > {self.memory_threshold}%")
            over_threshold = True

        if usage["disk"]["over_threshold"]:
            logger.warning(f"磁盘使用率超过阈值: {usage['disk']['percent']}% > {self.disk_threshold}%")
            over_threshold = True

        # 检查GPU使用情况（如果可用）
        if "gpu" in usage:
            for gpu in usage["gpu"]["usage"]:
                if gpu["percent"] > 90:
                    logger.warning(f"GPU {gpu['id']} 使用率超过90%: {gpu['percent']:.1f}%")
                    over_threshold = True

        return not over_threshold

    def _auto_adjust_thresholds(self):
        """自动调整资源使用阈值

        根据历史资源使用情况动态调整阈值，以适应系统负载变化
        """
        if len(self.resource_history) < 10:
            return

        # 计算历史平均资源使用情况
        cpu_usages = [h["cpu"]["percent"] for h in self.resource_history]
        memory_usages = [h["memory"]["percent"] for h in self.resource_history]
        disk_usages = [h["disk"]["percent"] for h in self.resource_history]

        avg_cpu = sum(cpu_usages) / len(cpu_usages)
        avg_memory = sum(memory_usages) / len(memory_usages)
        avg_disk = sum(disk_usages) / len(disk_usages)

        # 计算资源使用的标准差
        import numpy as np

        std_cpu = np.std(cpu_usages)
        std_memory = np.std(memory_usages)
        std_disk = np.std(disk_usages)

        # 动态调整阈值
        # 阈值 = 平均值 + 2 * 标准差，但不超过最大阈值
        new_cpu_threshold = min(90.0, avg_cpu + 2 * std_cpu)
        new_memory_threshold = min(85.0, avg_memory + 2 * std_memory)
        new_disk_threshold = min(95.0, avg_disk + 2 * std_disk)

        # 只在阈值变化较大时更新
        if abs(new_cpu_threshold - self.cpu_threshold) > 5:
            self.cpu_threshold = new_cpu_threshold
            logger.info(f"自动调整CPU阈值: {new_cpu_threshold:.1f}%")

        if abs(new_memory_threshold - self.memory_threshold) > 5:
            self.memory_threshold = new_memory_threshold
            logger.info(f"自动调整内存阈值: {new_memory_threshold:.1f}%")

        if abs(new_disk_threshold - self.disk_threshold) > 5:
            self.disk_threshold = new_disk_threshold
            logger.info(f"自动调整磁盘阈值: {new_disk_threshold:.1f}%")

    def get_optimal_workers(self) -> int:
        """获取最优的并行工作线程数

        Returns:
            int: 最优的并行工作线程数
        """
        usage = self.get_resource_usage()
        cpu_count = usage["cpu"]["count"]
        cpu_percent = usage["cpu"]["percent"]
        memory_percent = usage["memory"]["percent"]

        # 基于CPU和内存使用情况计算最优工作线程数
        available_cpu = cpu_count * (1 - cpu_percent / 100)
        available_memory = 1 - memory_percent / 100

        # 取两者的最小值，确保不会过度使用资源
        optimal_workers = max(1, int(min(available_cpu, available_memory * cpu_count)))

        # 考虑GPU使用情况（如果可用）
        if "gpu" in usage and usage["gpu"]["count"] > 0:
            # 如果有GPU，减少CPU工作线程数，为GPU留出资源
            optimal_workers = max(1, optimal_workers // 2)

        return optimal_workers

    def suggest_batch_size(self, base_batch_size: int = 32, model_type: str = "default") -> int:
        """根据资源使用情况建议批处理大小

        Args:
            base_batch_size: 基础批处理大小
            model_type: 模型类型 ('default', 'deep_learning', 'lightweight')

        Returns:
            int: 建议的批处理大小
        """
        usage = self.get_resource_usage()
        memory_percent = usage["memory"]["percent"]

        # 根据模型类型调整基础批处理大小
        if model_type == "deep_learning":
            base_batch_size = max(8, base_batch_size)
        elif model_type == "lightweight":
            base_batch_size = min(64, base_batch_size * 2)

        # 根据内存使用情况调整批处理大小
        if memory_percent > 75:
            # 内存使用较高，减小批处理大小
            return max(4, base_batch_size // 2)
        elif memory_percent > 60:
            # 内存使用适中，使用基础批处理大小
            return base_batch_size
        else:
            # 内存使用较低，可以增大批处理大小
            return min(256, base_batch_size * 2)

        # 考虑GPU使用情况（如果可用）
        if "gpu" in usage and usage["gpu"]["count"] > 0:
            gpu_usage = usage["gpu"]["usage"][0]["percent"]
            if gpu_usage > 80:
                return max(4, base_batch_size // 2)
            elif gpu_usage > 50:
                return base_batch_size
            else:
                return min(256, base_batch_size * 2)

    def should_scale_down(self) -> bool:
        """判断是否需要缩减资源使用

        Returns:
            bool: 是否需要缩减资源使用
        """
        usage = self.get_resource_usage()

        # 检查CPU、内存、磁盘是否超过阈值
        if usage["cpu"]["over_threshold"] or usage["memory"]["over_threshold"] or usage["disk"]["over_threshold"]:
            return True

        # 检查GPU使用情况（如果可用）
        if "gpu" in usage:
            for gpu in usage["gpu"]["usage"]:
                if gpu["percent"] > 90:
                    return True

        return False

    def get_resource_summary(self) -> str:
        """获取资源使用摘要

        Returns:
            str: 资源使用摘要
        """
        usage = self.get_resource_usage()
        summary = (
            f"CPU: {usage['cpu']['percent']:.1f}% (阈值: {self.cpu_threshold:.1f}%) | "
            f"内存: {usage['memory']['percent']:.1f}% (阈值: {self.memory_threshold:.1f}%) | "
            f"磁盘: {usage['disk']['percent']:.1f}% (阈值: {self.disk_threshold:.1f}%)"
        )

        # 添加GPU使用情况（如果可用）
        if "gpu" in usage:
            gpu_summary = []
            for gpu in usage["gpu"]["usage"]:
                gpu_summary.append(f"GPU{gpu['id']}: {gpu['percent']:.1f}%")
            if gpu_summary:
                summary += " | " + " ".join(gpu_summary)

        return summary

    def get_resource_trend(self, window: int = 30) -> Dict[str, Any]:
        """获取资源使用趋势

        Args:
            window: 时间窗口大小

        Returns:
            Dict: 资源使用趋势
        """
        if len(self.resource_history) < window:
            window = len(self.resource_history)

        recent_history = self.resource_history[-window:]

        # 计算趋势
        cpu_trend = [h["cpu"]["percent"] for h in recent_history]
        memory_trend = [h["memory"]["percent"] for h in recent_history]
        disk_trend = [h["disk"]["percent"] for h in recent_history]
        timestamps = [h["timestamp"] for h in recent_history]

        # 计算趋势斜率
        import numpy as np

        x = np.arange(len(cpu_trend))
        cpu_slope = np.polyfit(x, cpu_trend, 1)[0]
        memory_slope = np.polyfit(x, memory_trend, 1)[0]
        disk_slope = np.polyfit(x, disk_trend, 1)[0]

        return {
            "timestamps": timestamps,
            "cpu_trend": cpu_trend,
            "memory_trend": memory_trend,
            "disk_trend": disk_trend,
            "cpu_slope": cpu_slope,
            "memory_slope": memory_slope,
            "disk_slope": disk_slope,
        }

    def predict_resource_usage(self, minutes: int = 5) -> Dict[str, Any]:
        """预测未来资源使用情况

        Args:
            minutes: 预测时间（分钟）

        Returns:
            Dict: 预测的资源使用情况
        """
        if len(self.resource_history) < 10:
            return self.get_resource_usage()

        # 获取资源使用趋势
        trend = self.get_resource_trend()

        # 预测未来资源使用情况
        current_cpu = trend["cpu_trend"][-1]
        current_memory = trend["memory_trend"][-1]
        current_disk = trend["disk_trend"][-1]

        # 计算预测值
        predicted_cpu = current_cpu + trend["cpu_slope"] * minutes
        predicted_memory = current_memory + trend["memory_slope"] * minutes
        predicted_disk = current_disk + trend["disk_slope"] * minutes

        # 确保预测值在合理范围内
        predicted_cpu = max(0, min(100, predicted_cpu))
        predicted_memory = max(0, min(100, predicted_memory))
        predicted_disk = max(0, min(100, predicted_disk))

        return {
            "predicted_cpu": predicted_cpu,
            "predicted_memory": predicted_memory,
            "predicted_disk": predicted_disk,
            "prediction_time": minutes,
            "current_time": datetime.now().isoformat(),
        }


# 全局资源管理器实例
resource_manager = ResourceManager()


def get_resource_manager() -> ResourceManager:
    """获取资源管理器实例

    Returns:
        ResourceManager: 资源管理器实例
    """
    return resource_manager


def check_system_resources() -> bool:
    """检查系统资源

    Returns:
        bool: 是否所有资源都在安全范围内
    """
    return resource_manager.check_resources()


def get_optimal_workers() -> int:
    """获取最优的并行工作线程数

    Returns:
        int: 最优的并行工作线程数
    """
    return resource_manager.get_optimal_workers()


def suggest_batch_size(base_batch_size: int = 32) -> int:
    """根据资源使用情况建议批处理大小

    Args:
        base_batch_size: 基础批处理大小

    Returns:
        int: 建议的批处理大小
    """
    return resource_manager.suggest_batch_size(base_batch_size)


def get_resource_summary() -> str:
    """获取资源使用摘要

    Returns:
        str: 资源使用摘要
    """
    return resource_manager.get_resource_summary()
