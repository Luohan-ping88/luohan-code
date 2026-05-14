"""特征配置管理器
统一管理训练和预测流程中的特征配置
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """特征配置数据类"""

    select_top: Optional[int] = None
    feature_columns: List[str] = field(default_factory=list)
    feature_count: int = 0
    version: str = ""
    created_at: str = ""
    validation_score: float = 0.0
    config_source: str = ""


class FeatureConfigManager:
    """特征配置管理器 - 单例模式

    统一管理训练和预测流程中的特征配置，确保两者使用一致的配置
    """

    _instance: Optional["FeatureConfigManager"] = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_dirs: Optional[List[Path]] = None):
        if self._initialized:
            return

        # 默认配置目录
        if config_dirs is None:
            base_dir = Path(__file__).parent.parent.parent
            config_dirs = [
                base_dir / "logs",
                base_dir / "models",
                base_dir / "config",
            ]

        self.config_dirs = [Path(d) for d in config_dirs]
        self._cached_config: Optional[FeatureConfig] = None
        self._cached_config_path: Optional[Path] = None
        self._initialized = True

        logger.info(
            f"[FeatureConfigManager] 初始化完成，配置目录: {self.config_dirs}"
        )

    def find_config_file(
        self, filename: str = "best_feature_config.json"
    ) -> Optional[Path]:
        """查找配置文件

        Args:
            filename: 配置文件名

        Returns:
            配置文件路径，如果不存在返回None
        """
        for config_dir in self.config_dirs:
            config_path = config_dir / filename
            if config_path.exists():
                logger.info(
                    f"[FeatureConfigManager] 找到配置文件: {config_path}"
                )
                return config_path

        logger.warning(f"[FeatureConfigManager] 未找到配置文件: {filename}")
        return None

    def load_config(
        self, config_path: Optional[Path] = None
    ) -> Optional[FeatureConfig]:
        """加载特征配置

        Args:
            config_path: 配置文件路径，如果为None则自动查找

        Returns:
            特征配置对象
        """
        if config_path is None:
            config_path = self.find_config_file()

        if config_path is None or not config_path.exists():
            logger.warning(
                "[FeatureConfigManager] 配置文件不存在，使用默认配置"
            )
            return None

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 兼容两种格式：直接配置或嵌套在 best_config 中
            config_data = data.get("best_config", data)

            config = FeatureConfig(
                select_top=config_data.get("select_top"),
                feature_columns=config_data.get("feature_columns", []),
                feature_count=config_data.get("feature_count", 0),
                version=config_data.get("version", ""),
                created_at=config_data.get("created_at", ""),
                validation_score=config_data.get("validation_score", 0.0),
                config_source=str(config_path),
            )

            self._cached_config = config
            self._cached_config_path = config_path

            logger.info(
                f"[FeatureConfigManager] 加载配置成功: select_top={config.select_top}, "
                f"feature_count={config.feature_count}"
            )

            return config

        except Exception as e:
            logger.error(f"[FeatureConfigManager] 加载配置文件失败: {e}")
            return None

    def get_select_top(self) -> Optional[int]:
        """获取最佳特征数量

        Returns:
            最佳特征数量，如果不存在返回None
        """
        if self._cached_config is None:
            self.load_config()

        return self._cached_config.select_top if self._cached_config else None

    def get_feature_columns(self) -> List[str]:
        """获取特征列名列表

        Returns:
            特征列名列表
        """
        if self._cached_config is None:
            self.load_config()

        return (
            self._cached_config.feature_columns if self._cached_config else []
        )

    def get_config(self) -> Optional[FeatureConfig]:
        """获取完整配置

        Returns:
            特征配置对象
        """
        if self._cached_config is None:
            self.load_config()

        return self._cached_config

    def save_config(
        self, config: FeatureConfig, config_path: Optional[Path] = None
    ) -> bool:
        """保存特征配置

        Args:
            config: 特征配置对象
            config_path: 保存路径，如果为None则保存到默认位置

        Returns:
            是否保存成功
        """
        if config_path is None:
            config_path = self.find_config_file()

        if config_path is None:
            # 使用第一个配置目录
            config_path = self.config_dirs[0] / "best_feature_config.json"

        # 确保目录存在
        config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                "best_config": {
                    "select_top": config.select_top,
                    "feature_columns": config.feature_columns,
                    "feature_count": config.feature_count,
                    "version": config.version,
                    "created_at": config.created_at,
                    "validation_score": config.validation_score,
                }
            }

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self._cached_config = config
            self._cached_config_path = config_path

            logger.info(f"[FeatureConfigManager] 配置已保存到: {config_path}")
            return True

        except Exception as e:
            logger.error(f"[FeatureConfigManager] 保存配置失败: {e}")
            return False

    def invalidate_cache(self) -> None:
        """使缓存失效，强制重新加载配置"""
        self._cached_config = None
        self._cached_config_path = None
        logger.debug("[FeatureConfigManager] 缓存已失效")

    def reload(self) -> Optional[FeatureConfig]:
        """重新加载配置

        Returns:
            重新加载的配置对象
        """
        self.invalidate_cache()
        return self.load_config()

    def validate_config(self, available_columns: List[str]) -> Dict[str, Any]:
        """验证配置中的特征列是否都可用

        Args:
            available_columns: 可用的特征列名列表

        Returns:
            验证结果，包含：
            - is_valid: 配置是否有效
            - missing_columns: 缺失的列
            - extra_columns: 额外的列
            - valid_columns: 有效的列
        """
        config = self.get_config()

        if config is None:
            return {
                "is_valid": True,
                "missing_columns": [],
                "extra_columns": [],
                "valid_columns": available_columns,
            }

        config_columns = set(config.feature_columns)
        available_set = set(available_columns)

        missing = config_columns - available_set
        extra = available_set - config_columns
        valid = config_columns & available_set

        is_valid = len(missing) == 0

        result = {
            "is_valid": is_valid,
            "missing_columns": list(missing),
            "extra_columns": list(extra),
            "valid_columns": list(valid),
            "config_feature_count": len(config_columns),
            "available_feature_count": len(available_set),
            "valid_feature_count": len(valid),
        }

        if not is_valid:
            logger.warning(
                f"[FeatureConfigManager] 配置验证失败: {len(missing)} 个特征列缺失"
            )

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """获取配置统计信息

        Returns:
            统计信息字典
        """
        config = self.get_config()

        return {
            "has_config": config is not None,
            "select_top": config.select_top if config else None,
            "feature_count": config.feature_count if config else 0,
            "config_source": config.config_source if config else None,
            "validation_score": config.validation_score if config else 0.0,
            "cached": self._cached_config is not None,
            "cache_path": (
                str(self._cached_config_path)
                if self._cached_config_path
                else None
            ),
        }

    def reset(self) -> None:
        """重置管理器"""
        self.invalidate_cache()
        logger.info("[FeatureConfigManager] 管理器已重置")


# 全局特征配置管理器实例
_feature_config_manager: Optional[FeatureConfigManager] = None


def get_feature_config_manager() -> FeatureConfigManager:
    """获取全局特征配置管理器实例"""
    global _feature_config_manager
    if _feature_config_manager is None:
        _feature_config_manager = FeatureConfigManager()
    return _feature_config_manager
