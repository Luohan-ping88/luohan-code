"""
数据采集模块 V8.0 - 增强错误处理和容错机制
增强: 统一错误分类、结构化日志、指数退避重试、数据恢复
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Union
from functools import wraps
import time
import hashlib
import json
import logging
import re
from urllib.parse import urlparse
from .config import DATA_SOURCES, RAW_DATA_DIR, PROCESSED_DATA_DIR, PL5_CONFIG, setup_logging, MODELS_DIR

# 安全配置
ALLOWED_DOMAINS = {'17500.cn', 'localhost', '127.0.0.1'}
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10MB
REQUEST_TIMEOUT = (10, 30)  # (connect timeout, read timeout) in seconds

from src.core.utils.errors import (
    DataError, DataLoadError, DataValidationError, DataParseError,
    NetworkError, NetworkTimeoutError, NetworkConnectionError, NetworkHTTPError,
    ConfigError, ConfigSafeLoader,
    StructuredLogger, structured_logger,
    retry_with_exponential_backoff, handle_data_load_failure,
    handle_network_failure, ErrorSeverity
)
from src.core.monitoring.performance_monitor import track_performance

logger = setup_logging(__name__)


# ════════════════════════════════════════════════════════════════
# 安全验证函数
# ════════════════════════════════════════════════════════════════

def validate_url(url: str) -> bool:
    """验证URL是否安全"""
    try:
        parsed = urlparse(url)
        
        # 只允许HTTP和HTTPS
        if parsed.scheme not in ('http', 'https'):
            logger.warning(f"拒绝不安全的URL scheme: {parsed.scheme}")
            return False
        
        # 检查域名是否在白名单中
        domain = parsed.netloc.split(':')[0]  # 移除端口号
        if not any(allowed_domain in domain for allowed_domain in ALLOWED_DOMAINS):
            logger.warning(f"拒绝未授权的域名: {domain}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"URL验证失败: {e}")
        return False


def validate_response_content(content: str) -> Tuple[bool, str]:
    """验证响应内容是否合理"""
    if not content:
        return False, "内容为空"
    
    # 检查大小
    if len(content.encode('utf-8')) > MAX_RESPONSE_SIZE:
        return False, f"内容过大 ({len(content)} bytes)"
    
    # 检查是否包含预期的数据格式（期号和数字）
    lines = content.strip().split('\n')
    valid_lines = 0
    for line in lines[:10]:  # 只检查前10行
        parts = line.strip().split()
        if len(parts) >= 8 and parts[0].isdigit():
            valid_lines += 1
    
    if valid_lines == 0:
        return False, "未找到有效的数据格式"
    
    return True, f"验证通过，找到 {valid_lines} 条有效样例数据"


def sanitize_filename(filename: str) -> str:
    """清理文件名，防止路径遍历攻击"""
    # 移除路径分隔符和特殊字符
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 确保不包含路径遍历
    sanitized = sanitized.replace('..', '_')
    return sanitized


# ════════════════════════════════════════════════════════════════
# 装饰器 - 重试机制
# ════════════════════════════════════════════════════════════════

def retry_on_failure(max_retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    """重试装饰器 - 增强版，支持结构化日志和错误分类"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retry_count = 0
            current_delay = delay
            last_error = None

            while retry_count < max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    retry_count += 1
                    if retry_count >= max_retries:
                        error = NetworkError(
                            f"{func.__name__} failed after {max_retries} attempts: {str(e)}",
                            original_error=e,
                            severity=ErrorSeverity.ERROR_SEVERITY_HIGH
                        ) if isinstance(e, (requests.RequestException, TimeoutError)) else \
                              DataLoadError(
                                  f"{func.__name__} failed after {max_retries} attempts: {str(e)}",
                                  original_error=e
                              )
                        logger.error(f"{func.__name__} 在 {max_retries} 次尝试后失败: {str(e)}")
                        structured_logger.log_operation_failure(
                            func.__name__, error, 0
                        )
                        raise error

                    structured_logger.log_recovery_attempt(
                        func.__name__, retry_count, max_retries,
                        "retry_with_backoff"
                    )
                    logger.warning(f"{func.__name__} 第 {retry_count} 次尝试失败，{current_delay}秒后重试: {str(e)}")
                    time.sleep(current_delay)
                    current_delay *= backoff

            return None
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════
# 数据验证器
# ═══════════════════════════════════════════════════════════════

