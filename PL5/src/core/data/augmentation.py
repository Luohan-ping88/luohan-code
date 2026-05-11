"""
数据增强模块
  - SMOTE（合成少数类过采样技术）
  - 随机采样
  - 特征扰动
  - 时间序列数据增强
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any
from imblearn.over_sampling import SMOTE
from sklearn.utils import resample
import warnings
from pathlib import Path
from ..utils.logger import logger

warnings.filterwarnings("ignore")


class DataAugmenter:
    """数据增强器"""

    def __init__(self):
        self.augmented_data = []

    def smote_augmentation(
        self, X: np.ndarray, y: np.ndarray, sampling_strategy: str = "auto", k_neighbors: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """使用SMOTE技术进行数据增强"""
        try:
            # 确保y是一维数组
            if len(y.shape) > 1:
                y = y.flatten()

            smote = SMOTE(sampling_strategy=sampling_strategy, k_neighbors=k_neighbors, random_state=42)
            X_resampled, y_resampled = smote.fit_resample(X, y)
            logger.info(f"SMOTE增强完成，原始样本数: {len(X)}, 增强后样本数: {len(X_resampled)}")
            return X_resampled, y_resampled
        except ImportError:
            logger.warning("imbalanced-learn库未安装，跳过SMOTE增强")
            return X, y
        except Exception as e:
            logger.error(f"SMOTE增强失败: {e}")
            return X, y

    def random_oversampling(
        self, X: np.ndarray, y: np.ndarray, sampling_strategy: Dict = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """随机过采样"""
        logger.info(f"随机过采样前样本数: {len(X)}")

        if sampling_strategy is None:
            # 默认对所有类别进行过采样，使每个类别的样本数达到最大值
            unique_classes, class_counts = np.unique(y, return_counts=True)
            max_count = np.max(class_counts)
            sampling_strategy = {cls: max_count for cls in unique_classes}

        # 对每个类别进行过采样
        X_resampled = []
        y_resampled = []

        for cls, target_count in sampling_strategy.items():
            # 获取该类别的样本
            X_cls = X[y == cls]
            y_cls = y[y == cls]

            # 如果样本数不足，进行过采样
            if len(X_cls) < target_count:
                # 计算需要的样本数
                n_samples = target_count - len(X_cls)
                # 过采样
                X_cls_resampled, y_cls_resampled = resample(
                    X_cls, y_cls, replace=True, n_samples=n_samples, random_state=42
                )
                # 合并原始样本和过采样样本
                X_resampled.extend(X_cls)
                X_resampled.extend(X_cls_resampled)
                y_resampled.extend(y_cls)
                y_resampled.extend(y_cls_resampled)
            else:
                # 样本数足够，直接使用
                X_resampled.extend(X_cls)
                y_resampled.extend(y_cls)

        X_resampled = np.array(X_resampled)
        y_resampled = np.array(y_resampled)

        logger.info(f"随机过采样后样本数: {len(X_resampled)}")
        return X_resampled, y_resampled

    def feature_perturbation(
        self, X: np.ndarray, y: np.ndarray, perturbation_rate: float = 0.1, perturbation_std: float = 0.05
    ) -> Tuple[np.ndarray, np.ndarray]:
        """特征扰动增强"""
        logger.info(f"特征扰动增强，扰动率: {perturbation_rate}, 扰动标准差: {perturbation_std}")

        # 复制原始数据
        X_perturbed = X.copy()
        y_perturbed = y.copy()

        # 对每个样本进行扰动
        for i in range(len(X_perturbed)):
            # 随机选择要扰动的特征
            n_features = X_perturbed.shape[1]
            n_perturb = int(n_features * perturbation_rate)
            perturb_indices = np.random.choice(n_features, n_perturb, replace=False)

            # 对选中的特征添加高斯噪声
            for j in perturb_indices:
                std_dev = perturbation_std * (abs(X_perturbed[i, j]) + 1e-10)
                noise = np.random.normal(0, std_dev)
                X_perturbed[i, j] += noise

        logger.info(f"特征扰动增强完成，样本数: {len(X_perturbed)}")
        return X_perturbed, y_perturbed

    def time_series_augmentation(self, df: pd.DataFrame, position: str, n_augment: int = 100) -> pd.DataFrame:
        """时间序列数据增强"""
        logger.info(f"时间序列数据增强，位置: {position}, 增强样本数: {n_augment}")

        # 获取原始时间序列数据
        original_series = df[position].values

        # 生成增强数据
        augmented_series = []

        for i in range(n_augment):
            # 随机选择一个起始点
            start_idx = np.random.randint(0, len(original_series) - 10)
            # 随机选择一个长度
            length = np.random.randint(5, 15)
            # 截取子序列
            sub_series = original_series[start_idx : start_idx + length]

            # 添加高斯噪声
            noise = np.random.normal(0, 0.1, len(sub_series))
            augmented_sub_series = sub_series + noise
            # 确保值在0-9之间
            augmented_sub_series = np.clip(augmented_sub_series, 0, 9)
            # 四舍五入到整数
            augmented_sub_series = np.round(augmented_sub_series).astype(int)

            augmented_series.extend(augmented_sub_series)

        # 创建增强数据的DataFrame
        augmented_df = pd.DataFrame({position: augmented_series})

        # 添加其他位置的随机数据
        other_positions = ["wan", "qian", "bai", "shi", "ge"]
        other_positions.remove(position)

        for pos in other_positions:
            augmented_df[pos] = np.random.randint(0, 10, len(augmented_series))

        logger.info(f"时间序列数据增强完成，增强样本数: {len(augmented_df)}")
        return augmented_df

    def augment_data(
        self, df: pd.DataFrame, feature_cols: List[str], target_cols: List[str], augmentation_config: Dict = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """综合数据增强"""
        logger.info("开始综合数据增强...")

        if augmentation_config is None:
            augmentation_config = {
                "smote": True,
                "random_oversampling": True,
                "feature_perturbation": True,
                "time_series_augmentation": True,
                "n_augment": 500,
            }

        # 准备特征和目标数据
        X = df[feature_cols].values
        y_list = []

        # 对每个目标列进行数据增强
        for target_col in target_cols:
            y = df[target_col].values

            # 应用SMOTE
            if augmentation_config.get("smote", False):
                X, y = self.smote_augmentation(X, y)

            # 应用随机过采样
            if augmentation_config.get("random_oversampling", False):
                X, y = self.random_oversampling(X, y)

            # 应用特征扰动
            if augmentation_config.get("feature_perturbation", False):
                X = self.feature_perturbation(X)

            # 应用时间序列数据增强
            if augmentation_config.get("time_series_augmentation", False):
                augmented_df = self.time_series_augmentation(df, target_col, augmentation_config.get("n_augment", 500))
                # 提取特征
                augmented_X = augmented_df[feature_cols].values
                augmented_y = augmented_df[target_col].values
                # 合并数据
                X = np.vstack([X, augmented_X])
                y = np.concatenate([y, augmented_y])

            y_list.append(y)

        logger.info(f"综合数据增强完成，特征维度: {X.shape}, 目标维度: {[len(y) for y in y_list]}")
        return X, y_list
