"""
NumPy实现的强化学习模块 - 不依赖PyTorch
包含DQN和PPO算法的NumPy实现
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from collections import deque
import logging

logger = logging.getLogger(__name__)


class ReplayBuffer:
    """经验回放缓冲区"""
    
    def __init__(self, capacity: int = 10000):
        self.buffer = deque(maxlen=capacity)
        
    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))
        
    def sample(self, batch_size: int) -> Tuple:
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        states, actions, rewards, next_states, dones = zip(*[self.buffer[i] for i in indices])
        return np.array(states), np.array(actions), np.array(rewards), np.array(next_states), np.array(dones)
    
    def __len__(self):
        return len(self.buffer)


class NumpyMLP:
    """NumPy实现的多层感知机"""
    
    def __init__(self, input_dim: int, output_dim: int, hidden_dims: List[int], 
                 learning_rate: float = 0.001):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.learning_rate = learning_rate
        
        # 初始化网络结构
        dims = [input_dim] + hidden_dims + [output_dim]
        self.weights = []
        self.biases = []
        
        for i in range(len(dims) - 1):
            # He初始化
            std = np.sqrt(2.0 / dims[i])
            self.weights.append(np.random.randn(dims[i], dims[i+1]) * std)
            self.biases.append(np.zeros((1, dims[i+1])))
            
        self.activations = [np.tanh, np.tanh, lambda x: x]  # 最后一层线性
        
    def forward(self, x: np.ndarray) -> np.ndarray:
        """前向传播"""
        self.cache = [x]
        for i, (w, b, act) in enumerate(zip(self.weights, self.biases, self.activations)):
            x = x @ w + b
            x = act(x)
            self.cache.append(x)
        return x
    
    def backward(self, y_true: np.ndarray, y_pred: np.ndarray, 
                 optimizer='adam') -> float:
        """反向传播"""
        batch_size = y_true.shape[0]
        loss = np.mean((y_pred - y_true) ** 2)
        
        # 输出层梯度
        delta = 2 * (y_pred - y_true) / batch_size
        
        for i in reversed(range(len(self.weights))):
            dw = self.cache[i].T @ delta
            db = np.sum(delta, axis=0, keepdims=True)
            
            if i > 0:
                delta = delta @ self.weights[i].T * (1 - self.cache[i] ** 2)
                
            # 更新权重 (简单的Adam-like更新)
            self.weights[i] -= self.learning_rate * dw
            self.biases[i] -= self.learning_rate * db
            
        return loss
    
    def update(self, states: np.ndarray, targets: np.ndarray):
        """单步更新"""
        predictions = self.forward(states)
        return self.backward(targets, predictions)


class DQNAgent:
    """
    DQN (Deep Q-Network) 智能体 - NumPy实现
    
    适用于离散动作空间的决策问题
    """
    
    def __init__(self, state_dim: int, action_dim: int, 
                 hidden_dims: List[int] = [128, 128],
                 learning_rate: float = 0.001,
                 gamma: float = 0.99,
                 epsilon: float = 1.0,
                 epsilon_decay: float = 0.995,
                 epsilon_min: float = 0.01,
                 buffer_capacity: int = 10000,
                 batch_size: int = 64,
                 target_update_freq: int = 100):
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq
        self.train_step = 0
        
        # 主网络和目标网络
        self.q_network = NumpyMLP(state_dim, action_dim, hidden_dims, learning_rate)
        self.target_network = NumpyMLP(state_dim, action_dim, hidden_dims, learning_rate)
        self.update_target_network()
        
        # 经验回放
        self.replay_buffer = ReplayBuffer(buffer_capacity)
        
        # 经验记录
        self.episode_rewards: List[float] = []
        self.episode_losses: List[float] = []
        
    def update_target_network(self):
        """更新目标网络"""
        for i in range(len(self.q_network.weights)):
            self.target_network.weights[i] = self.q_network.weights[i].copy()
            self.target_network.biases[i] = self.q_network.biases[i].copy()
            
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """选择动作 (epsilon-greedy)"""
        if training and np.random.random() < self.epsilon:
            return np.random.randint(self.action_dim)
        
        state = state.reshape(1, -1)
        q_values = self.q_network.forward(state)
        return int(np.argmax(q_values))
    
    def store_transition(self, state, action, reward, next_state, done):
        """存储转移"""
        self.replay_buffer.push(state, action, reward, next_state, done)
        
    def train(self) -> Optional[float]:
        """训练一步"""
        if len(self.replay_buffer) < self.batch_size:
            return None
            
        # 采样
        states, actions, rewards, next_states, dones = \
            self.replay_buffer.sample(self.batch_size)
            
        # 计算目标Q值
        next_q_values = self.target_network.forward(next_states)
        max_next_q = np.max(next_q_values, axis=1)
        
        # Q学习目标
        targets = rewards + (1 - dones) * self.gamma * max_next_q
        
        # 更新网络
        predictions = self.q_network.forward(states)
        for i, (a, t) in enumerate(zip(actions, targets)):
            predictions[i, a] = t
            
        loss = self.q_network.update(states, predictions)
        
        # 更新目标网络
        self.train_step += 1
        if self.train_step % self.target_update_freq == 0:
            self.update_target_network()
            
        # 衰减epsilon
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        
        self.episode_losses.append(float(loss))
        return float(loss)
    
    def save(self, path: str):
        """保存模型"""
        np.savez(path,
                weights=self.q_network.weights,
                biases=self.q_network.biases,
                epsilon=self.epsilon)
                
    def load(self, path: str):
        """加载模型"""
        data = np.load(path, allow_pickle=True)
        self.q_network.weights = list(data['weights'])
        self.q_network.biases = list(data['biases'])
        self.epsilon = float(data['epsilon'])
        self.update_target_network()


class PPOAgent:
    """
    PPO (Proximal Policy Optimization) 智能体 - NumPy实现
    
    适用于连续和离散动作空间
    """
    
    def __init__(self, state_dim: int, action_dim: int,
                 hidden_dims: List[int] = [128, 128],
                 learning_rate: float = 0.0003,
                 gamma: float = 0.99,
                 lam: float = 0.95,
                 clip_ratio: float = 0.2,
                 value_coef: float = 0.5,
                 entropy_coef: float = 0.01,
                 update_epochs: int = 10,
                 batch_size: int = 64):
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.lam = lam
        self.clip_ratio = clip_ratio
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.update_epochs = update_epochs
        self.batch_size = batch_size
        
        # 策略网络
        self.policy_net = NumpyMLP(state_dim, action_dim, hidden_dims, learning_rate)
        
        # 价值网络
        self.value_net = NumpyMLP(state_dim, 1, hidden_dims, learning_rate)
        
        # 存储
        self.states: List[np.ndarray] = []
        self.actions: List[int] = []
        self.rewards: List[float] = []
        self.dones: List[bool] = []
        self.old_log_probs: List[float] = []
        
    def select_action(self, state: np.ndarray) -> Tuple[int, float]:
        """选择动作并返回log概率"""
        state = state.reshape(1, -1)
        probs = self.policy_net.forward(state)
        probs = np.exp(probs - np.max(probs, axis=1, keepdims=True))
        probs = probs / np.sum(probs, axis=1, keepdims=True)
        
        action = np.random.choice(self.action_dim, p=probs[0])
        log_prob = np.log(probs[0, action] + 1e-8)
        
        return int(action), float(log_prob)
    
    def store_transition(self, state, action, reward, done, log_prob):
        """存储转移"""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.dones.append(done)
        self.old_log_probs.append(log_prob)
    
    def compute_gae(self, rewards: np.ndarray, values: np.ndarray, 
                    dones: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """计算GAE (Generalized Advantage Estimation)"""
        advantages = np.zeros_like(rewards)
        gae = 0
        
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = 0
            else:
                next_value = values[t + 1]
                
            delta = rewards[t] + self.gamma * next_value * (1 - dones[t]) - values[t]
            gae = delta + self.gamma * self.lam * (1 - dones[t]) * gae
            advantages[t] = gae
            
        returns = advantages + values
        return advantages, returns
    
    def update(self) -> Dict[str, float]:
        """更新策略"""
        if len(self.states) == 0:
            return {}
            
        # 转换数据
        states = np.array(self.states)
        actions = np.array(self.actions)
        old_log_probs = np.array(self.old_log_probs)
        
        # 计算旧值和GAE
        values = np.array([self.value_net.forward(s.reshape(1, -1))[0, 0] 
                          for s in states])
        advantages, returns = self.compute_gae(
            np.array(self.rewards), values, np.array(self.dones)
        )
        
        # 标准化优势
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO更新
        policy_losses = []
        value_losses = []
        
        for _ in range(self.update_epochs):
            indices = np.random.permutation(len(states))
            
            for start in range(0, len(states), self.batch_size):
                end = min(start + self.batch_size, len(states))
                batch_idx = indices[start:end]
                
                batch_states = states[batch_idx]
                batch_actions = actions[batch_idx]
                batch_old_log_probs = old_log_probs[batch_idx]
                batch_advantages = advantages[batch_idx]
                batch_returns = returns[batch_idx]
                
                # 新策略概率
                probs = self.policy_net.forward(batch_states)
                probs = np.exp(probs - np.max(probs, axis=1, keepdims=True))
                probs = probs / np.sum(probs, axis=1, keepdims=True)
                
                new_log_probs = np.log(probs[np.arange(len(batch_actions)), batch_actions] + 1e-8)
                
                # 比率和新策略/旧策略
                ratio = np.exp(new_log_probs - batch_old_log_probs)
                
                # PPO裁剪损失
                surr1 = ratio * batch_advantages
                surr2 = np.clip(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio) * batch_advantages
                policy_loss = -np.mean(np.minimum(surr1, surr2))
                
                # 价值损失
                new_values = np.array([self.value_net.forward(s.reshape(1, -1))[0, 0] 
                                      for s in batch_states])
                value_loss = np.mean((new_values - batch_returns) ** 2)
                
                # 熵正则化
                entropy = -np.mean(np.sum(probs * np.log(probs + 1e-8), axis=1))
                
                # 总损失
                loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy
                
                # 更新网络
                self.policy_net.update(batch_states, probs)
                
                policy_losses.append(float(policy_loss))
                value_losses.append(float(value_loss))
        
        # 清空存储
        self.states = []
        self.actions = []
        self.rewards = []
        self.dones = []
        self.old_log_probs = []
        
        return {
            'policy_loss': np.mean(policy_losses),
            'value_loss': np.mean(value_losses),
            'mean_reward': np.mean(self.rewards) if self.rewards else 0
        }


class PL5RLOptimizer:
    """
    排列五RL优化器 - 使用强化学习优化预测策略
    """
    
    def __init__(self):
        self.state_dim = 50  # 特征维度
        self.action_dim = 10  # 10个数字
        self.dqn = DQNAgent(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            hidden_dims=[64, 64],
            learning_rate=0.001,
            gamma=0.99
        )
        
    def encode_state(self, features: np.ndarray) -> np.ndarray:
        """编码状态"""
        if len(features) < self.state_dim:
            features = np.pad(features, (0, self.state_dim - len(features)))
        elif len(features) > self.state_dim:
            features = features[:self.state_dim]
        return features
        
    def optimize(self, historical_data, n_episodes: int = 100) -> Dict:
        """执行RL优化"""
        results = {
            'episodes': [],
            'rewards': [],
            'losses': []
        }
        
        for episode in range(n_episodes):
            total_reward = 0
            total_loss = 0
            n_steps = 0
            
            # 简单模拟环境
            for i in range(len(historical_data) - 1):
                state = historical_data[i]
                state = self.encode_state(state)
                
                # 选择动作
                action = self.dqn.select_action(state, training=True)
                
                # 获取奖励 (根据预测准确度)
                next_state = historical_data[i + 1]
                actual = int(next_state[0])  # 万位
                
                reward = 1.0 if action == actual else 0.0
                done = i == len(historical_data) - 2
                
                # 存储并训练
                self.dqn.store_transition(state, action, reward, next_state, done)
                loss = self.dqn.train()
                
                if loss is not None:
                    total_loss += loss
                    n_steps += 1
                    
                total_reward += reward
                
            results['episodes'].append(episode)
            results['rewards'].append(total_reward)
            results['losses'].append(total_loss / n_steps if n_steps > 0 else 0)
            
            if episode % 10 == 0:
                logger.info(f"Episode {episode}: reward={total_reward:.2f}, loss={total_loss/n_steps if n_steps > 0 else 0:.4f}")
                
        return results
        
    def get_optimal_strategy(self) -> Dict[int, float]:
        """获取最优策略"""
        strategy = {}
        for digit in range(10):
            state = np.zeros(self.state_dim)
            q_values = self.dqn.q_network.forward(state.reshape(1, -1))[0]
            strategy[digit] = float(q_values[digit])
        return strategy


# 全局实例
_dqn_optimizer: Optional[DQNAgent] = None
_ppo_optimizer: Optional[PPOAgent] = None


def get_dqn_optimizer(state_dim: int = 50, action_dim: int = 10) -> DQNAgent:
    """获取DQN优化器全局实例"""
    global _dqn_optimizer
    if _dqn_optimizer is None:
        _dqn_optimizer = DQNAgent(state_dim=state_dim, action_dim=action_dim)
    return _dqn_optimizer


def get_ppo_optimizer(state_dim: int = 50, action_dim: int = 10) -> PPOAgent:
    """获取PPO优化器全局实例"""
    global _ppo_optimizer
    if _ppo_optimizer is None:
        _ppo_optimizer = PPOAgent(state_dim=state_dim, action_dim=action_dim)
    return _ppo_optimizer
