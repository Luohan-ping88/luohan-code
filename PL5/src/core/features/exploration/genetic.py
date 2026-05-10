"""
遗传算法特征生成器
通过遗传算法自动发现和优化特征组合
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
import logging
import random
from pathlib import Path
import pickle
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_val_score

logger = logging.getLogger(__name__)


class Chromosome:
    """染色体 - 表示一个特征组合"""

    def __init__(self, genes: np.ndarray, feature_names: List[str]):
        self.genes = genes
        self.feature_names = feature_names
        self.fitness = 0.0

    @property
    def selected_features(self) -> List[str]:
        """获取选中的特征列表"""
        return [name for name, gene in zip(self.feature_names, self.genes) if gene == 1]

    def __len__(self) -> int:
        return len(self.genes)

    def __repr__(self) -> str:
        return f"Chromosome(genes={self.genes}, fitness={self.fitness:.4f})"


class GeneticFeatureGenerator:
    """遗传算法特征生成器"""

    def __init__(
        self,
        population_size: int = 50,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.8,
        elitism_rate: float = 0.1,
        max_generations: int = 100,
        random_state: int = 42
    ):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism_rate = elitism_rate
        self.max_generations = max_generations
        self.random_state = random_state

        self.population: List[Chromosome] = []
        self.best_chromosome: Optional[Chromosome] = None
        self.fitness_history: List[float] = []
        self.feature_names: List[str] = []

        random.seed(random_state)
        np.random.seed(random_state)

    def _initialize_population(self, feature_names: List[str]) -> List[Chromosome]:
        """初始化种群"""
        population = []
        n_features = len(feature_names)

        for _ in range(self.population_size):
            genes = np.random.randint(0, 2, size=n_features)
            if np.sum(genes) == 0:
                genes[np.random.randint(0, n_features)] = 1
            chromosome = Chromosome(genes, feature_names)
            population.append(chromosome)

        return population

    def _fitness_function(
        self,
        chromosome: Chromosome,
        X: pd.DataFrame,
        y: pd.Series,
        model: Optional[BaseEstimator] = None,
        cv: int = 3
    ) -> float:
        """适应度函数 - 基于交叉验证评分"""
        selected_features = chromosome.selected_features

        if not selected_features:
            return 0.0

        X_subset = X[selected_features].fillna(0)

        if model is None:
            is_classification = len(np.unique(y)) <= 10
            if is_classification:
                model = RandomForestClassifier(
                    n_estimators=50,
                    max_depth=5,
                    random_state=self.random_state,
                    n_jobs=-1
                )
            else:
                model = RandomForestRegressor(
                    n_estimators=50,
                    max_depth=5,
                    random_state=self.random_state,
                    n_jobs=-1
                )

        try:
            scores = cross_val_score(model, X_subset, y, cv=cv, n_jobs=-1)
            feature_penalty = len(selected_features) / len(self.feature_names) * 0.1
            fitness = scores.mean() - feature_penalty
            return max(fitness, 0.0)
        except Exception as e:
            logger.warning(f"适应度计算失败: {e}")
            return 0.0

    def _evaluate_population(
        self,
        population: List[Chromosome],
        X: pd.DataFrame,
        y: pd.Series,
        model: Optional[BaseEstimator] = None
    ):
        """评估种群中所有染色体的适应度"""
        for chromosome in population:
            chromosome.fitness = self._fitness_function(chromosome, X, y, model)

    def _selection(self, population: List[Chromosome]) -> Chromosome:
        """选择操作 - 轮盘赌选择"""
        total_fitness = sum(c.fitness for c in population)
        if total_fitness == 0:
            return random.choice(population)

        pick = random.uniform(0, total_fitness)
        current = 0.0
        for chromosome in population:
            current += chromosome.fitness
            if current >= pick:
                return chromosome

        return population[-1]

    def _crossover(self, parent1: Chromosome, parent2: Chromosome) -> Tuple[Chromosome, Chromosome]:
        """交叉操作 - 单点交叉"""
        if random.random() > self.crossover_rate:
            return parent1, parent2

        point = random.randint(1, len(parent1.genes) - 1)
        child1_genes = np.concatenate([parent1.genes[:point], parent2.genes[point:]])
        child2_genes = np.concatenate([parent2.genes[:point], parent1.genes[point:]])

        child1 = Chromosome(child1_genes, parent1.feature_names)
        child2 = Chromosome(child2_genes, parent1.feature_names)

        return child1, child2

    def _mutation(self, chromosome: Chromosome):
        """变异操作 - 位翻转"""
        for i in range(len(chromosome.genes)):
            if random.random() < self.mutation_rate:
                chromosome.genes[i] = 1 - chromosome.genes[i]

        if np.sum(chromosome.genes) == 0:
            chromosome.genes[random.randint(0, len(chromosome.genes) - 1)] = 1

    def _create_next_generation(
        self,
        population: List[Chromosome],
        X: pd.DataFrame,
        y: pd.Series,
        model: Optional[BaseEstimator] = None
    ) -> List[Chromosome]:
        """创建下一代种群"""
        next_generation = []

        elitism_count = int(self.elitism_rate * self.population_size)
        sorted_population = sorted(population, key=lambda c: c.fitness, reverse=True)
        next_generation.extend(sorted_population[:elitism_count])

        while len(next_generation) < self.population_size:
            parent1 = self._selection(population)
            parent2 = self._selection(population)

            child1, child2 = self._crossover(parent1, parent2)
            self._mutation(child1)
            self._mutation(child2)

            if len(next_generation) < self.population_size:
                next_generation.append(child1)
            if len(next_generation) < self.population_size:
                next_generation.append(child2)

        self._evaluate_population(next_generation, X, y, model)
        return next_generation

    def generate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_cols: Optional[List[str]] = None,
        model: Optional[BaseEstimator] = None,
        early_stopping_patience: int = 10,
        verbose: bool = True
    ) -> List[str]:
        """
        运行遗传算法生成特征组合

        Args:
            X: 特征数据
            y: 目标变量
            feature_cols: 可选的特征列，默认使用所有数值列
            model: 可选的模型用于适应度评估
            early_stopping_patience: 早停耐心值
            verbose: 是否打印进度

        Returns:
            最佳特征组合列表
        """
        if feature_cols is None:
            feature_cols = [col for col in X.columns if np.issubdtype(X[col].dtype, np.number)]

        self.feature_names = feature_cols
        self.population = self._initialize_population(feature_cols)
        self._evaluate_population(self.population, X, y, model)

        self.fitness_history = []
        patience_counter = 0
        best_fitness = -float('inf')

        for generation in range(self.max_generations):
            current_best = max(self.population, key=lambda c: c.fitness)
            self.fitness_history.append(current_best.fitness)

            if current_best.fitness > best_fitness:
                best_fitness = current_best.fitness
                self.best_chromosome = Chromosome(current_best.genes.copy(), current_best.feature_names)
                self.best_chromosome.fitness = current_best.fitness
                patience_counter = 0
            else:
                patience_counter += 1

            if verbose:
                logger.info(f"Generation {generation + 1}/{self.max_generations} - "
                           f"Best Fitness: {best_fitness:.4f} - "
                           f"Features: {len(self.best_chromosome.selected_features)}")

            if patience_counter >= early_stopping_patience:
                if verbose:
                    logger.info(f"早停触发，在第 {generation + 1} 代停止")
                break

            self.population = self._create_next_generation(self.population, X, y, model)

        if self.best_chromosome is None:
            self.best_chromosome = max(self.population, key=lambda c: c.fitness)

        return self.best_chromosome.selected_features

    def get_feature_evolution_stats(self) -> Dict[str, Any]:
        """获取特征进化统计信息"""
        return {
            'best_fitness': self.best_chromosome.fitness if self.best_chromosome else 0.0,
            'best_features': self.best_chromosome.selected_features if self.best_chromosome else [],
            'num_features': len(self.best_chromosome.selected_features) if self.best_chromosome else 0,
            'fitness_history': self.fitness_history,
            'num_generations': len(self.fitness_history)
        }

    def save(self, filepath: Path):
        """保存生成器状态"""
        data = {
            'population_size': self.population_size,
            'mutation_rate': self.mutation_rate,
            'crossover_rate': self.crossover_rate,
            'elitism_rate': self.elitism_rate,
            'max_generations': self.max_generations,
            'random_state': self.random_state,
            'best_chromosome': {
                'genes': self.best_chromosome.genes.tolist() if self.best_chromosome else None,
                'feature_names': self.best_chromosome.feature_names if self.best_chromosome else None,
                'fitness': self.best_chromosome.fitness if self.best_chromosome else 0.0
            },
            'fitness_history': self.fitness_history,
            'feature_names': self.feature_names
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"遗传算法生成器已保存: {filepath}")

    def load(self, filepath: Path):
        """加载生成器状态"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        self.population_size = data['population_size']
        self.mutation_rate = data['mutation_rate']
        self.crossover_rate = data['crossover_rate']
        self.elitism_rate = data['elitism_rate']
        self.max_generations = data['max_generations']
        self.random_state = data['random_state']
        self.fitness_history = data['fitness_history']
        self.feature_names = data['feature_names']

        if data['best_chromosome']['genes'] is not None:
            self.best_chromosome = Chromosome(
                np.array(data['best_chromosome']['genes']),
                data['best_chromosome']['feature_names']
            )
            self.best_chromosome.fitness = data['best_chromosome']['fitness']

        logger.info(f"遗传算法生成器已加载: {filepath}")
