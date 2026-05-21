"""
V11高级架构组件 - 扩散模型精修器

基于扩散概率模型的概率分布精修器，用于提升预测质量和不确定性量化
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import logging

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logging.getLogger(__name__).warning("PyTorch未安装")

logger = logging.getLogger(__name__)


class DiffusionRefiner:
    """
    扩散模型概率精修器
    
    核心思想:
    1. 将初始概率分布视为带噪声的分布
    2. 通过扩散过程逐步去噪
    3. 输出精修后的概率分布
    
    特点:
    - 生成式建模能力
    - 不确定性量化
    - 概率分布平滑
    """
    
    def __init__(
        self,
        num_timesteps: int = 100,
        noise_scale: float = 0.1,
        device: str = 'cpu'
    ):
        if not HAS_TORCH:
            raise ImportError("PyTorch未安装，请先安装PyTorch")
        
        self.num_timesteps = num_timesteps
        self.noise_scale = noise_scale
        self.device = torch.device(device)
        
        self.schedule = self._build_cosine_schedule()
        self.denoising_net = self._build_denoising_network()
        
        self._is_trained = False
    
    def _build_cosine_schedule(self) -> np.ndarray:
        """构建余弦噪声调度"""
        steps = np.arange(self.num_timesteps + 1)
        s = 0.008
        
        f_t = np.cos(((steps / self.num_timesteps + s) / (1 + s)) * np.pi / 2) ** 2
        alpha_bar = f_t / f_t[0]
        
        return alpha_bar
    
    def _build_denoising_network(self) -> nn.Module:
        """构建去噪网络"""
        return nn.Sequential(
            nn.Linear(50, 128),
            nn.ReLU(),
            nn.LayerNorm(128),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.LayerNorm(256),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.LayerNorm(128),
            nn.Linear(128, 50)
        ).to(self.device)
    
    def fit(
        self,
        df: pd.DataFrame,
        epochs: int = 10,
        batch_size: int = 32
    ) -> Dict[str, List[float]]:
        """训练扩散模型"""
        optimizer = torch.optim.Adam(self.denoising_net.parameters(), lr=1e-4)
        criterion = nn.MSELoss()
        
        history = {'loss': []}
        
        features = ['wan', 'qian', 'bai', 'shi', 'ge']
        data = df[features].values
        
        for epoch in range(epochs):
            self.denoising_net.train()
            total_loss = 0.0
            
            for _ in range(len(data) // batch_size):
                idx = np.random.choice(len(data), batch_size, replace=False)
                clean_data = torch.FloatTensor(data[idx]).to(self.device)
                
                t = np.random.randint(0, self.num_timesteps, batch_size)
                alpha_bar = torch.FloatTensor(self.schedule[t]).to(self.device)
                
                noise = torch.randn_like(clean_data) * self.noise_scale
                noisy_data = torch.sqrt(alpha_bar.view(-1, 1)) * clean_data + \
                           torch.sqrt(1 - alpha_bar.view(-1, 1)) * noise
                
                optimizer.zero_grad()
                
                noise_pred = self.denoising_net(noisy_data)
                
                loss = criterion(noise_pred, noise)
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            avg_loss = total_loss / (len(data) // batch_size)
            history['loss'].append(avg_loss)
            
            if (epoch + 1) % 5 == 0:
                logger.info(f"Diffusion Epoch {epoch+1}/{epochs} - Loss: {avg_loss:.6f}")
        
        self._is_trained = True
        logger.info("扩散模型训练完成")
        
        return history
    
    def refine(
        self,
        probabilities: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        精修概率分布
        
        Args:
            probabilities: {位置: 概率分布}
        
        Returns:
            精修后的概率分布
        """
        if not self._is_trained:
            logger.warning("扩散模型未训练，返回原始概率")
            return probabilities
        
        self.denoising_net.eval()
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        probs_array = np.array([probabilities[pos] for pos in positions])
        probs_tensor = torch.FloatTensor(probs_array).to(self.device)
        
        with torch.no_grad():
            x = probs_tensor + torch.randn_like(probs_tensor) * 0.01
            
            for t in reversed(range(self.num_timesteps)):
                alpha_bar_t = self.schedule[t]
                alpha_bar_t_prev = self.schedule[t - 1] if t > 0 else 1.0
                
                beta_t = 1 - alpha_bar_t / alpha_bar_t_prev
                
                x = x / torch.sqrt(1 - beta_t)
                
                if t > 0:
                    noise_pred = self.denoising_net(x.flatten().unsqueeze(0))
                    x = x - (beta_t / torch.sqrt(1 - alpha_bar_t)) * noise_pred.view_as(x)
        
        refined_probs = x.detach().cpu().numpy()
        
        result = {}
        for i, pos in enumerate(positions):
            prob = refined_probs[i]
            prob = np.clip(prob, 0, None)
            prob = prob / prob.sum()
            result[pos] = prob
        
        return result
    
    def sample(self, n_samples: int = 1) -> Dict[str, np.ndarray]:
        """
        从扩散模型采样
        
        Args:
            n_samples: 采样数量
        
        Returns:
            采样的概率分布
        """
        self.denoising_net.eval()
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        result = []
        
        with torch.no_grad():
            for _ in range(n_samples):
                x = torch.randn(5, 10).to(self.device) * 0.1
                
                for t in reversed(range(self.num_timesteps)):
                    alpha_bar_t = self.schedule[t]
                    alpha_bar_t_prev = self.schedule[t - 1] if t > 0 else 1.0
                    beta_t = 1 - alpha_bar_t / alpha_bar_t_prev
                    
                    x = x / torch.sqrt(1 - beta_t)
                    
                    if t > 0:
                        noise_pred = self.denoising_net(x.flatten().unsqueeze(0))
                        x = x - (beta_t / torch.sqrt(1 - alpha_bar_t)) * noise_pred.view_as(x)
                
                sample_probs = x.detach().cpu().numpy()
                
                sample_dict = {}
                for i, pos in enumerate(positions):
                    prob = sample_probs[i]
                    prob = np.clip(prob, 0, None)
                    prob = prob / prob.sum()
                    sample_dict[pos] = prob
                
                result.append(sample_dict)
        
        if n_samples == 1:
            return result[0]
        
        return result


