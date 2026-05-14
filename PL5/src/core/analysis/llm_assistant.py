"""
LLM辅助分析模块
使用大语言模型增强预测分析能力
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMAnalysisConfig:
    """LLM分析配置"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: str = "https://api.openai.com/v1",
        model: str = "gpt-3.5-turbo",
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ):
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature


class LLMAnalysisResult:
    """LLM分析结果"""

    def __init__(
        self,
        success: bool,
        analysis: str = "",
        suggestions: List[str] = None,
        confidence: float = 0.0,
        error: str = "",
    ):
        self.success = success
        self.analysis = analysis
        self.suggestions = suggestions or []
        self.confidence = confidence
        self.error = error
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "analysis": self.analysis,
            "suggestions": self.suggestions,
            "confidence": self.confidence,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class LLMAssistant:
    """LLM辅助分析器"""

    def __init__(self, config: Optional[LLMAnalysisConfig] = None):
        self.config = config or LLMAnalysisConfig()
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化LLM客户端"""
        try:
            import openai

            if self.config.api_key:
                openai.api_key = self.config.api_key
            openai.api_base = self.config.api_base
            self.client = openai
            logger.info("LLM客户端初始化成功")
        except ImportError:
            logger.warning("OpenAI库未安装，LLM功能受限")
        except Exception as e:
            logger.error(f"LLM客户端初始化失败: {e}")

    def analyze_pattern(
        self, history_data: List[Dict[str, Any]], prediction: Dict[str, Any]
    ) -> LLMAnalysisResult:
        """分析历史模式和预测结果"""

        if not self.client:
            return LLMAnalysisResult(success=False, error="LLM客户端未初始化")

        prompt = self._build_pattern_analysis_prompt(history_data, prediction)

        try:
            response = self.client.ChatCompletion.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个彩票预测分析专家。",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            analysis = response.choices[0].message.content
            suggestions = self._extract_suggestions(analysis)

            return LLMAnalysisResult(
                success=True,
                analysis=analysis,
                suggestions=suggestions,
                confidence=0.85,
            )

        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            return LLMAnalysisResult(success=False, error=str(e))

    def generate_strategy(
        self,
        evaluation_metrics: Dict[str, Any],
        historical_performance: Dict[str, Any],
    ) -> LLMAnalysisResult:
        """生成优化策略建议"""

        if not self.client:
            return LLMAnalysisResult(success=False, error="LLM客户端未初始化")

        prompt = self._build_strategy_prompt(
            evaluation_metrics, historical_performance
        )

        try:
            response = self.client.ChatCompletion.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的量化交易策略分析师。",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            analysis = response.choices[0].message.content
            suggestions = self._extract_suggestions(analysis)

            return LLMAnalysisResult(
                success=True,
                analysis=analysis,
                suggestions=suggestions,
                confidence=0.90,
            )

        except Exception as e:
            logger.error(f"LLM策略生成失败: {e}")
            return LLMAnalysisResult(success=False, error=str(e))

    def explain_prediction(
        self, prediction: Dict[str, Any], features: Dict[str, Any]
    ) -> LLMAnalysisResult:
        """解释预测结果"""

        if not self.client:
            return LLMAnalysisResult(success=False, error="LLM客户端未初始化")

        prompt = self._build_explanation_prompt(prediction, features)

        try:
            response = self.client.ChatCompletion.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个友好的AI助手，解释数字预测的逻辑。",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            analysis = response.choices[0].message.content

            return LLMAnalysisResult(
                success=True,
                analysis=analysis,
                confidence=0.80,
            )

        except Exception as e:
            logger.error(f"LLM解释生成失败: {e}")
            return LLMAnalysisResult(success=False, error=str(e))

    def _build_pattern_analysis_prompt(
        self, history_data: List[Dict[str, Any]], prediction: Dict[str, Any]
    ) -> str:
        """构建模式分析提示"""

        recent_history = (
            history_data[-20:] if len(history_data) > 20 else history_data
        )

        history_str = "\n".join(
            [
                f"期号: {d.get('period', 'N/A')}, "
                f"万:{d.get('wan', 'N/A')}, "
                f"千:{d.get('qian', 'N/A')}, "
                f"百:{d.get('bai', 'N/A')}, "
                f"十:{d.get('shi', 'N/A')}, "
                f"个:{d.get('ge', 'N/A')}"
                for d in recent_history
            ]
        )

        pred_str = "\n".join(
            [
                f"{pos}: 预测 {prediction.get(pos, {}).get('top_k', [])} "
                f"(概率: {prediction.get(pos, {}).get('probabilities', [])})"
                for pos in ["wan", "qian", "bai", "shi", "ge"]
            ]
        )

        prompt = f"""分析以下彩票历史数据和预测结果，识别可能的模式：

