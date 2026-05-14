"""
模块注册中心
管理模块元数据、注册、注销、查询和版本管理
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ModuleStatus(Enum):
    """模块状态枚举"""

    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ERROR = "error"


@dataclass
class ModuleMetadata:
    """模块元数据"""

    name: str
    version: str
    description: str
    author: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    dependencies: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    status: ModuleStatus = ModuleStatus.REGISTERED
    config: Dict[str, Any] = field(default_factory=dict)
    module_class: Optional[type] = None
    module_instance: Optional[Any] = None

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = ModuleStatus(self.status)


class ModuleRegistry:
    """模块注册中心"""

    def __init__(self):
        self._modules: Dict[str, ModuleMetadata] = {}
        self._version_index: Dict[str, Dict[str, ModuleMetadata]] = {}
        self._tag_index: Dict[str, Set[str]] = {}

    def register(self, metadata: ModuleMetadata) -> bool:
        """
        注册模块

        Args:
            metadata: 模块元数据

        Returns:
            注册是否成功
        """
        if metadata.name in self._modules:
            logger.warning(f"模块 {metadata.name} 已存在，将被覆盖")

        self._modules[metadata.name] = metadata

        if metadata.name not in self._version_index:
            self._version_index[metadata.name] = {}
        self._version_index[metadata.name][metadata.version] = metadata

        for tag in metadata.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(metadata.name)

        logger.info(f"模块 {metadata.name} v{metadata.version} 注册成功")
        return True

    def unregister(self, name: str, version: Optional[str] = None) -> bool:
        """
        注销模块

        Args:
            name: 模块名称
            version: 模块版本（可选，不传则注销所有版本）

        Returns:
            注销是否成功
        """
        if name not in self._modules:
            logger.warning(f"模块 {name} 不存在")
            return False

        if version:
            if version not in self._version_index.get(name, {}):
                logger.warning(f"模块 {name} v{version} 不存在")
                return False

            del self._version_index[name][version]
            if not self._version_index[name]:
                del self._version_index[name]
                del self._modules[name]
        else:
            if name in self._version_index:
                del self._version_index[name]
            del self._modules[name]

        for tag in self._tag_index:
            if name in self._tag_index[tag]:
                self._tag_index[tag].remove(name)

        logger.info(f"模块 {name} 注销成功")
        return True

    def get(
        self, name: str, version: Optional[str] = None
    ) -> Optional[ModuleMetadata]:
        """
        获取模块

        Args:
            name: 模块名称
            version: 模块版本（可选，不传则获取最新版本）

        Returns:
            模块元数据，不存在则返回 None
        """
        if name not in self._modules:
            return None

        if version:
            return self._version_index.get(name, {}).get(version)

        return self._modules[name]

    def list_modules(
        self, tag: Optional[str] = None, status: Optional[ModuleStatus] = None
    ) -> List[ModuleMetadata]:
        """
        列出所有模块

        Args:
            tag: 按标签过滤（可选）
            status: 按状态过滤（可选）

        Returns:
            模块元数据列表
        """
        modules = list(self._modules.values())

        if tag and tag in self._tag_index:
            module_names = self._tag_index[tag]
            modules = [m for m in modules if m.name in module_names]

        if status:
            modules = [m for m in modules if m.status == status]

        return sorted(modules, key=lambda m: m.name)

    def update_status(self, name: str, status: ModuleStatus) -> bool:
        """
        更新模块状态

        Args:
            name: 模块名称
            status: 新状态

        Returns:
            更新是否成功
        """
        if name not in self._modules:
            logger.warning(f"模块 {name} 不存在")
            return False

        self._modules[name].status = status
        self._modules[name].updated_at = datetime.now()
        logger.info(f"模块 {name} 状态更新为 {status.value}")
        return True

    def get_versions(self, name: str) -> List[str]:
        """
        获取模块的所有版本

        Args:
            name: 模块名称

        Returns:
            版本号列表
        """
        if name not in self._version_index:
            return []
        return sorted(self._version_index[name].keys())

    def has_module(self, name: str, version: Optional[str] = None) -> bool:
        """
        检查模块是否存在

        Args:
            name: 模块名称
            version: 模块版本（可选）

        Returns:
            模块是否存在
        """
        if name not in self._modules:
            return False
        if version:
            return version in self._version_index.get(name, {})
        return True

    def clear(self) -> None:
        """清空注册中心"""
        self._modules.clear()
        self._version_index.clear()
        self._tag_index.clear()
        logger.info("模块注册中心已清空")


_global_registry: Optional[ModuleRegistry] = None


def get_global_registry() -> ModuleRegistry:
    """获取全局模块注册中心"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ModuleRegistry()
    return _global_registry
