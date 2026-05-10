"""
动态模块加载器
从文件系统动态加载Python模块，处理导入、初始化和资源清理
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Type, Callable, Set
from pathlib import Path
import importlib
import importlib.util
import sys
import gc
import logging
from datetime import datetime

from .registry import ModuleMetadata, ModuleStatus, get_global_registry

logger = logging.getLogger(__name__)


@dataclass
class LoadedModule:
    """已加载的模块信息"""
    module_name: str
    module_path: str
    module: Any
    metadata: ModuleMetadata
    loaded_at: datetime
    initialized: bool = False


class ModuleLoader:
    """动态模块加载器"""

    def __init__(self, module_paths: Optional[List[Path]] = None):
        """
        初始化模块加载器

        Args:
            module_paths: 模块搜索路径列表
        """
        self._module_paths: List[Path] = module_paths or []
        self._loaded_modules: Dict[str, LoadedModule] = {}
        self._module_registry = get_global_registry()

    def add_module_path(self, path: Path) -> None:
        """
        添加模块搜索路径

        Args:
            path: 要添加的路径
        """
        if path not in self._module_paths:
            self._module_paths.append(path)
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
            logger.info(f"添加模块搜索路径: {path}")

    def remove_module_path(self, path: Path) -> None:
        """
        移除模块搜索路径

        Args:
            path: 要移除的路径
        """
        if path in self._module_paths:
            self._module_paths.remove(path)
            if str(path) in sys.path:
                sys.path.remove(str(path))
            logger.info(f"移除模块搜索路径: {path}")

    def load_module_from_file(self, file_path: Path,
                              module_name: Optional[str] = None) -> Optional[LoadedModule]:
        """
        从文件加载模块

        Args:
            file_path: Python文件路径
            module_name: 模块名称（可选，自动从文件名推断）

        Returns:
            加载的模块信息，失败返回 None
        """
        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return None

        if file_path.suffix != '.py':
            logger.error(f"不是Python文件: {file_path}")
            return None

        if not module_name:
            module_name = file_path.stem

        if module_name in self._loaded_modules:
            logger.warning(f"模块 {module_name} 已加载，将重新加载")
            self.unload_module(module_name)

        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                logger.error(f"无法创建模块规范: {file_path}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            metadata = self._extract_metadata(module, module_name, str(file_path))
            self._module_registry.register(metadata)

            loaded_module = LoadedModule(
                module_name=module_name,
                module_path=str(file_path),
                module=module,
                metadata=metadata,
                loaded_at=datetime.now()
            )
            self._loaded_modules[module_name] = loaded_module

            logger.info(f"成功加载模块: {module_name} from {file_path}")
            return loaded_module

        except Exception as e:
            logger.error(f"加载模块失败: {file_path}, 错误: {e}", exc_info=True)
            if module_name in sys.modules:
                del sys.modules[module_name]
            return None

    def load_module_from_directory(self, directory: Path,
                                   recursive: bool = False) -> List[LoadedModule]:
        """
        从目录加载所有Python模块

        Args:
            directory: 目录路径
            recursive: 是否递归加载子目录

        Returns:
            加载的模块列表
        """
        if not directory.exists() or not directory.is_dir():
            logger.error(f"目录不存在: {directory}")
            return []

        loaded_modules = []
        pattern = "**/*.py" if recursive else "*.py"

        for file_path in directory.glob(pattern):
            if file_path.name.startswith('_'):
                continue
            loaded = self.load_module_from_file(file_path)
            if loaded:
                loaded_modules.append(loaded)

        return loaded_modules

    def initialize_module(self, module_name: str,
                          config: Optional[Dict[str, Any]] = None) -> bool:
        """
        初始化已加载的模块

        Args:
            module_name: 模块名称
            config: 初始化配置

        Returns:
            初始化是否成功
        """
        if module_name not in self._loaded_modules:
            logger.error(f"模块未加载: {module_name}")
            return False

        loaded_module = self._loaded_modules[module_name]

        try:
            if hasattr(loaded_module.module, 'initialize'):
                init_func = loaded_module.module.initialize
                if config:
                    init_func(**config)
                else:
                    init_func()

            loaded_module.initialized = True
            loaded_module.metadata.status = ModuleStatus.ACTIVE
            loaded_module.metadata.updated_at = datetime.now()

            logger.info(f"模块初始化成功: {module_name}")
            return True

        except Exception as e:
            logger.error(f"模块初始化失败: {module_name}, 错误: {e}", exc_info=True)
            loaded_module.metadata.status = ModuleStatus.ERROR
            return False

    def unload_module(self, module_name: str) -> bool:
        """
        卸载模块

        Args:
            module_name: 模块名称

        Returns:
            卸载是否成功
        """
        if module_name not in self._loaded_modules:
            logger.warning(f"模块未加载: {module_name}")
            return False

        loaded_module = self._loaded_modules[module_name]

        try:
            if hasattr(loaded_module.module, 'shutdown'):
                loaded_module.module.shutdown()

            if module_name in sys.modules:
                del sys.modules[module_name]

            for name in list(sys.modules.keys()):
                if name.startswith(f"{module_name}."):
                    del sys.modules[name]

            self._module_registry.update_status(module_name, ModuleStatus.INACTIVE)
            del self._loaded_modules[module_name]

            gc.collect()

            logger.info(f"模块卸载成功: {module_name}")
            return True

        except Exception as e:
            logger.error(f"模块卸载失败: {module_name}, 错误: {e}", exc_info=True)
            return False

    def reload_module(self, module_name: str) -> Optional[LoadedModule]:
        """
        重新加载模块

        Args:
            module_name: 模块名称

        Returns:
            重新加载的模块信息，失败返回 None
        """
        if module_name not in self._loaded_modules:
            logger.error(f"模块未加载: {module_name}")
            return None

        loaded_module = self._loaded_modules[module_name]
        file_path = Path(loaded_module.module_path)

        self.unload_module(module_name)
        return self.load_module_from_file(file_path, module_name)

    def get_loaded_module(self, module_name: str) -> Optional[LoadedModule]:
        """
        获取已加载的模块

        Args:
            module_name: 模块名称

        Returns:
            模块信息，不存在返回 None
        """
        return self._loaded_modules.get(module_name)

    def list_loaded_modules(self) -> List[LoadedModule]:
        """
        列出所有已加载的模块

        Returns:
            模块信息列表
        """
        return list(self._loaded_modules.values())

    def _extract_metadata(self, module: Any, module_name: str,
                          module_path: str) -> ModuleMetadata:
        """
        从模块中提取元数据

        Args:
            module: Python模块对象
            module_name: 模块名称
            module_path: 模块文件路径

        Returns:
            模块元数据
        """
        metadata = ModuleMetadata(
            name=module_name,
            version=getattr(module, '__version__', '1.0.0'),
            description=getattr(module, '__doc__', f'Module {module_name}'),
            author=getattr(module, '__author__', 'Unknown'),
            dependencies=getattr(module, '__dependencies__', []),
            tags=set(getattr(module, '__tags__', [])),
            config=getattr(module, '__config__', {})
        )

        if hasattr(module, 'ModuleClass'):
            metadata.module_class = getattr(module, 'ModuleClass')

        return metadata

    def clear(self) -> None:
        """清空所有已加载的模块"""
        for module_name in list(self._loaded_modules.keys()):
            self.unload_module(module_name)
        self._loaded_modules.clear()
        logger.info("所有模块已清空")


_global_loader: Optional[ModuleLoader] = None


def get_global_loader() -> ModuleLoader:
    """获取全局模块加载器"""
    global _global_loader
    if _global_loader is None:
        _global_loader = ModuleLoader()
    return _global_loader
