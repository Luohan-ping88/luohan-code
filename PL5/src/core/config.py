"""
核心配置 - 统一配置入口（V10.0 + ModelConfig）
兼容 from core.config import BASE_DIR, setup_logging, LOGS_DIR, DATA_DIR ...
新增: ModelConfig 类 - 从YAML加载、嵌套键访问、环境变量覆盖
"""
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# ── 目录定义 ──────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent.parent

BASE_DIR = ROOT_DIR

DATA_DIR = ROOT_DIR / 'data'
RAW_DATA_DIR = DATA_DIR / 'raw'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'

RESULTS_DIR = ROOT_DIR / 'results'

MODELS_DIR = ROOT_DIR / 'models'

LOGS_DIR = ROOT_DIR / 'logs'

CONFIG_DIR = ROOT_DIR / 'config'

for _d in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, RESULTS_DIR, MODELS_DIR, LOGS_DIR, CONFIG_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── 数据源配置 ────────────────────────────────────────────────
DATA_SOURCES: Dict[str, str] = {
    'lecai': 'http://data.17500.cn/pl5_asc.txt',
    'local': str(RAW_DATA_DIR / 'pl5_history.txt'),
}

# ── PL5 业务配置 ──────────────────────────────────────────────
PL5_CONFIG: Dict[str, Any] = {
    'positions': ['wan', 'qian', 'bai', 'shi', 'ge'],
    'history_length': 1000,
    'feature_window': 30,
    'prediction_window': 5,
}

# ── 模型配置（旧版兼容） ─────────────────────────────────────
MODEL_CONFIG: Dict[str, Any] = {
    'hmm': {'n_states': 4, 'n_iter': 100},
    'copula': {'family': 'gaussian'},
    'bsts': {'n_iter': 1000, 'burn': 100},
    'evm': {'threshold': 9.0},
}

# ── 训练配置 ──────────────────────────────────────────────────
TRAINING_CONFIG: Dict[str, Any] = {
    'test_size': 0.2,
    'random_state': 42,
    'n_splits': 5,
}

