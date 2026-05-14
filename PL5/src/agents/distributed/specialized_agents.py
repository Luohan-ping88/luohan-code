"""
专门化智能体
实现各种专门功能的智能体
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .protocol import (
    AgentCapability,
)
from .base_agent import (
    CollaborativeAgent,
    MasterAgent,
    TaskResult,
)

logger = logging.getLogger(__name__)


class PredictionAgent(CollaborativeAgent):
    """预测智能体 - 负责时序预测"""

    def __init__(self, position: str, protocol=None):
        self.position = position
        capabilities = [
            AgentCapability(
                name=f"predict_{position}",
                description=f"预测{position}位置",
                input_schema={"position": "string", "data": "array"},
                output_schema={"prediction": "array", "confidence": "float"},
            ),
            AgentCapability(
                name="ensemble_predict",
                description="集成预测",
                input_schema={"models": "array"},
                output_schema={"prediction": "array"},
            ),
        ]

        super().__init__(
            agent_name=f"PredictionAgent_{position}",
            agent_type="prediction",
            capabilities=capabilities,
            protocol=protocol,
        )

        self.model = None
        self._register_prediction_handlers()

    def _register_prediction_handlers(self):
        """注册预测处理器"""

        async def handle_predict(data: Dict[str, Any]) -> TaskResult:
            try:
                position = data.get("position", self.position)
                input_data = data.get("data", [])

                prediction_result = await self._predict(position, input_data)

                return TaskResult(
                    success=True,
                    result=prediction_result,
                    metadata={"position": position},
                )

            except Exception as e:
                logger.error(f"Prediction error: {e}")
                return TaskResult(success=False, error=str(e))

        self.register_handler(f"predict_{self.position}", handle_predict)

    async def _predict(self, position: str, data: List[Any]) -> Dict[str, Any]:
        """执行预测"""
        try:
            from src.core.models.transformer_predictor import (
                TimeSeriesTransformer,
            )
            import numpy as np

            if len(data) < 20:
                return {"prediction": list(range(10)), "confidence": 0.5}

            arr_data = np.array(data)
            transformer = TimeSeriesTransformer(
                d_model=32, n_heads=4, n_layers=2
            )

            result = transformer.fit(
                arr_data, seq_len=min(20, len(data) - 1), epochs=5
            )
            prediction = transformer.predict(
                arr_data, seq_len=min(20, len(data) - 1)
            )

            return {
                "prediction": prediction["top_k"],
                "probabilities": prediction["probabilities"],
                "confidence": prediction["confidence"],
                "entropy": prediction["entropy"],
            }

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {"prediction": list(range(10)), "confidence": 0.3}

    async def predict(self, data: List[Any]) -> Dict[str, Any]:
        """公开预测接口"""
        return await self._predict(self.position, data)


class AnalysisAgent(CollaborativeAgent):
    """分析智能体 - 负责模式分析和策略建议"""

    def __init__(self, protocol=None):
        capabilities = [
            AgentCapability(
                name="pattern_analysis",
                description="分析数据模式",
                input_schema={"data": "array"},
                output_schema={"patterns": "array", "confidence": "float"},
            ),
            AgentCapability(
                name="strategy_suggestion",
                description="生成策略建议",
                input_schema={"evaluation": "object"},
                output_schema={"suggestions": "array"},
            ),
            AgentCapability(
                name="anomaly_detection",
                description="异常检测",
                input_schema={"data": "array"},
                output_schema={"anomalies": "array"},
            ),
        ]

        super().__init__(
            agent_name="AnalysisAgent",
            agent_type="analysis",
            capabilities=capabilities,
            protocol=protocol,
        )

        self._register_analysis_handlers()

    def _register_analysis_handlers(self):
        """注册分析处理器"""

        async def handle_pattern_analysis(data: Dict[str, Any]) -> TaskResult:
            try:
                history_data = data.get("data", [])
                result = await self.analyze_patterns(history_data)

                return TaskResult(success=True, result=result)

            except Exception as e:
                logger.error(f"Pattern analysis error: {e}")
                return TaskResult(success=False, error=str(e))

        async def handle_strategy(data: Dict[str, Any]) -> TaskResult:
            try:
                evaluation = data.get("evaluation", {})
                result = await self.generate_strategy(evaluation)

                return TaskResult(success=True, result=result)

            except Exception as e:
                logger.error(f"Strategy generation error: {e}")
                return TaskResult(success=False, error=str(e))

        self.register_handler("pattern_analysis", handle_pattern_analysis)
        self.register_handler("strategy_suggestion", handle_strategy)

    async def analyze_patterns(
        self, data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """分析数据模式"""
        patterns = []
        frequencies = {}

        for record in data:
            for key, value in record.items():
                if key != "period" and isinstance(value, (int, str)):
                    freq_key = f"{key}_{value}"
                    frequencies[freq_key] = frequencies.get(freq_key, 0) + 1

        sorted_freq = sorted(
            frequencies.items(), key=lambda x: x[1], reverse=True
        )
        top_patterns = [
            {"pattern": p[0], "frequency": p[1]} for p in sorted_freq[:10]
        ]

        return {
            "patterns": top_patterns,
            "total_records": len(data),
            "unique_patterns": len(frequencies),
            "timestamp": datetime.now().isoformat(),
        }

    async def generate_strategy(
        self, evaluation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成策略建议"""
        suggestions = []

        accuracy = evaluation.get("accuracy", 0.5)
        if accuracy < 0.4:
            suggestions.append(
                {
                    "type": "warning",
                    "message": "准确率偏低，建议增加模型复杂度",
                    "action": "increase_model_depth",
                }
            )
        elif accuracy > 0.6:
            suggestions.append(
                {
                    "type": "success",
                    "message": "当前策略表现良好",
                    "action": "maintain",
                }
            )

        return {
            "suggestions": suggestions,
            "evaluation": evaluation,
            "timestamp": datetime.now().isoformat(),
        }


