"""
core 根级代理包
将 from core.xxx import ... 转发到 src.core.xxx
解决 monitor/、service/、scripts/ 等使用 `from core.xxx import` 时找不到模块的问题。
"""

import sys
from pathlib import Path

# 确保 src/ 在 sys.path 中，使 from src.core... 可以找到
_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# 将 src.core 的所有属性代理到本包
from src.core.config import (  # noqa: F401, E402
    ROOT_DIR,
    BASE_DIR,
    DATA_DIR,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    RESULTS_DIR,
    MODELS_DIR,
    LOGS_DIR,
    DATA_SOURCES,
    PL5_CONFIG,
    MODEL_CONFIG,
    TRAINING_CONFIG,
    setup_logging,
)

from src.core.utils import (  # noqa: F401, E402
    logger,
    log_execution_time,
    log_exception,
)
