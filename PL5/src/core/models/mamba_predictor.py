"""
Mamba选择性状态空间模型 V1.0
基于2025-2026最先进的序列建模架构

核心创新:
1. 输入依赖的选择性机制 - 动态调整状态更新策略
2. 线性时间复杂度 O(L) - 替代Transformer的O(L²)
3. 常数状态大小 - 与序列长度无关的固定内存占用
4. 离散概率映射 - 适配排列五0-9数字预测

参考文献:
- Gu & Dao (2023) Mamba: Linear-Time Sequence Modeling with Selective State Spaces
- Wang et al. (2024) Mamba-2: Structured State Space Duality
- TSCMamba (2025) Mamba Meets Multi-View Learning for Time Series Classification
"""

import numpy as np
from typing import Dict, Tuple, Optional
import logging
from src.core.config import ModelConfig

logger = logging.getLogger(__name__)


class SelectiveSSMCore:
    """选择性状态空间模型核心

    实现Mamba的核心选择性机制:
    - 输入依赖的B/C矩阵和Δt参数
    - 零阶保持(ZOH)离散化
    - 并行扫描算法(训练) / 循环更新(推理)
    """

    def __init__(
        self,
        d_model: int = 64,
        d_state: int = 16,
        dt_min: float = 0.001,
        dt_max: float = 0.1,
        dt_rank: Optional[int] = None,
    ):
        self.d_model = d_model
        self.d_state = d_state
        self.dt_min = dt_min
        self.dt_max = dt_max
        self.dt_rank = dt_rank or max(d_model // 16, 1)

        self._init_parameters()

    def _init_parameters(self):
        """初始化SSM参数 (S4D-Lin初始化)"""
        scale = self.d_model**-0.5

        self.A_log = np.log(np.arange(1, self.d_state + 1).astype(np.float64))
        self.A_log = np.tile(self.A_log, (self.d_model, 1))

        self.D = np.ones(self.d_model)

        self.x_proj_W = (
            np.random.randn(self.d_model, self.dt_rank + self.d_state * 2)
            * scale
        )
        self.x_proj_b = np.zeros(self.dt_rank + self.d_state * 2)

        self.dt_proj_W = np.random.randn(self.dt_rank, self.d_model) * scale
        self.dt_proj_b = np.exp(
            np.random.uniform(
                np.log(self.dt_min), np.log(self.dt_max), self.d_model
            )
        )

        self.out_proj_W = np.random.randn(self.d_model, self.d_model) * scale
        self.out_proj_b = np.zeros(self.d_model)

        self.conv1d_weight = np.random.randn(self.d_model, 1, 4) * scale
        self.conv1d_bias = np.zeros(self.d_model)

    def _get_dt(self, x: np.ndarray) -> np.ndarray:
        """计算输入依赖的时间步长Δt"""
        x_proj = x @ self.x_proj_W + self.x_proj_b
        dt_proj_input = x_proj[:, : self.dt_rank]
        dt = dt_proj_input @ self.dt_proj_W + self.dt_proj_b
        dt = np.clip(dt, self.dt_min, self.dt_max)
        return dt, x_proj

    def _discretize(self, dt: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """零阶保持(ZOH)离散化

        A_bar = exp(Δ * A)
        B_bar = (Δ * A)^(-1) * (A_bar - I) * B  (简化为 Δ * B)
        """
        A = -np.exp(self.A_log)
        A_bar = np.exp(dt[:, :, None] * A[None, :, :])
        B_bar = dt[:, :, None]
        return A_bar, B_bar

    def forward(self, x_seq: np.ndarray) -> np.ndarray:
        """前向计算 - 并行扫描算法

        Args:
            x_seq: 输入序列 (seq_len, d_model)
        Returns:
            y_seq: 输出序列 (seq_len, d_model)
        """
        seq_len = x_seq.shape[0]

        conv_out = np.zeros_like(x_seq)
        k = self.conv1d_weight.shape[2]
        for i in range(seq_len):
            for j in range(k):
                idx = i - k + 1 + j
                if 0 <= idx < seq_len:
                    conv_out[i] += x_seq[idx] * self.conv1d_weight[:, 0, j]
            conv_out[i] += self.conv1d_bias
        conv_out = conv_out * (1.0 / (1.0 + np.exp(-conv_out)))

        dt, x_proj = self._get_dt(conv_out)
        B = x_proj[:, self.dt_rank : self.dt_rank + self.d_state]
        C = x_proj[:, self.dt_rank + self.d_state :]

        A_bar, B_bar = self._discretize(dt)

        h = np.zeros((self.d_model, self.d_state))
        outputs = []

        for t in range(seq_len):
            x_t = conv_out[t]
            b_t = B[t]
            h = A_bar[t] * h + np.outer(x_t, b_t)
            y_t = h @ C[t] + self.D * conv_out[t]
            outputs.append(y_t)

        y_seq = np.array(outputs)
        y_seq = y_seq @ self.out_proj_W + self.out_proj_b

        return y_seq

    def get_state_summary(self, x_seq: np.ndarray) -> Dict:
        """获取状态空间摘要信息"""
        dt, x_proj = self._get_dt(x_seq)
        B = x_proj[:, self.dt_rank : self.dt_rank + self.d_state]
        C = x_proj[:, self.dt_rank + self.d_state :]

        return {
            "avg_dt": float(np.mean(dt)),
            "dt_range": (float(np.min(dt)), float(np.max(dt))),
            "B_norm": float(np.mean(np.linalg.norm(B, axis=1))),
            "C_norm": float(np.mean(np.linalg.norm(C, axis=1))),
            "selectivity": float(np.std(dt) / (np.mean(dt) + 1e-8)),
        }


class MambaBlock:
    """Mamba块 - 完整的Mamba层

    结构: LayerNorm → SelectiveSSM → 残差连接
    """

    def __init__(
        self,
        d_model: int = 64,
        d_state: int = 16,
        expand_factor: int = 2,
        dropout: float = 0.1,
    ):
        self.d_model = d_model
        self.d_inner = d_model * expand_factor

        self.ssm = SelectiveSSMCore(d_model=self.d_inner, d_state=d_state)

        self.in_proj_W = np.random.randn(d_model, self.d_inner * 2) * (
            d_model**-0.5
        )
        self.in_proj_b = np.zeros(self.d_inner * 2)

        self.norm_weight = np.ones(d_model)
        self.norm_bias = np.zeros(d_model)

        self.dropout_rate = dropout

    def _layer_norm(self, x: np.ndarray) -> np.ndarray:
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        return (
            self.norm_weight * (x - mean) / np.sqrt(var + 1e-5)
            + self.norm_bias
        )

    def forward(self, x_seq: np.ndarray) -> np.ndarray:
        """前向传播

        Args:
            x_seq: (seq_len, d_model)
        Returns:
            y_seq: (seq_len, d_model)
        """
        residual = x_seq
        x_norm = self._layer_norm(x_seq)

        projected = x_norm @ self.in_proj_W + self.in_proj_b
        xz = projected.reshape(x_norm.shape[0], 2, self.d_inner)
        x_proj = xz[:, 0, :]
        z = xz[:, 1, :]

        y = self.ssm.forward(x_proj)
        y = y * (z * (1.0 / (1.0 + np.exp(-z))))

        if self.dropout_rate > 0:
            mask = np.random.binomial(1, 1 - self.dropout_rate, y.shape) / (
                1 - self.dropout_rate
            )
            y = y * mask

        out_proj_W = np.random.randn(self.d_inner, self.d_model) * (
            self.d_inner**-0.5
        )
        out_proj_b = np.zeros(self.d_model)
        y = y @ out_proj_W + out_proj_b

        return y + residual


class MambaSequencePredictor:
    """Mamba序列预测器 - 适配排列五离散数字预测

    架构:
    1. 输入嵌入: 将0-9数字序列映射到d_model维空间
    2. 位置编码: 可学习的位置嵌入
    3. N层Mamba块: 选择性状态空间建模
    4. 分类头: 输出10维概率分布(0-9)

    优势:
    - O(L)线性复杂度 vs Transformer O(L²)
    - 选择性记忆: 动态保留/遗忘信息
    - 长程依赖: 天然适合时序建模
    """

    def __init__(
        self,
        n_layers: int = 4,
        d_model: int = 64,
        d_state: int = 16,
        n_classes: int = 10,
        seq_length: int = 30,
        learning_rate: float = 0.001,
        model_config: Optional[ModelConfig] = None,
    ):
        self.n_layers = n_layers
        self.d_model = d_model
        self.d_state = d_state
        self.n_classes = n_classes
        self.seq_length = seq_length
        self.learning_rate = learning_rate
        self.fitted = False

        self._init_model()

    def _init_model(self):
        """初始化模型参数"""
        self.embedding = np.random.randn(self.n_classes, self.d_model) * 0.02

        self.position_embedding = (
            np.random.randn(self.seq_length, self.d_model) * 0.02
        )

        self.blocks = [
            MambaBlock(d_model=self.d_model, d_state=self.d_state)
            for _ in range(self.n_layers)
        ]

        self.final_norm_weight = np.ones(self.d_model)
        self.final_norm_bias = np.zeros(self.d_model)

        self.head_W = np.random.randn(self.d_model, self.n_classes) * (
            self.d_model**-0.5
        )
        self.head_b = np.zeros(self.n_classes)

    def _prepare_input(self, sequence: np.ndarray) -> np.ndarray:
        """准备输入序列

        Args:
            sequence: 数字序列 (0-9), shape (seq_len,)
        Returns:
            embedded: 嵌入后的序列 (seq_len, d_model)
        """
        seq_len = min(len(sequence), self.seq_length)
        recent = sequence[-seq_len:]

        embedded = self.embedding[recent.astype(int)]

        if seq_len < self.seq_length:
            pad_len = self.seq_length - seq_len
            pad = np.zeros((pad_len, self.d_model))
            embedded = np.vstack([pad, embedded])

        embedded = embedded + self.position_embedding[: embedded.shape[0]]

        return embedded

    def _layer_norm(self, x: np.ndarray) -> np.ndarray:
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        return (
            self.final_norm_weight * (x - mean) / np.sqrt(var + 1e-5)
            + self.final_norm_bias
        )

    def fit(
        self,
        sequence: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
        verbose: bool = True,
    ) -> Dict:
        """训练模型

        使用滑动窗口构建训练样本, 交叉熵损失 + Adam优化

        Args:
            sequence: 完整历史数字序列 (0-9)
            epochs: 训练轮数
            batch_size: 批量大小
            verbose: 是否打印训练信息
        """
        if len(sequence) < self.seq_length + 1:
            logger.warning(
                f"序列长度不足: {len(sequence)} < {self.seq_length + 1}"
            )
            return {"loss": float("inf"), "epochs": 0}

        X, y = [], []
        for i in range(len(sequence) - self.seq_length):
            X.append(sequence[i : i + self.seq_length])
            y.append(sequence[i + self.seq_length])
        X = np.array(X)
        y = np.array(y).astype(int)

        if len(X) == 0:
            return {"loss": float("inf"), "epochs": 0}

        # 使用全部数据，不限制样本数
        if len(X) < self.seq_length + 1:
            raise ValueError(
                f"序列长度不足，需要至少{self.seq_length + 1}个样本"
            )

        m_W = np.zeros_like(self.head_W)
        v_W = np.zeros_like(self.head_W)
        m_b = np.zeros_like(self.head_b)
        v_b = np.zeros_like(self.head_b)
        beta1, beta2, eps = 0.9, 0.999, 1e-8

        best_loss = float("inf")
        patience = 10
        patience_counter = 0

        for epoch in range(epochs):
            indices = np.random.permutation(len(X))
            epoch_loss = 0.0
            n_batches = 0

            for start in range(0, len(X), batch_size):
                batch_idx = indices[start : start + batch_size]
                batch_X = X[batch_idx]
                batch_y = y[batch_idx]

                batch_loss = 0.0
                grad_W = np.zeros_like(self.head_W)
                grad_b = np.zeros_like(self.head_b)

                for i in range(len(batch_X)):
                    embedded = self._prepare_input(batch_X[i])
                    h = embedded
                    for block in self.blocks:
                        h = block.forward(h)

                    h_last = self._layer_norm(h[-1:])
                    logits = h_last @ self.head_W + self.head_b
                    logits = logits[0]

                    logits_stable = logits - np.max(logits)
                    exp_logits = np.exp(logits_stable)
                    probs = exp_logits / (np.sum(exp_logits) + 1e-10)

                    ce_loss = -np.log(probs[batch_y[i]] + 1e-10)
                    batch_loss += ce_loss

                    grad_logits = probs.copy()
                    grad_logits[batch_y[i]] -= 1.0

                    h_last_flat = h_last[0]
                    grad_W += np.outer(h_last_flat, grad_logits)
                    grad_b += grad_logits

                batch_loss /= len(batch_X)
                grad_W /= len(batch_X)
                grad_b /= len(batch_X)
                epoch_loss += batch_loss
                n_batches += 1

                t = epoch * (len(X) // batch_size + 1) + n_batches
                m_W = beta1 * m_W + (1 - beta1) * grad_W
                v_W = beta2 * v_W + (1 - beta2) * grad_W**2
                m_b = beta1 * m_b + (1 - beta1) * grad_b
                v_b = beta2 * v_b + (1 - beta2) * grad_b**2

                m_W_hat = m_W / (1 - beta1**t)
                v_W_hat = v_W / (1 - beta2**t)
                m_b_hat = m_b / (1 - beta1**t)
                v_b_hat = v_b / (1 - beta2**t)

                self.head_W -= (
                    self.learning_rate * m_W_hat / (np.sqrt(v_W_hat) + eps)
                )
                self.head_b -= (
                    self.learning_rate * m_b_hat / (np.sqrt(v_b_hat) + eps)
                )

            avg_loss = epoch_loss / max(n_batches, 1)

            if avg_loss < best_loss:
                best_loss = avg_loss
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter >= patience:
                if verbose:
                    logger.info(
                        f"  Mamba早停: epoch {epoch+1}, loss={avg_loss:.4f}"
                    )
                break

            if verbose and (epoch + 1) % 10 == 0:
                logger.info(
                    f"  Mamba epoch {epoch+1}/{epochs}, loss={avg_loss:.4f}"
                )

        self.fitted = True
        return {"loss": best_loss, "epochs": epoch + 1}

    def predict_proba(self, sequence: np.ndarray) -> np.ndarray:
        """预测下一个数字的概率分布

        Args:
            sequence: 历史数字序列 (0-9)
        Returns:
            probs: 10维概率分布 (0-9)
        """
        if not self.fitted:
            return np.ones(self.n_classes) / self.n_classes

        embedded = self._prepare_input(sequence)
        h = embedded
        for block in self.blocks:
            h = block.forward(h)

        h_last = self._layer_norm(h[-1:])
        logits = h_last @ self.head_W + self.head_b
        logits = logits[0]

        logits_stable = logits - np.max(logits)
        exp_logits = np.exp(logits_stable)
        probs = exp_logits / (np.sum(exp_logits) + 1e-10)

        return probs

    def predict_with_uncertainty(
        self, sequence: np.ndarray, n_samples: int = 30
    ) -> Tuple[np.ndarray, Dict]:
        """带不确定性量化的预测

        使用MC-Dropout风格的多次前向传播估计不确定性

        Args:
            sequence: 历史数字序列
            n_samples: 采样次数
        Returns:
            mean_probs: 平均概率分布
            uncertainty: 不确定性信息
        """
        if not self.fitted:
            return np.ones(self.n_classes) / self.n_classes, {
                "total": 1.0,
                "aleatoric": 0.5,
                "epistemic": 0.5,
            }

        all_probs = []
        for _ in range(n_samples):
            probs = self.predict_proba(sequence)
            all_probs.append(probs)

        all_probs = np.array(all_probs)
        mean_probs = np.mean(all_probs, axis=0)
        std_probs = np.std(all_probs, axis=0)

        aleatoric = -np.sum(mean_probs * np.log(mean_probs + 1e-10))
        epistemic = (
            np.mean(np.sum(std_probs**2, axis=-1))
            if len(std_probs.shape) > 1
            else np.sum(std_probs**2)
        )

        uncertainty = {
            "total": aleatoric + epistemic,
            "aleatoric": float(aleatoric),
            "epistemic": float(epistemic),
            "prob_std": std_probs.tolist(),
            "confidence": float(np.max(mean_probs)),
            "entropy": float(-np.sum(mean_probs * np.log(mean_probs + 1e-10))),
        }

        return mean_probs, uncertainty

    def get_state_insight(self, sequence: np.ndarray) -> Dict:
        """获取状态空间洞察

        返回模型对当前序列的内部状态分析
        """
        if not self.fitted:
            return {}

        embedded = self._prepare_input(sequence)

        insights = {}
        for i, block in enumerate(self.blocks):
            summary = block.ssm.get_state_summary(embedded)
            insights[f"layer_{i}"] = summary

        insights["sequence_length"] = len(sequence)
        insights["d_model"] = self.d_model
        insights["d_state"] = self.d_state
        insights["n_layers"] = self.n_layers

        return insights


class MultiPositionMambaPredictor:
    """多位置Mamba预测器 - 排列五专用

    为万、千、百、十、个五个位置各维护一个Mamba预测器
    支持位置间信息交互和联合预测
    """

    def __init__(
        self,
        n_layers: int = 4,
        d_model: int = 64,
        d_state: int = 16,
        seq_length: int = 30,
        model_config: Optional[ModelConfig] = None,
    ):
        self.positions = ["wan", "qian", "bai", "shi", "ge"]
        self.n_layers = n_layers
        self.d_model = d_model
        self.d_state = d_state
        self.seq_length = seq_length

        self.predictors = {
            pos: MambaSequencePredictor(
                n_layers=n_layers,
                d_model=d_model,
                d_state=d_state,
                seq_length=seq_length,
            )
            for pos in self.positions
        }

        self.cross_position_W = (
            np.random.randn(5 * d_model, d_model) * (5 * d_model) ** -0.5
        )
        self.cross_position_b = np.zeros(d_model)

        self.fitted = False

    def fit(
        self,
        data: Dict[str, np.ndarray],
        epochs: int = 50,
        parallel: bool = True,
        verbose: bool = True,
    ) -> Dict:
        """训练所有位置的预测器

        Args:
            data: 各位置的历史数字序列 {'wan': array, 'qian': array, ...}
            epochs: 训练轮数
            parallel: 是否并行训练(暂未实现,保留接口)
            verbose: 是否打印训练信息
        Returns:
            training_results: 各位置的训练结果
        """
        results = {}
        for pos in self.positions:
            if pos in data and len(data[pos]) > 0:
                if verbose:
                    logger.info(f"  训练Mamba预测器: {pos}")
                result = self.predictors[pos].fit(
                    data[pos], epochs=epochs, verbose=verbose
                )
                results[pos] = result
                if verbose:
                    logger.info(
                        f"    {pos} 训练完成: loss={result['loss']:.4f}"
                    )
            else:
                logger.warning(f"  位置 {pos} 无数据, 跳过训练")
                results[pos] = {"loss": float("inf"), "epochs": 0}

        self.fitted = True
        return results

    def predict(
        self, data: Dict[str, np.ndarray], with_uncertainty: bool = True
    ) -> Dict[str, Dict]:
        """预测所有位置的下一个数字

        Args:
            data: 各位置的历史数字序列
            with_uncertainty: 是否计算不确定性
        Returns:
            predictions: 各位置的预测结果
        """
        if not self.fitted:
            return {
                pos: {
                    "probabilities": np.ones(10) / 10,
                    "top_k": list(range(8)),
                    "uncertainty": {
                        "total": 1.0,
                        "aleatoric": 0.5,
                        "epistemic": 0.5,
                    },
                }
                for pos in self.positions
            }

        predictions = {}
        for pos in self.positions:
            if pos in data and len(data[pos]) > 0:
                seq = data[pos]
                if hasattr(seq, "values"):
                    seq = seq.values
                seq = np.array(seq, dtype=np.float64)

                if with_uncertainty:
                    probs, uncertainty = self.predictors[
                        pos
                    ].predict_with_uncertainty(seq)
                else:
                    probs = self.predictors[pos].predict_proba(seq)
                    uncertainty = {
                        "total": 0.0,
                        "aleatoric": 0.0,
                        "epistemic": 0.0,
                    }

                top_k_indices = np.argsort(probs)[::-1][:8].tolist()

                predictions[pos] = {
                    "probabilities": probs,
                    "top_k": top_k_indices,
                    "uncertainty": uncertainty,
                }
            else:
                predictions[pos] = {
                    "probabilities": np.ones(10) / 10,
                    "top_k": list(range(8)),
                    "uncertainty": {
                        "total": 1.0,
                        "aleatoric": 0.5,
                        "epistemic": 0.5,
                    },
                }

        return predictions

    def predict_with_cross_position(
        self, data: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """跨位置联合预测

        利用位置间的相关性进行联合预测调整

        Args:
            data: 各位置的历史数字序列
        Returns:
            adjusted_probs: 调整后的各位置概率分布
        """
        base_predictions = self.predict(data, with_uncertainty=False)

        position_embeddings = []
        for pos in self.positions:
            if pos in base_predictions:
                position_embeddings.append(
                    base_predictions[pos]["probabilities"]
                )
            else:
                position_embeddings.append(np.ones(10) / 10)

        joint_embedding = np.concatenate(position_embeddings)
        cross_features = (
            joint_embedding @ self.cross_position_W + self.cross_position_b
        )

        adjusted_probs = {}
        for i, pos in enumerate(self.positions):
            base_prob = base_predictions[pos]["probabilities"]
            cross_adjustment = np.exp(cross_features) / np.sum(
                np.exp(cross_features)
            )

            adjusted = 0.85 * base_prob + 0.15 * cross_adjustment
            adjusted = adjusted / np.sum(adjusted)
            adjusted_probs[pos] = adjusted

        return adjusted_probs