class MoEPredictor:
    """
    专家混合预测器 (Mixture of Experts)
    
    核心思想:
    1. 多个专家网络并行处理
    2. 门控网络动态选择专家
    3. 加权融合专家输出
    
    特点:
    - 自适应专家选择
    - 多模式数据处理
    - 动态路由
    """
    
    def __init__(
        self,
        num_experts: int = 4,
        d_model: int = 128,
        device: str = 'cpu'
    ):
        if not HAS_TORCH:
            raise ImportError("PyTorch未安装，请先安装PyTorch")
        
        self.num_experts = num_experts
        self.d_model = d_model
        self.device = torch.device(device)
        
        self.experts = self._build_experts()
        self.gate_network = self._build_gate_network()
        
        self._is_trained = False
    
    def _build_experts(self) -> nn.ModuleList:
        """构建专家网络列表"""
        experts = nn.ModuleList()
        
        for _ in range(self.num_experts):
            expert = nn.Sequential(
                nn.Linear(50, self.d_model),
                nn.ReLU(),
                nn.LayerNorm(self.d_model),
                nn.Linear(self.d_model, self.d_model),
                nn.ReLU(),
                nn.LayerNorm(self.d_model),
                nn.Linear(self.d_model, 50)
            ).to(self.device)
            experts.append(expert)
        
        return experts
    
    def _build_gate_network(self) -> nn.Module:
        """构建门控网络"""
        return nn.Sequential(
            nn.Linear(50, 64),
            nn.ReLU(),
            nn.Linear(64, self.num_experts),
            nn.Softmax(dim=-1)
        ).to(self.device)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        Args:
            x: (batch, 50) 展平的概率分布
        
        Returns:
            output: (batch, 50) 融合后的概率分布
        """
        gate_scores = self.gate_network(x)
        
        expert_outputs = []
        for expert in self.experts:
            expert_outputs.append(expert(x))
        
        expert_stack = torch.stack(expert_outputs, dim=-1)
        output = torch.einsum('bn,bnm->bm', gate_scores, expert_stack)
        
        return output
    
    def fit(
        self,
        df: pd.DataFrame,
        epochs: int = 10,
        batch_size: int = 32
    ) -> Dict[str, List[float]]:
        """训练MoE模型"""
        optimizer = torch.optim.Adam(
            list(self.experts.parameters()) + list(self.gate_network.parameters()),
            lr=1e-4
        )
        criterion = nn.MSELoss()
        
        history = {'loss': []}
        
        features = ['wan', 'qian', 'bai', 'shi', 'ge']
        data = df[features].values / 9.0
        
        for epoch in range(epochs):
            total_loss = 0.0
            
            for _ in range(len(data) // batch_size):
                idx = np.random.choice(len(data), batch_size, replace=False)
                x = torch.FloatTensor(data[idx]).to(self.device)
                x = x.view(batch_size, -1)
                
                optimizer.zero_grad()
                
                output = self.forward(x)
                
                loss = criterion(output, x)
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            avg_loss = total_loss / (len(data) // batch_size)
            history['loss'].append(avg_loss)
            
            if (epoch + 1) % 5 == 0:
                logger.info(f"MoE Epoch {epoch+1}/{epochs} - Loss: {avg_loss:.6f}")
        
        self._is_trained = True
        logger.info("MoE预测器训练完成")
        
        return history
    
    def predict(
        self,
        probabilities: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        使用MoE精修概率分布
        
        Args:
            probabilities: {位置: 概率分布}
        
        Returns:
            精修后的概率分布
        """
        if not self._is_trained:
            logger.warning("MoE未训练，返回原始概率")
            return probabilities
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        probs_array = np.array([probabilities[pos] for pos in positions]).flatten()
        probs_tensor = torch.FloatTensor(probs_array).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            output = self.forward(probs_tensor)
        
        refined_array = output.detach().cpu().numpy().reshape(5, 10)
        
        result = {}
        for i, pos in enumerate(positions):
            prob = refined_array[i]
            prob = np.clip(prob, 0, None)
            prob = prob / prob.sum()
            result[pos] = prob
        
        return result


