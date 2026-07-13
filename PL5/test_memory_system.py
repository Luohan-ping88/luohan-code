"""记忆系统测试"""

import unittest
from src.ai.memory import MemoryFactory, MemoryManager
from src.ai.types import MemoryConfig, MemoryType, ConversationMessage, ExecutionRecord


class TestMemorySystem(unittest.TestCase):
    """记忆系统测试"""
    
    def setUp(self):
        """设置测试环境"""
        import tempfile
        import os
        
        # 创建临时文件路径
        temp_dir = tempfile.mkdtemp()
        self.temp_files = []
        
        # 创建默认配置
        self.config = MemoryConfig(
            memory_type=MemoryType.CONVERSATION,
            max_size=10,
            ttl=3600,
            embedding_dim=128
        )
        
    def tearDown(self):
        """清理测试环境"""
        import os
        for file_path in self.temp_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
    
    def test_memory_factory(self):
        """测试记忆工厂"""
        # 测试创建对话记忆
        conversation_memory = MemoryFactory.create_memory(MemoryType.CONVERSATION, self.config)
        self.assertEqual(conversation_memory.memory_type, MemoryType.CONVERSATION)
        
        # 测试创建执行记忆
        execution_memory = MemoryFactory.create_memory(MemoryType.EXECUTION, self.config)
        self.assertEqual(execution_memory.memory_type, MemoryType.EXECUTION)
        
        # 测试创建长期记忆
        long_term_memory = MemoryFactory.create_memory(MemoryType.LONG_TERM, self.config)
        self.assertEqual(long_term_memory.memory_type, MemoryType.LONG_TERM)
        
        # 测试创建向量记忆
        vector_memory = MemoryFactory.create_memory(MemoryType.VECTOR, self.config)
        self.assertEqual(vector_memory.memory_type, MemoryType.VECTOR)
    
    def test_memory_manager(self):
        """测试记忆管理器"""
        manager = MemoryManager()
        
        # 测试创建并添加记忆
        conversation_memory = manager.create_and_add_memory("conversation", MemoryType.CONVERSATION, self.config)
        self.assertIsNotNone(conversation_memory)
        
        # 测试获取记忆
        retrieved_memory = manager.get_memory("conversation")
        self.assertIsNotNone(retrieved_memory)
        
        # 测试列出记忆
        memories = manager.list_memories()
        self.assertIn("conversation", memories)
        
        # 测试移除记忆
        result = manager.remove_memory("conversation")
        self.assertTrue(result)
        
        # 测试清空所有记忆
        manager.create_and_add_memory("test", MemoryType.CONVERSATION, self.config)
        manager.clear_all()
        test_memory = manager.get_memory("test")
        self.assertEqual(test_memory.size(), 0)
    
    def test_conversation_memory(self):
        """测试对话记忆"""
        memory = MemoryFactory.create_memory(MemoryType.CONVERSATION, self.config)
        
        # 测试添加消息
        result = memory.add_user_message("Hello")
        self.assertTrue(result)
        
        # 测试获取消息
        message = memory.get()
        self.assertIsNotNone(message)
        self.assertEqual(message.content, "Hello")
        
        # 测试获取所有消息
        messages = memory.get_all()
        self.assertEqual(len(messages), 1)
        
        # 测试获取最近n条消息
        memory.add_assistant_message("Hi there!")
        last_two = memory.get_last_n_messages(2)
        self.assertEqual(len(last_two), 2)
        
        # 测试按角色获取消息
        user_messages = memory.get_messages_by_role("user")
        self.assertEqual(len(user_messages), 1)
        
        # 测试获取消息历史
        history = memory.get_message_history()
        self.assertIn("Hello", history)
        
        # 测试移除消息
        result = memory.remove(0)
        self.assertTrue(result)
        
        # 测试清空记忆
        result = memory.clear()
        self.assertTrue(result)
        self.assertEqual(memory.size(), 0)
    
    def test_long_term_memory(self):
        """测试长期记忆"""
        import tempfile
        import os
        
        # 创建唯一的存储路径
        temp_file = tempfile.mktemp(suffix='.json')
        self.temp_files.append(temp_file)
        
        # 创建配置
        config = MemoryConfig(
            memory_type=MemoryType.LONG_TERM,
            max_size=10,
            ttl=3600,
            embedding_dim=128,
            storage_path=temp_file
        )
        
        memory = MemoryFactory.create_memory(MemoryType.LONG_TERM, config)
        
        # 测试添加记忆
        result = memory.add({"key": "value", "data": "test"})
        self.assertTrue(result)
        
        # 测试获取记忆
        item = memory.get()
        self.assertIsNotNone(item)
        
        # 测试搜索记忆
        results = memory.search("test")
        self.assertEqual(len(results), 1)
        
        # 测试按时间范围获取记忆
        import time
        start_time = time.time() - 100
        end_time = time.time() + 100
        results = memory.get_by_time_range(start_time, end_time)
        self.assertEqual(len(results), 1)
        
        # 测试移除记忆
        result = memory.remove("test")
        self.assertTrue(result)
        
        # 测试清空记忆
        result = memory.clear()
        self.assertTrue(result)
        self.assertEqual(memory.size(), 0)
    
    def test_vector_memory(self):
        """测试向量记忆"""
        memory = MemoryFactory.create_memory(MemoryType.VECTOR, self.config)
        
        # 测试添加记忆
        result = memory.add("test content")
        self.assertTrue(result)
        
        # 测试获取记忆
        item = memory.get()
        self.assertIsNotNone(item)
        
        # 测试按文本搜索
        results = memory.search_by_text("test")
        self.assertEqual(len(results), 1)
        
        # 测试获取嵌入
        embedding = memory.get_embedding(0)
        self.assertIsNotNone(embedding)
        
        # 测试获取所有ID
        ids = memory.get_ids()
        self.assertEqual(len(ids), 1)
        
        # 测试移除记忆
        result = memory.remove("test content")
        self.assertTrue(result)
        
        # 测试清空记忆
        result = memory.clear()
        self.assertTrue(result)
        self.assertEqual(memory.size(), 0)


if __name__ == "__main__":
    unittest.main()