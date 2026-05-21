"""
V11高级架构核心组件 - Mamba长序列预测器

基于Mamba-SSM的排列五预测器，实现线性复杂度的长序列建模
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from collections import OrderedDict
import logging

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logging.getLogger(__name__).warning("PyTorch未安装")

logger = logging.getLogger(__name__)


class MambaPL5Module(nn.Module):
    """
    Mamba-SSM排列五预测模块
    
    核心架构:
    1. 嵌入层: 将数字转换为向量表示
    2. Mamba-SSM: 长序列建模
    3. 输出头: 预测5个位置的概率分布
    
    特点:
    - 线性时间复杂度 O(n)
    - 理论无限上下文窗口
    - 高效的长序列建模
    """
    
    def __init__(
        self,
        vocab_size: int = 10,
        d_model: int = 256,
        n_layers: int = 6,
        d_state: int = 64,
        expand: int = 2,
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.n_layers = n_layers
        
        self.embedding = nn.Embedding(vocab_size, d_model)
        
        self.pos_encoder = PositionalEncoding(d_model, dropout)
        
        try:
            from mamba_ssm import Mamba
            self.backbone = nn.ModuleList([
                Mamba(
                    d_model=d_model,
                    d_state=d_state,
                    expand=expand
                ) for _ in range(n_layers)
            ])
        except ImportError:
            logger.warning("mamba-ssm未安装，使用Transformer替代")
            self.backbone = nn.TransformerEncoder(
                nn.TransformerEncoderLayer(
                    d_model=d_model,
                    nhead=8,
                    dim_feedforward=d_model * 4,
                    dropout=dropout
                ),
                num_layers=n_layers
            )
        
        self.norm = nn.LayerNorm(d_model)
        
        self.output_head = nn.Linear(d_model, 5 * vocab_size)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        Args:
            x: (batch, seq_len) 输入序列，每个位置是0-9的数字
        
        Returns:
            logits: (batch, 5, 10) 每个位置的概率分布logits
        """
        emb = self.embedding(x)
        emb = self.pos_encoder(emb)
        
        output = emb.transpose(0, 1)
        
        for layer in self.backbone:
            if isinstance(layer, torch.nn.TransformerEncoderLayer):
                output = layer(output)
            else:
                output = layer(output)
        
        output = output.transpose(0, 1)
        output = self.norm(output)
        
        last_hidden = output[:, -1, :]
        logits = self.output_head(last_hidden)
        logits = logits.view(-1, 5, self.vocab_size)
        
        return logits
    
    def predict(self, sequence: np.ndarray) -> Dict[str, np.ndarray]:
        """
        预测接口
        
        Args:
            sequence: 历史序列 (seq_len,) 或 (batch, seq_len)
        
        Returns:
            {位置: 概率分布}
        """
        self.eval()
        
        if sequence.ndim == 1:
            sequence = sequence.reshape(1, -1)
        
        input_tensor = torch.LongTensor(sequence)
        
        with torch.no_grad():
            logits = self.forward(input_tensor)
            probs = torch.softmax(logits, dim=-1)
        
        probs_np = probs.detach().cpu().numpy()
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        result = {pos: probs_np[0, i] for i, pos in enumerate(positions)}
        
        return result


