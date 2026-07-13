"""
模块组合生成器
处理模块依赖关系解析、模块组合生成和组合验证
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
import logging
from collections import deque

from .registry import ModuleMetadata, ModuleStatus, get_global_registry

logger = logging.getLogger(__name__)


class DependencyType(Enum):
    """依赖类型"""
    REQUIRED = "required"
    OPTIONAL = "optional"
    RUNTIME = "runtime"


@dataclass
class Dependency:
    """模块依赖"""
    module_name: str
    version_requirement: Optional[str] = None
    dependency_type: DependencyType = DependencyType.REQUIRED


@dataclass
class ModuleCombination:
    """模块组合"""
    name: str
    modules: List[ModuleMetadata]
    dependencies: Dict[str, List[Dependency]] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = False
    created_at: float = field(default_factory=lambda: __import__('time').time())


class ModuleComposer:
    """模块组合生成器"""

    def __init__(self):
        self._registry = get_global_registry()
        self._combinations: Dict[str, ModuleCombination] = {}

    def create_combination(self, name: str,
                           module_names: List[str],
                           validate: bool = True) -> Optional[ModuleCombination]:
        """
        创建模块组合

        Args:
            name: 组合名称
            module_names: 模块名称列表
            validate: 是否立即验证

        Returns:
            创建的模块组合，失败返回 None
        """
        modules = []
        for module_name in module_names:
            metadata = self._registry.get(module_name)
            if not metadata:
                logger.error(f"模块不存在: {module_name}")
                return None
            modules.append(metadata)

        combination = ModuleCombination(
            name=name,
            modules=modules
        )

        if validate:
            self.validate_combination(combination)

        self._combinations[name] = combination
        logger.info(f"创建模块组合: {name}")
        return combination

    def validate_combination(self, combination: ModuleCombination) -> bool:
        """
        验证模块组合

        Args:
            combination: 要验证的模块组合

        Returns:
            验证是否通过
        """
        errors = []
        module_set = {m.name for m in combination.modules}

        for module in combination.modules:
            if module.status == ModuleStatus.DEPRECATED:
                errors.append(f"模块 {module.name} 已废弃")
            if module.status == ModuleStatus.ERROR:
                errors.append(f"模块 {module.name} 处于错误状态")

            for dep_name in module.dependencies:
                if dep_name not in module_set:
                    dep_metadata = self._registry.get(dep_name)
                    if dep_metadata and dep_metadata.status == ModuleStatus.ACTIVE:
                        pass
                    else:
                        errors.append(f"模块 {module.name} 缺少依赖: {dep_name}")

        cycle_result = self._detect_cycles(combination.modules)
        if cycle_result:
            errors.append(f"检测到循环依赖: {' -> '.join(cycle_result)}")

        combination.validation_errors = errors
        combination.is_valid = len(errors) == 0

        if combination.is_valid:
            logger.info(f"模块组合验证通过: {combination.name}")
        else:
            logger.warning(f"模块组合验证失败: {combination.name}, 错误: {errors}")

        return combination.is_valid

    def _detect_cycles(self, modules: List[ModuleMetadata]) -> Optional[List[str]]:
        """
        检测模块循环依赖

        Args:
            modules: 模块列表

        Returns:
            循环依赖链（如果有），否则返回 None
        """
        module_map = {m.name: m for m in modules}
        visited = set()
        rec_stack = {}

        def dfs(module_name: str, path: List[str]) -> Optional[List[str]]:
            if module_name in rec_stack:
                idx = path.index(module_name)
                return path[idx:] + [module_name]
            if module_name in visited:
                return None

            visited.add(module_name)
            rec_stack[module_name] = True
            path.append(module_name)

            module = module_map.get(module_name)
            if module:
                for dep_name in module.dependencies:
                    cycle = dfs(dep_name, path)
                    if cycle:
                        return cycle

            path.pop()
            del rec_stack[module_name]
            return None

        for module_name in module_map:
            cycle = dfs(module_name, [])
            if cycle:
                return cycle

        return None

    def resolve_dependencies(self, module_names: List[str]) -> List[str]:
        """
        解析模块依赖关系，返回拓扑排序的模块列表

        Args:
            module_names: 模块名称列表

        Returns:
            拓扑排序后的模块名称列表
        """
        in_degree: Dict[str, int] = {}
        graph: Dict[str, List[str]] = {}

        all_modules = set(module_names)
        queue = deque(module_names)

        while queue:
            current = queue.popleft()
            metadata = self._registry.get(current)
            if not metadata:
                continue

            if current not in in_degree:
                in_degree[current] = 0
            if current not in graph:
                graph[current] = []

            for dep in metadata.dependencies:
                if dep not in all_modules:
                    all_modules.add(dep)
                    queue.append(dep)
                if dep not in graph:
                    graph[dep] = []
                if current not in graph[dep]:
                    graph[dep].append(current)
                if dep not in in_degree:
                    in_degree[dep] = 0
                in_degree[current] = in_degree.get(current, 0) + 1

        result = []
        temp_queue = deque([n for n in in_degree if in_degree[n] == 0])

        while temp_queue:
            current = temp_queue.popleft()
            result.append(current)
            for neighbor in graph.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    temp_queue.append(neighbor)

        if len(result) != len(all_modules):
            logger.error("无法解析依赖关系，存在循环依赖")
            return []

        return result

    def list_combinations(self) -> List[ModuleCombination]:
        """
        列出所有模块组合

        Returns:
            模块组合列表
        """
        return list(self._combinations.values())

    def get_combination(self, name: str) -> Optional[ModuleCombination]:
        """
        获取指定名称的模块组合

        Args:
            name: 组合名称

        Returns:
            模块组合，不存在返回 None
        """
        return self._combinations.get(name)

    def delete_combination(self, name: str) -> bool:
        """
        删除模块组合

        Args:
            name: 组合名称

        Returns:
            删除是否成功
        """
        if name in self._combinations:
            del self._combinations[name]
            logger.info(f"删除模块组合: {name}")
            return True
        return False

    def clear(self) -> None:
        """清空所有模块组合"""
        self._combinations.clear()
        logger.info("所有模块组合已清空")


_global_composer: Optional[ModuleComposer] = None


def get_global_composer() -> ModuleComposer:
    """获取全局模块组合生成器"""
    global _global_composer
    if _global_composer is None:
        _global_composer = ModuleComposer()
    return _global_composer
