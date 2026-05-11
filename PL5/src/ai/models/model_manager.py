"""模型管理器"""

from typing import Dict, List, Optional

from .base import BaseLLM, LLMFactory
from ..ai_types import LLMConfig, LLMType


class ModelManager:
    """模型管理器

    负责管理和切换不同的大模型，提供统一的接口。
    """

    def __init__(self):
        """初始化模型管理器"""
        self._models: Dict[str, BaseLLM] = {}
        self._default_model: Optional[str] = None

    def create_model(self, config: LLMConfig) -> BaseLLM:
        """创建模型实例

        Args:
            config: 模型配置

        Returns:
            模型实例
        """
        model = LLMFactory.create(config)
        model_id = f"{config.model_type.value}_{config.model_name}"
        self._models[model_id] = model

        if self._default_model is None:
            self._default_model = model_id

        return model

    def get_model(self, model_id: Optional[str] = None) -> BaseLLM:
        """获取模型实例

        Args:
            model_id: 模型ID，如果为None则返回默认模型

        Returns:
            模型实例

        Raises:
            ValueError: 如果模型不存在
        """
        if model_id is None:
            if self._default_model is None:
                raise ValueError("No model has been created yet")
            model_id = self._default_model

        if model_id not in self._models:
            raise ValueError(f"Model {model_id} not found")

        return self._models[model_id]

    def list_models(self) -> List[str]:
        """列出所有已创建的模型

        Returns:
            模型ID列表
        """
        return list(self._models.keys())

    def set_default_model(self, model_id: str):
        """设置默认模型

        Args:
            model_id: 模型ID

        Raises:
            ValueError: 如果模型不存在
        """
        if model_id not in self._models:
            raise ValueError(f"Model {model_id} not found")

        self._default_model = model_id

    def remove_model(self, model_id: str):
        """移除模型

        Args:
            model_id: 模型ID

        Raises:
            ValueError: 如果模型不存在
        """
        if model_id not in self._models:
            raise ValueError(f"Model {model_id} not found")

        del self._models[model_id]

        if self._default_model == model_id:
            self._default_model = next(iter(self._models.keys()), None)

    def clear_models(self):
        """清空所有模型"""
        self._models.clear()
        self._default_model = None

    def get_model_info(self, model_id: str) -> Dict:
        """获取模型信息

        Args:
            model_id: 模型ID

        Returns:
            模型信息字典

        Raises:
            ValueError: 如果模型不存在
        """
        model = self.get_model(model_id)
        config = model.get_config()

        return {
            "model_id": model_id,
            "model_type": config.model_type.value,
            "model_name": config.model_name,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "is_default": model_id == self._default_model,
        }

    def list_model_info(self) -> List[Dict]:
        """列出所有模型信息

        Returns:
            模型信息列表
        """
        return [self.get_model_info(model_id) for model_id in self._models.keys()]


# 全局模型管理器实例
_global_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """获取全局模型管理器实例

    Returns:
        模型管理器实例
    """
    global _global_model_manager
    if _global_model_manager is None:
        _global_model_manager = ModelManager()
    return _global_model_manager


def reset_model_manager():
    """重置全局模型管理器"""
    global _global_model_manager
    _global_model_manager = None
