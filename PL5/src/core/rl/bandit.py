"""
多臂老虎机算法模块 - UCB、Thompson Sampling、Epsilon-Greedy
"""

import numpy as np
from typing import Optional


class EpsilonGreedyBandit:
    """
    Epsilon-Greedy多臂老虎机算法
    """
    
    def __init__(self, n_arms: int, epsilon: float = 0.1, decay_rate: float = 0.995):
        self.n_arms = n_arms
        self.epsilon = epsilon
        self.decay_rate = decay_rate
        self.counts = np.zeros(n_arms)
        self.values = np.zeros(n_arms)
    
    def select(self) -> int:
        """
        选择动作
        """
        if np.random.random() < self.epsilon:
            return np.random.randint(self.n_arms)
        else:
            return np.argmax(self.values)
    
    def update(self, arm: int, reward: float) -> None:
        """
        更新参数
        """
        self.counts[arm] += 1
        n = self.counts[arm]
        value = self.values[arm]
        self.values[arm] = ((n - 1) / n) * value + (1 / n) * reward
        self.epsilon *= self.decay_rate
    
    def reset(self) -> None:
        """
        重置状态
        """
        self.counts = np.zeros(self.n_arms)
        self.values = np.zeros(self.n_arms)


class UCBBandit:
    """
    UCB多臂老虎机算法
    """
    
    def __init__(self, n_arms: int, c: float = 2.0):
        self.n_arms = n_arms
        self.c = c
        self.counts = np.zeros(n_arms)
        self.values = np.zeros(n_arms)
        self.total_counts = 0
    
    def select(self) -> int:
        """
        选择动作
        """
        for arm in range(self.n_arms):
            if self.counts[arm] == 0:
                return arm
        
        ucb_values = self.values + self.c * np.sqrt(np.log(self.total_counts) / self.counts)
        return np.argmax(ucb_values)
    
    def update(self, arm: int, reward: float) -> None:
        """
        更新参数
        """
        self.counts[arm] += 1
        self.total_counts += 1
        n = self.counts[arm]
        value = self.values[arm]
        self.values[arm] = ((n - 1) / n) * value + (1 / n) * reward
    
    def reset(self) -> None:
        """
        重置状态
        """
        self.counts = np.zeros(self.n_arms)
        self.values = np.zeros(self.n_arms)
        self.total_counts = 0


class ThompsonSamplingBandit:
    """
    Thompson Sampling多臂老虎机算法
    """
    
    def __init__(self, n_arms: int, alpha: float = 1.0, beta: float = 1.0):
        self.n_arms = n_arms
        self.alpha = np.ones(n_arms) * alpha
        self.beta = np.ones(n_arms) * beta
    
    def select(self) -> int:
        """
        选择动作
        """
        samples = np.random.beta(self.alpha, self.beta)
        return np.argmax(samples)
    
    def update(self, arm: int, reward: float) -> None:
        """
        更新参数
        """
        self.alpha[arm] += reward
        self.beta[arm] += (1 - reward)
    
    def reset(self) -> None:
        """
        重置状态
        """
        self.alpha = np.ones(self.n_arms)
        self.beta = np.ones(self.n_arms)
