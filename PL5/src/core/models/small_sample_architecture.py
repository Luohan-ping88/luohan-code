"""
小样本增强网络架构与优化器模块
=====================================

设计理念
--------
本模块专门针对小样本时序预测场景（如排列5彩票数据，仅7667期历史数据，
每期5个0-9的数字）设计，核心思想包括：

1. **元学习（MAML）框架**：通过内循环/外循环的双层优化，使模型在少量样本上
   即可快速适应新分布。内循环使用大学习率在支持集上做几步梯度下降得到
   task-specific 参数，外循环在查询集上计算元梯度更新元参数。

2. **多尺度特征提取**：1D 卷积捕获局部时序模式（如连号、奇偶排列），
   自注意力机制捕获全局长程依赖，残差连接避免深层网络的退化与梯度消失。

3. **正则化策略组合**：Dropout 随机失活 + BatchNorm 批归一化 + L2 权重衰减
   + 标签平滑（label smoothing）多重机制共同抑制小数据集上的过拟合。

4. **对比学习损失**：通过 InfoNCE 风格的对比损失，拉近同类特征表示、
   推远异类特征表示，增强特征空间的判别力与几何结构。

5. **多任务学习**：5 个位置（万/千/百/十/个）共享底层特征提取器，
   上层各自独立预测头，通过硬参数共享减少参数量、提升泛化能力。

6. **平坦最小值寻找**：基于 SAM（Sharpness-Aware Minimization）思路，
   优化损失函数的平坦邻域而非尖锐点，提升模型在测试集上的鲁棒性。

7. **梯度噪声注入**：训练过程中向梯度注入衰减型高斯噪声，帮助模型跳出
   sharp minima，在小数据集上获得更好的泛化性能。

实现说明
--------
所有核心逻辑使用 NumPy 实现（不依赖 PyTorch/TensorFlow），但代码结构
（forward/backward/parameters/grads 接口）严格对齐 PyTorch 的 Module 语义，
便于后续无缝迁移到 PyTorch 框架。所有可训练参数以字典形式存储，优化器通过
统一接口对其进行读写。

兼容性
------
提供 `predict` 方法，返回与 EnhancedPL5Predictor 一致的概率分布字典格式：
    {
        pos: {
            "top_k": List[int],            # top-k 候选数字
            "probabilities": List[float],  # 对应概率
            "uncertainty": float,          # 不确定性
            "fallback": bool               # 是否回退
        }
    }
"""

from __future__ import annotations

import logging
import math
import pickle
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# 5 个位置标识，与 EnhancedPL5Predictor 保持一致
POSITIONS: List[str] = ["wan", "qian", "bai", "shi", "ge"]
# 数字取值范围（排列5每个位置为 0-9）
NUM_CLASSES: int = 10


# =============================================================================
# 工具函数
# =============================================================================
def _softmax(x: np.ndarray, axis: int = -1, temperature: float = 1.0) -> np.ndarray:
    """数值稳定的 softmax

    Args:
        x: 输入 logits
        axis: softmax 作用的轴
        temperature: 温度系数，>1 平滑分布，<1 锐化分布

    Returns:
        与 x 同形状的概率分布
    """
    x = x / max(temperature, 1e-8)
    x_max = np.max(x, axis=axis, keepdims=True)
    e = np.exp(x - x_max)
    return e / (np.sum(e, axis=axis, keepdims=True) + 1e-12)


def _log_softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """数值稳定的 log-softmax"""
    x_max = np.max(x, axis=axis, keepdims=True)
    shifted = x - x_max
    log_sum_exp = np.log(np.sum(np.exp(shifted), axis=axis, keepdims=True) + 1e-12)
    return shifted - log_sum_exp


def _he_init(fan_in: int, fan_out: int, rng: np.random.RandomState) -> np.ndarray:
    """He 正态初始化（适合 ReLU 系激活）"""
    std = math.sqrt(2.0 / max(fan_in, 1))
    return rng.randn(fan_in, fan_out).astype(np.float64) * std


def _xavier_init(fan_in: int, fan_out: int, rng: np.random.RandomState) -> np.ndarray:
    """Xavier/Glorot 正态初始化（适合 tanh/sigmoid）"""
    std = math.sqrt(2.0 / max(fan_in + fan_out, 2))
    return rng.randn(fan_in, fan_out).astype(np.float64) * std


def _one_hot(labels: np.ndarray, num_classes: int = NUM_CLASSES) -> np.ndarray:
    """将整数标签转为 one-hot 编码"""
    out = np.zeros((labels.shape[0], num_classes), dtype=np.float64)
    out[np.arange(labels.shape[0]), labels.astype(int)] = 1.0
    return out


def _label_smooth(one_hot: np.ndarray, smoothing: float = 0.1) -> np.ndarray:
    """标签平滑：将 one-hot 转为 (1-α)*one_hot + α/K 的分布"""
    k = one_hot.shape[-1]
    return one_hot * (1.0 - smoothing) + smoothing / k


# =============================================================================
# 网络层（NumPy 实现，接口对齐 PyTorch Module）
# =============================================================================
class _Layer:
    """所有层的基类，对齐 PyTorch nn.Module 的 parameters/grads 接口"""

    def __init__(self) -> None:
        self.params: Dict[str, np.ndarray] = {}
        self.grads: Dict[str, np.ndarray] = {}
        self.training: bool = True

    def forward(self, *args: Any, **kwargs: Any) -> np.ndarray:
        raise NotImplementedError

    def backward(self, *args: Any, **kwargs: Any) -> np.ndarray:
        raise NotImplementedError

    def parameters(self) -> List[Tuple[str, np.ndarray]]:
        """返回 (name, param) 列表，便于优化器统一更新"""
        return [(k, v) for k, v in self.params.items()]

    def gradients(self) -> List[Tuple[str, np.ndarray]]:
        return [(k, v) for k, v in self.grads.items()]

    def train(self, mode: bool = True) -> "_Layer":
        self.training = mode
        return self

    def eval(self) -> "_Layer":
        return self.train(False)

    def leaf_layers(self) -> List["_Layer"]:
        """返回所有叶子层（自身即叶子的层返回 [self]；容器层需重写以递归展开）"""
        return [self]


class _Linear(_Layer):
    """全连接层：y = x @ W + b"""

    def __init__(self, in_features: int, out_features: int,
                 rng: np.random.RandomState, bias: bool = True,
                 init: str = "he") -> None:
        super().__init__()
        if init == "he":
            self.params["W"] = _he_init(in_features, out_features, rng)
        else:
            self.params["W"] = _xavier_init(in_features, out_features, rng)
        if bias:
            self.params["b"] = np.zeros(out_features, dtype=np.float64)
        self.in_features = in_features
        self.out_features = out_features
        self.has_bias = bias
        # 缓存反向传播所需中间量
        self._x: Optional[np.ndarray] = None
        # 梯度占位
        self.grads["W"] = np.zeros_like(self.params["W"])
        if bias:
            self.grads["b"] = np.zeros_like(self.params["b"])

    def forward(self, x: np.ndarray) -> np.ndarray:
        # x: (..., in_features) 支持任意前置维度（对齐 PyTorch nn.Linear）
        self._x = x
        out = x @ self.params["W"]
        if self.has_bias:
            out = out + self.params["b"]
        return out

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        # grad_output: (..., out_features)
        # 将前置维度展平后计算权重梯度
        x_2d = self._x.reshape(-1, self.in_features)         # (N, in)
        g_2d = grad_output.reshape(-1, self.out_features)    # (N, out)
        self.grads["W"] = x_2d.T @ g_2d                      # (in, out)
        if self.has_bias:
            # 对所有前置维度求和
            self.grads["b"] = np.sum(grad_output, axis=tuple(range(grad_output.ndim - 1)))
        return grad_output @ self.params["W"].T  # 回传到输入 (..., in_features)


class _LayerNorm(_Layer):
    """层归一化（对小 batch 更稳定，替代 BatchNorm 在 batch=1 时的退化）"""

    def __init__(self, num_features: int, eps: float = 1e-5) -> None:
        super().__init__()
        self.params["gamma"] = np.ones(num_features, dtype=np.float64)
        self.params["beta"] = np.zeros(num_features, dtype=np.float64)
        self.grads["gamma"] = np.zeros_like(self.params["gamma"])
        self.grads["beta"] = np.zeros_like(self.params["beta"])
        self.eps = eps
        self._x: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None
        self._mean: Optional[np.ndarray] = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        # x: (..., num_features)
        self._x = x
        self._mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        self._std = np.sqrt(var + self.eps)
        normed = (x - self._mean) / self._std
        return normed * self.params["gamma"] + self.params["beta"]

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        N = self._x.shape[-1]
        normed = (self._x - self._mean) / self._std
        self.grads["gamma"] = np.sum(grad_output * normed, axis=tuple(range(grad_output.ndim - 1)))
        self.grads["beta"] = np.sum(grad_output, axis=tuple(range(grad_output.ndim - 1)))
        # 关于输入的梯度
        dnorm = grad_output * self.params["gamma"]
        dx = (1.0 / N) * (self._std ** -1) * (
            N * dnorm
            - np.sum(dnorm, axis=-1, keepdims=True)
            - normed * np.sum(dnorm * normed, axis=-1, keepdims=True)
        )
        return dx


class _BatchNorm1D(_Layer):
    """1D 批归一化，训练时使用 batch 统计量，推理时使用滑动平均"""

    def __init__(self, num_features: int, momentum: float = 0.9, eps: float = 1e-5) -> None:
        super().__init__()
        self.params["gamma"] = np.ones(num_features, dtype=np.float64)
        self.params["beta"] = np.zeros(num_features, dtype=np.float64)
        # 非训练参数：滑动均值/方差
        self.running_mean = np.zeros(num_features, dtype=np.float64)
        self.running_var = np.ones(num_features, dtype=np.float64)
        self.grads["gamma"] = np.zeros_like(self.params["gamma"])
        self.grads["beta"] = np.zeros_like(self.params["beta"])
        self.momentum = momentum
        self.eps = eps
        self._cache: Optional[Dict[str, np.ndarray]] = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        # x: (batch, num_features)
        if self.training:
            mean = np.mean(x, axis=0)
            var = np.var(x, axis=0)
            std = np.sqrt(var + self.eps)
            x_hat = (x - mean) / std
            self.running_mean = self.momentum * self.running_mean + (1 - self.momentum) * mean
            self.running_var = self.momentum * self.running_var + (1 - self.momentum) * var
            self._cache = {"x_hat": x_hat, "std": std, "mean": mean, "var": var}
        else:
            std = np.sqrt(self.running_var + self.eps)
            x_hat = (x - self.running_mean) / std
            self._cache = None
        return x_hat * self.params["gamma"] + self.params["beta"]

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        if self._cache is None:
            return grad_output
        x_hat = self._cache["x_hat"]
        std = self._cache["std"]
        N = grad_output.shape[0]
        self.grads["gamma"] = np.sum(grad_output * x_hat, axis=0)
        self.grads["beta"] = np.sum(grad_output, axis=0)
        dnorm = grad_output * self.params["gamma"]
        dx = (1.0 / N) * (std ** -1) * (
            N * dnorm
            - np.sum(dnorm, axis=0)
            - x_hat * np.sum(dnorm * x_hat, axis=0)
        )
        return dx


