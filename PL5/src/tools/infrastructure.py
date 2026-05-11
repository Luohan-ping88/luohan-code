"""
PL5 基础设施层工具集 (Layer 1)

提供数据加载、缓存管理、配置读取、日志记录、数据验证等基础能力，
为上层核心工具和应用工具提供可靠的基础设施支撑。

包含工具:
- DataLoaderTool:  数据加载与预处理
- CacheTool:        缓存管理（TTL + LRU）
- ConfigTool:       配置读取与环境变量解析
- LoggerTool:       结构化日志记录
- ValidationTool:   数据验证与清洗
"""

import os
import time
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from collections import OrderedDict

import pandas as pd
import numpy as np

from .base import (
    BaseTool,
    ToolResult,
    ToolContext,
    ToolLayer,
    ErrorInfo,
    register_tool,
)

# ================================================================
# 1. DataLoaderTool — 数据加载与预处理
# ================================================================


@register_tool("data_loader", tags=["data", "infrastructure"])
class DataLoaderTool(BaseTool):
    """数据加载与预处理工具

    支持从多种来源加载数据（文件路径、DataFrame、字典），
    自动检测文件格式（CSV/JSON/Pickle/Excel），并提供基本的数据预处理能力：
    缺失值填充、类型转换、重复值处理。

    输入参数:
        path_or_data: 数据源，支持以下类型:
            - str / Path: 文件路径（自动检测格式）
            - pd.DataFrame: 直接使用
            - dict: 转换为 DataFrame
        preprocess: 是否执行基本预处理（默认 True）

    输出:
        data: 加载并预处理后的 pd.DataFrame
        stats: 数据统计信息字典
    """

    name = "data_loader"
    description = "数据加载与预处理工具：自动格式检测、缺失值处理、类型转换"
    layer = ToolLayer.INFRASTRUCTURE
    tags = ["data", "infrastructure", "preprocessing"]

    _SUPPORTED_EXTENSIONS = {
        ".csv": "csv",
        ".json": "json",
        ".pkl": "pickle",
        ".pickle": "pickle",
        ".xlsx": "excel",
        ".xls": "excel",
        ".parquet": "parquet",
        ".tsv": "tsv",
        ".txt": "text",
    }

    input_schema = {
        "type": "object",
        "properties": {
            "path_or_data": {
                "type": ["string", "object"],
                "description": "文件路径(str/Path)、pd.DataFrame 或 dict",
            },
            "preprocess": {
                "type": "boolean",
                "description": "是否执行基本预处理（缺失值填充、重复值删除）",
                "default": True,
            },
        },
        "required": ["path_or_data"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "data": {"type": "object", "description": "预处理后的 DataFrame"},
            "stats": {"type": "object", "description": "数据统计信息"},
            "source_type": {"type": "string", "description": "数据源类型"},
        },
    }

    def _detect_format(self, path: Path) -> Optional[str]:
        ext = path.suffix.lower()
        return self._SUPPORTED_EXTENSIONS.get(ext)

    def _load_from_file(self, path: Path) -> pd.DataFrame:
        fmt = self._detect_format(path)
        if not fmt:
            raise ValueError(f"不支持的文件格式: {path.suffix}")

        loaders = {
            "csv": lambda p: pd.read_csv(p),
            "tsv": lambda p: pd.read_csv(p, sep="\t"),
            "json": lambda p: pd.read_json(p),
            "pickle": lambda p: pd.read_pickle(p),
            "excel": lambda p: pd.read_excel(p),
            "parquet": lambda p: pd.read_parquet(p),
            "text": lambda p: pd.read_csv(p, sep=None, engine="python"),
        }
        return loaders[fmt](path)

    def _preprocess(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        report = {
            "original_rows": len(df),
            "original_cols": len(df.columns),
            "missing_before": int(df.isnull().sum().sum()),
            "duplicates_before": int(df.duplicated().sum()),
            "actions": [],
        }

        if df.empty:
            report["actions"].append("空数据框，跳过预处理")
            return df.copy(), report

        result = df.copy()

        numeric_cols = result.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0 and result[numeric_cols].isnull().any().any():
            for col in numeric_cols:
                if result[col].isnull().any():
                    median_val = result[col].median()
                    result[col] = result[col].fillna(median_val)
            report["actions"].append(f"数值列缺失值用中位数填充 ({len(numeric_cols)} 列)")

        non_numeric_cols = result.select_dtypes(exclude=[np.number]).columns
        if len(non_numeric_cols) > 0 and result[non_numeric_cols].isnull().any().any():
            for col in non_numeric_cols:
                if result[col].isnull().any():
                    mode_val = result[col].mode()
                    fill_value = mode_val.iloc[0] if len(mode_val) > 0 else "unknown"
                    result[col] = result[col].fillna(fill_value)
            report["actions"].append(f"非数值列缺失值用众数填充 ({len(non_numeric_cols)} 列)")

        dup_count = result.duplicated().sum()
        if dup_count > 0:
            result = result.drop_duplicates()
            report["actions"].append(f"删除 {dup_count} 行重复值")

        for col in result.select_dtypes(include=[np.number]).columns:
            if result[col].dtype == object:
                try:
                    result[col] = pd.to_numeric(result[col], errors="coerce")
                except Exception:
                    pass

        report["processed_rows"] = len(result)
        report["processed_cols"] = len(result.columns)
        report["missing_after"] = int(result.isnull().sum().sum())
        report["duplicates_after"] = int(result.duplicated().sum())

        return result, report

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        path_or_data = kwargs.get("path_or_data")
        preprocess = kwargs.get("preprocess", True)

        if path_or_data is None:
            return ToolResult.error_result(
                "path_or_data 参数不能为 None",
                code="DATA_LOADER_MISSING_INPUT",
            )

        source_type = "unknown"
        df = None

        try:
            if isinstance(path_or_data, pd.DataFrame):
                df = path_or_data.copy()
                source_type = "dataframe"
            elif isinstance(path_or_data, dict):
                df = pd.DataFrame(path_or_data)
                source_type = "dict"
            elif isinstance(path_or_data, (str, Path)):
                path = Path(path_or_data)
                if not path.exists():
                    return ToolResult.error_result(
                        f"文件不存在: {path}",
                        code="DATA_LOADER_FILE_NOT_FOUND",
                    )
                df = self._load_from_file(path)
                source_type = f"file:{self._detect_format(path)}"
            else:
                return ToolResult.error_result(
                    f"不支持的数据源类型: {type(path_or_data).__name__}",
                    code="DATA_LOADER_UNSUPPORTED_TYPE",
                )
        except Exception as e:
            ctx.log.exception("[data_loader] 加载数据失败")
            return ToolResult.error_result(
                f"数据加载失败: {str(e)}",
                code="DATA_LOADER_LOAD_ERROR",
            )

        if preprocess:
            df_cleaned, stats = self._preprocess(df)
        else:
            df_cleaned = df
            stats = {
                "original_rows": len(df),
                "original_cols": len(df.columns),
                "missing_before": int(df.isnull().sum().sum()),
                "duplicates_before": int(df.duplicated().sum()),
                "actions": ["预处理已禁用"],
                "processed_rows": len(df),
                "processed_cols": len(df.columns),
                "missing_after": int(df.isnull().sum().sum()),
                "duplicates_after": int(df.duplicated().sum()),
            }

        ctx.record_metric("data_loader.rows_loaded", len(df_cleaned))
        ctx.record_metric("data_loader.cols_loaded", len(df_cleaned.columns))
        ctx.set("last_loaded_data_shape", (len(df_cleaned), len(df_cleaned.columns)))

        return ToolResult.success_result(
            data={
                "data": df_cleaned,
                "stats": stats,
                "source_type": source_type,
            },
            tool="data_loader",
            rows=len(df_cleaned),
            cols=len(df_cleaned.columns),
            preprocessed=preprocess,
        )


# ================================================================
# 2. CacheTool — 缓存管理（TTL + LRU）
# ================================================================


class _LRUCache(OrderedDict):
    """内部 LRU 缓存实现，基于 OrderedDict"""

    def __init__(self, maxsize: int = 128):
        super().__init__()
        self.maxsize = maxsize

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            oldest = next(iter(self))
            super().__delitem__(oldest)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value


@register_tool("cache", tags=["cache", "infrastructure"])
class CacheTool(BaseTool):
    """缓存管理工具

    基于 ToolContext.cache 的内存缓存管理，支持以下操作:
    - set:    设置缓存条目（支持 TTL 过期时间）
    - get:    获取缓存条目（自动检查过期）
    - delete: 删除指定条目
    - clear:  清空所有缓存
    - keys:   列出所有有效键
    - stats:  返回缓存统计信息

    内部使用 LRU 淘汰策略，最大条目数可配置。
    TTL 过期机制确保缓存数据的时效性。

    输入参数:
        operation: 操作类型 (set/get/delete/clear/keys/stats)
        key:       缓存键名（set/get/delete 时必填）
        value:     缓存值（set 时必填）
        ttl:       过期时间秒数（set 时可选，0 或 None 表示永不过期）
        max_size:  LRU 最大容量（可选，默认 128）

    输出:
        根据操作类型返回对应结果或错误信息
    """

    name = "cache"
    description = "缓存管理工具：set/get/delete/clear/keys/stats，支持 TTL 和 LRU 淘汰"
    layer = ToolLayer.INFRASTRUCTURE
    tags = ["cache", "infrastructure", "memory"]

    _DEFAULT_MAX_SIZE = 128

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["set", "get", "delete", "clear", "keys", "stats"],
                "description": "缓存操作类型",
            },
            "key": {
                "type": "string",
                "description": "缓存键名",
            },
            "value": {
                "description": "缓存值（任意可序列化对象）",
            },
            "ttl": {
                "type": "number",
                "description": "过期时间（秒），0 或 None 表示永不过期",
                "default": None,
            },
            "max_size": {
                "type": "integer",
                "description": "LRU 最大容量",
                "default": 128,
            },
        },
        "required": ["operation"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "result": {"description": "操作结果"},
            "success": {"type": "boolean"},
        },
    }

    def _ensure_cache_store(self, ctx: ToolContext, max_size: int = None) -> Dict:
        if ctx.cache is None:
            ctx.cache = {}
        cache_meta_key = "__cache_metadata__"
        if cache_meta_key not in ctx.cache:
            ctx.cache[cache_meta_key] = {
                "store": _LRUCache(maxsize=max_size or self._DEFAULT_MAX_SIZE),
                "entries": {},
            }
        meta = ctx.cache[cache_meta_key]
        if max_size is not None and meta["store"].maxsize != max_size:
            new_store = _LRUCache(maxsize=max_size)
            for k, v in meta["store"].items():
                new_store[k] = v
            meta["store"] = new_store
        return meta

    def _is_expired(self, entry: Dict) -> bool:
        ttl = entry.get("ttl")
        if ttl is None or ttl <= 0:
            return False
        created = entry.get("created_at", 0)
        return (time.time() - created) > ttl

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        operation = kwargs.get("operation", "")
        key = kwargs.get("key")
        value = kwargs.get("value")
        ttl = kwargs.get("ttl")
        max_size = kwargs.get("max_size", self._DEFAULT_MAX_SIZE)

        valid_ops = {"set", "get", "delete", "clear", "keys", "stats"}
        if operation not in valid_ops:
            return ToolResult.error_result(
                f"无效的操作类型: '{operation}'，有效值: {valid_ops}",
                code="CACHE_INVALID_OPERATION",
            )

        meta = self._ensure_cache_store(ctx, max_size=max_size)
        store = meta["store"]
        entries = meta["entries"]
        now = time.time()

        if operation == "set":
            if not key:
                return ToolResult.error_result(
                    "set 操作需要提供 key 参数",
                    code="CACHE_MISSING_KEY",
                )
            if value is None and "value" not in kwargs:
                return ToolResult.error_result(
                    "set 操作需要提供 value 参数",
                    code="CACHE_MISSING_VALUE",
                )
            parsed_ttl = float(ttl) if ttl is not None else None
            entry_info = {
                "value": value,
                "created_at": now,
                "ttl": parsed_ttl,
                "access_count": 0,
            }
            store[key] = key
            entries[key] = entry_info
            ctx.log.debug(f"[cache] SET {key} (ttl={parsed_ttl})")
            return ToolResult.success_result(
                data={"operation": "set", "key": key, "cached": True},
                tool="cache",
                op="set",
            )

        elif operation == "get":
            if not key:
                return ToolResult.error_result(
                    "get 操作需要提供 key 参数",
                    code="CACHE_MISSING_KEY",
                )
            if key not in entries:
                return ToolResult.success_result(
                    data={"operation": "get", "key": key, "found": False, "value": None},
                    tool="cache",
                    hit=False,
                )
            entry = entries[key]
            if self._is_expired(entry):
                del entries[key]
                if key in store:
                    del store[key]
                ctx.log.debug(f"[cache] GET {key} => 已过期")
                return ToolResult.success_result(
                    data={"operation": "get", "key": key, "found": False, "expired": True, "value": None},
                    tool="cache",
                    hit=False,
                )
            entry["access_count"] = entry.get("access_count", 0) + 1
            if key in store:
                store.move_to_end(key)
            ctx.log.debug(f"[cache] GET {key} => 命中")
            return ToolResult.success_result(
                data={"operation": "get", "key": key, "found": True, "value": entry["value"]},
                tool="cache",
                hit=True,
            )

        elif operation == "delete":
            if not key:
                return ToolResult.error_result(
                    "delete 操作需要提供 key 参数",
                    code="CACHE_MISSING_KEY",
                )
            existed = key in entries
            if existed:
                del entries[key]
                if key in store:
                    del store[key]
            return ToolResult.success_result(
                data={"operation": "delete", "key": key, "deleted": existed},
                tool="cache",
                op="delete",
            )

        elif operation == "clear":
            count = len(entries)
            entries.clear()
            store.clear()
            ctx.log.info(f"[cache] CLEAR => 清除 {count} 条目")
            return ToolResult.success_result(
                data={"operation": "clear", "cleared_count": count},
                tool="cache",
                op="clear",
            )

        elif operation == "keys":
            expired_keys = []
            valid_keys = []
            for k, entry in entries.items():
                if self._is_expired(entry):
                    expired_keys.append(k)
                else:
                    valid_keys.append(k)
            for ek in expired_keys:
                del entries[ek]
                if ek in store:
                    del store[ek]
            return ToolResult.success_result(
                data={
                    "operation": "keys",
                    "keys": valid_keys,
                    "total_valid": len(valid_keys),
                    "total_expired_removed": len(expired_keys),
                },
                tool="cache",
                op="keys",
            )

        elif operation == "stats":
            total_entries = len(entries)
            expired_count = sum(1 for e in entries.values() if self._is_expired(e))
            valid_count = total_entries - expired_count
            total_access = sum(e.get("access_count", 0) for e in entries.values())
            stats_data = {
                "operation": "stats",
                "total_entries": total_entries,
                "valid_entries": valid_count,
                "expired_entries": expired_count,
                "lru_max_size": store.maxsize,
                "lru_utilization": round(len(store) / store.maxsize, 4) if store.maxsize > 0 else 0,
                "total_access_count": total_access,
                "keys_with_ttl": sum(1 for e in entries.values() if e.get("ttl") is not None and e["ttl"] > 0),
            }
            return ToolResult.success_result(data=stats_data, tool="cache", op="stats")

        return ToolResult.error_result(
            f"未处理的操作: {operation}",
            code="CACHE_UNHANDLED_OP",
        )