class PositionalEncoding(nn.Module):
    """位置编码模块"""
    
    def __init__(self, d_model: int, dropout: float = 0.1, max_len: int = 5000):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))
        
        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)
        
        self.register_buffer('pe', pe)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, seq_len, d_model)
        """
        x = x + self.pe[:x.size(1)]
        return self.dropout(x)


class PL5SequenceDataset(Dataset):
    """排列五序列数据集"""
    
    def __init__(
        self,
        data: pd.DataFrame,
        seq_len: int = 50,
        features: Optional[List[str]] = None
    ):
        self.data = data
        self.seq_len = seq_len
        self.features = features or ['wan', 'qian', 'bai', 'shi', 'ge']
        
        self.sequences = self._build_sequences()
    
    def _build_sequences(self) -> List[Tuple[np.ndarray, np.ndarray]]:
        """构建序列数据"""
        sequences = []
        
        for i in range(len(self.data) - self.seq_len):
            seq = self.data.iloc[i:i+self.seq_len][self.features].values.flatten()
            target = self.data.iloc[i+self.seq_len][self.features].values
            
            sequences.append((seq, target))
        
        return sequences
    
    def __len__(self) -> int:
        return len(self.sequences)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        seq, target = self.sequences[idx]
        return torch.LongTensor(seq), torch.LongTensor(target)


class MambaPL5Predictor:
    """
    Mamba-SSM排列五预测器
    
    完整的端到端预测器，包含训练和预测功能
    """
    
    def __init__(
        self,
        d_model: int = 256,
        n_layers: int = 6,
        seq_len: int = 50,
        device: str = 'cpu'
    ):
        if not HAS_TORCH:
            raise ImportError("PyTorch未安装，请先安装PyTorch")
        
        self.d_model = d_model
        self.n_layers = n_layers
        self.seq_len = seq_len
        
        self.device = torch.device(device)
        
        self.model = MambaPL5Module(
            vocab_size=10,
            d_model=d_model,
            n_layers=n_layers
        ).to(self.device)
        
        self.optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=1e-4,
            weight_decay=1e-5
        )
        
        self.criterion = nn.CrossEntropyLoss()
        
        self._is_trained = False
    
    def fit(
        self,
        df: pd.DataFrame,
        epochs: int = 50,
        batch_size: int = 32,
        val_split: float = 0.1
    ) -> Dict[str, List[float]]:
        """
        训练模型
        
        Args:
            df: 训练数据
            epochs: 训练轮数
            batch_size: 批次大小
            val_split: 验证集比例
        
        Returns:
            训练历史
        """
        dataset = PL5SequenceDataset(df, seq_len=self.seq_len)
        
        val_size = int(len(dataset) * val_split)
        train_size = len(dataset) - val_size
        
        train_dataset, val_dataset = torch.utils.data.random_split(
            dataset, [train_size, val_size]
        )
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)
        
        history = {'train_loss': [], 'val_loss': [], 'val_acc': []}
        
        for epoch in range(epochs):
            self.model.train()
            train_loss = 0.0
            
            for batch in train_loader:
                x, y = batch
                x, y = x.to(self.device), y.to(self.device)
                
                self.optimizer.zero_grad()
                
                logits = self.model(x)
                
                loss = 0.0
                for i in range(5):
                    loss += self.criterion(logits[:, i], y[:, i])
                loss /= 5
                
                loss.backward()
                self.optimizer.step()
                
                train_loss += loss.item() * len(x)
            
            train_loss /= len(train_dataset)
            
            val_loss, val_acc = self._evaluate(val_loader)
            
            history['train_loss'].append(train_loss)
            history['val_loss'].append(val_loss)
            history['val_acc'].append(val_acc)
            
            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs} - "
                    f"Train Loss: {train_loss:.4f} - "
                    f"Val Loss: {val_loss:.4f} - "
                    f"Val Acc: {val_acc:.4f}"
                )
        
        self._is_trained = True
        logger.info("Mamba预测器训练完成")
        
        return history
    
    def _evaluate(self, loader: DataLoader) -> Tuple[float, float]:
        """评估模型"""
        self.model.eval()
        
        total_loss = 0.0
        total_correct = 0
        total_samples = 0
        
        with torch.no_grad():
            for batch in loader:
                x, y = batch
                x, y = x.to(self.device), y.to(self.device)
                
                logits = self.model(x)
                
                loss = 0.0
                for i in range(5):
                    loss += self.criterion(logits[:, i], y[:, i])
                loss /= 5
                
                total_loss += loss.item() * len(x)
                
                preds = torch.argmax(logits, dim=-1)
                correct = (preds == y).sum().item()
                total_correct += correct
                total_samples += len(x) * 5
        
        avg_loss = total_loss / len(loader.dataset)
        avg_acc = total_correct / total_samples
        
        return avg_loss, avg_acc
    
    def predict(
        self,
        df: pd.DataFrame,
        top_k: int = 8
    ) -> Dict[str, Dict[str, Any]]:
        """
        预测接口
        
        Args:
            df: 输入数据
            top_k: 返回前k个预测
        
        Returns:
            {位置: {top_k, probabilities}}
        """
        if not self._is_trained:
            logger.warning("模型未训练，使用随机预测")
            return self._random_predict(top_k)
        
        self.model.eval()
        
        features = ['wan', 'qian', 'bai', 'shi', 'ge']
        seq = df[features].tail(self.seq_len).values.flatten()
        
        seq_tensor = torch.LongTensor(seq).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            logits = self.model(seq_tensor)
            probs = torch.softmax(logits, dim=-1)
        
        probs_np = probs.detach().cpu().numpy()[0]
        
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        result = {}
        
        for i, pos in enumerate(positions):
            pos_probs = probs_np[i]
            top_indices = np.argsort(pos_probs)[::-1][:top_k]
            
            result[pos] = {
                'top_k': top_indices.tolist(),
                'probabilities': pos_probs[top_indices].tolist(),
                'full_distribution': pos_probs.tolist()
            }
        
        return result
    
    def _random_predict(self, top_k: int) -> Dict[str, Dict[str, Any]]:
        """随机预测（模型未训练时使用）"""
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        result = {}
        
        for pos in positions:
            probs = np.ones(10) / 10
            top_indices = np.argsort(probs)[::-1][:top_k]
            
            result[pos] = {
                'top_k': top_indices.tolist(),
                'probabilities': probs[top_indices].tolist(),
                'full_distribution': probs.tolist()
            }
        
        return result
    
    def save(self, filepath: str):
        """保存模型"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'config': {
                'd_model': self.d_model,
                'n_layers': self.n_layers,
                'seq_len': self.seq_len
            }
        }, filepath)
        logger.info(f"Mamba预测器已保存到: {filepath}")
    
    def load(self, filepath: str):
        """加载模型"""
        checkpoint = torch.load(filepath, map_location=self.device)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self._is_trained = True
        
        logger.info(f"Mamba预测器已从 {filepath} 加载")
