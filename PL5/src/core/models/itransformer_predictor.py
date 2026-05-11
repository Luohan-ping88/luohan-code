"""
iTransformer - 倒置Transformer V1.0
基于清华&蚂蚁2024-2025最先进的时序预测架构

核心创新:
1. 维度倒置 - 将注意力从时间维度转向变量维度
2. 变量标记化 - 每个变量的完整历史序列作为独立标记
3. FFN时序编码 - 前馈网络沿时间维度操作，提取周期/趋势
4. 正确的层归一化 - 对单变量序列归一化，解决非平稳性

参考文献:
- Liu et al. (2024) iTransformer: Inverted Transformers Are Effective for Time Series Forecasting (ICLR 2024)
- 清华大学 & 蚂蚁集团联合提出
"""

import numpy as np
from typing import Dict, Tuple, Optional, List
import logging
from src.core.config import ModelConfig, get_model_config

logger = logging.getLogger(__name__)


class InvertedMultiHeadAttention:
    """倒置多头注意力 - 作用于变量维度

    与传统Transformer的关键区别:
    - 传统: 时间步作为token, 变量被拼接
    - 倒置: 变量作为token, 时间步被嵌入

    优势:
    - 注意力图天然捕捉变量间动态相互作用
    - 避免时间维度注意力的排列不变性矛盾
    - 变量数(5)远小于时间步数, 计算高效
    """

    def __init__(self, d_model: int = 64, n_heads: int = 4, dropout: float = 0.1):
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads
        self.dropout_rate = dropout

        scale = d_model**-0.5
        self.W_q = np.random.randn(d_model, d_model) * scale
        self.W_k = np.random.randn(d_model, d_model) * scale
        self.W_v = np.random.randn(d_model, d_model) * scale
        self.W_o = np.random.randn(d_model, d_model) * scale

        self.b_q = np.zeros(d_model)
        self.b_k = np.zeros(d_model)
        self.b_v = np.zeros(d_model)
        self.b_o = np.zeros(d_model)

    def forward(self, x: np.ndarray) -> np.ndarray:
        """前向传播

        Args:
            x: 变量嵌入 (n_vars, d_model), n_vars=5(万千万十个)
        Returns:
            output: (n_vars, d_model)
        """
        n_vars = x.shape[0]

        Q = x @ self.W_q + self.b_q
        K = x @ self.W_k + self.b_k
        V = x @ self.W_v + self.b_v

        Q = Q.reshape(n_vars, self.n_heads, self.d_k).transpose(1, 0, 2)
        K = K.reshape(n_vars, self.n_heads, self.d_k).transpose(1, 0, 2)
        V = V.reshape(n_vars, self.n_heads, self.d_k).transpose(1, 0, 2)

        scores = np.matmul(Q, K.transpose(0, 2, 1)) / np.sqrt(self.d_k)

        attention_weights = self._softmax(scores, axis=-1)

        if self.dropout_rate > 0 and self.training:
            mask = np.random.binomial(1, 1 - self.dropout_rate, attention_weights.shape)
            attention_weights = attention_weights * mask / (1 - self.dropout_rate)

        context = np.matmul(attention_weights, V)

        context = context.transpose(1, 0, 2).reshape(n_vars, self.d_model)
        output = context @ self.W_o + self.b_o

        self._last_attention = attention_weights
        return output

    def _softmax(self, x: np.ndarray, axis: int = -1) -> np.ndarray:
        x_max = np.max(x, axis=axis, keepdims=True)
        exp_x = np.exp(x - x_max)
        return exp_x / (np.sum(exp_x, axis=axis, keepdims=True) + 1e-10)

    def get_attention_map(self) -> np.ndarray:
        """获取注意力图 - 反映变量间相关性"""
        if hasattr(self, "_last_attention"):
            return np.mean(self._last_attention, axis=0)
        return np.eye(5)

    @property
    def training(self):
        return getattr(self, "_training", True)


