"""
智能动态多特征组合融合器 V11
核心设计理念：
1. 动态生成多个特征组合（基于数据漂移、特征相关性、周期性等）
2. 使用多特征组合分别训练模型
3. 根据历史表现动态调整各组合的融合权重
4. 智能融合多个特征组合的预测结果

用户期望的智能机制：
- 系统通过数据变化，在训练过程中智能动态选择多个特征组合
- 用不同特征组合验证训练预测效果
- 最终预测中融合多个动态特征组合来生成预测结果
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import joblib
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif

from src.core.utils.logger import get_logger

logger = get_logger("MultiFeatureFusion")

POSITIONS = ["wan", "qian", "bai", "shi", "ge"]


class FeatureCombination:
    """单个特征组合"""

    def __init__(self, name: str, features: List[str], priority: float = 1.0):
        self.name = name
        self.features = features
        self.priority = priority  # 动态调整的优先级
        self.model = None
        self.performance_history = []  # 历史表现记录
        self.hit_rate = 0.0  # 命中率

    def update_performance(self, hit: bool, period: str):
        """更新特征组合的表现"""
        self.performance_history.append(
            {
                "period": period,
                "hit": hit,
                "timestamp": datetime.now().isoformat(),
            }
        )
        # 只保留最近20期的记录
        if len(self.performance_history) > 20:
            self.performance_history.pop(0)
        # 计算最新命中率
        if self.performance_history:
            hits = sum(1 for p in self.performance_history if p["hit"])
            self.hit_rate = hits / len(self.performance_history)

    def get_adaptive_weight(self) -> float:
        """根据历史表现计算自适应权重"""
        if not self.performance_history:
            return self.priority
        # 使用指数加权移动平均，近期表现权重更高
        weights = []
        for i, perf in enumerate(self.performance_history[-10:]):
            weight = (1.5**i) * (1.0 if perf["hit"] else 0.3)
            weights.append(weight)
        return sum(weights) / len(weights) if weights else self.priority


class DynamicFeatureSelector:
    """动态特征选择器 - 根据数据特征智能生成特征组合"""

    def __init__(self, max_combinations: int = 5):
        self.max_combinations = max_combinations
        self.base_feature_groups = {
            "fibonacci": [],  # 斐波那契特征
            "markov": [],  # 马尔可夫特征
            "fourier": [],  # 傅里叶特征
            "extreme": [],  # 极值特征
            "pattern": [],  # 模式特征
            "momentum": [],  # 动量特征
            "statistical": [],  # 统计特征
        }

    def analyze_data(
        self, df: pd.DataFrame, all_features: List[str]
    ) -> List[FeatureCombination]:
        """
        分析数据特征，智能生成多个特征组合

        Returns:
            List[FeatureCombination]: 多个特征组合
        """
        combinations = []

        # 方法1: 基于特征类型分组
        combinations.extend(self._group_by_feature_type(all_features))

        # 方法2: 基于位置分组（万位、千位等）
        combinations.extend(self._group_by_position(all_features))

        # 方法3: 基于时间窗口分组
        combinations.extend(self._group_by_time_window(all_features))

        # 方法4: 高相关性特征组合
        combinations.extend(self._group_by_correlation(df, all_features))

        # 去重并限制数量
        seen = set()
        unique_combos = []
        for combo in combinations:
            key = tuple(sorted(combo.features))
            if key not in seen:
                seen.add(key)
                unique_combos.append(combo)

        # 限制最大组合数
        if len(unique_combos) > self.max_combinations:
            # 按优先级排序，取前N个
            unique_combos.sort(key=lambda x: x.priority, reverse=True)
            unique_combos = unique_combos[: self.max_combinations]

        logger.info(f"[智能特征选择] 生成了 {len(unique_combos)} 个特征组合")
        for combo in unique_combos:
            logger.info(
                f"  - {combo.name}: {len(combo.features)} 个特征, 优先级={combo.priority:.2f}"
            )

        return unique_combos

    def _group_by_feature_type(
        self, features: List[str]
    ) -> List[FeatureCombination]:
        """按特征类型分组"""
        groups = defaultdict(list)
        for f in features:
            for ft in self.base_feature_groups.keys():
                if ft in f.lower():
                    groups[ft].append(f)
                    break

        combos = []
        for name, feats in groups.items():
            if feats:
                combos.append(
                    FeatureCombination(
                        name=f"类型_{name}",
                        features=feats,
                        priority=len(feats) / 10.0,  # 特征越多优先级越高
                    )
                )
        return combos

    def _group_by_position(
        self, features: List[str]
    ) -> List[FeatureCombination]:
        """按位置分组（万位特征、千位特征等）"""
        groups = defaultdict(list)
        for f in features:
            for pos in POSITIONS:
                if f.startswith(pos + "_"):
                    groups[pos].append(f)
                    break

        combos = []
        for pos, feats in groups.items():
            if feats:
                combos.append(
                    FeatureCombination(
                        name=f"位置_{pos}", features=feats, priority=1.2
                    )  # 位置特征优先级较高
                )
        return combos

    def _group_by_time_window(
        self, features: List[str]
    ) -> List[FeatureCombination]:
        """按时序窗口分组（短期、中期、长期）"""
        windows = {
            "短期": [3, 5, 7, 10],
            "中期": [15, 20, 30],
            "长期": [50, 100],
        }

        combos = []
        for window_type, values in windows.items():
            window_features = []
            for f in features:
                for w in values:
                    if f"_{w}" in f or f"_{w}_" in f:
                        window_features.append(f)
                        break

            if window_features:
                combos.append(
                    FeatureCombination(
                        name=f"时序_{window_type}",
                        features=list(set(window_features)),
                        priority=1.0,
                    )
                )
        return combos

    def _group_by_correlation(
        self, df: pd.DataFrame, features: List[str]
    ) -> List[FeatureCombination]:
        """基于特征相关性分组"""
        # 选择目标变量
        target_cols = [c for c in df.columns if c in POSITIONS]
        if not target_cols or len(features) < 10:
            return []

        combos = []
        # 计算与目标变量的互信息
        try:
            X = df[features].fillna(0)
            y = df[target_cols[0]]

            mi_scores = mutual_info_classif(X, y, random_state=42)
            mi_dict = dict(zip(features, mi_scores))

            # 选择互信息最高的特征
            sorted_features = sorted(
                mi_dict.items(), key=lambda x: x[1], reverse=True
            )

            # 分成高、中、低相关三组
            n = len(sorted_features) // 3
            if n > 0:
                high_corr = [f for f, _ in sorted_features[:n]]
                mid_corr = [f for f, _ in sorted_features[n : 2 * n]]
                low_corr = [f for f, _ in sorted_features[2 * n :]]

                combos.append(
                    FeatureCombination("高相关", high_corr, priority=1.5)
                )
                combos.append(
                    FeatureCombination("中相关", mid_corr, priority=1.0)
                )
                if low_corr:
                    combos.append(
                        FeatureCombination("低相关", low_corr, priority=0.5)
                    )
        except Exception as e:
            logger.warning(f"相关性分析失败: {e}")

        return combos


class MultiFeatureFusionPredictor:
    """
    智能动态多特征组合融合预测器 V11

    核心功能：
    1. 动态生成多个特征组合
    2. 使用多特征组合分别训练模型
    3. 动态调整融合权重
    4. 智能融合预测结果
    5. 模型缓存和持久化（优化后）
    """

    MODEL_CACHE_FILE = "models/multi_feature_fusion_cache.joblib"

    def __init__(self, max_combinations: int = 5):
        self.max_combinations = max_combinations
        self.feature_selector = DynamicFeatureSelector(max_combinations)
        self.feature_combinations: List[FeatureCombination] = []
        self.models: Dict[str, Any] = {}  # 组合名 -> 模型
        self.position_models: Dict[str, Dict[str, Any]] = (
            {}
        )  # 位置 -> 组合名 -> 模型
        self.is_trained = False
        self.training_history = []
        self._cache_info = {
            "trained_at": None,
            "data_periods": 0,
            "n_combinations": 0,
        }

    def _clean_data(
        self, df: pd.DataFrame, features: List[str]
    ) -> Tuple[np.ndarray, List[str]]:
        """清洗数据，移除无穷大值和非有限值"""
        valid_features = []
        for f in features:
            if f in df.columns:
                if np.isfinite(df[f]).all():
                    valid_features.append(f)
                else:
                    logger.debug(f"跳过无效特征: {f}")

        if not valid_features:
            return np.array([]), []

        X = df[valid_features].fillna(0).values
        X = np.where(np.isfinite(X), X, 0)
        X = np.clip(X, -1e10, 1e10)

        return X, valid_features

    def save_model(self, filepath: str = None):
        """保存模型到文件"""
        if filepath is None:
            filepath = self.MODEL_CACHE_FILE

        cache_data = {
            "position_models": {},
            "feature_combinations_data": [],
            "training_history": self.training_history,
            "cache_info": self._cache_info,
            "is_trained": self.is_trained,
            "max_combinations": self.max_combinations,
        }

        for pos, pos_models in self.position_models.items():
            cache_data["position_models"][pos] = {}
            for combo_name, model_info in pos_models.items():
                combo = model_info["combination"]
                cache_data["position_models"][pos][combo_name] = {
                    "model": model_info["model"],
                    "features": model_info["features"],
                    "combo_name": combo.name,
                    "combo_priority": combo.priority,
                    "combo_hit_rate": combo.hit_rate,
                    "combo_performance_history": combo.performance_history,
                }

        for combo in self.feature_combinations:
            cache_data["feature_combinations_data"].append(
                {
                    "name": combo.name,
                    "features": combo.features,
                    "priority": combo.priority,
                    "hit_rate": combo.hit_rate,
                    "performance_history": combo.performance_history,
                }
            )

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(cache_data, filepath)
        logger.info(f"[MFF] 模型已保存: {filepath}")

    def load_model(self, filepath: str = None) -> bool:
        """从文件加载模型"""
        if filepath is None:
            filepath = self.MODEL_CACHE_FILE

        if not Path(filepath).exists():
            logger.info(f"[MFF] 缓存模型不存在: {filepath}")
            return False

        try:
            cache_data = joblib.load(filepath)

            self.is_trained = cache_data.get("is_trained", False)
            self.max_combinations = cache_data.get("max_combinations", 5)
            self.training_history = cache_data.get("training_history", [])
            self._cache_info = cache_data.get("cache_info", {})

            self.feature_combinations = []
            for combo_data in cache_data.get("feature_combinations_data", []):
                combo = FeatureCombination(
                    name=combo_data["name"],
                    features=combo_data["features"],
                    priority=combo_data.get("priority", 1.0),
                )
                combo.hit_rate = combo_data.get("hit_rate", 0.0)
                combo.performance_history = combo_data.get(
                    "performance_history", []
                )
                self.feature_combinations.append(combo)

            self.position_models = {}
            for pos, pos_models in cache_data.get(
                "position_models", {}
            ).items():
                self.position_models[pos] = {}
                for combo_name, model_info in pos_models.items():
                    combo = None
                    for c in self.feature_combinations:
                        if c.name == combo_name:
                            combo = c
                            break
                    if combo is None:
                        combo = FeatureCombination(
                            name=model_info["combo_name"],
                            features=model_info["features"],
                            priority=model_info.get("combo_priority", 1.0),
                        )

                    self.position_models[pos][combo_name] = {
                        "model": model_info["model"],
                        "features": model_info["features"],
                        "combination": combo,
                    }

            logger.info(f"[MFF] 模型已加载: {filepath}")
            logger.info(
                f"  训练时间: {self._cache_info.get('trained_at', '未知')}"
            )
            logger.info(f"  特征组合数: {len(self.feature_combinations)}")
            return True

        except Exception as e:
            logger.error(f"[MFF] 加载模型失败: {e}")
            return False

    def is_cache_valid(
        self, data_periods: int = 0, max_age_hours: int = 24
    ) -> bool:
        """检查缓存是否有效"""
        if not Path(self.MODEL_CACHE_FILE).exists():
            return False

        if not self.is_trained:
            return False

        cache_time = Path(self.MODEL_CACHE_FILE).stat().st_mtime
        cache_age_hours = (time.time() - cache_time) / 3600

        if cache_age_hours > max_age_hours:
            logger.info(
                f"[MFF] 缓存过期: {cache_age_hours:.1f}小时 > {max_age_hours}小时"
            )
            return False

        if (
            data_periods > 0
            and self._cache_info.get("data_periods", 0) < data_periods
        ):
            logger.info(f"[MFF] 数据量增加，需要重新训练")
            return False

        return True

    def fit(
        self,
        df: pd.DataFrame,
        all_features: List[str],
        recent_periods: int = 100,
        save_cache: bool = True,
    ):
        """
        使用多特征组合训练模型

        Args:
            df: 包含特征和目标变量的数据
            all_features: 所有可用特征
            recent_periods: 用于训练的历史期数
        """
        logger.info("[MultiFeatureFusion] 开始多特征组合训练...")

        # 使用最近N期数据进行训练
        train_df = df.tail(recent_periods)

        # 清洗所有特征数据，保留共同的有效特征
        valid_all_features = []
        for f in all_features:
            if f in df.columns and np.isfinite(df[f]).all():
                valid_all_features.append(f)

        logger.info(f"  有效特征数: {len(valid_all_features)}")

        # 动态生成特征组合（使用清洗后的特征）
        self.feature_combinations = self.feature_selector.analyze_data(
            train_df, valid_all_features
        )

        if not self.feature_combinations:
            logger.warning(
                "[MultiFeatureFusion] 未能生成特征组合，使用默认特征"
            )
            self.feature_combinations = [
                FeatureCombination(
                    "默认",
                    valid_all_features[: min(50, len(valid_all_features))],
                    1.0,
                )
            ]

        # 为每个位置训练多个特征组合的模型
        for pos in POSITIONS:
            self.position_models[pos] = {}
            y = train_df[pos].values

            for combo in self.feature_combinations:
                # 只使用有效特征
                combo_valid_features = [
                    f for f in combo.features if f in valid_all_features
                ]
                if len(combo_valid_features) < 5:
                    continue

                # 提取训练数据
                X = train_df[combo_valid_features].fillna(0).values
                X = np.clip(X, -1e10, 1e10)

                # 训练随机森林模型
                model = RandomForestClassifier(
                    n_estimators=50, max_depth=8, random_state=42, n_jobs=-1
                )
                model.fit(X, y)

                self.position_models[pos][combo.name] = {
                    "model": model,
                    "features": combo_valid_features,  # 保存清洗后的特征列表
                    "combination": combo,
                }

                logger.info(
                    f"  [{pos}] {combo.name}: {len(combo_valid_features)} 个特征训练完成"
                )

        self.is_trained = True
        self.training_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "n_combinations": len(self.feature_combinations),
                "positions": list(POSITIONS),
            }
        )

        self._cache_info = {
            "trained_at": datetime.now().isoformat(),
            "data_periods": len(df),
            "n_combinations": len(self.feature_combinations),
        }

        if save_cache:
            self.save_model()

        logger.info(
            f"[MultiFeatureFusion] 多特征组合训练完成！共 {len(self.feature_combinations)} 个组合"
        )

    def predict(
        self, df: pd.DataFrame, top_k: int = 8
    ) -> Dict[str, Dict[str, Any]]:
        """
        使用多特征组合融合进行预测

        Returns:
            {位置: {'top_k': [...], 'probabilities': [...], 'combination_details': {...}}}
        """
        if not self.is_trained:
            logger.warning("[MultiFeatureFusion] 模型未训练，返回默认预测")
            return {
                pos: {
                    "top_k": list(range(10))[:top_k],
                    "probabilities": [0.1] * top_k,
                    "combination_details": {},
                }
                for pos in POSITIONS
            }

        results = {}

        for pos in POSITIONS:
            if pos not in self.position_models:
                continue

            # 收集所有组合的预测概率
            all_proba = []
            weights = []

            for combo_name, model_info in self.position_models[pos].items():
                model = model_info["model"]
                features = model_info["features"]
                combo = model_info["combination"]

                try:
                    # 使用训练时保存的特征列表
                    X = df[features].fillna(0).iloc[[-1]].values
                    X = np.clip(X, -1e10, 1e10)
                    proba = model.predict_proba(X)[0]
                    all_proba.append(proba)

                    # 获取自适应权重
                    adaptive_weight = combo.get_adaptive_weight()
                    weights.append(adaptive_weight)

                    logger.debug(
                        f"  [{pos}] {combo_name}: weight={adaptive_weight:.3f}, top3={np.argsort(proba)[-3:][::-1]}"
                    )
                except Exception as e:
                    logger.warning(f"  [{pos}] {combo_name} 预测失败: {e}")

            # 加权融合
            if all_proba and weights:
                # 归一化权重
                total_weight = sum(weights)
                normalized_weights = [w / total_weight for w in weights]

                # 加权平均
                fused_proba = np.zeros(10)
                for proba, weight in zip(all_proba, normalized_weights):
                    fused_proba += proba * weight

                # 归一化
                fused_proba = fused_proba / (fused_proba.sum() + 1e-12)

                # 获取Top-K
                top_indices = np.argsort(fused_proba)[::-1][:top_k]

                # 构建组合详情
                combo_details = {}
                for i, (combo_name, model_info) in enumerate(
                    self.position_models[pos].items()
                ):
                    combo = model_info["combination"]
                    combo_details[combo_name] = {
                        "weight": (
                            normalized_weights[i]
                            if i < len(normalized_weights)
                            else 0
                        ),
                        "hit_rate": combo.hit_rate,
                        "n_features": len(model_info["features"]),
                    }

                results[pos] = {
                    "top_k": top_indices.tolist(),
                    "probabilities": [
                        float(fused_proba[i]) for i in top_indices
                    ],
                    "fused_proba": fused_proba.tolist(),
                    "combination_details": combo_details,
                    "n_combinations_used": len(all_proba),
                }
            else:
                # 回退
                results[pos] = {
                    "top_k": list(range(10))[:top_k],
                    "probabilities": [0.1] * top_k,
                    "combination_details": {},
                }

        return results

    def update_with_result(self, period: str, actual_numbers: Dict[str, int]):
        """
        根据实际开奖结果更新各特征组合的表现

        Args:
            period: 期号
            actual_numbers: {位置: 开奖号码}
        """
        for pos, num in actual_numbers.items():
            if pos not in self.position_models:
                continue

            for combo_name, model_info in self.position_models[pos].items():
                combo = model_info["combination"]
                model = model_info["model"]

                try:
                    features = model_info["features"]
                    # 预测最新一期
                    # 注意：这里需要传入包含最新特征的数据框
                    # 简化版本：直接检查是否命中
                    hit = False  # 实际实现需要更复杂的逻辑
                    combo.update_performance(hit, period)
                except Exception as e:
                    logger.warning(f"更新表现失败 [{pos}][{combo_name}]: {e}")

        logger.info(f"[MultiFeatureFusion] 已更新期号 {period} 的预测表现")

    def get_intelligent_summary(self) -> Dict[str, Any]:
        """获取智能融合摘要"""
        summary = {
            "n_combinations": len(self.feature_combinations),
            "is_trained": self.is_trained,
            "combinations": [],
        }

        for combo in self.feature_combinations:
            summary["combinations"].append(
                {
                    "name": combo.name,
                    "n_features": len(combo.features),
                    "hit_rate": combo.hit_rate,
                    "adaptive_weight": combo.get_adaptive_weight(),
                    "recent_performance": (
                        combo.performance_history[-5:]
                        if combo.performance_history
                        else []
                    ),
                }
            )

        return summary


def create_multi_feature_predictor() -> MultiFeatureFusionPredictor:
    """工厂函数：创建多特征融合预测器"""
    return MultiFeatureFusionPredictor(max_combinations=5)
