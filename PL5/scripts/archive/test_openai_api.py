"""测试OpenAI API适配器"""

import os
from src.ai.models.model_manager import get_model_manager
from src.ai.types import LLMConfig, LLMType


def test_openai_api():
    """测试OpenAI API适配器"""
    print("=== 测试OpenAI API适配器 ===")
    
    # 创建模型管理器
    model_manager = get_model_manager()
    
    # 测试1: 创建OpenAI模型实例
    print("\n1. 测试创建OpenAI模型实例")
    config = LLMConfig(
        model_type=LLMType.OPENAI,
        model_name="gpt-3.5-turbo",
        api_key=os.environ.get("OPENAI_API_KEY"),
        temperature=0.7,
        max_tokens=500
    )
    
    model = model_manager.create_model(config)
    model_id = f"{config.model_type.value}_{config.model_name}"
    print(f"创建模型成功，模型ID: {model_id}")
    
    # 测试2: 检查API密钥状态
    print("\n2. 测试API密钥状态")
    api_key_status = model.get_api_key_status()
    print(f"API密钥状态: {'有效' if api_key_status else '无效（使用模拟实现）'}")
    
    # 测试3: 文本生成
    print("\n3. 测试文本生成")
    prompt = "请简要介绍一下人工智能"
    result = model.generate(prompt)
    print(f"生成结果: {result}")
    
    # 测试4: 流式文本生成
    print("\n4. 测试流式文本生成")
    print("流式输出:")
    for chunk in model.generate_stream("请简要介绍一下机器学习"):
        print(chunk, end="", flush=True)
    print()
    
    # 测试5: 对话功能
    print("\n5. 测试对话功能")
    messages = [
        {"role": "user", "content": "你好，我叫小明"},
        {"role": "assistant", "content": "你好，小明！很高兴认识你。"},
        {"role": "user", "content": "你能告诉我今天天气怎么样吗？"}
    ]
    response = model.chat(messages)
    print(f"对话响应: {response['content']}")
    
    # 测试6: 流式对话
    print("\n6. 测试流式对话")
    print("流式对话输出:")
    for chunk in model.chat_stream([{"role": "user", "content": "请简要介绍一下OpenAI"}]):
        print(chunk['content'], end="", flush=True)
    print()
    
    # 测试7: 更新API密钥
    print("\n7. 测试更新API密钥")
    new_api_key = os.environ.get("OPENAI_API_KEY")
    if new_api_key:
        model.update_api_key(new_api_key)
        new_status = model.get_api_key_status()
        print(f"更新API密钥后状态: {'有效' if new_status else '无效'}")
    else:
        print("未设置OPENAI_API_KEY环境变量，跳过API密钥更新测试")
    
    # 测试8: 列出模型信息
    print("\n8. 测试列出模型信息")
    model_info = model_manager.get_model_info(model_id)
    print(f"模型信息: {model_info}")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_openai_api()
