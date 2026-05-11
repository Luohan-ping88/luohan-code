"""
数据处理智能体 - 负责数据采集、清洗、特征工程
"""

import asyncio
from typing import Dict, Any, List
from datetime import datetime
import logging
import pandas as pd
import numpy as np

from .base_agent import BaseAgent, AgentTask, AgentResult

logger = logging.getLogger(__name__)


class DataProcessingAgent(BaseAgent):
    """
    数据处理智能体

    职责：
    1. 从多个数据源并行采集数据
    2. 数据清洗和验证
    3. 特征工程（支持并行计算）
    4. 数据版本管理和缓存
    """

    def __init__(self, max_workers: int = 8):
        super().__init__("DataProcessingAgent", max_workers)
        self.data_cache = {}
        self.feature_cache = {}

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "数据采集、清洗、特征工程",
            "supported_tasks": [
                "fetch_data",  # 采集数据
                "clean_data",  # 数据清洗
                "extract_features",  # 特征工程
                "validate_data",  # 数据验证
                "cache_management",  # 缓存管理
            ],
            "parallel_support": True,
            "cache_support": True,
        }

    def validate(self, task: AgentTask) -> bool:
        """验证任务参数"""
        required_params = {
            "fetch_data": ["sources"],
            "clean_data": ["data"],
            "extract_features": ["data", "feature_types"],
            "validate_data": ["data"],
            "cache_management": ["operation"],
        }

        task_type = task.task_type
        if task_type not in required_params:
            return False

        params = task.params
        for param in required_params[task_type]:
            if param not in params:
                logger.error(f"[{self.name}] 缺少必要参数: {param}")
                return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """执行任务"""
        start_time = datetime.now()
        task_type = task.task_type

        try:
            if task_type == "fetch_data":
                result_data = await self._fetch_data(task.params)
            elif task_type == "clean_data":
                result_data = await self._clean_data(task.params)
            elif task_type == "extract_features":
                result_data = await self._extract_features(task.params)
            elif task_type == "validate_data":
                result_data = await self._validate_data(task.params)
            elif task_type == "cache_management":
                result_data = await self._manage_cache(task.params)
            else:
                raise ValueError(f"未知任务类型: {task_type}")

            execution_time = (datetime.now() - start_time).total_seconds()

            return AgentResult(task_id=task.task_id, success=True, data=result_data, execution_time=execution_time)

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{self.name}] 任务执行失败: {str(e)}")

            return AgentResult(
                task_id=task.task_id, success=False, data={}, execution_time=execution_time, error_message=str(e)
            )

    async def _fetch_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """从数据源采集数据 - 使用单一数据源避免阻塞"""
        sources = params.get("sources", ["lecai"])

        logger.info(f"[{self.name}] 开始从数据源采集数据")

        # 只使用第一个数据源，避免并行采集导致的阻塞
        source = sources[0] if sources else "lecai"

        try:
            # 添加超时保护
            result = await asyncio.wait_for(self._fetch_from_source(source), timeout=60)  # 60秒超时

            logger.info(f"[{self.name}] 数据采集完成: {len(result)} 条记录")

            # 缓存数据
            cache_key = f"raw_data_{datetime.now().strftime('%Y%m%d')}"
            self.data_cache[cache_key] = result

            return {"data": result, "record_count": len(result), "sources": [source], "cache_key": cache_key}

        except asyncio.TimeoutError:
            logger.error(f"[{self.name}] 数据采集超时")
            raise Exception("数据采集超时")
        except Exception as e:
            logger.error(f"[{self.name}] 数据采集失败: {str(e)}")
            raise

    async def _fetch_from_source(self, source: str) -> pd.DataFrame:
        """从单个数据源采集"""
        # 使用现有的 data_collector_v8
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.core.data.collector import PL5DataCollector

        collector = PL5DataCollector()

        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()

        # 调用统一的更新方法
        df = await loop.run_in_executor(self.executor, collector.update_data)

        return df

    def _merge_data_sources(self, data_list: List[pd.DataFrame]) -> pd.DataFrame:
        """合并多个数据源的数据"""
        merged = pd.concat(data_list, ignore_index=True)
        # 去重（基于期号）
        merged = merged.drop_duplicates(subset=["period"], keep="first")
        # 排序
        merged = merged.sort_values("period").reset_index(drop=True)
        return merged

    async def _clean_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """数据清洗"""
        data = params.get("data")

        logger.info(f"[{self.name}] 开始数据清洗")

        # 使用线程池执行
        loop = asyncio.get_event_loop()
        cleaned_data = await loop.run_in_executor(self.executor, self._clean_data_sync, data)

        logger.info(f"[{self.name}] 数据清洗完成")

        return {"data": cleaned_data, "record_count": len(cleaned_data), "cleaned": True}

    def _clean_data_sync(self, data: pd.DataFrame) -> pd.DataFrame:
        """同步数据清洗"""
        df = data.copy()

        # 1. 处理缺失值
        df = df.dropna(subset=["period", "wan", "qian", "bai", "shi", "ge"])

        # 2. 验证数值范围
        for col in ["wan", "qian", "bai", "shi", "ge"]:
            df = df[(df[col] >= 0) & (df[col] <= 9)]

        # 3. 验证期号格式
        df = df[df["period"].astype(str).str.match(r"^\d{7}$")]

        # 4. 排序
        df = df.sort_values("period").reset_index(drop=True)

        return df

    async def _extract_features(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """特征工程（支持并行）"""
        data = params.get("data")
        feature_types = params.get("feature_types", "all")

        logger.info(f"[{self.name}] 开始特征工程")

        # 检查缓存
        cache_key = f"features_{hash(str(data.shape))}_{feature_types}"
        if cache_key in self.feature_cache:
            logger.info(f"[{self.name}] 使用缓存的特征数据")
            return {
                "features": self.feature_cache[cache_key],
                "feature_count": len(self.feature_cache[cache_key].columns),
                "from_cache": True,
            }

        # 使用线程池执行特征工程
        loop = asyncio.get_event_loop()

        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.core.features.engineer import FeatureEngineer

        engineer = FeatureEngineer()

        features = await loop.run_in_executor(self.executor, engineer.extract_all_features, data)

        # 缓存结果
        self.feature_cache[cache_key] = features

        feature_cols = [
            c for c in features.columns if c not in ["period", "full_number", "wan", "qian", "bai", "shi", "ge"]
        ]

        logger.info(f"[{self.name}] 特征工程完成: {len(feature_cols)} 个特征")

        return {
            "features": features,
            "feature_cols": feature_cols,
            "feature_count": len(feature_cols),
            "from_cache": False,
        }

    async def _validate_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """数据验证"""
        data = params.get("data")

        validation_results = {
            "record_count": len(data),
            "period_range": (data["period"].min(), data["period"].max()),
            "missing_values": data.isnull().sum().to_dict(),
            "duplicate_periods": data["period"].duplicated().sum(),
            "value_ranges": {},
        }

        for col in ["wan", "qian", "bai", "shi", "ge"]:
            validation_results["value_ranges"][col] = {
                "min": int(data[col].min()),
                "max": int(data[col].max()),
                "mean": float(data[col].mean()),
            }

        # 检查数据连续性
        periods = sorted([int(p) for p in data["period"].unique()])
        gaps = []
        for i in range(1, len(periods)):
            if periods[i] - periods[i - 1] > 1:
                gaps.append((periods[i - 1], periods[i]))

        validation_results["period_gaps"] = gaps
        validation_results["is_valid"] = len(gaps) == 0 and data.isnull().sum().sum() == 0

        return validation_results

    async def _manage_cache(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """缓存管理"""
        operation = params.get("operation")

        if operation == "clear":
            self.data_cache.clear()
            self.feature_cache.clear()
            return {"cleared": True}

        elif operation == "stats":
            return {
                "data_cache_size": len(self.data_cache),
                "feature_cache_size": len(self.feature_cache),
                "data_cache_keys": list(self.data_cache.keys()),
                "feature_cache_keys": list(self.feature_cache.keys()),
            }

        elif operation == "get":
            key = params.get("key")
            cache_type = params.get("cache_type", "data")

            if cache_type == "data":
                return {"data": self.data_cache.get(key)}
            else:
                return {"data": self.feature_cache.get(key)}

        else:
            raise ValueError(f"未知的缓存操作: {operation}")

    async def analyze_data_quality(self, data) -> Dict[str, Any]:
        """
        分析数据质量

        Args:
            data: 数据

        Returns:
            数据质量分析结果
        """
        try:
            if not data:
                return {
                    "agent": "data",
                    "confidence": 0.6,
                    "recommendation": "collect_more_data",
                    "quality_score": 0,
                    "issues": ["No data provided"],
                }

            # 简单的数据质量分析
            record_count = len(data) if isinstance(data, list) else len(data)

            quality_score = min(100, record_count * 2)  # 简单的质量评分

            issues = []
            if record_count < 100:
                issues.append("Insufficient data records")

            return {
                "agent": "data",
                "confidence": 0.8,
                "recommendation": "sufficient_data" if record_count >= 100 else "collect_more_data",
                "quality_score": quality_score,
                "record_count": record_count,
                "issues": issues,
            }
        except Exception as e:
            logger.error(f"[DataAgent] 分析数据质量失败: {str(e)}")
            return {"agent": "data", "error": str(e)}

    async def suggest_optimizations(self) -> Dict[str, Any]:
        """
        提供数据优化建议

        Returns:
            优化建议
        """
        try:
            return {
                "agent": "data",
                "suggestions": ["增加数据采集频率", "优化特征提取算法", "实现数据缓存机制", "添加数据验证步骤"],
                "priority": "medium",
            }
        except Exception as e:
            logger.error(f"[DataAgent] 生成优化建议失败: {str(e)}")
            return {"agent": "data", "error": str(e)}


from pathlib import Path