class DataValidator:
    """数据验证器 - 验证数据格式和完整性"""
    
    @staticmethod
    def validate_period(period: str) -> bool:
        """验证期号格式"""
        if not period or not isinstance(period, str):
            return False
        # 支持格式: 2026076 或 26076
        return period.isdigit() and len(period) in [5, 7]
    
    @staticmethod
    def validate_digit(digit: Union[str, int]) -> bool:
        """验证数字是否在0-9范围内"""
        try:
            d = int(digit)
            return 0 <= d <= 9
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_record(record: Dict) -> Tuple[bool, str]:
        """验证单条记录"""
        required_fields = ['period', 'wan', 'qian', 'bai', 'shi', 'ge']
        
        # 检查必需字段
        for field in required_fields:
            if field not in record:
                return False, f"缺少字段: {field}"
        
        # 验证期号
        if not DataValidator.validate_period(str(record['period'])):
            return False, f"无效的期号: {record['period']}"
        
        # 验证数字
        for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
            if not DataValidator.validate_digit(record[pos]):
                return False, f"无效的数字: {pos}={record[pos]}"
        
        return True, "验证通过"


# ═══════════════════════════════════════════════════════════════
# 数据版本管理
# ═══════════════════════════════════════════════════════════════

class DataVersionManager:
    """数据版本管理器"""
    
    def __init__(self):
        self.version_file = MODELS_DIR / "data_version.json"
        self.backup_dir = RAW_DATA_DIR / "backups"
        # 确保父目录存在
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def get_current_version(self) -> Dict:
        """获取当前数据版本信息"""
        if self.version_file.exists():
            with open(self.version_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'version': '0.0.0',
            'last_update': None,
            'record_count': 0,
            'latest_period': None,
            'data_hash': None
        }
    
    def calculate_data_hash(self, df: pd.DataFrame) -> str:
        """计算数据哈希值"""
        # 使用期号和号码计算哈希
        hash_content = ''.join(df['period'].astype(str).tolist())
        return hashlib.md5(hash_content.encode()).hexdigest()[:16]
    
    def save_version(self, df: pd.DataFrame, source: str = 'unknown'):
        """保存数据版本信息"""
        version_info = {
            'version': datetime.now().strftime('%Y%m%d.%H%M%S'),
            'last_update': datetime.now().isoformat(),
            'record_count': len(df),
            'latest_period': str(df['period'].iloc[-1]) if not df.empty else None,
            'data_hash': self.calculate_data_hash(df),
            'source': source,
            'columns': df.columns.tolist()
        }
        
        with open(self.version_file, 'w', encoding='utf-8') as f:
            json.dump(version_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据版本已保存: {version_info['version']}, 记录数: {version_info['record_count']}")
    
    def create_backup(self, df: pd.DataFrame) -> Path:
        """创建数据备份（在现有备份上更新，不生成新文件）"""
        # 使用固定的备份文件名，每次更新时覆盖
        backup_path = self.backup_dir / "pl5_backup.csv"
        df.to_csv(backup_path, index=False, encoding='utf-8')
        logger.info(f"数据备份已更新: {backup_path}")
        return backup_path
    
    def list_backups(self) -> List[Path]:
        """列出所有备份"""
        # 先检查固定备份文件
        backup_path = self.backup_dir / "pl5_backup.csv"
        if backup_path.exists():
            return [backup_path]
        # 兼容旧的备份文件格式
        old_backups = sorted(self.backup_dir.glob('pl5_backup_*.csv'), reverse=True)
        return old_backups
    
    def restore_backup(self, backup_path: Path) -> Optional[pd.DataFrame]:
        """从备份恢复数据"""
        try:
            df = pd.read_csv(backup_path, encoding='utf-8')
            logger.info(f"已从备份恢复数据: {backup_path}, 记录数: {len(df)}")
            return df
        except Exception as e:
            logger.error(f"恢复备份失败: {str(e)}")
            return None


# ═══════════════════════════════════════════════════════════════
# 增强版数据采集器 V8.0
# ═══════════════════════════════════════════════════════════════

class PL5DataCollectorV8:
    """排列五数据采集器 V8.0 - 增强错误处理和容错机制"""
    
    def __init__(self):
        self.raw_data_path = RAW_DATA_DIR / "pl5_history.txt"
        self.processed_data_path = PROCESSED_DATA_DIR / "pl5_processed.csv"
        self.positions = PL5_CONFIG["positions"]
        self.validator = DataValidator()
        self.version_manager = DataVersionManager()
        
        # 多数据源配置
        self.data_sources = {
            'lecai': {
                'url': DATA_SOURCES.get("lecai", "http://data.17500.cn/pl5_asc.txt"),
                'enabled': True,
                'priority': 1
            },
            'local': {
                'path': self.raw_data_path,
                'enabled': True,
                'priority': 2
            }
        }
        
        # 缓存机制
        self.cache = {}
        self.cache_expiry = {}
        self.cache_ttl = 3600  # 缓存过期时间（秒）
    
    @track_performance
    @retry_on_failure(max_retries=3, delay=2, backoff=2, 
                     exceptions=(requests.RequestException, TimeoutError))
    def fetch_from_network(self, source_name: str = 'lecai') -> Optional[str]:
        """从网络获取数据（安全增强版）"""
        source = self.data_sources.get(source_name)
        if not source or not source.get('enabled'):
            logger.warning(f"数据源 {source_name} 未启用")
            return None
        
        url = source.get('url')
        
        # 安全验证URL
        if not validate_url(url):
            raise NetworkError(f"不安全的URL被拒绝: {url}")
        
        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_DATA_FETCH,
            {"source": source_name, "url": url}
        )
        start_time = time.time()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/plain,text/html;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }
        
        try:
            # 使用流式响应防止内存溢出
            with requests.get(
                url, 
                headers=headers, 
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                stream=True
            ) as response:
                response.encoding = 'utf-8'
                
                # 检查状态码
                if response.status_code != 200:
                    if response.status_code == 403:
                        raise NetworkHTTPError(
                            f"Access forbidden (403)", url=url, status_code=403,
                            severity=ErrorSeverity.ERROR_SEVERITY_HIGH
                        )
                    elif response.status_code == 404:
                        raise NetworkHTTPError(
                            f"Data not found (404)", url=url, status_code=404,
                            severity=ErrorSeverity.ERROR_SEVERITY_HIGH
                        )
                    else:
                        raise NetworkHTTPError(
                            f"HTTP error: {response.status_code}", url=url, status_code=response.status_code
                        )
                
                # 检查响应头中的Content-Length
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > MAX_RESPONSE_SIZE:
                    raise NetworkError(f"响应过大: {content_length} bytes")
                
                # 读取响应
                content = response.text
                
                # 验证响应内容
                is_valid, validation_msg = validate_response_content(content)
                if not is_valid:
                    logger.warning(f"响应内容验证失败: {validation_msg}")
                    return None
                
                if len(content) < 100:
                    structured_logger.log_operation_warning(
                        StructuredLogger.OPERATION_DATA_FETCH,
                        "Data content too short",
                        {"content_length": len(content)}
                    )
                    logger.warning(f"获取的数据内容过少，可能无效")
                    return None
                
                # 安全写入文件
                safe_path = RAW_DATA_DIR / sanitize_filename(self.raw_data_path.name)
                with open(safe_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                duration_ms = (time.time() - start_time) * 1000
                structured_logger.log_operation_success(
                    StructuredLogger.OPERATION_DATA_FETCH,
                    duration_ms,
                    {"content_length": len(content), "source": source_name}
                )
                logger.info(f"数据获取成功，大小: {len(content)} 字符")
                return content
                
        except requests.Timeout as e:
            raise NetworkTimeoutError(
                f"Request timeout for {url}",
                url=url,
                original_error=e
            )
        except requests.ConnectionError as e:
            raise NetworkConnectionError(
                f"Connection error, please check network",
                url=url,
                original_error=e
            )
        except (NetworkError,):
            raise
        except Exception as e:
            raise NetworkError(
                f"Unexpected request error: {str(e)}",
                url=url,
                original_error=e
            )
    
    @track_performance
    def parse_raw_data(self, raw_text: str) -> pd.DataFrame:
        """解析原始数据文本（增强版，带详细错误处理和分类）"""
        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_DATA_PARSE,
            {"input_length": len(raw_text) if raw_text else 0}
        )
        start_time = time.time()

        if not raw_text or not isinstance(raw_text, str):
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_DATA_PARSE,
                DataParseError("Raw data is empty or invalid format"),
                0
            )
            logger.error("原始数据为空或格式错误")
            return pd.DataFrame()
        
        records = []
        error_count = 0
        success_count = 0
        validation_errors = []
        
        lines = raw_text.strip().split('\n')
        logger.info(f"开始解析 {len(lines)} 行数据...")
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                parts = line.split()
                
                if len(parts) < 8:
                    logger.debug(f"第 {line_num} 行字段不足，跳过: {line[:50]}")
                    error_count += 1
                    continue
                
                period = parts[0].strip()
                date = parts[1].strip()
                
                if not self.validator.validate_period(period):
                    validation_errors.append(f"Line {line_num}: invalid period '{period}'")
                    logger.debug(f"第 {line_num} 行期号格式无效: {period}")
                    error_count += 1
                    continue
                
                try:
                    wan = int(parts[2])
                    qian = int(parts[3])
                    bai = int(parts[4])
                    shi = int(parts[5])
                    ge = int(parts[6])
                except (ValueError, IndexError) as e:
                    validation_errors.append(f"Line {line_num}: digit parse error - {e}")
                    logger.debug(f"第 {line_num} 行数字解析失败: {str(e)}")
                    error_count += 1
                    continue
                
                digits = [wan, qian, bai, shi, ge]
                if not all(self.validator.validate_digit(d) for d in digits):
                    validation_errors.append(f"Line {line_num}: out-of-range digits")
                    logger.debug(f"第 {line_num} 行数字超出范围")
                    error_count += 1
                    continue
                
                record = {
                    'period': period,
                    'date': date,
                    'wan': wan,
                    'qian': qian,
                    'bai': bai,
                    'shi': shi,
                    'ge': ge,
                    'full_number': f"{wan}{qian}{bai}{shi}{ge}",
                    'parse_line': line_num
                }
                
                is_valid, msg = self.validator.validate_record(record)
                if not is_valid:
                    validation_errors.append(f"Line {line_num}: {msg}")
                    logger.debug(f"第 {line_num} 行验证失败: {msg}")
                    error_count += 1
                    continue
                
                records.append(record)
                success_count += 1
                
            except Exception as e:
                logger.debug(f"第 {line_num} 行解析异常: {str(e)}")
                error_count += 1
                continue
        
        df = pd.DataFrame(records)
        
        if not df.empty:
            df = df.sort_values('period').reset_index(drop=True)
            
            duplicates = df[df.duplicated(subset=['period'], keep=False)]
            if not duplicates.empty:
                logger.warning(f"发现 {len(duplicates)} 条重复期号记录，保留最后一条")
                df = df.drop_duplicates(subset=['period'], keep='last')

            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_success(
                StructuredLogger.OPERATION_DATA_PARSE,
                duration_ms,
                {
                    "success_count": success_count,
                    "error_count": error_count,
                    "final_records": len(df),
                    "validation_error_rate": f"{error_count/(success_count+error_count)*100:.1f}%"
                        if (success_count + error_count) > 0 else "N/A"
                }
            )
            logger.info(f"解析完成: 成功 {success_count} 条, 失败 {error_count} 条, 最终 {len(df)} 条")
        else:
            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_DATA_PARSE,
                DataParseError("No valid records parsed from input data",
                              record_count=0),
                duration_ms
            )
            if validation_errors:
                logger.warning(f"验证错误摘要 (前5条): {validation_errors[:5]}")
            logger.error("没有成功解析任何记录")
        
        return df
    
    def load_local_data(self) -> Optional[pd.DataFrame]:
        """加载本地数据（增强版）"""
        try:
            if not self.raw_data_path.exists():
                logger.warning(f"本地数据文件不存在: {self.raw_data_path}")
                return None
            
            # 检查文件大小
            file_size = self.raw_data_path.stat().st_size
            if file_size == 0:
                logger.error("本地数据文件为空")
                return None
            
            if file_size < 1000:
                logger.warning(f"本地数据文件过小 ({file_size} bytes)，可能不完整")
            
            with open(self.raw_data_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            
            df = self.parse_raw_data(raw_text)
            
            if df.empty:
                logger.error("本地数据解析失败")
                return None
            
            return df
            
        except UnicodeDecodeError:
            logger.error("文件编码错误，尝试使用其他编码")
            try:
                with open(self.raw_data_path, 'r', encoding='gbk') as f:
                    raw_text = f.read()
                return self.parse_raw_data(raw_text)
            except Exception as e:
                logger.error(f"使用GBK编码读取失败: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"加载本地数据失败: {str(e)}")
            return None
    
    def load_processed_data(self) -> Optional[pd.DataFrame]:
        """加载处理后的数据（兼容旧版）"""
        try:
            from .config import PROCESSED_DATA_DIR
            processed_file = PROCESSED_DATA_DIR / "pl5_processed.csv"
            
            if not processed_file.exists():
                logger.warning(f"处理后的数据文件不存在: {processed_file}")
                # 尝试从原始数据重新处理
                return self.load_local_data()
            
            df = pd.read_csv(processed_file, encoding='utf-8')
            logger.info(f"成功加载处理后的数据: {len(df)} 条记录")
            return df
            
        except Exception as e:
            logger.error(f"加载处理后数据失败: {str(e)}")
            return None
    
    @track_performance
    def update_data(self) -> pd.DataFrame:
        """更新数据（增强版，带完整错误处理、版本管理和恢复机制）"""
        # 检查缓存
        cache_key = 'update_data'
        current_time = time.time()
        if cache_key in self.cache and current_time < self.cache_expiry.get(cache_key, 0):
            logger.info("使用缓存的更新数据")
            return self.cache[cache_key]
        logger.info("=" * 60)
        logger.info("开始更新数据 V8.0 (增强错误处理)")
        logger.info("=" * 60)

        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_DATA_FETCH,
            {"operation": "full_update_pipeline"}
        )
        start_time = time.time()

        df = None
        source = None
        errors_encountered = []

        try:
            raw_text = self.fetch_from_network('lecai')
            if raw_text:
                df = self.parse_raw_data(raw_text)
                if not df.empty:
                    source = 'lecai'
                    logger.info(f"从网络获取数据成功: {len(df)} 条记录")
                else:
                    errors_encountered.append(("network_parse", "Network data parsed to empty DataFrame"))
        except NetworkError as e:
            errors_encountered.append(("network", str(e)))
            logger.error(f"从网络获取数据失败: {e.to_dict()}")
        except Exception as e:
            errors_encountered.append(("network_unknown", str(e)))
            logger.error(f"从网络获取数据失败: {str(e)}")

        if df is None or df.empty:
            logger.info("尝试加载本地数据...")
            try:
                df = self.load_local_data()
                if df is not None and not df.empty:
                    source = 'local'
                    logger.info(f"从本地加载数据成功: {len(df)} 条记录")
                else:
                    errors_encountered.append(("local_load", "Local data is None or empty"))
            except DataError as e:
                errors_encountered.append(("local_data", str(e)))
                logger.error(f"本地数据加载失败: {e.to_dict()}")
            except Exception as e:
                errors_encountered.append(("local_unknown", str(e)))
                logger.error(f"本地数据加载异常: {str(e)}")

        if df is None or df.empty:
            logger.warning("尝试从备份恢复...")
            try:
                backups = self.version_manager.list_backups()
                if backups:
                    df = self.version_manager.restore_backup(backups[0])
                    if df is not None and not df.empty:
                        source = 'backup'
                        structured_logger.log_fallback_used(
                            StructuredLogger.OPERATION_DATA_FETCH,
                            "backup_restore",
                            f"Using backup from {backups[0].name}"
                        )
                        logger.info(f"从备份恢复数据成功: {backups[0].name}, 记录数: {len(df)}")
                    else:
                        errors_encountered.append(("backup_restore", "Backup restore returned empty"))
                else:
                    errors_encountered.append(("no_backup", "No backups available"))
            except Exception as e:
                errors_encountered.append(("backup_error", str(e)))
                logger.error(f"备份恢复失败: {str(e)}")

        if df is None or df.empty:
            duration_ms = (time.time() - start_time) * 1000
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_DATA_FETCH,
                DataLoadError(
                    "无法获取数据: 网络、本地和备份都失败",
                    data_source="all",
                    record_count=0,
                    context={"errors": errors_encountered}
                ),
                duration_ms
            )
            raise DataLoadError(
                "无法获取数据: 网络、本地和备份都失败",
                data_source="all",
                context={"errors": errors_encountered}
            )

        # 保存到 processed 目录
        try:
            PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
            processed_file = PROCESSED_DATA_DIR / 'pl5_processed.csv'
            df.to_csv(processed_file, index=False)
            logger.info(f"数据已保存到 processed 目录: {processed_file}")
        except Exception as e:
            logger.warning(f"保存 processed 数据失败（非致命）: {str(e)}")

        try:
            self.version_manager.create_backup(df)
        except Exception as e:
            logger.warning(f"创建备份失败（非致命）: {str(e)}")
            structured_logger.log_operation_warning(
                StructuredLogger.OPERATION_DATA_FETCH,
                "Backup creation failed (non-fatal)",
                {"error": str(e)}
            )

        try:
            self.version_manager.save_version(df, source)
        except Exception as e:
            logger.warning(f"保存版本信息失败（非致命）: {str(e)}")

        duration_ms = (time.time() - start_time) * 1000
        structured_logger.log_operation_success(
            StructuredLogger.OPERATION_DATA_FETCH,
            duration_ms,
            {
                "source": source,
                "record_count": len(df),
                "errors_count": len(errors_encountered),
                "fallback_used": source != 'lecai'
            }
        )

        logger.info("=" * 60)
        logger.info(f"数据更新完成: 来源={source}, 记录数={len(df)}")
        logger.info("=" * 60)
        
        # 保存到缓存
        cache_key = 'update_data'
        self.cache[cache_key] = df
        self.cache_expiry[cache_key] = time.time() + self.cache_ttl
        
        return df
    
    def get_latest_period(self) -> Optional[str]:
        """获取最新期号"""
        try:
            # 1. 首先尝试从版本管理器获取
            version_info = self.version_manager.get_current_version()
            latest_period = version_info.get('latest_period')
            if latest_period:
                logger.info(f"从版本管理器获取最新期号: {latest_period}")
                return str(latest_period)
            
            # 2. 尝试从处理后的数据获取
            df = self.load_processed_data()
            if df is not None and not df.empty:
                latest_period = str(df['period'].iloc[-1])
                logger.info(f"从数据文件获取最新期号: {latest_period}")
                return latest_period
            
            # 3. 尝试从原始数据获取
            df = self.load_local_data()
            if df is not None and not df.empty:
                latest_period = str(df['period'].iloc[-1])
                logger.info(f"从原始数据获取最新期号: {latest_period}")
                return latest_period
            
            logger.warning("无法获取最新期号")
            return None
            
        except Exception as e:
            logger.error(f"获取最新期号失败: {str(e)}")
            return None


# 保持向后兼容
PL5DataCollector = PL5DataCollectorV8
