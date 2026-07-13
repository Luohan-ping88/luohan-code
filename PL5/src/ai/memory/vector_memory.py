"""向量记忆实现"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np

from .base import BaseMemory
from ..ai_types import MemoryConfig, MemoryType


class VectorMemory(BaseMemory):
    """向量记忆
    
    用于存储和检索向量表示的记忆项，支持语义搜索。
    """
    
    def __init__(self, config: MemoryConfig):
        super().__init__(config)
        self._embeddings = []  # 向量嵌入
        self._items = []  # 原始记忆项
        self._ids = []  # 记忆项ID
        self._timestamps = []  # 时间戳
    
    def add(self, item: Any, embedding: Optional[np.ndarray] = None) -> bool:
        """添加记忆项
        
        Args:
            item: 记忆项
            embedding: 向量嵌入，如果为None则使用默认嵌入
            
        Returns:
            是否添加成功
        """
        try:
            # 生成默认嵌入（如果没有提供）
            if embedding is None:
                embedding = self._generate_default_embedding(item)
            
            # 确保嵌入维度正确
            if len(embedding) != self.embedding_dim:
                embedding = self._resize_embedding(embedding)
            
            # 添加到存储
            self._embeddings.append(embedding)
            self._items.append(item)
            self._ids.append(f"vec_{int(datetime.now().timestamp() * 1000)}")
            self._timestamps.append(datetime.now().timestamp())
            
            self._maintain_size()
            return True
        except Exception:
            return False
    
    def get(self, key: Any = None) -> Optional[Any]:
        """获取记忆项"""
        try:
            if key is None:
                return self._items[-1] if self._items else None
            
            # 支持按ID检索
            if isinstance(key, str) and key.startswith('vec_'):
                try:
                    idx = self._ids.index(key)
                    return self._items[idx]
                except ValueError:
                    pass
            
            # 支持按向量相似度检索
            if isinstance(key, np.ndarray):
                results = self.search_by_vector(key, top_k=1)
                return results[0][0] if results else None
            
            # 支持按内容检索
            if isinstance(key, str):
                results = self.search_by_text(key, top_k=1)
                return results[0][0] if results else None
            
            return None
        except Exception:
            return None
    
    def get_all(self) -> List[Any]:
        """获取所有记忆项"""
        return self._items
    
    def remove(self, key: Any) -> bool:
        """移除记忆项"""
        try:
            # 支持按ID移除
            if isinstance(key, str) and key.startswith('vec_'):
                try:
                    idx = self._ids.index(key)
                    self._remove_by_index(idx)
                    return True
                except ValueError:
                    pass
            
            # 支持按内容移除
            if key in self._items:
                idx = self._items.index(key)
                self._remove_by_index(idx)
                return True
            
            return False
        except Exception:
            return False
    
    def clear(self) -> bool:
        """清空记忆"""
        try:
            self._embeddings.clear()
            self._items.clear()
            self._ids.clear()
            self._timestamps.clear()
            return True
        except Exception:
            return False
    
    def size(self) -> int:
        """获取记忆大小"""
        return len(self._items)
    
    def search_by_vector(self, query_vector: np.ndarray, top_k: int = 5) -> List[Tuple[Any, float]]:
        """按向量搜索
        
        Args:
            query_vector: 查询向量
            top_k: 返回前k个结果
            
        Returns:
            (记忆项, 相似度) 元组列表
        """
        if not self._embeddings:
            return []
        
        try:
            # 确保查询向量维度正确
            if len(query_vector) != self.embedding_dim:
                query_vector = self._resize_embedding(query_vector)
            
            # 计算余弦相似度
            similarities = []
            for embedding in self._embeddings:
                sim = self._cosine_similarity(query_vector, embedding)
                similarities.append(sim)
            
            # 排序并返回前k个结果
            sorted_indices = np.argsort(similarities)[::-1][:top_k]
            results = []
            for idx in sorted_indices:
                results.append((self._items[idx], similarities[idx]))
            
            return results
        except Exception:
            return []
    
    def search_by_text(self, query: str, top_k: int = 5) -> List[Tuple[Any, float]]:
        """按文本搜索
        
        Args:
            query: 查询文本
            top_k: 返回前k个结果
            
        Returns:
            (记忆项, 相似度) 元组列表
        """
        # 生成查询文本的嵌入
        query_embedding = self._generate_default_embedding(query)
        return self.search_by_vector(query_embedding, top_k)
    
    def _remove_by_index(self, idx: int):
        """按索引移除记忆项"""
        if 0 <= idx < len(self._items):
            self._embeddings.pop(idx)
            self._items.pop(idx)
            self._ids.pop(idx)
            self._timestamps.pop(idx)
    
    def _generate_default_embedding(self, item: Any) -> np.ndarray:
        """生成默认嵌入
        
        简单的基于文本的嵌入生成方法
        """
        text = str(item)
        # 基于字符频率的简单嵌入
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # 生成固定维度的嵌入
        embedding = np.zeros(self.embedding_dim)
        for i, (char, count) in enumerate(char_counts.items()):
            if i >= self.embedding_dim:
                break
            embedding[i] = count / len(text)
        
        return embedding
    
    def _resize_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """调整嵌入维度"""
        if len(embedding) == self.embedding_dim:
            return embedding
        
        if len(embedding) > self.embedding_dim:
            # 截断
            return embedding[:self.embedding_dim]
        else:
            # 填充
            return np.pad(embedding, (0, self.embedding_dim - len(embedding)))
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot_product / (norm1 * norm2)
        except Exception:
            return 0.0
    
    def get_embedding(self, idx: int) -> Optional[np.ndarray]:
        """获取指定索引的嵌入"""
        if 0 <= idx < len(self._embeddings):
            return self._embeddings[idx]
        return None
    
    def get_ids(self) -> List[str]:
        """获取所有记忆项ID"""
        return self._ids