class _Dropout(_Layer):
    """倒置 Dropout，仅训练时生效"""

    def __init__(self, p: float = 0.3, rng: Optional[np.random.RandomState] = None) -> None:
        super().__init__()
        self.p = float(np.clip(p, 0.0, 0.9))
        self.rng = rng or np.random.RandomState(42)
        self._mask: Optional[np.ndarray] = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        if not self.training or self.p <= 0.0:
            self._mask = None
            return x
        # 倒置 dropout：保留的神经元乘以 1/(1-p) 保持期望不变
        self._mask = (self.rng.rand(*x.shape) > self.p).astype(np.float64) / max(1.0 - self.p, 1e-8)
        return x * self._mask

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        if self._mask is None:
            return grad_output
        return grad_output * self._mask


class _ReLU(_Layer):
    """ReLU 激活"""

    def __init__(self) -> None:
        super().__init__()
        self._mask: Optional[np.ndarray] = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        self._mask = (x > 0).astype(np.float64)
        return x * self._mask

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        return grad_output * self._mask


class _GELU(_Layer):
    """GELU 激活（近似实现），适合小样本平滑梯度"""

    def __init__(self) -> None:
        super().__init__()
        self._x: Optional[np.ndarray] = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        self._x = x
        # GELU 近似: 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
        c = math.sqrt(2.0 / math.pi)
        inner = c * (x + 0.044715 * x ** 3)
        return 0.5 * x * (1.0 + np.tanh(inner))

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        x = self._x
        c = math.sqrt(2.0 / math.pi)
        inner = c * (x + 0.044715 * x ** 3)
        t = np.tanh(inner)
        # d/dx [0.5 * x * (1 + tanh(inner))]
        sech2 = 1.0 - t * t
        dinner = c * (1.0 + 3 * 0.044715 * x ** 2)
        dx = 0.5 * (1.0 + t) + 0.5 * x * sech2 * dinner
        return grad_output * dx


class _Conv1D(_Layer):
    """1D 卷积层（支持多通道）

    输入形状: (batch, in_channels, length)
    输出形状: (batch, out_channels, out_length)
    """

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int,
                 rng: np.random.RandomState, stride: int = 1, padding: int = 0) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        # 权重: (out_channels, in_channels, kernel_size)
        fan_in = in_channels * kernel_size
        self.params["W"] = _he_init(fan_in, out_channels, rng).T.reshape(out_channels, in_channels, kernel_size)
        self.params["b"] = np.zeros(out_channels, dtype=np.float64)
        self.grads["W"] = np.zeros_like(self.params["W"])
        self.grads["b"] = np.zeros_like(self.params["b"])
        self._cache: Optional[Dict[str, np.ndarray]] = None

    def _pad(self, x: np.ndarray) -> np.ndarray:
        if self.padding <= 0:
            return x
        return np.pad(x, ((0, 0), (0, 0), (self.padding, self.padding)), mode="constant")

    def forward(self, x: np.ndarray) -> np.ndarray:
        # x: (batch, in_channels, length)
        x_pad = self._pad(x)
        batch, in_ch, length = x_pad.shape
        out_length = (length - self.kernel_size) // self.stride + 1
        out = np.zeros((batch, self.out_channels, out_length), dtype=np.float64)
        # 使用 im2col 简化实现
        # 构造滑窗矩阵: (batch, in_ch * kernel_size, out_length)
        windows = np.zeros((batch, in_ch * self.kernel_size, out_length), dtype=np.float64)
        for i in range(out_length):
            start = i * self.stride
            seg = x_pad[:, :, start:start + self.kernel_size]  # (batch, in_ch, k)
            windows[:, :, i] = seg.reshape(batch, -1)
        # 权重 reshape: (out_channels, in_ch * k)
        W_mat = self.params["W"].reshape(self.out_channels, -1)  # (out_ch, in_ch*k)
        # 输出: (batch, out_ch, out_length)
        out = np.einsum("oc,bcl->bol", W_mat, windows) + self.params["b"][None, :, None]
        self._cache = {"windows": windows, "x_shape": x.shape, "x_pad_shape": x_pad.shape, "out_length": out_length}
        return out

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        # grad_output: (batch, out_ch, out_length)
        windows = self._cache["windows"]  # (batch, in_ch*k, out_length)
        batch = windows.shape[0]
        # 梯度对 W
        # dW: (out_ch, in_ch*k) = sum_batch grad_output[b] @ windows[b].T
        dW_mat = np.einsum("bol,bcl->oc", grad_output, windows)
        self.grads["W"] = dW_mat.reshape(self.params["W"].shape)
        self.grads["b"] = np.sum(grad_output, axis=(0, 2))
        # 梯度对输入
        W_mat = self.params["W"].reshape(self.out_channels, -1)  # (out_ch, in_ch*k)
        dwindows = np.einsum("oc,bol->bcl", W_mat, grad_output)  # (batch, in_ch*k, out_length)
        # 还原到 x_pad
        in_ch = self.in_channels
        dx_pad = np.zeros(self._cache["x_pad_shape"], dtype=np.float64)
        out_length = self._cache["out_length"]
        for i in range(out_length):
            start = i * self.stride
            seg_grad = dwindows[:, :, i].reshape(batch, in_ch, self.kernel_size)
            dx_pad[:, :, start:start + self.kernel_size] += seg_grad
        # 去除 padding
        if self.padding > 0:
            return dx_pad[:, :, self.padding:-self.padding]
        return dx_pad


class _MultiHeadSelfAttention(_Layer):
    """多头自注意力机制

    输入: (batch, seq_len, d_model)
    输出: (batch, seq_len, d_model)
    """

    def __init__(self, d_model: int, num_heads: int, rng: np.random.RandomState,
                 dropout: float = 0.1) -> None:
        super().__init__()
        assert d_model % num_heads == 0, "d_model 必须能被 num_heads 整除"
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_head = d_model // num_heads
        # Q/K/V 投影
        self.params["Wq"] = _xavier_init(d_model, d_model, rng)
        self.params["Wk"] = _xavier_init(d_model, d_model, rng)
        self.params["Wv"] = _xavier_init(d_model, d_model, rng)
        self.params["Wo"] = _xavier_init(d_model, d_model, rng)
        self.params["bq"] = np.zeros(d_model, dtype=np.float64)
        self.params["bk"] = np.zeros(d_model, dtype=np.float64)
        self.params["bv"] = np.zeros(d_model, dtype=np.float64)
        self.params["bo"] = np.zeros(d_model, dtype=np.float64)
        for k in ["Wq", "Wk", "Wv", "Wo", "bq", "bk", "bv", "bo"]:
            self.grads[k] = np.zeros_like(self.params[k])
        self.attn_dropout = dropout
        self.rng = rng
        self._cache: Optional[Dict[str, np.ndarray]] = None
        self._attn_mask_drop: Optional[np.ndarray] = None

    def _split_heads(self, x: np.ndarray) -> np.ndarray:
        # (batch, seq, d_model) -> (batch, num_heads, seq, d_head)
        batch, seq, _ = x.shape
        return x.reshape(batch, seq, self.num_heads, self.d_head).transpose(0, 2, 1, 3)

    def _merge_heads(self, x: np.ndarray) -> np.ndarray:
        # (batch, num_heads, seq, d_head) -> (batch, seq, d_model)
        batch, _, seq, _ = x.shape
        return x.transpose(0, 2, 1, 3).reshape(batch, seq, self.d_model)

    def forward(self, x: np.ndarray) -> np.ndarray:
        Q = x @ self.params["Wq"] + self.params["bq"]
        K = x @ self.params["Wk"] + self.params["bk"]
        V = x @ self.params["Wv"] + self.params["bv"]
        Qh = self._split_heads(Q)
        Kh = self._split_heads(K)
        Vh = self._split_heads(V)
        # 注意力分数: (batch, heads, seq, seq)
        scores = np.einsum("bhqd,bhkd->bhqk", Qh, Kh) / math.sqrt(self.d_head)
        attn = _softmax(scores, axis=-1)
        # 推理时不 dropout
        if self.training and self.attn_dropout > 0:
            keep = (self.rng.rand(*attn.shape) > self.attn_dropout).astype(np.float64) / max(1.0 - self.attn_dropout, 1e-8)
            attn = attn * keep
            self._attn_mask_drop = keep
        else:
            self._attn_mask_drop = None
        # 上下文: (batch, heads, seq, d_head)
        ctx = np.einsum("bhqk,bhkd->bhqd", attn, Vh)
        ctx = self._merge_heads(ctx)
        out = ctx @ self.params["Wo"] + self.params["bo"]
        self._cache = {"x": x, "Qh": Qh, "Kh": Kh, "Vh": Vh, "attn": attn, "ctx": ctx}
        return out

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        c = self._cache
        x = c["x"]
        batch = x.shape[0]
        # 对 Wo / bo（使用缓存的 ctx，forward 中已 merge_heads，直接使用）
        ctx_merged = c["ctx"]  # (batch, seq, d_model)
        self.grads["Wo"] = ctx_merged.reshape(-1, self.d_model).T @ grad_output.reshape(-1, self.d_model)
        self.grads["bo"] = np.sum(grad_output, axis=(0, 1))
        dctx = grad_output @ self.params["Wo"].T  # (batch, seq, d_model)
        dctx = self._split_heads(dctx)  # (batch, heads, seq, d_head)
        # attn dropout 反向
        if self._attn_mask_drop is not None:
            dctx_attn_factor = self._attn_mask_drop  # 对 attn 的梯度需乘以 keep
        else:
            dctx_attn_factor = np.ones_like(c["attn"])
        # 对 attn 和 Vh 的梯度
        # ctx = attn @ Vh -> dVh = attn^T @ dctx; dattn = dctx @ Vh^T
        dVh = np.einsum("bhqk,bhqd->bhkd", c["attn"], dctx)
        dattn = np.einsum("bhqd,bhkd->bhqk", dctx, c["Vh"]) * dctx_attn_factor
        # softmax 反向
        # dscores = attn * (dattn - sum(dattn * attn, axis=-1, keepdims))
        sum_dattn_attn = np.sum(dattn * c["attn"], axis=-1, keepdims=True)
        dscores = c["attn"] * (dattn - sum_dattn_attn) / math.sqrt(self.d_head)
        # 对 Qh / Kh
        dQh = np.einsum("bhqk,bhkd->bhqd", dscores, c["Kh"])
        dKh = np.einsum("bhqk,bhqd->bhkd", dscores, c["Qh"])
        dQ = self._merge_heads(dQh)
        dK = self._merge_heads(dKh)
        dV = self._merge_heads(dVh)
        # 对投影权重
        self.grads["Wq"] = x.reshape(-1, self.d_model).T @ dQ.reshape(-1, self.d_model)
        self.grads["Wk"] = x.reshape(-1, self.d_model).T @ dK.reshape(-1, self.d_model)
        self.grads["Wv"] = x.reshape(-1, self.d_model).T @ dV.reshape(-1, self.d_model)
        self.grads["bq"] = np.sum(dQ, axis=(0, 1))
        self.grads["bk"] = np.sum(dK, axis=(0, 1))
        self.grads["bv"] = np.sum(dV, axis=(0, 1))
        # 回传到 x
        dx = (dQ @ self.params["Wq"].T + dK @ self.params["Wk"].T + dV @ self.params["Wv"].T)
        return dx