class DataCollectionAgent(CollaborativeAgent):
    """数据收集智能体"""

    def __init__(self, protocol=None):
        capabilities = [
            AgentCapability(
                name="collect_data",
                description="收集历史数据",
                input_schema={"source": "string", "count": "int"},
                output_schema={"data": "array"},
            ),
            AgentCapability(
                name="validate_data",
                description="验证数据质量",
                input_schema={"data": "array"},
                output_schema={"valid": "bool", "quality": "float"},
            ),
        ]

        super().__init__(
            agent_name="DataCollectionAgent",
            agent_type="data_collection",
            capabilities=capabilities,
            protocol=protocol,
        )

        self._register_data_handlers()

    def _register_data_handlers(self):
        """注册数据处理器"""

        async def handle_collect(data: Dict[str, Any]) -> TaskResult:
            try:
                count = data.get("count", 100)
                result = await self.collect_data(count)

                return TaskResult(success=True, result=result)

            except Exception as e:
                logger.error(f"Data collection error: {e}")
                return TaskResult(success=False, error=str(e))

        async def handle_validate(data: Dict[str, Any]) -> TaskResult:
            try:
                data_list = data.get("data", [])
                result = await self.validate_data(data_list)

                return TaskResult(success=True, result=result)

            except Exception as e:
                logger.error(f"Data validation error: {e}")
                return TaskResult(success=False, error=str(e))

        self.register_handler("collect_data", handle_collect)
        self.register_handler("validate_data", handle_validate)

    async def collect_data(self, count: int) -> Dict[str, Any]:
        """收集数据"""
        try:
            from src.core.data.collector import PL5DataCollector

            collector = PL5DataCollector()
            data = collector.fetch_historical_data(count=count)

            return {
                "data": (
                    data if isinstance(data, list) else data.to_dict("records")
                ),
                "count": len(data) if hasattr(data, "__len__") else 0,
                "source": "local",
            }

        except Exception as e:
            logger.error(f"Data collection failed: {e}")
            return {"data": [], "count": 0, "error": str(e)}

    async def validate_data(self, data: List[Any]) -> Dict[str, Any]:
        """验证数据"""
        if not data:
            return {"valid": False, "quality": 0.0, "errors": ["Empty data"]}

        errors = []
        for i, record in enumerate(data):
            if not isinstance(record, dict):
                errors.append(f"Record {i}: not a dict")

        quality = 1.0 - (len(errors) / max(len(data), 1))

        return {
            "valid": len(errors) == 0,
            "quality": quality,
            "errors": errors,
            "total_records": len(data),
        }