# ================================================================
# 3. ConfigTool — 配置读取与环境变量解析
# ================================================================


@register_tool("config", tags=["config", "infrastructure"])
class ConfigTool(BaseTool):
    """配置读取与环境变量解析工具

    从 ToolContext.config 中读取配置（兼容 ModelConfig 和普通 dict），
    支持环境变量覆盖（PL5_ 前缀）、嵌套键访问和配置验证。

    功能:
    - 嵌套键访问: 如 "stacking.n_estimators" 可访问 config['stacking']['n_estimators']
    - 环境变量覆盖: PL5_STACKING__N_ESTIMATORS=200 会覆盖 stacking.n_estimators
    - 配置片段获取: 通过 section 参数获取整个配置子树
    - 默认值回退: 当配置不存在时返回指定的默认值

    输入参数:
        key_path:  配置键路径，点号分隔（如 "stacking.base_config.n_estimators"）
                   为 None 或省略时返回完整配置摘要
        section:   配置节名称（如 "stacking"、"hmm"、"training"）
                   与 key_path 互斥，优先使用 key_path
        default:   默认值（当 key 不存在时返回）
        required:  是否要求键必须存在（默认 False）

    输出:
        配置值或配置片段
    """

    name = "config"
    description = "配置读取工具：嵌套键访问、环境变量覆盖、配置验证与默认值回退"
    layer = ToolLayer.INFRASTRUCTURE
    tags = ["config", "infrastructure", "settings"]

    _ENV_PREFIX = "PL5_"

    input_schema = {
        "type": "object",
        "properties": {
            "key_path": {
                "type": "string",
                "description": "点号分隔的嵌套配置路径，如 'stacking.n_estimators'",
            },
            "section": {
                "type": "string",
                "description": "配置节名称，如 'stacking'、'hmm'",
            },
            "default": {
                "description": "键不存在时的默认回退值",
            },
            "required": {
                "type": "boolean",
                "description": "是否要求键必须存在",
                "default": False,
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "value": {"description": "查询到的配置值"},
            "key_path": {"type": "string"},
            "found": {"type": "boolean"},
            "source": {"type": "string", "description": "值来源 (config/env/default)"},
        },
    }

    def _resolve_env_override(self, key_path: str) -> Tuple[Optional[str], Any]:
        parts = key_path.split(".")
        env_var_name = self._ENV_PREFIX + "__".join(p.upper() for p in parts)
        env_value = os.environ.get(env_var_name)
        if env_value is None:
            return None, None
        parsed = self._parse_env_value(env_value)
        return env_var_name, parsed

    @staticmethod
    def _parse_env_value(value: str) -> Any:
        if value.lower() in ("true", "yes", "on"):
            return True
        if value.lower() in ("false", "no", "off"):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def _navigate_config(self, config: Any, keys: List[str]) -> Tuple[Any, bool]:
        current = config
        for k in keys:
            if current is None:
                return None, False
            if hasattr(current, "get") and not isinstance(current, dict):
                current = current.get(k)
                if current is None:
                    return None, False
            elif isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None, False
        return current, True

    def _get_section(self, config: Any, section_name: str) -> Any:
        if hasattr(config, "section"):
            return config.section(section_name)
        if hasattr(config, "get") and not isinstance(config, dict):
            val = config.get(section_name)
            return val if val is not None else {}
        if isinstance(config, dict):
            return config.get(section_name, {})
        return {}

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        key_path = kwargs.get("key_path")
        section = kwargs.get("section")
        default = kwargs.get("default", None)
        required = kwargs.get("required", False)

        if ctx.config is None:
            if required:
                return ToolResult.error_result(
                    "配置未初始化且该键标记为 required=True",
                    code="CONFIG_NOT_INITIALIZED",
                )
            return ToolResult.success_result(
                data={
                    "value": default,
                    "key_path": key_path or section,
                    "found": False,
                    "source": "default",
                    "warning": "ctx.config 为 None，返回默认值",
                },
                tool="config",
            )

        if key_path and section:
            ctx.log.warning("[config] 同时指定了 key_path 和 section，优先使用 key_path")

        if key_path:
            keys = key_path.split(".")
            env_name, env_val = self._resolve_env_override(key_path)
            if env_val is not None:
                ctx.log.debug(f"[config] 环境变量覆盖: {env_name} => {key_path}")
                return ToolResult.success_result(
                    data={
                        "value": env_val,
                        "key_path": key_path,
                        "found": True,
                        "source": "env",
                        "env_variable": env_name,
                    },
                    tool="config",
                )

            value, found = self._navigate_config(ctx.config, keys)
            if found:
                return ToolResult.success_result(
                    data={
                        "value": value,
                        "key_path": key_path,
                        "found": True,
                        "source": "config",
                    },
                    tool="config",
                )
            else:
                if required:
                    return ToolResult.error_result(
                        f"必需的配置键不存在: '{key_path}'",
                        code="CONFIG_KEY_NOT_FOUND",
                    )
                return ToolResult.success_result(
                    data={
                        "value": default,
                        "key_path": key_path,
                        "found": False,
                        "source": "default",
                    },
                    tool="config",
                )

        elif section:
            section_data = self._get_section(ctx.config, section)
            return ToolResult.success_result(
                data={
                    "value": section_data,
                    "section": section,
                    "found": bool(section_data),
                    "source": "config",
                },
                tool="config",
            )

        else:
            summary = {}
            if hasattr(ctx.config, "summary"):
                summary = ctx.config.summary()
            elif hasattr(ctx.config, "raw"):
                summary = {"raw_keys": list(ctx.config.raw.keys())}
            elif isinstance(ctx.config, dict):
                summary = {"keys": list(ctx.config.keys())}
            else:
                summary = {"type": type(ctx.config).__name__}

            return ToolResult.success_result(
                data={
                    "value": summary,
                    "found": True,
                    "source": "config_summary",
                },
                tool="config",
            )


# ================================================================
# 4. LoggerTool — 结构化日志记录
# ================================================================


@register_tool("logger", tags=["logging", "infrastructure"])
class LoggerTool(BaseTool):
    """结构化日志记录工具

    记录结构化日志到 ToolContext.logger，支持不同日志级别，
    自动附加上下文信息（时间戳、工具名、用户ID 等），
    并可选持久化到文件。

    日志格式:
        [LEVEL] [timestamp] [tool=user_tool] [user_id=xxx] message {extra}

    输入参数:
        message: 日志消息内容
        level:   日志级别 (debug/info/warning/error/critical)
        extra:   额外的结构化字段（dict），会附加到日志中
        persist: 是否同时写入持久化日志文件（默认 False）

    输出:
        日志确认信息，包含时间戳和级别
    """

    name = "logger"
    description = "结构化日志记录工具：多级别日志、上下文附加、可选文件持久化"
    layer = ToolLayer.INFRASTRUCTURE
    tags = ["logging", "infrastructure", "monitoring"]

    _VALID_LEVELS = {"debug", "info", "warning", "error", "critical"}
    _LEVEL_MAP = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    input_schema = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "日志消息内容",
            },
            "level": {
                "type": "string",
                "enum": ["debug", "info", "warning", "error", "critical"],
                "description": "日志级别",
                "default": "info",
            },
            "extra": {
                "type": "object",
                "description": "额外的结构化字段",
            },
            "persist": {
                "type": "boolean",
                "description": "是否写入持久化文件",
                "default": False,
            },
        },
        "required": ["message"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "logged": {"type": "boolean"},
            "level": {"type": "string"},
            "timestamp": {"type": "number"},
            "message": {"type": "string"},
        },
    }

    def _build_log_message(self, message: str, extra: Dict, ctx: ToolContext) -> str:
        parts = [message]
        context_parts = []
        if ctx.user_id:
            context_parts.append(f"user_id={ctx.user_id}")
        if extra:
            for k, v in extra.items():
                context_parts.append(f"{k}={v}")
        if context_parts:
            parts.append(" {" + ", ".join(context_parts) + "}")
        return "".join(parts)

    def _persist_to_file(self, message: str, level: str, extra: Dict, ctx: ToolContext):
        log_dir = getattr(ctx, "log_dir", None) or os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "tool_logs.jsonl")
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "extra": extra,
            "user_id": ctx.user_id,
        }
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            ctx.log.warning(f"[logger] 持久化写入失败: {e}")

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        message = kwargs.get("message", "")
        level = kwargs.get("level", "info").lower()
        extra = kwargs.get("extra") or {}
        persist = kwargs.get("persist", False)

        if not message:
            return ToolResult.error_result(
                "message 参数不能为空",
                code="LOGGER_EMPTY_MESSAGE",
            )

        if level not in self._VALID_LEVELS:
            return ToolResult.error_result(
                f"无效的日志级别: '{level}'，有效值: {self._VALID_LEVELS}",
                code="LOGGER_INVALID_LEVEL",
            )

        log_message = self._build_log_message(message, extra, ctx)
        log_level = self._LEVEL_MAP[level]

        logger_instance = ctx.log
        logger_instance.log(log_level, log_message)

        if persist:
            self._persist_to_file(message, level, extra, ctx)

        timestamp = time.time()
        ctx.set(
            "last_log_entry",
            {
                "timestamp": timestamp,
                "level": level,
                "message": message,
            },
        )

        return ToolResult.success_result(
            data={
                "logged": True,
                "level": level,
                "timestamp": timestamp,
                "message": message,
                "extra_keys": list(extra.keys()) if extra else [],
                "persisted": persist,
            },
            tool="logger",
        )


