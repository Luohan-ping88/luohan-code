"""
模块化解耦系统
包含模块注册中心、动态加载器、组合生成器和A/B测试框架
"""

from .registry import (
    ModuleStatus,
    ModuleMetadata,
    ModuleRegistry,
    get_global_registry,
)

from .loader import LoadedModule, ModuleLoader, get_global_loader

from .composer import (
    DependencyType,
    Dependency,
    ModuleCombination,
    ModuleComposer,
    get_global_composer,
)

from .ab_test import (
    ExperimentStatus,
    Variant,
    MetricValue,
    ExperimentResult,
    Experiment,
    ABTestFramework,
    get_global_ab_framework,
)

__all__ = [
    "ModuleStatus",
    "ModuleMetadata",
    "ModuleRegistry",
    "get_global_registry",
    "LoadedModule",
    "ModuleLoader",
    "get_global_loader",
    "DependencyType",
    "Dependency",
    "ModuleCombination",
    "ModuleComposer",
    "get_global_composer",
    "ExperimentStatus",
    "Variant",
    "MetricValue",
    "ExperimentResult",
    "Experiment",
    "ABTestFramework",
    "get_global_ab_framework",
]

__version__ = "1.0.0"
