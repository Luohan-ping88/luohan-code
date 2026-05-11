"""
策略库管理模块
策略存储、检索、版本管理和元数据管理
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum
from datetime import datetime
import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class PolicyStatus(Enum):
    """策略状态枚举"""

    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class PolicyMetadata:
    """策略元数据"""

    name: str
    version: str
    description: str
    author: str
    policy_type: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    dependencies: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    status: PolicyStatus = PolicyStatus.DRAFT
    config: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, float] = field(default_factory=dict)
    policy_object: Optional[Any] = None

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = PolicyStatus(self.status)


class PolicyLibrary:
    """策略库管理类"""

    def __init__(self, storage_path: Optional[Path] = None):
        self._policies: Dict[str, PolicyMetadata] = {}
        self._version_index: Dict[str, Dict[str, PolicyMetadata]] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._type_index: Dict[str, Set[str]] = {}
        self._storage_path = storage_path or Path("./policy_library")
        self._storage_path.mkdir(exist_ok=True, parents=True)

    def add_policy(self, metadata: PolicyMetadata) -> bool:
        """
        添加策略到策略库

        Args:
            metadata: 策略元数据

        Returns:
            添加是否成功
        """
        if metadata.name in self._policies:
            logger.warning(f"策略 {metadata.name} 已存在，将被覆盖")

        self._policies[metadata.name] = metadata

        if metadata.name not in self._version_index:
            self._version_index[metadata.name] = {}
        self._version_index[metadata.name][metadata.version] = metadata

        for tag in metadata.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(metadata.name)

        if metadata.policy_type not in self._type_index:
            self._type_index[metadata.policy_type] = set()
        self._type_index[metadata.policy_type].add(metadata.name)

        logger.info(f"策略 {metadata.name} v{metadata.version} 添加成功")
        return True

    def remove_policy(self, name: str, version: Optional[str] = None) -> bool:
        """
        从策略库移除策略

        Args:
            name: 策略名称
            version: 策略版本（可选，不传则移除所有版本）

        Returns:
            移除是否成功
        """
        if name not in self._policies:
            logger.warning(f"策略 {name} 不存在")
            return False

        if version:
            if version not in self._version_index.get(name, {}):
                logger.warning(f"策略 {name} v{version} 不存在")
                return False

            del self._version_index[name][version]
            if not self._version_index[name]:
                del self._version_index[name]
                self._remove_from_indices(name)
                del self._policies[name]
        else:
            if name in self._version_index:
                del self._version_index[name]
            self._remove_from_indices(name)
            del self._policies[name]

        logger.info(f"策略 {name} 移除成功")
        return True

    def _remove_from_indices(self, name: str) -> None:
        """从所有索引中移除策略"""
        for tag in self._tag_index:
            if name in self._tag_index[tag]:
                self._tag_index[tag].remove(name)

        for policy_type in self._type_index:
            if name in self._type_index[policy_type]:
                self._type_index[policy_type].remove(name)

    def get_policy(self, name: str, version: Optional[str] = None) -> Optional[PolicyMetadata]:
        """
        获取策略

        Args:
            name: 策略名称
            version: 策略版本（可选，不传则获取最新版本）

        Returns:
            策略元数据，不存在则返回 None
        """
        if name not in self._policies:
            return None

        if version:
            return self._version_index.get(name, {}).get(version)

        return self._policies[name]

    def list_policies(
        self, tag: Optional[str] = None, policy_type: Optional[str] = None, status: Optional[PolicyStatus] = None
    ) -> List[PolicyMetadata]:
        """
        列出所有策略

        Args:
            tag: 按标签过滤（可选）
            policy_type: 按类型过滤（可选）
            status: 按状态过滤（可选）

        Returns:
            策略元数据列表
        """
        policies = list(self._policies.values())

        if tag and tag in self._tag_index:
            policy_names = self._tag_index[tag]
            policies = [p for p in policies if p.name in policy_names]

        if policy_type and policy_type in self._type_index:
            policy_names = self._type_index[policy_type]
            policies = [p for p in policies if p.name in policy_names]

        if status:
            policies = [p for p in policies if p.status == status]

        return sorted(policies, key=lambda p: p.name)

    def update_status(self, name: str, status: PolicyStatus) -> bool:
        """
        更新策略状态

        Args:
            name: 策略名称
            status: 新状态

        Returns:
            更新是否成功
        """
        if name not in self._policies:
            logger.warning(f"策略 {name} 不存在")
            return False

        self._policies[name].status = status
        self._policies[name].updated_at = datetime.now()
        logger.info(f"策略 {name} 状态更新为 {status.value}")
        return True

    def update_performance(self, name: str, performance: Dict[str, float]) -> bool:
        """
        更新策略性能指标

        Args:
            name: 策略名称
            performance: 性能指标字典

        Returns:
            更新是否成功
        """
        if name not in self._policies:
            logger.warning(f"策略 {name} 不存在")
            return False

        self._policies[name].performance.update(performance)
        self._policies[name].updated_at = datetime.now()
        logger.info(f"策略 {name} 性能指标已更新")
        return True

    def get_versions(self, name: str) -> List[str]:
        """
        获取策略的所有版本

        Args:
            name: 策略名称

        Returns:
            版本号列表
        """
        if name not in self._version_index:
            return []
        return sorted(self._version_index[name].keys(), reverse=True)

    def has_policy(self, name: str, version: Optional[str] = None) -> bool:
        """
        检查策略是否存在

        Args:
            name: 策略名称
            version: 策略版本（可选）

        Returns:
            策略是否存在
        """
        if name not in self._policies:
            return False
        if version:
            return version in self._version_index.get(name, {})
        return True

    def save_to_disk(self, file_path: Optional[Path] = None) -> None:
        """
        保存策略库到磁盘

        Args:
            file_path: 保存路径（可选）
        """
        save_path = file_path or self._storage_path / "policy_library.pkl"
        with open(save_path, "wb") as f:
            pickle.dump(
                {
                    "policies": self._policies,
                    "version_index": self._version_index,
                    "tag_index": self._tag_index,
                    "type_index": self._type_index,
                },
                f,
            )
        logger.info(f"策略库已保存到 {save_path}")

    def load_from_disk(self, file_path: Optional[Path] = None) -> bool:
        """
        从磁盘加载策略库

        Args:
            file_path: 加载路径（可选）

        Returns:
            加载是否成功
        """
        load_path = file_path or self._storage_path / "policy_library.pkl"
        if not load_path.exists():
            logger.warning(f"策略库文件 {load_path} 不存在")
            return False

        try:
            with open(load_path, "rb") as f:
                data = pickle.load(f)
                self._policies = data["policies"]
                self._version_index = data["version_index"]
                self._tag_index = data["tag_index"]
                self._type_index = data["type_index"]
            logger.info(f"策略库已从 {load_path} 加载")
            return True
        except Exception as e:
            logger.error(f"加载策略库失败: {e}")
            return False

    def clear(self) -> None:
        """清空策略库"""
        self._policies.clear()
        self._version_index.clear()
        self._tag_index.clear()
        self._type_index.clear()
        logger.info("策略库已清空")


_global_library: Optional[PolicyLibrary] = None


def get_global_library(storage_path: Optional[Path] = None) -> PolicyLibrary:
    """获取全局策略库"""
    global _global_library
    if _global_library is None:
        _global_library = PolicyLibrary(storage_path)
    return _global_library
