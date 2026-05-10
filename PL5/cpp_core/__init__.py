"""
C++高性能计算核心模块
V5.3 Final: 优先尝试加载C++扩展，失败时回退到Python实现
"""

import logging as _log
import os as _os
import sys as _sys

_logger = _log.getLogger(__name__)

# 尝试导入C++扩展
try:
    # 首先尝试从build目录导入已编译的模块
    _build_dir = _os.path.join(_os.path.dirname(__file__), 'build', 'lib.win-amd64-cpython-312')
    if _os.path.exists(_build_dir) and _build_dir not in _sys.path:
        _sys.path.insert(0, _build_dir)
    
    # 尝试导入C++模块
    from .pl5_core import FeatureCalculator, HMMModel, CopulaModel, benchmark
    CPP_AVAILABLE = True
    _logger.info("[cpp_core] C++ extension loaded successfully — high performance mode")
except Exception as _e:
    # 回退到Python实现
    from .pl5_core import FeatureCalculator, HMMModel, CopulaModel, benchmark
    CPP_AVAILABLE = False
    _logger.info(f"[cpp_core] Using Python fallback (pl5_core.py) — stable mode (reason: {_e})")

__all__ = ["FeatureCalculator", "HMMModel", "CopulaModel", "benchmark", "CPP_AVAILABLE"]