class _ResidualBlock(_Layer):
    """残差连接块：LayerNorm -> Attention -> Dropout -> +残差 -> LayerNorm -> FFN -> Dropout -> +残差"""

    def __init__(self, d_model: int, num_heads: int, rng: np.random.RandomState,
                 ff_hidden: int = None, dropout: float = 0.1) -> None:
        super().__init__()
        self.attn = _MultiHeadSelfAttention(d_model, num_heads, rng, dropout=dropout)
        ff_hidden = ff_hidden or 4 * d_model
        self.ff1 = _Linear(d_model, ff_hidden, rng, init="he")
        self.ff_act = _GELU()
        self.ff2 = _Linear(ff_hidden, d_model, rng, init="he")
        self.norm1 = _LayerNorm(d_model)
        self.norm2 = _LayerNorm(d_model)
        # 使用独立的 Dropout 实例，避免 forward 时 mask 被后续调用覆盖
        self.drop1 = _Dropout(dropout, rng=rng)
        self.drop2 = _Dropout(dropout, rng=rng)
        self.drop3 = _Dropout(dropout, rng=rng)
        self._sub_layers: List[_Layer] = [
            self.attn, self.ff1, self.ff2, self.norm1, self.norm2,
            self.ff_act, self.drop1, self.drop2, self.drop3
        ]
        self._cache: Optional[Dict[str, np.ndarray]] = None

    def leaf_layers(self) -> List[_Layer]:
        """递归展开所有叶子层"""
        leaves: List[_Layer] = []
        for sub in self._sub_layers:
            leaves.extend(sub.leaf_layers())
        return leaves

    def train(self, mode: bool = True) -> "_ResidualBlock":
        """重写以将训练/推理模式传播到所有子层"""
        self.training = mode
        for sub in self._sub_layers:
            sub.train(mode)
        return self

    def forward(self, x: np.ndarray) -> np.ndarray:
        # Pre-LN 残差
        h = self.norm1.forward(x)
        a = self.attn.forward(h)
        a = self.drop1.forward(a)
        x1 = x + a
        h2 = self.norm2.forward(x1)
        h2 = self.ff1.forward(h2)
        h2 = self.ff_act.forward(h2)
        h2 = self.drop2.forward(h2)
        h2 = self.ff2.forward(h2)
        h2 = self.drop3.forward(h2)
        out = x1 + h2
        self._cache = {"x": x, "x1": x1}
        return out

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        # out = x1 + h2 -> dx1 = grad_output, dh2 = grad_output
        dh2 = self.drop3.backward(grad_output)
        dh2 = self.ff2.backward(dh2)
        dh2 = self.drop2.backward(dh2)
        dh2 = self.ff_act.backward(dh2)
        dh2 = self.ff1.backward(dh2)
        dnorm2 = self.norm2.backward(dh2)
        dx1 = grad_output + dnorm2
        # x1 = x + a -> dx = dx1, da = dx1
        da = self.drop1.backward(dx1)
        dnorm1 = self.attn.backward(da)
        dnorm1 = self.norm1.backward(dnorm1)
        dx = dx1 + dnorm1
        return dx


