"""本地模型适配器"""

from typing import Dict, List, Any, Generator
import os

from .base import BaseLLM, LLMFactory
from ..ai_types import LLMConfig, LLMType


class LocalLLM(BaseLLM):
    """本地大模型适配器

    支持本地运行的模型，如LLaMA、Mistral等。
    集成了llama-cpp-python，支持模型加载、配置、文本生成和对话功能。
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._model = None
        self._llm = None
        self._pipeline = None
        self._initialize_model()

    def _initialize_model(self):
        """初始化本地模型"""
        try:
            # 尝试导入llama-cpp-python
            try:
                from llama_cpp import Llama

                # 获取模型路径
                model_path = self.config.base_url
                if not model_path:
                    # 尝试从环境变量获取
                    model_path = os.environ.get("LLAMA_CPP_MODEL_PATH")
                if not model_path:
                    # 默认模型路径
                    model_path = "models/llama-2-7b-chat.Q4_0.gguf"

                # 检查模型文件是否存在
                if not os.path.exists(model_path):
                    raise FileNotFoundError(
                        f"Model file not found: {model_path}"
                    )

                # 初始化llama-cpp模型
                self._llm = Llama(
                    model_path=model_path,
                    n_ctx=2048,  # 上下文长度
                    n_threads=4,  # 线程数
                    n_gpu_layers=0,  # GPU层数量
                    verbose=False,
                )
                self._model = "llama_cpp"
            except ImportError:
                # 尝试导入transformers
                try:
                    from transformers import pipeline

                    self._pipeline = pipeline("text-generation")
                    self._model = "transformers"
                except ImportError:
                    # 如果transformers不可用，使用简单的模拟实现
                    self._model = "mock"
        except Exception as e:
            # 如果初始化失败，使用模拟实现
            print(f"Failed to initialize local model: {str(e)}")
            self._model = "mock"

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if self._model == "llama_cpp":
            try:
                response = self._llm(
                    prompt,
                    max_tokens=self.config.max_tokens or 1000,
                    temperature=self.config.temperature or 0.7,
                    **kwargs,
                )
                return response["choices"][0]["text"].strip()
            except Exception as e:
                return f"Llama.cpp generation failed: {str(e)}"
        elif self._model == "transformers":
            try:
                response = self._pipeline(
                    prompt,
                    max_new_tokens=self.config.max_tokens or 1000,
                    temperature=self.config.temperature or 0.7,
                    **kwargs,
                )
                return response[0]["generated_text"].strip()
            except Exception as e:
                return f"Local model generation failed: {str(e)}"
        else:
            # 模拟实现
            return f"[Local Model] {prompt} - This is a mock response"

    def generate_stream(
        self, prompt: str, **kwargs
    ) -> Generator[str, None, None]:
        """流式生成文本"""
        if self._model == "llama_cpp":
            try:
                # 使用llama.cpp的流式生成
                for chunk in self._llm(
                    prompt,
                    max_tokens=self.config.max_tokens or 1000,
                    temperature=self.config.temperature or 0.7,
                    stream=True,
                    **kwargs,
                ):
                    if "choices" in chunk and chunk["choices"]:
                        text = chunk["choices"][0]["text"]
                        if text:
                            yield text
            except Exception as e:
                yield f"Llama.cpp streaming failed: {str(e)}"
        else:
            # 对于其他模型，使用模拟的流式生成
            response = self.generate(prompt, **kwargs)
            for i in range(0, len(response), 5):
                yield response[i : i + 5]

    def chat(self, messages: List[Dict], **kwargs) -> Dict:
        """对话"""
        if self._model == "llama_cpp":
            # 使用llama.cpp的对话格式
            try:
                response = self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=self.config.max_tokens or 1000,
                    temperature=self.config.temperature or 0.7,
                    **kwargs,
                )
                return response["choices"][0]["message"]
            except Exception as e:
                return {
                    "role": "assistant",
                    "content": f"Llama.cpp chat failed: {str(e)}",
                }
        else:
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
        if self._model == "llama_cpp":
            try:
                # 使用llama.cpp的流式对话
                for chunk in self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=self.config.max_tokens or 1000,
                    temperature=self.config.temperature or 0.7,
                    stream=True,
                    **kwargs,
                ):
                    if "choices" in chunk and chunk["choices"]:
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            yield {
                                "role": delta.get("role", "assistant"),
                                "content": delta["content"],
                            }
            except Exception as e:
                yield {
                    "role": "assistant",
                    "content": f"Llama.cpp streaming chat failed: {str(e)}",
                }
        else:
            # 对于其他模型，使用模拟的流式对话
            response = self.chat(messages, **kwargs)
            content = response["content"]
            for i in range(0, len(content), 5):
                yield {"role": "assistant", "content": content[i : i + 5]}

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        info = {
            "model_type": self._model,
            "model_name": self.model_name,
            "config": {
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "base_url": self.config.base_url,
            },
        }

        if self._model == "llama_cpp" and hasattr(self._llm, "model_path"):
            info["model_path"] = self._llm.model_path

        return info

    def close(self):
        """关闭模型"""
        if self._model == "llama_cpp" and self._llm:
            try:
                # llama-cpp-python目前没有明确的close方法，但我们可以尝试释放资源
                del self._llm
                self._llm = None
            except Exception:
                pass


# 注册到工厂
LLMFactory.register(LLMType.LOCAL, LocalLLM)
