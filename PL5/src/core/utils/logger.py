#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志管理模块 V7.0
核心设计：
  - 所有运行日志 -> logs/system.log (RotatingFileHandler, 10MB×5)
  - 控制台独立格式 (CleanFormatter)
  - 业务数据JSON -> logs/data/ 子目录
  - 结构化JSON日志 -> logs/system.json.log (追加)
  - get_logger() 返回统一日志器，但不同源的模块名仍可识别
"""

import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

# ── 目录定义 ──────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = LOG_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── 日志文件路径 ──────────────────────────────────────────
SYSTEM_LOG = LOG_DIR / "system.log"  # 主运行日志（轮转）
STRUCTURED_LOG = LOG_DIR / "system.json.log"  # 结构化日志（追加）

# ── Formatter ─────────────────────────────────────────────


class CleanFormatter(logging.Formatter):
    """简化格式 - 用于控制台（纯 ASCII，兼容 GBK 编码）"""

    def format(self, record: logging.LogRecord) -> str:
        time_str = datetime.now().strftime("%H:%M:%S")
        return f"[{time_str}] [{record.levelname}] {record.getMessage()}"


class DetailFormatter(logging.Formatter):
    """详细格式 - 用于文件"""

    def format(self, record: logging.LogRecord) -> str:
        time_str = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        # 使用模块名作为来源标识，若为 PL5.xxx 则截取 xxx 部分
        source = record.name.replace("PL5.", "", 1) if record.name.startswith("PL5.") else record.name
        return f"{time_str} | {record.levelname:8} | {source:20} | {record.getMessage()}"


# ── 根日志器（单例） ──────────────────────────────────────
_ROOT_LOGGER: logging.Logger = None


def _get_root_logger() -> logging.Logger:
    """获取/创建根日志器（全局单例，确保只有一个 RotatingFileHandler）"""
    global _ROOT_LOGGER
    if _ROOT_LOGGER is not None:
        return _ROOT_LOGGER

    # ── PL5 专用日志器 ──
    pl5 = logging.getLogger("PL5")
    pl5.setLevel(logging.INFO)
    pl5.handlers.clear()
    pl5.propagate = False  # 不传播到 Python root logger

    # 控制台 handler（使用 UTF-8 编码避免 GBK 兼容问题）
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(CleanFormatter())
    # Windows 控制台默认为 GBK，强制使用 UTF-8 写入
    import io

    if hasattr(sys.stdout, "buffer"):
        console.setStream(io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))
    pl5.addHandler(console)

    # 文件 handler（轮转）
    file_handler = RotatingFileHandler(SYSTEM_LOG, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(DetailFormatter())
    pl5.addHandler(file_handler)

    # ── Python 根日志器（捕获所有 logger.getLogger 调用）──
    python_root = logging.getLogger()
    # 避免重复添加（可能有第三方库已经设置了 handler）
    has_file = any(
        isinstance(h, RotatingFileHandler) and h.baseFilename == str(SYSTEM_LOG) for h in python_root.handlers
    )
    if not has_file:
        # 添加同一个文件 handler，但使用不同的 formatter（包含 logger name）
        root_fh = RotatingFileHandler(SYSTEM_LOG, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        root_fh.setLevel(logging.WARNING)  # 非 PL5 日志只记录 WARNING 及以上
        root_fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)8s | %(name)-20s | %(message)s"))
        python_root.addHandler(root_fh)

    _ROOT_LOGGER = pl5
    return pl5


# ── 公共 API ──────────────────────────────────────────────


def get_logger(name: str = "main") -> logging.Logger:
    """
    获取统一日志器。
    所有 logger 共享同一个 RotatingFileHandler，写入同一个 system.log。
    """
    root = _get_root_logger()
    # 创建子 logger，继承 root 的 handler
    child = logging.getLogger(f"PL5.{name}")
    child.propagate = True  # 传播到 PL5 根日志器
    child.setLevel(logging.INFO)
    return child


def setup_logging(name: str = None) -> logging.Logger:
    """兼容旧 API：返回与 get_logger 相同的日志器"""
    return get_logger(name or "main")


# ── 业务数据持久化 ─────────────────────────────────────────


def save_data_file(filename: str, data: dict) -> Path:
    """
    将业务数据（预测结果、训练信息等）保存到 logs/data/ 目录。
    返回值：Path 对象

    用法:
        save_data_file('prediction_2026111.json', {...})
        save_data_file('training_info.json', {...})
    """
    path = DATA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    return path


def read_data_file(filename: str) -> dict:
    """从 logs/data/ 读取业务数据 JSON"""
    path = DATA_DIR / filename
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 结构化日志写入 ─────────────────────────────────────────


def log_structured(level: str, module: str, message: str, **extra):
    """
    写入结构化 JSON 日志（追加到 system.json.log）。
    便于后续自动化分析和监控。

    Args:
        level: INFO / WARNING / ERROR
        module: 来源模块名（如 scheduler, orchestrator）
        message: 日志正文
        **extra: 额外字段（如 task_name, duration, record_count 等）
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level.upper(),
        "module": module,
        "message": message,
        **extra,
    }
    try:
        with open(STRUCTURED_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass  # 不影响主流程


# ── 装饰器 ────────────────────────────────────────────────

import functools
import asyncio


def log_exception(func_name: str):
    """异常装饰器"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = get_logger()
                logger.error(f"[{func_name}] 异常: {str(e)}")
                raise

        return wrapper

    return decorator


def log_execution_time(func_name: str):
    """计时装饰器（支持同步和异步函数）"""

    def decorator(func):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = datetime.now()
            try:
                return func(*args, **kwargs)
            finally:
                dur = (datetime.now() - start).total_seconds()
                logger = get_logger()
                logger.info(f"[⏱ {func_name}] {dur:.2f}秒")

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = datetime.now()
            try:
                return await func(*args, **kwargs)
            finally:
                dur = (datetime.now() - start).total_seconds()
                logger = get_logger()
                logger.info(f"[⏱ {func_name}] {dur:.2f}秒")

        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# ── 兼容旧 API ────────────────────────────────────────────


def log_performance_metric(metric_name, value, unit=""):
    """记录性能指标（兼容旧版）"""
    get_logger().info(f"Performance metric: {metric_name} = {value} {unit}")
    log_structured("INFO", "metrics", f"{metric_name}={value}{unit}", metric=metric_name, value=value, unit=unit)


def log_system_status(status_message):
    """记录系统状态（兼容旧版）"""
    get_logger().info(f"System status: {status_message}")


# ── 初始化 ────────────────────────────────────────────────
logger = get_logger("main")
