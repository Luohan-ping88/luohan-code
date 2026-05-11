#!/usr/bin/env python3
"""
动态特征组验证器
用于依据开奖数据的变化采用动态的多维特征组验证训练策略
"""

import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import MODEL_CONFIG, MODELS_DIR, LOGS_DIR

logger = logging.getLogger(__name__)


class DynamicFeatureValidator:
    """动态特征组验证器

    用于依据开奖数据的变化采用动态的多维特征组验证训练策略
    能够适应开奖数据的变化及检验出最佳特征组合
    """

    def __init__(self):
        self.collector = PL5DataCollector()
        self.engineer = FeatureEngineer()
        self.best_feature_config = None
        self.validation_history = []

    def generate_feature_combinations(self) -> List[Dict[str, Any]]:
        """生成多种特征组合策略

        Returns:
            List[Dict[str, Any]]: 特征组合策略列表
        """
        feature_combinations = [
            {"name": "full_features", "description": "全量特征", "select_top": None, "feature_selection_method": "rfe"},
            {
                "name": "top_50_rfe",
                "description": "RFE选择前50个特征",
                "select_top": 50,
                "feature_selection_method": "rfe",
            },
            {
                "name": "top_100_rfe",
                "description": "RFE选择前100个特征",
                "select_top": 100,
                "feature_selection_method": "rfe",
            },
            {
                "name": "top_150_rfe",
                "description": "RFE选择前150个特征",
                "select_top": 150,
                "feature_selection_method": "rfe",
            },
            {
                "name": "top_50_model_based",
                "description": "模型选择前50个特征",
                "select_top": 50,
                "feature_selection_method": "model_based",
            },
            {
                "name": "top_100_model_based",
                "description": "模型选择前100个特征",
                "select_top": 100,
                "feature_selection_method": "model_based",
            },
        ]

        return feature_combinations

    def validate_feature_combination(self, df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证单个特征组合的性能

        Args:
            df: 输入数据
            config: 特征组合配置

        Returns:
            Dict[str, Any]: 验证结果
        """
        try:
            logger.info(f"验证特征组合: {config['name']} ({config['description']})")

            # 提取特征
            df_features = self.engineer.extract_all_features(
                df, select_top=config["select_top"], feature_selection_method=config["feature_selection_method"]
            )

            # 提取特征列
            feature_cols = [
                col
                for col in df_features.columns
                if col not in ["period", "date", "full_number", "wan", "qian", "bai", "shi", "ge"]
            ]

            # 划分训练集和测试集
            test_size = 20
            if len(df_features) < test_size * 2:
                logger.warning(f"数据量不足，使用全部数据进行验证")
                train_data = df_features
                test_data = df_features.tail(5)
            else:
                train_data = df_features.iloc[:-test_size]
                test_data = df_features.iloc[-test_size:]

            # 训练模型
            predictor = EnhancedPL5Predictor()
            predictor.fit(train_data, feature_cols)

            # 验证模型
            total_hits = 0
            total_tests = 0

            for i, row in test_data.iterrows():
                # 提取特征向量
                features_list = []
                for col in feature_cols:
                    val = row[col]
                    # 处理可能的 Inf/NaN 和类型问题
                    try:
                        val = float(val)
                        if np.isfinite(val):
                            features_list.append(val)
                        else:
                            features_list.append(0.0)
                    except (ValueError, TypeError):
                        features_list.append(0.0)

                features = np.array(features_list, dtype=np.float64)

                # 准备最近的原始数据
                recent_original_data = {}
                for pos in ["wan", "qian", "bai", "shi", "ge"]:
                    if pos in df.columns:
                        recent_data = df[pos].values[-20:] if len(df) >= 20 else df[pos].values
                        recent_original_data[pos] = recent_data

                # 预测
                predictions = predictor.predict(
                    features=features,
                    recent_original_data=recent_original_data,
                    top_k=8,
                    use_rl=False,
                    use_uncertainty=False,
                )

                # 验证预测结果
                for pos in ["wan", "qian", "bai", "shi", "ge"]:
                    actual_value = int(row[pos])
                    if pos in predictions and "top_k" in predictions[pos]:
                        top_k = predictions[pos]["top_k"]
                        if actual_value in top_k:
                            total_hits += 1
                        total_tests += 1

            # 计算准确率
            accuracy = total_hits / total_tests if total_tests > 0 else 0

            result = {
                "name": config["name"],
                "description": config["description"],
                "select_top": config["select_top"],
                "feature_selection_method": config["feature_selection_method"],
                "feature_count": len(feature_cols),
                "accuracy": accuracy,
                "hits": total_hits,
                "tests": total_tests,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"特征组合 {config['name']} 验证完成，准确率: {accuracy:.4f}")
            return result

        except Exception as e:
            logger.error(f"验证特征组合 {config['name']} 失败: {e}")
            return {
                "name": config["name"],
                "description": config["description"],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def find_best_feature_combination(self, df: pd.DataFrame) -> Dict[str, Any]:
        """寻找最佳特征组合

        Args:
            df: 输入数据

        Returns:
            Dict[str, Any]: 最佳特征组合配置
        """
        logger.info("开始寻找最佳特征组合...")

        # 生成特征组合策略
        feature_combinations = self.generate_feature_combinations()

        # 验证每个特征组合
        validation_results = []
        for config in feature_combinations:
            result = self.validate_feature_combination(df, config)
            if "error" not in result:
                validation_results.append(result)

        # 选择最佳特征组合
        if validation_results:
            best_result = max(validation_results, key=lambda x: x["accuracy"])
            logger.info(f"最佳特征组合: {best_result['name']}，准确率: {best_result['accuracy']:.4f}")

            # 更新最佳特征配置
            self.best_feature_config = {
                "select_top": best_result["select_top"],
                "feature_selection_method": best_result["feature_selection_method"],
            }

            # 记录验证历史
            self.validation_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "best_feature_combination": best_result,
                    "all_results": validation_results,
                }
            )

            return self.best_feature_config
        else:
            logger.warning("所有特征组合验证失败，使用默认配置")
            return {"select_top": None, "feature_selection_method": "rfe"}

    def get_best_feature_config(self) -> Dict[str, Any]:
        """获取最佳特征配置

        Returns:
            Dict[str, Any]: 最佳特征配置
        """
        if self.best_feature_config is None:
            # 如果没有最佳配置，使用默认配置
            return {"select_top": None, "feature_selection_method": "rfe"}
        return self.best_feature_config

    def validate_and_update_features(self) -> Dict[str, Any]:
        """验证并更新特征配置

        Returns:
            Dict[str, Any]: 验证结果
        """
        # 加载最新数据（使用 update_data 而非 load_processed_data，确保数据最新）
        df = self.collector.update_data()
        if df is None:
            logger.error("无法加载数据，使用默认特征配置")
            return {"success": False, "error": "无法加载数据"}

        # 寻找最佳特征组合
        best_config = self.find_best_feature_combination(df)

        # 保存最佳特征配置（同时保存到 models 和 logs 目录，保持内容一致）
        config_data = {
            "best_config": best_config,
            "validation_history": self.validation_history[-5:],  # 只保存最近5次验证结果
            "last_updated": datetime.now().isoformat(),
        }
        try:
            import json

            for config_dir in [MODELS_DIR, LOGS_DIR]:
                config_path = config_dir / "best_feature_config.json"
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                logger.info(f"最佳特征配置已保存到: {config_path}")
        except Exception as e:
            logger.error(f"保存最佳特征配置失败: {e}")

        return {"success": True, "best_config": best_config, "validation_history": self.validation_history[-1:]}


if __name__ == "__main__":
    # 测试动态特征验证器
    validator = DynamicFeatureValidator()
    result = validator.validate_and_update_features()
    print(f"验证结果: {result}")
