"""
PPO智能体模块 - 策略网络、价值网络、GAE优势估计
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Categorical
from typing import Tuple, List


class PolicyNetwork(nn.Module):
    """
    策略网络模型
    """

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128):
        super(PolicyNetwork, self).__init__()
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, action_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return torch.softmax(self.fc3(x), dim=-1)


class ValueNetwork(nn.Module):
    """
    价值网络模型
    """

    def __init__(self, state_dim: int, hidden_dim: int = 128):
        super(ValueNetwork, self).__init__()
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.fc3(x)


class PPOAgent:
    """
    PPO智能体
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
        actor_lr: float = 0.0003,
        critic_lr: float = 0.001,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_param: float = 0.2,
        vf_coef: float = 0.5,
        entropy_coef: float = 0.01,
        max_grad_norm: float = 0.5,
        update_epochs: int = 10,
        batch_size: int = 64,
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_param = clip_param
        self.vf_coef = vf_coef
        self.entropy_coef = entropy_coef
        self.max_grad_norm = max_grad_norm
        self.update_epochs = update_epochs
        self.batch_size = batch_size

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.policy_network = PolicyNetwork(
            state_dim, action_dim, hidden_dim
        ).to(self.device)
        self.value_network = ValueNetwork(state_dim, hidden_dim).to(
            self.device
        )

        self.actor_optimizer = optim.Adam(
            self.policy_network.parameters(), lr=actor_lr
        )
        self.critic_optimizer = optim.Adam(
            self.value_network.parameters(), lr=critic_lr
        )

        self.states: List[np.ndarray] = []
        self.actions: List[int] = []
        self.log_probs: List[float] = []
        self.rewards: List[float] = []
        self.values: List[float] = []
        self.dones: List[bool] = []

    def select_action(self, state: np.ndarray) -> Tuple[int, float, float]:
        """
        选择动作并返回动作、对数概率和价值
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            probs = self.policy_network(state_tensor)
            value = self.value_network(state_tensor)

        dist = Categorical(probs)
        action = dist.sample()
        log_prob = dist.log_prob(action)

        return action.item(), log_prob.item(), value.item()

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        log_prob: float,
        reward: float,
        value: float,
        done: bool,
    ) -> None:
        """
        存储经验
        """
        self.states.append(state)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.values.append(value)
        self.dones.append(done)

    def compute_gae(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算GAE优势估计和回报
        """
        values = np.array(self.values + [0])
        rewards = np.array(self.rewards)
        dones = np.array(self.dones)

        advantages = np.zeros_like(rewards)
        last_advantage = 0

        for t in reversed(range(len(rewards))):
            delta = (
                rewards[t]
                + self.gamma * values[t + 1] * (1 - dones[t])
                - values[t]
            )
            last_advantage = (
                delta
                + self.gamma
                * self.gae_lambda
                * (1 - dones[t])
                * last_advantage
            )
            advantages[t] = last_advantage

        returns = advantages + np.array(self.values)

        advantages = (advantages - advantages.mean()) / (
            advantages.std() + 1e-8
        )

        return advantages, returns

    def update(self) -> Tuple[float, float, float]:
        """
        更新网络
        """
        if len(self.states) == 0:
            return 0.0, 0.0, 0.0

        advantages, returns = self.compute_gae()

        states = torch.FloatTensor(np.array(self.states)).to(self.device)
        actions = torch.LongTensor(np.array(self.actions)).to(self.device)
        old_log_probs = torch.FloatTensor(np.array(self.log_probs)).to(
            self.device
        )
        advantages = torch.FloatTensor(advantages).to(self.device)
        returns = torch.FloatTensor(returns).to(self.device)

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0

        for _ in range(self.update_epochs):
            indices = torch.randperm(len(self.states))

            for start in range(0, len(self.states), self.batch_size):
                end = start + self.batch_size
                batch_indices = indices[start:end]

                batch_states = states[batch_indices]
                batch_actions = actions[batch_indices]
                batch_old_log_probs = old_log_probs[batch_indices]
                batch_advantages = advantages[batch_indices]
                batch_returns = returns[batch_indices]

                probs = self.policy_network(batch_states)
                dist = Categorical(probs)
                new_log_probs = dist.log_prob(batch_actions)
                entropy = dist.entropy().mean()

                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                surr1 = ratio * batch_advantages
                surr2 = (
                    torch.clamp(
                        ratio, 1 - self.clip_param, 1 + self.clip_param
                    )
                    * batch_advantages
                )

                policy_loss = -torch.min(surr1, surr2).mean()

                values = self.value_network(batch_states).squeeze()
                value_loss = ((values - batch_returns) ** 2).mean()

                loss = (
                    policy_loss
                    + self.vf_coef * value_loss
                    - self.entropy_coef * entropy
                )

                self.actor_optimizer.zero_grad()
                self.critic_optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(
                    self.policy_network.parameters(), self.max_grad_norm
                )
                nn.utils.clip_grad_norm_(
                    self.value_network.parameters(), self.max_grad_norm
                )
                self.actor_optimizer.step()
                self.critic_optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()

        self.clear_buffer()

        n_updates = self.update_epochs * max(
            1, len(self.states) // self.batch_size
        )
        avg_policy_loss = total_policy_loss / n_updates
        avg_value_loss = total_value_loss / n_updates
        avg_entropy = total_entropy / n_updates

        return avg_policy_loss, avg_value_loss, avg_entropy

    def clear_buffer(self) -> None:
        """
        清空缓冲区
        """
        self.states = []
        self.actions = []
        self.log_probs = []
        self.rewards = []
        self.values = []
        self.dones = []

    def save(self, path: str) -> None:
        """
        保存模型
        """
        torch.save(
            {
                "policy_network": self.policy_network.state_dict(),
                "value_network": self.value_network.state_dict(),
                "actor_optimizer": self.actor_optimizer.state_dict(),
                "critic_optimizer": self.critic_optimizer.state_dict(),
            },
            path,
        )

    def load(self, path: str) -> None:
        """
        加载模型
        """
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_network.load_state_dict(checkpoint["policy_network"])
        self.value_network.load_state_dict(checkpoint["value_network"])
        self.actor_optimizer.load_state_dict(checkpoint["actor_optimizer"])
        self.critic_optimizer.load_state_dict(checkpoint["critic_optimizer"])
