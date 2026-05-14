"""HuggingFace模型适配器"""

from typing import Dict, List, Generator

from .base import BaseLLM, LLMFactory
from ..ai_types import LLMConfig, LLMType


class HuggingFaceLLM(BaseLLM):
    """HuggingFace模型适配器

    支持HuggingFace上的开源模型。
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._pipeline = None
        self._tokenizer = None
        self._model = None
        self._initialize_model()

    def _initialize_model(self):
        """初始化HuggingFace模型"""
        try:
            from transformers import (
                pipeline,
                AutoTokenizer,
                AutoModelForCausalLM,
            )

            # 尝试加载tokenizer和模型
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.config.model_name
                )
                self._model = AutoModelForCausalLM.from_pretrained(
                    self.config.model_name
                )
                self._pipeline = pipeline(
                    "text-generation",
                    model=self._model,
                    tokenizer=self._tokenizer,
                    device_map="auto",
                )
            except Exception:
                # 如果加载完整模型失败，使用pipeline直接加载
                self._pipeline = pipeline(
                    "text-generation",
                    model=self.config.model_name,
                    device_map="auto",
                )
        except ImportError:
            # 如果transformers不可用，使用模拟实现
            self._pipeline = None
        except Exception as e:
            # 其他初始化失败，使用模拟实现
            self._pipeline = None

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if self._pipeline:
            try:
                response = self._pipeline(
                    prompt,
                    max_new_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    **kwargs,
                )
                return response[0]["generated_text"].strip()
            except Exception as e:
                return f"HuggingFace model generation failed: {str(e)}"
        else:
            # 模拟实现
            return f"[HuggingFace Model] {prompt} - This is a mock response"

    def generate_stream(
        self, prompt: str, **kwargs
    ) -> Generator[str, None, None]:
        """流式生成文本"""
        response = self.generate(prompt, **kwargs)
        # 简单的流式模拟
        for i in range(0, len(response), 5):
            yield response[i : i + 5]

    def chat(self, messages: List[Dict], **kwargs) -> Dict:
        """对话"""
        # 构建对话历史
        prompt = ""
        for msg in messages:
            if msg["role"] == "user":
                prompt += f"User: {msg['content']}\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n"
        prompt += "Assistant:"

        response = self.generate(prompt, **kwargs)
        return {"role": "assistant", "content": response}

    def chat_stream(
        self, messages: List[Dict], **kwargs
    ) -> Generator[Dict, None, None]:
        """流式对话"""
        response = self.chat(messages, **kwargs)
        content = response["content"]
        # 简单的流式模拟
        for i in range(0, len(content), 5):
            yield {"role": "assistant", "content": content[i : i + 5]}


# 注册到工厂
LLMFactory.register(LLMType.HUGGINGFACE, HuggingFaceLLM)
