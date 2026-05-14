"""
符号回归特征发现
通过数学表达式生成发现新特征
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple, Any
import logging
import random
from pathlib import Path
import pickle
from sklearn.ensemble import RandomForestRegressor
from sklearn.base import BaseEstimator

logger = logging.getLogger(__name__)


class ExpressionNode:
    """表达式树节点"""

    OPERATORS = {
        "add": {"func": lambda x, y: x + y, "arity": 2},
        "sub": {"func": lambda x, y: x - y, "arity": 2},
        "mul": {"func": lambda x, y: x * y, "arity": 2},
        "div": {"func": lambda x, y: x / (y + 1e-10), "arity": 2},
        "pow": {
            "func": lambda x, y: np.power(
                np.abs(x) + 1e-10, np.clip(y, 0.1, 3)
            ),
            "arity": 2,
        },
        "sin": {"func": lambda x: np.sin(x), "arity": 1},
        "cos": {"func": lambda x: np.cos(x), "arity": 1},
        "exp": {"func": lambda x: np.exp(np.clip(x, -10, 10)), "arity": 1},
        "log": {"func": lambda x: np.log(np.abs(x) + 1e-10), "arity": 1},
        "sqrt": {"func": lambda x: np.sqrt(np.abs(x) + 1e-10), "arity": 1},
        "abs": {"func": lambda x: np.abs(x), "arity": 1},
    }

    def __init__(self, node_type: str, value: Any = None):
        self.node_type = node_type
        self.value = value
        self.left: Optional["ExpressionNode"] = None
        self.right: Optional["ExpressionNode"] = None

    def evaluate(self, X: pd.DataFrame) -> np.ndarray:
        """评估表达式"""
        if self.node_type == "variable":
            return X[self.value].values
        elif self.node_type == "constant":
            return np.full(len(X), self.value)
        elif self.node_type == "operator":
            op = self.OPERATORS[self.value]
            if op["arity"] == 1:
                left_val = self.left.evaluate(X)
                return op["func"](left_val)
            else:
                left_val = self.left.evaluate(X)
                right_val = self.right.evaluate(X)
                return op["func"](left_val, right_val)
        else:
            raise ValueError(f"未知节点类型: {self.node_type}")

    def depth(self) -> int:
        """计算树深度"""
        if self.node_type in ["variable", "constant"]:
            return 1
        left_depth = self.left.depth() if self.left else 0
        right_depth = self.right.depth() if self.right else 0
        return 1 + max(left_depth, right_depth)

    def size(self) -> int:
        """计算树节点数"""
        if self.node_type in ["variable", "constant"]:
            return 1
        left_size = self.left.size() if self.left else 0
        right_size = self.right.size() if self.right else 0
        return 1 + left_size + right_size

    def clone(self) -> "ExpressionNode":
        """克隆节点"""
        node = ExpressionNode(self.node_type, self.value)
        if self.left:
            node.left = self.left.clone()
        if self.right:
            node.right = self.right.clone()
        return node

    def __repr__(self) -> str:
        if self.node_type == "variable":
            return f"Var({self.value})"
        elif self.node_type == "constant":
            return f"Const({self.value:.2f})"
        else:
            return f"Op({self.value})"


class SymbolicFeatureDiscoverer:
    """符号回归特征发现器"""

    def __init__(
        self,
        population_size: int = 100,
        max_depth: int = 4,
        mutation_rate: float = 0.2,
        crossover_rate: float = 0.7,
        elitism_rate: float = 0.1,
        max_generations: int = 50,
        random_state: int = 42,
    ):
        self.population_size = population_size
        self.max_depth = max_depth
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism_rate = elitism_rate
        self.max_generations = max_generations
        self.random_state = random_state

        self.population: List[ExpressionNode] = []
        self.best_expression: Optional[ExpressionNode] = None
        self.best_fitness = -float("inf")
        self.fitness_history: List[float] = []
        self.feature_names: List[str] = []

        random.seed(random_state)
        np.random.seed(random_state)

    def _generate_random_expression(
        self,
        feature_names: List[str],
        depth: int = 0,
        max_depth: Optional[int] = None,
    ) -> ExpressionNode:
        """生成随机表达式"""
        if max_depth is None:
            max_depth = self.max_depth

        if depth >= max_depth or random.random() < 0.3:
            if random.random() < 0.7:
                var_name = random.choice(feature_names)
                return ExpressionNode("variable", var_name)
            else:
                const = random.uniform(-5, 5)
                return ExpressionNode("constant", const)
        else:
            ops = list(ExpressionNode.OPERATORS.keys())
            op_name = random.choice(ops)
            op = ExpressionNode.OPERATORS[op_name]
            node = ExpressionNode("operator", op_name)

            node.left = self._generate_random_expression(
                feature_names, depth + 1, max_depth
            )
            if op["arity"] == 2:
                node.right = self._generate_random_expression(
                    feature_names, depth + 1, max_depth
                )

            return node

    def _initialize_population(
        self, feature_names: List[str]
    ) -> List[ExpressionNode]:
        """初始化种群"""
        population = []
        for _ in range(self.population_size):
            expr = self._generate_random_expression(feature_names)
            population.append(expr)
        return population

    def _fitness_function(
        self,
        expression: ExpressionNode,
        X: pd.DataFrame,
        y: pd.Series,
        model: Optional[BaseEstimator] = None,
    ) -> float:
        """适应度函数 - 评估新特征的预测能力"""
        try:
            feature_values = expression.evaluate(X)

            if np.any(np.isnan(feature_values)) or np.any(
                np.isinf(feature_values)
            ):
                return -float("inf")

            feature_values = (feature_values - feature_values.mean()) / (
                feature_values.std() + 1e-10
            )

            if model is None:
                model = RandomForestRegressor(
                    n_estimators=30,
                    max_depth=4,
                    random_state=self.random_state,
                    n_jobs=-1,
                )

            X_feature = feature_values.reshape(-1, 1)
            from sklearn.model_selection import cross_val_score

            scores = cross_val_score(
                model, X_feature, y, cv=3, scoring="r2", n_jobs=-1
            )

            complexity_penalty = expression.size() * 0.01

            return scores.mean() - complexity_penalty
        except Exception as e:
            logger.debug(f"表达式评估失败: {e}")
            return -float("inf")

    def _evaluate_population(
        self,
        population: List[ExpressionNode],
        X: pd.DataFrame,
        y: pd.Series,
        model: Optional[BaseEstimator] = None,
    ) -> List[float]:
        """评估种群"""
        fitnesses = []
        for expr in population:
            fitness = self._fitness_function(expr, X, y, model)
            fitnesses.append(fitness)
        return fitnesses

    def _selection(
        self, population: List[ExpressionNode], fitnesses: List[float]
    ) -> ExpressionNode:
        """选择操作"""
        valid_indices = [
            i for i, f in enumerate(fitnesses) if f != -float("inf")
        ]
        if not valid_indices:
            return random.choice(population)

        valid_fitnesses = [fitnesses[i] for i in valid_indices]
        min_fitness = min(valid_fitnesses)
        adjusted_fitnesses = [f - min_fitness + 1e-10 for f in valid_fitnesses]
        total_fitness = sum(adjusted_fitnesses)

        pick = random.uniform(0, total_fitness)
        current = 0.0
        for idx, fitness in zip(valid_indices, adjusted_fitnesses):
            current += fitness
            if current >= pick:
                return population[idx]

        return population[valid_indices[-1]]

    def _crossover(
        self, parent1: ExpressionNode, parent2: ExpressionNode
    ) -> ExpressionNode:
        """交叉操作 - 子树交换"""
        if random.random() > self.crossover_rate:
            return parent1.clone()

        child = parent1.clone()

        nodes1 = self._collect_nodes(child)
        nodes2 = self._collect_nodes(parent2)

        if nodes1 and nodes2:
            node1 = random.choice(nodes1)
            node2 = random.choice(nodes2)

            node1.node_type = node2.node_type
            node1.value = node2.value
            node1.left = node2.left.clone() if node2.left else None
            node1.right = node2.right.clone() if node2.right else None

        return child

    def _collect_nodes(self, node: ExpressionNode) -> List[ExpressionNode]:
        """收集所有节点"""
        nodes = [node]
        if node.left:
            nodes.extend(self._collect_nodes(node.left))
        if node.right:
            nodes.extend(self._collect_nodes(node.right))
        return nodes

    def _mutation(self, expression: ExpressionNode, feature_names: List[str]):
        """变异操作"""
        if random.random() > self.mutation_rate:
            return

        nodes = self._collect_nodes(expression)
        if not nodes:
            return

        target_node = random.choice(nodes)

        if target_node.node_type == "variable":
            target_node.value = random.choice(feature_names)
        elif target_node.node_type == "constant":
            target_node.value = random.uniform(-5, 5)
        else:
            ops = list(ExpressionNode.OPERATORS.keys())
            target_node.value = random.choice(ops)
            op = ExpressionNode.OPERATORS[target_node.value]

            if op["arity"] == 1:
                if target_node.right is not None:
                    if target_node.left is None:
                        target_node.left = target_node.right
                    target_node.right = None
            else:
                if target_node.right is None:
                    target_node.right = self._generate_random_expression(
                        feature_names, max_depth=2
                    )

    def _simplify_expression(
        self, expression: ExpressionNode
    ) -> ExpressionNode:
        """简化表达式"""
        if expression.node_type in ["variable", "constant"]:
            return expression

        if expression.left:
            expression.left = self._simplify_expression(expression.left)
        if expression.right:
            expression.right = self._simplify_expression(expression.right)

        if expression.value == "add":
            if (
                expression.left.node_type == "constant"
                and expression.left.value == 0
            ):
                return expression.right
            if (
                expression.right.node_type == "constant"
                and expression.right.value == 0
            ):
                return expression.left
        elif expression.value == "mul":
            if (
                expression.left.node_type == "constant"
                and expression.left.value == 1
            ):
                return expression.right
            if (
                expression.right.node_type == "constant"
                and expression.right.value == 1
            ):
                return expression.left
            if (
                expression.left.node_type == "constant"
                and expression.left.value == 0
            ) or (
                expression.right.node_type == "constant"
                and expression.right.value == 0
            ):
                return ExpressionNode("constant", 0.0)

        return expression

    def discover(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_cols: Optional[List[str]] = None,
        model: Optional[BaseEstimator] = None,
        num_features: int = 5,
        early_stopping_patience: int = 10,
        verbose: bool = True,
    ) -> List[Tuple[str, ExpressionNode, float]]:
        """
        发现新特征

        Args:
            X: 特征数据
            y: 目标变量
            feature_cols: 可选的特征列，默认使用所有数值列
            model: 可选的模型用于评估
            num_features: 要发现的特征数量
            early_stopping_patience: 早停耐心值
            verbose: 是否打印进度

        Returns:
            发现的特征列表，格式为 (特征名, 表达式, 适应度)
        """
        if feature_cols is None:
            feature_cols = [
                col
                for col in X.columns
                if np.issubdtype(X[col].dtype, np.number)
            ]

        self.feature_names = feature_cols
        discovered_features = []

        for feature_idx in range(num_features):
            if verbose:
                logger.info(
                    f"发现第 {feature_idx + 1}/{num_features} 个特征..."
                )

            self.population = self._initialize_population(feature_cols)
            fitnesses = self._evaluate_population(self.population, X, y, model)

            self.fitness_history = []
            patience_counter = 0
            best_fitness = -float("inf")

            for generation in range(self.max_generations):
                current_best_idx = np.argmax(fitnesses)
                current_best_fitness = fitnesses[current_best_idx]
                self.fitness_history.append(current_best_fitness)

                if current_best_fitness > best_fitness:
                    best_fitness = current_best_fitness
                    self.best_expression = self._simplify_expression(
                        self.population[current_best_idx].clone()
                    )
                    self.best_fitness = best_fitness
                    patience_counter = 0
                else:
                    patience_counter += 1

                if verbose:
                    logger.info(
                        f"  Generation {generation + 1}/{self.max_generations} - "
                        f"Best Fitness: {best_fitness:.4f}"
                    )

                if patience_counter >= early_stopping_patience:
                    if verbose:
                        logger.info(
                            f"  早停触发，在第 {generation + 1} 代停止"
                        )
                    break

                next_generation = []
                elitism_count = int(self.elitism_rate * self.population_size)
                sorted_indices = np.argsort(fitnesses)[::-1]
                next_generation.extend(
                    [
                        self.population[i].clone()
                        for i in sorted_indices[:elitism_count]
                    ]
                )

                while len(next_generation) < self.population_size:
                    parent1 = self._selection(self.population, fitnesses)
                    parent2 = self._selection(self.population, fitnesses)

                    child = self._crossover(parent1, parent2)
                    self._mutation(child, feature_cols)
                    next_generation.append(child)

                self.population = next_generation
                fitnesses = self._evaluate_population(
                    self.population, X, y, model
                )

            if self.best_expression and self.best_fitness > 0:
                feature_name = f"symbolic_feature_{feature_idx + 1}"
                discovered_features.append(
                    (feature_name, self.best_expression, self.best_fitness)
                )
                if verbose:
                    logger.info(
                        f"发现特征 {feature_name}，适应度: {self.best_fitness:.4f}"
                    )

        return discovered_features

    def generate_features(
        self,
        X: pd.DataFrame,
        discovered_features: List[Tuple[str, ExpressionNode, float]],
    ) -> pd.DataFrame:
        """
        根据发现的特征生成新特征数据

        Args:
            X: 原始数据
            discovered_features: 发现的特征列表

        Returns:
            包含新特征的DataFrame
        """
        result = X.copy()
        for feature_name, expression, _ in discovered_features:
            try:
                result[feature_name] = expression.evaluate(X)
            except Exception as e:
                logger.warning(f"生成特征 {feature_name} 失败: {e}")
        return result

    def save(self, filepath: Path):
        """保存发现器状态"""
        data = {
            "population_size": self.population_size,
            "max_depth": self.max_depth,
            "mutation_rate": self.mutation_rate,
            "crossover_rate": self.crossover_rate,
            "elitism_rate": self.elitism_rate,
            "max_generations": self.max_generations,
            "random_state": self.random_state,
            "best_fitness": self.best_fitness,
            "fitness_history": self.fitness_history,
            "feature_names": self.feature_names,
        }
        with open(filepath, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"符号回归发现器已保存: {filepath}")

    def load(self, filepath: Path):
        """加载发现器状态"""
        with open(filepath, "rb") as f:
            data = pickle.load(f)

        self.population_size = data["population_size"]
        self.max_depth = data["max_depth"]
        self.mutation_rate = data["mutation_rate"]
        self.crossover_rate = data["crossover_rate"]
        self.elitism_rate = data["elitism_rate"]
        self.max_generations = data["max_generations"]
        self.random_state = data["random_state"]
        self.best_fitness = data["best_fitness"]
        self.fitness_history = data["fitness_history"]
        self.feature_names = data["feature_names"]

        logger.info(f"符号回归发现器已加载: {filepath}")
