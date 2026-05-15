"""模型管理系统测试"""

import unittest
from src.ai.models.model_manager import get_model_manager
from src.ai.types import LLMConfig, LLMType


class TestModelManager(unittest.TestCase):
    """模型管理器测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 重置模型管理器
        from src.ai.models.model_manager import reset_model_manager
        reset_model_manager()
        self.model_manager = get_model_manager()
    
    def test_create_model(self):
        """测试创建模型"""
        # 创建OpenAI模型
        openai_config = LLMConfig(
            model_type=LLMType.OPENAI,
            model_name="gpt-3.5-turbo",
            api_key="test_key",
            temperature=0.7,
            max_tokens=1000
        )
        openai_model = self.model_manager.create_model(openai_config)
        self.assertIsNotNone(openai_model)
        
        # 创建HuggingFace模型
        hf_config = LLMConfig(
            model_type=LLMType.HUGGINGFACE,
            model_name="gpt2",
            temperature=0.7,
            max_tokens=1000
        )
        hf_model = self.model_manager.create_model(hf_config)
        self.assertIsNotNone(hf_model)
    
    def test_get_model(self):
        """测试获取模型"""
        # 创建模型
        openai_config = LLMConfig(
            model_type=LLMType.OPENAI,
            model_name="gpt-3.5-turbo",
            api_key="test_key"
        )
        self.model_manager.create_model(openai_config)
        
        # 获取默认模型
        default_model = self.model_manager.get_model()
        self.assertIsNotNone(default_model)
        
        # 获取指定模型
        model_id = "openai_gpt-3.5-turbo"
        model = self.model_manager.get_model(model_id)
        self.assertIsNotNone(model)
    
    def test_list_models(self):
        """测试列出模型"""
        # 创建模型
        openai_config = LLMConfig(
            model_type=LLMType.OPENAI,
            model_name="gpt-3.5-turbo",
            api_key="test_key"
        )
        self.model_manager.create_model(openai_config)
        
        hf_config = LLMConfig(
            model_type=LLMType.HUGGINGFACE,
            model_name="gpt2"
        )
        self.model_manager.create_model(hf_config)
        
        # 列出模型
        models = self.model_manager.list_models()
        self.assertEqual(len(models), 2)
        self.assertIn("openai_gpt-3.5-turbo", models)
        self.assertIn("huggingface_gpt2", models)
    
    def test_set_default_model(self):
        """测试设置默认模型"""
        # 创建模型
        openai_config = LLMConfig(
            model_type=LLMType.OPENAI,
            model_name="gpt-3.5-turbo",
            api_key="test_key"
        )
        self.model_manager.create_model(openai_config)
        
        hf_config = LLMConfig(
            model_type=LLMType.HUGGINGFACE,
            model_name="gpt2"
        )
        self.model_manager.create_model(hf_config)
        
        # 设置默认模型
        hf_model_id = "huggingface_gpt2"
        self.model_manager.set_default_model(hf_model_id)
        
        # 验证默认模型
        default_model = self.model_manager.get_model()
        self.assertEqual(default_model.model_name, "gpt2")
    
    def test_remove_model(self):
        """测试移除模型"""
        # 创建模型
        openai_config = LLMConfig(
            model_type=LLMType.OPENAI,
            model_name="gpt-3.5-turbo",
            api_key="test_key"
        )
        self.model_manager.create_model(openai_config)
        
        hf_config = LLMConfig(
            model_type=LLMType.HUGGINGFACE,
            model_name="gpt2"
        )
        self.model_manager.create_model(hf_config)
        
        # 移除模型
        openai_model_id = "openai_gpt-3.5-turbo"
        self.model_manager.remove_model(openai_model_id)
        
        # 验证模型已移除
        models = self.model_manager.list_models()
        self.assertEqual(len(models), 1)
        self.assertNotIn(openai_model_id, models)
    
    def test_clear_models(self):
        """测试清空模型"""
        # 创建模型
        openai_config = LLMConfig(
            model_type=LLMType.OPENAI,
            model_name="gpt-3.5-turbo",
            api_key="test_key"
        )
        self.model_manager.create_model(openai_config)
        
        # 清空模型
        self.model_manager.clear_models()
        
        # 验证模型已清空
        models = self.model_manager.list_models()
        self.assertEqual(len(models), 0)
    
    def test_get_model_info(self):
        """测试获取模型信息"""
        # 创建模型
        openai_config = LLMConfig(
            model_type=LLMType.OPENAI,
            model_name="gpt-3.5-turbo",
            api_key="test_key",
            temperature=0.7,
            max_tokens=1000
        )
        self.model_manager.create_model(openai_config)
        
        # 获取模型信息
        model_id = "openai_gpt-3.5-turbo"
        model_info = self.model_manager.get_model_info(model_id)
        
        # 验证模型信息
        self.assertEqual(model_info["model_id"], model_id)
        self.assertEqual(model_info["model_type"], "openai")
        self.assertEqual(model_info["model_name"], "gpt-3.5-turbo")
        self.assertEqual(model_info["temperature"], 0.7)
        self.assertEqual(model_info["max_tokens"], 1000)
        self.assertTrue(model_info["is_default"])
    
    def test_list_model_info(self):
        """测试列出模型信息"""
        # 创建模型
        openai_config = LLMConfig(
            model_type=LLMType.OPENAI,
            model_name="gpt-3.5-turbo",
            api_key="test_key"
        )
        self.model_manager.create_model(openai_config)
        
        hf_config = LLMConfig(
            model_type=LLMType.HUGGINGFACE,
            model_name="gpt2"
        )
        self.model_manager.create_model(hf_config)
        
        # 列出模型信息
        model_infos = self.model_manager.list_model_info()
        self.assertEqual(len(model_infos), 2)
        
        # 验证模型信息
        openai_info = next(info for info in model_infos if info["model_type"] == "openai")
        self.assertEqual(openai_info["model_name"], "gpt-3.5-turbo")
        
        hf_info = next(info for info in model_infos if info["model_type"] == "huggingface")
        self.assertEqual(hf_info["model_name"], "gpt2")


if __name__ == "__main__":
    unittest.main()