历史数据（最近20期）：
{history_str}

当前预测：
{pred_str}

请分析：
1. 历史数据中是否存在明显的模式或规律？
2. 预测结果与历史模式的关系
3. 可能的高概率组合
4. 风险提示

用中文回答。"""

        return prompt

    def _build_strategy_prompt(
        self,
        evaluation_metrics: Dict[str, Any],
        historical_performance: Dict[str, Any],
    ) -> str:
        """构建策略生成提示"""

        metrics_str = json.dumps(
            evaluation_metrics, indent=2, ensure_ascii=False
        )
        perf_str = json.dumps(
            historical_performance, indent=2, ensure_ascii=False
        )

        prompt = f"""基于以下评估指标和历史表现，生成优化策略：

评估指标：
{metrics_str}

历史表现：
{perf_str}

请提供：
1. 当前策略的优势和不足
2. 具体改进建议（3-5条）
3. 风险控制建议
4. 预期收益分析

用中文回答，简明扼要。"""

        return prompt

    def _build_explanation_prompt(
        self, prediction: Dict[str, Any], features: Dict[str, Any]
    ) -> str:
        """构建解释提示"""

        pred_str = "\n".join(
            [
                f"{pos}: 预测 {prediction.get(pos, {}).get('top_k', [])} "
                f"置信度: {prediction.get(pos, {}).get('confidence', 0):.2%}"
                for pos in ["wan", "qian", "bai", "shi", "ge"]
            ]
        )

        prompt = f"""用简单易懂的语言解释以下预测：

预测结果：
{pred_str}

请解释：
1. 这些预测是如何得出的？
2. 每个位置的预测依据是什么？
3. 有什么需要注意的？

用中文回答，让非专业用户也能理解。"""

        return prompt

    def _extract_suggestions(self, text: str) -> List[str]:
        """从文本中提取建议"""
        suggestions = []
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if any(
                marker in line
                for marker in [
                    "建议",
                    "推荐",
                    "注意",
                    "建议:",
                    "1.",
                    "2.",
                    "3.",
                ]
            ):
                clean_line = line.lstrip("0123456789.、) ").strip()
                if clean_line and len(clean_line) > 5:
                    suggestions.append(clean_line)

        return suggestions[:5]


class LLMAnalysisOrchestrator:
    """LLM分析编排器"""

    def __init__(self):
        self.assistant = LLMAssistant()
        self.analysis_cache: Dict[str, LLMAnalysisResult] = {}

    def analyze_and_suggest(
        self, history_data: List[Dict[str, Any]], prediction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """综合分析并提供建议"""

        pattern_analysis = self.assistant.analyze_pattern(
            history_data, prediction
        )

        suggestions = []
        if pattern_analysis.success:
            suggestions.extend(pattern_analysis.suggestions)

        return {
            "pattern_analysis": pattern_analysis.to_dict(),
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat(),
        }

    def generate_optimization_report(
        self,
        evaluation_metrics: Dict[str, Any],
        historical_performance: Dict[str, Any],
        history_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """生成完整的优化报告"""

        strategy = self.assistant.generate_strategy(
            evaluation_metrics, historical_performance
        )

        report = {
            "strategy": strategy.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }

        if history_data and len(history_data) > 10:
            recent_analysis = self.assistant.analyze_pattern(
                history_data[-10:], {}
            )
            report["recent_pattern"] = recent_analysis.to_dict()

        return report
