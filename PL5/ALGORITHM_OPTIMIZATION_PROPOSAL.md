# PL5 智能预测系统核心算法优化方案

## 文档信息
- **版本**: v1.0
- **日期**: 2026-05-20
- **基于**: Code Wiki v1.0

---

## 一、当前算法架构分析

### 1.1 现有算法体系

```
┌─────────────────────────────────────────────────────────────────┐
│                    多模型融合预测架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐                                               │
│  │   输入特征   │ ──→ 76+ 维特征向量                              │
│  └──────┬──────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    子模型预测层                           │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │ Stacking │ │   HMM    │ │  Copula  │ │   BSTS   │   │    │
│  │  │ (0.40)   │ │  (0.15)  │ │  (0.25)  │ │  (自适应) │   │    │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │    │
│  └───────┼────────────┼────────────┼────────────┼──────────┘    │
│          │            │            │            │                 │
│          └────────────┴─────┬──────┴────────────┘                 │
│                             ▼                                      │
│                    ┌─────────────────┐                            │
│                    │   权重融合层     │                            │
│                    │  (固定权重/R L) │                            │
│                    └────────┬────────┘                            │
│                             │                                      │
│                             ▼                                      │
│                    ┌─────────────────┐                            │
│                    │   最终Top-8预测 │                            │
│                    └─────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 现有算法优缺点分析

| 模块 | 优点 | 缺点 |
|------|------|------|
| **Stacking** | 集成多种基学习器，泛化能力强 | 基学习器多样性不足，元特征工程较简单 |
| **HMM** | 能捕捉时序转移规律 | 状态数固定，未考虑多位置联合 |
| **Copula** | 建模多维联合分布 | 仅用gaussian类型，相关性捕捉有限 |
| **BSTS** | 分解趋势/季节性/异常 | 后验采样计算开销大 |
| **RL优化器** | 自适应调整权重 | 收敛慢，状态空间设计冗余 |

---

## 二、特征工程优化方案

### 2.1 问题诊断

**当前问题**:
1. **特征冗余**: 76+特征中存在大量相关性高的特征
2. **时间窗口固定**: 未能自适应调整窗口大小
3. **特征交互缺失**: 未建模特征间的非线性交互
4. **分布信息利用不足**: 仅用均值/标准差统计量

### 2.2 优化方案

#### 方案1: 自适应特征选择 (优先级: 高)

```python
# 建议新增: AdaptiveFeatureSelector
class AdaptiveFeatureSelector:
    """
    基于在线学习的多阶段特征选择器
    
    改进点:
    1. 使用L1正则化在线学习进行动态特征筛选
    2. 特征重要性衰减机制
    3. 特征组内选择 (避免同组特征冗余)
    """
    
    def __init__(self, decay_factor: float = 0.95, min_importance: float = 0.01):
        self.decay_factor = decay_factor
        self.min_importance = min_importance
        self.feature_scores = {}
        self.group_constraints = {
            'fibonacci': 3,   # 每组最多选3个
            'entropy': 2,
            'markov': 2,
            'fourier': 2,
            # ...
        }
    
    def update(self, feature_importance: Dict[str, float], period: int):
        """更新特征重要性分数"""
        for feat, score in feature_importance.items():
            if feat not in self.feature_scores:
                self.feature_scores[feat] = 0.0
            
            # 指数加权更新
            self.feature_scores[feat] = (
                self.decay_factor * self.feature_scores[feat] +
                (1 - self.decay_factor) * score
            )
```

#### 方案2: 深度特征交互 (优先级: 中)

```python
# 建议新增: FeatureInteractionExtractor
class FeatureInteractionExtractor:
    """
    建模特征间的二阶/高阶交互
    
    改进点:
    1. 使用FM (Factorization Machine) 捕捉二阶交互
    2. 位置交叉特征: wan_qian_sum, bai_shi_diff
    3. 跨期交互: lag_1_wan * lag_2_qian
    """
    
    def extract_cross_features(self, df: pd.DataFrame) -> pd.DataFrame:
        features = {}
        
        # 位置交叉
        for pos1, pos2 in [('wan', 'qian'), ('bai', 'shi'), ('shi', 'ge')]:
            features[f'{pos1}_{pos2}_sum'] = df[pos1] + df[pos2]
            features[f'{pos1}_{pos2}_diff'] = df[pos1] - df[pos2]
            features[f'{pos1}_{pos2}_product'] = df[pos1] * df[pos2]
        
        # 跨期交叉
        for lag in [1, 2, 3]:
            for pos in ['wan', 'qian', 'bai']:
                col = f'lag_{lag}_{pos}'
                if col in df.columns and pos in df.columns:
                    features[f'{col}_ratio_{pos}'] = df[col] / (df[pos] + 1)
        
        # 数字频率交叉
        features['digit_freq_interaction'] = (
            df.get('wan_digit_freq', 0) * df.get('qian_digit_freq', 0)
        )
        
        return pd.DataFrame(features)
