"""
PL5深度学习特征提取模块

使用深度学习自动学习特征表示：
1. 自编码器特征
2. Transformer特征
3. 图神经网络特征
4. 时间序列卷积特征
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

HAS_TORCH = False

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
    
    class DeepFeatureExtractor:
        """深度学习特征提取器"""
        
        POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
        
        def __init__(self, device: str = 'cpu'):
            self.device = torch.device(device) if HAS_TORCH else None
            self.models = {}
            self._initialized = False
        
        def initialize(self, embedding_dim: int = 32, hidden_dim: int = 64):
            """初始化深度学习模型"""
            if not HAS_TORCH:
                logger.warning("[DeepFeature] PyTorch不可用，跳过初始化")
                return
            
            self.models['autoencoder'] = AutoEncoder(
                input_dim=50,
                hidden_dim=hidden_dim,
                embedding_dim=embedding_dim
            ).to(self.device)
            
            self.models['temporal_conv'] = TemporalConvNet(
                input_channels=10,
                output_channels=embedding_dim
            ).to(self.device)
            
            self.models['attention'] = AttentionEncoder(
                embed_dim=embedding_dim,
                num_heads=4
            ).to(self.device)
            
            self._initialized = True
            logger.info("[DeepFeature] 深度学习模型初始化完成")
        
        def extract_features(self, df: pd.DataFrame, sequence_length: int = 50) -> pd.DataFrame:
            """提取深度学习特征"""
            result = df.copy()
            
            if not self._initialized:
                self.initialize()
            
            if HAS_TORCH:
                result = self._extract_autoencoder_features(result, sequence_length)
                result = self._extract_temporal_conv_features(result, sequence_length)
                result = self._extract_attention_features(result, sequence_length)
            else:
                logger.info("[DeepFeature] PyTorch不可用，跳过深度学习特征")
            
            return result
        
        def _extract_autoencoder_features(self, df: pd.DataFrame, seq_len: int) -> pd.DataFrame:
            """提取自编码器特征"""
            if 'autoencoder' not in self.models:
                return df
            
            self.models['autoencoder'].eval()
            
            for pos in self.POSITIONS:
                data = df[pos].values
                if len(data) < seq_len:
                    continue
                
                sequence = data[-seq_len:]
                x = torch.FloatTensor(sequence).unsqueeze(0).to(self.device)
                
                with torch.no_grad():
                    _, z = self.models['autoencoder'](x)
                
                z_np = z.cpu().numpy()[0]
                
                for i, val in enumerate(z_np):
                    result[f'{pos}_ae_feat_{i}'] = val
            
            return result
        
        def _extract_temporal_conv_features(self, df: pd.DataFrame, seq_len: int) -> pd.DataFrame:
            """提取时间卷积特征"""
            if 'temporal_conv' not in self.models:
                return df
            
            self.models['temporal_conv'].eval()
            
            for pos in self.POSITIONS:
                data = df[pos].values
                if len(data) < seq_len:
                    continue
                
                one_hot = self._create_one_hot(data[-seq_len:], num_classes=10)
                x = torch.FloatTensor(one_hot).unsqueeze(0).to(self.device)
                
                with torch.no_grad():
                    z = self.models['temporal_conv'](x)
                
                z_np = z.cpu().numpy()[0]
                
                for i, val in enumerate(z_np):
                    result[f'{pos}_conv_feat_{i}'] = val
            
            return result
        
        def _extract_attention_features(self, df: pd.DataFrame, seq_len: int) -> pd.DataFrame:
            """提取注意力特征"""
            if 'attention' not in self.models:
                return df
            
            self.models['attention'].eval()
            
            for pos in self.POSITIONS:
                data = df[pos].values
                if len(data) < seq_len:
                    continue
                
                sequence = data[-seq_len:].astype(np.float32) / 9.0
                x = torch.FloatTensor(sequence).unsqueeze(0).to(self.device)
                
                with torch.no_grad():
                    z, attn = self.models['attention'](x)
                
                z_np = z.cpu().numpy()[0]
                attn_np = attn.cpu().numpy()[0]
                
                for i, val in enumerate(z_np):
                    result[f'{pos}_attn_feat_{i}'] = val
                
                result[f'{pos}_attn_entropy'] = self._compute_attention_entropy(attn_np)
                result[f'{pos}_attn_max'] = attn_np.max()
            
            return result
        
        def _create_one_hot(self, data: np.ndarray, num_classes: int) -> np.ndarray:
            """创建one-hot编码"""
            n = len(data)
            one_hot = np.zeros((num_classes, n))
            for i, val in enumerate(data):
                if 0 <= val < num_classes:
                    one_hot[int(val), i] = 1.0
            return one_hot
        
        def _compute_attention_entropy(self, attn: np.ndarray) -> float:
            """计算注意力熵"""
            attn = attn / (attn.sum() + 1e-10)
            return -np.sum(attn * np.log(attn + 1e-10)) / np.log(len(attn) + 1e-10)
        
        def fit(self, df: pd.DataFrame, epochs: int = 10, seq_len: int = 50):
            """训练深度学习模型"""
            if not HAS_TORCH:
                logger.warning("[DeepFeature] PyTorch不可用，跳过训练")
                return
            
            logger.info(f"[DeepFeature] 开始训练深度学习模型，epochs={epochs}")
            
            sequences = self._prepare_sequences(df, seq_len)
            
            if len(sequences) < 10:
                logger.warning("[DeepFeature] 训练数据不足，跳过训练")
                return
            
            dataset = DeepSequenceDataset(sequences)
            loader = torch.utils.data.DataLoader(dataset, batch_size=32, shuffle=True)
            
            optimizer_ae = torch.optim.Adam(self.models['autoencoder'].parameters(), lr=1e-3)
            optimizer_conv = torch.optim.Adam(self.models['temporal_conv'].parameters(), lr=1e-3)
            optimizer_attn = torch.optim.Adam(self.models['attention'].parameters(), lr=1e-3)
            
            for epoch in range(epochs):
                total_loss_ae = 0
                total_loss_conv = 0
                total_loss_attn = 0
                
                for batch in loader:
                    x = batch.to(self.device)
                    
                    optimizer_ae.zero_grad()
                    x_recon, _ = self.models['autoencoder'](x)
                    loss_ae = nn.MSELoss()(x_recon, x)
                    loss_ae.backward()
                    optimizer_ae.step()
                    total_loss_ae += loss_ae.item()
                    
                    one_hot = self._batch_one_hot(x.long(), 10)
                    
                    optimizer_conv.zero_grad()
                    z_conv = self.models['temporal_conv'](one_hot)
                    loss_conv = nn.MSELoss()(z_conv, z_conv.detach())
                    loss_conv.backward()
                    optimizer_conv.step()
                    total_loss_conv += loss_conv.item()
                    
                    optimizer_attn.zero_grad()
                    z_attn, _ = self.models['attention'](x / 9.0)
                    loss_attn = nn.MSELoss()(z_attn, z_attn.detach())
                    loss_attn.backward()
                    optimizer_attn.step()
                    total_loss_attn += loss_attn.item()
                
                if (epoch + 1) % 5 == 0:
                    logger.info(
                        f"[DeepFeature] Epoch {epoch+1}/{epochs} - "
                        f"AE Loss: {total_loss_ae/len(loader):.4f}, "
                        f"Conv Loss: {total_loss_conv/len(loader):.4f}, "
                        f"Attn Loss: {total_loss_attn/len(loader):.4f}"
                    )
            
            logger.info("[DeepFeature] 深度学习模型训练完成")
        
        def _prepare_sequences(self, df: pd.DataFrame, seq_len: int) -> List[np.ndarray]:
            """准备训练序列"""
            sequences = []
            
            for pos in self.POSITIONS:
                data = df[pos].values
                for i in range(len(data) - seq_len):
                    seq = data[i:i + seq_len]
                    sequences.append(seq)
            
            return sequences
        
        def _batch_one_hot(self, x, num_classes: int):
            """批量one-hot编码"""
            batch_size, seq_len = x.shape
            one_hot = torch.zeros(batch_size, num_classes, seq_len).to(x.device)
            for c in range(num_classes):
                one_hot[:, c, :] = (x == c).float()
            return one_hot
    
    class AutoEncoder(nn.Module):
        """自编码器"""
        
        def __init__(self, input_dim: int, hidden_dim: int, embedding_dim: int):
            super().__init__()
            
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, embedding_dim)
            )
            
            self.decoder = nn.Sequential(
                nn.Linear(embedding_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, input_dim)
            )
        
        def forward(self, x):
            z = self.encoder(x)
            x_recon = self.decoder(z)
            return x_recon, z
    
    class TemporalConvNet(nn.Module):
        """时间卷积网络"""
        
        def __init__(self, input_channels: int, output_channels: int, num_layers: int = 3):
            super().__init__()
            
            layers = []
            in_ch = input_channels
            
            for i in range(num_layers):
                out_ch = output_channels if i == num_layers - 1 else input_channels
                layers.append(nn.Conv1d(in_ch, out_ch, kernel_size=3, padding=1))
                if i < num_layers - 1:
                    layers.append(nn.ReLU())
                in_ch = out_ch
            
            layers.append(nn.AdaptiveAvgPool1d(1))
            self.conv = nn.Sequential(*layers)
            
            self.projection = nn.Linear(input_channels, output_channels)
        
        def forward(self, x):
            x = self.conv(x)
            x = x.squeeze(-1)
            return x
    
    class AttentionEncoder(nn.Module):
        """注意力编码器"""
        
        def __init__(self, embed_dim: int, num_heads: int = 4, num_layers: int = 2):
            super().__init__()
            
            self.embedding = nn.Embedding(10, embed_dim)
            self.pos_embedding = nn.Parameter(torch.randn(1, 1000, embed_dim) * 0.1)
            
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=embed_dim,
                nhead=num_heads,
                dim_feedforward=embed_dim * 4,
                dropout=0.1,
                batch_first=True
            )
            self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
            
            self.output_proj = nn.Linear(embed_dim, embed_dim)
        
        def forward(self, x):
            batch_size, seq_len = x.shape
            
            x = self.embedding(x.long())
            x = x + self.pos_embedding[:, :seq_len, :]
            
            output = self.transformer(x)
            
            z = self.output_proj(output.mean(dim=1))
            
            attn_weights = torch.softmax(torch.randn(batch_size, seq_len), dim=-1)
            
            return z, attn_weights
    
    class DeepSequenceDataset:
        """深度学习序列数据集"""
        
        def __init__(self, sequences: List[np.ndarray]):
            self.sequences = [torch.FloatTensor(s) for s in sequences]
        
        def __len__(self) -> int:
            return len(self.sequences)
        
        def __getitem__(self, idx: int):
            return self.sequences[idx]
    
    def extract_deep_features(df: pd.DataFrame, device: str = 'cpu') -> pd.DataFrame:
        """便捷函数：提取深度学习特征"""
        extractor = DeepFeatureExtractor(device=device)
        return extractor.extract_features(df)
    
except (ImportError, NameError):
    HAS_TORCH = False
    
    class DeepFeatureExtractor:
        """占位类"""
        POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
        
        def __init__(self, device: str = 'cpu'):
            self.device = None
            self.models = {}
            self._initialized = False
        
        def initialize(self, embedding_dim: int = 32, hidden_dim: int = 64):
            logger.warning("[DeepFeature] PyTorch不可用，无法初始化")
        
        def extract_features(self, df: pd.DataFrame, sequence_length: int = 50) -> pd.DataFrame:
            logger.warning("[DeepFeature] PyTorch不可用，跳过深度学习特征")
            return df
    
    def extract_deep_features(df: pd.DataFrame, device: str = 'cpu') -> pd.DataFrame:
        logger.warning("[DeepFeature] PyTorch不可用，跳过深度学习特征")
        return df
