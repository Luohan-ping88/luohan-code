"""OpenAI模型适配器"""

import os
from typing import Dict, List, Any, Generator

from .base import BaseLLM, LLMFactory
from ..ai_types import LLMConfig, LLMType


class OpenAILLM(BaseLLM):
    """OpenAI模型适配器
    
    支持OpenAI GPT系列模型，包括API密钥管理、文本生成和对话功能，支持流式生成。
    """
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化OpenAI客户端
        
        优先使用配置中的API密钥，如果没有则尝试从环境变量读取。
        """
        try:
            from openai import OpenAI
            
            # 创建客户端
            client_kwargs = {}
            
            # 优先使用配置中的API密钥
            api_key = self.config.api_key
            
            # 如果配置中没有API密钥，尝试从环境变量读取
            if not api_key:
                api_key = os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    api_key = os.environ.get("OPENAI_KEY")
            
            if api_key:
                client_kwargs["api_key"] = api_key
            
            # 设置基础URL
            if self.config.base_url:
                client_kwargs["base_url"] = self.config.base_url
            
            # 设置超时
            if self.config.timeout:
                client_kwargs["timeout"] = self.config.timeout
            
            self._client = OpenAI(**client_kwargs)
        except ImportError:
            # 如果openai不可用，使用模拟实现
            self._client = None
        except Exception as e:
            # 其他初始化失败，使用模拟实现
            self._client = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本
        
        Args:
            prompt: 提示文本
            kwargs: 额外参数，如top_p、frequency_penalty等
            
        Returns:
            生成的文本
        """
        if self._client:
            try:
                response = self._client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    **kwargs
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                return f"OpenAI model generation failed: {str(e)}"
        else:
            # 模拟实现
            return f"[OpenAI Model] {prompt} - This is a mock response"
    
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """流式生成文本
        
        Args:
            prompt: 提示文本
            kwargs: 额外参数
            
        Yields:
            生成的文本片段
        """
        if self._client:
            try:
                response = self._client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    stream=True,
                    **kwargs
                )
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            except Exception as e:
                yield f"OpenAI model generation failed: {str(e)}"
        else:
            # 模拟实现
            response = f"[OpenAI Model] {prompt} - This is a mock response"
            for i in range(0, len(response), 5):
                yield response[i:i+5]
    
    def chat(self, messages: List[Dict], **kwargs) -> Dict:
        """对话
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            kwargs: 额外参数
            
        Returns:
            对话响应
        """
        if self._client:
            try:
                response = self._client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    **kwargs
                )
                return {
                    "role": "assistant",
                    "content": response.choices[0].message.content.strip()
                }
            except Exception as e:
                return {
                    "role": "assistant",
                    "content": f"OpenAI model chat failed: {str(e)}"
                }
        else:
            # 模拟实现
            return {
                "role": "assistant",
                "content": f"[OpenAI Model] Chat response - This is a mock response"
            }
    
    def chat_stream(self, messages: List[Dict], **kwargs) -> Generator[Dict, None, None]:
        """流式对话
        
        Args:
            messages: 消息列表
            kwargs: 额外参数
            
        Yields:
            对话响应片段
        """
        if self._client:
            try:
                response = self._client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    stream=True,
                    **kwargs
                )
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield {
                            "role": "assistant",
                            "content": chunk.choices[0].delta.content
                        }
            except Exception as e:
                yield {
                    "role": "assistant",
                    "content": f"OpenAI model chat failed: {str(e)}"
                }
        else:
            # 模拟实现
            response = "[OpenAI Model] Chat response - This is a mock response"
            for i in range(0, len(response), 5):
                yield {
                    "role": "assistant",
                    "content": response[i:i+5]
                }
    
    def update_api_key(self, api_key: str):
        """更新API密钥
        
        Args:
            api_key: 新的API密钥
        """
        self.config.api_key = api_key
        self._initialize_client()
    
    def get_api_key_status(self) -> bool:
        """检查API密钥状态
        
        Returns:
            API密钥是否有效
        """
        return self._client is not None


# 注册到工厂
LLMFactory.register(LLMType.OPENAI, OpenAILLM)