class TemporalFFN:
    """时序前馈网络 - 沿时间维度操作

    iTransformer的关键组件:
    - FFN在时间维度上操作(而非变量维度)
    - 神经元自发形成类似数字滤波器的模式
    - 有效提取周期、趋势等时序特征
    """

    def __init__(self, d_model: int = 64, d_ff: int = 256, dropout: float = 0.1):
        self.d_model = d_model
        self.d_ff = d_ff
        self.dropout_rate = dropout

        scale = d_model**-0.5
        self.W1 = np.random.randn(d_model, d_ff) * scale
        self.b1 = np.zeros(d_ff)
        self.W2 = np.random.randn(d_ff, d_model) * scale
        self.b2 = np.zeros(d_model)

    def forward(self, x: np.ndarray) -> np.ndarray:
        """前向传播

        Args:
            x: (n_vars, d_model)
        Returns:
            output: (n_vars, d_model)
        """
        h = x @ self.W1 + self.b1
        h = np.maximum(h, 0)

        if self.dropout_rate > 0:
            mask = np.random.binomial(1, 1 - self.dropout_rate, h.shape) / (1 - self.dropout_rate)
            h = h * mask

        output = h @ self.W2 + self.b2
        return output


class InvertedTransformerBlock:
    """倒置Transformer块

    结构: LayerNorm(变量) → MultiHeadAttention → Residual →
          LayerNorm(变量) → FFN(时间) → Residual
    """

    def __init__(self, d_model: int = 64, n_heads: int = 4, d_ff: int = 256, dropout: float = 0.1):
        self.attention = InvertedMultiHeadAttention(d_model, n_heads, dropout)
        self.ffn = TemporalFFN(d_model, d_ff, dropout)

        self.norm1_weight = np.ones(d_model)
        self.norm1_bias = np.zeros(d_model)
        self.norm2_weight = np.ones(d_model)
        self.norm2_bias = np.zeros(d_model)

    def _layer_norm(self, x: np.ndarray, weight: np.ndarray, bias: np.ndarray) -> np.ndarray:
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        return weight * (x - mean) / np.sqrt(var + 1e-5) + bias

    def forward(self, x: np.ndarray) -> np.ndarray:
        """前向传播

        Args:
            x: (n_vars, d_model)
        Returns:
            output: (n_vars, d_model)
        """
        normed = self._layer_norm(x, self.norm1_weight, self.norm1_bias)
        attn_out = self.attention.forward(normed)
        x = x + attn_out

        normed = self._layer_norm(x, self.norm2_weight, self.norm2_bias)
        ffn_out = self.ffn.forward(normed)
        x = x + ffn_out

        return x


