"""llama-cpp集成示例"""

from src.ai.models.model_manager import get_model_manager
from src.ai.types import LLMConfig, LLMType


def run_llama_cpp_example():
    """运行llama-cpp集成示例"""
    print("=== llama-cpp Integration Example ===")
    
    # 创建模型管理器
    model_manager = get_model_manager()
    
    # 配置本地模型
    # 注意：请确保你有一个有效的llama模型文件
    # 你可以从https://huggingface.co/TheBloke下载模型
    local_config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="llama2",
        # 模型路径配置
        # 方式1: 直接指定路径
        # base_url="path/to/your/model.gguf",
        # 方式2: 使用环境变量LLAMA_CPP_MODEL_PATH
        # 方式3: 默认为models/llama-2-7b-chat.Q4_0.gguf
        temperature=0.7,
        max_tokens=500
    )
    
    try:
        # 创建本地模型实例
        local_model = model_manager.create_model(local_config)
        print(f"\nModel Info: {local_model.get_model_info()}")
        
        # 示例1: 文本生成
        print("\n=== Text Generation Example ===")
        prompt = "Write a short essay on the future of artificial intelligence."
        print(f"Prompt: {prompt}")
        response = local_model.generate(prompt)
        print(f"Response: {response}")
        
        # 示例2: 流式文本生成
        print("\n=== Streaming Text Generation Example ===")
        prompt = "Explain quantum computing in simple terms."
        print(f"Prompt: {prompt}")
        print("Streaming response:")
        for chunk in local_model.generate_stream(prompt):
            print(chunk, end="", flush=True)
        print()
        
        # 示例3: 对话
        print("\n=== Chat Example ===")
        messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you! How can I help you today?"},
            {"role": "user", "content": "What's the capital of France?"}
        ]
        chat_response = local_model.chat(messages)
        print(f"Chat response: {chat_response}")
        
        # 示例4: 流式对话
        print("\n=== Streaming Chat Example ===")
        messages = [
            {"role": "user", "content": "Write a short story about a time traveler."}
        ]
        print("Streaming chat response:")
        for chunk in local_model.chat_stream(messages):
            print(chunk['content'], end="", flush=True)
        print()
        
        # 关闭模型
        local_model.close()
        print("\nExample completed successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Note: Make sure you have llama-cpp-python installed and a valid model file.")
        print("Install llama-cpp-python: pip install llama-cpp-python")
        print("Download models from: https://huggingface.co/TheBloke")


if __name__ == "__main__":
    run_llama_cpp_example()
