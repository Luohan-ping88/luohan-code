"""
Time-Series Transformer预测模型
基于Transformer架构的时序预测模型，用于增强PL5预测能力
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class PositionalEncoding:
    """位置编码"""

    def __init__(self, d_model: int, max_len: int = 5000):
        self.d_model = d_model
        pe = np.zeros((max_len, d_model))
        position = np.arange(0, max_len, dtype=np.float32).reshape(-1, 1)
        div_term = np.exp(
            np.arange(0, d_model, 2, dtype=np.float32) * (-np.log(10000.0) / d_model)
        )
        pe[:, 0::2] = np.sin(position * div_term)
        pe[:, 1::2] = np.cos(position * div_term)
        pe = pe.reshape(1, max_len, d_model)
        self.register_buffer = pe

    def forward(self, x: np.ndarray) -> np.ndarray:
        return x + self.register_buffer[:, : x.shape[1], :]


class MultiHeadAttention:
    """多头注意力机制"""

    def __init__(self, d_model: int, n_heads: int = 8):
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads
        self.W_q = np.random.randn(d_model, d_model) * 0.02
        self.W_k = np.random.randn(d_model, d_model) * 0.02
        self.W_v = np.random.randn(d_model, d_model) * 0.02
        self.W_o = np.random.randn(d_model, d_model) * 0.02

    def forward(
        self, query: np.ndarray, key: np.ndarray, value: np.ndarray, mask: Optional[np.ndarray] = None
    ) -> np.ndarray:
        batch_size = query.shape[0]
        Q = np.dot(query, self.W_q).reshape(batch_size, -1, self.n_heads, self.d_k).transpose(0, 2, 1, 3)
        K = np.dot(key, self.W_k).reshape(batch_size, -1, self.n_heads, self.d_k).transpose(0, 2, 1, 3)
        V = np.dot(value, self.W_v).reshape(batch_size, -1, self.n_heads, self.d_k).transpose(0, 2, 1, 3)

        scores = np.matmul(Q, K.transpose(0, 1, 3, 2)) / np.sqrt(self.d_k)
        if mask is not None:
            scores = scores * mask

        attention_weights = self._softmax(scores)
        context = np.matmul(attention_weights, V)
        context = context.transpose(0, 2, 1, 3).reshape(batch_size, -1, self.d_model)
        output = np.dot(context, self.W_o)

        return output

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)


class FeedForward:
    """前馈神经网络"""

    def __init__(self, d_model: int, d_ff: int = 2048):
        self.W1 = np.random.randn(d_model, d_ff) * 0.02
        self.b1 = np.zeros(d_ff)
        self.W2 = np.random.randn(d_ff, d_model) * 0.02
        self.b2 = np.zeros(d_model)

    def forward(self, x: np.ndarray) -> np.ndarray:
        hidden = np.maximum(0, np.dot(x, self.W1) + self.b1)
        output = np.dot(hidden, self.W2) + self.b2
        return output


class TransformerBlock:
    """Transformer编码器块"""

    def __init__(self, d_model: int, n_heads: int = 8, d_ff: int = 2048, dropout: float = 0.1):
        self.attention = MultiHeadAttention(d_model, n_heads)
        self.feed_forward = FeedForward(d_model, d_ff)
        self.norm1 = np.zeros(d_model)
        self.norm2 = np.zeros(d_model)
        self.dropout = dropout

    def forward(self, x: np.ndarray, mask: Optional[np.ndarray] = None) -> np.ndarray:
        attn_output = self.attention.forward(x, x, x, mask)
        x = x + attn_output
        x = x / (np.std(x, axis=-1, keepdims=True) + 1e-6)

        ff_output = self.feed_forward.forward(x)
        x = x + ff_output
        x = x / (np.std(x, axis=-1, keepdims=True) + 1e-6)

        return x


class TimeSeriesTransformer:
    """时序Transformer预测器"""

    def __init__(
        self,
        d_model: int = 128,
        n_heads: int = 8,
        n_layers: int = 4,
        d_ff: int = 512,
        dropout: float = 0.1,
        max_seq_len: int = 100,
    ):
        self.d_model = d_model
        self.n_heads = n_heads
        self.n_layers = n_layers
        self.d_ff = d_ff
        self.dropout = dropout
        self.max_seq_len = max_seq_len

        self.pos_encoder = PositionalEncoding(d_model, max_seq_len)
        self.encoder_blocks = [
            TransformerBlock(d_model, n_heads, d_ff, dropout) for _ in range(n_layers)
        ]
        self.output_layer = np.random.randn(d_model, 10) * 0.02

        self.is_fitted = False
        self.scaler_mean = None
        self.scaler_std = None

    def _prepare_input(
        self, data: np.ndarray, seq_len: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """准备输入数据"""
        if len(data) < seq_len + 1:
            data = np.pad(data, (0, seq_len + 1 - len(data)), mode="edge")

        X = []
        y = []
        for i in range(seq_len, len(data)):
            X.append(data[i - seq_len : i])
            y.append(data[i])

        X = np.array(X)
        y = np.array(y)

        X = X.reshape(-1, seq_len, 1)
        X = X.repeat(self.d_model, axis=-1) / np.sqrt(self.d_model)

        return X, y

    def fit(
        self,
        data: np.ndarray,
        seq_len: int = 50,
        epochs: int = 100,
        learning_rate: float = 0.001,
        batch_size: int = 32,
    ) -> Dict[str, Any]:
        """训练模型"""
        logger.info(f"开始训练Time-Series Transformer，序列长度={seq_len}，轮次={epochs}")

        X, y = self._prepare_input(data, seq_len)

        self.scaler_mean = X.mean()
        self.scaler_std = X.std() + 1e-8
        X = (X - self.scaler_mean) / self.scaler_std

        n_samples = len(X)
        indices = np.arange(n_samples)

        for epoch in range(epochs):
            np.random.shuffle(indices)
            total_loss = 0
            n_batches = 0

            for i in range(0, n_samples, batch_size):
                batch_indices = indices[i : i + batch_size]
                X_batch = X[batch_indices]
                y_batch = y[batch_indices]

                hidden = X_batch
                hidden = self.pos_encoder.forward(hidden)

                for block in self.encoder_blocks:
                    hidden = block.forward(hidden)

                last_hidden = hidden[:, -1, :]
                logits = np.dot(last_hidden, self.output_layer)

                probs = self._softmax(logits)
                loss = -np.mean(np.log(probs[np.arange(len(y_batch)), y_batch] + 1e-8))

                gradient = (probs - np.eye(10)[y_batch]) / len(y_batch)
                output_gradient = np.dot(hidden[:, -1, :].T, gradient)
                self.output_layer -= learning_rate * output_gradient

                total_loss += loss
                n_batches += 1

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {total_loss / n_batches:.4f}")

        self.is_fitted = True
        logger.info("Time-Series Transformer训练完成")

        return {"status": "trained", "epochs": epochs, "final_loss": total_loss / n_batches}

    def predict_proba(self, data: np.ndarray, seq_len: int = 50) -> np.ndarray:
        """预测概率分布"""
        if not self.is_fitted:
            logger.warning("模型未训练，返回均匀分布")
            return np.ones(10) / 10

        X, _ = self._prepare_input(data, seq_len)
        X = (X - self.scaler_mean) / self.scaler_std

        hidden = X
        hidden = self.pos_encoder.forward(hidden)

        for block in self.encoder_blocks:
            hidden = block.forward(hidden)

        last_hidden = hidden[:, -1, :]
        logits = np.dot(last_hidden, self.output_layer)
        probs = self._softmax(logits)

        return probs

    def predict(self, data: np.ndarray, seq_len: int = 50, top_k: int = 8) -> Dict[str, Any]:
        """预测并返回top_k结果"""
        probs = self.predict_proba(data, seq_len)

        top_indices = np.argsort(probs)[::-1][:top_k]
        top_probs = probs[top_indices]

        return {
            "top_k": top_indices.tolist(),
            "probabilities": top_probs.tolist(),
            "entropy": -np.sum(probs * np.log(probs + 1e-8)),
            "confidence": np.max(probs),
        }

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)

    def save(self, path: str) -> None:
        """保存模型"""
        model_data = {
            "output_layer": self.output_layer,
            "scaler_mean": self.scaler_mean,
            "scaler_std": self.scaler_std,
            "is_fitted": self.is_fitted,
            "d_model": self.d_model,
        }

        with open(path, "wb") as f:
            pickle.dump(model_data, f)

        logger.info(f"模型已保存到: {path}")

    def load(self, path: str) -> bool:
        """加载模型"""
        if not Path(path).exists():
            logger.warning(f"模型文件不存在: {path}")
            return False

        try:
            with open(path, "rb") as f:
                model_data = pickle.load(f)

            self.output_layer = model_data["output_layer"]
            self.scaler_mean = model_data["scaler_mean"]
            self.scaler_std = model_data["scaler_std"]
            self.is_fitted = model_data["is_fitted"]

            logger.info(f"模型已从: {path} 加载")
            return True

        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False


class TransformerEnsemble:
    """Transformer集成器 - 结合多个Transformer模型"""

    def __init__(self, positions: List[str] = None):
        self.positions = positions or ["wan", "qian", "bai", "shi", "ge"]
        self.models: Dict[str, TimeSeriesTransformer] = {}
        self._init_models()

    def _init_models(self):
        """初始化各位置的Transformer模型"""
        for pos in self.positions:
            self.models[pos] = TimeSeriesTransformer(
                d_model=64,
                n_heads=4,
                n_layers=2,
                d_ff=256,
                dropout=0.1,
                max_seq_len=50,
            )

    def fit(self, df: pd.DataFrame, epochs: int = 50) -> Dict[str, Any]:
        """训练所有位置的Transformer模型"""
        results = {}

        for pos in self.positions:
            if pos in df.columns:
                data = df[pos].values
                self.models[pos].d_model = 64
                self.models[pos].output_layer = np.random.randn(64, 10) * 0.02
                results[pos] = self.models[pos].fit(
                    data, seq_len=30, epochs=epochs, batch_size=16
                )

        return results

    def predict(self, df: pd.DataFrame, top_k: int = 8) -> Dict[str, Dict[str, Any]]:
        """预测所有位置"""
        predictions = {}

        for pos in self.positions:
            if pos in df.columns and pos in self.models:
                data = df[pos].values
                predictions[pos] = self.models[pos].predict(data, seq_len=30, top_k=top_k)

        return predictions

    def save(self, path: str = "models/transformer_ensemble.pkl") -> None:
        """保存集成模型"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump(
                {
                    "models": {pos: model.output_layer for pos, model in self.models.items()},
                    "positions": self.positions,
                },
                f,
            )

        logger.info(f"Transformer集成模型已保存到: {path}")

    def load(self, path: str = "models/transformer_ensemble.pkl") -> bool:
        """加载集成模型"""
        if not Path(path).exists():
            logger.warning(f"模型文件不存在: {path}")
            return False

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            for pos in data["positions"]:
                if pos in self.models:
                    self.models[pos].output_layer = data["models"][pos]
                    self.models[pos].is_fitted = True

            logger.info(f"Transformer集成模型已从: {path} 加载")
            return True

        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False
