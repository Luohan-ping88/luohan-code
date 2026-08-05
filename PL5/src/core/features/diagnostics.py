#!/usr/bin/env python3
"""
特征与数据诊断模块 V10.8

针对用户提出的三个增强方向提供统一诊断接口：
1. 特征空间覆盖度诊断：基于 PCA 主成分覆盖率和有效秩
2. 样本量充足性分析：样本量-准确率饱和曲线
3. 频域特征挖掘：BSTS 频谱分解增强输出

设计原则：
- 无副作用：仅做诊断和报告，不修改训练流程
- 可选接入：日循环任务可选择是否调用
- 报告落盘：结果以 JSON 形式写入 LOGS_DIR，便于追踪
"""

import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.core.config import LOGS_DIR

logger = logging.getLogger(__name__)


class FeatureSpaceDiagnostics:
    """特征空间覆盖度诊断：基于 PCA 主成分覆盖率和有效秩。

    核心问题：特征数量多 ≠ 特征空间覆盖好。100 个高度相关的特征
    实际可能只覆盖少数几个独立方向。本诊断回答：
    - 有效秩（独立方向数）是多少？
    - 前 k 个主成分覆盖了多少方差？
    - 是否存在冗余特征簇？
    """

    def __init__(self, variance_thresholds: Tuple[float, ...] = (0.80, 0.90, 0.95, 0.99)):
        self.variance_thresholds = variance_thresholds

    def diagnose(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> Dict:
        """执行特征空间覆盖度诊断。

        Args:
            X: 特征矩阵 (n_samples, n_features)
            feature_names: 特征名列表（可选）

        Returns:
            诊断结果字典
        """
        from sklearn.preprocessing import StandardScaler
        from sklearn.decomposition import PCA

        n_samples, n_features = X.shape
        logger.info(
            f"[特征诊断] 开始特征空间覆盖度诊断 | "
            f"samples={n_samples} features={n_features}"
        )

        # 标准化（PCA 对尺度敏感）
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 全量 PCA
        pca = PCA(n_components=min(n_samples, n_features))
        pca.fit(X_scaled)
        explained_ratio = pca.explained_variance_ratio_
        cumulative = np.cumsum(explained_ratio)

        # 有效秩：参与 95% 累计方差所需的主成分数
        eff_rank_95 = int(np.searchsorted(cumulative, 0.95) + 1)
        eff_rank_99 = int(np.searchsorted(cumulative, 0.99) + 1)

        # 各阈值对应的主成分数
        thresholds_pc = {}
        for thr in self.variance_thresholds:
            idx = int(np.searchsorted(cumulative, thr) + 1)
            idx = min(idx, len(cumulative))
            thresholds_pc[f"pc_for_{int(thr*100)}pct"] = idx

        # 覆盖率指标：有效秩 / 特征总数
        coverage_ratio = eff_rank_95 / n_features if n_features > 0 else 0.0

        # 冗余诊断：若 eff_rank_95 << n_features，说明大量特征冗余
        redundancy_ratio = 1.0 - coverage_ratio

        # 主成分载荷：识别每个主成分贡献最大的特征
        top_loadings = {}
        if feature_names is not None and len(feature_names) == n_features:
            components = pca.components_
            for i in range(min(5, len(components))):  # 前5个主成分
                loading = np.abs(components[i])
                top_idx = np.argsort(loading)[::-1][:5]
                top_loadings[f"pc{i+1}"] = [
                    {"feature": feature_names[j], "loading": float(loading[j])}
                    for j in top_idx
                ]

        result = {
            "diagnostic_type": "feature_space_coverage",
            "timestamp": datetime.now().isoformat(),
            "n_samples": int(n_samples),
            "n_features": int(n_features),
            "effective_rank_95pct": eff_rank_95,
            "effective_rank_99pct": eff_rank_99,
            "coverage_ratio": float(coverage_ratio),  # 越接近1，特征空间利用越充分
            "redundancy_ratio": float(redundancy_ratio),  # 越接近1，冗余越多
            "explained_variance_top10": [float(x) for x in explained_ratio[:10]],
            "cumulative_variance_top10": [float(x) for x in cumulative[:10]],
            "thresholds_pc_count": thresholds_pc,
            "top_loadings": top_loadings,
            "verdict": self._make_verdict(coverage_ratio, redundancy_ratio, n_features, eff_rank_95),
        }

        logger.info(
            f"[特征诊断] 完成 | 有效秩(95%)={eff_rank_95}/{n_features} | "
            f"覆盖率={coverage_ratio:.2%} | 冗余率={redundancy_ratio:.2%} | "
            f"判定: {result['verdict']['status']}"
        )

        return result

    def _make_verdict(self, coverage: float, redundancy: float,
                      n_features: int, eff_rank: int) -> Dict:
        """生成诊断判定"""
        if coverage >= 0.8:
            status = "good"
            msg = f"特征空间利用充分，{n_features}个特征覆盖{eff_rank}个独立方向"
        elif coverage >= 0.5:
            status = "moderate"
            msg = f"特征空间存在冗余，建议精简至约{eff_rank}个核心特征"
        else:
            status = "poor"
            msg = f"特征空间严重冗余，{n_features}个特征仅覆盖{eff_rank}个独立方向，建议降维"
        return {"status": status, "message": msg, "coverage": float(coverage)}


class SampleSizeDiagnostics:
    """样本量充足性分析：样本量-准确率饱和曲线。

    核心问题：7681 期数据是否足够？还是已经进入"加数据也没用"的饱和区？
    本诊断通过逐步扩大训练集、观察验证准确率是否收敛来回答。
    """

    def __init__(self, min_fraction: float = 0.2, steps: int = 8,
                 random_state: int = 42):
        self.min_fraction = min_fraction
        self.steps = steps
        self.random_state = random_state

    def diagnose(self, X: np.ndarray, y: np.ndarray,
                 estimator=None, cv_folds: int = 3) -> Dict:
        """执行样本量-准确率饱和曲线分析。

        Args:
            X: 特征矩阵
            y: 标签（多位数需自行展平，本方法接受 1D 标签）
            estimator: 可选的分类器，默认 RandomForestClassifier
            cv_folds: 交叉验证折数

        Returns:
            诊断结果字典
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score

        if estimator is None:
            estimator = RandomForestClassifier(
                n_estimators=50, max_depth=8, random_state=self.random_state,
                n_jobs=-1
            )

        n_total = len(X)
        logger.info(
            f"[样本诊断] 开始样本量-准确率饱和曲线分析 | "
            f"total_samples={n_total} steps={self.steps}"
        )

        # 构造训练子集大小序列（等比递增）
        fractions = np.linspace(self.min_fraction, 1.0, self.steps)
        sizes = [int(f * n_total) for f in fractions]

        curve = []
        for size in sizes:
            if size < 100:
                continue
            X_sub = X[:size]
            y_sub = y[:size]
            try:
                scores = cross_val_score(
                    estimator, X_sub, y_sub, cv=min(cv_folds, 3),
                    scoring='accuracy', n_jobs=-1
                )
                acc_mean = float(np.mean(scores))
                acc_std = float(np.std(scores))
            except Exception as e:
                logger.warning(f"[样本诊断] size={size} 评估失败: {e}")
                acc_mean, acc_std = 0.0, 0.0

            curve.append({
                "train_size": int(size),
                "fraction": float(size / n_total),
                "accuracy_mean": acc_mean,
                "accuracy_std": acc_std,
            })
            logger.info(
                f"[样本诊断] size={size} ({size/n_total:.0%}) | "
                f"acc={acc_mean:.4f} ± {acc_std:.4f}"
            )

        # 饱和判定：最后两个点的准确率提升是否 < 1%
        verdict = self._assess_saturation(curve)

        result = {
            "diagnostic_type": "sample_size_saturation",
            "timestamp": datetime.now().isoformat(),
            "total_samples": int(n_total),
            "curve": curve,
            "saturation_verdict": verdict,
        }

        logger.info(
            f"[样本诊断] 完成 | 饱和判定: {verdict['status']} | {verdict['message']}"
        )
        return result

    def _assess_saturation(self, curve: List[Dict]) -> Dict:
        """评估是否已进入饱和区"""
        if len(curve) < 2:
            return {"status": "unknown", "message": "数据点不足，无法判定", "improvement": None}

        last_acc = curve[-1]["accuracy_mean"]
        prev_acc = curve[-2]["accuracy_mean"]
        improvement = last_acc - prev_acc

        if improvement < 0.005:
            status = "saturated"
            msg = f"已进入饱和区，最后增量仅 {improvement:+.4f}，增加样本收益递减"
        elif improvement < 0.02:
            status = "near_saturation"
            msg = f"接近饱和，最后增量 {improvement:+.4f}，可继续收集但收益有限"
        else:
            status = "not_saturated"
            msg = f"未饱和，最后增量 {improvement:+.4f}，增加样本仍有明显收益"

        return {"status": status, "message": msg, "improvement": float(improvement)}


class SpectralDiagnostics:
    """频域特征诊断：BSTS 频谱分解增强输出。

    核心问题：现有 BSTSModel 仅做指数加权频率统计，丢失了周期性信息。
    本诊断对每个位置的时间序列做 FFT 频谱分解，识别主要周期成分，
    为预测提供频域特征支持。
    """

    def __init__(self, top_k_periods: int = 5, min_period: int = 2):
        self.top_k_periods = top_k_periods
        self.min_period = min_period

    def diagnose(self, series_dict: Dict[str, np.ndarray]) -> Dict:
        """对多个位置的时间序列做频谱分解。

        Args:
            series_dict: {position_name: 1D array} 如 {'wan': array([7,0,8,...])}

        Returns:
            诊断结果字典
        """
        logger.info(
            f"[频域诊断] 开始 BSTS 频谱分解 | positions={list(series_dict.keys())}"
        )

        positions_result = {}
        for pos, series in series_dict.items():
            series = np.asarray(series, dtype=float).ravel()
            if len(series) < 32:
                logger.warning(f"[频域诊断] {pos} 数据过短({len(series)}),跳过")
                positions_result[pos] = {"error": "data too short"}
                continue

            spectrum = self._compute_spectrum(series)
            top_periods = self._extract_top_periods(spectrum, len(series))
            spectral_entropy = self._spectral_entropy(spectrum)

            positions_result[pos] = {
                "n_samples": int(len(series)),
                "dominant_periods": top_periods,
                "spectral_entropy": float(spectral_entropy),
                "spectral_flatness": float(self._spectral_flatness(spectrum)),
                "verdict": self._spectral_verdict(spectral_entropy, top_periods),
            }

            logger.info(
                f"[频域诊断] {pos} | 主周期={top_periods[:3]} | "
                f"谱熵={spectral_entropy:.4f} | "
                f"判定: {positions_result[pos]['verdict']['status']}"
            )

        result = {
            "diagnostic_type": "spectral_decomposition",
            "timestamp": datetime.now().isoformat(),
            "positions": positions_result,
        }
        return result

    def _compute_spectrum(self, series: np.ndarray) -> np.ndarray:
        """计算单边功率谱密度"""
        # 去均值
        series = series - series.mean()
        # FFT
        fft = np.fft.rfft(series)
        power = np.abs(fft) ** 2
        # 归一化
        if power.sum() > 0:
            power = power / power.sum()
        return power

    def _extract_top_periods(self, spectrum: np.ndarray, n: int) -> List[Dict]:
        """提取主要周期成分"""
        # 跳过 DC 分量（index 0）
        valid = spectrum[1:]
        if len(valid) == 0:
            return []

        top_idx = np.argsort(valid)[::-1][:self.top_k_periods]
        periods = []
        for idx in top_idx:
            freq = (idx + 1) / n  # 归一化频率
            if freq < 1e-6:
                continue
            period = 1.0 / freq
            if period < self.min_period:
                continue
            periods.append({
                "period": float(period),
                "power": float(valid[idx]),
                "frequency": float(freq),
            })
        return periods

    def _spectral_entropy(self, spectrum: np.ndarray) -> float:
        """谱熵：衡量频谱集中度。越低=越集中（有明确周期），越高=越白噪声"""
        valid = spectrum[1:]
        if len(valid) == 0 or valid.sum() == 0:
            return 0.0
        p = valid / valid.sum()
        p = p[p > 0]
        return float(-np.sum(p * np.log(p)))

    def _spectral_flatness(self, spectrum: np.ndarray) -> float:
        """谱平坦度：几何均值/算术均值。接近1=白噪声，接近0=有调性"""
        valid = spectrum[1:]
        if len(valid) == 0 or valid.sum() == 0:
            return 0.0
        log_mean = np.mean(np.log(valid + 1e-12))
        arith_mean = np.mean(valid)
        if arith_mean <= 0:
            return 0.0
        return float(np.exp(log_mean) / arith_mean)

    def _spectral_verdict(self, entropy: float, periods: List[Dict]) -> Dict:
        """频谱判定"""
        if not periods:
            return {"status": "no_period", "message": "未检测到明显周期成分"}
        top_power = periods[0]["power"]
        if entropy < 3.0 and top_power > 0.1:
            return {
                "status": "strong_periodicity",
                "message": f"强周期性，主周期约{periods[0]['period']:.1f}期，功率占比{top_power:.2%}",
            }
        elif entropy < 5.0:
            return {
                "status": "weak_periodicity",
                "message": f"弱周期性，谱熵={entropy:.2f}，可考虑加入周期特征",
            }
        else:
            return {
                "status": "noise_like",
                "message": f"近似白噪声，谱熵={entropy:.2f}，周期特征价值有限",
            }


def run_full_diagnostics(
    feature_matrix: np.ndarray,
    feature_names: Optional[List[str]] = None,
    labels: Optional[np.ndarray] = None,
    series_dict: Optional[Dict[str, np.ndarray]] = None,
    save_to: Optional[Path] = None,
) -> Dict:
    """运行全套诊断（特征空间 + 样本量 + 频域）。

    Args:
        feature_matrix: 特征矩阵 (n_samples, n_features)
        feature_names: 特征名
        labels: 1D 标签数组（样本量诊断用）
        series_dict: 各位置时间序列（频域诊断用）
        save_to: 报告保存路径，默认 LOGS_DIR/diagnostics_YYYYMMDD_HHMMSS.json

    Returns:
        合并的诊断结果字典
    """
    logger.info("=" * 80)
    logger.info("[诊断] 开始运行全套特征与数据诊断")
    logger.info("=" * 80)

    full_result = {
        "timestamp": datetime.now().isoformat(),
        "feature_space": None,
        "sample_size": None,
        "spectral": None,
    }

    # 1. 特征空间覆盖度
    try:
        fs_diag = FeatureSpaceDiagnostics()
        full_result["feature_space"] = fs_diag.diagnose(feature_matrix, feature_names)
    except Exception as e:
        logger.error(f"[诊断] 特征空间诊断失败: {e}", exc_info=True)
        full_result["feature_space"] = {"error": str(e)}

    # 2. 样本量饱和曲线（需标签）
    if labels is not None:
        try:
            # 标签可能是多位，取第一个位置做示例诊断
            y = np.asarray(labels)
            if y.ndim > 1:
                y = y[:, 0]  # 取第一位
            ss_diag = SampleSizeDiagnostics()
            full_result["sample_size"] = ss_diag.diagnose(feature_matrix, y)
        except Exception as e:
            logger.error(f"[诊断] 样本量诊断失败: {e}", exc_info=True)
            full_result["sample_size"] = {"error": str(e)}
    else:
        logger.info("[诊断] 未提供标签，跳过样本量饱和曲线分析")

    # 3. 频域诊断（需时间序列）
    if series_dict is not None:
        try:
            spec_diag = SpectralDiagnostics()
            full_result["spectral"] = spec_diag.diagnose(series_dict)
        except Exception as e:
            logger.error(f"[诊断] 频域诊断失败: {e}", exc_info=True)
            full_result["spectral"] = {"error": str(e)}
    else:
        logger.info("[诊断] 未提供时间序列，跳过频域诊断")

    # 落盘
    if save_to is None:
        save_to = LOGS_DIR / f"diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_to = Path(save_to)
    save_to.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(save_to, 'w', encoding='utf-8') as f:
            json.dump(full_result, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"[诊断] 报告已保存: {save_to}")
    except Exception as e:
        logger.error(f"[诊断] 报告保存失败: {e}", exc_info=True)

    logger.info("=" * 80)
    logger.info("[诊断] 全套诊断完成")
    logger.info("=" * 80)

    return full_result
