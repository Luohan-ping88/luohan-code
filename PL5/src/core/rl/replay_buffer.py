"""
经验回放缓冲区模块 - 支持FIFO存储、随机采样和优先级采样
"""

import numpy as np
from typing import Any, Tuple, List, Optional
from collections import deque
import random


class ReplayBuffer:
    """
    基础FIFO经验回放缓冲区
    """
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
    
    def add(self, state: np.ndarray, action: int, reward: float, 
            next_state: np.ndarray, done: bool) -> None:
        """
        添加经验到缓冲区
        """
        self.buffer.append((state, action, reward, next_state, done))
    
    def sample(self, batch_size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        随机采样一批经验
        """
        if len(self.buffer) < batch_size:
            batch_size = len(self.buffer)
        
        batch = random.sample(self.buffer, batch_size)
        
        states = np.array([s[0] for s in batch])
        actions = np.array([s[1] for s in batch])
        rewards = np.array([s[2] for s in batch])
        next_states = np.array([s[3] for s in batch])
        dones = np.array([s[4] for s in batch])
        
        return states, actions, rewards, next_states, dones
    
    def __len__(self) -> int:
        return len(self.buffer)


class PrioritizedReplayBuffer:
    """
    优先级经验回放缓冲区
    """
    
    def __init__(self, capacity: int, alpha: float = 0.6, beta: float = 0.4, 
                 beta_increment: float = 0.001):
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.beta_increment = beta_increment
        
        self.buffer = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.position = 0
        self.size = 0
    
    def add(self, state: np.ndarray, action: int, reward: float, 
            next_state: np.ndarray, done: bool, priority: Optional[float] = None) -> None:
        """
        添加经验到缓冲区
        """
        max_priority = self.priorities.max() if self.size > 0 else 1.0
        if priority is not None:
            max_priority = max(max_priority, priority)
        
        if self.size < self.capacity:
            self.buffer.append((state, action, reward, next_state, done))
            self.size += 1
        else:
            self.buffer[self.position] = (state, action, reward, next_state, done)
        
        self.priorities[self.position] = max_priority
        self.position = (self.position + 1) % self.capacity
    
    def sample(self, batch_size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        按优先级采样一批经验
        """
        if self.size < batch_size:
            batch_size = self.size
        
        priorities = self.priorities[:self.size]
        probs = priorities ** self.alpha
        probs /= probs.sum()
        
        indices = np.random.choice(self.size, batch_size, p=probs, replace=False)
        weights = (self.size * probs[indices]) ** (-self.beta)
        weights /= weights.max()
        
        self.beta = min(1.0, self.beta + self.beta_increment)
        
        batch = [self.buffer[i] for i in indices]
        
        states = np.array([s[0] for s in batch])
        actions = np.array([s[1] for s in batch])
        rewards = np.array([s[2] for s in batch])
        next_states = np.array([s[3] for s in batch])
        dones = np.array([s[4] for s in batch])
        
        return states, actions, rewards, next_states, dones, indices, weights
    
    def update_priorities(self, indices: np.ndarray, priorities: np.ndarray) -> None:
        """
        更新经验的优先级
        """
        for idx, priority in zip(indices, priorities):
            self.priorities[idx] = priority + 1e-6
    
    def __len__(self) -> int:
        return self.size
