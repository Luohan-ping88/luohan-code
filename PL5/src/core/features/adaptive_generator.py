"""
自适应特征发现模块 V1.0
实现动态特征生成和进化机制

核心功能：
1. 基于统计分析自动发现有价值的特征组合
2. 使用遗传算法优化特征表达式
3. 从模型训练反馈中学习新特征
4. 动态特征选择和进化
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Callable, Optional
from pathlib import Path
import pickle
import random
from collections import defaultdict
from sklearn.feature_selection import mutual_info_classif, SelectKBest
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import mutual_info_score

logger = logging.getLogger(__name__)

class AdaptiveFeatureGenerator:
    """自适应特征生成器 - 自动发现和生成新特征"""
    
    def __init__(self):
        self.feature_templates = self._load_feature_templates()
        self.discovered_features = {}
        self.feature_performance = defaultdict(list)
        self.generation = 0
        
    def _load_feature_templates(self) -> List[Dict]:
        """加载特征生成模板"""
        return [
            # 基础数学运算
            {'name': 'add', 'func': lambda a, b: a + b, 'description': '两特征相加'},
            {'name': 'sub', 'func': lambda a, b: a - b, 'description': '两特征相减'},
            {'name': 'mul', 'func': lambda a, b: a * b, 'description': '两特征相乘'},
            {'name': 'div', 'func': lambda a, b: np.where(b != 0, a / b, 0), 'description': '两特征相除'},
            {'name': 'pow', 'func': lambda a, b: np.power(a, b), 'description': '特征幂运算'},
            
            # 统计运算
            {'name': 'ratio', 'func': lambda a, b: np.where(b != 0, a / (a + b), 0), 'description': '比例特征'},
            {'name': 'diff_ratio', 'func': lambda a, b: np.where(b != 0, (a - b) / b, 0), 'description': '差分比例'},
            {'name': 'log_ratio', 'func': lambda a, b: np.log(np.where(a > 0, a, 1)) - np.log(np.where(b > 0, b, 1)), 'description': '对数比例'},
            
            # 非线性变换
            {'name': 'abs_diff', 'func': lambda a, b: np.abs(a - b), 'description': '绝对差值'},
            {'name': 'sq_diff', 'func': lambda a, b: (a - b) ** 2, 'description': '平方差'},
            {'name': 'interact', 'func': lambda a, b: a * b * (a - b), 'description': '交互项'},
            
            # 单特征变换
            {'name': 'log', 'func': lambda a, _: np.log(np.where(a > 0, a, 1)), 'description': '对数变换'},
            {'name': 'sqrt', 'func': lambda a, _: np.sqrt(np.where(a >= 0, a, 0)), 'description': '平方根'},
            {'name': 'square', 'func': lambda a, _: a ** 2, 'description': '平方'},
            {'name': 'cube', 'func': lambda a, _: a ** 3, 'description': '立方'},
            {'name': 'reciprocal', 'func': lambda a, _: np.where(a != 0, 1 / a, 0), 'description': '倒数'},
            {'name': 'sin', 'func': lambda a, _: np.sin(a), 'description': '正弦变换'},
            {'name': 'cos', 'func': lambda a, _: np.cos(a), 'description': '余弦变换'},
        ]
    
    def discover_new_features(self, df: pd.DataFrame, 
                             target_col: str,
                             max_candidates: int = 50,
                             quality_threshold: float = 0.01) -> pd.DataFrame:
        """
        基于统计分析发现新特征
        
        Args:
            df: 输入数据
            target_col: 目标列名
            max_candidates: 最大候选特征数
            quality_threshold: 互信息阈值
            
        Returns:
            包含新发现特征的DataFrame
        """
        logger.info(f"开始特征发现...")
        
        # 获取数值特征列
        numeric_cols = [col for col in df.columns 
                       if df[col].dtype in [np.float64, np.float32, np.int64, np.int32]
                       and col != target_col]
        
        if len(numeric_cols) < 2:
            logger.warning("数值特征不足，无法生成新特征")
            return df.copy()
        
        # 生成候选特征
        candidates = []
        templates = self.feature_templates
        np.random.seed(self.generation)
        
        # 随机选择特征对进行组合
        for _ in range(max_candidates * 2):
            template = np.random.choice(templates)
            if template['name'] in ['log', 'sqrt', 'square', 'cube', 'reciprocal', 'sin', 'cos']:
                # 单特征变换
                col = np.random.choice(numeric_cols)
                try:
                    result = template['func'](df[col].values, None)
                    if not np.isnan(result).all() and np.std(result) > 0.001:
                        candidates.append({
                            'name': f"{col}_{template['name']}",
                            'data': result,
                            'template': template['name'],
                            'base_cols': [col]
                        })
                except Exception as e:
                    continue
            else:
                # 双特征运算
                col1, col2 = np.random.choice(numeric_cols, 2, replace=False)
                try:
                    result = template['func'](df[col1].values, df[col2].values)
                    if not np.isnan(result).all() and np.std(result) > 0.001:
                        candidates.append({
                            'name': f"{col1}_{template['name']}_{col2}",
                            'data': result,
                            'template': template['name'],
                            'base_cols': [col1, col2]
                        })
                except Exception as e:
                    continue
        
        # 评估候选特征质量
        if candidates and target_col in df.columns:
            X = np.array([c['data'] for c in candidates]).T
            y = df[target_col].values
            
            # 使用互信息评估特征质量
            try:
                scores = mutual_info_classif(X, y, random_state=42)
                for i, candidate in enumerate(candidates):
                    candidate['score'] = scores[i]
            except Exception:
                # 如果互信息计算失败，使用相关性
                for candidate in candidates:
                    candidate['score'] = np.abs(np.corrcoef(candidate['data'], y)[0, 1])
            
            # 过滤低质量特征
            candidates = [c for c in candidates if c.get('score', 0) >= quality_threshold]
            # 按质量排序
            candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
            # 限制数量
            candidates = candidates[:max_candidates]
        
        logger.info(f"发现 {len(candidates)} 个新特征")
        
        # 添加新特征到DataFrame
        result = df.copy()
        for candidate in candidates:
            result[candidate['name']] = candidate['data']
            self.discovered_features[candidate['name']] = {
                'template': candidate['template'],
                'base_cols': candidate['base_cols'],
                'score': candidate.get('score', 0)
            }
        
        return result
    
    def update_performance(self, feature_name: str, score: float):
        """更新特征性能记录"""
        self.feature_performance[feature_name].append(score)
        if len(self.feature_performance[feature_name]) > 10:
            self.feature_performance[feature_name] = self.feature_performance[feature_name][-10:]
    
    def get_top_features(self, n: int = 20) -> List[str]:
        """获取性能最好的特征"""
        avg_scores = {}
        for name, scores in self.feature_performance.items():
            if scores:
                avg_scores[name] = np.mean(scores)
        return sorted(avg_scores.keys(), key=lambda x: avg_scores[x], reverse=True)[:n]


class GeneticFeatureOptimizer:
    """遗传特征优化器 - 使用遗传算法进化特征表达式"""
    
    def __init__(self, population_size: int = 50, mutation_rate: float = 0.1):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.operations = ['+', '-', '*', '/', '**', 'log', 'sqrt', 'abs']
        self.population = []
    
    def _create_random_expression(self, feature_names: List[str]) -> str:
        """创建随机特征表达式"""
        if not feature_names:
            return "x"
        
        op = np.random.choice(self.operations)
        if op in ['log', 'sqrt', 'abs']:
            # 单操作数
            return f"{op}({np.random.choice(feature_names)})"
        else:
            # 双操作数
            return f"({np.random.choice(feature_names)}){op}({np.random.choice(feature_names)})"
    
    def _evaluate_expression(self, expr: str, df: pd.DataFrame, target: pd.Series) -> float:
        """评估特征表达式的质量"""
        try:
            # 创建安全的局部环境
            local_vars = {name: df[name].values for name in df.columns}
            local_vars.update({
                'log': np.log,
                'sqrt': np.sqrt,
                'abs': np.abs,
                'np': np
            })
            result = eval(expr, {"__builtins__": {}}, local_vars)
            
            if not np.isfinite(result).all():
                return -1.0
            
            score = mutual_info_score(target, pd.cut(result, bins=10, labels=False))
            return score if np.isfinite(score) else 0.0
        except Exception:
            return -1.0
    
    def _crossover(self, expr1: str, expr2: str) -> str:
        """交叉操作"""
        if len(expr1) < 5 or len(expr2) < 5:
            return expr1
        
        split_pos = np.random.randint(1, min(len(expr1), len(expr2)) - 1)
        return expr1[:split_pos] + expr2[split_pos:]
    
    def _mutate(self, expr: str, feature_names: List[str]) -> str:
        """变异操作"""
        if np.random.random() > self.mutation_rate:
            return expr
        
        # 随机替换一部分表达式
        new_part = self._create_random_expression(feature_names)
        if len(expr) > 10:
            start = np.random.randint(0, len(expr) - 5)
            length = np.random.randint(3, min(10, len(expr) - start))
            return expr[:start] + new_part[:length] + expr[start + length:]
        return new_part
    
    def optimize(self, df: pd.DataFrame, target_col: str, 
                 generations: int = 10) -> List[Dict]:
        """
        运行遗传算法优化特征
        
        Args:
            df: 输入数据
            target_col: 目标列
            generations: 进化代数
            
        Returns:
            优化后的特征表达式列表
        """
        feature_names = [col for col in df.columns if col != target_col]
        if not feature_names:
            return []
        
        # 初始化种群
        self.population = [self._create_random_expression(feature_names) 
                          for _ in range(self.population_size)]
        
        target = df[target_col]
        
        for gen in range(generations):
            # 评估种群
            scores = [self._evaluate_expression(expr, df, target) 
                     for expr in self.population]
            
            # 选择优秀个体
            sorted_indices = np.argsort(scores)[::-1]
            top_indices = sorted_indices[:self.population_size // 2]
            top_population = [self.population[i] for i in top_indices]
            
            # 繁殖新种群
            new_population = top_population.copy()
            
            while len(new_population) < self.population_size:
                parent1, parent2 = np.random.choice(top_population, 2, replace=False)
                child = self._crossover(parent1, parent2)
                child = self._mutate(child, feature_names)
                new_population.append(child)
            
            self.population = new_population
            
            best_score = max(scores)
            best_expr = self.population[np.argmax(scores)]
            logger.info(f"遗传优化代 {gen+1}: 最佳得分={best_score:.4f}")
        
        # 返回最佳特征
        scores = [self._evaluate_expression(expr, df, target) 
                 for expr in self.population]
        sorted_indices = np.argsort(scores)[::-1]
        
        results = []
        for i in sorted_indices[:10]:
            expr = self.population[i]
            try:
                local_vars = {name: df[name].values for name in df.columns}
                local_vars.update({'log': np.log, 'sqrt': np.sqrt, 'abs': np.abs, 'np': np})
                data = eval(expr, {"__builtins__": {}}, local_vars)
                results.append({
                    'expression': expr,
                    'score': scores[i],
                    'data': data
                })
            except Exception:
                continue
        
        return results
