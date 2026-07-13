"""OpenAI API适配器使用示例"""

import os
from src.ai.models.model_manager import get_model_manager
from src.ai.types import LLMConfig, LLMType


def main():
    """示例主函数"""
    print("=== OpenAI API适配器使用示例 ===")
    
    # 创建模型管理器
    model_manager = get_model_manager()
    
    # 方式1: 直接在代码中设置API密钥
    print("\n1. 方式1: 直接在代码中设置API密钥")
    api_key = "your-openai-api-key-here"  # 替换为实际的API密钥
    
    config = LLMConfig(
        model_type=LLMType.OPENAI,
        model_name="gpt-3.5-turbo",
        api_key=api_key,
        temperature=0.7,
        max_tokens=500
    )
    
    model = model_manager.create_model(config)
    model_id = f"{config.model_type.value}_{config.model_name}"
    print(f"创建模型成功，模型ID: {model_id}")
    
    # 检查API密钥状态
    api_key_status = model.get_api_key_status()
    print(f"API密钥状态: {'有效' if api_key_status else '无效（使用模拟实现）'}")
    
    # 方式2: 从环境变量读取API密钥
    print("\n2. 方式2: 从环境变量读取API密钥")
    # 注意：需要先设置环境变量 OPENAI_API_KEY
    # 例如：export OPENAI_API_KEY=your-openai-api-key-here (Linux/Mac)
    # 或：set OPENAI_API_KEY=your-openai-api-key-here (Windows)
    
    config_from_env = LLMConfig(
        model_type=LLMType.OPENAI,
        model_name="gpt-3.5-turbo",
        # 不设置api_key，会自动从环境变量读取
        temperature=0.7,
        max_tokens=500
    )
    
    model_from_env = model_manager.create_model(config_from_env)
    model_id_from_env = f"{config_from_env.model_type.value}_{config_from_env.model_name}"
    print(f"从环境变量创建模型成功，模型ID: {model_id_from_env}")
    
    # 检查API密钥状态
    api_key_status_from_env = model_from_env.get_api_key_status()
    print(f"从环境变量读取的API密钥状态: {'有效' if api_key_status_from_env else '无效（使用模拟实现）'}")
    
    # 文本生成示例
    print("\n3. 文本生成示例")
    prompt = "请简要介绍一下人工智能的发展历史"
    print(f"提示词: {prompt}")
    result = model.generate(prompt)
    print(f"生成结果: {result}")
    
    # 流式文本生成示例
    print("\n4. 流式文本生成示例")
    prompt_stream = "请简要介绍一下机器学习的基本原理"
    print(f"提示词: {prompt_stream}")
    print("流式输出:")
    for chunk in model.generate_stream(prompt_stream):
        print(chunk, end="", flush=True)
    print()
    
    # 对话功能示例
    print("\n5. 对话功能示例")
    messages = [
        {"role": "system", "content": "你是一个 helpful 的助手"},
        {"role": "user", "content": "你好，我想了解一下Python编程"},
        {"role": "assistant", "content": "你好！Python是一种简单易学的编程语言，广泛应用于数据分析、人工智能、Web开发等领域。"},
        {"role": "user", "content": "能给我推荐一些学习Python的资源吗？"}
    ]
    print("对话历史:")
    for msg in messages:
        print(f"{msg['role']}: {msg['content']}")
    
    response = model.chat(messages)
    print(f"\n助手响应: {response['content']}")
    
    # 流式对话示例
    print("\n6. 流式对话示例")
    messages_stream = [
        {"role": "user", "content": "请简要介绍一下OpenAI的GPT模型"}
    ]
    print("流式对话输出:")
    for chunk in model.chat_stream(messages_stream):
        print(chunk['content'], end="", flush=True)
    print()
    
    # 更新API密钥示例
    print("\n7. 更新API密钥示例")
    new_api_key = "your-new-openai-api-key-here"  # 替换为新的API密钥
    model.update_api_key(new_api_key)
    new_status = model.get_api_key_status()
    print(f"更新API密钥后状态: {'有效' if new_status else '无效'}")
    
    # 列出所有模型
    print("\n8. 列出所有模型")
    models = model_manager.list_models()
    print(f"已创建的模型: {models}")
    
    # 获取模型信息
    print("\n9. 获取模型信息")
    for model_id in models:
        info = model_manager.get_model_info(model_id)
        print(f"模型 {model_id}: {info}")
    
    print("\n=== 示例完成 ===")


if __name__ == "__main__":
    main()