```

#### 方案3: 分布感知特征 (优先级: 中)

```python
# 建议新增: DistributionAwareFeatures
class DistributionAwareFeatures:
    """
    基于分布统计的增强特征
    
    改进点:
    1. 分位数特征 (非参数化)
    2. 分布距离特征 (KL散度、Wasserstein距离)
    3. 分布矩特征 (偏度、峰度)
    """
    
    def compute_distribution_features(self, series: pd.Series, 
                                     windows: List[int] = [10, 20, 50]) -> pd.DataFrame:
        features = {}
        
        for w in windows:
            if len(series) >= w:
                window = series.iloc[-w:]
                
                # 分位数特征
                for q in [0.1, 0.25, 0.5, 0.75, 0.9]:
                    features[f'quantile_{q}_w{w}'] = window.quantile(q)
                
                # 分布矩
                features[f'skewness_w{w}'] = window.skew()
                features[f'kurtosis_w{w}'] = window.kurtosis()
                
                # 极值相关
                features[f'range_w{w}'] = window.max() - window.min()
                features[f'midrange_w{w}'] = (window.max() + window.min()) / 2
        
        return pd.DataFrame(features)
```

---

## 三、预测模型优化方案

### 3.1 Stacking模型优化

#### 当前问题
1. 基学习器种类有限 (RF/LGBM/XGB)
2. 元学习器选择简单
3. 未考虑类别不平衡

#### 优化方案

```python
# 建议优化: EnhancedStackingEnsemble
class EnhancedStackingEnsemble:
    """
    增强版Stacking集成
    
    改进点:
    1. 多样性驱动的基学习器选择
    2. 加权元学习器集成
    3. 层次化Stacking
    """
    
    def fit_with_diversity(self, X, y, feature_cols):
        # 1. 多样性驱动的基学习器池
        base_pool = {
            # 树模型族
            'rf': RandomForestClassifier(n_estimators=50, max_depth=8),
            'et': ExtraTreesClassifier(n_estimators=50, max_depth=8),
            'lgbm': LGBMClassifier(n_estimators=50, max_depth=6, verbose=-1),
            'xgb': XGBClassifier(n_estimators=50, max_depth=6, use_label_encoder=False),
            
            # 线性模型族 (增加多样性)
            'lr': LogisticRegression(C=1.0, max_iter=1000),
            'ridge': RidgeClassifier(alpha=1.0),
            
            # KNN族
            'knn_5': KNeighborsClassifier(n_neighbors=5),
            'knn_10': KNeighborsClassifier(n_neighbors=10),
            
            # 朴素贝叶斯
            'nb': GaussianNB(),
        }
        
        # 2. 选择多样化子集 (避免相似模型)
        selected_models = self._select_diverse_models(base_pool, X, y, n_select=4)
        
        # 3. 层次化Stacking
        # Level 1: 基学习器
        level1_meta = self._generate_meta_features(X, y, selected_models)
        
        # Level 2: 元学习器集成
        meta_models = [
            LogisticRegression(C=1.0),
            RidgeClassifier(alpha=1.0),
            SVC(probability=True)
        ]
        
        level2_preds = []
        for meta_clf in meta_models:
            level2_preds.append(meta_clf.fit_predict_proba(level1_meta, y))
        
        # 4. 加权集成
        final_proba = np.average(level2_preds, axis=0, weights=self._learn_weights())
        
        return final_proba
