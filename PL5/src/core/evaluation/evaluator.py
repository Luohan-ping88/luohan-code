"""
预测结果评估模块
用于智能自主评估预测结果，并提供详细的评估报告
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class PredictionEvaluator:
    """预测结果评估器"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent / "config.json"
        self.config = self._load_config()
        self.evaluation_history = []
        self.history_path = Path(__file__).parent / "evaluation_history.json"
        self._load_history()

    def _load_config(self) -> Dict[str, Any]:
        """加载评估配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载评估配置失败: {e}")

        # 默认配置
        return {
            "top_k_values": [3, 5, 8],
            "evaluation_metrics": ["accuracy", "hit_rate", "confidence"],
            "history_size": 100,
        }

    def _load_history(self) -> None:
        """加载评估历史"""
        if self.history_path.exists():
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 验证JSON格式
                if not content.strip():
                    # 空文件，初始化为空列表
                    self.evaluation_history = []
                    logger.info("评估历史文件为空，初始化为空列表")
                    return

                # 尝试解析JSON
                try:
                    self.evaluation_history = json.loads(content)
                    # 验证数据类型
                    if not isinstance(self.evaluation_history, list):
                        raise ValueError("评估历史数据必须是列表格式")
                    logger.info(f"加载评估历史成功，共 {len(self.evaluation_history)} 条记录")
                except json.JSONDecodeError as e:
                    logger.error(f"评估历史文件JSON格式错误: {e}")
                    # 重置为空列表
                    self.evaluation_history = []
                    # 尝试修复文件
                    self._save_history()
                    logger.info("已修复评估历史文件，重置为空列表")
                except Exception as e:
                    logger.error(f"加载评估历史失败: {e}")
                    # 重置为空列表
                    self.evaluation_history = []
            except Exception as e:
                logger.error(f"读取评估历史文件失败: {e}")
                # 重置为空列表
                self.evaluation_history = []
        else:
            # 文件不存在，初始化为空列表
            self.evaluation_history = []
            logger.info("评估历史文件不存在，初始化为空列表")
            # 创建空文件
            self._save_history()
            logger.info("已创建评估历史文件")

    def _save_history(self) -> None:
        """保存评估历史"""
        try:
            # 限制历史记录数量
            if len(self.evaluation_history) > self.config.get("history_size", 100):
                self.evaluation_history = self.evaluation_history[-self.config["history_size"] :]

            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.evaluation_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存评估历史失败: {e}")

    def evaluate_predictions(self, actual: Dict[str, int], predictions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """评估预测结果

        Args:
            actual: 实际开奖号码
            predictions: 预测结果

        Returns:
            Dict[str, Any]: 评估结果
        """
        try:
            evaluation = {
                "timestamp": datetime.now().isoformat(),
                "actual": actual,
                "predictions": predictions,
                "metrics": {},
                "detailed_metrics": {},
                "summary": {},
            }

            # 计算每个位置的评估指标
            position_metrics = {}
            for pos in ["wan", "qian", "bai", "shi", "ge"]:
                if pos in actual and pos in predictions:
                    actual_digit = actual[pos]
                    pred_top_k = predictions[pos].get("top_k", [])
                    pred_probs = predictions[pos].get("probabilities", [])

                    # 计算每个top_k的命中率
                    position_metrics[pos] = {}
                    for k in self.config.get("top_k_values", [3, 5, 8]):
                        if len(pred_top_k) >= k:
                            hit = actual_digit in pred_top_k[:k]
                            position_metrics[pos][f"hit_top_{k}"] = hit

                            # 计算置信度
                            if hit and len(pred_probs) >= k:
                                # 找到实际数字在预测中的位置
                                idx = pred_top_k[:k].index(actual_digit)
                                confidence = pred_probs[idx] if idx < len(pred_probs) else 0.0
                                position_metrics[pos][f"confidence_top_{k}"] = confidence

            evaluation["detailed_metrics"] = position_metrics

            # 计算整体评估指标
            overall_metrics = {}
            for k in self.config.get("top_k_values", [3, 5, 8]):
                hits = 0
                total = 0
                total_confidence = 0
                hit_confidence = 0

                for pos, metrics in position_metrics.items():
                    if f"hit_top_{k}" in metrics:
                        total += 1
                        if metrics[f"hit_top_{k}"]:
                            hits += 1
                            if f"confidence_top_{k}" in metrics:
                                hit_confidence += metrics[f"confidence_top_{k}"]
                    if f"confidence_top_{k}" in metrics:
                        total_confidence += metrics[f"confidence_top_{k}"]

                overall_metrics[f"accuracy_top_{k}"] = hits / total if total > 0 else 0.0
                overall_metrics[f"hit_rate_top_{k}"] = hits / total if total > 0 else 0.0
                overall_metrics[f"average_confidence_top_{k}"] = total_confidence / total if total > 0 else 0.0
                overall_metrics[f"average_hit_confidence_top_{k}"] = hit_confidence / hits if hits > 0 else 0.0

            evaluation["metrics"] = overall_metrics

            # 生成评估摘要
            summary = {
                "total_positions": len(position_metrics),
                "total_hits": sum(1 for pos, metrics in position_metrics.items() if metrics.get("hit_top_3", False)),
                "best_accuracy": max(overall_metrics.values()) if overall_metrics else 0.0,
                "worst_accuracy": min(overall_metrics.values()) if overall_metrics else 0.0,
                "average_accuracy": np.mean(list(overall_metrics.values())) if overall_metrics else 0.0,
            }

            evaluation["summary"] = summary

            # 生成评估报告
            evaluation["report"] = self._generate_evaluation_report(evaluation)

            # 保存评估历史
            self.evaluation_history.append(evaluation)
            self._save_history()

            logger.info(f"预测结果评估完成，准确率: {overall_metrics.get('accuracy_top_3', 0.0):.4f}")

            return evaluation

        except Exception as e:
            logger.error(f"评估预测结果失败: {e}")
            return {"success": False, "error": str(e)}

    def _generate_evaluation_report(self, evaluation: Dict[str, Any]) -> str:
        """生成评估报告

        Args:
            evaluation: 评估结果

        Returns:
            str: 评估报告
        """
        # 提取评估信息
        timestamp = evaluation.get("timestamp", "")
        actual = evaluation.get("actual", {})
        predictions = evaluation.get("predictions", {})
        metrics = evaluation.get("metrics", {})
        detailed_metrics = evaluation.get("detailed_metrics", {})
        summary = evaluation.get("summary", {})

        # 构建HTML内容
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>PL5 预测结果评估报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                h1 {{ color: #333; }}
                h2 {{ color: #555; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .section {{ margin-bottom: 20px; }}
                .success {{ color: green; }}
                .warning {{ color: orange; }}
                .error {{ color: red; }}
                .hit {{ background-color: #d4edda; }}
                .miss {{ background-color: #f8d7da; }}
            </style>
        </head>
        <body>
            <h1>PL5 预测结果评估报告</h1>
            <p>生成时间: {timestamp}</p>
            
            <div class="section">
                <h2>1. 实际开奖号码</h2>
                <table>
                    <tr>
                        <th>位置</th>
                        <th>实际号码</th>
                    </tr>
                    {self._generate_actual_table(actual)}
                </table>
            </div>
            
            <div class="section">
                <h2>2. 预测结果评估</h2>
                <table>
                    <tr>
                        <th>评估指标</th>
                        <th>值</th>
                    </tr>
                    {self._generate_metrics_table(metrics)}
                </table>
            </div>
            
            <div class="section">
                <h2>3. 详细评估</h2>
                <table>
                    <tr>
                        <th>位置</th>
                        <th>Top 3 命中</th>
                        <th>Top 5 命中</th>
                        <th>Top 8 命中</th>
                    </tr>
                    {self._generate_detailed_table(detailed_metrics)}
                </table>
            </div>
            
            <div class="section">
                <h2>4. 评估摘要</h2>
                <table>
                    <tr>
                        <th>项目</th>
                        <th>值</th>
                    </tr>
                    <tr>
                        <td>总位置数</td>
                        <td>{summary.get('total_positions', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td>总命中数</td>
                        <td>{summary.get('total_hits', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td>最佳准确率</td>
                        <td>{summary.get('best_accuracy', 'N/A'):.4f}</td>
                    </tr>
                    <tr>
                        <td>最差准确率</td>
                        <td>{summary.get('worst_accuracy', 'N/A'):.4f}</td>
                    </tr>
                    <tr>
                        <td>平均准确率</td>
                        <td>{summary.get('average_accuracy', 'N/A'):.4f}</td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <h2>5. 系统信息</h2>
                <p>此报告由 PL5 预测系统自动生成，请勿直接回复。</p>
            </div>
        </body>
        </html>
        """

        return html

    def _generate_actual_table(self, actual: Dict[str, int]) -> str:
        """生成实际号码表格

        Args:
            actual: 实际开奖号码

        Returns:
            str: HTML表格
        """
        rows = []
        positions = ["wan", "qian", "bai", "shi", "ge"]
        pos_names = {"wan": "万位", "qian": "千位", "bai": "百位", "shi": "十位", "ge": "个位"}

        for pos in positions:
            if pos in actual:
                rows.append(f"<tr><td>{pos_names.get(pos, pos)}</td><td>{actual[pos]}</td></tr>")

        return "\n".join(rows)

    def _generate_metrics_table(self, metrics: Dict[str, float]) -> str:
        """生成评估指标表格

        Args:
            metrics: 评估指标

        Returns:
            str: HTML表格
        """
        rows = []

        for key, value in metrics.items():
            rows.append(f"<tr><td>{key}</td><td>{value:.4f}</td></tr>")

        return "\n".join(rows)

    def _generate_detailed_table(self, detailed_metrics: Dict[str, Dict[str, Any]]) -> str:
        """生成详细评估表格

        Args:
            detailed_metrics: 详细评估指标

        Returns:
            str: HTML表格
        """
        rows = []
        positions = ["wan", "qian", "bai", "shi", "ge"]
        pos_names = {"wan": "万位", "qian": "千位", "bai": "百位", "shi": "十位", "ge": "个位"}

        for pos in positions:
            if pos in detailed_metrics:
                metrics = detailed_metrics[pos]
                row = f"<tr><td>{pos_names.get(pos, pos)}</td>"

                for k in [3, 5, 8]:
                    hit = metrics.get(f"hit_top_{k}", False)
                    class_name = "hit" if hit else "miss"
                    row += f"<td class='{class_name}'>{'✓' if hit else '✗'}</td>"

                row += "</tr>"
                rows.append(row)

        return "\n".join(rows)

    def get_evaluation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取评估历史

        Args:
            limit: 返回记录数限制

        Returns:
            List[Dict[str, Any]]: 评估历史
        """
        return self.evaluation_history[-limit:]

    def get_evaluation_statistics(self) -> Dict[str, Any]:
        """获取评估统计信息

        Returns:
            Dict[str, Any]: 评估统计信息
        """
        if not self.evaluation_history:
            return {
                "total_evaluations": 0,
                "average_accuracy": 0.0,
                "best_accuracy": 0.0,
                "worst_accuracy": 0.0,
                "accuracy_trend": "N/A",
            }

        # 计算统计信息
        accuracies = []
        for eval_record in self.evaluation_history:
            metrics = eval_record.get("metrics", {})
            if "accuracy_top_3" in metrics:
                accuracies.append(metrics["accuracy_top_3"])

        if accuracies:
            return {
                "total_evaluations": len(self.evaluation_history),
                "average_accuracy": np.mean(accuracies),
                "best_accuracy": np.max(accuracies),
                "worst_accuracy": np.min(accuracies),
                "accuracy_trend": self._calculate_trend(accuracies),
            }
        else:
            return {
                "total_evaluations": len(self.evaluation_history),
                "average_accuracy": 0.0,
                "best_accuracy": 0.0,
                "worst_accuracy": 0.0,
                "accuracy_trend": "N/A",
            }

    def _calculate_trend(self, values: List[float]) -> str:
        """计算趋势

        Args:
            values: 值列表

        Returns:
            str: 趋势
        """
        if len(values) < 3:
            return "Insufficient data"

        # 计算线性回归斜率
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]

        if slope > 0.01:
            return "Improving"
        elif slope < -0.01:
            return "Declining"
        else:
            return "Stable"