class CausalReasoningEngine:
    """
    因果推理引擎
    
    核心功能:
    1. 构建因果图
    2. 估计特征因果效应
    3. 提供可解释性分析
    
    特点:
    - 基于因果图的推理
    - 特征重要性分析
    - 决策解释
    """
    
    def __init__(self):
        self.graph = {}
        self.feature_effects = {}
    
    def build_graph(self, features: List[str]):
        """
        构建因果图
        
        Args:
            features: 特征列表
        """
        self.graph = {feat: [] for feat in features}
        
        default_edges = [
            ('lag_1_wan', 'wan'),
            ('lag_2_wan', 'wan'),
            ('digit_freq_wan', 'wan'),
            ('trend_wan', 'wan'),
            ('lag_1_qian', 'qian'),
            ('lag_2_qian', 'qian'),
            ('digit_freq_qian', 'qian'),
            ('trend_qian', 'qian'),
            ('wan', 'qian'),
            ('qian', 'bai'),
            ('bai', 'shi'),
            ('shi', 'ge'),
        ]
        
        for src, dst in default_edges:
            if src in self.graph and dst in self.graph:
                self.graph[src].append(dst)
        
        logger.info(f"因果图构建完成，包含 {len(self.graph)} 个节点")
    
    def estimate_effect(self, feature: str, outcome: str) -> float:
        """
        估计特征对结果的因果效应
        
        Args:
            feature: 特征名
            outcome: 结果变量
        
        Returns:
            因果效应估计值
        """
        if feature not in self.graph:
            return 0.0
        
        path_length = self._shortest_path(feature, outcome)
        
        if path_length is None:
            return 0.0
        
        base_effect = 0.1
        effect = base_effect / (path_length + 1)
        
        self.feature_effects[(feature, outcome)] = effect
        
        return effect
    
    def _shortest_path(self, start: str, end: str) -> Optional[int]:
        """计算最短路径长度"""
        if start == end:
            return 0
        
        visited = {start}
        queue = [(start, 0)]
        
        while queue:
            node, dist = queue.pop(0)
            
            if node not in self.graph:
                continue
            
            for neighbor in self.graph[node]:
                if neighbor == end:
                    return dist + 1
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        
        return None
    
    def get_feature_importance(self, outcome: str) -> Dict[str, float]:
        """
        获取各特征对结果的重要性
        
        Args:
            outcome: 结果变量
        
        Returns:
            {特征: 重要性分数}
        """
        importance = {}
        
        for feature in self.graph:
            effect = self.estimate_effect(feature, outcome)
            importance[feature] = effect
        
        total = sum(importance.values()) or 1.0
        for feat in importance:
            importance[feat] /= total
        
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
    
    def explain_prediction(
        self,
        predictions: Dict[str, List[int]],
        features: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        解释预测结果
        
        Args:
            predictions: 预测结果
            features: 特征值
        
        Returns:
            解释信息
        """
        explanations = {}
        
        for pos, preds in predictions.items():
            importance = self.get_feature_importance(pos)
            
            top_features = list(importance.keys())[:5]
            
            explanations[pos] = {
                'prediction': preds,
                'top_features': top_features,
                'feature_importance': {k: round(v, 4) for k, v in importance.items() if v > 0.01}
            }
        
        return explanations