```

### 3.2 HMM模型优化

#### 当前问题
1. 状态数固定或简单选择
2. 仅用单变量HMM
3. 未考虑时变转移矩阵

#### 优化方案

```python
# 建议优化: VariationalHMM
class VariationalHMM:
    """
    变分推断HMM
    
    改进点:
    1. 贝叶斯变分推断，自动确定最优状态数
    2. 时变转移矩阵 (考虑时间依赖)
    3. 多位置联合建模
    """
    
    def __init__(self, n_states_range=(2, 8), learning_rate=0.01):
        self.n_states_range = n_states_range
        self.learning_rate = learning_rate
        self.transition_matrix_history = []
    
    def fit_variable_states(self, sequences: Dict[str, np.ndarray]):
        """
        变分推断自动选择最优状态数
        
        原理: 使用变分下界 (ELBO) 作为模型选择准则
        ELBO = E[log p(X,Z|θ)] - E[log q(Z|φ)]
        
        优势:
        - 避免过拟合 (自动选择状态数)
        - 计算效率高 (无需交叉验证)
        """
        best_elbo = float('-inf')
        best_n_states = 4
        
        for n_states in range(self.n_states_range[0], self.n_states_range[1] + 1):
            elbo = self._compute_elbo(sequences, n_states)
            if elbo > best_elbo:
                best_elbo = elbo
                best_n_states = n_states
        
        return self._fit_with_states(sequences, best_n_states)
    
    def fit_time_varying(self, sequences: np.ndarray, time_windows: List[int]):
        """
        时变转移矩阵
        
        假设: 转移概率随时间缓慢变化
        P(Z_t | Z_{t-1}) = softmax(W_t * Z_{t-1} + b)
        """
        n_times = len(sequences) // min(time_windows)
        
        self.transition_matrices = []
        for i in range(n_times):
            start_idx = i * min(time_windows)
            end_idx = (i + 1) * min(time_windows)
            window_data = sequences[start_idx:end_idx]
            
            # 估计当前窗口的转移矩阵
            A_t = self._estimate_transition_matrix(window_data)
            self.transition_matrices.append(A_t)
```

### 3.3 Copula模型优化

#### 当前问题
1. 仅支持Gaussian Copula
2. 未考虑尾部依赖
3. 静态参数估计

#### 优化方案

```python
# 建议优化: TailAwareCopula
class TailAwareCopula:
    """
    尾部敏感Copula模型
    
    改进点:
    1. 多Copula混合 (Gaussian + t + Gumbel)
    2. 尾部依赖建模 (极值理论)
    3. 动态参数更新
    """
    
    def __init__(self):
        self.copula_types = ['gaussian', 't', 'gumbel', 'clayton']
        self.mixture_weights = None
    
    def fit_mixture(self, data: np.ndarray):
        """
        混合Copula估计
        
        原理: 不同Copula适合建模不同类型的相关性
        - Gaussian: 线性相关
        - t-Copula: 中度尾部相关
        - Gumbel: 上尾相关
        - Clayton: 下尾相关
        
        混合权重通过EM算法估计
        """
        from scipy.optimize import minimize
        
        def em_update(data, weights, copulas):
            # E步: 计算每个样本属于各Copula的后验概率
            log_liks = np.array([c.log_likelihood(data) for c in copulas])
            posterior = np.exp(log_liks - log_liks.max(axis=0))
            posterior = posterior / posterior.sum(axis=0)
            
            # M步: 更新权重和参数
            new_weights = posterior.mean(axis=1)
            for i, c in enumerate(copulas):
                c.fit(data, weights=posterior[i])
            
            return new_weights, copulas
        
        # 初始化
        copulas = [self._init_copula(t) for t in self.copula_types]
        weights = np.ones(len(copulas)) / len(copulas)
        
        # EM迭代
        for _ in range(50):
            weights, copulas = em_update(data, weights, copulas)
        
        self.mixture_weights = weights
        self.copulas = copulas
    
    def predict_with_tail_aware(self, marginals: np.ndarray) -> np.ndarray:
        """
        带尾部加权的预测
        """
        joint_probs = np.zeros(10)
        
        for i, (copula, weight) in enumerate(zip(self.copulas, self.mixture_weights)):
            # 计算当前Copula的联合概率
            prob = copula.predict(marginals)
            
            # 尾部放大: 当概率较低时增加权重
            tail_boost = 1.0 + np.exp(-prob * 10)
            prob = prob * tail_boost
            
            joint_probs += weight * prob
        
        return joint_probs / joint_probs.sum()