class EvaluationAgent(CollaborativeAgent):
    """评估智能体"""

    def __init__(self, protocol=None):
        capabilities = [
            AgentCapability(
                name="evaluate_prediction",
                description="评估预测结果",
                input_schema={"prediction": "array", "actual": "array"},
                output_schema={"accuracy": "float", "metrics": "object"},
            ),
            AgentCapability(
                name="compare_models",
                description="比较模型性能",
                input_schema={"model_results": "array"},
                output_schema={"best_model": "string", "rankings": "array"},
            ),
        ]

        super().__init__(
            agent_name="EvaluationAgent",
            agent_type="evaluation",
            capabilities=capabilities,
            protocol=protocol,
        )

        self._register_evaluation_handlers()

    def _register_evaluation_handlers(self):
        """注册评估处理器"""

        async def handle_evaluate(data: Dict[str, Any]) -> TaskResult:
            try:
                prediction = data.get("prediction", [])
                actual = data.get("actual", [])

                result = await self.evaluate(prediction, actual)

                return TaskResult(success=True, result=result)

            except Exception as e:
                logger.error(f"Evaluation error: {e}")
                return TaskResult(success=False, error=str(e))

        self.register_handler("evaluate_prediction", handle_evaluate)

    async def evaluate(
        self, prediction: List[Any], actual: List[Any]
    ) -> Dict[str, Any]:
        """评估预测"""
        if not prediction or not actual:
            return {"accuracy": 0.0, "metrics": {}}

        correct = sum(1 for p, a in zip(prediction, actual) if p == a)
        accuracy = correct / len(actual)

        return {
            "accuracy": accuracy,
            "correct": correct,
            "total": len(actual),
            "metrics": {
                "precision": accuracy,
                "recall": accuracy,
            },
            "timestamp": datetime.now().isoformat(),
        }


class OrchestratorAgent(MasterAgent):
    """编排智能体 - 协调多个智能体工作"""

    def __init__(self, protocol=None):
        super().__init__(
            agent_name="OrchestratorAgent",
            agent_type="orchestrator",
            protocol=protocol,
        )

        self.prediction_agents: Dict[str, PredictionAgent] = {}
        self.analysis_agent: Optional[AnalysisAgent] = None
        self.data_agent: Optional[DataCollectionAgent] = None
        self.evaluation_agent: Optional[EvaluationAgent] = None

    async def initialize_team(self):
        """初始化团队"""
        from .protocol import AgentCommunicationProtocol

        if self.protocol is None:
            self.protocol = AgentCommunicationProtocol()

        for position in ["wan", "qian", "bai", "shi", "ge"]:
            agent = PredictionAgent(position, self.protocol)
            self.prediction_agents[position] = agent
            self.register_worker(agent)

        self.analysis_agent = AnalysisAgent(self.protocol)
        self.register_worker(self.analysis_agent)

        self.data_agent = DataCollectionAgent(self.protocol)
        self.register_worker(self.data_agent)

        self.evaluation_agent = EvaluationAgent(self.protocol)
        self.register_worker(self.evaluation_agent)

        logger.info("Agent team initialized")

    async def run_prediction_workflow(
        self, count: int = 100
    ) -> Dict[str, Any]:
        """运行预测工作流"""
        await self.protocol.start()

        for agent in list(self.prediction_agents.values()) + [
            self.analysis_agent,
            self.data_agent,
            self.evaluation_agent,
        ]:
            if agent:
                await agent.start()

        try:
            data_result = await self.data_agent.collect_data(count)

            predictions = {}
            for position, agent in self.prediction_agents.items():
                pred = await agent.predict(data_result.get("data", [])[-50:])
                predictions[position] = pred

            analysis_result = await self.analysis_agent.analyze_patterns(
                data_result.get("data", [])
            )

            return {
                "success": True,
                "predictions": predictions,
                "analysis": analysis_result,
                "data_count": data_result.get("count", 0),
            }

        finally:
            for agent in list(self.prediction_agents.values()) + [
                self.analysis_agent,
                self.data_agent,
                self.evaluation_agent,
            ]:
                if agent:
                    await agent.stop()

            await self.protocol.stop()