# =============================================================================
# 增强特征提取器
# =============================================================================
class EnhancedFeatureExtractor:
    """
    增强特征提取器
    ===============
    将原始序列（每期5个0-9数字的历史窗口）转换为多尺度深度特征。

    组件：
    1. 多尺度 1D 卷积（kernel=3/5/7 并行提取局部模式）
    2. 自注意力特征加权（突出关键时间步）
    3. 残差连接特征融合（避免信息丢失）
    4. 特征降维与选择（控制参数量，避免过拟合）

    输入：原始序列 (batch, seq_len, 5)（每期5个位置）
    输出：融合特征 (batch, d_model)
    """

    def __init__(self, seq_len: int = 30, d_model: int = 64,
                 num_heads: int = 4, dropout: float = 0.2,
                 rng: Optional[np.random.RandomState] = None) -> None:
        self.seq_len = seq_len
        self.d_model = d_model
        self.rng = rng or np.random.RandomState(42)
        # 输入嵌入：将 5 维原始输入映射到 d_model
        self.input_proj = _Linear(5, d_model, self.rng, init="xavier")
        # 多尺度卷积（kernel 3/5/7），输出拼接后投影回 d_model
        self.conv3 = _Conv1D(d_model, d_model // 2, 3, self.rng, padding=1)
        self.conv5 = _Conv1D(d_model, d_model // 2, 5, self.rng, padding=2)
        self.conv7 = _Conv1D(d_model, d_model // 2, 7, self.rng, padding=3)
        self.conv_fuse = _Linear(3 * (d_model // 2), d_model, self.rng, init="xavier")
        self.conv_act = _GELU()
        self.conv_norm = _LayerNorm(d_model)
        # 残差 Transformer 块
        self.res_block = _ResidualBlock(d_model, num_heads, self.rng, ff_hidden=2 * d_model, dropout=dropout)
        # 特征加权（自注意力打分）
        self.attn_scorer = _Linear(d_model, 1, self.rng, init="xavier")
        # 降维投影
        self.reduce_proj = _Linear(d_model * seq_len, d_model, self.rng, init="xavier")
        self.reduce_norm = _LayerNorm(d_model)
        self.drop = _Dropout(dropout, rng=self.rng)
        self._all_layers: List[_Layer] = [
            self.input_proj, self.conv3, self.conv5, self.conv7,
            self.conv_fuse, self.conv_act, self.conv_norm, self.res_block,
            self.attn_scorer, self.reduce_proj, self.reduce_norm, self.drop
        ]
        self._cache: Optional[Dict[str, np.ndarray]] = None

    def layers(self) -> List[_Layer]:
        """返回所有顶层子模块（用于 train/eval 模式切换等）"""
        return self._all_layers

    def leaf_layers(self) -> List[Tuple[str, _Layer]]:
        """递归展开所有叶子层，返回 (命名前缀, 叶子层) 列表

        命名前缀形如 `feat_{i}`，其中 i 为叶子层在展开序列中的全局序号。
        该方法保证参数与梯度的命名完全一致，便于优化器统一读写。
        """
        leaves: List[Tuple[str, _Layer]] = []
        idx = 0
        for layer in self._all_layers:
            for sub in layer.leaf_layers():
                leaves.append((f"feat_{idx}", sub))
                idx += 1
        return leaves

    def parameters(self) -> List[Tuple[str, np.ndarray]]:
        """返回所有参数（带叶子层命名前缀，递归展开残差块等容器层）"""
        result: List[Tuple[str, np.ndarray]] = []
        for prefix, layer in self.leaf_layers():
            for k, v in layer.params.items():
                result.append((f"{prefix}_{k}", v))
        return result

    def gradients(self) -> Dict[str, np.ndarray]:
        """返回所有梯度（命名与 parameters() 一致）"""
        grads: Dict[str, np.ndarray] = {}
        for prefix, layer in self.leaf_layers():
            for k, v in layer.grads.items():
                grads[f"{prefix}_{k}"] = v
        return grads

    def set_parameters_from_dict(self, named_params: Dict[str, np.ndarray]) -> None:
        """从命名参数字典回填各叶子层参数（用于 MAML 克隆、warm start）"""
        for prefix, layer in self.leaf_layers():
            for k in list(layer.params.keys()):
                key = f"{prefix}_{k}"
                if key in named_params:
                    layer.params[k] = named_params[key].copy()

    def set_gradients(self, named_grads: Dict[str, np.ndarray]) -> None:
        """从命名梯度字典回填各叶子层梯度"""
        for prefix, layer in self.leaf_layers():
            for k in list(layer.grads.keys()):
                key = f"{prefix}_{k}"
                if key in named_grads:
                    layer.grads[k] = named_grads[key]

    def train(self, mode: bool = True) -> "EnhancedFeatureExtractor":
        for layer in self._all_layers:
            layer.train(mode)
        return self

    def eval(self) -> "EnhancedFeatureExtractor":
        return self.train(False)

    def forward(self, x: np.ndarray) -> np.ndarray:
        """前向传播

        Args:
            x: (batch, seq_len, 5) 原始序列

        Returns:
            (batch, d_model) 融合特征
        """
        batch, seq, _ = x.shape
        # 输入嵌入
        h = self.input_proj.forward(x)  # (batch, seq, d_model)
        # 多尺度卷积：转成 (batch, d_model, seq)
        h_t = h.transpose(0, 2, 1)
        c3 = self.conv3.forward(h_t).transpose(0, 2, 1)  # (batch, seq, d/2)
        c5 = self.conv5.forward(h_t).transpose(0, 2, 1)
        c7 = self.conv7.forward(h_t).transpose(0, 2, 1)
        concat = np.concatenate([c3, c5, c7], axis=-1)  # (batch, seq, 3*d/2)
        fused = self.conv_fuse.forward(concat)  # (batch, seq, d)
        fused = self.conv_act.forward(fused)
        fused = fused + h  # 残差
        fused = self.conv_norm.forward(fused)
        # 残差 Transformer 块
        fused = self.res_block.forward(fused)
        # 自注意力加权：对每个时间步打分
        scores = self.attn_scorer.forward(fused)  # (batch, seq, 1)
        weights = _softmax(scores, axis=1)  # (batch, seq, 1)
        weighted = fused * weights  # 加权
        # 展平并降维
        flat = weighted.reshape(batch, -1)  # (batch, seq*d_model)
        out = self.reduce_proj.forward(flat)  # (batch, d_model)
        out = self.reduce_norm.forward(out)
        out = self.drop.forward(out)
        self._cache = {
            "x": x, "h": h, "h_t": h_t, "c3": c3, "c5": c5, "c7": c7,
            "concat": concat, "fused": fused, "weights": weights,
            "weighted": weighted, "flat": flat
        }
        return out

    def backward(self, grad_output: np.ndarray) -> np.ndarray:
        """反向传播，返回对输入的梯度

        Args:
            grad_output: (batch, d_model) 对输出特征的梯度

        Returns:
            (batch, seq_len, 5) 对输入序列的梯度
        """
        c = self._cache
        # 降维层反向（forward 顺序: reduce_proj -> reduce_norm -> drop）
        # backward 顺序: drop -> reduce_norm -> reduce_proj
        d_out = self.drop.backward(grad_output)               # (batch, d_model)
        d_after_proj = self.reduce_norm.backward(d_out)        # (batch, d_model)
        d_flat = self.reduce_proj.backward(d_after_proj)       # (batch, seq*d_model)
        # 还原到 (batch, seq, d)
        d_weighted = d_flat.reshape(c["weighted"].shape)
        # 加权反向: d_fused += d_weighted * weights; d_weights = sum(d_weighted * fused, axis=-1)
        d_fused = d_weighted * c["weights"]
        d_scores = np.sum(d_weighted * c["fused"], axis=-1, keepdims=True)
        # softmax 对 scores 反向
        # weights = softmax(scores, axis=1)
        sum_dw_w = np.sum(d_scores * c["weights"], axis=1, keepdims=True)
        d_scores_full = c["weights"] * (d_scores - sum_dw_w)
        d_fused = d_fused + self.attn_scorer.backward(d_scores_full)
        # 残差块反向
        d_fused = self.res_block.backward(d_fused)
        # conv_norm 反向 + 残差
        # forward: fused = conv_act(conv_fuse(concat)) + h; 然后 conv_norm
        # backward: conv_norm.backward 得到对 (conv_act_out + h) 的梯度 d_fused_pre
        d_fused_pre = self.conv_norm.backward(d_fused)
        # 拆分残差：梯度同时流向 conv_act_out 和 h
        d_conv_act_out = self.conv_act.backward(d_fused_pre)   # (batch, seq, d_model)
        d_concat = self.conv_fuse.backward(d_conv_act_out)     # (batch, seq, 3*d/2)
        d_h = d_fused_pre.copy()  # 残差分支到 h
        # 拆分 concat
        d_c3 = d_concat[..., :c["c3"].shape[-1]]
        d_c5 = d_concat[..., c["c3"].shape[-1]:c["c3"].shape[-1] + c["c5"].shape[-1]]
        d_c7 = d_concat[..., c["c3"].shape[-1] + c["c5"].shape[-1]:]
        # 卷积反向（转回 channel-first）
        d_h_t = (
            self.conv3.backward(d_c3.transpose(0, 2, 1)) +
            self.conv5.backward(d_c5.transpose(0, 2, 1)) +
            self.conv7.backward(d_c7.transpose(0, 2, 1))
        )
        d_h = d_h + d_h_t.transpose(0, 2, 1)
        # 输入投影反向
        d_x = self.input_proj.backward(d_h)
        return d_x


# =============================================================================
# 小样本增强网络
# =============================================================================
class SmallSampleEnhancedNet:
    """
    小样本增强网络架构
    ==================
    基于元学习（MAML）思想，融合多尺度卷积、自注意力、残差连接，
    支持多任务学习（5位置联合预测）与对比学习。

    结构：
        输入序列 (batch, seq_len, 5)
            -> EnhancedFeatureExtractor -> (batch, d_model)
            -> 5 个共享底座 + 各自预测头 -> (batch, 10) * 5

    MAML 支持：
        - `meta_forward` / `meta_backward`：内循环使用支持集快速适应
        - `meta_update`：外循环基于查询集更新元参数
    """

    def __init__(self, seq_len: int = 30, d_model: int = 64,
                 num_heads: int = 4, dropout: float = 0.2,
                 contrastive_temp: float = 0.1,
                 label_smoothing: float = 0.1,
                 rng: Optional[np.random.RandomState] = None) -> None:
        self.seq_len = seq_len
        self.d_model = d_model
        self.num_heads = num_heads
        self.contrastive_temp = contrastive_temp
        self.label_smoothing = label_smoothing
        self.rng = rng or np.random.RandomState(42)
        # 共享特征提取器
        self.feature_extractor = EnhancedFeatureExtractor(
            seq_len=seq_len, d_model=d_model, num_heads=num_heads,
            dropout=dropout, rng=self.rng
        )
        # 5 个位置的预测头（共享底座，独立头）
        self.heads: Dict[str, _Layer] = {}
        for pos in POSITIONS:
            head = _Linear(d_model, NUM_CLASSES, self.rng, init="xavier")
            self.heads[pos] = head
        # 对比学习投影头（将特征投影到对比空间）
        self.contrast_proj = _Linear(d_model, d_model, self.rng, init="xavier")
        self._all_head_layers: List[_Layer] = list(self.heads.values()) + [self.contrast_proj]
        self._cache: Optional[Dict[str, Any]] = None

    # ---------------- 参数管理 ----------------
    def parameters(self) -> Dict[str, np.ndarray]:
        """返回所有可训练参数的字典（用于优化器统一更新）"""
        params: Dict[str, np.ndarray] = {}
        for name, p in self.feature_extractor.parameters():
            params[name] = p
        for i, layer in enumerate(self._all_head_layers):
            for k, v in layer.params.items():
                params[f"head_{i}_{k}"] = v
        return params

    def gradients(self) -> Dict[str, np.ndarray]:
        """返回所有梯度"""
        grads: Dict[str, np.ndarray] = {}
        # 特征提取器：通过 leaf_layers 递归收集（含残差块内部子层）
        grads.update(self.feature_extractor.gradients())
        for i, layer in enumerate(self._all_head_layers):
            for k, v in layer.grads.items():
                grads[f"head_{i}_{k}"] = v
        return grads

    def set_parameters(self, params: Dict[str, np.ndarray]) -> None:
        """从字典加载参数（用于 MAML 内循环克隆、warm start）"""
        # 特征提取器：递归写入叶子层
        self.feature_extractor.set_parameters_from_dict(params)
        for i, layer in enumerate(self._all_head_layers):
            for k in list(layer.params.keys()):
                key = f"head_{i}_{k}"
                if key in params:
                    layer.params[k] = params[key].copy()

    def clone_params(self) -> Dict[str, np.ndarray]:
        """深拷贝当前参数（MAML 内循环使用）"""
        return {k: v.copy() for k, v in self.parameters().items()}

    # ---------------- 训练/推理模式 ----------------
    def train(self, mode: bool = True) -> "SmallSampleEnhancedNet":
        self.feature_extractor.train(mode)
        for layer in self._all_head_layers:
            layer.train(mode)
        return self

    def eval(self) -> "SmallSampleEnhancedNet":
        return self.train(False)

    # ---------------- 前向传播 ----------------
    def forward(self, x: np.ndarray) -> Tuple[Dict[str, np.ndarray], np.ndarray]:
        """前向传播

        Args:
            x: (batch, seq_len, 5) 输入序列

        Returns:
            logits_dict: 每个位置的 logits，{pos: (batch, 10)}
            features: (batch, d_model) 共享特征（用于对比学习）
        """
        features = self.feature_extractor.forward(x)
        logits_dict: Dict[str, np.ndarray] = {}
        for pos in POSITIONS:
            logits_dict[pos] = self.heads[pos].forward(features)
        # 对比投影
        contrast_features = self.contrast_proj.forward(features)
        # L2 归一化用于对比学习
        contrast_features = contrast_features / (np.linalg.norm(contrast_features, axis=-1, keepdims=True) + 1e-8)
        self._cache = {"x": x, "features": features, "logits_dict": logits_dict, "contrast": contrast_features}
        return logits_dict, features

    def forward_with_features(self, x: np.ndarray) -> Tuple[Dict[str, np.ndarray], np.ndarray, np.ndarray]:
        """前向传播，额外返回对比特征"""
        logits_dict, features = self.forward(x)
        return logits_dict, features, self._cache["contrast"]

    # ---------------- 损失函数 ----------------
    def compute_loss(self, logits_dict: Dict[str, np.ndarray],
                     labels: np.ndarray,
                     contrast_features: Optional[np.ndarray] = None,
                     lambda_contrast: float = 0.1) -> Tuple[float, Dict[str, float]]:
        """计算多任务损失 + 对比学习损失

        Args:
            logits_dict: 每个位置的 logits
            labels: (batch, 5) 真实标签，5 列对应 5 个位置
            contrast_features: (batch, d_model) 对比特征
            lambda_contrast: 对比损失权重

        Returns:
            total_loss: 总损失
            loss_components: 各项损失明细
        """
        batch = labels.shape[0]
        total_ce = 0.0
        components: Dict[str, float] = {}
        for i, pos in enumerate(POSITIONS):
            logits = logits_dict[pos]
            target = labels[:, i].astype(int)
            one_hot = _one_hot(target, NUM_CLASSES)
            smooth_target = _label_smooth(one_hot, self.label_smoothing)
            log_probs = _log_softmax(logits, axis=-1)
            ce = -np.sum(smooth_target * log_probs) / batch
            total_ce += ce
            components[f"ce_{pos}"] = float(ce)
        total_ce /= len(POSITIONS)
        components["ce_avg"] = float(total_ce)
        # 对比学习损失（InfoNCE）
        contrast_loss = 0.0
        if contrast_features is not None and lambda_contrast > 0:
            contrast_loss = self._info_nce_loss(contrast_features, labels)
            components["contrast"] = float(contrast_loss)
        total_loss = total_ce + lambda_contrast * contrast_loss
        components["total"] = float(total_loss)
        return float(total_loss), components

    def _info_nce_loss(self, features: np.ndarray, labels: np.ndarray) -> float:
        """InfoNCE 对比损失

        以"5个位置完全相同的样本对"为正样本对，不同为负样本对。
        简化版：使用每个样本的"标签签名"（5位数字拼接）作为正负判据。

        Args:
            features: (batch, d_model) 已 L2 归一化
            labels: (batch, 5)

        Returns:
            对比损失标量
        """
        batch = features.shape[0]
        if batch < 2:
            return 0.0
        # 相似度矩阵
        sim = features @ features.T / max(self.contrastive_temp, 1e-8)  # (batch, batch)
        # 构造正样本掩码：标签签名相同
        signatures = labels.dot(np.array([10000, 1000, 100, 10, 1]))
        pos_mask = (signatures[:, None] == signatures[None, :]).astype(np.float64)
        np.fill_diagonal(pos_mask, 0.0)  # 排除自身
        # 如果没有正样本对，退化为 0
        if pos_mask.sum() == 0:
            return 0.0
        # log-softmax over rows（排除自身）
        mask_self = np.eye(batch, dtype=np.float64)
        # 数值稳定
        sim_max = np.max(sim, axis=1, keepdims=True)
        exp_sim = np.exp(sim - sim_max)
        exp_sim = exp_sim * (1 - mask_self)  # 排除自身
        sum_exp = np.sum(exp_sim, axis=1, keepdims=True) + 1e-12
        log_prob = (sim - sim_max) - np.log(sum_exp + 1e-12)
        # 对每个 anchor，平均其所有正样本的 log_prob
        pos_count = np.sum(pos_mask, axis=1) + 1e-12
        per_anchor = np.sum(pos_mask * log_prob, axis=1) / pos_count
        # 只对有正样本的 anchor 计数
        valid = (np.sum(pos_mask, axis=1) > 0).astype(np.float64)
        loss = -np.sum(per_anchor * valid) / (np.sum(valid) + 1e-12)
        return float(loss)

    # ---------------- 反向传播 ----------------
    def backward(self, labels: np.ndarray,
                 lambda_contrast: float = 0.1) -> np.ndarray:
        """反向传播，将梯度写入各层 .grads

        Args:
            labels: (batch, 5)
            lambda_contrast: 对比损失权重

        Returns:
            对输入的梯度 (batch, seq_len, 5)
        """
        c = self._cache
        batch = labels.shape[0]
        features = c["features"]
        logits_dict = c["logits_dict"]
        contrast = c["contrast"]
        # 1. 分类损失反向
        d_features = np.zeros_like(features)
        for i, pos in enumerate(POSITIONS):
            logits = logits_dict[pos]
            target = labels[:, i].astype(int)
            one_hot = _one_hot(target, NUM_CLASSES)
            smooth_target = _label_smooth(one_hot, self.label_smoothing)
            probs = _softmax(logits, axis=-1)
            d_logits = (probs - smooth_target) / batch  # 交叉熵 + 标签平滑梯度
            d_features += self.heads[pos].backward(d_logits)
        d_features /= len(POSITIONS)
        # 2. 对比损失反向（InfoNCE）
        if lambda_contrast > 0 and batch >= 2:
            signatures = labels.dot(np.array([10000, 1000, 100, 10, 1]))
            pos_mask = (signatures[:, None] == signatures[None, :]).astype(np.float64)
            np.fill_diagonal(pos_mask, 0.0)
            if pos_mask.sum() > 0:
                sim = contrast @ contrast.T / max(self.contrastive_temp, 1e-8)
                mask_self = np.eye(batch, dtype=np.float64)
                sim_max = np.max(sim, axis=1, keepdims=True)
                exp_sim = np.exp(sim - sim_max) * (1 - mask_self)
                sum_exp = np.sum(exp_sim, axis=1, keepdims=True) + 1e-12
                # d_loss/d_sim
                pos_count = np.sum(pos_mask, axis=1) + 1e-12
                valid = (np.sum(pos_mask, axis=1) > 0).astype(np.float64)
                # dL/d_sim[i,j] = -pos_mask[i,j]/pos_count[i]/valid_count_normalized - (- exp_sim/sum_exp) * valid_norm
                # 简化推导后：
                d_sim = np.zeros_like(sim)
                # 对每个 i 的正样本 j: d_sim[i,j] -= pos_mask[i,j] / pos_count[i]
                # 对所有 j != i: d_sim[i,j] += exp_sim[i,j] / sum_exp[i]
                # 然后乘以 valid 归一化
                d_sim -= pos_mask / pos_count
                d_sim += exp_sim / sum_exp
                d_sim *= valid[:, None] / (np.sum(valid) + 1e-12)
                np.fill_diagonal(d_sim, 0.0)
                # sim = contrast @ contrast.T / temp
                # d_contrast = (d_sim + d_sim.T) @ contrast / temp
                d_contrast = (d_sim + d_sim.T) @ contrast / max(self.contrastive_temp, 1e-8)
                # contrast 已 L2 归一化，需对归一化前特征反传
                # contrast = z / ||z||, d_z = (d_contrast - contrast * (contrast·d_contrast)) / ||z||
                norm_z = np.linalg.norm(c["contrast"], axis=-1, keepdims=True) + 1e-8
                d_z = (d_contrast - contrast * np.sum(contrast * d_contrast, axis=-1, keepdims=True)) / norm_z
                d_features += lambda_contrast * self.contrast_proj.backward(d_z)
        # 3. 特征提取器反向
        d_x = self.feature_extractor.backward(d_features)
        return d_x

    # ---------------- MAML 元学习接口 ----------------
    def meta_forward(self, support_x: np.ndarray, support_y: np.ndarray,
                     inner_lr: float = 0.01, inner_steps: int = 1) -> Dict[str, np.ndarray]:
        """MAML 内循环：在支持集上做几步梯度下降，返回 task-specific 参数

        Args:
            support_x: (batch, seq_len, 5) 支持集输入
            support_y: (batch, 5) 支持集标签
            inner_lr: 内循环学习率
            inner_steps: 内循环步数

        Returns:
            适应后的参数字典
        """
        # 克隆元参数
        adapted_params = self.clone_params()
        original_params = self.clone_params()
        self.set_parameters(adapted_params)
        self.train(True)
        for step in range(inner_steps):
            logits_dict, features, contrast = self.forward_with_features(support_x)
            loss, _ = self.compute_loss(logits_dict, support_y, contrast, lambda_contrast=0.0)
            self.backward(support_y, lambda_contrast=0.0)
            # 内循环纯 SGD 更新（一阶 MAML）
            grads = self.gradients()
            new_params: Dict[str, np.ndarray] = {}
            for name, p in self.parameters().items():
                if name in grads:
                    new_params[name] = p - inner_lr * grads[name]
                else:
                    new_params[name] = p
            self.set_parameters(new_params)
            adapted_params = new_params
        # 恢复元参数（外循环再决定是否更新）
        self.set_parameters(original_params)
        return adapted_params

    def meta_update(self, query_x: np.ndarray, query_y: np.ndarray,
                    adapted_params: Dict[str, np.ndarray],
                    optimizer: "AdaptiveRegularizedOptimizer",
                    lambda_contrast: float = 0.1) -> float:
        """MAML 外循环：使用适应后的参数在查询集上计算元梯度并更新元参数

        Args:
            query_x: 查询集输入
            query_y: 查询集标签
            adapted_params: 内循环适应后的参数
            optimizer: 优化器
            lambda_contrast: 对比损失权重

        Returns:
            查询集损失
        """
        # 临时装入适应参数
        original_params = self.clone_params()
        self.set_parameters(adapted_params)
        self.train(True)
        logits_dict, features, contrast = self.forward_with_features(query_x)
        loss, _ = self.compute_loss(logits_dict, query_y, contrast, lambda_contrast=lambda_contrast)
        self.backward(query_y, lambda_contrast=lambda_contrast)
        meta_grads = self.gradients()
        # 恢复元参数，对其应用元梯度
        self.set_parameters(original_params)
        optimizer.step(self.parameters(), meta_grads)
        return float(loss)

    # ---------------- 预测接口（兼容 EnhancedPL5Predictor） ----------------
    def predict(self, features: np.ndarray,
                top_k: int = 8,
                use_uncertainty: bool = True) -> Dict[str, Dict[str, Any]]:
        """预测接口，返回与 EnhancedPL5Predictor 一致的概率分布格式

        Args:
            features: 输入特征。支持两种形式：
                - (seq_len, 5)：单样本序列
                - (5,)：单期5数字（自动扩展为 (1, 1, 5)）
                - (batch, seq_len, 5)：批量序列
            top_k: 返回 top-k 候选数字数量
            use_uncertainty: 是否计算不确定性（基于熵）

        Returns:
            {pos: {"top_k": List[int], "probabilities": List[float],
                   "uncertainty": float, "fallback": bool}}
        """
        # 输入归一化
        x = np.asarray(features, dtype=np.float64)
        if x.ndim == 1:
            # (5,) 单期 -> 扩展为 (1, 1, 5)
            x = x.reshape(1, 1, 5)
        elif x.ndim == 2:
            # (seq_len, 5) 单样本
            x = x.reshape(1, x.shape[0], 5)
        # 若 seq_len 不足，零填充；若超出，取最后 seq_len
        if x.shape[1] < self.seq_len:
            pad = np.zeros((x.shape[0], self.seq_len - x.shape[1], 5), dtype=np.float64)
            x = np.concatenate([pad, x], axis=1)
        elif x.shape[1] > self.seq_len:
            x = x[:, -self.seq_len:, :]
        self.eval()
        try:
            logits_dict, _ = self.forward(x)
        except Exception as e:
            logger.warning(f"[SmallSampleEnhancedNet] 预测前向失败，返回均匀分布: {e}")
            return {pos: {"top_k": list(range(min(top_k, NUM_CLASSES))),
                          "probabilities": [1.0 / min(top_k, NUM_CLASSES)] * min(top_k, NUM_CLASSES),
                          "uncertainty": float(np.log(NUM_CLASSES)),
                          "fallback": True} for pos in POSITIONS}
        result: Dict[str, Dict[str, Any]] = {}
        for pos in POSITIONS:
            logits = logits_dict[pos][0]  # 取第一个样本
            probs = _softmax(logits, axis=-1)
            k = min(top_k, NUM_CLASSES)
            top_idx = np.argsort(probs)[::-1][:k]
            top_probs = probs[top_idx]
            # 归一化 top-k 概率
            top_probs = top_probs / (np.sum(top_probs) + 1e-12)
            uncertainty = float(-np.sum(probs * np.log(probs + 1e-12))) if use_uncertainty else 0.0
            result[pos] = {
                "top_k": [int(i) for i in top_idx],
                "probabilities": [float(p) for p in top_probs],
                "uncertainty": uncertainty,
                "fallback": False,
            }
        return result

    def predict_proba(self, features: np.ndarray) -> Dict[str, np.ndarray]:
        """返回每个位置的完整概率分布（10维）"""
        x = np.asarray(features, dtype=np.float64)
        if x.ndim == 1:
            x = x.reshape(1, 1, 5)
        elif x.ndim == 2:
            x = x.reshape(1, x.shape[0], 5)
        if x.shape[1] < self.seq_len:
            pad = np.zeros((x.shape[0], self.seq_len - x.shape[1], 5), dtype=np.float64)
            x = np.concatenate([pad, x], axis=1)
        elif x.shape[1] > self.seq_len:
            x = x[:, -self.seq_len:, :]
        self.eval()
        logits_dict, _ = self.forward(x)
        return {pos: _softmax(logits_dict[pos][0], axis=-1) for pos in POSITIONS}


# =============================================================================
# 自适应正则化优化器
# =============================================================================
@dataclass
class OptimizerConfig:
    """优化器配置"""
    lr: float = 1e-3
    betas: Tuple[float, float] = (0.9, 0.999)
    eps: float = 1e-8
    weight_decay: float = 1e-4                 # L2 正则化
    adaptive_reg: bool = True                  # 自适应正则化（根据梯度方差调整）
    adaptive_reg_factor: float = 0.01          # 自适应正则化强度
    max_grad_norm: float = 1.0                 # 梯度裁剪阈值
    warmup_steps: int = 50                     # 学习率预热步数
    total_steps: int = 1000                    # 总训练步数（用于余弦退火）
    min_lr: float = 1e-6                       # 余弦退火最小学习率
    use_cosine_anneal: bool = True             # 是否使用余弦退火
    use_sam: bool = False                      # 是否启用 SAM（平坦最小值）
    sam_rho: float = 0.05                      # SAM 扰动半径
    noise_std: float = 0.0                     # 梯度噪声标准差（衰减型）
    noise_decay: float = 0.999                 # 噪声衰减率


class AdaptiveRegularizedOptimizer:
    """
    自适应正则化优化器
    ==================
    基于 Adam，集成以下小样本优化技术：

    1. **自适应正则化**：根据参数梯度方差动态调整 L2 强度，
       梯度方差大的参数加强正则化，方差小的参数减弱。
    2. **梯度裁剪**：按全局范数裁剪，防止梯度爆炸。
    3. **学习率预热 + 余弦退火**：warmup 阶段线性增长，
       之后余弦退火至 min_lr。
    4. **SAM（Sharpness-Aware Minimization）**：先在梯度方向扰动参数，
       再在扰动点计算真正梯度，寻找平坦最小值。
    5. **梯度噪声注入**：向梯度注入衰减型高斯噪声，帮助逃离 sharp minima。
    """

    def __init__(self, config: Optional[OptimizerConfig] = None,
                 rng: Optional[np.random.RandomState] = None) -> None:
        self.config = config or OptimizerConfig()
        self.rng = rng or np.random.RandomState(42)
        self.t: int = 0  # 全局步数
        # Adam 一阶/二阶矩缓存
        self.m: Dict[str, np.ndarray] = {}
        self.v: Dict[str, np.ndarray] = {}
        # 梯度方差滑动平均（自适应正则化）
        self.grad_var_ema: Dict[str, np.ndarray] = {}
        self.current_lr: float = self.config.lr

    def _init_state(self, params: Dict[str, np.ndarray]) -> None:
        for name, p in params.items():
            if name not in self.m:
                self.m[name] = np.zeros_like(p)
                self.v[name] = np.zeros_like(p)
                self.grad_var_ema[name] = np.zeros_like(p)

    def _compute_lr(self) -> float:
        """计算当前学习率（warmup + cosine anneal）"""
        cfg = self.config
        if self.t < cfg.warmup_steps:
            # 线性 warmup
            lr = cfg.lr * (self.t + 1) / max(cfg.warmup_steps, 1)
        elif cfg.use_cosine_anneal:
            # 余弦退火
            progress = (self.t - cfg.warmup_steps) / max(cfg.total_steps - cfg.warmup_steps, 1)
            progress = min(max(progress, 0.0), 1.0)
            lr = cfg.min_lr + 0.5 * (cfg.lr - cfg.min_lr) * (1.0 + math.cos(math.pi * progress))
        else:
            lr = cfg.lr
        self.current_lr = lr
        return lr

    def _clip_grad_norm(self, grads: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """全局梯度范数裁剪"""
        total_norm = math.sqrt(sum(float(np.sum(g * g)) for g in grads.values()))
        clip = self.config.max_grad_norm
        if total_norm > clip and total_norm > 0:
            scale = clip / total_norm
            return {k: v * scale for k, v in grads.items()}
        return grads

    def _inject_noise(self, grads: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """注入衰减型高斯噪声"""
        std = self.config.noise_std * (self.config.noise_decay ** self.t)
        if std <= 1e-8:
            return grads
        out: Dict[str, np.ndarray] = {}
        for k, v in grads.items():
            out[k] = v + self.rng.randn(*v.shape) * std
        return out

    def _get_adaptive_wd(self, name: str) -> np.ndarray:
        """获取每个参数的自适应权重衰减系数（按元素）"""
        cfg = self.config
        if not cfg.adaptive_reg:
            return np.array(cfg.weight_decay)
        var_norm = self.grad_var_ema[name] / (np.max(self.grad_var_ema[name]) + 1e-8)
        return cfg.weight_decay * (1.0 + cfg.adaptive_reg_factor * var_norm)

    def _sam_perturb(self, params: Dict[str, np.ndarray],
                     grads: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """SAM 第一步：在梯度方向扰动参数"""
        rho = self.config.sam_rho
        total_norm = math.sqrt(sum(float(np.sum(g * g)) for g in grads.values()))
        if total_norm < 1e-8:
            return {k: v.copy() for k, v in params.items()}
        scale = rho / total_norm
        perturbed: Dict[str, np.ndarray] = {}
        for k, p in params.items():
            perturbed[k] = p + scale * grads[k]
        return perturbed

    def step(self, params: Dict[str, np.ndarray],
             grads: Dict[str, np.ndarray],
             sam_second_step: bool = False) -> Dict[str, np.ndarray]:
        """执行一步参数更新

        Args:
            params: 当前参数
            grads: 梯度
            sam_second_step: 是否为 SAM 第二步（已经在扰动点计算了梯度）

        Returns:
            更新后的参数
        """
        self._init_state(params)
        cfg = self.config
        # SAM 第一步
        if cfg.use_sam and not sam_second_step:
            perturbed = self._sam_perturb(params, grads)
            # 调用方需要在扰动点重新计算梯度后再次调用 step(sam_second_step=True)
            # 这里直接返回扰动参数（不更新元参数），由调用方再次前向反向
            return perturbed
        # 梯度裁剪
        grads = self._clip_grad_norm(grads)
        # 梯度噪声
        grads = self._inject_noise(grads)
        # 更新梯度方差 EMA（用于自适应正则化）
        for name, g in grads.items():
            var = g * g
            beta = 0.99
            self.grad_var_ema[name] = beta * self.grad_var_ema[name] + (1 - beta) * var
        # Adam 更新
        self.t += 1
        lr = self._compute_lr()
        beta1, beta2 = cfg.betas
        new_params: Dict[str, np.ndarray] = {}
        for name, p in params.items():
            g = grads[name]
            self.m[name] = beta1 * self.m[name] + (1 - beta1) * g
            self.v[name] = beta2 * self.v[name] + (1 - beta2) * (g * g)
            m_hat = self.m[name] / (1 - beta1 ** self.t)
            v_hat = self.v[name] / (1 - beta2 ** self.t)
            # 自适应权重衰减（解耦，类似 AdamW）
            wd = self._get_adaptive_wd(name)
            update = lr * (m_hat / (np.sqrt(v_hat) + cfg.eps) + wd * p)
            new_params[name] = p - update
        return new_params

    def zero_grad(self) -> None:
        """重置优化器状态（不重置动量，仅语义对齐）"""
        pass

    def get_lr(self) -> float:
        return self.current_lr

    def state_dict(self) -> Dict[str, Any]:
        """导出优化器状态（用于 warm start）"""
        return {
            "t": self.t,
            "m": {k: v.copy() for k, v in self.m.items()},
            "v": {k: v.copy() for k, v in self.v.items()},
            "grad_var_ema": {k: v.copy() for k, v in self.grad_var_ema.items()},
            "current_lr": self.current_lr,
        }

    def load_state_dict(self, state: Dict[str, Any]) -> None:
        """加载优化器状态"""
        self.t = state.get("t", 0)
        self.m = {k: v.copy() for k, v in state.get("m", {}).items()}
        self.v = {k: v.copy() for k, v in state.get("v", {}).items()}
        self.grad_var_ema = {k: v.copy() for k, v in state.get("grad_var_ema", {}).items()}
        self.current_lr = state.get("current_lr", self.config.lr)


# =============================================================================
# 小样本数据增强器
# =============================================================================
class SmallSampleDataAugmentor:
    """
    小样本数据增强器
    ================
    针对排列5时序数据的增强策略组合：

    1. **时序窗口滑动增强**：在历史序列上滑动不同起点，生成多个子序列样本。
    2. **噪声注入增强**：向数字加入小幅高斯噪声（保持离散语义）。
    3. **Mixup 增强**：在特征空间线性插值两个样本及标签。
    4. **位置置换增强**：随机置换5个位置的顺序（注意：仅适用于对位置不敏感的任务）。
    """

    def __init__(self, rng: Optional[np.random.RandomState] = None,
                 noise_std: float = 0.3,
                 mixup_alpha: float = 0.2,
                 permute_prob: float = 0.1) -> None:
        self.rng = rng or np.random.RandomState(42)
        self.noise_std = noise_std
        self.mixup_alpha = mixup_alpha
        self.permute_prob = permute_prob

    def sliding_window(self, series: np.ndarray, window: int,
                       stride: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """时序窗口滑动增强

        Args:
            series: (T, 5) 完整历史序列
            window: 窗口长度（输入序列长度）
            stride: 滑动步长

        Returns:
            X: (N, window, 5) 输入窗口
            Y: (N, 5) 对应的下一期标签
        """
        T = series.shape[0]
        if T <= window:
            # 数据不足，零填充
            pad = np.zeros((window + 1 - T, 5), dtype=np.float64)
            series = np.concatenate([pad, series], axis=0)
            T = series.shape[0]
        X_list: List[np.ndarray] = []
        Y_list: List[np.ndarray] = []
        for start in range(0, T - window, stride):
            X_list.append(series[start:start + window])
            Y_list.append(series[start + window])
        if not X_list:
            X_list.append(series[:window])
            Y_list.append(series[window] if T > window else series[-1])
        return np.array(X_list, dtype=np.float64), np.array(Y_list, dtype=np.float64)

    def noise_inject(self, X: np.ndarray, Y: Optional[np.ndarray] = None
                     ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """噪声注入增强

        Args:
            X: (N, window, 5)
            Y: (N, 5) 可选

        Returns:
            增强后的 X, Y
        """
        noise = self.rng.randn(*X.shape) * self.noise_std
        X_aug = X + noise
        if Y is not None:
            # 标签也可加入轻微噪声（保持整数语义）
            Y_noise = self.rng.randn(*Y.shape) * self.noise_std * 0.5
            Y_aug = np.clip(np.round(Y + Y_noise), 0, NUM_CLASSES - 1).astype(np.float64)
            return X_aug, Y_aug
        return X_aug, None

    def mixup(self, X: np.ndarray, Y: np.ndarray,
              alpha: Optional[float] = None) -> Tuple[np.ndarray, np.ndarray]:
        """Mixup 增强

        Args:
            X: (N, window, 5)
            Y: (N, 5)
            alpha: Beta 分布参数

        Returns:
            混合后的 X, Y
        """
        alpha = alpha if alpha is not None else self.mixup_alpha
        if alpha <= 0:
            return X, Y
        N = X.shape[0]
        lam = self.rng.beta(alpha, alpha, size=(N, 1, 1))
        perm = self.rng.permutation(N)
        X_mix = lam * X + (1 - lam) * X[perm]
        # 标签 mixup：连续值混合（训练时用平滑标签）
        lam_y = lam[:, 0, 0].reshape(-1, 1)
        Y_mix = lam_y * Y + (1 - lam_y) * Y[perm]
        return X_mix, Y_mix

    def position_permute(self, X: np.ndarray, Y: Optional[np.ndarray] = None
                         ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """位置置换增强：随机置换5个位置维度

        注意：排列5中5个位置语义不同（万/千/百/十/个），但底层时序模式
        可能存在共性。以一定概率置换可作为一种正则化。

        Args:
            X: (N, window, 5)
            Y: (N, 5) 可选

        Returns:
            增强后的 X, Y
        """
        N = X.shape[0]
        X_aug = X.copy()
        Y_aug = Y.copy() if Y is not None else None
        for i in range(N):
            if self.rng.rand() < self.permute_prob:
                perm = self.rng.permutation(5)
                X_aug[i] = X[i][..., perm]
                if Y is not None:
                    Y_aug[i] = Y[i][perm]
        return X_aug, Y_aug

    def augment(self, X: np.ndarray, Y: np.ndarray,
                use_sliding: bool = False,
                use_noise: bool = True,
                use_mixup: bool = True,
                use_permute: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """组合多种增强策略

        Args:
            X: (N, window, 5)
            Y: (N, 5)
            use_sliding: 是否再做窗口滑动（通常 False，因为 X 已是窗口化）
            use_noise: 是否噪声注入
            use_mixup: 是否 mixup
            use_permute: 是否位置置换

        Returns:
            增强后的 X, Y（样本数可能翻倍）
        """
        aug_X_list: List[np.ndarray] = [X]
        aug_Y_list: List[np.ndarray] = [Y]
        if use_noise:
            Xn, Yn = self.noise_inject(X, Y)
            aug_X_list.append(Xn)
            aug_Y_list.append(Yn)
        if use_mixup:
            Xm, Ym = self.mixup(X, Y)
            aug_X_list.append(Xm)
            aug_Y_list.append(Ym)
        if use_permute:
            Xp, Yp = self.position_permute(X, Y)
            aug_X_list.append(Xp)
            aug_Y_list.append(Yp)
        return np.concatenate(aug_X_list, axis=0), np.concatenate(aug_Y_list, axis=0)


# =============================================================================
# 小样本训练器
# =============================================================================
@dataclass
class TrainingHistory:
    """训练历史记录"""
    epochs: List[int] = field(default_factory=list)
    train_loss: List[float] = field(default_factory=list)
    val_loss: List[float] = field(default_factory=list)
    val_accuracy: List[float] = field(default_factory=list)
    learning_rates: List[float] = field(default_factory=list)
    best_val_loss: float = float("inf")
    best_epoch: int = 0
    stopped_early: bool = False
    fold_metrics: List[Dict[str, float]] = field(default_factory=list)


class SmallSampleTrainer:
    """
    小样本训练器
    ============
    集成 K 折交叉验证、早停、模型集成、增量学习（warm start）。

    训练流程：
        1. 数据增强（可选）
        2. K 折交叉验证，每折训练一个模型
        3. 每折内：mini-batch 训练 + 验证集早停
        4. 多折模型集成为最终模型
        5. 支持从已有参数 warm start 继续训练
    """

    def __init__(self, net: SmallSampleEnhancedNet,
                 optimizer: Optional[AdaptiveRegularizedOptimizer] = None,
                 augmentor: Optional[SmallSampleDataAugmentor] = None,
                 rng: Optional[np.random.RandomState] = None) -> None:
        self.net = net
        self.optimizer = optimizer or AdaptiveRegularizedOptimizer(rng=rng)
        self.augmentor = augmentor or SmallSampleDataAugmentor(rng=rng)
        self.rng = rng or np.random.RandomState(42)
        self.history = TrainingHistory()
        # 集成模型参数（K 折产生）
        self.ensemble_params: List[Dict[str, np.ndarray]] = []
        self.is_trained: bool = False

    def _accuracy(self, logits_dict: Dict[str, np.ndarray], labels: np.ndarray) -> float:
        """计算多任务准确率（5位置平均 top-1）"""
        correct = 0
        total = 0
        for i, pos in enumerate(POSITIONS):
            preds = np.argmax(logits_dict[pos], axis=-1)
            correct += int(np.sum(preds == labels[:, i].astype(int)))
            total += labels.shape[0]
        return correct / max(total, 1)

    def _mini_batches(self, X: np.ndarray, Y: np.ndarray,
                      batch_size: int, shuffle: bool = True) -> List[Tuple[np.ndarray, np.ndarray]]:
        """生成 mini-batch"""
        N = X.shape[0]
        idx = self.rng.permutation(N) if shuffle else np.arange(N)
        batches: List[Tuple[np.ndarray, np.ndarray]] = []
        for start in range(0, N, batch_size):
            end = start + batch_size
            bi = idx[start:end]
            batches.append((X[bi], Y[bi]))
        return batches

    def train_fold(self, X_train: np.ndarray, Y_train: np.ndarray,
                   X_val: np.ndarray, Y_val: np.ndarray,
                   epochs: int = 50, batch_size: int = 32,
                   lambda_contrast: float = 0.1,
                   patience: int = 10,
                   use_augmentation: bool = True,
                   warm_start_params: Optional[Dict[str, np.ndarray]] = None,
                   verbose: bool = True) -> Dict[str, Any]:
        """训练单折

        Args:
            X_train: (N, seq_len, 5)
            Y_train: (N, 5)
            X_val: 验证集
            Y_val: 验证集标签
            epochs: 训练轮数
            batch_size: 批大小
            lambda_contrast: 对比损失权重
            patience: 早停耐心值
            use_augmentation: 是否使用数据增强
            warm_start_params: warm start 参数
            verbose: 是否打印日志

        Returns:
            训练结果字典
        """
        # warm start
        if warm_start_params is not None:
            self.net.set_parameters(warm_start_params)
        # 配置优化器总步数
        self.optimizer.config.total_steps = epochs * max(1, (X_train.shape[0] + batch_size - 1) // batch_size)
        # 早停
        best_val_loss = float("inf")
        best_params: Optional[Dict[str, np.ndarray]] = None
        no_improve = 0
        fold_history: Dict[str, List[float]] = {"train_loss": [], "val_loss": [], "val_acc": [], "lr": []}

        self.net.train(True)
        for epoch in range(epochs):
            # 数据增强
            if use_augmentation:
                X_aug, Y_aug = self.augmentor.augment(X_train, Y_train)
            else:
                X_aug, Y_aug = X_train, Y_train
            # mini-batch 训练
            batches = self._mini_batches(X_aug, Y_aug, batch_size, shuffle=True)
            epoch_loss = 0.0
            n_batches = 0
            for bx, by in batches:
                logits_dict, features, contrast = self.net.forward_with_features(bx)
                loss, _ = self.net.compute_loss(logits_dict, by, contrast, lambda_contrast=lambda_contrast)
                self.net.backward(by, lambda_contrast=lambda_contrast)
                params = self.net.parameters()
                grads = self.net.gradients()
                # SAM 两步
                if self.optimizer.config.use_sam:
                    perturbed = self.optimizer.step(params, grads, sam_second_step=False)
                    self.net.set_parameters(perturbed)
                    logits_dict2, features2, contrast2 = self.net.forward_with_features(bx)
                    self.net.backward(by, lambda_contrast=lambda_contrast)
                    grads2 = self.net.gradients()
                    # 恢复原参数再做第二步更新
                    self.net.set_parameters(params)
                    new_params = self.optimizer.step(params, grads2, sam_second_step=True)
                else:
                    new_params = self.optimizer.step(params, grads)
                self.net.set_parameters(new_params)
                epoch_loss += loss
                n_batches += 1
            avg_train_loss = epoch_loss / max(n_batches, 1)
            # 验证
            self.net.eval()
            val_logits, _, val_contrast = self.net.forward_with_features(X_val)
            val_loss, _ = self.net.compute_loss(val_logits, Y_val, val_contrast, lambda_contrast=0.0)
            val_acc = self._accuracy(val_logits, Y_val)
            self.net.train(True)
            # 记录
            fold_history["train_loss"].append(float(avg_train_loss))
            fold_history["val_loss"].append(float(val_loss))
            fold_history["val_acc"].append(float(val_acc))
            fold_history["lr"].append(float(self.optimizer.get_lr()))
            self.history.epochs.append(epoch)
            self.history.train_loss.append(float(avg_train_loss))
            self.history.val_loss.append(float(val_loss))
            self.history.val_accuracy.append(float(val_acc))
            self.history.learning_rates.append(float(self.optimizer.get_lr()))
            if verbose:
                logger.info(
                    f"[Fold] epoch={epoch+1}/{epochs} "
                    f"train_loss={avg_train_loss:.4f} val_loss={val_loss:.4f} "
                    f"val_acc={val_acc:.4f} lr={self.optimizer.get_lr():.6f}"
                )
            # 早停
            if val_loss < best_val_loss - 1e-6:
                best_val_loss = val_loss
                best_params = self.net.clone_params()
                no_improve = 0
                self.history.best_val_loss = best_val_loss
                self.history.best_epoch = epoch
            else:
                no_improve += 1
                if no_improve >= patience:
                    if verbose:
                        logger.info(f"[Fold] 早停于 epoch={epoch+1}, 最佳 val_loss={best_val_loss:.4f}")
                    self.history.stopped_early = True
                    break
        # 恢复最佳参数
        if best_params is not None:
            self.net.set_parameters(best_params)
        return {
            "best_val_loss": best_val_loss,
            "best_params": best_params or self.net.clone_params(),
            "history": fold_history,
        }

    def k_fold_train(self, X: np.ndarray, Y: np.ndarray,
                     k: int = 5, epochs: int = 50, batch_size: int = 32,
                     lambda_contrast: float = 0.1, patience: int = 10,
                     use_augmentation: bool = True,
                     warm_start_params: Optional[Dict[str, np.ndarray]] = None,
                     verbose: bool = True) -> Dict[str, Any]:
        """K 折交叉验证训练，产生 K 个模型集成

        Args:
            X: (N, seq_len, 5)
            Y: (N, 5)
            k: 折数
            epochs: 每折训练轮数
            batch_size: 批大小
            lambda_contrast: 对比损失权重
            patience: 早停耐心值
            use_augmentation: 是否数据增强
            warm_start_params: warm start 参数（用于增量学习）
            verbose: 是否打印日志

        Returns:
            训练汇总结果
        """
        N = X.shape[0]
        k = min(k, N)
        indices = self.rng.permutation(N)
        fold_size = N // k
        self.ensemble_params = []
        meta_params_template = warm_start_params or self.net.clone_params()
        fold_results: List[Dict[str, Any]] = []
        for fold in range(k):
            if verbose:
                logger.info(f"=== K-Fold {fold+1}/{k} ===")
            start = fold * fold_size
            end = start + fold_size if fold < k - 1 else N
            val_idx = indices[start:end]
            train_idx = np.concatenate([indices[:start], indices[end:]])
            X_tr, Y_tr = X[train_idx], Y[train_idx]
            X_va, Y_va = X[val_idx], Y[val_idx]
            # 每折重新初始化优化器状态，但 warm start 元参数
            self.optimizer = AdaptiveRegularizedOptimizer(
                config=self.optimizer.config, rng=self.rng
            )
            result = self.train_fold(
                X_tr, Y_tr, X_va, Y_va,
                epochs=epochs, batch_size=batch_size,
                lambda_contrast=lambda_contrast, patience=patience,
                use_augmentation=use_augmentation,
                warm_start_params=meta_params_template,
                verbose=verbose,
            )
            self.ensemble_params.append(result["best_params"])
            fold_results.append(result)
            self.history.fold_metrics.append({"fold": fold, "val_loss": result["best_val_loss"]})
            # 更新 warm start 模板为当前最佳（增量学习）
            meta_params_template = result["best_params"]
        # 将最后一折（或最佳折）参数装入网络作为默认模型
        # 选择验证损失最低的折
        best_fold_idx = int(np.argmin([r["best_val_loss"] for r in fold_results]))
        self.net.set_parameters(self.ensemble_params[best_fold_idx])
        self.is_trained = True
        avg_val_loss = float(np.mean([r["best_val_loss"] for r in fold_results]))
        if verbose:
            logger.info(f"=== K-Fold 完成, 平均 val_loss={avg_val_loss:.4f}, 最佳折={best_fold_idx} ===")
        return {
            "fold_results": fold_results,
            "avg_val_loss": avg_val_loss,
            "best_fold": best_fold_idx,
            "ensemble_size": len(self.ensemble_params),
        }

    def predict_ensemble(self, features: np.ndarray, top_k: int = 8,
                         use_uncertainty: bool = True) -> Dict[str, Dict[str, Any]]:
        """集成预测：对所有折模型预测取平均

        Args:
            features: 输入特征
            top_k: top-k 数量
            use_uncertainty: 是否计算不确定性

        Returns:
            与 predict 一致的格式
        """
        if not self.ensemble_params:
            return self.net.predict(features, top_k=top_k, use_uncertainty=use_uncertainty)
        # 输入归一化
        x = np.asarray(features, dtype=np.float64)
        if x.ndim == 1:
            x = x.reshape(1, 1, 5)
        elif x.ndim == 2:
            x = x.reshape(1, x.shape[0], 5)
        if x.shape[1] < self.net.seq_len:
            pad = np.zeros((x.shape[0], self.net.seq_len - x.shape[1], 5), dtype=np.float64)
            x = np.concatenate([pad, x], axis=1)
        elif x.shape[1] > self.net.seq_len:
            x = x[:, -self.net.seq_len:, :]
        # 各模型概率平均
        prob_sums: Dict[str, np.ndarray] = {pos: np.zeros(NUM_CLASSES) for pos in POSITIONS}
        original_params = self.net.clone_params()
        self.net.eval()
        # x 当前为 (1, seq_len, 5)，取第 0 个样本的 (seq_len, 5) 传给 predict_proba
        single_seq = x[0]  # (seq_len, 5)
        for params in self.ensemble_params:
            self.net.set_parameters(params)
            proba = self.net.predict_proba(single_seq)
            for pos in POSITIONS:
                prob_sums[pos] += proba[pos]
        # 恢复
        self.net.set_parameters(original_params)
        result: Dict[str, Dict[str, Any]] = {}
        for pos in POSITIONS:
            avg_probs = prob_sums[pos] / len(self.ensemble_params)
            k = min(top_k, NUM_CLASSES)
            top_idx = np.argsort(avg_probs)[::-1][:k]
            top_probs = avg_probs[top_idx]
            top_probs = top_probs / (np.sum(top_probs) + 1e-12)
            uncertainty = float(-np.sum(avg_probs * np.log(avg_probs + 1e-12))) if use_uncertainty else 0.0
            result[pos] = {
                "top_k": [int(i) for i in top_idx],
                "probabilities": [float(p) for p in top_probs],
                "uncertainty": uncertainty,
                "fallback": False,
            }
        return result

    def save(self, path: str) -> None:
        """保存训练器状态（含集成参数）"""
        state = {
            "net_params": self.net.clone_params(),
            "ensemble_params": self.ensemble_params,
            "optimizer_state": self.optimizer.state_dict(),
            "history": {
                "epochs": self.history.epochs,
                "train_loss": self.history.train_loss,
                "val_loss": self.history.val_loss,
                "val_accuracy": self.history.val_accuracy,
                "learning_rates": self.history.learning_rates,
                "best_val_loss": self.history.best_val_loss,
                "best_epoch": self.history.best_epoch,
                "stopped_early": self.history.stopped_early,
                "fold_metrics": self.history.fold_metrics,
            },
            "is_trained": self.is_trained,
            "net_config": {
                "seq_len": self.net.seq_len,
                "d_model": self.net.d_model,
                "num_heads": self.net.num_heads,
                "contrastive_temp": self.net.contrastive_temp,
                "label_smoothing": self.net.label_smoothing,
            },
        }
        with open(path, "wb") as f:
            pickle.dump(state, f)
        logger.info(f"[SmallSampleTrainer] 已保存到 {path}")

    def load(self, path: str) -> None:
        """加载训练器状态（warm start / 增量学习）"""
        with open(path, "rb") as f:
            state = pickle.load(f)
        self.net.set_parameters(state["net_params"])
        self.ensemble_params = state.get("ensemble_params", [])
        self.optimizer.load_state_dict(state.get("optimizer_state", {}))
        h = state.get("history", {})
        self.history.epochs = h.get("epochs", [])
        self.history.train_loss = h.get("train_loss", [])
        self.history.val_loss = h.get("val_loss", [])
        self.history.val_accuracy = h.get("val_accuracy", [])
        self.history.learning_rates = h.get("learning_rates", [])
        self.history.best_val_loss = h.get("best_val_loss", float("inf"))
        self.history.best_epoch = h.get("best_epoch", 0)
        self.history.stopped_early = h.get("stopped_early", False)
        self.history.fold_metrics = h.get("fold_metrics", [])
        self.is_trained = state.get("is_trained", False)
        logger.info(f"[SmallSampleTrainer] 已从 {path} 加载 (trained={self.is_trained})")


# =============================================================================
# 工厂函数
# =============================================================================
def create_small_sample_pipeline(seq_len: int = 30,
                                 d_model: int = 64,
                                 rng: Optional[np.random.RandomState] = None,
                                 optimizer_config: Optional[OptimizerConfig] = None
                                 ) -> Tuple[SmallSampleEnhancedNet,
                                            AdaptiveRegularizedOptimizer,
                                            SmallSampleDataAugmentor,
                                            SmallSampleTrainer]:
    """一键创建小样本训练流水线

    Args:
        seq_len: 输入序列长度
        d_model: 模型隐藏维度
        rng: 随机数生成器
        optimizer_config: 优化器配置

    Returns:
        (net, optimizer, augmentor, trainer)
    """
    rng = rng or np.random.RandomState(42)
    net = SmallSampleEnhancedNet(seq_len=seq_len, d_model=d_model, rng=rng)
    optimizer = AdaptiveRegularizedOptimizer(config=optimizer_config, rng=rng)
    augmentor = SmallSampleDataAugmentor(rng=rng)
    trainer = SmallSampleTrainer(net=net, optimizer=optimizer, augmentor=augmentor, rng=rng)
    return net, optimizer, augmentor, trainer


# =============================================================================
# 模块自检（不依赖外部数据）
# =============================================================================
def _self_check() -> None:
    """模块自检：构造小数据测试前向/反向/训练流程是否跑通"""
    rng = np.random.RandomState(0)
    net = SmallSampleEnhancedNet(seq_len=10, d_model=32, num_heads=4, rng=rng)
    optimizer = AdaptiveRegularizedOptimizer(
        config=OptimizerConfig(lr=1e-3, warmup_steps=2, total_steps=20, use_sam=False, noise_std=0.0),
        rng=rng,
    )
    trainer = SmallSampleTrainer(net, optimizer, rng=rng)
    # 构造假数据
    N = 32
    X = rng.randint(0, NUM_CLASSES, size=(N, 10, 5)).astype(np.float64)
    Y = rng.randint(0, NUM_CLASSES, size=(N, 5)).astype(np.float64)
    # 前向
    logits_dict, features, contrast = net.forward_with_features(X)
    assert logits_dict["wan"].shape == (N, NUM_CLASSES)
    assert features.shape == (N, 32)
    # 损失
    loss, comps = net.compute_loss(logits_dict, Y, contrast, lambda_contrast=0.1)
    assert np.isfinite(loss), f"loss 非有限: {loss}"
    # 反向
    net.backward(Y, lambda_contrast=0.1)
    grads = net.gradients()
    assert all(np.all(np.isfinite(g)) for g in grads.values()), "梯度含 NaN/Inf"
    # 单折训练 2 轮
    result = trainer.train_fold(X[:24], Y[:24], X[24:], Y[24:],
                                epochs=2, batch_size=8, patience=5,
                                use_augmentation=True, verbose=False)
    assert "best_val_loss" in result
    # 预测
    pred = trainer.predict_ensemble(X[0, :, :], top_k=5)
    assert set(pred.keys()) == set(POSITIONS)
    for pos in POSITIONS:
        assert len(pred[pos]["top_k"]) == 5
        assert abs(sum(pred[pos]["probabilities"]) - 1.0) < 1e-3
    logger.info("[self_check] 通过")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_check()
