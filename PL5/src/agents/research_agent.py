"""
研究分析智能体 - 自动分析历史数据发现新规律
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentTask, AgentResult
from src.core.knowledge.rag_system import PL5KnowledgeRAG
from src.core.utils import logger


class ResearchAgent(BaseAgent):
    """
    研究分析智能体

    功能：
    1. 自动分析历史开奖数据，发现新的模式和规律
    2. 基于统计分析和机器学习方法识别异常模式
    3. 生成数据驱动的研究报告
    4. 与其他智能体协作，提供数据洞察
    """

    def __init__(self, max_workers: int = 4):
        super().__init__("ResearchAgent", max_workers)
        self.rag_system = PL5KnowledgeRAG()
        self.analysis_history = []

    async def analyze_historical_patterns(self, df: pd.DataFrame, feature_cols: List[str]) -> Dict[str, Any]:
        """分析历史模式

        Args:
            df: 包含历史开奖数据的DataFrame
            feature_cols: 特征列名列表

        Returns:
            分析结果
        """
        logger.info("[ResearchAgent] 开始分析历史开奖模式...")

        analysis_result = {
            "basic_statistics": await self._analyze_basic_statistics(df),
            "pattern_analysis": await self._analyze_patterns(df),
            "anomaly_detection": await self._detect_anomalies(df),
            "trend_analysis": await self._analyze_trends(df),
            "correlation_analysis": await self._analyze_correlations(df),
            "timestamp": datetime.now().isoformat(),
        }

        # 保存分析历史
        self.analysis_history.append(analysis_result)

        logger.info("[ResearchAgent] 历史模式分析完成")
        return analysis_result

    async def _analyze_basic_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析基本统计信息

        Args:
            df: 数据

        Returns:
            统计信息
        """
        positions = ["wan", "qian", "bai", "shi", "ge"]
        stats = {}

        for pos in positions:
            pos_data = df[pos].values
            stats[pos] = {
                "mean": float(np.mean(pos_data)),
                "std": float(np.std(pos_data)),
                "min": int(np.min(pos_data)),
                "max": int(np.max(pos_data)),
                "median": float(np.median(pos_data)),
                "mode": int(np.bincount(pos_data).argmax()),
            }

        return stats

    async def _analyze_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析模式

        Args:
            df: 数据

        Returns:
            模式分析结果
        """
        patterns = {
            "consecutive_patterns": await self._detect_consecutive_patterns(df),
            "repeat_patterns": await self._detect_repeat_patterns(df),
            "alternating_patterns": await self._detect_alternating_patterns(df),
            "trend_patterns": await self._detect_trend_patterns(df),
        }

        return patterns

    async def _detect_consecutive_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """检测连续模式

        Args:
            df: 数据

        Returns:
            连续模式分析
        """
        positions = ["wan", "qian", "bai", "shi", "ge"]
        consecutive_patterns = {}

        for pos in positions:
            data = df[pos].values
            max_consecutive = 1
            current_consecutive = 1

            for i in range(1, len(data)):
                if data[i] == data[i - 1]:
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 1

            consecutive_patterns[pos] = {
                "max_consecutive": max_consecutive,
                "consecutive_count": self._count_consecutive(data),
            }

        return consecutive_patterns

    def _count_consecutive(self, data: np.ndarray) -> int:
        """统计连续出现的次数

        Args:
            data: 数据

        Returns:
            连续出现的总次数
        """
        count = 0
        current_consecutive = 1

        for i in range(1, len(data)):
            if data[i] == data[i - 1]:
                current_consecutive += 1
            else:
                if current_consecutive > 1:
                    count += 1
                current_consecutive = 1

        if current_consecutive > 1:
            count += 1

        return count

    async def _detect_repeat_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """检测重复模式

        Args:
            df: 数据

        Returns:
            重复模式分析
        """
        positions = ["wan", "qian", "bai", "shi", "ge"]
        repeat_patterns = {}

        for pos in positions:
            data = df[pos].values
            value_counts = np.bincount(data)
            most_common_value = np.argmax(value_counts)
            most_common_count = value_counts[most_common_value]

            repeat_patterns[pos] = {
                "most_common_value": int(most_common_value),
                "most_common_count": int(most_common_count),
                "repeat_ratio": float(most_common_count / len(data)),
            }

        return repeat_patterns

    async def _detect_alternating_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """检测交替模式

        Args:
            df: 数据

        Returns:
            交替模式分析
        """
        positions = ["wan", "qian", "bai", "shi", "ge"]
        alternating_patterns = {}

        for pos in positions:
            data = df[pos].values
            alternating_count = 0

            for i in range(2, len(data)):
                if data[i] == data[i - 2] and data[i] != data[i - 1]:
                    alternating_count += 1

            alternating_patterns[pos] = {
                "alternating_count": alternating_count,
                "alternating_ratio": float(alternating_count / (len(data) - 2)) if len(data) > 2 else 0.0,
            }

        return alternating_patterns

    async def _detect_trend_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """检测趋势模式

        Args:
            df: 数据

        Returns:
            趋势模式分析
        """
        positions = ["wan", "qian", "bai", "shi", "ge"]
        trend_patterns = {}

        for pos in positions:
            data = df[pos].values
            increasing_count = 0
            decreasing_count = 0

            for i in range(1, len(data)):
                if data[i] > data[i - 1]:
                    increasing_count += 1
                elif data[i] < data[i - 1]:
                    decreasing_count += 1

            trend_patterns[pos] = {
                "increasing_count": increasing_count,
                "decreasing_count": decreasing_count,
                "trend_bias": float((increasing_count - decreasing_count) / (len(data) - 1)) if len(data) > 1 else 0.0,
            }

        return trend_patterns

    async def _detect_anomalies(self, df: pd.DataFrame) -> Dict[str, Any]:
        """检测异常

        Args:
            df: 数据

        Returns:
            异常检测结果
        """
        positions = ["wan", "qian", "bai", "shi", "ge"]
        anomalies = {}

        for pos in positions:
            data = df[pos].values
            mean = np.mean(data)
            std = np.std(data)
            threshold = 2.0  # 2倍标准差

            anomaly_indices = np.where(np.abs(data - mean) > threshold * std)[0]
            anomaly_values = data[anomaly_indices]

            anomalies[pos] = {
                "anomaly_count": len(anomaly_indices),
                "anomaly_indices": anomaly_indices.tolist(),
                "anomaly_values": anomaly_values.tolist(),
                "anomaly_ratio": float(len(anomaly_indices) / len(data)),
            }

        return anomalies

    async def _analyze_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析趋势

        Args:
            df: 数据

        Returns:
            趋势分析结果
        """
        positions = ["wan", "qian", "bai", "shi", "ge"]
        trends = {}

        for pos in positions:
            data = df[pos].values
            # 简单线性回归计算趋势
            x = np.arange(len(data))
            slope = np.polyfit(x, data, 1)[0]

            trends[pos] = {
                "trend_slope": float(slope),
                "trend_direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
            }

        return trends

    async def _analyze_correlations(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析位置间相关性

        Args:
            df: 数据

        Returns:
            相关性分析结果
        """
        positions = ["wan", "qian", "bai", "shi", "ge"]
        correlations = {}

        for i, pos1 in enumerate(positions):
            for j, pos2 in enumerate(positions):
                if i < j:
                    correlation = np.corrcoef(df[pos1], df[pos2])[0, 1]
                    correlations[f"{pos1}_{pos2}"] = float(correlation)

        return correlations

    async def generate_research_report(self, analysis_result: Dict[str, Any]) -> str:
        """生成研究报告

        Args:
            analysis_result: 分析结果

        Returns:
            研究报告文本
        """
        report_parts = []
        report_parts.append(f"# 排列五研究分析报告")
        report_parts.append(f"生成时间: {analysis_result['timestamp']}")
        report_parts.append("")

        # 基本统计
        report_parts.append("## 基本统计信息")
        for pos, stats in analysis_result["basic_statistics"].items():
            report_parts.append(
                f"- {pos}位: 均值={stats['mean']:.2f}, 标准差={stats['std']:.2f}, 范围={stats['min']}-{stats['max']}, 众数={stats['mode']}"
            )
        report_parts.append("")

        # 模式分析
        report_parts.append("## 模式分析")
        for pattern_type, patterns in analysis_result["pattern_analysis"].items():
            report_parts.append(f"### {pattern_type}")
            for pos, pattern in patterns.items():
                report_parts.append(f"- {pos}位: {pattern}")
            report_parts.append("")

        # 异常检测
        report_parts.append("## 异常检测")
        for pos, anomaly in analysis_result["anomaly_detection"].items():
            report_parts.append(
                f"- {pos}位: 异常数量={anomaly['anomaly_count']}, 异常比例={anomaly['anomaly_ratio']:.2f}"
            )
        report_parts.append("")

        # 趋势分析
        report_parts.append("## 趋势分析")
        for pos, trend in analysis_result["trend_analysis"].items():
            report_parts.append(f"- {pos}位: 趋势={trend['trend_direction']}, 斜率={trend['trend_slope']:.4f}")
        report_parts.append("")

        # 相关性分析
        report_parts.append("## 相关性分析")
        sorted_correlations = sorted(
            analysis_result["correlation_analysis"].items(), key=lambda x: abs(x[1]), reverse=True
        )
        for pair, corr in sorted_correlations[:5]:
            report_parts.append(f"- {pair}: {corr:.4f}")

        return "\n".join(report_parts)

    def get_analysis_history(self) -> List[Dict[str, Any]]:
        """获取分析历史

        Returns:
            分析历史列表
        """
        return self.analysis_history

    def clear_history(self):
        """清空分析历史"""
        self.analysis_history = []
        logger.info("[ResearchAgent] 分析历史已清空")

    def shutdown(self):
        """关闭智能体"""
        self.clear_history()
        super().shutdown()
        logger.info("[ResearchAgent] 智能体已关闭")

    async def execute(self, task: AgentTask) -> AgentResult:
        """执行智能体任务"""
        start_time = datetime.now()

        try:
            if task.task_type == "analyze_patterns":
                result = await self.analyze_historical_patterns(
                    task.params.get("data"), task.params.get("feature_cols", [])
                )
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data=result,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
            elif task.task_type == "generate_report":
                report = await self.generate_research_report(task.params.get("analysis_result"))
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"report": report},
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
            else:
                return AgentResult(
                    task_id=task.task_id,
                    success=False,
                    data={},
                    execution_time=(datetime.now() - start_time).total_seconds(),
                    error_message=f"Unknown task type: {task.task_type}",
                )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                success=False,
                data={},
                execution_time=(datetime.now() - start_time).total_seconds(),
                error_message=str(e),
            )

    def validate(self, task: AgentTask) -> bool:
        """验证任务参数是否合法"""
        required_params = {"analyze_patterns": ["data"], "generate_report": ["analysis_result"]}

        task_type = task.task_type
        if task_type not in required_params:
            return False

        params = task.params
        for param in required_params[task_type]:
            if param not in params:
                return False

        return True

    def get_capabilities(self) -> Dict[str, Any]:
        """获取智能体能力描述"""
        return {
            "name": self.name,
            "description": "历史数据模式分析、异常检测、研究报告生成",
            "supported_tasks": ["analyze_patterns", "generate_report"],
            "analysis_support": True,
            "report_support": True,
        }