# ================================================================
# 5. ValidationTool — 数据验证与清洗
# ================================================================


@register_tool("validation", tags=["validation", "infrastructure"])
class ValidationTool(BaseTool):
    """数据验证与清洗工具

    对 DataFrame 进行全面的数据质量验证和清洗:
    - 必要列检查: 确认 DataFrame 包含指定的必要列
    - 数据类型校验: 检查各列是否符合预期的数据类型
    - 异常值检测和处理:
        * NaN 值定位和统计
        * Inf/-Inf 值检测
        * 数值越界检查（通过 rules 配置范围约束）
    - 清洗策略: 根据 rules 中的配置决定如何处理异常值（删除/填充/截断）

    输入参数:
        data:              待验证的 pd.DataFrame
        required_columns:  必须存在的列名列表
        rules:             验证规则字典，格式示例:
            {
                "column_name": {
                    "type": "numeric",          # 期望类型: numeric/category/datetime/boolean
                    "nullable": false,           # 是否允许空值
                    "min": 0,                   # 最小值（仅 numeric）
                    "max": 100,                 # 最大值（仅 numeric）
                    "fillna": 0,                # 空值填充值
                    "clip_outliers": true,      # 是否截断越界值
                    "drop_na": false,           # 是否直接删除含空值的行
                }
            }
        strict:            严格模式（任何验证失败即返回 error result）

    输出:
        report:   验证报告（包含各项检查的详细结果）
        cleaned:  清洗后的 DataFrame（如果执行了清洗操作）
        is_valid: 整体验证是否通过
    """

    name = "validation"
    description = "数据验证与清洗工具：列检查、类型校验、异常值检测、数据清洗"
    layer = ToolLayer.INFRASTRUCTURE
    tags = ["validation", "infrastructure", "quality"]

    input_schema = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "description": "待验证的 pd.DataFrame",
            },
            "required_columns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "必须存在的列名列表",
            },
            "rules": {
                "type": "object",
                "description": "逐列验证规则字典",
            },
            "strict": {
                "type": "boolean",
                "description": "严格模式（任何失败即返回错误）",
                "default": False,
            },
        },
        "required": ["data"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "report": {"type": "object", "description": "详细验证报告"},
            "cleaned": {"type": "object", "description": "清洗后的 DataFrame"},
            "is_valid": {"type": "boolean"},
        },
    }

    def _check_required_columns(self, df: pd.DataFrame, required: List[str]) -> Dict:
        missing = [col for col in required if col not in df.columns]
        return {
            "checked": True,
            "required_columns": required,
            "actual_columns": list(df.columns),
            "missing_columns": missing,
            "passed": len(missing) == 0,
        }

    def _check_types(self, df: pd.DataFrame, rules: Dict) -> Dict:
        results = {}
        for col, rule in rules.items():
            if col not in df.columns:
                continue
            expected_type = rule.get("type")
            if not expected_type:
                results[col] = {"checked": False, "reason": "无类型规则"}
                continue
            actual_dtype = str(df[col].dtype)
            type_map = {
                "numeric": ["int", "float"],
                "category": ["category", "object"],
                "datetime": ["datetime"],
                "boolean": ["bool"],
            }
            allowed = type_map.get(expected_type, [])
            passed = any(actual_dtype.startswith(t) for t in allowed)
            results[col] = {
                "expected": expected_type,
                "actual": actual_dtype,
                "passed": passed,
            }
        return results

    def _detect_anomalies(self, df: pd.DataFrame, rules: Dict) -> Dict:
        anomaly_report = {
            "nan_counts": {},
            "inf_counts": {},
            "out_of_range": {},
            "total_anomalies": 0,
        }

        for col in df.columns:
            col_rules = rules.get(col, {})

            nan_count = int(df[col].isna().sum())
            if nan_count > 0:
                anomaly_report["nan_counts"][col] = nan_count

            if pd.api.types.is_numeric_dtype(df[col]):
                inf_mask = np.isinf(df[col])
                inf_count = int(inf_mask.sum())
                if inf_count > 0:
                    anomaly_report["inf_counts"][col] = inf_count

                col_min = col_rules.get("min")
                col_max = col_rules.get("max")
                if col_min is not None or col_max is not None:
                    series = df[col].replace([np.inf, -np.inf], np.nan).dropna()
                    if len(series) > 0:
                        oor_low = int((series < col_min).sum()) if col_min is not None else 0
                        oor_high = int((series > col_max).sum()) if col_max is not None else 0
                        if oor_low > 0 or oor_high > 0:
                            anomaly_report["out_of_range"][col] = {
                                "below_min": oor_low,
                                "above_max": oor_high,
                                "min_bound": col_min,
                                "max_bound": col_max,
                            }

        anomaly_report["total_anomalies"] = (
            sum(anomaly_report["nan_counts"].values())
            + sum(anomaly_report["inf_counts"].values())
            + sum(v.get("below_min", 0) + v.get("above_max", 0) for v in anomaly_report["out_of_range"].values())
        )
        return anomaly_report

    def _clean_data(self, df: pd.DataFrame, rules: Dict, anomaly_report: Dict) -> pd.DataFrame:
        cleaned = df.copy()
        cleaning_log = []

        for col in df.columns:
            col_rules = rules.get(col, {})

            if col_rules.get("drop_na") and cleaned[col].isna().any():
                before = len(cleaned)
                cleaned = cleaned.dropna(subset=[col])
                cleaning_log.append(f"删除 {col} 含 NA 行: {before} -> {len(cleaned)}")
                continue

            fillna_val = col_rules.get("fillna")
            if fillna_val is not None and cleaned[col].isna().any():
                na_count = int(cleaned[col].isna().sum())
                cleaned[col] = cleaned[col].fillna(fillna_val)
                cleaning_log.append(f"{col}: 用 {fillna_val} 填充 {na_count} 个 NA")

            if pd.api.types.is_numeric_dtype(cleaned[col]):
                inf_mask = np.isinf(cleaned[col])
                if inf_mask.any():
                    inf_count = int(inf_mask.sum())
                    replacement = col_rules.get("fillna", 0)
                    cleaned.loc[inf_mask, col] = replacement
                    cleaning_log.append(f"{col}: 替换 {inf_count} 个 Inf 值为 {replacement}")

                clip_enabled = col_rules.get("clip_outliers", False)
                col_min = col_rules.get("min")
                col_max = col_rules.get("max")
                if clip_enabled and (col_min is not None or col_max is not None):
                    before_clip = cleaned[col].copy()
                    cleaned[col] = cleaned[col].clip(lower=col_min, upper=col_max)
                    clipped_count = int((before_clip != cleaned[col]).sum())
                    if clipped_count > 0:
                        cleaning_log.append(f"{col}: 截断 {clipped_count} 个越界值到 [{col_min}, {col_max}]")

        ctx_local = getattr(self, "_clean_ctx", None)
        if ctx_local:
            ctx_local.set("validation_cleaning_log", cleaning_log)

        return cleaned

    def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        data = kwargs.get("data")
        required_columns = kwargs.get("required_columns") or []
        rules = kwargs.get("rules") or {}
        strict = kwargs.get("strict", False)

        if data is None:
            return ToolResult.error_result(
                "data 参数不能为 None",
                code="VALIDATION_NO_DATA",
            )

        if not isinstance(data, pd.DataFrame):
            return ToolResult.error_result(
                f"data 必须是 pd.DataFrame，实际类型: {type(data).__name__}",
                code="VALIDATION_INVALID_TYPE",
            )

        if data.empty:
            report = {
                "row_count": 0,
                "col_count": len(data.columns),
                "columns_check": self._check_required_columns(data, required_columns),
                "type_check": {},
                "anomalies": {"nan_counts": {}, "inf_counts": {}, "out_of_range": {}, "total_anomalies": 0},
                "cleaning_applied": False,
                "is_valid": len(required_columns) == 0,
                "warnings": ["输入 DataFrame 为空"],
            }
            return ToolResult.success_result(
                data={
                    "report": report,
                    "cleaned": data.copy(),
                    "is_valid": report["is_valid"],
                },
                tool="validation",
            )

        self._clean_ctx = ctx

        columns_check = self._check_required_columns(data, required_columns)
        type_check = self._check_types(data, rules)
        anomalies = self._detect_anomalies(data, rules)

        has_errors = (
            not columns_check["passed"]
            or anomalies["total_anomalies"] > 0
            or any(not r.get("passed", True) for r in type_check.values())
        )

        should_clean = rules and has_errors
        cleaned_data = self._clean_data(data, rules, anomalies) if should_clean else data.copy()

        cleaning_log = ctx.get("validation_cleaning_log", [])

        report = {
            "row_count": len(data),
            "col_count": len(data.columns),
            "columns_check": columns_check,
            "type_check": type_check,
            "anomalies": anomalies,
            "cleaning_applied": should_clean,
            "cleaning_actions": cleaning_log,
            "is_valid": not has_errors or not strict,
            "strict_mode": strict,
        }

        ctx.record_metric("validation.row_count", len(data))
        ctx.record_metric("validation.is_valid", report["is_valid"])
        ctx.record_metric("validation.anomaly_count", anomalies["total_anomalies"])

        if strict and has_errors:
            errors = []
            if columns_check["missing_columns"]:
                errors.append(
                    ErrorInfo(
                        code="VALIDATION_MISSING_COLS",
                        message=f"缺少必要列: {columns_check['missing_columns']}",
                        severity="error",
                        details=columns_check,
                    )
                )
            if anomalies["total_anomalies"] > 0:
                errors.append(
                    ErrorInfo(
                        code="VALIDATION_ANOMALIES",
                        message=f"检测到 {anomalies['total_anomalies']} 个异常值",
                        severity="error",
                        details=anomalies,
                    )
                )

            result = ToolResult.error_result(
                f"严格模式验证失败: {len(errors)} 项检查未通过",
                code="VALIDATION_STRICT_FAILED",
            )
            result.errors.extend(errors)
            result.data = {
                "report": report,
                "cleaned": cleaned_data,
                "is_valid": False,
            }
            return result

        return ToolResult.success_result(
            data={
                "report": report,
                "cleaned": cleaned_data,
                "is_valid": report["is_valid"],
            },
            tool="validation",
            anomalies_found=anomalies["total_anomalies"],
            cleaning_applied=should_clean,
        )