class iTransformerPredictor:
    """iTransformer预测器 - 排列五专用

    架构:
    1. 变量嵌入: 每个位置(万千万十个)的完整历史序列 → d_model维向量
    2. N层倒置Transformer: 变量维度注意力 + 时间维度FFN
    3. 预测头: 每个变量独立输出10维概率分布

    核心优势:
    - 变量维度注意力天然捕捉5位置间的动态相互作用
    - FFN沿时间维度提取周期/趋势特征
    - 变量数(5)远小于时间步数, 注意力计算高效
    - 层归一化对单变量序列归一化, 解决非平稳性
    """

    def __init__(
        self,
        n_layers: int = 3,
        d_model: int = 64,
        n_heads: int = 4,
        d_ff: int = 256,
        seq_length: int = 30,
        n_classes: int = 10,
        learning_rate: float = 0.001,
        model_config: Optional[ModelConfig] = None,
    ):
        self.positions = ["wan", "qian", "bai", "shi", "ge"]
        self.n_vars = 5
        self.n_layers = n_layers
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_ff = d_ff
        self.seq_length = seq_length
        self.n_classes = n_classes
        self.learning_rate = learning_rate
        self.fitted = False

        self._init_model()

    def _init_model(self):
        """初始化模型参数"""
        scale = self.d_model**-0.5

        self.var_embedding_W = np.random.randn(self.seq_length, self.d_model) * scale
        self.var_embedding_b = np.zeros(self.d_model)

        self.blocks = [
            InvertedTransformerBlock(d_model=self.d_model, n_heads=self.n_heads, d_ff=self.d_ff)
            for _ in range(self.n_layers)
        ]

        self.final_norm_weight = np.ones(self.d_model)
        self.final_norm_bias = np.zeros(self.d_model)

        self.heads_W = np.random.randn(self.n_vars, self.d_model, self.n_classes) * scale
        self.heads_b = np.zeros((self.n_vars, self.n_classes))

    def _embed_variables(self, data: Dict[str, np.ndarray]) -> np.ndarray:
        """变量嵌入 - 将每个位置的历史序列映射为d_model维向量

        Args:
            data: 各位置的历史序列
        Returns:
            var_embeddings: (n_vars, d_model)
        """
        embeddings = []
        for pos in self.positions:
            if pos in data and len(data[pos]) > 0:
                seq = data[pos]
                if hasattr(seq, "values"):
                    seq = seq.values
                seq = np.array(seq, dtype=np.float64)

                recent = seq[-self.seq_length :]
                if len(recent) < self.seq_length:
                    pad = np.zeros(self.seq_length - len(recent))
                    recent = np.concatenate([pad, recent])

                one_hot = np.zeros((self.seq_length, self.n_classes))
                for t, val in enumerate(recent):
                    v = int(val)
                    if 0 <= v < self.n_classes:
                        one_hot[t, v] = 1.0

                freq_features = np.fft.rfft(one_hot, axis=0).real
                if freq_features.shape[0] > self.seq_length:
                    freq_features = freq_features[: self.seq_length]
                elif freq_features.shape[0] < self.seq_length:
                    pad_rows = self.seq_length - freq_features.shape[0]
                    freq_features = np.vstack([freq_features, np.zeros((pad_rows, self.n_classes))])

                combined = np.concatenate([one_hot, freq_features], axis=1)

                if combined.shape[0] > self.seq_length:
                    combined = combined[: self.seq_length]

                target_len = self.var_embedding_W.shape[0]
                if combined.shape[0] < target_len:
                    pad_rows = target_len - combined.shape[0]
                    combined = np.vstack([np.zeros((pad_rows, combined.shape[1])), combined])
                elif combined.shape[0] > target_len:
                    combined = combined[:target_len]

                if combined.shape[1] != self.d_model:
                    proj_W = np.random.randn(combined.shape[1], self.d_model) * (combined.shape[1] ** -0.5)
                    emb = combined @ proj_W
                else:
                    emb = combined @ self.var_embedding_W + self.var_embedding_b

                var_emb = np.mean(emb, axis=0)
            else:
                var_emb = np.zeros(self.d_model)

            embeddings.append(var_emb)

        return np.array(embeddings)

    def _layer_norm(self, x: np.ndarray) -> np.ndarray:
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        return self.final_norm_weight * (x - mean) / np.sqrt(var + 1e-5) + self.final_norm_bias

    def fit(self, data: Dict[str, np.ndarray], epochs: int = 50, verbose: bool = True) -> Dict:
        """训练模型

        Args:
            data: 各位置的历史数字序列
            epochs: 训练轮数
            verbose: 是否打印训练信息
        """
        seq_len = min(len(data[p]) for p in self.positions if p in data)
        if seq_len < self.seq_length + 1:
            logger.warning(f"序列长度不足: {seq_len} < {self.seq_length + 1}")
            return {"loss": float("inf"), "epochs": 0}

        m_W = [np.zeros_like(self.heads_W[i]) for i in range(self.n_vars)]
        v_W = [np.zeros_like(self.heads_W[i]) for i in range(self.n_vars)]
        m_b = [np.zeros_like(self.heads_b[i]) for i in range(self.n_vars)]
        v_b = [np.zeros_like(self.heads_b[i]) for i in range(self.n_vars)]
        beta1, beta2, eps = 0.9, 0.999, 1e-8

        best_loss = float("inf")
        patience = 10
        patience_counter = 0
        t_step = 0

        for epoch in range(epochs):
            total_loss = 0.0
            n_samples = 0

            for start in range(0, seq_len - self.seq_length, max(1, (seq_len - self.seq_length) // 20)):
                window_data = {}
                targets = {}
                for pos in self.positions:
                    if pos in data:
                        window_data[pos] = data[pos][start : start + self.seq_length]
                        if start + self.seq_length < len(data[pos]):
                            targets[pos] = int(data[pos][start + self.seq_length])

                if len(targets) < self.n_vars:
                    continue

                var_emb = self._embed_variables(window_data)

                h = var_emb
                for block in self.blocks:
                    block.attention._training = False
                    h = block.forward(h)

                h = self._layer_norm(h)

                loss = 0.0
                grads_W = [np.zeros_like(self.heads_W[i]) for i in range(self.n_vars)]
                grads_b = [np.zeros_like(self.heads_b[i]) for i in range(self.n_vars)]

                for i, pos in enumerate(self.positions):
                    if pos not in targets:
                        continue

                    logits = h[i] @ self.heads_W[i] + self.heads_b[i]
                    logits_max = logits - np.max(logits)
                    exp_logits = np.exp(logits_max)
                    probs = exp_logits / (np.sum(exp_logits) + 1e-10)

                    loss += -np.log(probs[targets[pos]] + 1e-10)

                    grad_logits = probs.copy()
                    grad_logits[targets[pos]] -= 1.0

                    grads_W[i] += np.outer(h[i], grad_logits)
                    grads_b[i] += grad_logits

                loss /= len(targets)
                total_loss += loss
                n_samples += 1

                t_step += 1
                for i in range(self.n_vars):
                    m_W[i] = beta1 * m_W[i] + (1 - beta1) * grads_W[i]
                    v_W[i] = beta2 * v_W[i] + (1 - beta2) * grads_W[i] ** 2
                    m_b[i] = beta1 * m_b[i] + (1 - beta1) * grads_b[i]
                    v_b[i] = beta2 * v_b[i] + (1 - beta2) * grads_b[i] ** 2

                    m_W_hat = m_W[i] / (1 - beta1**t_step)
                    v_W_hat = v_W[i] / (1 - beta2**t_step)
                    m_b_hat = m_b[i] / (1 - beta1**t_step)
                    v_b_hat = v_b[i] / (1 - beta2**t_step)

                    self.heads_W[i] -= self.learning_rate * m_W_hat / (np.sqrt(v_W_hat) + eps)
                    self.heads_b[i] -= self.learning_rate * m_b_hat / (np.sqrt(v_b_hat) + eps)

            avg_loss = total_loss / max(n_samples, 1)

            if avg_loss < best_loss:
                best_loss = avg_loss
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter >= patience:
                if verbose:
                    logger.info(f"  iTransformer早停: epoch {epoch+1}, loss={avg_loss:.4f}")
                break

            if verbose and (epoch + 1) % 10 == 0:
                logger.info(f"  iTransformer epoch {epoch+1}/{epochs}, loss={avg_loss:.4f}")

        self.fitted = True
        return {"loss": best_loss, "epochs": epoch + 1}

    def predict_proba(self, data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """预测各位置的下一个数字概率分布

        Args:
            data: 各位置的历史数字序列
        Returns:
            predictions: 各位置的概率分布
        """
        if not self.fitted:
            return {pos: np.ones(self.n_classes) / self.n_classes for pos in self.positions}

        var_emb = self._embed_variables(data)

        h = var_emb
        for block in self.blocks:
            block.attention._training = False
            h = block.forward(h)

        h = self._layer_norm(h)

        predictions = {}
        for i, pos in enumerate(self.positions):
            logits = h[i] @ self.heads_W[i] + self.heads_b[i]
            logits_max = logits - np.max(logits)
            exp_logits = np.exp(logits_max)
            probs = exp_logits / (np.sum(exp_logits) + 1e-10)
            predictions[pos] = probs

        return predictions

    def get_variable_attention_map(self, data: Dict[str, np.ndarray]) -> np.ndarray:
        """获取变量间注意力图

        反映5个位置之间的动态相关性
        """
        if not self.fitted or not self.blocks:
            return np.eye(self.n_vars)

        var_emb = self._embed_variables(data)
        _ = var_emb
        for block in self.blocks:
            block.attention._training = False
            _ = block.forward(_)

        attention_maps = []
        for block in self.blocks:
            attention_maps.append(block.attention.get_attention_map())

        avg_attention = np.mean(attention_maps, axis=0)
        return avg_attention

    def get_position_correlation_insight(self, data: Dict[str, np.ndarray]) -> Dict:
        """获取位置间相关性洞察"""
        attn_map = self.get_variable_attention_map(data)

        insights = {
            "attention_matrix": attn_map.tolist(),
            "position_names": self.positions,
            "strongest_pairs": [],
            "independent_positions": [],
        }

        for i in range(self.n_vars):
            for j in range(i + 1, self.n_vars):
                strength = (attn_map[i, j] + attn_map[j, i]) / 2
                insights["strongest_pairs"].append(
                    {"positions": (self.positions[i], self.positions[j]), "strength": float(strength)}
                )

        insights["strongest_pairs"].sort(key=lambda x: x["strength"], reverse=True)

        for i in range(self.n_vars):
            row = attn_map[i].copy()
            row[i] = 0
            if np.max(row) < 0.15:
                insights["independent_positions"].append(self.positions[i])

        return insights
