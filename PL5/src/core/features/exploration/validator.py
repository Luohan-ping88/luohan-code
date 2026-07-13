"""
新特征验证器
对新发现的特征进行全面验证和评估
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
import logging
from pathlib import Path
import pickle
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import r2_score, accuracy_score, roc_auc_score
from scipy.stats import pearsonr, spearmanr

logger = logging.getLogger(__name__)


class FeatureValidator:
    """新特征验证器"""

    def __init__(
        self,
        correlation_threshold: float = 0.9,
        stability_threshold: float = 0.8,
        min_performance_improvement: float = 0.01,
        random_state: int = 42
    ):
        self.correlation_threshold = correlation_threshold
        self.stability_threshold = stability_threshold
        self.min_performance_improvement = min_performance_improvement
        self.random_state = random_state

        self.validation_results: Dict[str, Dict[str, Any]] = {}
        self.baseline_performance: Optional[float] = None

    def validate_all(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        new_features: List[str],
        existing_features: Optional[List[str]] = None,
        model: Optional[BaseEstimator] = None
    ) -> Dict[str, Any]:
        """
        完整验证所有新特征

        Args:
            X: 特征数据（包含新特征和现有特征）
            y: 目标变量
            new_features: 新特征名称列表
            existing_features: 现有特征名称列表，默认从X中自动识别
            model: 可选的评估模型

        Returns:
            验证结果
        """
        if existing_features is None:
            existing_features = [col for col in X.columns if col not in new_features]

        results = {
            'correlation_analysis': self.analyze_correlation(X, new_features, existing_features),
            'stability_test': self.test_stability(X, y, new_features, model),
            'performance_evaluation': self.evaluate_performance(
                X, y, new_features, existing_features, model
            ),
            'integration_decision': {}
        }

        results['integration_decision'] = self.make_integration_decision(results)

        for feature in new_features:
            self.validation_results[feature] = {
                'correlation': results['correlation_analysis'].get(feature, {}),
                'stability': results['stability_test'].get(feature, {}),
                'performance': results['performance_evaluation'].get(feature, {}),
                'accepted': results['integration_decision'].get(feature, False)
            }

        return results

    def analyze_correlation(
        self,
        X: pd.DataFrame,
        new_features: List[str],
        existing_features: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        特征相关性分析

        Args:
            X: 特征数据
            new_features: 新特征列表
            existing_features: 现有特征列表

        Returns:
            相关性分析结果
        """
        results = {}

        for feature in new_features:
            if feature not in X.columns:
                continue

            feature_data = X[feature].fillna(0)
            max_corr = 0.0
            most_correlated = None
            correlations = []

            for existing_feature in existing_features:
                if existing_feature not in X.columns:
                    continue

                existing_data = X[existing_feature].fillna(0)

                try:
                    pearson_corr, _ = pearsonr(feature_data, existing_data)
                    spearman_corr, _ = spearmanr(feature_data, existing_data)
                    abs_corr = max(abs(pearson_corr), abs(spearman_corr))

                    correlations.append({
                        'feature': existing_feature,
                        'pearson': pearson_corr,
                        'spearman': spearman_corr
                    })

                    if abs_corr > max_corr:
                        max_corr = abs_corr
                        most_correlated = existing_feature
                except Exception:
                    continue

            correlations_sorted = sorted(
                correlations,
                key=lambda x: abs(x['pearson']),
                reverse=True
            )[:5]

            results[feature] = {
                'max_correlation': max_corr,
                'most_correlated_feature': most_correlated,
                'top_correlations': correlations_sorted,
                'high_correlation_warning': max_corr > self.correlation_threshold
            }

        return results

    def test_stability(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        new_features: List[str],
        model: Optional[BaseEstimator] = None,
        n_splits: int = 5
    ) -> Dict[str, Dict[str, Any]]:
        """
        特征稳定性测试

        Args:
            X: 特征数据
            y: 目标变量
            new_features: 新特征列表
            model: 可选的评估模型
            n_splits: 交叉验证折数

        Returns:
            稳定性测试结果
        """
        results = {}

        for feature in new_features:
            if feature not in X.columns:
                continue

            feature_data = X[feature].fillna(0).values.reshape(-1, 1)

            if model is None:
                is_classification = len(np.unique(y)) <= 10
                if is_classification:
                    model = RandomForestClassifier(
                        n_estimators=50,
                        max_depth=5,
                        random_state=self.random_state,
                        n_jobs=-1
                    )
                else:
                    model = RandomForestRegressor(
                        n_estimators=50,
                        max_depth=5,
                        random_state=self.random_state,
                        n_jobs=-1
                    )

            scores = cross_val_score(model, feature_data, y, cv=n_splits, n_jobs=-1)

            mean_score = scores.mean()
            std_score = scores.std()
            cv = std_score / (mean_score + 1e-10)

            stability_score = 1.0 - min(cv, 1.0)

            results[feature] = {
                'mean_score': mean_score,
                'std_score': std_score,
                'coefficient_of_variation': cv,
                'stability_score': stability_score,
                'stable': stability_score >= self.stability_threshold,
                'all_scores': scores.tolist()
            }

        return results

    def evaluate_performance(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        new_features: List[str],
        existing_features: List[str],
        model: Optional[BaseEstimator] = None,
        test_size: float = 0.3
    ) -> Dict[str, Dict[str, Any]]:
        """
        特征性能评估

        Args:
            X: 特征数据
            y: 目标变量
            new_features: 新特征列表
            existing_features: 现有特征列表
            model: 可选的评估模型
            test_size: 测试集比例

        Returns:
            性能评估结果
        """
        results = {}

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state
        )

        existing_cols = [col for col in existing_features if col in X.columns]

        if model is None:
            is_classification = len(np.unique(y)) <= 10
            if is_classification:
                model = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=8,
                    random_state=self.random_state,
                    n_jobs=-1
                )
            else:
                model = RandomForestRegressor(
                    n_estimators=100,
                    max_depth=8,
                    random_state=self.random_state,
                    n_jobs=-1
                )

        if existing_cols:
            model.fit(X_train[existing_cols].fillna(0), y_train)
            baseline_pred = model.predict(X_test[existing_cols].fillna(0))

            if len(np.unique(y)) <= 10:
                self.baseline_performance = accuracy_score(y_test, baseline_pred)
            else:
                self.baseline_performance = r2_score(y_test, baseline_pred)
        else:
            self.baseline_performance = 0.0

        for feature in new_features:
            if feature not in X.columns:
                continue

            all_features = existing_cols + [feature]
            all_features = [col for col in all_features if col in X.columns]

            model.fit(X_train[all_features].fillna(0), y_train)
            predictions = model.predict(X_test[all_features].fillna(0))

            if len(np.unique(y)) <= 10:
                performance = accuracy_score(y_test, predictions)
                metric_name = 'accuracy'
            else:
                performance = r2_score(y_test, predictions)
                metric_name = 'r2'

            improvement = performance - self.baseline_performance

            results[feature] = {
                'metric': metric_name,
                'baseline_performance': self.baseline_performance,
                'new_performance': performance,
                'improvement': improvement,
                'relative_improvement': improvement / (self.baseline_performance + 1e-10),
                'significant_improvement': improvement >= self.min_performance_improvement
            }

        return results

    def make_integration_decision(
        self,
        validation_results: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        特征集成决策

        Args:
            validation_results: 验证结果

        Returns:
            每个特征是否被接受的决策
        """
        decisions = {}

        correlation_results = validation_results.get('correlation_analysis', {})
        stability_results = validation_results.get('stability_test', {})
        performance_results = validation_results.get('performance_evaluation', {})

        all_features = set(correlation_results.keys())
        all_features.update(stability_results.keys())
        all_features.update(performance_results.keys())

        for feature in all_features:
            corr_res = correlation_results.get(feature, {})
            stab_res = stability_results.get(feature, {})
            perf_res = performance_results.get(feature, {})

            low_correlation = not corr_res.get('high_correlation_warning', False)
            stable = stab_res.get('stable', False)
            good_performance = perf_res.get('significant_improvement', False)

            score = 0
            if low_correlation:
                score += 1
            if stable:
                score += 1
            if good_performance:
                score += 1

            decisions[feature] = score >= 2

        return decisions

    def get_accepted_features(self) -> List[str]:
        """获取被接受的特征列表"""
        return [
            feature for feature, result in self.validation_results.items()
            if result.get('accepted', False)
        ]

    def get_feature_report(self, feature: str) -> Optional[str]:
        """获取单个特征的详细报告"""
        if feature not in self.validation_results:
            return None

        result = self.validation_results[feature]
        report = []
        report.append(f"=== 特征验证报告: {feature} ===")
        report.append(f"状态: {'接受' if result['accepted'] else '拒绝'}")
        report.append("")

        corr = result.get('correlation', {})
        report.append("[相关性分析]")
        report.append(f"  最大相关性: {corr.get('max_correlation', 0):.4f}")
        report.append(f"  最相关特征: {corr.get('most_correlated_feature', 'N/A')}")
        report.append(f"  高相关性警告: {'是' if corr.get('high_correlation_warning', False) else '否'}")
        report.append("")

        stab = result.get('stability', {})
        report.append("[稳定性测试]")
        report.append(f"  稳定性分数: {stab.get('stability_score', 0):.4f}")
        report.append(f"  平均性能: {stab.get('mean_score', 0):.4f}")
        report.append(f"  标准差: {stab.get('std_score', 0):.4f}")
        report.append(f"  稳定: {'是' if stab.get('stable', False) else '否'}")
        report.append("")

        perf = result.get('performance', {})
        report.append("[性能评估]")
        report.append(f"  基线性能: {perf.get('baseline_performance', 0):.4f}")
        report.append(f"  新性能: {perf.get('new_performance', 0):.4f}")
        report.append(f"  提升: {perf.get('improvement', 0):.4f}")
        report.append(f"  相对提升: {perf.get('relative_improvement', 0):.2%}")
        report.append(f"  显著提升: {'是' if perf.get('significant_improvement', False) else '否'}")

        return "\n".join(report)

    def save(self, filepath: Path):
        """保存验证器状态"""
        data = {
            'correlation_threshold': self.correlation_threshold,
            'stability_threshold': self.stability_threshold,
            'min_performance_improvement': self.min_performance_improvement,
            'random_state': self.random_state,
            'validation_results': self.validation_results,
            'baseline_performance': self.baseline_performance
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"特征验证器已保存: {filepath}")

    def load(self, filepath: Path):
        """加载验证器状态"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        self.correlation_threshold = data['correlation_threshold']
        self.stability_threshold = data['stability_threshold']
        self.min_performance_improvement = data['min_performance_improvement']
        self.random_state = data['random_state']
        self.validation_results = data['validation_results']
        self.baseline_performance = data['baseline_performance']

        logger.info(f"特征验证器已加载: {filepath}")
