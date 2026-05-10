"""模型管理器使用示例"""

from src.ai.models.model_manager import get_model_manager
from src.ai.types import LLMConfig, LLMType


def main():
    """主函数"""
    # 获取模型管理器
    model_manager = get_model_manager()
    
    print("=== 模型管理系统示例 ===")
    
    # 1. 创建OpenAI模型
    print("\n1. 创建OpenAI模型...")
    openai_config = LLMConfig(
        model_type=LLMType.OPENAI,
        model_name="gpt-3.5-turbo",
        api_key="your_api_key_here",  # 请替换为实际的API密钥
        temperature=0.7,
        max_tokens=1000
    )
    openai_model = model_manager.create_model(openai_config)
    print(f"创建成功: {openai_model.model_name}")
    
    # 2. 创建HuggingFace模型
    print("\n2. 创建HuggingFace模型...")
    hf_config = LLMConfig(
        model_type=LLMType.HUGGINGFACE,
        model_name="gpt2",
        temperature=0.7,
        max_tokens=1000
    )
    hf_model = model_manager.create_model(hf_config)
    print(f"创建成功: {hf_model.model_name}")
    
    # 3. 列出所有模型
    print("\n3. 列出所有模型...")
    models = model_manager.list_models()
    for model_id in models:
        print(f"- {model_id}")
    
    # 4. 获取模型信息
    print("\n4. 获取模型信息...")
    for model_id in models:
        info = model_manager.get_model_info(model_id)
        print(f"\n模型ID: {info['model_id']}")
        print(f"模型类型: {info['model_type']}")
        print(f"模型名称: {info['model_name']}")
        print(f"温度参数: {info['temperature']}")
        print(f"最大token数: {info['max_tokens']}")
        print(f"是否默认: {info['is_default']}")
    
    # 5. 使用默认模型生成文本
    print("\n5. 使用默认模型生成文本...")
    prompt = "请简要介绍人工智能的发展历程"
    default_model = model_manager.get_model()
    print(f"使用模型: {default_model.model_name}")
    response = default_model.generate(prompt)
    print(f"生成结果: {response}")
    
    # 6. 使用指定模型进行对话
    print("\n6. 使用指定模型进行对话...")
    hf_model_id = "huggingface_gpt2"
    hf_model = model_manager.get_model(hf_model_id)
    messages = [
        {"role": "user", "content": "你好，我是一名学生"},
        {"role": "assistant", "content": "你好！有什么我可以帮助你的吗？"},
        {"role": "user", "content": "请解释一下什么是机器学习"}
    ]
    chat_response = hf_model.chat(messages)
    print(f"对话结果: {chat_response['content']}")
    
    # 7. 设置默认模型
    print("\n7. 设置默认模型...")
    model_manager.set_default_model(hf_model_id)
    new_default_model = model_manager.get_model()
    print(f"新的默认模型: {new_default_model.model_name}")
    
    # 8. 移除模型
    print("\n8. 移除模型...")
    openai_model_id = "openai_gpt-3.5-turbo"
    model_manager.remove_model(openai_model_id)
    remaining_models = model_manager.list_models()
    print("剩余模型:")
    for model_id in remaining_models:
        print(f"- {model_id}")
    
    # 9. 清空所有模型
    print("\n9. 清空所有模型...")
    model_manager.clear_models()
    print(f"模型数量: {len(model_manager.list_models())}")
    
    print("\n=== 示例结束 ===")


if __name__ == "__main__":
    main()