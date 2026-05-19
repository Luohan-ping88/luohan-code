"""测试llama-cpp集成"""

import sys
from src.ai.models.model_manager import get_model_manager
from src.ai.types import LLMConfig, LLMType


def test_llama_cpp_integration():
    """测试llama-cpp集成"""
    print("Testing llama-cpp integration...")
    
    # 创建模型管理器
    model_manager = get_model_manager()
    
    # 配置本地模型
    local_config = LLMConfig(
        model_type=LLMType.LOCAL,
        model_name="llama2",
        # 这里可以设置实际的模型路径
        base_url="models/llama-2-7b-chat.Q4_0.gguf",
        temperature=0.7,
        max_tokens=500
    )
    
    try:
        # 创建本地模型实例
        local_model = model_manager.create_model(local_config)
        print(f"Model created successfully: {local_model.get_model_info()}")
        
        # 测试文本生成
        print("\nTesting text generation...")
        prompt = "Write a short poem about AI."
        response = local_model.generate(prompt)
        print(f"Prompt: {prompt}")
        print(f"Response: {response}")
        
        # 测试流式生成
        print("\nTesting streaming generation...")
        prompt = "Write a short story about a robot learning to paint."
        print(f"Prompt: {prompt}")
        print("Streaming response:")
        for chunk in local_model.generate_stream(prompt):
            print(chunk, end="", flush=True)
        print()
        
        # 测试对话
        print("\nTesting chat...")
        messages = [
            {"role": "user", "content": "Hello, who are you?"},
            {"role": "assistant", "content": "I am a helpful AI assistant."},
            {"role": "user", "content": "What can you do?"}
        ]
        chat_response = local_model.chat(messages)
        print(f"Chat response: {chat_response}")
        
        # 测试流式对话
        print("\nTesting streaming chat...")
        messages = [
            {"role": "user", "content": "Tell me a joke about programming."}
        ]
        print("Streaming chat response:")
        for chunk in local_model.chat_stream(messages):
            print(chunk['content'], end="", flush=True)
        print()
        
        # 关闭模型
        local_model.close()
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Note: If you see a 'Model file not found' error, please make sure you have a llama model file in the specified path.")
        print("You can download models from: https://huggingface.co/TheBloke")


if __name__ == "__main__":
    test_llama_cpp_integration()