```

---

## 四、融合策略优化方案

### 4.1 当前权重融合问题

**现有方法**:
- 固定权重 (不够灵活)
- RL自适应 (收敛慢，128维状态空间冗余)

### 4.2 优化方案

#### 方案1: 上下文感知权重 (优先级: 高)

```python
# 建议优化: ContextAwareWeightFusion
class ContextAwareWeightFusion:
    """
    上下文感知的动态权重融合
    
    改进点:
    1. 简化RL状态空间 (128→32维)
    2. 上下文感知的权重预测
    3. 置信度加权的集成
    """
    
    def __init__(self, n_positions=5):
        self.n_positions = n_positions
        self.model_weights = {
            'stacking': 0.35,
            'hmm': 0.15,
            'copula': 0.25,
            'bayesian': 0.15,
            'mamba': 0.10
        }
        
        # 上下文编码器 (简化版)
        self.context_encoder = self._build_context_encoder()
        
        # 权重预测器
        self.weight_predictor = self._build_weight_predictor()
    
    def _build_context_encoder(self):
        """
        上下文编码器: 32维紧凑状态表示
        
        输入: [特征统计(10), 模型置信度(5), 近期表现(10), 趋势(7)]
        输出: 32维上下文向量
        """
        return tf.keras.Sequential([
            tf.keras.layers.Dense(64, activation='relu', input_shape=(32,)),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(32, activation='relu'),
        ])
    
    def _build_weight_predictor(self):
        """
        权重预测器: 基于上下文的动态权重生成
        
        输出: 5个模型的权重 (归一化)
        """
        return tf.keras.Sequential([
            tf.keras.layers.Dense(32, activation='relu', input_shape=(32,)),
            tf.keras.layers.Dense(16, activation='relu'),
            tf.keras.layers.Dense(5, activation='softmax')  # 输出权重
        ])
    
    def get_weights(self, context_features: np.ndarray) -> Dict[str, float]:
        """
        基于上下文预测动态权重
        """
        # 编码上下文
        context_vec = self.context_encoder.predict(context_features.reshape(1, -1))[0]
        
        # 预测权重
        raw_weights = self.weight_predictor.predict(context_vec.reshape(1, -1))[0]
        
        # 归一化并映射到模型
        model_names = ['stacking', 'hmm', 'copula', 'bayesian', 'mamba']
        return dict(zip(model_names, raw_weights))
    
    def fuse_predictions(self, 
                         predictions: Dict[str, np.ndarray],
                         context_features: np.ndarray) -> np.ndarray:
        """
        上下文感知的概率融合
        """
        weights = self.get_weights(context_features)
        
        # 置信度加权
        fused = np.zeros(10)
        total_confidence = 0.0
        
        for model_name, proba in predictions.items():
            confidence = np.max(proba) - np.entropy(proba) / np.log(10)
            adjusted_weight = weights.get(model_name, 0.2) * confidence
            fused += adjusted_weight * proba
            total_confidence += adjusted_weight
        
        return fused / total_confidence
```

#### 方案2: 在线学习权重优化 (优先级: 中)

```python
# 建议优化: OnlineWeightOptimizer
class OnlineWeightOptimizer:
    """
    基于Thompson Sampling的在线权重优化
    
    改进点:
    1. 每期更新，无需离线训练
    2. 探索-利用平衡
    3. 置信区间估计
    """
    
    def __init__(self, model_names, alpha_prior=1.0, beta_prior=1.0):
        self.model_names = model_names
        self.prior = {'alpha': alpha_prior, 'beta': beta_prior}
        self.posterior = {m: {'alpha': alpha_prior, 'beta': beta_prior} 
                         for m in model_names}
    
    def update(self, hit_results: Dict[str, bool]):
        """
        根据预测结果更新后验分布
        
        使用Beta-Bernoulli共轭:
        Prior: Beta(α, β)
        Likelihood: Bernoulli(p)
        Posterior: Beta(α + hits, β + misses)
        """
        for model, hit in hit_results.items():
            if model in self.posterior:
                self.posterior[model]['alpha'] += hit
                self.posterior[model]['beta'] += not hit
    
    def sample_weights(self, n_samples=1000) -> np.ndarray:
        """
        Thompson Sampling采样
        
        每个模型从其后验Beta分布采样，
        归一化得到权重向量
        """
        samples = np.zeros((n_samples, len(self.model_names)))
        
        for i, model in enumerate(self.model_names):
            alpha = self.posterior[model]['alpha']
            beta = self.posterior[model]['beta']
            samples[:, i] = np.random.beta(alpha, beta, n_samples)
        
        # 归一化
        samples = samples / samples.sum(axis=1, keepdims=True)
        return samples.mean(axis=0)  # 返回平均权重
    
    def get_confidence_interval(self, model: str, confidence=0.95) -> Tuple[float, float]:
        """
        获取权重的置信区间
        """
        alpha = self.posterior[model]['alpha']
        beta = self.posterior[model]['beta']
        
        lower = alpha / (alpha + beta)
        # Beta分布置信区间近似
        margin = 1.96 * np.sqrt(alpha * beta / ((alpha + beta)**2 * (alpha + beta + 1)))
        
        return max(0, lower - margin), min(1, lower + margin)
