"""
策略演化机制模块
策略变异、交叉和选择机制
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
import logging
import random
import numpy as np

logger = logging.getLogger(__name__)


class SelectionMethod(Enum):
    """选择方法枚举"""

    TOURNAMENT = "tournament"
    ROULETTE_WHEEL = "roulette_wheel"
    RANK_BASED = "rank_based"
    ELITIST = "elitist"


class MutationMethod(Enum):
    """变异方法枚举"""

    GAUSSIAN = "gaussian"
    UNIFORM = "uniform"
    BIT_FLIP = "bit_flip"
    POLYNOMIAL = "polynomial"


class CrossoverMethod(Enum):
    """交叉方法枚举"""

    ONE_POINT = "one_point"
    TWO_POINT = "two_point"
    UNIFORM = "uniform"
    BLEND = "blend"


@dataclass
class Individual:
    """个体（策略配置）"""

    id: str
    genotype: Dict[str, Any]
    fitness: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: np.random.rand())


@dataclass
class EvolutionResult:
    """演化结果"""

    best_individual: Individual
    population: List[Individual]
    generation: int
    fitness_history: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


class GeneticAlgorithm:
    """遗传算法策略演化器"""

    def __init__(
        self,
        population_size: int = 50,
        max_generations: int = 100,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.8,
        elitism_rate: float = 0.1,
        selection_method: SelectionMethod = SelectionMethod.TOURNAMENT,
        mutation_method: MutationMethod = MutationMethod.GAUSSIAN,
        crossover_method: CrossoverMethod = CrossoverMethod.ONE_POINT,
        random_seed: Optional[int] = None,
    ):
        self.population_size = population_size
        self.max_generations = max_generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism_rate = elitism_rate
        self.selection_method = selection_method
        self.mutation_method = mutation_method
        self.crossover_method = crossover_method

        if random_seed is not None:
            random.seed(random_seed)
            np.random.seed(random_seed)

        self.population: List[Individual] = []
        self.fitness_history: List[float] = []
        self._fitness_function: Optional[Callable[[Dict[str, Any]], float]] = (
            None
        )

    def set_fitness_function(
        self, fitness_function: Callable[[Dict[str, Any]], float]
    ) -> None:
        """设置适应度函数"""
        self._fitness_function = fitness_function

    def initialize_population(
        self, genotype_template: Dict[str, Dict[str, Any]]
    ) -> List[Individual]:
        """
        初始化种群

        Args:
            genotype_template: 基因型模板，格式为 {param_name: {'type': 'int/float/bool', 'min': x, 'max': y, 'options': []}}

        Returns:
            初始种群
        """
        self.population = []
        for i in range(self.population_size):
            genotype = self._generate_genotype(genotype_template)
            individual = Individual(
                id=f"ind_{i}_{np.random.randint(10000)}", genotype=genotype
            )
            self.population.append(individual)

        logger.info(f"初始化种群完成，大小: {len(self.population)}")
        return self.population

    def _generate_genotype(
        self, genotype_template: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成随机基因型"""
        genotype = {}
        for param_name, param_spec in genotype_template.items():
            param_type = param_spec.get("type", "float")

            if param_type == "int":
                min_val = param_spec.get("min", 0)
                max_val = param_spec.get("max", 100)
                genotype[param_name] = random.randint(min_val, max_val)
            elif param_type == "float":
                min_val = param_spec.get("min", 0.0)
                max_val = param_spec.get("max", 1.0)
                genotype[param_name] = random.uniform(min_val, max_val)
            elif param_type == "bool":
                genotype[param_name] = random.choice([True, False])
            elif param_type == "categorical":
                options = param_spec.get("options", [])
                if options:
                    genotype[param_name] = random.choice(options)
            elif param_type == "list":
                options = param_spec.get("options", [])
                min_len = param_spec.get("min_len", 1)
                max_len = param_spec.get("max_len", 5)
                length = random.randint(min_len, max_len)
                genotype[param_name] = (
                    random.sample(options, min(length, len(options)))
                    if options
                    else []
                )

        return genotype

    def evaluate_population(self) -> List[float]:
        """
        评估种群适应度

        Returns:
            适应度列表
        """
        if self._fitness_function is None:
            raise ValueError("请先设置适应度函数")

        fitness_values = []
        for individual in self.population:
            fitness = self._fitness_function(individual.genotype)
            individual.fitness = fitness
            fitness_values.append(fitness)

        return fitness_values

    def select_parents(self, num_parents: int) -> List[Individual]:
        """
        选择父代

        Args:
            num_parents: 父代数量

        Returns:
            选中的父代列表
        """
        if self.selection_method == SelectionMethod.TOURNAMENT:
            return self._tournament_selection(num_parents)
        elif self.selection_method == SelectionMethod.ROULETTE_WHEEL:
            return self._roulette_wheel_selection(num_parents)
        elif self.selection_method == SelectionMethod.RANK_BASED:
            return self._rank_based_selection(num_parents)
        elif self.selection_method == SelectionMethod.ELITIST:
            return self._elitist_selection(num_parents)
        else:
            return self._tournament_selection(num_parents)

    def _tournament_selection(
        self, num_parents: int, tournament_size: int = 3
    ) -> List[Individual]:
        """锦标赛选择"""
        parents = []
        for _ in range(num_parents):
            tournament = random.sample(self.population, tournament_size)
            winner = max(tournament, key=lambda x: x.fitness)
            parents.append(winner)
        return parents

    def _roulette_wheel_selection(self, num_parents: int) -> List[Individual]:
        """轮盘赌选择"""
        total_fitness = sum(ind.fitness for ind in self.population)
        if total_fitness == 0:
            return random.sample(self.population, num_parents)

        selection_probs = [
            ind.fitness / total_fitness for ind in self.population
        ]
        parents = random.choices(
            self.population, weights=selection_probs, k=num_parents
        )
        return parents

    def _rank_based_selection(self, num_parents: int) -> List[Individual]:
        """基于排名的选择"""
        sorted_pop = sorted(self.population, key=lambda x: x.fitness)
        ranks = list(range(1, len(sorted_pop) + 1))
        total_rank = sum(ranks)
        selection_probs = [rank / total_rank for rank in ranks]
        parents = random.choices(
            sorted_pop, weights=selection_probs, k=num_parents
        )
        return parents

    def _elitist_selection(self, num_parents: int) -> List[Individual]:
        """精英选择"""
        sorted_pop = sorted(
            self.population, key=lambda x: x.fitness, reverse=True
        )
        return sorted_pop[:num_parents]

    def crossover(
        self, parent1: Individual, parent2: Individual
    ) -> Tuple[Individual, Individual]:
        """
        交叉操作

        Args:
            parent1: 父代1
            parent2: 父代2

        Returns:
            两个子代
        """
        if self.crossover_method == CrossoverMethod.ONE_POINT:
            return self._one_point_crossover(parent1, parent2)
        elif self.crossover_method == CrossoverMethod.TWO_POINT:
            return self._two_point_crossover(parent1, parent2)
        elif self.crossover_method == CrossoverMethod.UNIFORM:
            return self._uniform_crossover(parent1, parent2)
        elif self.crossover_method == CrossoverMethod.BLEND:
            return self._blend_crossover(parent1, parent2)
        else:
            return self._one_point_crossover(parent1, parent2)

    def _one_point_crossover(
        self, parent1: Individual, parent2: Individual
    ) -> Tuple[Individual, Individual]:
        """单点交叉"""
        keys = list(parent1.genotype.keys())
        if len(keys) < 2:
            return parent1, parent2

        crossover_point = random.randint(1, len(keys) - 1)

        child1_genotype = {}
        child2_genotype = {}

        for i, key in enumerate(keys):
            if i < crossover_point:
                child1_genotype[key] = parent1.genotype[key]
                child2_genotype[key] = parent2.genotype[key]
            else:
                child1_genotype[key] = parent2.genotype[key]
                child2_genotype[key] = parent1.genotype[key]

        child1 = Individual(
            id=f"child_{np.random.randint(10000)}", genotype=child1_genotype
        )
        child2 = Individual(
            id=f"child_{np.random.randint(10000)}", genotype=child2_genotype
        )

        return child1, child2

    def _two_point_crossover(
        self, parent1: Individual, parent2: Individual
    ) -> Tuple[Individual, Individual]:
        """两点交叉"""
        keys = list(parent1.genotype.keys())
        if len(keys) < 3:
            return self._one_point_crossover(parent1, parent2)

        point1 = random.randint(1, len(keys) - 2)
        point2 = random.randint(point1 + 1, len(keys) - 1)

        child1_genotype = {}
        child2_genotype = {}

        for i, key in enumerate(keys):
            if i < point1 or i >= point2:
                child1_genotype[key] = parent1.genotype[key]
                child2_genotype[key] = parent2.genotype[key]
            else:
                child1_genotype[key] = parent2.genotype[key]
                child2_genotype[key] = parent1.genotype[key]

        child1 = Individual(
            id=f"child_{np.random.randint(10000)}", genotype=child1_genotype
        )
        child2 = Individual(
            id=f"child_{np.random.randint(10000)}", genotype=child2_genotype
        )

        return child1, child2

    def _uniform_crossover(
        self, parent1: Individual, parent2: Individual
    ) -> Tuple[Individual, Individual]:
        """均匀交叉"""
        child1_genotype = {}
        child2_genotype = {}

        for key in parent1.genotype.keys():
            if random.random() < 0.5:
                child1_genotype[key] = parent1.genotype[key]
                child2_genotype[key] = parent2.genotype[key]
            else:
                child1_genotype[key] = parent2.genotype[key]
                child2_genotype[key] = parent1.genotype[key]

        child1 = Individual(
            id=f"child_{np.random.randint(10000)}", genotype=child1_genotype
        )
        child2 = Individual(
            id=f"child_{np.random.randint(10000)}", genotype=child2_genotype
        )

        return child1, child2

    def _blend_crossover(
        self, parent1: Individual, parent2: Individual, alpha: float = 0.5
    ) -> Tuple[Individual, Individual]:
        """混合交叉（用于数值参数）"""
        child1_genotype = {}
        child2_genotype = {}

        for key in parent1.genotype.keys():
            val1 = parent1.genotype[key]
            val2 = parent2.genotype[key]

            if isinstance(val1, (int, float)) and isinstance(
                val2, (int, float)
            ):
                d = abs(val2 - val1)
                lower = min(val1, val2) - alpha * d
                upper = max(val1, val2) + alpha * d

                child1_genotype[key] = random.uniform(lower, upper)
                child2_genotype[key] = random.uniform(lower, upper)
            else:
                if random.random() < 0.5:
                    child1_genotype[key] = val1
                    child2_genotype[key] = val2
                else:
                    child1_genotype[key] = val2
                    child2_genotype[key] = val1

        child1 = Individual(
            id=f"child_{np.random.randint(10000)}", genotype=child1_genotype
        )
        child2 = Individual(
            id=f"child_{np.random.randint(10000)}", genotype=child2_genotype
        )

        return child1, child2

    def mutate(
        self,
        individual: Individual,
        genotype_template: Dict[str, Dict[str, Any]],
    ) -> Individual:
        """
        变异操作

        Args:
            individual: 个体
            genotype_template: 基因型模板

        Returns:
            变异后的个体
        """
        mutated_genotype = individual.genotype.copy()

        for param_name, param_spec in genotype_template.items():
            if random.random() < self.mutation_rate:
                param_type = param_spec.get("type", "float")

                if self.mutation_method == MutationMethod.GAUSSIAN:
                    mutated_genotype = self._gaussian_mutate(
                        mutated_genotype, param_name, param_spec
                    )
                elif self.mutation_method == MutationMethod.UNIFORM:
                    mutated_genotype = self._uniform_mutate(
                        mutated_genotype, param_name, param_spec
                    )
                elif self.mutation_method == MutationMethod.BIT_FLIP:
                    mutated_genotype = self._bit_flip_mutate(
                        mutated_genotype, param_name, param_spec
                    )
                elif self.mutation_method == MutationMethod.POLYNOMIAL:
                    mutated_genotype = self._polynomial_mutate(
                        mutated_genotype, param_name, param_spec
                    )

        return Individual(
            id=individual.id,
            genotype=mutated_genotype,
            metadata=individual.metadata,
        )

    def _gaussian_mutate(
        self,
        genotype: Dict[str, Any],
        param_name: str,
        param_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """高斯变异"""
        param_type = param_spec.get("type", "float")

        if param_type == "float":
            current = genotype[param_name]
            min_val = param_spec.get("min", 0.0)
            max_val = param_spec.get("max", 1.0)
            sigma = (max_val - min_val) * 0.1
            new_val = current + np.random.normal(0, sigma)
            genotype[param_name] = max(min_val, min(max_val, new_val))
        elif param_type == "int":
            current = genotype[param_name]
            min_val = param_spec.get("min", 0)
            max_val = param_spec.get("max", 100)
            sigma = (max_val - min_val) * 0.1
            new_val = int(round(current + np.random.normal(0, sigma)))
            genotype[param_name] = max(min_val, min(max_val, new_val))
        elif param_type == "bool":
            genotype[param_name] = not genotype[param_name]

        return genotype

    def _uniform_mutate(
        self,
        genotype: Dict[str, Any],
        param_name: str,
        param_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """均匀变异"""
        param_type = param_spec.get("type", "float")

        if param_type == "float":
            min_val = param_spec.get("min", 0.0)
            max_val = param_spec.get("max", 1.0)
            genotype[param_name] = random.uniform(min_val, max_val)
        elif param_type == "int":
            min_val = param_spec.get("min", 0)
            max_val = param_spec.get("max", 100)
            genotype[param_name] = random.randint(min_val, max_val)
        elif param_type == "bool":
            genotype[param_name] = random.choice([True, False])
        elif param_type == "categorical":
            options = param_spec.get("options", [])
            if options:
                genotype[param_name] = random.choice(options)

        return genotype

    def _bit_flip_mutate(
        self,
        genotype: Dict[str, Any],
        param_name: str,
        param_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """位翻转变异"""
        param_type = param_spec.get("type", "float")

        if param_type == "bool":
            genotype[param_name] = not genotype[param_name]
        elif param_type == "int":
            genotype[param_name] = (
                1 - genotype[param_name]
                if genotype[param_name] in [0, 1]
                else genotype[param_name]
            )

        return genotype

    def _polynomial_mutate(
        self,
        genotype: Dict[str, Any],
        param_name: str,
        param_spec: Dict[str, Any],
        eta: float = 20.0,
    ) -> Dict[str, Any]:
        """多项式变异"""
        param_type = param_spec.get("type", "float")

        if param_type in ["float", "int"]:
            current = genotype[param_name]
            min_val = param_spec.get(
                "min", 0.0 if param_type == "float" else 0
            )
            max_val = param_spec.get(
                "max", 1.0 if param_type == "float" else 100
            )

            delta1 = (current - min_val) / (max_val - min_val)
            delta2 = (max_val - current) / (max_val - min_val)

            rand = random.random()
            mut_pow = 1.0 / (eta + 1.0)

            if rand <= 0.5:
                xy = 1.0 - delta1
                val = 2.0 * rand + (1.0 - 2.0 * rand) * (xy ** (eta + 1.0))
                deltaq = (val**mut_pow) - 1.0
            else:
                xy = 1.0 - delta2
                val = 2.0 * (1.0 - rand) + 2.0 * (rand - 0.5) * (
                    xy ** (eta + 1.0)
                )
                deltaq = 1.0 - (val**mut_pow)

            new_val = current + deltaq * (max_val - min_val)
            new_val = max(min_val, min(max_val, new_val))

            if param_type == "int":
                new_val = int(round(new_val))

            genotype[param_name] = new_val

        return genotype

    def evolve(
        self, genotype_template: Dict[str, Dict[str, Any]]
    ) -> EvolutionResult:
        """
        执行演化过程

        Args:
            genotype_template: 基因型模板

        Returns:
            演化结果
        """
        if not self.population:
            self.initialize_population(genotype_template)

        self.fitness_history = []

        for generation in range(self.max_generations):
            self.evaluate_population()

            best_fitness = max(ind.fitness for ind in self.population)
            self.fitness_history.append(best_fitness)
            logger.info(
                f"Generation {generation}: Best fitness = {best_fitness}"
            )

            new_population = []

            num_elite = int(self.elitism_rate * self.population_size)
            if num_elite > 0:
                sorted_pop = sorted(
                    self.population, key=lambda x: x.fitness, reverse=True
                )
                new_population.extend(sorted_pop[:num_elite])

            while len(new_population) < self.population_size:
                parents = self.select_parents(2)

                if random.random() < self.crossover_rate:
                    child1, child2 = self.crossover(parents[0], parents[1])
                else:
                    child1, child2 = parents[0], parents[1]

                child1 = self.mutate(child1, genotype_template)
                child2 = self.mutate(child2, genotype_template)

                new_population.append(child1)
                if len(new_population) < self.population_size:
                    new_population.append(child2)

            self.population = new_population[: self.population_size]

        self.evaluate_population()
        best_individual = max(self.population, key=lambda x: x.fitness)

        return EvolutionResult(
            best_individual=best_individual,
            population=self.population,
            generation=self.max_generations,
            fitness_history=self.fitness_history,
        )

    def get_best_individual(self) -> Optional[Individual]:
        """获取当前最佳个体"""
        if not self.population:
            return None
        return max(self.population, key=lambda x: x.fitness)
