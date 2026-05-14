#!/usr/bin/env python3
"""
强化的反馈学习模块 V10.0
多步骤分析策略导致命中率低的原因，重点优化8码命中率
"""

import json
import logging
from typing import Dict, List
from datetime import datetime

from src.core.config import MODELS_DIR, LOGS_DIR
from src.core.data.collector import PL5DataCollector
from src.core.models.enhanced_predictor import EnhancedPL5Predictor

logger = logging.getLogger(__name__)

_FEEDBACK_HISTORY_PATH = MODELS_DIR / "feedback_learning_history.json"
_PREDICTION_HISTORY_PATH = MODELS_DIR / "prediction_history.json"


class FeedbackAnalyzer:
    """反馈分析器 - 分析策略导致命中率低的原因"""

    def __init__(self):
        self.collector = PL5DataCollector()
        self.predictor = EnhancedPL5Predictor()
        self.feedback_history = self._load_feedback_history()
        self.prediction_history = self._load_prediction_history()

    def _load_feedback_history(self) -> List[Dict]:
        """加载反馈学习历史"""
        try:
            if _FEEDBACK_HISTORY_PATH.exists():
                with open(_FEEDBACK_HISTORY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载反馈学习历史失败: {e}")
        return []

    def _load_prediction_history(self) -> List[Dict]:
        """加载预测历史"""
        try:
            if _PREDICTION_HISTORY_PATH.exists():
                with open(
                    _PREDICTION_HISTORY_PATH, "r", encoding="utf-8"
                ) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载预测历史失败: {e}")
        return []

    def _save_feedback_history(self):
        """保存反馈学习历史"""
        try:
            with open(_FEEDBACK_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    self.feedback_history, f, indent=2, ensure_ascii=False
                )
        except Exception as e:
            logger.error(f"保存反馈学习历史失败: {e}")

    def _save_prediction_history(self):
        """保存预测历史"""
        try:
            with open(_PREDICTION_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    self.prediction_history, f, indent=2, ensure_ascii=False
                )
        except Exception as e:
            logger.error(f"保存预测历史失败: {e}")

    def analyze_strategy_performance(self, window_size: int = 20) -> Dict:
        """分析策略性能，重点关注8码命中率"""
        logger.info(f"开始分析策略性能，窗口大小: {window_size}期")

        # 加载历史数据
        df = self.collector.load_processed_data()
        if len(df) < window_size:
            logger.warning(f"数据量不足，使用所有可用数据: {len(df)}期")
            window_size = len(df)

        # 分析预测历史
        recent_predictions = (
            self.prediction_history[-window_size:]
            if len(self.prediction_history) >= window_size
            else self.prediction_history
        )

        # 计算各个位置的命中率
        position_analysis = {}
        position_names = ["wan", "qian", "bai", "shi", "ge"]

        for pos in position_names:
            analysis = self._analyze_position_performance(
                pos, recent_predictions, df
            )
            position_analysis[pos] = analysis

        # 计算总体性能
        overall_analysis = self._calculate_overall_performance(
            position_analysis
        )

        # 分析策略问题
        strategy_issues = self._identify_strategy_issues(
            position_analysis, overall_analysis
        )

        # 生成改进建议
        improvement_suggestions = self._generate_improvement_suggestions(
            strategy_issues, position_analysis
        )

        analysis_result = {
            "timestamp": datetime.now().isoformat(),
            "window_size": window_size,
            "position_analysis": position_analysis,
            "overall_analysis": overall_analysis,
            "strategy_issues": strategy_issues,
            "improvement_suggestions": improvement_suggestions,
        }

        # 保存到历史
        self.feedback_history.append(analysis_result)
        if len(self.feedback_history) > 20:
            self.feedback_history = self.feedback_history[-20:]
        self._save_feedback_history()

        return analysis_result

    def _analyze_position_performance(
        self, position: str, predictions: List[Dict], df
    ) -> Dict:
        """分析单个位置的性能"""
        top1_hits = 0
        top3_hits = 0
        top5_hits = 0
        top8_hits = 0
        total_tests = 0

        for pred in predictions:
            if "predictions" in pred and position in pred["predictions"]:
                pred_data = pred["predictions"][position]
                period = pred.get("period")

                # 查找实际开奖号码
                actual_row = df[df["period"] == period]
                if not actual_row.empty:
                    actual_value = actual_row[position].iloc[0]
                    total_tests += 1

                    if "top_k" in pred_data:
                        top_k = pred_data["top_k"]
                        if actual_value in top_k[:1]:
                            top1_hits += 1
                        if actual_value in top_k[:3]:
                            top3_hits += 1
                        if actual_value in top_k[:5]:
                            top5_hits += 1
                        if actual_value in top_k[:8]:
                            top8_hits += 1

        return {
            "top1_hits": top1_hits,
            "top3_hits": top3_hits,
            "top5_hits": top5_hits,
            "top8_hits": top8_hits,
            "total_tests": total_tests,
            "top1_accuracy": top1_hits / total_tests if total_tests > 0 else 0,
            "top3_accuracy": top3_hits / total_tests if total_tests > 0 else 0,
            "top5_accuracy": top5_hits / total_tests if total_tests > 0 else 0,
            "top8_accuracy": top8_hits / total_tests if total_tests > 0 else 0,
        }

    def _calculate_overall_performance(self, position_analysis: Dict) -> Dict:
        """计算总体性能"""
        total_top1_hits = 0
        total_top3_hits = 0
        total_top5_hits = 0
        total_top8_hits = 0
        total_tests = 0

        for pos, analysis in position_analysis.items():
            total_top1_hits += analysis["top1_hits"]
            total_top3_hits += analysis["top3_hits"]
            total_top5_hits += analysis["top5_hits"]
            total_top8_hits += analysis["top8_hits"]
            total_tests += analysis["total_tests"]

        return {
            "top1_accuracy": (
                total_top1_hits / total_tests if total_tests > 0 else 0
            ),
            "top3_accuracy": (
                total_top3_hits / total_tests if total_tests > 0 else 0
            ),
            "top5_accuracy": (
                total_top5_hits / total_tests if total_tests > 0 else 0
            ),
            "top8_accuracy": (
                total_top8_hits / total_tests if total_tests > 0 else 0
            ),
            "total_tests": total_tests,
        }

    def _identify_strategy_issues(
        self, position_analysis: Dict, overall_analysis: Dict
    ) -> List[Dict]:
        """识别策略问题"""
        issues = []

        # 目标值设置
        TARGET_TOP8 = 0.95  # 8码命中率目标
        TARGET_TOP5 = 0.70  # 5码命中率目标
        TARGET_TOP3 = 0.50  # 3码命中率目标

        # 8码命中率分析
        overall_top8 = overall_analysis["top8_accuracy"]
        if overall_top8 < TARGET_TOP8:
            severity = "high" if overall_top8 < TARGET_TOP8 * 0.8 else "medium"
            issues.append(
                {
                    "severity": severity,
                    "category": "overall_performance",
                    "description": f"8码总体命中率未达到目标: {overall_top8:.4f} (目标: {TARGET_TOP8:.2f})",
                    "threshold": TARGET_TOP8,
                    "current_value": overall_top8,
                    "gap": TARGET_TOP8 - overall_top8,
                    "possible_causes": [
                        "特征工程不足，缺少关键特征",
                        "模型权重配置不合理",
                        "集成策略不当",
                        "阈值设置过于严格",
                        "模型选择不适合8码预测",
                    ],
                }
            )

        # 5码命中率分析
        overall_top5 = overall_analysis["top5_accuracy"]
        if overall_top5 < TARGET_TOP5:
            severity = "high" if overall_top5 < TARGET_TOP5 * 0.8 else "medium"
            issues.append(
                {
                    "severity": severity,
                    "category": "overall_performance",
                    "description": f"5码总体命中率未达到目标: {overall_top5:.4f} (目标: {TARGET_TOP5:.2f})",
                    "threshold": TARGET_TOP5,
                    "current_value": overall_top5,
                    "gap": TARGET_TOP5 - overall_top5,
                    "possible_causes": [
                        "5码预测策略不当",
                        "模型权重配置不合理",
                        "阈值设置不合适",
                    ],
                }
            )

        # 3码命中率分析
        overall_top3 = overall_analysis["top3_accuracy"]
        if overall_top3 < TARGET_TOP3:
            severity = "high" if overall_top3 < TARGET_TOP3 * 0.8 else "medium"
            issues.append(
                {
                    "severity": severity,
                    "category": "overall_performance",
                    "description": f"3码总体命中率未达到目标: {overall_top3:.4f} (目标: {TARGET_TOP3:.2f})",
                    "threshold": TARGET_TOP3,
                    "current_value": overall_top3,
                    "gap": TARGET_TOP3 - overall_top3,
                    "possible_causes": [
                        "3码预测策略不当",
                        "模型过拟合",
                        "阈值设置过高",
                    ],
                }
            )

        # 位置性能分析
        for pos, analysis in position_analysis.items():
            # 8码分析
            top8_accuracy = analysis["top8_accuracy"]
            if top8_accuracy < TARGET_TOP8:
                severity = (
                    "high" if top8_accuracy < TARGET_TOP8 * 0.8 else "medium"
                )
                issues.append(
                    {
                        "severity": severity,
                        "category": f"position_{pos}",
                        "description": f"{pos}位8码命中率未达到目标: {top8_accuracy:.4f} (目标: {TARGET_TOP8:.2f})",
                        "threshold": TARGET_TOP8,
                        "current_value": top8_accuracy,
                        "gap": TARGET_TOP8 - top8_accuracy,
                        "possible_causes": [
                            f"{pos}位特征提取不足",
                            f"{pos}位模型配置不当",
                            f"{pos}位历史数据模式分析不足",
                            f"{pos}位阈值设置不合理",
                            f"{pos}位模型选择不当",
                        ],
                    }
                )

            # 5码分析
            top5_accuracy = analysis["top5_accuracy"]
            if top5_accuracy < TARGET_TOP5:
                severity = (
                    "high" if top5_accuracy < TARGET_TOP5 * 0.8 else "medium"
                )
                issues.append(
                    {
                        "severity": severity,
                        "category": f"position_{pos}",
                        "description": f"{pos}位5码命中率未达到目标: {top5_accuracy:.4f} (目标: {TARGET_TOP5:.2f})",
                        "threshold": TARGET_TOP5,
                        "current_value": top5_accuracy,
                        "gap": TARGET_TOP5 - top5_accuracy,
                        "possible_causes": [
                            f"{pos}位5码预测策略不当",
                            f"{pos}位模型权重配置不合理",
                            f"{pos}位阈值设置不合适",
                        ],
                    }
                )

            # 3码分析
            top3_accuracy = analysis["top3_accuracy"]
            if top3_accuracy < TARGET_TOP3:
                severity = (
                    "high" if top3_accuracy < TARGET_TOP3 * 0.8 else "medium"
                )
                issues.append(
                    {
                        "severity": severity,
                        "category": f"position_{pos}",
                        "description": f"{pos}位3码命中率未达到目标: {top3_accuracy:.4f} (目标: {TARGET_TOP3:.2f})",
                        "threshold": TARGET_TOP3,
                        "current_value": top3_accuracy,
                        "gap": TARGET_TOP3 - top3_accuracy,
                        "possible_causes": [
                            f"{pos}位3码预测策略不当",
                            f"{pos}位模型过拟合",
                            f"{pos}位阈值设置过高",
                        ],
                    }
                )

        # 策略分析
        if (
            overall_analysis["top8_accuracy"]
            < overall_analysis["top5_accuracy"]
        ):
            issues.append(
                {
                    "severity": "medium",
                    "category": "strategy_issue",
                    "description": "8码命中率低于5码，策略可能过于保守",
                    "details": f'8码: {overall_analysis["top8_accuracy"]:.4f}, 5码: {overall_analysis["top5_accuracy"]:.4f}',
                    "possible_causes": [
                        "8码预测的阈值设置过高",
                        "模型权重偏向于保守预测",
                        "集成策略过于严格",
                    ],
                }
            )

        # 性能趋势分析
        if len(self.feedback_history) >= 3:
            recent_analyses = self.feedback_history[-3:]
            recent_top8 = [
                a["overall_analysis"]["top8_accuracy"] for a in recent_analyses
            ]

            if recent_top8[-1] < recent_top8[0] * 0.9:
                issues.append(
                    {
                        "severity": "high",
                        "category": "trend_issue",
                        "description": "8码命中率呈下降趋势",
                        "details": f"最近3次分析: {recent_top8[0]:.4f} → {recent_top8[1]:.4f} → {recent_top8[2]:.4f}",
                        "possible_causes": [
                            "策略过拟合",
                            "数据分布发生变化",
                            "模型退化",
                        ],
                    }
                )

        return issues

    def _generate_improvement_suggestions(
        self, issues: List[Dict], position_analysis: Dict
    ) -> List[Dict]:
        """生成改进建议"""
        suggestions = []

        # 8码优化专项建议（最高优先级）
        suggestions.append(
            {
                "priority": "high",
                "category": "eight_code_optimization",
                "title": "8码命中率专项优化",
                "description": "专门针对8码预测的全面优化策略",
                "action_items": [
                    "为8码预测单独设置较低的概率阈值",
                    "增加8码预测的特征数量和质量",
                    "使用专门的8码预测模型",
                    "优化8码预测的集成策略",
                    "对8码预测进行专门的交叉验证",
                ],
            }
        )

        # 特征工程增强
        suggestions.append(
            {
                "priority": "high",
                "category": "feature_engineering",
                "title": "增强8码特征工程",
                "description": "增加更多时间序列特征和统计特征，特别是针对8码预测",
                "action_items": [
                    "添加更多的时间滞后特征（如前10期、前20期的数据）",
                    "增加周期性特征（日、周、月、季节）",
                    "添加更多的统计特征（均值、方差、偏度、峰度等）",
                    "使用RFE进行特征选择，保留最相关的特征",
                    "添加位置间的关联特征",
                    "增加趋势特征和模式识别特征",
                ],
            }
        )

        # 模型权重调整
        suggestions.append(
            {
                "priority": "high",
                "category": "model_weights",
                "title": "优化8码模型权重",
                "description": "根据各模型在8码预测上的表现调整权重",
                "action_items": [
                    "增加在8码预测上表现好的模型权重",
                    "减少在8码预测上表现差的模型权重",
                    "考虑使用动态权重，根据近期表现自动调整",
                    "为8码预测设置单独的权重配置",
                ],
            }
        )

        # 位置特定建议
        for pos, analysis in position_analysis.items():
            if analysis["top8_accuracy"] < 0.6:
                suggestions.append(
                    {
                        "priority": "high",
                        "category": f"position_{pos}",
                        "title": f"优化{pos}位8码预测策略",
                        "description": f"{pos}位8码命中率过低，需要针对性优化",
                        "action_items": [
                            f"增加{pos}位的特征数量，特别是历史模式特征",
                            f"为{pos}位单独训练8码预测模型",
                            f"降低{pos}位8码预测的阈值参数",
                            f"深入分析{pos}位的历史规律和模式",
                            f"为{pos}位设置单独的模型权重",
                        ],
                    }
                )
            elif analysis["top8_accuracy"] < 0.7:
                suggestions.append(
                    {
                        "priority": "medium",
                        "category": f"position_{pos}",
                        "title": f"提升{pos}位8码预测精度",
                        "description": f"{pos}位8码命中率需要进一步提升",
                        "action_items": [
                            f"优化{pos}位的特征组合",
                            f"微调{pos}位的模型参数",
                            f"调整{pos}位的8码预测阈值",
                            f"分析{pos}位与其他位置的关联",
                        ],
                    }
                )

        # 集成策略优化
        suggestions.append(
            {
                "priority": "medium",
                "category": "ensemble_strategy",
                "title": "改进8码集成策略",
                "description": "优化模型集成方法，提高8码预测的稳定性",
                "action_items": [
                    "尝试不同的集成方法（投票、加权平均、 stacking）",
                    "增加模型多样性，引入更多不同类型的模型",
                    "使用贝叶斯优化调整集成参数",
                    "为8码预测设置专门的集成策略",
                ],
            }
        )

        # 阈值调整
        suggestions.append(
            {
                "priority": "medium",
                "category": "threshold_adjustment",
                "title": "优化8码预测阈值",
                "description": "针对8码预测调整概率阈值，平衡召回率和精准率",
                "action_items": [
                    "降低8码预测的概率阈值",
                    "为每个位置设置单独的8码阈值",
                    "使用验证集优化阈值",
                    "考虑使用动态阈值，根据近期表现调整",
                ],
            }
        )

        # 模型选择和调优
        suggestions.append(
            {
                "priority": "medium",
                "category": "model_selection",
                "title": "8码模型选择和调优",
                "description": "选择最适合8码预测的模型并进行调优",
                "action_items": [
                    "测试不同类型的模型在8码预测上的表现",
                    "对表现好的模型进行超参数调优",
                    "考虑使用集成学习方法",
                    "定期评估和更新模型",
                ],
            }
        )

        # 数据质量提升
        suggestions.append(
            {
                "priority": "medium",
                "category": "data_quality",
                "title": "提升数据质量",
                "description": "改善数据质量以提高8码预测准确性",
                "action_items": [
                    "增加历史数据量",
                    "确保数据的准确性和一致性",
                    "处理异常值和缺失值",
                    "考虑数据标准化和归一化",
                ],
            }
        )

        return suggestions

    def generate_feedback_report(self, analysis_result: Dict) -> str:
        """生成反馈分析报告"""
        report = []
        report.append("=" * 80)
        report.append("策略反馈分析报告")
        report.append("=" * 80)

        report.append(f"\n分析时间: {analysis_result.get('timestamp')}")
        report.append(f"分析窗口: {analysis_result.get('window_size')} 期\n")

        # 总体性能
        overall = analysis_result.get("overall_analysis", {})
        report.append("【总体性能】")
        report.append(f"Top-1准确率: {overall.get('top1_accuracy', 0):.4f}")
        report.append(
            f"Top-3准确率: {overall.get('top3_accuracy', 0):.4f} (目标: 0.50)"
        )
        report.append(
            f"Top-5准确率: {overall.get('top5_accuracy', 0):.4f} (目标: 0.70)"
        )
        report.append(
            f"Top-8准确率: {overall.get('top8_accuracy', 0):.4f} (目标: 0.95)"
        )
        report.append(f"测试总数: {overall.get('total_tests', 0)}")

        # 位置性能
        position_analysis = analysis_result.get("position_analysis", {})
        report.append("\n【各位置性能】")
        for pos, analysis in position_analysis.items():
            report.append(f"{pos}位:")
            report.append(f"  Top-1: {analysis.get('top1_accuracy', 0):.4f}")
            report.append(
                f"  Top-3: {analysis.get('top3_accuracy', 0):.4f} (目标: 0.50)"
            )
            report.append(
                f"  Top-5: {analysis.get('top5_accuracy', 0):.4f} (目标: 0.70)"
            )
            report.append(
                f"  Top-8: {analysis.get('top8_accuracy', 0):.4f} (目标: 0.95)"
            )

        # 策略问题
        issues = analysis_result.get("strategy_issues", [])
        if issues:
            report.append("\n【策略问题】")
            for issue in issues:
                severity = issue.get("severity", "medium")
                severity_icon = "🔴" if severity == "high" else "🟡"
                report.append(f"{severity_icon} {issue.get('description')}")
                if "details" in issue:
                    report.append(f"   详情: {issue.get('details')}")
                if "possible_causes" in issue:
                    report.append("   可能原因:")
                    for cause in issue.get("possible_causes", []):
                        report.append(f"     - {cause}")

        # 改进建议
        suggestions = analysis_result.get("improvement_suggestions", [])
        if suggestions:
            report.append("\n【改进建议】")
            for i, suggestion in enumerate(suggestions, 1):
                priority = suggestion.get("priority", "medium")
                priority_icon = "🏆" if priority == "high" else "⭐"
                report.append(
                    f"{i}. {priority_icon} {suggestion.get('title')}"
                )
                report.append(f"   描述: {suggestion.get('description')}")
                action_items = suggestion.get("action_items", [])
                if action_items:
                    report.append("   行动项:")
                    for item in action_items:
                        report.append(f"     - {item}")

        report.append("\n" + "=" * 80)
        report.append("反馈分析报告结束")
        report.append("=" * 80)

        return "\n".join(report)

    def update_prediction_history(self, predictions: Dict, period: str):
        """更新预测历史"""
        prediction_record = {
            "timestamp": datetime.now().isoformat(),
            "period": period,
            "predictions": predictions,
        }

        self.prediction_history.append(prediction_record)
        if len(self.prediction_history) > 100:
            self.prediction_history = self.prediction_history[-100:]
        self._save_prediction_history()

    def run_feedback_analysis(self, window_size: int = 20) -> Dict:
        """运行完整的反馈分析"""
        logger.info("开始运行反馈分析...")

        analysis_result = self.analyze_strategy_performance(window_size)
        report = self.generate_feedback_report(analysis_result)

        logger.info(f"\n{report}")

        return analysis_result


class FeedbackLearningSystem:
    """反馈学习系统 - 基于反馈不断优化策略"""

    def __init__(self):
        self.analyzer = FeedbackAnalyzer()

    def learn_from_feedback(self):
        """从反馈中学习并优化策略"""
        logger.info("开始从反馈中学习...")

        # 运行反馈分析
        analysis_result = self.analyzer.run_feedback_analysis()

        # 提取改进建议
        suggestions = analysis_result.get("improvement_suggestions", [])

        # 优先级排序
        high_priority_suggestions = [
            s for s in suggestions if s.get("priority") == "high"
        ]
        medium_priority_suggestions = [
            s for s in suggestions if s.get("priority") == "medium"
        ]

        logger.info("\n【学习结果】")
        logger.info(f"高优先级建议: {len(high_priority_suggestions)}")
        logger.info(f"中优先级建议: {len(medium_priority_suggestions)}")

        # 生成学习报告
        learning_report = {
            "timestamp": datetime.now().isoformat(),
            "high_priority_suggestions": high_priority_suggestions,
            "medium_priority_suggestions": medium_priority_suggestions,
            "analysis_result": analysis_result,
        }

        # 保存学习报告
        learning_report_path = (
            LOGS_DIR
            / f"feedback_learning_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        try:
            with open(learning_report_path, "w", encoding="utf-8") as f:
                json.dump(learning_report, f, indent=2, ensure_ascii=False)
            logger.info(f"学习报告已保存: {learning_report_path}")
        except Exception as e:
            logger.error(f"保存学习报告失败: {e}")

        return learning_report

    def optimize_strategy_for_8code(self):
        """专门优化8码命中率"""
        logger.info("开始优化8码命中率...")

        # 运行针对8码的分析
        analysis_result = self.analyzer.analyze_strategy_performance(
            window_size=30
        )

        # 提取8码相关的问题和建议
        issues = analysis_result.get("strategy_issues", [])
        suggestions = analysis_result.get("improvement_suggestions", [])

        # 过滤出8码相关的内容
        eight_code_issues = [
            issue for issue in issues if "8码" in issue.get("description", "")
        ]
        eight_code_suggestions = [
            s
            for s in suggestions
            if "8码" in s.get("description", "")
            or "Top-8" in s.get("description", "")
        ]

        logger.info("\n【8码优化分析】")
        logger.info(f"8码相关问题: {len(eight_code_issues)}")
        logger.info(f"8码相关建议: {len(eight_code_suggestions)}")

        # 生成8码优化报告
        eight_code_report = {
            "timestamp": datetime.now().isoformat(),
            "eight_code_issues": eight_code_issues,
            "eight_code_suggestions": eight_code_suggestions,
            "analysis_result": analysis_result,
        }

        # 保存8码优化报告
        eight_code_report_path = (
            LOGS_DIR
            / f"eight_code_optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        try:
            with open(eight_code_report_path, "w", encoding="utf-8") as f:
                json.dump(eight_code_report, f, indent=2, ensure_ascii=False)
            logger.info(f"8码优化报告已保存: {eight_code_report_path}")
        except Exception as e:
            logger.error(f"保存8码优化报告失败: {e}")

        return eight_code_report
