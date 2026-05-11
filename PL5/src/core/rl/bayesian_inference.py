"""
贝叶斯推理模块 - 提供不确定性量化和概率校准
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from scipy import stats
from sklearn.base import BaseEstimator, ClassifierMixin
import logging

logger = logging.getLogger(__name__)


class BayesianEnsemble:
    def __init__(self, base_estimators: List[BaseEstimator], n_bootstrap: int = 30):
        self.base_estimators = base_estimators
        self.n_bootstrap = n_bootstrap
        self.fitted_estimators: List[List[BaseEstimator]] = []
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BayesianEnsemble":
        n_samples = len(X)
        self.fitted_estimators = []

        for _ in range(self.n_bootstrap):
            boot_indices = np.random.choice(n_samples, n_samples, replace=True)
            X_boot = X[boot_indices]
            y_boot = y[boot_indices]

            estimators = []
            for est in self.base_estimators:
                from sklearn.base import clone

                est_clone = clone(est)
                est_clone.fit(X_boot, y_boot)
                estimators.append(est_clone)

            self.fitted_estimators.append(estimators)

        self.is_fitted = True
        return self

    def predict_proba_with_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if not self.is_fitted:
            raise ValueError("Model not fitted")

        all_predictions = []

        for estimators in self.fitted_estimators:
            for est in estimators:
                if hasattr(est, "predict_proba"):
                    pred = est.predict_proba(X)
                    all_predictions.append(pred)

        if not all_predictions:
            n_classes = 10
            return np.ones((len(X), n_classes)) / n_classes, np.zeros((len(X), n_classes)), np.zeros(len(X))

        all_predictions = np.array(all_predictions)

        mean_pred = np.mean(all_predictions, axis=0)
        std_pred = np.std(all_predictions, axis=0)

        entropy = -np.sum(mean_pred * np.log(mean_pred + 1e-10), axis=1)

        return mean_pred, std_pred, entropy

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        mean, _, _ = self.predict_proba_with_uncertainty(X)
        return mean

    def predict(self, X: np.ndarray) -> np.ndarray:
        proba = self.predict_proba(X)
        return np.argmax(proba, axis=1)


class MCDropoutEstimator(BaseEstimator, ClassifierMixin):
    def __init__(self, base_estimator: BaseEstimator = None, dropout_rate: float = 0.2, n_samples: int = 50):
        self.base_estimator = base_estimator
        self.dropout_rate = dropout_rate
        self.n_samples = n_samples
        self.classes_ = np.arange(10)
        self.fitted_model_ = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "MCDropoutEstimator":
        from sklearn.base import clone

        if self.base_estimator is None:
            from sklearn.ensemble import RandomForestClassifier

            self.base_estimator = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42)

        self.fitted_model_ = clone(self.base_estimator)
        self.fitted_model_.fit(X, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.fitted_model_ is None:
            return np.ones((len(X), 10)) / 10

        proba_list = []
        for _ in range(self.n_samples):
            X_dropout = X.copy()
            mask = np.random.binomial(1, 1 - self.dropout_rate, X_dropout.shape)
            X_dropout = X_dropout * mask

            if hasattr(self.fitted_model_, "predict_proba"):
                proba = self.fitted_model_.predict_proba(X_dropout)
            else:
                proba = np.zeros((len(X), 10))
                predictions = self.fitted_model_.predict(X_dropout)
                for i, pred in enumerate(predictions):
                    proba[i, int(pred)] = 1.0

            proba_list.append(proba)

        return np.mean(proba_list, axis=0)

    def predict(self, X: np.ndarray) -> np.ndarray:
        proba = self.predict_proba(X)
        return np.argmax(proba, axis=1)


class CalibrationEvaluator:
    def __init__(self, n_bins: int = 10):
        self.n_bins = n_bins
        self.confidences: List[float] = []
        self.accuracies: List[bool] = []

    def add_prediction(self, confidence: float, is_correct: bool):
        self.confidences.append(confidence)
        self.accuracies.append(is_correct)

    def get_calibration_error(self) -> float:
        if len(self.confidences) < 10:
            return 1.0

        confidences = np.array(self.confidences)
        accuracies = np.array(self.accuracies, dtype=float)

        bin_boundaries = np.linspace(0, 1, self.n_bins + 1)
        ece = 0.0

        for i in range(self.n_bins):
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]

            mask = (confidences > bin_lower) & (confidences <= bin_upper)
            if mask.sum() > 0:
                bin_confidence = confidences[mask].mean()
                bin_accuracy = accuracies[mask].mean()
                ece += mask.sum() * abs(bin_confidence - bin_accuracy)

        ece /= len(self.confidences)
        return ece

    def get_reliability_diagram(self) -> Dict:
        if len(self.confidences) < 10:
            return {"bins": [], "confidences": [], "accuracies": []}

        confidences = np.array(self.confidences)
        accuracies = np.array(self.accuracies, dtype=float)

        bin_boundaries = np.linspace(0, 1, self.n_bins + 1)
        bins = []
        confidences_per_bin = []
        accuracies_per_bin = []

        for i in range(self.n_bins):
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]

            mask = (confidences > bin_lower) & (confidences <= bin_upper)
            if mask.sum() > 0:
                bins.append((bin_lower + bin_upper) / 2)
                confidences_per_bin.append(confidences[mask].mean())
                accuracies_per_bin.append(accuracies[mask].mean())

        return {"bins": bins, "confidences": confidences_per_bin, "accuracies": accuracies_per_bin}


class UncertaintyAwarePredictor:
    def __init__(self, base_predictor):
        self.base_predictor = base_predictor
        self.calibration = CalibrationEvaluator()
        self.uncertainty_threshold = 0.3

    def predict_with_uncertainty(self, X: np.ndarray) -> Dict:
        mean_pred, std_pred, entropy = self.base_predictor.predict_proba_with_uncertainty(X)

        predictions = np.argmax(mean_pred, axis=1)

        high_uncertainty_mask = entropy > self.uncertainty_threshold

        results = []
        for i in range(len(X)):
            uncertainty_level = "low"
            if entropy[i] > self.uncertainty_threshold * 2:
                uncertainty_level = "high"
            elif entropy[i] > self.uncertainty_threshold:
                uncertainty_level = "medium"

            results.append(
                {
                    "prediction": int(predictions[i]),
                    "confidence": float(mean_pred[i].max()),
                    "uncertainty": float(entropy[i]),
                    "uncertainty_level": uncertainty_level,
                    "std": float(std_pred[i].mean()),
                    "is_uncertain": bool(high_uncertainty_mask[i]),
                }
            )

        return {"predictions": results, "mean_prediction": mean_pred, "uncertainty": entropy}

    def calibrate(self, X_cal: np.ndarray, y_cal: np.ndarray):
        proba = self.base_predictor.predict_proba(X_cal)
        predictions = np.argmax(proba, axis=1)
        confidences = proba[np.arange(len(proba)), predictions]

        for conf, pred, true in zip(confidences, predictions, y_cal):
            self.calibration.add_prediction(float(conf), int(pred) == int(true))

        ece = self.calibration.get_calibration_error()
        logger.info(f"[UncertaintyAware] Calibration ECE: {ece:.4f}")
        return ece
