"""模型层基础接口"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Generator
from dataclasses import dataclass

from ..ai_types import LLMConfig, LLMType


class BaseLLM(ABC):
    """大模型抽象基类"""
    
    def __init__(self, config: LLMConfig):
        """初始化大模型
        
        Args:
            config: 大模型配置
        """
        self.config = config
        self.model_type = config.model_type
        self.model_name = config.model_name
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本
        
        Args:
            prompt: 提示文本
            kwargs: 额外参数
            
        Returns:
            生成的文本
        """
        pass
    
    @abstractmethod
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """流式生成文本
        
        Args:
            prompt: 提示文本
            kwargs: 额外参数
            
        Yields:
            生成的文本片段
        """
        pass
    
    @abstractmethod
    def chat(self, messages: List[Dict], **kwargs) -> Dict:
        """对话
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            kwargs: 额外参数
            
        Returns:
            对话响应
        """
        pass
    
    @abstractmethod
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[Dict, None, None]:
        """流式对话
        
        Args:
            messages: 消息列表
            kwargs: 额外参数
            
        Yields:
            对话响应片段
        """
        pass
    
    def get_config(self) -> LLMConfig:
        """获取配置
        
        Returns:
            大模型配置
        """
        return self.config
    
    def set_config(self, config: LLMConfig) -> None:
        """设置配置
        
        Args:
            config: 大模型配置
        """
        self.config = config
        self.model_type = config.model_type
        self.model_name = config.model_name


class LLMFactory:
    """大模型工厂类"""
    
    _llm_classes = {}
    
    @classmethod
    def register(cls, model_type: LLMType, llm_class: type):
        """注册大模型类
        
        Args:
            model_type: 模型类型
            llm_class: 大模型类
        """
        cls._llm_classes[model_type] = llm_class
    
    @classmethod
    def create(cls, config: LLMConfig) -> BaseLLM:
        """创建大模型实例
        
        Args:
            config: 大模型配置
            
        Returns:
            大模型实例
            
        Raises:
            ValueError: 如果模型类型不支持
        """
        llm_class = cls._llm_classes.get(config.model_type)
        if not llm_class:
            raise ValueError(f"Unsupported model type: {config.model_type}")
        return llm_class(config)
    
    @classmethod
    def list_supported_models(cls) -> List[LLMType]:
        """列出支持的模型类型
        
        Returns:
            支持的模型类型列表
        """
        return list(cls._llm_classes.keys())
    
    @classmethod
    def is_supported(cls, model_type: LLMType) -> bool:
        """检查模型类型是否支持
        
        Args:
            model_type: 模型类型
            
        Returns:
            是否支持
        """
        return model_type in cls._llm_classes
