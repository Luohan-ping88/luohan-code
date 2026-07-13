"""
强化学习框架模块 - 完整的强化学习算法实现
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

from .replay_buffer import ReplayBuffer, PrioritizedReplayBuffer
from .bandit import EpsilonGreedyBandit, UCBBandit, ThompsonSamplingBandit

# 尝试导入PyTorch相关模块，失败时不影响核心功能
try:
    from .dqn import QNetwork, DQNAgent
    from .ppo import PolicyNetwork, ValueNetwork, PPOAgent
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"PyTorch模块导入失败，将使用NumPy实现的RL优化器: {e}")
    # 定义占位符类，避免导入错误
    class QNetwork:
        pass
    
    class DQNAgent:
        pass
    
    class PolicyNetwork:
        pass
    
    class ValueNetwork:
        pass
    
    class PPOAgent:
        pass

logger = logging.getLogger(__name__)


@dataclass
class RLConfig:
    actor_lr: float = 0.001
    critic_lr: float = 0.005
    gamma: float = 0.95
    epsilon: float = 1.0
    epsilon_decay: float = 0.995
    epsilon_min: float = 0.01
    batch_size: int = 32
    memory_capacity: int = 10000


class ExperienceBuffer:
    def __init__(self, capacity: int):
        self.buffer: List[Tuple] = []
        self.capacity = capacity

    def push(self, state: np.ndarray, action: np.ndarray, reward: float,
             next_state: np.ndarray, done: bool):
        self.buffer.append((state, action, reward, next_state, done))
        if len(self.buffer) > self.capacity:
            self.buffer.pop(0)

    def sample(self, batch_size: int) -> Tuple:
        indices = np.random.choice(len(self.buffer),
                                   min(batch_size, len(self.buffer)),
                                   replace=False)
        states, actions, rewards, next_states, dones = zip(*[self.buffer[i] for i in indices])
        return np.array(states), np.array(actions), np.array(rewards), np.array(next_states), np.array(dones)


class Actor:
    def __init__(self, state_dim: int, action_dim: int, lr: float):
        self.weights = np.random.randn(state_dim, action_dim) * 0.01
        self.lr = lr

    def forward(self, state: np.ndarray) -> np.ndarray:
        logits = np.dot(state, self.weights)
        exp_logits = np.exp(logits - np.max(logits))
        return exp_logits / (exp_logits.sum() + 1e-12)

    def update(self, states: np.ndarray, actions: np.ndarray, advantages: np.ndarray):
        probs = np.array([self.forward(s) for s in states])
        grads = np.zeros_like(self.weights)

        for i, (s, a, adv) in enumerate(zip(states, actions, advantages)):
            prob = probs[i]
            one_hot = np.zeros_like(prob)
            one_hot[a] = 1.0
            grad = (one_hot - prob) * adv
            grads += np.outer(s, grad)

        self.weights += self.lr * grads / (len(states) + 1e-12)


class Critic:
    def __init__(self, state_dim: int, lr: float):
        self.weights = np.random.randn(state_dim) * 0.01
        self.lr = lr

    def forward(self, state: np.ndarray) -> float:
        return np.dot(state, self.weights)

    def update(self, states: np.ndarray, td_errors: np.ndarray):
        grads = np.zeros_like(self.weights)
        for s, td in zip(states, td_errors):
            grads += s * td
        self.weights += self.lr * grads / (len(states) + 1e-12)


class ModelWeightRLOptimizer:
    def __init__(self, n_models: int = 4, state_dim: int = 64):
        self.config = RLConfig()
        self.n_models = n_models
        self.state_dim = state_dim

        self.actor = Actor(state_dim, n_models, self.config.actor_lr)
        self.critic = Critic(state_dim, self.config.critic_lr)
        self.memory = ExperienceBuffer(self.config.memory_capacity)

        self.current_weights = np.ones(n_models) / n_models
        self.training_history: List[float] = []
        self.is_trained = False

    def get_action(self, state: np.ndarray) -> np.ndarray:
        if np.random.rand() < self.config.epsilon:
            return np.random.dirichlet(np.ones(self.n_models))
        return self.actor.forward(state)

    def compute_reward(self, predictions: Dict[str, List[int]],
                       actual: Dict[str, int], weights: np.ndarray) -> float:
        hit_count = 0
        total_count = 0

        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            if pos in predictions and pos in actual:
                weighted_proba = 0.0
                for model_idx, model_pred in enumerate(predictions.values()):
                    if actual[pos] in model_pred[:3]:
                        weighted_proba += weights[model_idx]

                if weighted_proba > 0:
                    hit_count += 1
                total_count += 1

        base_reward = hit_count / total_count if total_count > 0 else 0.0

        consistency_bonus = 0.0
        weight_entropy = -np.sum(weights * np.log(weights + 1e-12))
        consistency_bonus = weight_entropy * 0.1

        return base_reward + consistency_bonus

    def update(self, state: np.ndarray, action: np.ndarray, reward: float,
               next_state: np.ndarray, done: bool):
        self.memory.push(state, action, reward, next_state, done)

        if len(self.memory.buffer) < self.config.batch_size:
            return

        states, actions, rewards, next_states, dones = self.memory.sample(self.config.batch_size)

        td_targets = rewards + self.config.gamma * np.array(
            [self.critic.forward(ns) for ns in next_states]
        ) * (1 - dones)
        td_errors = td_targets - np.array([self.critic.forward(s) for s in states])

        self.critic.update(states, td_errors)
        advantages = td_errors

        self.actor.update(states, actions, advantages)

        self.config.epsilon = max(
            self.config.epsilon_min,
            self.config.epsilon * self.config.epsilon_decay
        )

    def fit(self, states_history: List[np.ndarray], rewards_history: List[float],
            n_episodes: int = 100):
        for episode in range(n_episodes):
            if not states_history:
                break

            episode_reward = 0
            indices = np.random.choice(len(states_history),
                                       min(32, len(states_history)),
                                       replace=False)

            for idx in indices:
                state = states_history[idx]
                action = self.get_action(state)
                self.current_weights = action

                reward = rewards_history[idx] if idx < len(rewards_history) else 0.0

                next_state = states_history[idx + 1] if idx + 1 < len(states_history) else state

                self.update(state, action, reward, next_state, idx == len(states_history) - 1)
                episode_reward += reward

            self.training_history.append(episode_reward)

            if episode % 10 == 0:
                logger.info(f"[RL] Episode {episode + 1}/{n_episodes}, "
                           f"Reward: {episode_reward:.4f}, "
                           f"Epsilon: {self.config.epsilon:.4f}")

        self.is_trained = True
        logger.info("[RL] Training completed")

    def get_optimal_weights(self, state: Optional[np.ndarray] = None) -> np.ndarray:
        if state is None or not self.is_trained:
            return self.current_weights
        return self.actor.forward(state)


class ThompsonSamplingOptimizer:
    def __init__(self, n_arms: int):
        self.n_arms = n_arms
        self.successes = np.ones(n_arms)
        self.failures = np.ones(n_arms)
        self.history: List[Tuple] = []

    def select_arm(self) -> int:
        theta = np.random.beta(self.successes, self.failures)
        return int(np.argmax(theta))

    def update(self, arm: int, success: bool):
        if success:
            self.successes[arm] += 1.0
        else:
            self.failures[arm] += 0.5
        self.history.append((arm, success))

    def get_best_arm(self) -> int:
        means = self.successes / (self.successes + self.failures)
        return int(np.argmax(means))

    def get_probabilities(self) -> np.ndarray:
        return self.successes / (self.successes + self.failures)