# ── 日志工具 ──────────────────────────────────────────────────
def setup_logging(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    [已废弃] 请使用 src.core.utils.logger.get_logger()。
    此处保留仅为兼容旧代码，将重定向到统一日志器。
    """
    from src.core.utils.logger import get_logger as _new_get_logger
    return _new_get_logger(name or 'main')


# ================================================================
# ModelConfig - 统一配置管理类 V1.0
# ================================================================

_DEFAULT_CONFIG_PATH = CONFIG_DIR / 'model_config.yaml'


class ConfigValidationError(Exception):
    pass


class ModelConfig:
    """统一模型配置管理器

    功能:
    - 从YAML文件加载配置
    - 支持嵌套键访问 (config.get("stacking.base_config.n_estimators"))
    - 类型安全的配置访问接口
    - 默认值处理和配置验证
    - 环境变量覆盖支持 (PL5_STACKING__BASE_CONFIG__N_ESTIMATORS=200)
    - 配置变更监听和回调
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self._config_path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        self._data: Dict[str, Any] = {}
        self._env_prefix = "PL5_"
        self._callbacks: List[callable] = []
        self._loaded = False

        if self._config_path.exists():
            self.load()
        else:
            logger = logging.getLogger(__name__)
            logger.warning(f"[ModelConfig] 配置文件不存在: {self._config_path}, 使用内置默认值")
            self._data = self._get_builtin_defaults()
            self._loaded = True

    @staticmethod
    def _get_builtin_defaults() -> Dict[str, Any]:
        return {
            'stacking': {
                'base_config': {'n_estimators': 100, 'max_depth': 12, 'random_state': 42, 'n_jobs': -1, 'learning_rate': 0.1},
                'meta_config': {'type': 'logistic', 'C': 1.0, 'max_iter': 500, 'l1_ratio': 0.5, 'alpha': 0.0001, 'cv_folds': 5, 'auto_select': True, 'enable_meta_features': True},
                # 【V10.5精度优化】优化模型权重：增强集成模型权重，提升稳定性
                'model_weights': {
                    'stacking': 0.45,    # 集成模型权重提升（稳定性最强）
                    'hmm': 0.15,         # 时序模式识别
                    'copula': 0.25,       # 联合概率调整
                    'bayesian': 0.15     # 不确定性估计（降低权重提升稳定性）
                }
            },
            'hmm': {'n_states': 4, 'n_mixtures': 2, 'auto_select': False, 'criterion': 'bic', 'max_states': 8, 'min_states': 2, 'max_iterations': 50, 'convergence_tol': 1e-6},
            'copula': {'type': 'gaussian', 'regularization': 1e-6, 'auto_select': False},
            'bsts': {'trend_window': 20, 'seasonality_period': None, 'outlier_threshold': 2.5, 'n_posterior_samples': 1000, 'confidence_level': 0.95, 'candidate_windows': [10, 15, 20, 30, 50], 'retrain_threshold': 0.3, 'max_history_length': 500, 'learning_rate': 0.3},
            'feature_engineering': {
                'feature_groups': {},
                'cache': {'max_size': 10},
                'scaler': {'method': 'standard', 'robust_quantile_range': [25.0, 75.0]},
                'drift_detection': {'psi_threshold': 0.2, 'ks_threshold': 0.05},
                'selection': {'select_top': 100, 'method': 'rfe'},
                'parallel': {'enable': True}
            },
            'self_learning': {'window': 10, 'retrain_threshold': 0.02, 'min_history': 3, 'volatility_factor': 3.0, 'warning_accuracy': 0.12, 'urgent_accuracy': 0.08, 'max_history_records': 200, 'max_suggestion_records': 500, 'comprehensive_score_weights': {'accuracy': 0.40, 'hit_rate': 0.20, 'confidence': 0.20, 'stability': 0.20}},
            'rl_optimizer': {'state_dim': 128, 'action_dim': 4, 'actor_lr': 0.001, 'critic_lr': 0.005, 'gamma': 0.95, 'epsilon': 1.0, 'epsilon_decay': 0.995, 'epsilon_min': 0.01, 'batch_size': 32, 'memory_capacity': 10000, 'n_models': 4, 'performance_window': 30, 'thompson_sampling': {'initial_alpha': 2.0, 'initial_beta': 3.0, 'n_arms': 5}},
            'prediction': {'top_k': 8, 'use_rl': True, 'use_uncertainty': True, 'parallel_training': True, 'prediction_cache_size': 200},
            'training': {'test_size': 0.2, 'random_state': 42, 'n_splits': 5}
        }

    def load(self, config_path: Optional[Union[str, Path]] = None) -> "ModelConfig":
        path = Path(config_path) if config_path else self._config_path
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {path}")

        if _HAS_YAML:
            with open(path, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f) or {}
        else:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f) if path.suffix == '.json' else {}

        self._data = raw_data
        self._apply_env_overrides()
        self._validate()
        self._loaded = True
        logger = logging.getLogger(__name__)
        logger.info(f"[ModelConfig] 配置已加载: {path}")
        return self

    def reload(self) -> "ModelConfig":
        return self.load()

    def save(self, path: Optional[Union[str, Path]] = None) -> "ModelConfig":
        target = Path(path) if path else self._config_path
        target.parent.mkdir(parents=True, exist_ok=True)

        if _HAS_YAML:
            with open(target, 'w', encoding='utf-8') as f:
                yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        else:
            import json
            with open(target, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)

        logger = logging.getLogger(__name__)
        logger.info(f"[ModelConfig] 配置已保存: {target}")
        return self

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_int(self, key: str, default: int = 0) -> int:
        val = self.get(key, default)
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key, default)
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes', 'on')
        return bool(val)

    def get_list(self, key: str, default: Optional[List] = None) -> list:
        val = self.get(key)
        if val is None:
            return default or []
        if isinstance(val, list):
            return val
        return [val]

    def get_dict(self, key: str, default: Optional[Dict] = None) -> dict:
        val = self.get(key)
        if val is None:
            return default or {}
        if isinstance(val, dict):
            return val
        return {}

    def set(self, key: str, value: Any) -> "ModelConfig":
        keys = key.split('.')
        target = self._data
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self._notify_change(key, value)
        return self

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(f"配置键不存在: '{key}'")
        return val

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def keys(self, prefix: str = "") -> List[str]:
        if not prefix:
            return list(self._data.keys())
        node = self._data
        for part in prefix.split('.'):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return []
        return list(node.keys()) if isinstance(node, dict) else []

    def section(self, name: str) -> Dict[str, Any]:
        return self.get_dict(name)

    def _apply_env_overrides(self):
        for key in os.environ:
            if not key.startswith(self._env_prefix):
                continue
            env_key = key[len(self._env_prefix):].lower()
            config_parts = env_key.split('__')
            value = os.environ[key]

            target = self._data
            valid = True
            for part in config_parts[:-1]:
                if isinstance(target, dict):
                    target = target.setdefault(part, {})
                else:
                    valid = False
                    break

            if valid and isinstance(target, dict):
                last_part = config_parts[-1]
                parsed_value = self._parse_env_value(value)
                target[last_part] = parsed_value
                logger = logging.getLogger(__name__)
                logger.debug(f"[ModelConfig] 环境变量覆盖: {key} => {'.'.join(config_parts)} = {parsed_value}")

    @staticmethod
    def _parse_env_value(value: str) -> Any:
        if value.lower() in ('true', 'yes', 'on'):
            return True
        if value.lower() in ('false', 'no', 'off'):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def _validate(self):
        validations = [
            ("stacking.base_config.n_estimators", lambda v: isinstance(v, int) and v > 0),
            ("stacking.base_config.max_depth", lambda v: isinstance(v, (int, float)) and float(v) > 0),
            ("stacking.meta_config.cv_folds", lambda v: isinstance(v, int) and v >= 2),
            ("hmm.n_states", lambda v: isinstance(v, int) and v > 0),
            ("bsts.trend_window", lambda v: isinstance(v, int) and v > 0),
            ("rl_optimizer.state_dim", lambda v: isinstance(v, int) and v > 0),
            ("rl_optimizer.learning_rate" if False else "", lambda v: True),
        ]

        errors = []
        for key, check_fn in validations:
            if not key:
                continue
            val = self.get(key)
            if val is not None:
                try:
                    if not check_fn(val):
                        errors.append(f"{key}={val} 验证失败")
                except Exception:
                    pass

        if errors:
            logger = logging.getLogger(__name__)
            logger.warning(f"[ModelConfig] 配置验证警告: {errors}")

    def on_change(self, callback: callable) -> "ModelConfig":
        self._callbacks.append(callback)
        return self

    def _notify_change(self, key: str, value: Any):
        for cb in self._callbacks:
            try:
                cb(key, value)
            except Exception:
                pass

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def raw(self) -> Dict[str, Any]:
        return self._data.copy()

    def stacking_base_config(self) -> Dict[str, Any]:
        return self.get_dict('stacking.base_config', {
            'n_estimators': 100, 'max_depth': 12, 'random_state': 42,
            'n_jobs': -1, 'learning_rate': 0.1
        })

    def stacking_meta_config(self) -> Dict[str, Any]:
        return self.get_dict('stacking.meta_config', {
            'type': 'logistic', 'C': 1.0, 'max_iter': 500, 'l1_ratio': 0.5,
            'alpha': 0.0001, 'cv_folds': 5, 'auto_select': True, 'enable_meta_features': True
        })

    def model_weights(self) -> Dict[str, float]:
        return self.get_dict('stacking.model_weights', {
            'stacking': 0.40, 'hmm': 0.15, 'copula': 0.25, 'bayesian': 0.20
        })

    def hmm_config(self) -> Dict[str, Any]:
        return self.get_dict('hmm', {
            'n_states': 4, 'n_mixtures': 2, 'auto_select': False, 'criterion': 'bic'
        })

    def copula_config(self) -> Dict[str, Any]:
        return self.get_dict('copula', {
            'type': 'gaussian', 'regularization': 1e-6, 'auto_select': False
        })

    def bsts_config(self) -> Dict[str, Any]:
        return self.get_dict('bsts', {
            'trend_window': 20, 'seasonality_period': None, 'outlier_threshold': 2.5,
            'n_posterior_samples': 1000, 'confidence_level': 0.95
        })

    def feature_config(self) -> Dict[str, Any]:
        return self.get_dict('feature_engineering', {})

    def self_learning_config(self) -> Dict[str, Any]:
        return self.get_dict('self_learning', {
            'window': 10, 'retrain_threshold': 0.02, 'min_history': 3,
            'volatility_factor': 3.0, 'warning_accuracy': 0.12, 'urgent_accuracy': 0.08
        })

    def rl_config(self) -> Dict[str, Any]:
        return self.get_dict('rl_optimizer', {
            'state_dim': 128, 'actor_lr': 0.001, 'critic_lr': 0.005,
            'gamma': 0.95, 'batch_size': 32, 'memory_capacity': 10000, 'n_models': 4
        })

    def prediction_config(self) -> Dict[str, Any]:
        return self.get_dict('prediction', {
            'top_k': 8, 'use_rl': True, 'use_uncertainty': True, 'parallel_training': True
        })

    def summary(self) -> Dict[str, Any]:
        return {
            'config_path': str(self._config_path),
            'is_loaded': self._loaded,
            'top_level_keys': list(self._data.keys()),
            'stacking_n_estimators': self.get_int('stacking.base_config.n_estimators'),
            'stacking_max_depth': self.get_int('stacking.base_config.max_depth'),
            'hmm_n_states': self.get_int('hmm.n_states'),
            'hmm_criterion': self.get('hmm.criterion'),
            'copula_type': self.get('copula.type'),
            'bsts_trend_window': self.get_int('bsts.trend_window'),
            'rl_state_dim': self.get_int('rl_optimizer.state_dim'),
            'rl_actor_lr': self.get_float('rl_optimizer.actor_lr'),
            'self_learning_window': self.get_int('self_learning.window'),
            'prediction_top_k': self.get_int('prediction.top_k'),
        }

    def __repr__(self) -> str:
        status = "已加载" if self._loaded else "未加载"
        return f"<ModelConfig path={self._config_path} status={status} keys={list(self._data.keys())}>"


_global_model_config: Optional[ModelConfig] = None


def get_model_config(config_path: Optional[Union[str, Path]] = None) -> ModelConfig:
    global _global_model_config
    if _global_model_config is None:
        _global_model_config = ModelConfig(config_path)
    return _global_model_config


def reset_model_config():
    global _global_model_config
    _global_model_config = None