```

#### 方案3: 对抗训练增强 (优先级: 中)

```python
# 建议新增: AdversarialEnsemble
class AdversarialEnsemble:
    """
    对抗训练增强的集成
    
    改进点:
    1. 对抗样本增强
    2. 鲁棒性加权
    3. 分布外检测
    """
    
    def generate_adversarial_samples(self, X, y, epsilon=0.1):
        """
        生成对抗样本 (FGSM)
        
        原理: 在输入特征上加微扰动，
        使模型预测改变但真实标签不变
        """
        # 使用简单梯度扰动
        perturbation = epsilon * np.sign(np.random.randn(*X.shape))
        X_adv = X + perturbation
        return np.clip(X_adv, X.min(), X.max())
    
    def fit_robust(self, X, y, n_adv_iterations=5):
        """
        对抗训练
        
        每次迭代:
        1. 在干净样本上训练
        2. 生成对抗样本
        3. 在对抗样本上评估
        4. 更新模型
        """
        for iteration in range(n_adv_iterations):
            # 正常训练
            self.model.fit(X, y)
            
            # 生成对抗样本
            X_adv = self.generate_adversarial_samples(X, y)
            
            # 对抗评估
            adv_accuracy = self.model.evaluate(X_adv, y)
            
            # 检测分布偏移
            if adv_accuracy < 0.3:  # 对抗样本准确率过低
                self._trigger_retraining()
```

---

## 五、实施路线图

### 5.1 优先级矩阵

| 优化项 | 预期收益 | 实现复杂度 | 优先级 |
|--------|----------|-----------|--------|
| 自适应特征选择 | 高 | 中 | ⭐⭐⭐ |
| 上下文感知权重 | 高 | 高 | ⭐⭐⭐ |
| 尾部敏感Copula | 中 | 中 | ⭐⭐ |
| 对抗训练增强 | 中 | 高 | ⭐⭐ |
| 变分推断HMM | 中 | 高 | ⭐ |
| 多样性Stacking | 中 | 低 | ⭐⭐ |

### 5.2 实施阶段

```
Phase 1 (Week 1-2): 特征工程优化
├── AdaptiveFeatureSelector
├── FeatureInteractionExtractor
└── DistributionAwareFeatures

Phase 2 (Week 3-4): 融合策略优化
├── ContextAwareWeightFusion
├── OnlineWeightOptimizer
└── 简化RL状态空间

Phase 3 (Week 5-6): 模型层优化
├── EnhancedStackingEnsemble
├── TailAwareCopula
└── VariationalHMM

Phase 4 (Week 7-8): 测试与调优
├── A/B测试框架
├── 在线评估系统
└── 参数自动调优
```

### 5.3 评估指标

| 指标 | 当前基线 | 目标提升 | 测量方法 |
|------|----------|---------|----------|
| Top-3准确率 | ~15% | +2-3% | 回测验证 |
| Top-5准确率 | ~30% | +3-5% | 回测验证 |
| 模型稳定性 | - | +20% | 滚动窗口方差 |
| 预测延迟 | <5s | <3s | 实际测量 |

---

## 六、风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 过度拟合 | 高 | 高 | 增加正则化、使用交叉验证 |
| 计算开销增加 | 中 | 中 | 使用缓存、减少迭代次数 |
| 收敛不稳定 | 中 | 高 | 预训练权重warm-up |
| 历史模式偏移 | 高 | 中 | 漂移检测触发重训练 |

---

## 七、附录

### A. 参考算法

1. **Stacking**: Wolpert, D. H. (1992). Stacked generalization
2. **Copula**: Sklar, A. (1959). Fonctions de répartition à n dimensions
3. **Thompson Sampling**: Thompson, W. R. (1933). On the likelihood that one unknown probability exceeds another
4. **变分推断**: Blei, D. M. et al. (2017). Variational Inference: A Review for Statisticians

### B. 快速验证建议

```python
# 1. 离线回测对比
def backtest_compare(original_predictor, optimized_predictor, test_data):
    # 使用相同测试集评估
    # 记录Top-3/5准确率
    pass

# 2. A/B在线测试
def online_ab_test(rollout_percentage=0.1):
    # 10%流量使用新模型
    # 监控点击率、转化率等
    pass
```

### C. 建议配置文件更新

```yaml
# model_config_v2.yaml
optimization:
  feature_selection:
    enabled: true
    decay_factor: 0.95
    min_importance: 0.01
    
  fusion_strategy:
    type: "context_aware"  # options: fixed, rl, context_aware
    state_dim: 32
    confidence_weighted: true
    
  ensemble:
    diversity_threshold: 0.7
    use_adversarial: false
```
