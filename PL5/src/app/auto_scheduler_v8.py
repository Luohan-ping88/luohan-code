"""
智能自动化分析系统 - 后台持续学习进化
调度流程优化模块 V10.3
增强: 统一错误分类、结构化日志、错误恢复机制、任务调度监控
包含任务失败重试机制、异常报警系统、任务状态持久化、任务依赖管理等功能
新增: 特征版本管理、系统健康监控
"""
import schedule
import time
import logging
import subprocess
import sys
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import pickle
import traceback

# 先添加路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

# 然后导入配置，确保 MODELS_DIR 等在使用前已定义
from src.core.config import LOGS_DIR, MODELS_DIR, DATA_DIR
from src.core.utils.logger import get_logger, log_structured, save_data_file, read_data_file
from src.core.features.feature_version_manager import get_feature_version_manager
from src.core.monitoring.health_monitor import get_health_monitor
from src.core.utils.errors import (
    DataError, ModelError, ConfigError, NetworkError,
    ConfigValueError,
    PL5BaseError, ErrorSeverity,
    StructuredLogger, structured_logger,
    ConfigSafeLoader, RecoveryStrategy
)
from src.core.workflow import IntelligentWorkflowOrchestrator
from src.core.workflow.intelligent_time_scheduler import IntelligentTimeScheduler, TimeStrategy

logger = get_logger('scheduler')

# 任务依赖关系定义
TASK_DEPENDENCIES = {
    'data_fetch': [],
    'evaluation': ['data_fetch'],
    'optimization': ['evaluation'],
    'training': ['optimization'],
    'send_report': ['training']
}


class TaskRetryManager:
    """任务重试管理器 - 增强版，支持结构化日志和错误分类"""

    def __init__(self):
        self.retry_config = {
            'max_retries': 3,
            'base_delay': 1,
            'max_delay': 60,
            'backoff_factor': 2
        }
        self.retry_counts: Dict[str, int] = {}
        self.failed_tasks: Dict[str, Dict] = {}

    def should_retry(self, task_name: str) -> bool:
        if task_name not in self.retry_counts:
            self.retry_counts[task_name] = 0
        return self.retry_counts[task_name] < self.retry_config['max_retries']

    def increment_retry_count(self, task_name: str):
        if task_name not in self.retry_counts:
            self.retry_counts[task_name] = 0
        self.retry_counts[task_name] += 1

    def reset_retry_count(self, task_name: str):
        self.retry_counts[task_name] = 0

    def get_delay(self, task_name: str) -> int:
        retry_count = self.retry_counts.get(task_name, 0)
        delay = self.retry_config['base_delay'] * (self.retry_config['backoff_factor'] ** retry_count)
        return min(delay, self.retry_config['max_delay'])

    def record_failure(self, task_name: str, error: Exception):
        self.failed_tasks[task_name] = {
            "error": str(error),
            "error_type": type(error).__name__,
            "timestamp": datetime.now().isoformat(),
            "retry_count": self.retry_counts.get(task_name, 0)
        }


class TaskHistoryManager:
    """任务历史管理器 - 【V10.4修复】线程安全"""
    
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self._lock = threading.Lock()  # 【V10.4新增】线程锁
        self.history = self.load_history()
    
    def load_history(self) -> List[Dict]:
        """加载任务历史 - 双格式支持"""
        try:
            # 优先JSON
            json_file = self.history_file.with_suffix('.json')
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            elif self.history_file.exists():
                with open(self.history_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            logger.warning(f"加载任务历史失败: {e}")
        return []
    
    def save_history(self):
        """保存任务历史 - 双格式同时保存"""
        try:
            # 保存PKL
            with open(self.history_file, 'wb') as f:
                pickle.dump(self.history, f)
            # 保存JSON
            json_file = self.history_file.with_suffix('.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"保存任务历史失败: {e}")
    
    # 最大保留记录数（约30天 × 每天约25条任务）
    MAX_HISTORY_RECORDS = 800

    def add_task_record(self, task_name: str, status: str, start_time: datetime, 
                       end_time: datetime, error_msg: str = None):
        """添加任务执行记录（自动截断，保留最近 MAX_HISTORY_RECORDS 条）"""
        record = {
            'task_name': task_name,
            'status': status,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration': (end_time - start_time).total_seconds(),
            'error_message': error_msg
        }
        with self._lock:  # 【V10.4修复】线程安全保护
            self.history.append(record)
            # 【修复】自动截断，防止无限增长
            if len(self.history) > self.MAX_HISTORY_RECORDS:
                self.history = self.history[-self.MAX_HISTORY_RECORDS:]
        self.save_history()
    
    def get_task_history(self, task_name: str = None, limit: int = 10) -> List[Dict]:
        """获取任务历史记录"""
        if task_name:
            records = [r for r in self.history if r['task_name'] == task_name]
        else:
            records = self.history[:]
        
        # 按时间倒序排列
        records.sort(key=lambda x: x['start_time'], reverse=True)
        return records[:limit]


class AutoSchedulerV8:
    """调度流程优化模块V8.0"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / "config" / "scheduler_config_v8.json"
        self.workflow_config_file = self.base_dir / "config" / "workflow_config.json"
        self.history_file = LOGS_DIR / "task_history_v8.pkl"
        self.config_file.parent.mkdir(exist_ok=True)
        
        self.running = False
        self.retry_manager = TaskRetryManager()
        self.history_manager = TaskHistoryManager(self.history_file)
        
        self.workflow_enabled = False
        self.orchestrator = None
        self.workflow_config = None
        
        # 智能时间调度器
        self.time_scheduler = None
        
        # 任务状态持久化
        self.current_status = {
            'last_run': None,
            'next_run': None,
            'current_task': None,
            'learning_progress': 0,
            'task_chain': [],
            'last_successful_run': None
        }
        
        # 【修复BUG-01】提前初始化 custom_tasks 与 task_map，防止 run_full_pipeline/
        # _get_task_handler 在 init_orchestrator 之前被调用时出现 AttributeError
        self.custom_tasks: List[str] = []  # 将在 init_orchestrator 后填充
        self.task_map: Dict[str, tuple] = {}  # 将在 _build_task_map() 后填充
        
        self.load_config()
        self.load_workflow_config()
        self.init_orchestrator()
        self.init_time_scheduler()
        self._build_task_map()          # 构建任务映射表
        self.load_current_status()
        self.start_time = datetime.now()  # 记录调度器启动时间
    
    def load_config(self):
        """加载配置 - 增强版，配置错误时使用默认值并告警"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)

                required_keys = ['data_fetch_time', 'evaluation_time', 'training_start',
                                'email_send_time']
                for key in required_keys:
                    if key not in self.config:
                        default_value = ConfigSafeLoader.DEFAULT_CONFIG_VALUES.get(
                            'scheduler_config', {}
                        ).get(key)
                        if default_value:
                            self.config[key] = default_value
                            structured_logger.log_fallback_used(
                                "CONFIG_LOAD",
                                RecoveryStrategy.FALLBACK_TO_DEFAULT,
                                f"Config key '{key}' missing, using default: {default_value}"
                            )
                            logger.warning(f"配置缺少 '{key}'，使用默认值: {default_value}")

                logger.info(f"配置加载成功: {self.config_file}")
            except json.JSONDecodeError as e:
                structured_logger.log_operation_failure(
                    "CONFIG_LOAD",
                    ConfigValueError(f"Invalid JSON in config file: {e}",
                                    config_file=str(self.config_file),
                                    original_error=e),
                    0
                )
                logger.error(f"配置文件JSON格式错误: {e}，使用默认配置")
                self._use_default_config()
            except Exception as e:
                structured_logger.log_operation_failure(
                    "CONFIG_LOAD",
                    ConfigError(f"Failed to load config: {e}",
                               config_file=str(self.config_file),
                               original_error=e),
                    0
                )
                logger.error(f"加载配置失败: {e}，使用默认配置")
                self._use_default_config()
        else:
            logger.warning(f"配置文件不存在: {self.config_file}，创建默认配置")
            self._use_default_config()

    def _use_default_config(self):
        """使用默认配置"""
        defaults = ConfigSafeLoader.DEFAULT_CONFIG_VALUES.get('scheduler_config', {})
        self.config = {
            'data_fetch_time': defaults.get('data_fetch_time', '22:15'),  # 开奖后获取数据
            'evaluation_time': defaults.get('evaluation_time', '22:15'),  # 模型评估和调优
            'optimization_start': defaults.get('optimization_start', '22:45'),  # 策略优化
            'training_start': defaults.get('training_start', '00:30'),  # 深度训练
            'incremental_training_time': defaults.get('incremental_training_time', '08:00'),  # 增量训练
            'incremental_training_morning': defaults.get('incremental_training_morning', '08:00'),  # 上午增量训练
            'first_prediction_verification': defaults.get('first_prediction_verification', '10:00'),  # 首次预测验证
            'incremental_training_noon': defaults.get('incremental_training_noon', '12:00'),  # 中午增量训练
            'incremental_training_afternoon': defaults.get('incremental_training_afternoon', '14:00'),  # 下午增量训练
            'deep_strategy_optimization': defaults.get('deep_strategy_optimization', '16:00'),  # 深度策略优化
            'prediction_preview': defaults.get('prediction_preview', '17:00'),  # 预测预生成
            'final_prediction_time': defaults.get('final_prediction_time', '18:00'),  # 最终预测
            'final_prediction_verification_time': defaults.get('final_prediction_verification_time', '19:00'),  # 最终预测验证
            'pre_sale_prediction_time': defaults.get('pre_sale_prediction_time', '20:00'),  # 售前最终预测
            'training_deadline': '17:00',
            'email_send_time': defaults.get('email_send_time', '20:15'),
            'enabled': True,
            'monitoring_enabled': True
        }
        self.save_config()
    
    def save_config(self):
        """保存配置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def load_workflow_config(self):
        """加载智能工作流配置"""
        if self.workflow_config_file.exists():
            try:
                with open(self.workflow_config_file, 'r', encoding='utf-8') as f:
                    self.workflow_config = json.load(f)
                self.workflow_enabled = self.workflow_config.get('enabled', False)
                logger.info(f"智能工作流配置加载成功: {self.workflow_config_file}")
            except json.JSONDecodeError as e:
                logger.error(f"智能工作流配置JSON格式错误: {e}，使用默认配置")
                self._use_default_workflow_config()
            except Exception as e:
                logger.error(f"加载智能工作流配置失败: {e}，使用默认配置")
                self._use_default_workflow_config()
        else:
            logger.warning(f"智能工作流配置文件不存在: {self.workflow_config_file}，使用默认配置")
            self._use_default_workflow_config()
    
    def _use_default_workflow_config(self):
        """使用默认智能工作流配置"""
        self.workflow_config = {
            'enabled': False,
            'time_window': {'start': '00:00', 'end': '17:30'},
            'retry': {'max_retries': 3, 'base_delay': 1, 'max_delay': 60, 'backoff_factor': 2},
            'intelligent_scheduling': {'enabled': True, 'check_interval': 60, 'early_execution_enabled': True, 'missed_task_catchup_enabled': True},
            'state': {'persistence_enabled': True, 'state_file_path': 'logs/workflow_state.pkl'},
            'tasks': {
                'data_fetch': {'enabled': True, 'priority': 1},
                'evaluation': {'enabled': True, 'priority': 2},
                'optimization': {'enabled': True, 'priority': 3},
                'training': {'enabled': True, 'priority': 4},
                'send_report': {'enabled': True, 'priority': 5}
            }
        }
        self.workflow_enabled = False
    
    def save_workflow_config(self):
        """保存智能工作流配置"""
        if self.workflow_config:
            with open(self.workflow_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.workflow_config, f, indent=2, ensure_ascii=False)
    
    def init_orchestrator(self):
        if self.workflow_enabled:
            try:
                state_file_path = self.workflow_config.get('state', {}).get('state_file_path', 'logs/workflow_state.pkl')
                self.orchestrator = IntelligentWorkflowOrchestrator(state_file_path=state_file_path, config=self.config)
                self._register_custom_tasks()
                logger.info(f"智能工作流编排器初始化成功")
            except Exception as e:
                logger.error(f"智能工作流编排器初始化失败: {e}")
                self.workflow_enabled = False
                self.orchestrator = None
    
    def _register_custom_tasks(self):
        if not self.orchestrator:
            return
        from src.core.workflow.orchestrator import TaskStatus
        custom_tasks = [
            "incremental_training",
            "first_prediction_verification",
            "second_prediction_verification",
            "third_prediction_verification",
            "deep_strategy_optimization",
            "prediction_preview",
            "final_prediction",
            "final_prediction_verification",
            "pre_sale_prediction",
            "extra_training",
            "hyperparameter_tune",
            "ensemble_refine",
            "auto_learn_task",
            "strategy_selection",
            "ga_optimizer",
            "sa_optimizer",
            "full_training",
        ]
        for task in custom_tasks:
            if task not in self.orchestrator.state["tasks"]:
                self.orchestrator.state["tasks"][task] = {
                    "status": TaskStatus.PENDING.value,
                    "start_time": None,
                    "end_time": None,
                    "result": None,
                    "error": None,
                    "retry_count": 0,
                    "last_executed_time": None,
                    "is_missed": False
                }
                self.orchestrator.task_order.append(task)
        self.orchestrator._save_state()
    
    def init_time_scheduler(self):
        """初始化智能时间调度器"""
        try:
            email_time = self.config.get('email_send_time', '20:15')
            self.time_scheduler = IntelligentTimeScheduler(
                draw_time="21:25",
                email_time=email_time
            )
            logger.info("智能时间调度器初始化成功")
            
            # 显示调度摘要
            summary = self.time_scheduler.get_schedule_summary()
            logger.info(f"[智能时间调度] 策略: {summary['strategy']}")
            logger.info(f"[智能时间调度] 距离开奖: {summary['time_to_draw']}")
        except Exception as e:
            logger.error(f"智能时间调度器初始化失败: {e}")
            self.time_scheduler = None

    def _build_task_map(self):
        """【新增】集中构建任务名→处理器映射，并同步更新 custom_tasks 列表。
        所有任务的注册都在此处完成，setup_schedule / run_full_pipeline / run_task_manually
        均从这里读取，保证一致性。
        """
        # ── 完整佐证链任务列表（与 setup_schedule 中的定时任务完全一致）──
        self.custom_tasks = [
            "data_fetch",
            "evaluation",
            "optimization",
            "training",
            "incremental_training",
            "first_prediction_verification",
            "second_prediction_verification",
            "third_prediction_verification",
            "deep_strategy_optimization",
            "prediction_preview",
            "final_prediction",
            "final_prediction_verification",
            "pre_sale_prediction",
            "send_report",
        ]

        # ── 任务名 → (显示名称, 处理函数) ──
        self.task_map = {
            'data_fetch':                    ('任务1:  数据获取',          self.task_fetch_data),
            'evaluation':                    ('任务2:  评估分析',          self.task_evaluate),
            'optimization':                  ('任务3:  策略优化',          self.task_optimize),
            'training':                      ('任务4:  深度训练',          self.task_train),
            'incremental_training':          ('任务5/7/8: 增量训练',       self.task_incremental_train),
            'first_prediction_verification': ('任务6:  首次预测验证',       self.task_first_prediction_verification),
            'second_prediction_verification':('任务6b: 二次预测验证',       self.task_second_prediction_verification),   # 【BUG-1修复】指向独立handler
            'third_prediction_verification': ('任务6c: 三次预测验证',       self.task_third_prediction_verification),    # 【BUG-1修复】指向独立handler
            'deep_strategy_optimization':    ('任务9:  深度策略优化',       self.task_deep_strategy_optimization),
            'prediction_preview':            ('任务10: 预测预生成',         self.task_prediction_preview),
            'final_prediction':              ('任务11: 最终预测',           self.task_final_prediction),
            'final_prediction_verification': ('任务12: 最终预测验证',       self.task_final_prediction_verification),
            'pre_sale_prediction':           ('任务13: 售前最终预测',       self.task_pre_sale_prediction),
            'send_report':                   ('任务14: 发送报告',           self.task_send_report),
            # 额外优化任务（可选，由智能调度器触发）
            'extra_training':                ('额外: 强化训练',             self.task_incremental_train),
            'hyperparameter_tune':           ('额外: 超参优化',             self.task_optimize),
            'ensemble_refine':               ('额外: 集成精调',             self.task_incremental_train),
            'auto_learn_task':               ('额外: 自动学习',             self.task_optimize),
            'strategy_selection':            ('额外: 策略选择',             self.task_optimize),
            'ga_optimizer':                  ('额外: 遗传算法优化',         self.task_optimize),
            'sa_optimizer':                  ('额外: 模拟退火优化',         self.task_optimize),
            'full_training':                 ('额外: 全量训练',             self.task_train),
        }
        logger.info(f"[task_map] 已注册 {len(self.task_map)} 个任务, custom_tasks 共 {len(self.custom_tasks)} 步")
    
    def load_current_status(self):
        """加载当前状态"""
        try:
            status_file = LOGS_DIR / "scheduler_v8_status.json"
            if status_file.exists():
                with open(status_file, 'r', encoding='utf-8') as f:
                    self.current_status = json.load(f)
        except Exception as e:
            logger.warning(f"加载当前状态失败: {e}")
    
    def save_current_status(self):
        """保存当前状态"""
        try:
            status_file = LOGS_DIR / "scheduler_v8_status.json"
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存当前状态失败: {e}")
    
    def log_status(self, task_name, status, progress=0):
        """记录状态"""
        self.current_status['current_task'] = task_name
        self.current_status['learning_progress'] = progress
        logger.info(f"[{task_name}] {status} (进度: {progress}%)")
        self.save_current_status()
    
    def send_alert(self, task_name: str, error_msg: str, level: str = "ERROR"):
        """发送异常报警 - 增强版，带结构化日志和错误分类"""
        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_EMAIL_SEND,
            {"action": "alert", "task": task_name, "level": level}
        )
        start_time = time.time()

        try:
            from src.app.email_sender import EmailSender
            config_path_new = self.base_dir.parent / "config" / "email_config.json"
            config_path_old = self.base_dir / "email_config.json"
            email_config = None

            if config_path_new.exists():
                email_config = config_path_new
            elif config_path_old.exists():
                logger.warning(f"邮件配置使用旧路径(建议迁移至 config/ 目录): {config_path_old}")
                email_config = config_path_old

            if email_config and email_config.exists():
                with open(email_config, 'r', encoding='utf-8') as f:
                    email_conf = json.load(f)

                    sender_email = ConfigSafeLoader.safe_get(
                        email_conf, 'sender_email',
                        default='unknown@example.com'
                    )
                    auth_code = ConfigSafeLoader.safe_get(
                        email_conf, 'auth_code',
                        default=''
                    )
                    smtp_server = ConfigSafeLoader.safe_get_with_category(
                        'network_config', 'smtp_server',
                        {"custom": email_conf}
                    ) or email_conf.get('smtp_server', 'smtp.qq.com')
                    smtp_port = int(ConfigSafeLoader.safe_get_with_category(
                        'network_config', 'smtp_port',
                        {"custom": email_conf}
                    ) or email_conf.get('smtp_port', 465))

                    sender = EmailSender(sender_email, auth_code, smtp_server, smtp_port)

                    subject = f"PL5系统异常报警 - {task_name}"
                    content = f"""
                    <h2>PL5系统异常报警</h2>
                    <p><strong>任务名称:</strong> {task_name}</p>
                    <p><strong>错误类型:</strong> {level}</p>
                    <p><strong>错误信息:</strong> {error_msg}</p>
                    <p><strong>时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p><strong>系统状态:</strong> {json.dumps(self.current_status, ensure_ascii=False, default=str)}</p>
                    """

                    recipients = email_conf.get('recipients', [])
                    send_success = 0
                    for recipient in recipients:
                        try:
                            result = sender.send_report(recipient, subject, content)
                            if result:
                                send_success += 1
                        except Exception as recip_err:
                            logger.warning(f"发送报警邮件至 {recipient} 失败: {recip_err}")

                    duration_ms = (time.time() - start_time) * 1000
                    if send_success > 0:
                        structured_logger.log_operation_success(
                            StructuredLogger.OPERATION_EMAIL_SEND,
                            duration_ms,
                            {
                                "action": "alert",
                                "recipients_count": send_success,
                                "total_recipients": len(recipients)
                            }
                        )
                        logger.info(f"邮件报警已发送至 {send_success}/{len(recipients)} 个收件人")
                    else:
                        structured_logger.log_operation_failure(
                            StructuredLogger.OPERATION_EMAIL_SEND,
                            PL5BaseError("No alert emails sent successfully"),
                            duration_ms
                        )
                        logger.error("所有报警邮件发送失败")
            else:
                logger.warning(f"邮件配置文件不存在: {config_path_new} 或 {config_path_old}，跳过报警邮件")
                structured_logger.log_operation_warning(
                    StructuredLogger.OPERATION_EMAIL_SEND,
                    "Email config not found",
                    {"config_path_new": str(config_path_new), "config_path_old": str(config_path_old)}
                )

        except ConfigError as e:
            logger.error(f"配置错误导致报警失败: {e.to_dict()}")
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_EMAIL_SEND, e,
                (time.time() - start_time) * 1000
            )
        except Exception as e:
            logger.error(f"发送报警邮件失败: {str(e)}", exc_info=True)
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_EMAIL_SEND,
                PL5BaseError(f"Alert email failed: {e}", original_error=e),
                (time.time() - start_time) * 1000
            )
    
    def execute_with_retry(self, task_func, task_name: str, *args, **kwargs):
        """执行任务并带重试机制 - 增强版，支持结构化日志和错误分类"""
        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_TASK_SCHEDULE,
            {"task": task_name, "action": "execute"}
        )
        start_time = time.time()
        retry_count = 0

        while True:
            try:
                result = task_func(*args, **kwargs)
                self.retry_manager.reset_retry_count(task_name)

                duration_ms = (time.time() - start_time) * 1000
                structured_logger.log_operation_success(
                    StructuredLogger.OPERATION_TASK_SCHEDULE,
                    duration_ms,
                    {"task": task_name, "status": "SUCCESS", "retries": retry_count}
                )
                return result
            except Exception as e:
                retry_count += 1

                error_obj = e if isinstance(e, PL5BaseError) else \
                    PL5BaseError(str(e), original_error=e)

                if isinstance(e, DataError):
                    logger.error(f"[{task_name}] 数据错误: {e.to_dict()}")
                elif isinstance(e, ModelError):
                    logger.error(f"[{task_name}] 模型错误: {e.to_dict()}")
                elif isinstance(e, NetworkError):
                    logger.error(f"[{task_name}] 网络错误: {e.to_dict()}")
                elif isinstance(e, ConfigError):
                    logger.warning(f"[{task_name}] 配置警告: {e.to_dict()}, 使用默认值继续")
                    self.retry_manager.reset_retry_count(task_name)
                    return None
                else:
                    logger.error(f"[{task_name}] 未知异常: {str(e)}", exc_info=True)

                self.retry_manager.record_failure(task_name, e)

                if self.retry_manager.should_retry(task_name):
                    # 【修复BUG】先increment计数，再get_delay，确保指数退避从正确基数开始
                    self.retry_manager.increment_retry_count(task_name)
                    delay = self.retry_manager.get_delay(task_name)
                    structured_logger.log_recovery_attempt(
                        StructuredLogger.OPERATION_TASK_SCHEDULE,
                        retry_count,
                        self.retry_manager.retry_config['max_retries'] + 1,
                        RecoveryStrategy.RETRY_WITH_BACKOFF
                    )
                    logger.warning(
                        f"任务 {task_name} 第 {retry_count} 次失败，"
                        f"{delay}秒后重试: {str(e)}"
                    )
                    time.sleep(delay)
                else:
                    duration_ms = (time.time() - start_time) * 1000
                    structured_logger.log_operation_failure(
                        StructuredLogger.OPERATION_TASK_SCHEDULE,
                        error_obj,
                        duration_ms
                    )

                    error_msg = f"任务 {task_name} 多次重试后最终失败: {str(e)}"
                    logger.error(error_msg)
                    self.send_alert(task_name, error_msg)
                    self.history_manager.add_task_record(
                        task_name,
                        "FAILED",
                        datetime.now(),
                        datetime.now(),
                        str(e)
                    )
                    raise
    
    def task_fetch_data(self):
        """自动获取新的开奖数据"""
        logger.info("=" * 80)
        logger.info("【任务1】自动获取开奖数据")
        logger.info("=" * 80)
        self.log_status("数据获取", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "data_fetch"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.data.collector import PL5DataCollector
            collector = PL5DataCollector()
            df = collector.update_data()
            logger.info(f"✓ 数据获取完成: {len(df)} 条记录")

            latest_period = df['period'].iloc[-1]
            logger.info(f"✓ 最新期号: {latest_period}")

            self.current_status['last_run'] = datetime.now().isoformat()
            self.log_status("数据获取", "完成", 100)

            # 【修复】数据获取成功后，自动更新 last_completed_period 到配置文件
            try:
                self.config['last_completed_period'] = str(latest_period)
                self.save_config()
                logger.info(f"✓ 已更新 last_completed_period -> {latest_period}")
            except Exception as cfg_err:
                logger.warning(f"更新 last_completed_period 失败（不影响主流程）: {cfg_err}")

            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, {"record_count": len(df), "latest_period": latest_period})
            
            self.history_manager.add_task_record(
                "data_fetch", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return True
        except Exception as e:
            error_msg = f"数据获取失败: {str(e)}"
            logger.error(error_msg)
            self.log_status("数据获取", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "data_fetch", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False
    
    def task_evaluate(self):
        """评估预测期的逻辑推理及命中情况（智能决策版本）"""
        logger.info("=" * 80)
        logger.info("【任务2】评估预测逻辑与命中情况")
        logger.info("=" * 80)
        logger.info("  智能决策：根据命中率决定后续操作")
        self.log_status("评估分析", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "evaluation"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.strategy_evaluator import StrategyEvaluator
            
            evaluator = StrategyEvaluator()
            
            # 评估所有策略的效果
            logger.info("  开始评估所有策略的效果...")
            self.log_status("评估分析", "评估所有策略", 20)

            # 使用智能动态调整的策略评估
            logger.info("  使用智能动态调整的策略评估")
            logger.info("  目标：先快速完成，然后根据时间深入评估")
            evaluation_result = evaluator.evaluate_all_strategies(test_window=30, target_duration_minutes=45)
            
            # 生成并打印策略对比报告
            report = evaluator.get_strategy_comparison_report(evaluation_result)
            logger.info(f"\n{report}")
            
            final_elapsed = (datetime.now() - start_time).total_seconds() / 3600
            logger.info(f"  评估完成，耗时: {final_elapsed:.2f} 小时")
            
            # === 智能决策核心逻辑 ===
            logger.info("=" * 80)
            logger.info("【智能决策】根据命中率决定后续操作")
            logger.info("=" * 80)
            
            # 获取最佳策略的评估结果
            best_strategy = evaluation_result.get('best_strategy', {})
            if best_strategy:
                best_name = best_strategy.get('name', '未知')
                
                # 获取最佳策略的详细结果
                strategies = evaluation_result.get('strategies', {})
                best_result = strategies.get(best_name, {})
                overall = best_result.get('overall', {})
                
                top1_accuracy = overall.get('top1_accuracy', 0)
                top3_accuracy = overall.get('top3_accuracy', 0)
                top5_accuracy = overall.get('top5_accuracy', 0)
                top8_accuracy = overall.get('top8_accuracy', 0)
                
                logger.info(f"  最佳策略: {best_name}")
                logger.info(f"  Top-1准确率: {top1_accuracy:.4f}")
                logger.info(f"  Top-3准确率: {top3_accuracy:.4f}")
                logger.info(f"  Top-5准确率: {top5_accuracy:.4f}")
                logger.info(f"  Top-8准确率: {top8_accuracy:.4f}")
            else:
                # 没有找到最佳策略，使用默认值
                best_name = '未知'
                top1_accuracy = 0
                top3_accuracy = 0
                top5_accuracy = 0
                top8_accuracy = 0
                logger.info("  未找到最佳策略，使用默认值")
            
            # 【V10.5核心新增】评估实际预测 vs 开奖命中率（反馈闭环）
            logger.info("  [反馈闭环] 开始评估实际预测命中率...")
            actual_hit_summary = self._evaluate_actual_hits()
            if actual_hit_summary:
                logger.info(f"  [反馈闭环] 实际Top-3命中率: {actual_hit_summary.get('top3_accuracy', 0):.4f}")
                logger.info(f"  [反馈闭环] 实际Top-8命中率: {actual_hit_summary.get('top8_accuracy', 0):.4f}")
                # 如果有实际命中率，优先使用实际命中率做决策
                actual_top3 = actual_hit_summary.get('top3_accuracy', 0)
                if actual_top3 > 0:
                    logger.info(f"  [反馈闭环] 使用实际命中率替代回测命中率做决策")
                    top3_accuracy = actual_top3  # 用实际命中率覆盖回测命中率

            # 智能决策阈值
            # Top-3准确率 > 0.4 → 表现很好，只需要策略微调
            # Top-3准确率 > 0.25 → 表现一般，可以策略微调或轻量训练
            # Top-3准确率 < 0.25 → 表现较差，需要深度训练

            if top3_accuracy > 0.4:
                decision = "策略微调"
                should_retrain = False
                reason = f"表现很好，Top-3准确率 {top3_accuracy:.4f}，只需要策略微调"
                logger.info(f"  ✅ 决策: {decision}")
                logger.info(f"  理由: {reason}")
            elif top3_accuracy > 0.25:
                decision = "轻量训练+策略微调"
                should_retrain = True
                reason = f"表现一般，Top-3准确率 {top3_accuracy:.4f}，需要轻量训练+策略微调"
                logger.info(f"  ⚠️ 决策: {decision}")
                logger.info(f"  理由: {reason}")
            else:
                decision = "深度训练"
                should_retrain = True
                reason = f"表现较差，Top-3准确率 {top3_accuracy:.4f}，需要深度训练"
                logger.info(f"  ❌ 决策: {decision}")
                logger.info(f"  理由: {reason}")
            
            logger.info("=" * 80)
            
            self.log_status("评估分析", "完成", 100)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, {
                    "should_retrain": should_retrain, 
                    "reason": reason, 
                    "decision": decision,
                    "evaluation_duration": final_elapsed,
                    "best_strategy": best_strategy,
                    "evaluation_results_count": 1,
                    "top1_accuracy": top1_accuracy,
                    "top3_accuracy": top3_accuracy,
                    "top5_accuracy": top5_accuracy,
                    "top8_accuracy": top8_accuracy
                })
            
            self.history_manager.add_task_record(
                "evaluation", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return should_retrain, reason
        except Exception as e:
            error_msg = f"评估失败: {str(e)}"
            logger.error(error_msg)
            self.log_status("评估分析", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "evaluation", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False, str(e)
    
    def task_optimize(self):
        """依据命中情况进行推理逻辑策略优化学习"""
        logger.info("=" * 80)
        logger.info("【任务3】推理逻辑策略优化学习")
        logger.info("=" * 80)
        self.log_status("策略优化", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "optimization"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.strategy_evaluator import StrategyEvaluator
            from src.core.self_learning import SelfLearningSystem
            
            evaluator = StrategyEvaluator()
            sls = SelfLearningSystem()
            
            # 生成优化建议
            suggestions = sls.generate_optimization_suggestions()
            logger.info(f"优化建议: {suggestions}")
            
            # 测试不同策略的效果 - 这是最重要的！
            logger.info("  开始测试不同推理策略的效果...")
            logger.info("  目标：回答'如果换一种策略又会怎么样？'")
            self.log_status("策略优化", "测试不同策略", 20)
            
            # 使用策略评估器来评估策略
            logger.info("  使用策略评估器评估不同策略组合...")
            self.log_status("策略优化", "策略评估器评估", 40)
            
            # 评估策略（智能动态调整）
            target_duration_minutes = 30  # 优化任务目标时间30分钟
            logger.info(f"  目标运行时间: {target_duration_minutes} 分钟")
            evaluation_result = evaluator.evaluate_all_strategies(
                test_window=30, 
                target_duration_minutes=target_duration_minutes
            )
            
            # 打印策略对比报告
            report = evaluator.get_strategy_comparison_report(evaluation_result)
            logger.info(f"\n{report}")
            
            # 找出最佳策略
            best_strategy = evaluation_result.get('best_strategy', {})
            if best_strategy:
                logger.info(f"\n🏆 发现最佳策略: {best_strategy.get('name')}")
                logger.info(f"   Top-3准确率: {best_strategy.get('score', 0):.4f}")
                logger.info(f"   如果使用这个策略，又会怎么样？可能会有更好的预测效果！")

            # 【V10.5核心新增】运行反馈学习系统，基于实际命中率生成改进建议
            logger.info("=" * 80)
            logger.info("【反馈闭环】启动反馈学习系统，基于实际命中率优化策略")
            logger.info("=" * 80)
            try:
                from src.core.feedback_learning import FeedbackLearningSystem
                fls = FeedbackLearningSystem()

                # 1. 运行反馈分析（基于实际预测历史）
                learning_report = fls.learn_from_feedback()
                logger.info("[反馈闭环] 反馈学习完成，已生成改进建议")

                # 2. 专门优化8码命中率
                eight_code_report = fls.optimize_strategy_for_8code()
                logger.info("[反馈闭环] 8码优化分析完成")

                # 3. 将反馈学习结果传递给SelfLearningSystem
                if learning_report and 'analysis_result' in learning_report:
                    analysis = learning_report['analysis_result']
                    overall = analysis.get('overall_analysis', {})
                    actual_top8 = overall.get('top8_accuracy', 0)
                    actual_top3 = overall.get('top3_accuracy', 0)
                    logger.info(f"[反馈闭环] 反馈学习统计 - 实际Top-3: {actual_top3:.4f}, Top-8: {actual_top8:.4f}")

            except Exception as e:
                logger.warning(f"[反馈闭环] 反馈学习系统运行失败（非致命）: {e}")

            final_elapsed = (datetime.now() - start_time).total_seconds() / 3600
            logger.info(f"  策略优化完成，耗时: {final_elapsed:.2f} 小时")

            sls.flush()
            self.log_status("策略优化", "完成", 100)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, {
                    "suggestions_count": len(suggestions) if suggestions else 0, 
                    "optimization_needed": len(suggestions) > 0, 
                    "optimization_duration": final_elapsed,
                    "best_strategy": best_strategy,
                    "strategy_tested": 1
                })
            
            self.history_manager.add_task_record(
                "optimization", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return True
        except Exception as e:
            error_msg = f"优化失败: {str(e)}"
            logger.error(error_msg)
            self.log_status("策略优化", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "optimization", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False
    
    # =========================================================================
    # 【V10.5新增】预测-开奖反馈闭环辅助方法
    # =========================================================================

    def _record_prediction(self, predictions: Dict, period: str, prediction_type: str = "final"):
        """记录预测结果到 prediction_history.json，用于后续开奖对比"""
        try:
            from src.core.feedback_learning import FeedbackAnalyzer
            analyzer = FeedbackAnalyzer()
            analyzer.update_prediction_history(predictions, period)
            logger.info(f"[反馈闭环] 已记录{prediction_type}预测到prediction_history (期号: {period})")
        except Exception as e:
            logger.warning(f"[反馈闭环] 记录预测失败（非致命）: {e}")

    def _apply_repeat_penalty(self, prediction: Dict, last_period_numbers: Dict[str, int]) -> Tuple[Dict, bool]:
        """
        对预测结果全部重复上期号码的情况进行概率惩罚。
        历史数据显示连续两期完全相同的概率仅约0.013%（万分之一），
        但模型可能因过拟合给出高置信度的重复预测。
        返回: (修正后的预测, 是否触发了惩罚)
        """
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']

        # 检查是否所有位置的top-1都与上期相同
        all_same = True
        for pos in positions:
            if pos in prediction and pos in last_period_numbers:
                top1 = prediction[pos]['top_k'][0]
                if top1 != last_period_numbers[pos]:
                    all_same = False
                    break
            else:
                all_same = False
                break

        if all_same:
            logger.warning("=" * 80)
            logger.warning("【重复号码惩罚】检测到预测结果全部重复上期号码!")
            logger.warning(f"  上期号码: {last_period_numbers}")
            logger.warning("  历史概率: 连续两期完全相同仅约0.013%（万分之一）")
            logger.warning("  模型给出的高置信度重复预测极不可靠，强制执行概率惩罚")
            logger.warning("=" * 80)

            for pos in positions:
                if pos not in prediction:
                    continue
                top_k = prediction[pos]['top_k']
                probs = prediction[pos]['probabilities']

                if len(probs) >= 2:
                    # 将top-1的概率衰减到与top-2相近
                    original_top1_prob = probs[0]
                    original_top2_prob = probs[1]

                    # 惩罚策略：让top-1和top-2概率接近，打破绝对 dominance
                    new_top1_prob = (original_top1_prob + original_top2_prob) / 2
                    new_top2_prob = new_top1_prob

                    probs[0] = new_top1_prob
                    probs[1] = new_top2_prob

                    # 重新归一化
                    total = sum(probs)
                    if total > 0:
                        probs = [p / total for p in probs]

                    # 重新排序top_k（因为概率变了）
                    prob_num_pairs = list(zip(probs, top_k))
                    prob_num_pairs.sort(key=lambda x: x[0], reverse=True)
                    new_top_k = [num for _, num in prob_num_pairs]
                    new_probs = [prob for prob, _ in prob_num_pairs]

                    prediction[pos]['top_k'] = new_top_k
                    prediction[pos]['probabilities'] = new_probs
                    prediction[pos]['repeat_penalty_applied'] = True
                    prediction[pos]['original_top1'] = top_k[0]

            logger.info("【重复号码惩罚】已应用概率修正:")
            for pos in positions:
                if pos in prediction:
                    pk = prediction[pos]['top_k']
                    logger.info(f"  {pos}: {pk[:3]} (原top-1: {prediction[pos].get('original_top1', 'N/A')})")

            return prediction, True

        return prediction, False

    def _evaluate_actual_hits(self) -> Dict:
        """
        【V10.5核心新增】评估实际预测 vs 实际开奖结果的命中率。
        读取 prediction_history.json 和最新开奖数据，对比计算真实命中率，
        并将结果记录到 feedback_learning_history.json，形成知识图谱。
        """
        try:
            from src.core.feedback_learning import FeedbackAnalyzer
            from src.core.data.collector import PL5DataCollector

            logger.info("=" * 80)
            logger.info("【反馈闭环】评估实际预测 vs 开奖命中率")
            logger.info("=" * 80)

            collector = PL5DataCollector()
            df = collector.load_processed_data()
            if df is None or len(df) == 0:
                logger.warning("[反馈闭环] 无数据，跳过实际命中率评估")
                return {}

            # 加载预测历史
            analyzer = FeedbackAnalyzer()
            predictions = analyzer.prediction_history
            if not predictions:
                logger.warning("[反馈闭环] prediction_history为空，无法评估实际命中率")
                return {}

            logger.info(f"[反馈闭环] 加载到 {len(predictions)} 条预测历史记录")

            positions = ['wan', 'qian', 'bai', 'shi', 'ge']
            hit_records = []

            for pred_record in predictions:
                period = pred_record.get('period')
                pred_data = pred_record.get('predictions', {})

                # 查找该期的实际开奖结果
                actual_row = df[df['period'].astype(str) == str(period)]
                if actual_row.empty:
                    logger.debug(f"[反馈闭环] 期号 {period} 的开奖数据尚未获取，跳过")
                    continue

                actual = {}
                for pos in positions:
                    actual[pos] = int(actual_row[pos].iloc[0])

                # 计算各层级命中率
                record = {
                    'period': period,
                    'timestamp': pred_record.get('timestamp'),
                    'actual': actual,
                    'hits': {}
                }

                for pos in positions:
                    if pos not in pred_data:
                        continue
                    top_k = pred_data[pos].get('top_k', [])
                    actual_num = actual[pos]

                    record['hits'][pos] = {
                        'actual': actual_num,
                        'top1_hit': actual_num in top_k[:1] if len(top_k) >= 1 else False,
                        'top3_hit': actual_num in top_k[:3] if len(top_k) >= 3 else False,
                        'top5_hit': actual_num in top_k[:5] if len(top_k) >= 5 else False,
                        'top8_hit': actual_num in top_k[:8] if len(top_k) >= 8 else False,
                        'predicted_top_k': top_k
                    }

                hit_records.append(record)

            if not hit_records:
                logger.info("[反馈闭环] 暂无已开奖的可评估预测记录")
                return {}

            # 汇总统计
            total = len(hit_records)
            summary = {
                'total_evaluated': total,
                'periods': [r['period'] for r in hit_records],
                'top1_hits': sum(1 for r in hit_records for p in positions if r['hits'].get(p, {}).get('top1_hit')),
                'top3_hits': sum(1 for r in hit_records for p in positions if r['hits'].get(p, {}).get('top3_hit')),
                'top5_hits': sum(1 for r in hit_records for p in positions if r['hits'].get(p, {}).get('top5_hit')),
                'top8_hits': sum(1 for r in hit_records for p in positions if r['hits'].get(p, {}).get('top8_hit')),
                'total_position_tests': total * len(positions),
                'evaluation_time': datetime.now().isoformat()
            }

            summary['top1_accuracy'] = summary['top1_hits'] / summary['total_position_tests']
            summary['top3_accuracy'] = summary['top3_hits'] / summary['total_position_tests']
            summary['top5_accuracy'] = summary['top5_hits'] / summary['total_position_tests']
            summary['top8_accuracy'] = summary['top8_hits'] / summary['total_position_tests']

            logger.info("=" * 80)
            logger.info("【反馈闭环】实际命中率统计结果")
            logger.info("=" * 80)
            logger.info(f"  评估期数: {total} 期")
            logger.info(f"  测试位置数: {summary['total_position_tests']} 个")
            logger.info(f"  Top-1 命中率: {summary['top1_hits']}/{summary['total_position_tests']} = {summary['top1_accuracy']:.4f}")
            logger.info(f"  Top-3 命中率: {summary['top3_hits']}/{summary['total_position_tests']} = {summary['top3_accuracy']:.4f}")
            logger.info(f"  Top-5 命中率: {summary['top5_hits']}/{summary['total_position_tests']} = {summary['top5_accuracy']:.4f}")
            logger.info(f"  Top-8 命中率: {summary['top8_hits']}/{summary['total_position_tests']} = {summary['top8_accuracy']:.4f}")
            logger.info("=" * 80)

            # 保存到 feedback_learning_history
            feedback_entry = {
                'timestamp': datetime.now().isoformat(),
                'type': 'actual_hit_evaluation',
                'summary': summary,
                'hit_records': hit_records[-20:]  # 只保存最近20期
            }

            feedback_path = MODELS_DIR / "feedback_learning_history.json"
            try:
                existing = []
                if feedback_path.exists():
                    with open(feedback_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                if not isinstance(existing, list):
                    existing = []
                existing.append(feedback_entry)
                # 只保留最近100条
                if len(existing) > 100:
                    existing = existing[-100:]
                with open(feedback_path, 'w', encoding='utf-8') as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
                logger.info(f"[反馈闭环] 已保存命中率评估到 {feedback_path}")
            except Exception as e:
                logger.warning(f"[反馈闭环] 保存feedback_learning_history失败: {e}")

            return summary

        except Exception as e:
            logger.error(f"[反馈闭环] 实际命中率评估异常: {e}", exc_info=True)
            return {}

    def _get_best_feature_config(self, force_validate: bool = False) -> dict:
        """【V10.4修复】获取最佳特征配置，支持缓存过期和强制验证
        
        修复问题：
        1. 动态特征验证从未真正执行的问题
        2. 添加缓存过期机制（24小时）
        3. 在深度训练时强制执行动态验证
        
        Args:
            force_validate: 是否强制执行动态验证（深度训练时应为True）
        """
        from datetime import timedelta
        
        # 【V10.4新增】检查是否需要强制验证
        if not force_validate:
            # 检查缓存是否存在且未过期
            for config_dir in [LOGS_DIR, MODELS_DIR]:
                best_config_path = config_dir / "best_feature_config.json"
                if best_config_path.exists():
                    try:
                        with open(best_config_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                        
                        # 【V10.4新增】检查缓存是否过期（超过24小时）
                        last_updated_str = config_data.get('last_updated', '')
                        if last_updated_str:
                            try:
                                last_updated = datetime.fromisoformat(last_updated_str)
                                cache_age = datetime.now() - last_updated
                                if cache_age > timedelta(hours=24):
                                    logger.info(f"[_get_best_feature_config] 缓存已过期（{cache_age.total_seconds()/3600:.1f}小时），将执行动态验证")
                                    force_validate = True
                                    break
                            except Exception as e:
                                logger.warning(f"[_get_best_feature_config] 解析缓存时间失败: {e}")
                        
                        # 缓存有效，直接返回
                        if not force_validate:
                            if 'best_config' in config_data:
                                best_config = config_data['best_config']
                                logger.info(f"[_get_best_feature_config] 从缓存加载最佳特征配置: {best_config}")
                                return best_config
                            else:
                                logger.info(f"[_get_best_feature_config] 从缓存加载最佳特征配置: {config_data}")
                                return config_data
                    except Exception as e:
                        logger.warning(f"[_get_best_feature_config] 读取缓存失败: {e}")
        
        # 【V10.4修复】执行动态特征验证
        logger.info("=" * 60)
        logger.info("【动态特征验证】开始执行多特征组验证...")
        logger.info("=" * 60)
        
        from src.core.features.dynamic_validator import DynamicFeatureValidator
        validator = DynamicFeatureValidator()
        
        try:
            validation_result = validator.validate_and_update_features()

            if validation_result['success']:
                best_config = validation_result['best_config']
                logger.info(f"【动态特征验证】完成！最佳配置: {best_config}")
                
                # 【V10.4新增】记录验证报告
                if 'report' in validation_result:
                    report = validation_result['report']
                    logger.info(f"【动态特征验证】验证了 {len(report.get('all_results', []))} 种特征组合")
                    if 'improvement' in report:
                        imp = report['improvement']
                        logger.info(f"【动态特征验证】相比默认配置提升: {imp.get('improvement_pct', 0):.2f}%")
                
                return best_config
            else:
                logger.warning(f"【动态特征验证】失败: {validation_result.get('error', '未知错误')}，使用默认配置")
                return {
                    'select_top': None,
                    'feature_selection_method': 'rfe'
                }
        except Exception as e:
            logger.error(f"【动态特征验证】异常: {e}，使用默认配置")
            return {
                'select_top': None,
                'feature_selection_method': 'rfe'
            }
    
    def _save_feature_config(self, config: dict):
        """【V10.2修复】保存特征配置到文件，与 dynamic_validator.py 保持一致（同时保存到两个目录）"""
        try:
            # 统一保存格式，与 dynamic_validator.py 保持一致
            config_data = {
                'best_config': config,
                'last_updated': datetime.now().isoformat()
            }
            # 【V10.2修复】同时保存到 LOGS_DIR 和 MODELS_DIR，与 dynamic_validator.py 保持一致
            for config_dir in [LOGS_DIR, MODELS_DIR]:
                best_config_path = config_dir / "best_feature_config.json"
                with open(best_config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                logger.info(f"[_save_feature_config] 特征配置已保存到: {best_config_path}")
        except Exception as e:
            logger.warning(f"[_save_feature_config] 保存特征配置失败: {e}")
    
    def _load_all_verification_results(self) -> Dict:
        """【V10.4新增】加载所有佐证结果
        
        Returns:
            Dict: 包含所有佐证结果的字典
        """
        results = {}
        verification_files = [
            ("first_verification", "first_prediction_verification.json"),
            ("second_verification", "second_prediction_verification.json"),
            ("third_verification", "third_prediction_verification.json"),
            ("final_verification", "final_prediction_verification.json"),
            ("deep_strategy", "deep_strategy_optimization.json"),
        ]
        
        for result_key, result_file in verification_files:
            result_path = LOGS_DIR / result_file
            if result_path.exists():
                try:
                    with open(result_path, 'r', encoding='utf-8') as rf:
                        results[result_key] = json.load(rf)
                    logger.info(f"[_load_all_verification_results] 已读取 {result_file}")
                except Exception as e:
                    logger.warning(f"[_load_all_verification_results] 读取 {result_file} 失败: {e}")
            else:
                logger.info(f"[_load_all_verification_results] {result_file} 不存在")
        
        return results
    
    def _calculate_verification_consistency(self, verification_results: Dict) -> Dict:
        """【V10.4新增】计算佐证一致性分数
        
        Args:
            verification_results: 所有佐证结果
            
        Returns:
            Dict: 包含整体一致性和各位置一致性的字典
        """
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        all_predictions = []
        
        # 收集所有佐证的预测结果
        for name, result in verification_results.items():
            if result and 'predictions' in result:
                all_predictions.append(result['predictions'])
        
        if len(all_predictions) < 2:
            logger.info("[_calculate_verification_consistency] 佐证次数不足，返回默认一致性")
            return {'overall': 1.0, 'positions': {}, 'verification_count': len(all_predictions)}
        
        # 计算各位置的一致性
        consistency = {}
        for pos in positions:
            top_k_sets = []
            for pred in all_predictions:
                if pos in pred and 'top_k' in pred[pos]:
                    top_k_sets.append(set(pred[pos]['top_k'][:3]))  # Top-3 一致性
            
            if len(top_k_sets) >= 2:
                # 计算交集比例
                common = set.intersection(*top_k_sets)
                consistency[pos] = len(common) / 3  # 最大为3
            else:
                consistency[pos] = 1.0  # 数据不足时默认一致
        
        # 计算整体一致性
        overall = sum(consistency.values()) / len(consistency) if consistency else 0
        
        return {
            'overall': overall,
            'positions': consistency,
            'verification_count': len(all_predictions)
        }
    
    def task_incremental_train(self):
        """执行增量训练（08:00-10:00）"""
        logger.info("=" * 80)
        logger.info("【任务4.1】增量训练")
        logger.info("=" * 80)
        self.log_status("增量训练", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "incremental_training"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.data.collector import PL5DataCollector
            from src.core.features.engineer import FeatureEngineer
            from src.core.models.enhanced_predictor import EnhancedPL5Predictor
            
            self.log_status("增量训练", "加载数据", 10)
            collector = PL5DataCollector()
            df = collector.update_data()
            if df is None or len(df) == 0:
                raise ValueError("无法加载训练数据")
            logger.info(f"  数据加载完成: {len(df)} 条记录")
            logger.info(f"  最新期号: {df['period'].iloc[-1]}")
            
            self.log_status("增量训练", "动态特征验证", 20)
            # 【V10.1修复】使用统一方法获取最佳特征配置
            best_config = self._get_best_feature_config()
            # 【V10.1修复】保存配置供后续预测任务使用
            self._save_feature_config(best_config)
            
            self.log_status("增量训练", "特征工程", 30)
            engineer = FeatureEngineer()
            df_features = engineer.extract_all_features(
                df,
                select_top=best_config['select_top'],
                feature_selection_method=best_config['feature_selection_method']
            )
            
            feature_cols = [
                col for col in df_features.columns
                if col not in ['date', 'period', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']
            ]
            logger.info(f"  特征工程完成: {len(feature_cols)} 个特征")
            
            predictor = EnhancedPL5Predictor()
            loaded = predictor.load_models()
            
            if loaded:
                logger.info("  执行增量训练...")
                self.log_status("增量训练", "执行增量更新", 60)
                
                # 增量更新模型
                predictor.feature_cols = feature_cols
                
                # 对每个位置的模型进行增量更新
                for pos in ["wan", "qian", "bai", "shi", "ge"]:
                    if pos in predictor.stacking:
                        for name, model in predictor.stacking[pos].position_models.items():
                            if hasattr(model, 'warm_start'):
                                model.warm_start = True
                                model.n_estimators += 10  # 少量增加树的数量
                                logger.info(f"    {pos}/{name}: 增量增加至 {model.n_estimators} 棵树")
                
                # 执行增量训练
                predictor.fit(df_features, feature_cols, parallel=True, incremental=True)
                predictor.save_models()
                logger.info("  增量训练完成")
            else:
                logger.warning("  模型未加载，执行全量训练")
                self.log_status("增量训练", "执行全量训练", 60)
                predictor.fit(df_features, feature_cols, parallel=True)
                predictor.save_models()
                logger.info("  全量训练完成")
            
            # 确保训练时长在合理范围内（最多2小时）
            elapsed = (datetime.now() - start_time).total_seconds() / 3600
            logger.info(f"  训练时长: {elapsed:.1f} 小时")
            
            self.log_status("增量训练", "完成", 100)
            logger.info("  增量训练完成")
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, {
                    "training_type": "incremental",
                    "training_duration": elapsed,
                    "feature_count": len(feature_cols),
                    "data_count": len(df),
                    "feature_config": best_config
                })
            
            self.history_manager.add_task_record(
                "incremental_training", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return True
        except Exception as e:
            error_msg = f"增量训练失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_status("增量训练", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "incremental_training", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False
    
    def task_train(self):
        """对下一期进行深度训练（22:00-02:00）"""
        logger.info("=" * 80)
        logger.info("【任务4】深度学习训练")
        logger.info("=" * 80)
        self.log_status("深度学习", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "training"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.data.collector import PL5DataCollector
            from src.core.features.engineer import FeatureEngineer
            from src.core.models.enhanced_predictor import EnhancedPL5Predictor
            from src.core.self_learning import SelfLearningSystem
            
            self.log_status("深度学习", "加载数据", 5)
            collector = PL5DataCollector()
            # 首先更新数据，确保使用最新数据进行训练
            df = collector.update_data()
            if df is None or len(df) == 0:
                raise ValueError("无法加载训练数据")
            logger.info(f"  数据加载完成: {len(df)} 条记录")
            logger.info(f"  最新期号: {df['period'].iloc[-1]}")
            
            self.log_status("深度学习", "动态特征验证", 15)
            # 【V10.4修复】深度训练时强制执行动态特征验证
            # 这是客户期望的核心功能：训练中智能动态应用多个特征组来检验训练最优效果
            best_config = self._get_best_feature_config(force_validate=True)
            # 【V10.1修复】保存配置供后续预测任务使用
            self._save_feature_config(best_config)
            
            self.log_status("深度学习", "特征工程", 20)
            engineer = FeatureEngineer()
            df_features = engineer.extract_all_features(
                df,
                select_top=best_config['select_top'],
                feature_selection_method=best_config['feature_selection_method']
            )
            
            feature_cols = [
                col for col in df_features.columns
                if col not in ['date', 'period', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']
            ]
            logger.info(f"  特征工程完成: {len(feature_cols)} 个特征")
            
            self.log_status("深度学习", "检查训练策略", 30)
            sls = SelfLearningSystem()
            should_retrain, reason = sls.should_trigger_retrain()
            
            predictor = EnhancedPL5Predictor()
            
            # 检查特征维度是否匹配，如果不匹配则强制重新训练
            loaded = predictor.load_models()
            if loaded and hasattr(predictor, 'feature_cols') and predictor.feature_cols:
                old_feature_count = len(predictor.feature_cols)
                new_feature_count = len(feature_cols)
                if old_feature_count != new_feature_count:
                    logger.warning(f"  特征维度不匹配: 旧模型{old_feature_count}维，新数据{new_feature_count}维，强制重新训练")
                    should_retrain = True
                    reason = f"特征维度不匹配({old_feature_count} != {new_feature_count})"
            
            if not should_retrain and loaded:
                logger.info(f"  性能稳定({reason})，尝试增量更新集成模型...")
                self.log_status("深度学习", "增量更新集成模型", 40)
                try:
                    predictor.feature_cols = feature_cols
                    logger.info(f"  特征列已更新: {len(feature_cols)} 个特征")
                    
                    for pos in ["wan", "qian", "bai", "shi", "ge"]:
                        if pos in predictor.stacking:
                            for name, model in predictor.stacking[pos].position_models.items():
                                if hasattr(model, 'warm_start'):
                                    model.warm_start = True
                                    model.n_estimators += 20  # 增加更多树以延长训练时间
                                    logger.info(f"    {pos}/{name}: 增量增加至 {model.n_estimators} 棵树")
                    predictor.save_models()
                    logger.info("  增量更新完成")
                except Exception as e:
                    logger.warning(f"  增量更新失败，回退到全量训练: {str(e)}")
                    predictor.fit(df_features, feature_cols, parallel=False)
                    predictor.save_models()
            else:
                self.log_status("深度学习", "全量训练HMM/Copula/BSTS/集成模型", 40)
                logger.info(f"  触发全量训练: {reason}")
                predictor.fit(df_features, feature_cols, parallel=False)
                predictor.save_models()
                logger.info("  全部模型训练完成")
            
            # 【修复BUG-03】将无限while循环改为有界强化训练：
            # 最多执行 MAX_EXTRA_ROUNDS 轮，且总时长不得超过 max_training_hours，
            # 防止永久阻塞调度线程。
            elapsed = (datetime.now() - start_time).total_seconds() / 3600
            logger.info(f"  实际训练时长: {elapsed:.1f} 小时")

            MAX_EXTRA_ROUNDS = 3          # 最多额外强化轮次
            max_training_hours = 10.0     # 绝对上限（小时）
            extra_round = 0

            while elapsed < 5.0 and extra_round < MAX_EXTRA_ROUNDS:
                extra_round += 1
                remaining = 5.0 - elapsed
                logger.info(f"  [强化训练] 第{extra_round}轮，还需 {remaining:.1f}h 达到最少训练时长")
                self.log_status("深度学习", f"强化训练{extra_round}/{MAX_EXTRA_ROUNDS}", 90)

                try:
                    for pos in ["wan", "qian", "bai", "shi", "ge"]:
                        if pos in predictor.stacking:
                            for name, model in predictor.stacking[pos].position_models.items():
                                if hasattr(model, 'warm_start') and hasattr(model, 'n_estimators'):
                                    model.warm_start = True
                                    model.n_estimators += 30
                                    logger.info(f"    {pos}/{name}: 强化→{model.n_estimators}棵树")
                    predictor.fit(df_features, feature_cols, parallel=False)
                    predictor.save_models()
                    logger.info(f"  [强化训练] 第{extra_round}轮完成")
                except Exception as reinforce_err:
                    logger.warning(f"  [强化训练] 第{extra_round}轮失败，跳过: {reinforce_err}")

                elapsed = (datetime.now() - start_time).total_seconds() / 3600
                if elapsed >= max_training_hours:
                    logger.info(f"  已达最大训练时长 {max_training_hours}h，停止")
                    break
            
            # 【V10.3优化】保存特征版本，确保训练和预测一致
            self.log_status("深度学习", "保存特征版本", 95)
            feature_manager = get_feature_version_manager()
            version_id = feature_manager.save_feature_version(
                feature_cols=feature_cols,
                feature_config=best_config,
                metadata={
                    "training_period": str(df['period'].iloc[-1]),
                    "data_count": len(df),
                    "training_type": "deep_training"
                }
            )
            logger.info(f"  特征版本已保存: {version_id}")
            
            # 训练完成
            final_elapsed = (datetime.now() - start_time).total_seconds() / 3600
            logger.info(f"  最终训练时长: {final_elapsed:.1f} 小时")
            
            sls.flush()
            self.log_status("深度学习", "完成", 100)
            logger.info("  深度学习训练完成")
            
            # 保存训练信息（【修复BUG-04】latest_period 强制转 str，防止 numpy.int64 序列化失败）
            training_info = {
                'model_version': 'V10.3',
                'training_time': (datetime.now() - start_time).total_seconds(),
                'feature_count': len(feature_cols),
                'data_count': len(df),
                'latest_period': str(df['period'].iloc[-1]),
                'training_status': 'SUCCESS'
            }
            
            training_info_path = LOGS_DIR / "training_info.json"
            with open(training_info_path, 'w', encoding='utf-8') as f:
                json.dump(training_info, f, indent=2, ensure_ascii=False)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, training_info)
            
            self.history_manager.add_task_record(
                "training", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return True
        except (ModelError, DataError) as e:
            # 【V10.4修复】模型/数据错误 - 严重但可恢复，记录详细日志
            error_msg = f"训练失败(模型/数据错误): {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_status("深度学习", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "training", "FAILED", start_time, datetime.now(), error_msg
            )
            return False
        except (ConfigError, ConfigValueError) as e:
            # 【V10.4修复】配置错误 - 需要人工介入
            error_msg = f"训练失败(配置错误): {str(e)}"
            logger.critical(error_msg, exc_info=True)
            self.log_status("深度学习", f"配置错误: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "training", "FAILED", start_time, datetime.now(), error_msg
            )
            return False
        except MemoryError:
            # 【V10.4修复】内存不足 - 系统级错误
            error_msg = "训练失败: 内存不足"
            logger.critical(error_msg, exc_info=True)
            self.log_status("深度学习", "内存不足", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "training", "FAILED", start_time, datetime.now(), error_msg
            )
            return False
        except Exception as e:
            # 【V10.4修复】未知异常 - 兜底处理
            error_msg = f"训练失败(未知错误): {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_status("深度学习", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "training", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False
    
    def task_send_report(self):
        """发送训练报告到邮箱（包含预测期号、性能指标、训练状态和模型版本号）- 增强版"""
        logger.info("=" * 80)
        logger.info("【任务5】发送训练报告")
        logger.info("=" * 80)
        self.log_status("发送报告", "开始执行", 0)

        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_EMAIL_SEND,
            {"action": "send_report"}
        )
        start_time = datetime.now()
        task_name = "send_report"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)

        try:
            from src.app.analyze_and_send import analyze_and_send
            from src.core.data.collector import PL5DataCollector
            import json

            training_info = {
                'model_version': 'V10.3',
                'training_time': 0,
                'feature_count': 0,
                'data_count': 0,
                'latest_period': '',
                'training_status': 'UNKNOWN'
            }

            training_info_path = LOGS_DIR / "training_info.json"
            if training_info_path.exists():
                try:
                    with open(training_info_path, 'r', encoding='utf-8') as f:
                        training_info = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"加载训练信息失败（非致命）: {e}")
                    structured_logger.log_operation_warning(
                        StructuredLogger.OPERATION_EMAIL_SEND,
                        "Training info load failed",
                        {"error": str(e)}
                    )

            collector = PL5DataCollector()
            df = collector.load_processed_data()
            if df is not None and len(df) > 0:
                latest_period = df['period'].iloc[-1]
                next_period = str(int(latest_period) + 1)
                logger.info(f"  最新期号: {latest_period}")
                logger.info(f"  预测期号: {next_period}")
            else:
                next_period = '未知'
                logger.warning("  无法获取最新期号")

            logger.info(f"  调用分析发送模块...")
            # 【修复BUG-05 + V2扩展】不再同步调用预测任务。
            # 此处读取所有已生成的验证结果文件（含首次/二次/三次佐证），
            # 供 analyze_and_send() 生成综合报告。
            all_verification_results = {}
            verification_files = [
                ("first_verification",  "first_prediction_verification.json"),
                ("second_verification", "second_prediction_verification.json"),
                ("third_verification",  "third_prediction_verification.json"),
                ("final_verification",  "final_prediction_verification.json"),
                ("deep_strategy",       "deep_strategy_optimization.json"),
            ]
            for result_key, result_file in verification_files:
                result_path = LOGS_DIR / result_file
                if result_path.exists():
                    try:
                        with open(result_path, 'r', encoding='utf-8') as rf:
                            _res = json.load(rf)
                            all_verification_results[result_key] = _res
                        logger.info(f"  已读取 {result_file}: OK")
                    except Exception as read_err:
                        logger.warning(f"  读取 {result_file} 失败（非致命）: {read_err}")
                else:
                    logger.warning(f"  {result_file} 不存在，对应任务可能尚未执行")
            
            # 【V10.3优化】读取日循环最终预测结果，传给 analyze_and_send 跳过重复推理
            precomputed_predictions = None
            for prediction_file in ["pre_sale_prediction.json", "final_prediction.json"]:
                pred_path = LOGS_DIR / prediction_file
                if pred_path.exists():
                    try:
                        with open(pred_path, 'r', encoding='utf-8') as pf:
                            pred_data = json.load(pf)
                        raw_pred = pred_data.get('pre_sale_predictions', pred_data.get('predictions', None))
                        if raw_pred:
                            precomputed_predictions = raw_pred
                            logger.info(f"  已读取 {prediction_file}，将使用该预测结果（跳过重复推理）")
                            break
                    except Exception as pred_err:
                        logger.warning(f"  读取 {prediction_file} 失败（非致命）: {pred_err}")
            
            if precomputed_predictions is None:
                logger.info("  [说明] 未找到日循环预计算预测结果，analyze_and_send 将执行即时推理")
            
            # 发送报告（传入佐证结果 + 预计算预测）
            result = analyze_and_send(
                verification_results=all_verification_results,
                precomputed_predictions=precomputed_predictions
            )

            report_info = {
                'report_time': datetime.now().isoformat(),
                'prediction_period': next_period,
                'model_version': training_info.get('model_version', 'V10.3'),
                'training_status': training_info.get('training_status', 'SUCCESS'),
                'training_time': training_info.get('training_time', 0),
                'latest_data_period': training_info.get('latest_period', ''),
                'feature_count': training_info.get('feature_count', 0),
                'data_count': training_info.get('data_count', 0),
                'send_result': result
            }

            report_info_path = LOGS_DIR / "report_info.json"
            with open(report_info_path, 'w', encoding='utf-8') as f:
                json.dump(report_info, f, indent=2, ensure_ascii=False)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            structured_logger.log_operation_success(
                StructuredLogger.OPERATION_EMAIL_SEND,
                duration_ms,
                {
                    "prediction_period": next_period,
                    "model_version": training_info.get('model_version'),
                    "send_result": result
                }
            )

            self.log_status("发送报告", "完成", 100)
            logger.info("✓ 报告发送完成")
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, report_info)

            self.history_manager.add_task_record(
                "send_report",
                "SUCCESS",
                start_time,
                datetime.now()
            )
            return True
        except DataError as e:
            error_msg = f"数据错误导致发送失败: {e.to_dict()}"
            logger.error(error_msg)
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            self._record_send_failure(start_time, error_msg, str(e))
            return False
        except NetworkError as e:
            error_msg = f"网络错误导致发送失败: {e.to_dict()}"
            logger.error(error_msg)
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            self._record_send_failure(start_time, error_msg, str(e))
            return False
        except Exception as e:
            error_msg = f"发送失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            self._record_send_failure(start_time, error_msg, str(e))
            return False

    def _record_send_failure(self, start_time: datetime, error_msg: str, detail: str):
        """记录发送失败信息"""
        self.log_status("发送报告", f"失败: {detail}", 0)
        structured_logger.log_operation_failure(
            StructuredLogger.OPERATION_EMAIL_SEND,
            PL5BaseError(error_msg, original_error=Exception(detail)),
            (datetime.now() - start_time).total_seconds() * 1000
        )
        self.history_manager.add_task_record(
            "send_report",
            "FAILED",
            start_time,
            datetime.now(),
            error_msg
        )
    
    def _get_task_handler(self, task_name: str):
        """根据任务名从 task_map 动态获取处理器方法（用于 run_full_pipeline）"""
        if hasattr(self, 'task_map') and task_name in self.task_map:
            return self.task_map[task_name][1]
        return None

    def run_full_pipeline(self):
        """运行完整流程 - 增强版，带结构化日志和错误分类"""
        logger.info("\n" + "=" * 80)
        logger.info("开始执行完整自动化流程 (增强错误处理)")
        logger.info("=" * 80)

        structured_logger.log_operation_start(
            StructuredLogger.OPERATION_TASK_SCHEDULE,
            {"action": "full_pipeline"}
        )
        start_time = datetime.now()

        # 使用完整佐证链（与 setup_schedule 的 custom_tasks 保持一致）
        task_chain = self.custom_tasks
        results = {}

        try:
            for task_name in task_chain:
                # 动态查找任务处理器（来自 task_map）
                task_handler = self._get_task_handler(task_name)

                logger.info(f"执行任务: {task_name}")
                try:
                    if task_handler is None:
                        # 无处理器，记录警告并跳过
                        logger.warning(f"任务 {task_name} 无处理器，跳过")
                        results[task_name] = {"status": "SKIPPED", "reason": "no handler"}
                        continue

                    success = False
                    if task_name == 'data_fetch':
                        success = self.execute_with_retry(self.task_fetch_data, 'data_fetch')
                    elif task_name == 'evaluation':
                        result = self.execute_with_retry(self.task_evaluate, 'evaluation')
                        success = result is not None and isinstance(result, tuple)
                    elif task_name == 'send_report':
                        success = self.execute_with_retry(self.task_send_report, 'send_report')
                    else:
                        # 通用处理器（增量训练/佐证链/调优任务统一调用）
                        success = self.execute_with_retry(task_handler, task_name)

                    results[task_name] = {"status": "SUCCESS" if success else "FAILED"}

                    if not success:
                        logger.error(f"任务 {task_name} 执行失败")
                except DataError as e:
                    logger.error(f"[数据错误] 任务 {task_name}: {e.to_dict()}")
                    results[task_name] = {"status": "FAILED", "error_type": "DataError", "detail": str(e)}
                except ModelError as e:
                    logger.error(f"[模型错误] 任务 {task_name}: {e.to_dict()}")
                    results[task_name] = {"status": "FAILED", "error_type": "ModelError", "detail": str(e)}
                except NetworkError as e:
                    logger.error(f"[网络错误] 任务 {task_name}: {e.to_dict()}")
                    results[task_name] = {"status": "FAILED", "error_type": "NetworkError", "detail": str(e)}
                except ConfigError as e:
                    logger.warning(f"[配置警告] 任务 {task_name}: {e.to_dict()}")
                    results[task_name] = {"status": "SUCCESS_WITH_WARNING", "error_type": "ConfigWarning", "detail": str(e)}
                except Exception as e:
                    logger.error(f"[未知异常] 任务 {task_name}: {str(e)}", exc_info=True)
                    results[task_name] = {"status": "FAILED", "error_type": "Unknown", "detail": str(e)}

            duration_sec = (datetime.now() - start_time).total_seconds()
            success_count = sum(1 for r in results.values() if r.get('status') in ('SUCCESS', 'SUCCESS_WITH_WARNING'))
            total_executed = len([r for r in results.values() if r.get('status') != 'SKIPPED'])

            self.current_status['last_successful_run'] = datetime.now().isoformat()
            self.save_current_status()

            structured_logger.log_operation_success(
                StructuredLogger.OPERATION_TASK_SCHEDULE,
                duration_sec * 1000,
                {
                    "total_tasks": len(task_chain),
                    "success_count": success_count,
                    "total_executed": total_executed,
                    "duration_seconds": round(duration_sec, 2),
                    "task_results": {k: v["status"] for k, v in results.items()}
                }
            )

            logger.info("\n" + "=" * 80)
            logger.info(f"完整流程执行完毕: {success_count}/{total_executed} 成功, 耗时 {duration_sec:.1f}s")
            for task_name, result in results.items():
                status_icon = "✓" if result.get('status') in ('SUCCESS', 'SUCCESS_WITH_WARNING') else \
                              "⊘" if result.get('status') == 'SKIPPED' else "✗"
                logger.info(f"  {status_icon} {task_name}: {result['status']}")
            logger.info("=" * 80)
            return success_count == total_executed

        except Exception as e:
            duration_sec = (datetime.now() - start_time).total_seconds()
            structured_logger.log_operation_failure(
                StructuredLogger.OPERATION_TASK_SCHEDULE,
                PL5BaseError(f"Pipeline execution error: {e}", original_error=e),
                duration_sec * 1000
            )
            logger.error(f"流程执行异常: {str(e)}", exc_info=True)
            self.send_alert("完整流程", str(e))
            return False
    
    def task_final_prediction(self):
        """生成最终预测结果 - 【V10.4修复】整合佐证结果"""
        logger.info("=" * 80)
        logger.info("【任务11】生成最终预测结果")
        logger.info("=" * 80)
        self.log_status("最终预测", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "final_prediction"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.models.enhanced_predictor import EnhancedPL5Predictor
            from src.core.config import ModelConfig
            from src.core.features.engineer import FeatureEngineer
            from src.core.data.collector import PL5DataCollector
            
            # 【V10.4新增】读取所有佐证结果
            verification_results = self._load_all_verification_results()
            
            # 【V10.4新增】计算佐证一致性
            consistency_scores = self._calculate_verification_consistency(verification_results)
            logger.info(f"【佐证一致性】整体一致性: {consistency_scores['overall']:.2%}")
            for pos, score in consistency_scores.get('positions', {}).items():
                logger.info(f"  {pos}位一致性: {score:.2%}")
            
            # 加载数据
            collector = PL5DataCollector()
            data = collector.load_processed_data()
            
            # 【V10.1修复】使用与训练一致的特征配置
            best_config = self._get_best_feature_config()
            logger.info(f"[final_prediction] 使用特征配置: {best_config}")
            
            # 生成特征（使用与训练一致的特征配置）
            engineer = FeatureEngineer(enable_parallel=False)
            features = engineer.extract_all_features(
                data,
                select_top=best_config.get('select_top', None),
                feature_selection_method=best_config.get('feature_selection_method', 'rfe'),
                detect_drift=False,
                enable_scaler=False
            )
            
            # 加载模型并对齐特征
            model_config = ModelConfig()
            predictor = EnhancedPL5Predictor(model_config)
            predictor.load_models()
            
            # 【关键修复】使用模型存储的 feature_cols 而非全量特征
            if predictor.feature_cols and len(predictor.feature_cols) > 0:
                missing = [c for c in predictor.feature_cols if c not in features.columns]
                if missing:
                    logger.warning(f"[final_prediction] 模型特征列中有 {len(missing)} 个缺失，将用0填充")
                    for col in missing:
                        features[col] = 0.0
                feature_cols = predictor.feature_cols
            else:
                feature_cols = [col for col in features.columns if col not in ['date', 'period', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']]
            
            # 使用最新的特征进行预测
            test_row = features.iloc[-1]
            test_features = test_row[feature_cols].values.astype(float)
            
            # 【V3修复】从原始 data 而非 features 提取 recent_original_data
            recent_original_data = {}
            positions = ['wan', 'qian', 'bai', 'shi', 'ge']
            for pos in positions:
                recent_original_data[pos] = data[pos].values[-10:]
            
            # 生成预测
            prediction = predictor.predict(test_features, recent_original_data, top_k=8)

            # 【V10.5新增】获取上期开奖号码，用于重复惩罚
            last_period_numbers = {
                'wan': int(data['wan'].iloc[-1]),
                'qian': int(data['qian'].iloc[-1]),
                'bai': int(data['bai'].iloc[-1]),
                'shi': int(data['shi'].iloc[-1]),
                'ge': int(data['ge'].iloc[-1])
            }

            # 【V10.5核心新增】应用重复号码惩罚
            prediction, penalty_applied = self._apply_repeat_penalty(prediction, last_period_numbers)

            # 【V10.5核心新增】记录预测到prediction_history，用于开奖后对比
            next_period = str(int(data['period'].iloc[-1]) + 1)
            self._record_prediction(prediction, next_period, prediction_type="final")

            # 【V10.4新增】基于佐证一致性调整预测权重
            if consistency_scores['overall'] < 0.5:
                logger.warning(f"【佐证一致性警告】一致性较低 ({consistency_scores['overall']:.2%})，预测结果可能不稳定")
            elif consistency_scores['overall'] >= 0.7:
                logger.info(f"【佐证一致性良好】一致性较高 ({consistency_scores['overall']:.2%})，预测结果可信度高")
            
            # 保存预测结果
            prediction_info = {
                'prediction_time': datetime.now().isoformat(),
                'latest_period': int(data['period'].iloc[-1]),
                'next_period': str(int(data['period'].iloc[-1]) + 1),
                'predictions': prediction,
                'feature_config': best_config,
                'verification_consistency': consistency_scores,
                'verification_results_summary': {
                    k: {
                        'timestamp': v.get('timestamp', ''),
                        'predictions': {pos: v.get('predictions', {}).get(pos, {}).get('top_k', [])[:3] 
                                       for pos in positions}
                    }
                    for k, v in verification_results.items() if v
                }
            }
            
            if penalty_applied:
                prediction_info['repeat_penalty_applied'] = True
                prediction_info['last_period_numbers'] = last_period_numbers
            
            prediction_path = LOGS_DIR / "final_prediction.json"
            with open(prediction_path, 'w', encoding='utf-8') as f:
                json.dump(prediction_info, f, indent=2, ensure_ascii=False)
            
            logger.info("✓ 最终预测完成")
            logger.info(f"预测期号: {prediction_info['next_period']}")
            for pos, data in prediction.items():
                logger.info(f"  {pos}: {data['top_k']}")
            
            self.log_status("最终预测", "完成", 100)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, prediction_info)
            
            self.history_manager.add_task_record(
                "final_prediction", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return True
        except Exception as e:
            error_msg = f"最终预测失败: {str(e)}"
            logger.error(error_msg)
            self.log_status("最终预测", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "final_prediction", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False
    
    def task_final_prediction_verification(self):
        """验证最终预测结果"""
        logger.info("=" * 80)
        logger.info("【任务12】验证最终预测结果")
        logger.info("=" * 80)
        self.log_status("预测验证", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "final_prediction_verification"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.models.enhanced_predictor import EnhancedPL5Predictor
            from src.core.config import ModelConfig
            from src.core.features.engineer import FeatureEngineer
            from src.core.data.collector import PL5DataCollector
            
            # 加载数据
            collector = PL5DataCollector()
            data = collector.load_processed_data()
            
            # 【V10.1修复】使用与训练一致的特征配置
            best_config = self._get_best_feature_config()
            logger.info(f"[final_prediction_verification] 使用特征配置: {best_config}")
            
            # 生成特征（使用与训练一致的特征配置）
            engineer = FeatureEngineer(enable_parallel=False)
            features = engineer.extract_all_features(
                data,
                select_top=best_config.get('select_top', None),
                feature_selection_method=best_config.get('feature_selection_method', 'rfe'),
                detect_drift=False,
                enable_scaler=False
            )
            
            # 加载模型并对齐特征
            model_config = ModelConfig()
            predictor = EnhancedPL5Predictor(model_config)
            predictor.load_models()
            
            if predictor.feature_cols and len(predictor.feature_cols) > 0:
                missing = [c for c in predictor.feature_cols if c not in features.columns]
                if missing:
                    logger.warning(f"[final_prediction_verification] 模型特征列缺失 {len(missing)} 个")
                    for col in missing:
                        features[col] = 0.0
                feature_cols = predictor.feature_cols
            else:
                feature_cols = [col for col in features.columns if col not in ['date', 'period', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']]
            
            # 使用最新的特征进行验证预测
            test_row = features.iloc[-1]
            test_features = test_row[feature_cols].values.astype(float)
            
            # 【V3修复】从原始 data 而非 features 提取 recent_original_data
            recent_original_data = {}
            positions = ['wan', 'qian', 'bai', 'shi', 'ge']
            for pos in positions:
                recent_original_data[pos] = data[pos].values[-10:]
            
            # 生成验证预测
            verification_prediction = predictor.predict(test_features, recent_original_data, top_k=8)
            
            # 加载之前的预测结果
            prediction_path = LOGS_DIR / "final_prediction.json"
            if prediction_path.exists():
                with open(prediction_path, 'r', encoding='utf-8') as f:
                    previous_prediction = json.load(f)
            else:
                previous_prediction = None
            
            # 比较两次预测结果
            verification_info = {
                'verification_time': datetime.now().isoformat(),
                'latest_period': int(data['period'].iloc[-1]),
                'next_period': str(int(data['period'].iloc[-1]) + 1),
                'verification_predictions': verification_prediction,
                'previous_predictions': previous_prediction,
                'feature_config': best_config
            }
            
            # 计算预测一致性
            consistency = {}
            if previous_prediction:
                for pos in positions:
                    prev_top_k = previous_prediction['predictions'][pos]['top_k']
                    curr_top_k = verification_prediction[pos]['top_k']
                    common = set(prev_top_k) & set(curr_top_k)
                    consistency[pos] = len(common) / len(prev_top_k) if prev_top_k else 0
                verification_info['consistency'] = consistency
                logger.info("预测一致性:")
                for pos, score in consistency.items():
                    logger.info(f"  {pos}: {score:.2f}")
            
            # 保存验证结果
            verification_path = LOGS_DIR / "prediction_verification.json"
            with open(verification_path, 'w', encoding='utf-8') as f:
                json.dump(verification_info, f, indent=2, ensure_ascii=False)
            
            logger.info("✓ 最终预测验证完成")
            logger.info(f"验证期号: {verification_info['next_period']}")
            for pos, data in verification_prediction.items():
                logger.info(f"  {pos}: {data['top_k']}")
            
            self.log_status("预测验证", "完成", 100)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, verification_info)
            
            self.history_manager.add_task_record(
                "final_prediction_verification", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return True
        except Exception as e:
            error_msg = f"最终预测验证失败: {str(e)}"
            logger.error(error_msg)
            self.log_status("预测验证", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "final_prediction_verification", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False
    
    def task_pre_sale_prediction(self):
        """售前最终预测（停售前1小时）"""
        logger.info("=" * 80)
        logger.info("【任务13】售前最终预测")
        logger.info("=" * 80)
        self.log_status("售前预测", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "pre_sale_prediction"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.models.enhanced_predictor import EnhancedPL5Predictor
            from src.core.config import ModelConfig
            from src.core.features.engineer import FeatureEngineer
            from src.core.data.collector import PL5DataCollector
            
            # 加载数据
            collector = PL5DataCollector()
            data = collector.load_processed_data()
            
            # 【V10.1修复】使用与训练一致的特征配置
            best_config = self._get_best_feature_config()
            logger.info(f"[pre_sale_prediction] 使用特征配置: {best_config}")
            
            # 生成特征（使用与训练一致的特征配置）
            engineer = FeatureEngineer(enable_parallel=False)
            features = engineer.extract_all_features(
                data,
                select_top=best_config.get('select_top', None),
                feature_selection_method=best_config.get('feature_selection_method', 'rfe'),
                detect_drift=False,
                enable_scaler=False
            )
            
            # 加载模型并对齐特征
            model_config = ModelConfig()
            predictor = EnhancedPL5Predictor(model_config)
            predictor.load_models()
            
            if predictor.feature_cols and len(predictor.feature_cols) > 0:
                missing = [c for c in predictor.feature_cols if c not in features.columns]
                if missing:
                    logger.warning(f"[pre_sale_prediction] 模型特征列缺失 {len(missing)} 个")
                    for col in missing:
                        features[col] = 0.0
                feature_cols = predictor.feature_cols
            else:
                feature_cols = [col for col in features.columns if col not in ['date', 'period', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']]
            
            # 使用最新的特征进行预测
            test_row = features.iloc[-1]
            test_features = test_row[feature_cols].values.astype(float)
            
            # 【V3修复】从原始 data 而非 features 提取 recent_original_data
            recent_original_data = {}
            positions = ['wan', 'qian', 'bai', 'shi', 'ge']
            for pos in positions:
                recent_original_data[pos] = data[pos].values[-10:]
            
            # 生成最终预测
            pre_sale_prediction = predictor.predict(test_features, recent_original_data, top_k=8)

            # 【V10.5新增】获取上期开奖号码，用于重复惩罚
            last_period_numbers = {
                'wan': int(data['wan'].iloc[-1]),
                'qian': int(data['qian'].iloc[-1]),
                'bai': int(data['bai'].iloc[-1]),
                'shi': int(data['shi'].iloc[-1]),
                'ge': int(data['ge'].iloc[-1])
            }

            # 【V10.5核心新增】应用重复号码惩罚
            pre_sale_prediction, penalty_applied = self._apply_repeat_penalty(pre_sale_prediction, last_period_numbers)

            # 【V10.5核心新增】记录预测到prediction_history
            next_period = str(int(data['period'].iloc[-1]) + 1)
            self._record_prediction(pre_sale_prediction, next_period, prediction_type="pre_sale")

            # 保存售前预测结果
            pre_sale_info = {
                'pre_sale_time': datetime.now().isoformat(),
                'latest_period': int(data['period'].iloc[-1]),
                'next_period': str(int(data['period'].iloc[-1]) + 1),
                'pre_sale_predictions': pre_sale_prediction,
                'feature_config': best_config
            }
            
            pre_sale_path = LOGS_DIR / "pre_sale_prediction.json"
            with open(pre_sale_path, 'w', encoding='utf-8') as f:
                json.dump(pre_sale_info, f, indent=2, ensure_ascii=False)
            
            logger.info("✓ 售前最终预测完成")
            logger.info(f"预测期号: {pre_sale_info['next_period']}")
            for pos, data in pre_sale_prediction.items():
                logger.info(f"  {pos}: {data['top_k']}")
            
            self.log_status("售前预测", "完成", 100)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, pre_sale_info)
            
            self.history_manager.add_task_record(
                "pre_sale_prediction", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return True
        except Exception as e:
            error_msg = f"售前最终预测失败: {str(e)}"
            logger.error(error_msg)
            self.log_status("售前预测", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "pre_sale_prediction", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False
    
    def _run_prediction_verification(self, task_name: str, round_name: str, output_file: str) -> bool:
        """【V1+V3修复】统一的预测验证执行器，支持独立的首次/二次/三次佐证。
        
        Args:
            task_name: 任务名称（传递给 orchestrator）
            round_name: 轮次名称（首次佐证/二次佐证/三次佐证）
            output_file: 输出 JSON 文件名
        """
        logger.info("=" * 80)
        logger.info(f"【{round_name}】执行预测验证")
        logger.info("=" * 80)
        self.log_status(round_name, "开始执行", 0)
        
        start_time = datetime.now()
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.models.enhanced_predictor import EnhancedPL5Predictor
            from src.core.config import ModelConfig
            from src.core.features.engineer import FeatureEngineer
            from src.core.data.collector import PL5DataCollector
            from src.core.strategy_evaluator import StrategyEvaluator
            
            # 1. 验证推理策略
            logger.info(f"步骤1 [{round_name}]: 验证当前推理策略...")
            evaluator = StrategyEvaluator()
            evaluation_result = evaluator.evaluate_all_strategies(test_window=20)
            # 【V10.3修复】添加 None 检查，防止 best_strategy 为 None 时出错
            best_strategy = evaluation_result.get('best_strategy', {})
            if best_strategy:
                logger.info(f"  最佳策略: {best_strategy.get('name', '未知')}")
            else:
                logger.info(f"  最佳策略: 未知")
            
            # 2. 加载原始数据（使用 update_data 确保最新数据）
            collector = PL5DataCollector()
            data = collector.load_processed_data()
            logger.info(f"  原始数据: {len(data)} 条，最新期号: {int(data['period'].iloc[-1])}")
            
            # 【V10.1修复】使用与训练一致的特征配置
            best_config = self._get_best_feature_config()
            logger.info(f"[{round_name}] 使用特征配置: {best_config}")
            
            # 3. 生成特征（使用与训练一致的特征配置）
            engineer = FeatureEngineer(enable_parallel=False)
            features = engineer.extract_all_features(
                data,
                select_top=best_config.get('select_top', None),
                feature_selection_method=best_config.get('feature_selection_method', 'rfe'),
                detect_drift=False,
                enable_scaler=False
            )
            
            # 【V10.3优化】检查特征一致性
            logger.info(f"步骤3.1 [{round_name}]: 检查特征一致性...")
            feature_manager = get_feature_version_manager()
            current_features = [col for col in features.columns if col not in ['date', 'period', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']]
            consistency_result = feature_manager.check_feature_consistency(current_features)
            
            if not consistency_result['consistent']:
                logger.warning(f"[{round_name}] 特征一致性警告: {consistency_result.get('reason')}")
                if 'added_features' in consistency_result:
                    logger.warning(f"  新增特征数: {consistency_result.get('added_count', 0)}")
                    if consistency_result['added_features']:
                        logger.warning(f"  新增特征示例: {consistency_result['added_features']}")
                if 'removed_features' in consistency_result:
                    logger.warning(f"  移除特征数: {consistency_result.get('removed_count', 0)}")
                    if consistency_result['removed_features']:
                        logger.warning(f"  移除特征示例: {consistency_result['removed_features']}")
            else:
                logger.info(f"[{round_name}] 特征一致性检查通过: 版本 {consistency_result.get('version_id', 'unknown')}")
            
            # 4. 加载模型并对齐特征（V1关键修复：使用模型存储的 feature_cols 而非全量特征）
            model_config = ModelConfig()
            predictor = EnhancedPL5Predictor(model_config)
            predictor.load_models()
            
            if predictor.feature_cols and len(predictor.feature_cols) > 0:
                # 用模型训练时的精确特征集
                missing = [c for c in predictor.feature_cols if c not in features.columns]
                if missing:
                    logger.warning(f"[{round_name}] 模型特征列中有 {len(missing)} 个缺失，将用0填充: {missing[:3]}")
                    for col in missing:
                        features[col] = 0.0
                feature_cols = predictor.feature_cols
                logger.info(f"[{round_name}] 使用模型训练时的 {len(feature_cols)} 个特征列")
            else:
                feature_cols = [col for col in features.columns if col not in ['date', 'period', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']]
                logger.warning(f"[{round_name}] 模型无 feature_cols，使用全量特征 {len(feature_cols)} 个")
            
            # 5. 提取特征向量
            test_row = features.iloc[-1]
            test_features = test_row[feature_cols].values.astype(float)
            
            # 6. 提取最近的原始数据（V3修复：从原始 data 而非 features，确保与模型训练一致）
            recent_original_data = {}
            positions = ['wan', 'qian', 'bai', 'shi', 'ge']
            for pos in positions:
                recent_original_data[pos] = data[pos].values[-10:]
            
            # 7. 生成预测
            prediction = predictor.predict(test_features, recent_original_data, top_k=8)
            
            # 8. 保存验证结果（每个轮次写入独立文件）
            verification_info = {
                'verification_time': datetime.now().isoformat(),
                'verification_round': round_name,
                'task_name': task_name,
                'latest_period': int(data['period'].iloc[-1]),
                'next_period': str(int(data['period'].iloc[-1]) + 1),
                'predictions': prediction,
                'strategy_evaluation': evaluation_result,
                'feature_config': best_config
            }
            
            output_path = LOGS_DIR / output_file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(verification_info, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✓ {round_name} 完成")
            logger.info(f"预测期号: {verification_info['next_period']}")
            for pos, pred_data in prediction.items():
                logger.info(f"  {pos}: {pred_data['top_k']}")
            
            self.log_status(round_name, "完成", 100)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, verification_info)
            
            self.history_manager.add_task_record(
                task_name,
                "SUCCESS",
                start_time,
                datetime.now()
            )
            return True
        except Exception as e:
            error_msg = f"{round_name}失败: {str(e)}"
            logger.error(error_msg)
            self.log_status(round_name, f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                task_name,
                "FAILED",
                start_time,
                datetime.now(),
                error_msg
            )
            return False
    
    def task_first_prediction_verification(self):
        """首次预测验证（首次佐证）"""
        return self._run_prediction_verification(
            task_name="first_prediction_verification",
            round_name="首次佐证",
            output_file="first_prediction_verification.json"
        )
    
    def task_second_prediction_verification(self):
        """二次预测验证（二次佐证）【V1新增独立handler】"""
        return self._run_prediction_verification(
            task_name="second_prediction_verification",
            round_name="二次佐证",
            output_file="second_prediction_verification.json"
        )
    
    def task_third_prediction_verification(self):
        """三次预测验证（三次佐证）【V1新增独立handler】"""
        return self._run_prediction_verification(
            task_name="third_prediction_verification",
            round_name="三次佐证",
            output_file="third_prediction_verification.json"
        )
    
    def task_deep_strategy_optimization(self):
        """深度策略优化（四次佐证）"""
        logger.info("=" * 80)
        logger.info("【任务9】深度策略优化（四次佐证）")
        logger.info("=" * 80)
        self.log_status("深度策略优化", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "deep_strategy_optimization"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.strategy_evaluator import StrategyEvaluator
            from src.core.self_learning import SelfLearningSystem
            
            evaluator = StrategyEvaluator()
            sls = SelfLearningSystem()
            
            # 使用多个测试窗口进行深度优化
            test_windows = [15, 20, 25, 30, 35]
            all_results = []
            
            for i, window in enumerate(test_windows):
                progress = int((i + 1) / len(test_windows) * 80)
                self.log_status("深度策略优化", f"测试窗口: {window}期", progress)
                logger.info(f"  测试窗口: {window}期")
                
                evaluation_result = evaluator.evaluate_all_strategies(test_window=window)
                all_results.append({
                    'window': window,
                    'result': evaluation_result
                })
                
                # 打印策略对比报告
                report = evaluator.get_strategy_comparison_report(evaluation_result)
                logger.info(f"\n{report}")
                
                time.sleep(30)  # 每次测试间隔
            
            # 分析所有测试结果，找出最优策略
            best_strategy_name = None
            best_score = -1
            for result_data in all_results:
                strategy = result_data['result'].get('best_strategy', {})
                score = strategy.get('score', 0)
                if score > best_score:
                    best_score = score
                    best_strategy_name = strategy.get('name')
            
            logger.info(f"\n🏆 深度优化完成，最佳策略: {best_strategy_name}, 得分: {best_score:.4f}")
            
            # 保存深度策略优化结果
            deep_optimization_info = {
                'optimization_time': datetime.now().isoformat(),
                'optimization_type': '四次佐证',
                'test_windows': test_windows,
                'best_strategy': best_strategy_name,
                'best_score': best_score,
                'all_results': all_results
            }
            
            deep_optimization_path = LOGS_DIR / "deep_strategy_optimization.json"
            with open(deep_optimization_path, 'w', encoding='utf-8') as f:
                json.dump(deep_optimization_info, f, indent=2, ensure_ascii=False)
            
            sls.flush()
            self.log_status("深度策略优化", "完成", 100)
            logger.info("✓ 深度策略优化完成（四次佐证）")
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, deep_optimization_info)
            
            self.history_manager.add_task_record(
                "deep_strategy_optimization", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return True
        except Exception as e:
            error_msg = f"深度策略优化失败: {str(e)}"
            logger.error(error_msg)
            self.log_status("深度策略优化", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "deep_strategy_optimization", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False
    
    def task_prediction_preview(self):
        """预测结果预生成（五次佐证）"""
        logger.info("=" * 80)
        logger.info("【任务10】预测结果预生成（五次佐证）")
        logger.info("=" * 80)
        self.log_status("预测预生成", "开始执行", 0)
        
        start_time = datetime.now()
        task_name = "prediction_preview"
        
        if self.workflow_enabled and self.orchestrator:
            self.orchestrator.start_task(task_name)
        
        try:
            from src.core.models.enhanced_predictor import EnhancedPL5Predictor
            from src.core.config import ModelConfig
            from src.core.features.engineer import FeatureEngineer
            from src.core.data.collector import PL5DataCollector
            from src.core.strategy_evaluator import StrategyEvaluator
            
            # 1. 最终验证推理策略
            logger.info("步骤1: 最终验证推理策略...")
            evaluator = StrategyEvaluator()
            evaluation_result = evaluator.evaluate_all_strategies(test_window=25)
            logger.info(f"  当前最佳策略: {evaluation_result.get('best_strategy', {}).get('name', '未知')}")
            
            # 2. 加载数据
            collector = PL5DataCollector()
            data = collector.load_processed_data()
            
            # 【V10.1修复】使用与训练一致的特征配置
            best_config = self._get_best_feature_config()
            logger.info(f"[prediction_preview] 使用特征配置: {best_config}")
            
            # 3. 生成特征（使用与训练一致的特征配置）
            engineer = FeatureEngineer(enable_parallel=False)
            features = engineer.extract_all_features(
                data,
                select_top=best_config.get('select_top', None),
                feature_selection_method=best_config.get('feature_selection_method', 'rfe'),
                detect_drift=False,
                enable_scaler=False
            )
            # 【BUG-3修复】与其他任务保持一致，排除 period/full_number/parse_line
            feature_cols = [col for col in features.columns
                            if col not in ['period', 'date', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']]
            
            # 4. 加载模型
            model_config = ModelConfig()
            predictor = EnhancedPL5Predictor(model_config)
            
            # 【BUG-2关联修复】使用模型已训练的 feature_cols，确保训练-预测特征完全一致
            if hasattr(predictor, 'feature_cols') and predictor.feature_cols:
                available_feature_cols = [c for c in predictor.feature_cols if c in features.columns]
                if available_feature_cols:
                    feature_cols = available_feature_cols
                    logger.info(f"[prediction_preview] 使用模型feature_cols({len(feature_cols)}个)")
                else:
                    logger.warning("[prediction_preview] 模型feature_cols与当前特征不匹配，使用过滤后的feature_cols")
            
            # 5. 使用最新的特征进行预预测
            test_row = features.iloc[-1]
            test_features = test_row[feature_cols].values.astype(float)
            
            # 6. 提取最近的原始数据
            recent_data = {}
            positions = ['wan', 'qian', 'bai', 'shi', 'ge']
            for pos in positions:
                recent_data[pos] = data[pos].values[-10:]
            
            # 7. 生成预预测（五次佐证）
            preview_prediction = predictor.predict(test_features, recent_data, top_k=8)
            
            # 8. 对比之前的预测结果
            previous_predictions = {}
            consistency_scores = {}
            
            # 检查首次验证结果
            first_verification_path = LOGS_DIR / "first_prediction_verification.json"
            if first_verification_path.exists():
                with open(first_verification_path, 'r', encoding='utf-8') as f:
                    first_verification = json.load(f)
                    previous_predictions['首次佐证'] = first_verification.get('predictions', {})
            
            # 计算一致性
            for source_name, prev_pred in previous_predictions.items():
                consistency = {}
                for pos in positions:
                    if pos in prev_pred and pos in preview_prediction:
                        prev_top_k = prev_pred[pos].get('top_k', [])
                        curr_top_k = preview_prediction[pos].get('top_k', [])
                        common = set(prev_top_k) & set(curr_top_k)
                        consistency[pos] = len(common) / len(prev_top_k) if prev_top_k else 0
                consistency_scores[source_name] = consistency
                logger.info(f"与{source_name}的一致性:")
                for pos, score in consistency.items():
                    logger.info(f"  {pos}: {score:.2f}")
            
            # 9. 保存预测预生成结果
            preview_info = {
                'preview_time': datetime.now().isoformat(),
                'preview_type': '五次佐证',
                'latest_period': int(data['period'].iloc[-1]),
                'next_period': str(int(data['period'].iloc[-1]) + 1),
                'predictions': preview_prediction,
                'previous_predictions': previous_predictions,
                'consistency_scores': consistency_scores,
                'strategy_evaluation': evaluation_result,
                'feature_config': best_config
            }
            
            preview_path = LOGS_DIR / "prediction_preview.json"
            with open(preview_path, 'w', encoding='utf-8') as f:
                json.dump(preview_info, f, indent=2, ensure_ascii=False)
            
            logger.info("✓ 预测结果预生成完成（五次佐证）")
            logger.info(f"预测期号: {preview_info['next_period']}")
            for pos, data in preview_prediction.items():
                logger.info(f"  {pos}: {data['top_k']}")
            
            self.log_status("预测预生成", "完成", 100)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.complete_task(task_name, preview_info)
            
            self.history_manager.add_task_record(
                "prediction_preview", 
                "SUCCESS", 
                start_time, 
                datetime.now()
            )
            return True
        except Exception as e:
            error_msg = f"预测结果预生成失败: {str(e)}"
            logger.error(error_msg)
            self.log_status("预测预生成", f"失败: {str(e)}", 0)
            
            if self.workflow_enabled and self.orchestrator:
                self.orchestrator.fail_task(task_name, error_msg)
            
            self.history_manager.add_task_record(
                "prediction_preview", 
                "FAILED", 
                start_time, 
                datetime.now(), 
                error_msg
            )
            return False
    
    def _schedule_thread_wrapper(self, task_func):
        """在独立线程中执行定时任务，防止长时间任务阻塞后续任务"""
        task_name = getattr(task_func, '__name__', str(task_func))
        lock_name = f'_lock_{task_name}'
        if not hasattr(self, lock_name):
            setattr(self, lock_name, threading.Lock())
        lock = getattr(self, lock_name)
        if lock.locked():
            logger.warning(f'[线程安全] 任务 {task_name} 已在执行中，跳过本次触发')
            return
        t = threading.Thread(target=task_func, daemon=True)
        t.start()
    
    def setup_schedule(self):
        """设置定时任务 - 从配置读取时间（完整佐证流程）"""
        logger.info("=" * 80)
        logger.info("设置定时任务（完整佐证流程）")
        logger.info("=" * 80)
        
        # 【V10.1修复】从配置文件读取所有时间点，默认时间与客户配置保持一致
        data_fetch_time = self.config.get('data_fetch_time', '22:15')
        evaluation_time = self.config.get('evaluation_time', '22:15')
        optimization_start = self.config.get('optimization_start', '22:45')
        training_start = self.config.get('training_start', '00:30')
        incremental_training_morning = self.config.get('incremental_training_morning', '08:00')
        first_prediction_verification = self.config.get('first_prediction_verification', '10:00')
        incremental_training_noon = self.config.get('incremental_training_noon', '12:00')
        second_prediction_verification = self.config.get('second_prediction_verification', '13:00')      # 【佐证链修复】二次预测验证
        incremental_training_afternoon = self.config.get('incremental_training_afternoon', '14:00')
        third_prediction_verification = self.config.get('third_prediction_verification', '15:00')        # 【佐证链修复】三次预测验证
        deep_strategy_optimization = self.config.get('deep_strategy_optimization', '16:00')
        prediction_preview = self.config.get('prediction_preview', '17:00')
        final_prediction_time = self.config.get('final_prediction_time', '18:00')
        final_prediction_verification_time = self.config.get('final_prediction_verification_time', '19:00')
        pre_sale_prediction_time = self.config.get('pre_sale_prediction_time', '20:00')
        email_send_time = self.config.get('email_send_time', '20:15')
        
        # 任务1: 自动获取开奖数据 (22:15)
        schedule.every().day.at(data_fetch_time).do(lambda: self._schedule_thread_wrapper(self.task_fetch_data))
        logger.info(f"[OK] {data_fetch_time} - 自动获取开奖数据")
        
        # 任务2: 评估预测逻辑与命中情况 (22:15) - 评估在训练之前
        schedule.every().day.at(evaluation_time).do(lambda: self._schedule_thread_wrapper(self.task_evaluate))
        logger.info(f"[OK] {evaluation_time} - 评估预测逻辑与命中情况")
        
        # 任务3: 推理逻辑策略优化学习 (22:45)
        schedule.every().day.at(optimization_start).do(lambda: self._schedule_thread_wrapper(self.task_optimize))
        logger.info(f"[OK] {optimization_start} - 推理逻辑策略优化学习")
        
        # 任务4: 开始深度训练 (00:30)
        schedule.every().day.at(training_start).do(lambda: self._schedule_thread_wrapper(self.task_train))
        logger.info(f"[OK] {training_start} - 开始深度训练")
        
        # 任务5: 进行增量训练（上午） (08:00) - 首次佐证前的增量学习
        schedule.every().day.at(incremental_training_morning).do(lambda: self._schedule_thread_wrapper(self.task_incremental_train))
        logger.info(f"[OK] {incremental_training_morning} - 进行增量训练（上午）- 首次佐证")
        
        # 任务6: 首次预测验证 (10:00) - 首次佐证，验证推理逻辑
        schedule.every().day.at(first_prediction_verification).do(lambda: self._schedule_thread_wrapper(self.task_first_prediction_verification))
        logger.info(f"[OK] {first_prediction_verification} - 首次预测验证（首次佐证）")
        
        # 任务7: 进行增量训练（中午） (12:00) - 二次佐证前的增量学习
        schedule.every().day.at(incremental_training_noon).do(lambda: self._schedule_thread_wrapper(self.task_incremental_train))
        logger.info(f"[OK] {incremental_training_noon} - 进行增量训练（中午）- 二次佐证前训练")
        
        # 【佐证链修复】任务7b: 二次预测验证 (13:00) - 二次佐证
        schedule.every().day.at(second_prediction_verification).do(lambda: self._schedule_thread_wrapper(self.task_second_prediction_verification))
        logger.info(f"[OK] {second_prediction_verification} - 二次预测验证（二次佐证）")
        
        # 任务8: 进行增量训练（下午） (14:00) - 三次佐证前的增量学习
        schedule.every().day.at(incremental_training_afternoon).do(lambda: self._schedule_thread_wrapper(self.task_incremental_train))
        logger.info(f"[OK] {incremental_training_afternoon} - 进行增量训练（下午）- 三次佐证前训练")
        
        # 【佐证链修复】任务8b: 三次预测验证 (15:00) - 三次佐证
        schedule.every().day.at(third_prediction_verification).do(lambda: self._schedule_thread_wrapper(self.task_third_prediction_verification))
        logger.info(f"[OK] {third_prediction_verification} - 三次预测验证（三次佐证）")
        
        # 任务9: 深度策略优化 (16:00) - 四次佐证
        schedule.every().day.at(deep_strategy_optimization).do(lambda: self._schedule_thread_wrapper(self.task_deep_strategy_optimization))
        logger.info(f"[OK] {deep_strategy_optimization} - 深度策略优化（四次佐证）")
        
        # 任务10: 预测结果预生成 (17:00) - 五次佐证
        schedule.every().day.at(prediction_preview).do(lambda: self._schedule_thread_wrapper(self.task_prediction_preview))
        logger.info(f"[OK] {prediction_preview} - 预测结果预生成（五次佐证）")
        
        # 任务11: 生成最终预测结果 (18:00)
        schedule.every().day.at(final_prediction_time).do(lambda: self._schedule_thread_wrapper(self.task_final_prediction))
        logger.info(f"[OK] {final_prediction_time} - 生成最终预测结果")
        
        # 任务12: 验证最终预测结果 (19:00) - 六次佐证
        schedule.every().day.at(final_prediction_verification_time).do(lambda: self._schedule_thread_wrapper(self.task_final_prediction_verification))
        logger.info(f"[OK] {final_prediction_verification_time} - 验证最终预测结果（六次佐证）")
        
        # 任务13: 售前最终预测 (20:00)
        schedule.every().day.at(pre_sale_prediction_time).do(lambda: self._schedule_thread_wrapper(self.task_pre_sale_prediction))
        logger.info(f"[OK] {pre_sale_prediction_time} - 售前最终预测")
        
        # 任务14: 发送训练报告和最终预测到邮箱 (20:00)
        schedule.every().day.at(email_send_time).do(lambda: self._schedule_thread_wrapper(self.task_send_report))
        logger.info(f"[OK] {email_send_time} - 发送训练报告和最终预测到邮箱")
        
        logger.info("=" * 80)
        logger.info("完整佐证流程已设置完成！")
        logger.info("=" * 80)
    
    def check_intelligent_scheduling(self):
        if not self.workflow_enabled or not self.orchestrator:
            return
        
        intelligent_config = self.workflow_config.get('intelligent_scheduling', {})
        if not intelligent_config.get('enabled', True):
            return
        
        # 【启动保护】系统启动后5分钟内，不执行补执行，等待 schedule 定时器触发
        if hasattr(self, 'start_time'):
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed < 300:  # 启动后5分钟内
                logger.info(f"[智能调度] 调度器刚启动 {elapsed:.0f} 秒，等待 schedule 定时器触发（还需等待 {300 - elapsed:.0f} 秒）")
                return
        
        now = datetime.now()

        cycle_trigger_time = datetime.strptime('22:00', '%H:%M').time()
        data_fetch_time = datetime.strptime(self.config.get('data_fetch_time', '22:15'), '%H:%M').time()
        send_report_time = datetime.strptime(self.config.get('email_send_time', '20:15'), '%H:%M').time()
        standby_start_time = datetime.strptime('21:00', '%H:%M').time()
        
        if self.time_scheduler:
            summary = self.time_scheduler.get_schedule_summary()
            strategy = summary.get('strategy', 'unknown')
            time_to_draw = summary.get('time_to_draw', 'unknown')
            logger.debug(f"[智能调度] 当前策略: {strategy}, 距离开奖: {time_to_draw}")  # 【V10.4修复】降为DEBUG级别
        
        in_daily_cycle = False
        cycle_start = None
        cycle_end = None
        
        today_2200 = datetime.combine(now.date(), cycle_trigger_time)
        tomorrow_2015 = datetime.combine(now.date() + timedelta(days=1), send_report_time)
        yesterday_2200 = datetime.combine(now.date() - timedelta(days=1), cycle_trigger_time)
        today_2015 = datetime.combine(now.date(), send_report_time)
        
        if now >= today_2200:
            cycle_start = today_2200
            cycle_end = tomorrow_2015
            in_daily_cycle = True
        elif now <= today_2015:
            cycle_start = yesterday_2200
            cycle_end = today_2015
            in_daily_cycle = True
        else:
            if now.time() >= standby_start_time and now.time() < cycle_trigger_time:
                logger.debug(f"[智能调度] 系统待机时间 (21:00-22:00)，距下一个日循环还有 {(today_2200 - now).seconds // 60} 分钟")  # 【V10.4修复】降为DEBUG
            else:
                logger.debug(f"[智能调度] 不在日循环周期内，距下一个日循环还有 {(today_2200 - now).seconds // 60} 分钟")  # 【V10.4修复】降为DEBUG
            return
        
        if in_daily_cycle:
            logger.debug(f"[智能调度] 在日循环周期内 [{cycle_start.strftime('%Y-%m-%d %H:%M')} → {cycle_end.strftime('%Y-%m-%d %H:%M')}]")  # 【V10.4修复】降为DEBUG
        
        current_cycle_date = self.orchestrator._get_current_cycle_date().isoformat()
        saved_cycle_date = self.orchestrator.state.get("cycle_date")
        
        if saved_cycle_date and saved_cycle_date != current_cycle_date:
            logger.info(f"[智能调度] 检测到新周期（当前: {current_cycle_date}, 保存: {saved_cycle_date}），重置工作流状态")
            self.orchestrator.reset_workflow()
            self._register_custom_tasks()
        
        workflow_state = self.orchestrator.get_current_workflow_state()
        workflow_status = workflow_state.get("workflow_status")
        if workflow_status == "completed":
            logger.debug("[智能调度] 当前周期任务已全部完成，等待定时任务触发")  # 【V10.4修复】降为DEBUG
            return
        
        catchup_tasks = self.orchestrator.get_catchup_candidates()
        
        current_task = workflow_state.get("current_task")
        if current_task:
            task_status = workflow_state.get("tasks", {}).get(current_task, {}).get("status")
            if task_status == "in_progress":
                logger.debug(f"[智能调度] 有任务正在执行: {current_task}，暂时不执行补任务")  # 【V10.4修复】降为DEBUG
                return
        
        if not catchup_tasks:
            logger.debug("[智能调度] 所有任务已完成，等待定时任务触发")  # 【V10.4修复】降为DEBUG
            return
        
        logger.info(f"[智能调度] 检测到 {len(catchup_tasks)} 个任务需要补执行: {catchup_tasks}")
        
        cutoff_datetime = datetime.combine(now.date() + timedelta(days=1), send_report_time)
        self._execute_catchup_tasks(catchup_tasks, cutoff_datetime)
    
    def _calculate_task_durations(self) -> Dict[str, float]:
        """计算任务链总耗时（分钟）- 支持压缩模式"""
        base_durations = {
            'data_fetch': 5,
            'evaluation': 15,
            'optimization': 20,
            'training': 60,
            'send_report': 5,
        }

        now = datetime.now()
        cutoff_time = datetime.strptime('21:00', '%H:%M').time()
        send_report_time = cutoff_time
        cutoff_datetime = datetime.combine(now.date(), cutoff_time)
        if now.time() >= cutoff_time:
            cutoff_datetime += timedelta(days=1)
        available_minutes = (cutoff_datetime - now).total_seconds() / 60

        if available_minutes <= 0:
            return {'send_report': 5}

        full_time_needed = sum(base_durations.values())

        if available_minutes >= full_time_needed * 1.2:
            return base_durations
        elif available_minutes >= full_time_needed:
            scale = available_minutes / full_time_needed
            return {k: v * scale for k, v in base_durations.items()}
        else:
            critical = {
                'evaluation': 10,
                'training': 30,
                'send_report': 5,
            }
            return critical
    
    def _calculate_minimum_task_set(self, task_durations: Dict[str, float], available_minutes: float) -> List[str]:
        """计算最小可行任务集，确保能在可用时间内完成"""
        # 按优先级排序（越靠前越重要）
        priority_order = ['evaluation', 'training', 'send_report']
        
        cumulative_time = 0
        selected_tasks = []
        
        for task in priority_order:
            if task in task_durations:
                task_time = task_durations[task]
                if cumulative_time + task_time <= available_minutes * 0.9:  # 留10%缓冲
                    selected_tasks.append(task)
                    cumulative_time += task_time
        
        if selected_tasks and cumulative_time <= available_minutes * 0.9:
            return selected_tasks
        return []
    
    def _execute_catchup_tasks(self, catchup_tasks: List[str], cutoff_datetime):
        """执行补执行任务，带时间检查（使用完整 datetime 比较避免时间回绕）"""
        for task_name in catchup_tasks:
            # 再次检查时间，确保在执行过程中不会超过截止时间
            now = datetime.now()
            if now >= cutoff_datetime:
                logger.info("[保证模式] 已过截止时间，停止补执行，等待日循环")
                break

            # 【关键修复】检查任务的预定执行时间是否已到（从配置文件动态加载，与setup_schedule一致）
            # orchestrator.should_catchup_task() 已包含此检查，
            # 此处增加双重保护，防止直接调用时绕过检查
            if self.orchestrator and not self.orchestrator._is_task_scheduled_time_reached(task_name):
                scheduled_t = self.orchestrator._task_scheduled_times.get(task_name)
                logger.info(f"[保证模式] 任务 {task_name} 预定时间 {scheduled_t} 未到，跳过补执行（将按日循环日程在预定时间由schedule定时器触发）")
                continue

            self.orchestrator.mark_task_catchup_started(task_name)
            logger.info(f"[保证模式] 开始补执行任务: {task_name}")
            self.run_task_manually(task_name)
    
    def _dynamic_task_adjustment(self):
        """动态任务调整 - 根据当前时间和策略智能调度"""
        if not self.time_scheduler:
            return
        
        try:
            base_schedule = {
                'data_fetch': self.config.get('data_fetch_time', '22:15'),
                'evaluation': self.config.get('evaluation_time', '22:15'),
                'optimization': self.config.get('optimization_start', '22:45'),
                'training': self.config.get('training_start', '00:30'),
                'incremental_training': self.config.get('incremental_training_morning', '08:00'),
                'first_prediction_verification': self.config.get('first_prediction_verification', '10:00'),
                'second_prediction_verification': self.config.get('second_prediction_verification', '13:00'),  # 【佐证链修复】
                'third_prediction_verification': self.config.get('third_prediction_verification', '15:00'),    # 【佐证链修复】
                'deep_strategy_optimization': self.config.get('deep_strategy_optimization', '16:00'),
                'prediction_preview': self.config.get('prediction_preview', '17:00'),
                'final_prediction': self.config.get('final_prediction_time', '18:00'),
                'final_prediction_verification': self.config.get('final_prediction_verification_time', '19:00'),
                'pre_sale_prediction': self.config.get('pre_sale_prediction_time', '20:00'),
                'send_report': self.config.get('email_send_time', '20:15')
            }
            
            # 获取动态调度信息
            dynamic_schedule = self.time_scheduler.get_dynamic_schedule(base_schedule)
            
            # 检查关键任务链是否能完成
            critical_chain = ['evaluation', 'optimization', 'training']
            can_complete = self.time_scheduler.ensure_task_chain_completion(critical_chain, base_schedule)
            
            if not can_complete:
                logger.warning("[智能调度] 关键任务链无法在开奖前完成，尝试调整...")
                self._adjust_schedule_for_completion(base_schedule, dynamic_schedule)
            else:
                logger.info("[智能调度] 关键任务链可以完整执行")
                
        except Exception as e:
            logger.error(f"[智能调度] 动态任务调整失败: {e}")
    
    def _adjust_schedule_for_completion(self, base_schedule: Dict[str, str], dynamic_schedule: Dict[str, Dict]):
        """调整调度以确保任务链完整完成"""
        if not self.time_scheduler:
            return
        
        try:
            strategy, time_to_draw = self.time_scheduler.get_current_strategy()
            
            logger.info(f"[智能调度] 调整策略: {strategy.value}, 剩余时间: {time_to_draw}")
            
            # 计算关键任务链总时长
            critical_tasks = ['evaluation', 'optimization', 'training']
            total_critical_duration = sum(
                self.time_scheduler.task_durations.get(t, 30) for t in critical_tasks
            )
            
            # 计算邮件发送前的可用时间
            email_time_str = self.config.get('email_send_time', '20:15')
            now = datetime.now()
            email_time = now.replace(
                hour=int(email_time_str.split(':')[0]),
                minute=int(email_time_str.split(':')[1]),
                second=0, microsecond=0
            )
            if email_time < now:
                email_time += timedelta(days=1)
            
            available_time = email_time - now
            
            logger.info(f"[智能调度] 关键任务链需要: {total_critical_duration}分钟")
            logger.info(f"[智能调度] 距邮件发送还有: {available_time.total_seconds()/60:.0f}分钟")
            
            if available_time.total_seconds() / 60 >= total_critical_duration:
                logger.info("[智能调度] 时间充足，可以完成关键任务链")
                return
            
            # 时间不足，尝试延迟非关键任务
            logger.warning("[智能调度] 时间不足，延迟非关键任务...")
            
            # 延迟策略
            if strategy == TimeStrategy.NORMAL:
                # 正常模式：延迟增量训练和验证任务
                delay_tasks = ['incremental_training', 'first_prediction_verification', 
                             'deep_strategy_optimization', 'prediction_preview']
                for task in delay_tasks:
                    if task in dynamic_schedule:
                        dynamic_schedule[task]['status'] = 'delayed'
                        dynamic_schedule[task]['delay_reason'] = '关键任务链优先'
                        logger.info(f"[智能调度] 任务 {task} 已延迟")
            
            elif strategy == TimeStrategy.COMPRESSED:
                # 压缩模式：只保留最关键的任务
                delay_tasks = ['incremental_training', 'first_prediction_verification',
                             'prediction_preview']
                for task in delay_tasks:
                    if task in dynamic_schedule:
                        dynamic_schedule[task]['status'] = 'delayed'
                        dynamic_schedule[task]['delay_reason'] = '压缩模式，非关键任务延迟'
                        logger.info(f"[智能调度] 任务 {task} 已延迟")
            
            else:  # CRITICAL
                # 紧急模式：只执行核心任务
                keep_tasks = ['data_fetch', 'evaluation', 'optimization', 'training', 'send_report']
                for task_name, task_info in dynamic_schedule.items():
                    if task_name not in keep_tasks:
                        task_info['status'] = 'skipped'
                        task_info['skip_reason'] = '紧急模式，跳过非核心任务'
                        logger.info(f"[智能调度] 任务 {task_name} 已跳过")
                        
        except Exception as e:
            logger.error(f"[智能调度] 调整调度失败: {e}")
    
    def run(self):
        """运行调度器"""
        import os
        import hashlib
        
        current_pid = os.getpid()
        unique_id = hashlib.md5(f"{current_pid}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
        
        logger.info("\n" + "=" * 80)
        logger.info("排列五智能自动化学习分析系统 V10.3 启动")
        logger.info(f"[系统标识] PID={current_pid} SID={unique_id}")
        logger.info("后台持续学习进化模式")
        logger.info("=" * 80)
        
        self.setup_schedule()
        self.running = True
        
        if self.workflow_enabled and self.orchestrator:
            logger.info(f"智能工作流编排器已启用: {self.workflow_config_file}")
            
            # 检查并恢复未完成的任务
            self._recover_incomplete_tasks()
        
        logger.info("\n排列五智能自动化学习分析系统已启动，正在后台运行...")
        logger.info("按 Ctrl+C 停止\n")
        
        try:
            logger.info("主循环开始运行...")
            # 【V10.3优化】健康监控计数器
            health_check_counter = 0
            
            while self.running:
                try:
                    schedule.run_pending()
                    self.check_intelligent_scheduling()
                    
                    # 【V10.3优化】每10分钟检查一次系统健康状态
                    health_check_counter += 1
                    if health_check_counter >= 10:
                        health_check_counter = 0
                        health_monitor = get_health_monitor()
                        status = health_monitor.get_current_status()
                        logger.info(f"[系统健康] 健康评分: {status['health_score']}, 状态: {status['status']}")
                        
                        if status['health_score'] < 50:
                            logger.warning(f"[系统健康] 健康状态异常，建议检查")
                    
                    time.sleep(60)
                except KeyboardInterrupt:
                    logger.info("\n检测到中断信号")
                    self.running = False
                    break
                except Exception as e:
                    logger.error(f"主循环异常: {e}", exc_info=True)
                    time.sleep(5)
        except KeyboardInterrupt:
            logger.info("\n用户中断 - 系统停止")
            self.running = False
        except Exception as e:
            logger.critical(f"系统异常退出: {e}", exc_info=True)
    
    def _recover_incomplete_tasks(self):
        """检查并恢复未完成的任务 - 集成智能时间调度"""
        try:
            workflow_state = self.orchestrator.get_current_workflow_state()
            workflow_status = workflow_state.get("workflow_status")
            current_task = workflow_state.get("current_task")
            
            logger.info(f"[任务恢复] 工作流状态: {workflow_status}")
            
            # 检查智能时间调度 - 是否延迟邮件发送
            if self.time_scheduler:
                should_delay, new_email_time = self.time_scheduler.should_delay_email(recovery_delay=3)
                if should_delay and new_email_time:
                    logger.info(f"[智能调度] 检测到时间充裕，邮件发送延迟到 {new_email_time}")
                    logger.info(f"[智能调度] 这段时间将执行额外优化任务...")
                    
                    # 执行额外优化任务
                    self._execute_extra_optimization_tasks()
            
            # 检查是否有进行中的任务
            if current_task:
                task_state = workflow_state.get("tasks", {}).get(current_task, {})
                task_status = task_state.get("status")
                
                if task_status == "in_progress":
                    logger.warning(f"[任务恢复] 检测到未完成的任务: {current_task}")
                    
                    # 将任务状态重置为PENDING，但不立即执行，避免阻塞主循环
                    # 让定时调度器在合适的时间执行任务
                    self.orchestrator.state["tasks"][current_task]["status"] = "pending"
                    self.orchestrator._save_state()
                    
                    logger.info(f"[任务恢复] 任务已重置为待执行状态，将由定时调度器执行")
                    logger.info(f"[任务恢复] 这样可以避免阻塞其他定时任务的执行")
            
            # 检查是否有RUNNING状态的工作流但没有当前任务
            if workflow_status == "running" and not current_task:
                logger.info("[任务恢复] 检测到未完成的工作流")
                logger.info("[任务恢复] 让定时调度器在合适的时间执行任务，避免阻塞主循环")
            
            # 检查是否有错过的任务（无论工作流状态如何）
            if hasattr(self, 'workflow_config'):
                intelligent_config = self.workflow_config.get('intelligent_scheduling', {})
                if intelligent_config.get('missed_task_catchup_enabled', True):
                    # 检测错过的任务
                    missed_tasks = self.orchestrator.detect_missed_tasks(datetime.now())
                    if missed_tasks:
                        logger.warning(f"[任务恢复] 检测到错过的任务: {missed_tasks}")
                        logger.info("[任务恢复] 让定时调度器在合适的时间执行任务，避免阻塞主循环")
            
            logger.info("[任务恢复] 无未完成任务需要恢复")
            
        except Exception as e:
            logger.error(f"[任务恢复] 检查失败: {e}", exc_info=True)
    
    def _execute_extra_optimization_tasks(self):
        """执行额外优化任务（时间充裕时）"""
        if not self.time_scheduler:
            return
        
        try:
            strategy, time_to_draw = self.time_scheduler.get_current_strategy()
            logger.info(f"[智能调度] 开始执行额外优化任务，策略: {strategy.value}")
            
            # 获取可执行的额外任务
            extra_tasks = []
            if self.time_scheduler.should_execute_extra_task("extra_training"):
                extra_tasks.append("extra_training")
            
            if self.time_scheduler.should_execute_extra_task("hyperparameter_tune"):
                extra_tasks.append("hyperparameter_tune")
            
            if self.time_scheduler.should_execute_extra_task("ensemble_refine"):
                extra_tasks.append("ensemble_refine")
            
            logger.info(f"[智能调度] 将执行 {len(extra_tasks)} 个额外优化任务")
            
            # 执行额外任务（这里是占位符，实际需要实现具体逻辑）
            for task_name in extra_tasks:
                logger.info(f"[智能调度] 执行额外优化任务: {task_name}")
                # TODO: 实现具体的额外优化任务逻辑
                time.sleep(1)  # 模拟执行时间
            
            logger.info(f"[智能调度] 额外优化任务执行完成")
            
        except Exception as e:
            logger.error(f"[智能调度] 执行额外优化任务失败: {e}", exc_info=True)
    
    def get_task_monitoring_data(self) -> Dict:
        """获取任务监控面板数据"""
        monitoring_data = {
            'current_status': self.current_status,
            'config': self.config,
            'retry_counts': self.retry_manager.retry_counts,
            'task_history': self.history_manager.get_task_history(limit=20),
            'workflow_enabled': self.workflow_enabled
        }
        
        if self.workflow_enabled and self.orchestrator:
            monitoring_data['workflow_state'] = self.orchestrator.get_current_workflow_state()
        
        return monitoring_data
    
    def run_task_manually(self, task_name: str) -> bool:
        """手动运行指定任务"""
        logger.info(f"手动运行任务: {task_name}")

        # 【修复BUG-06】直接使用 self.task_map（由 _build_task_map 统一维护），
        # 消除与 setup_schedule 之间的重复定义问题。
        if task_name not in self.task_map:
            logger.error(f"未知任务: {task_name}")
            logger.info(f"可用任务: {list(self.task_map.keys())}")
            return False
        
        task_name_display, task_fn = self.task_map[task_name]
        logger.info(f"[单任务模式] 执行: {task_name_display}")
        
        # 先标记任务为执行中
        self.orchestrator.start_task(task_name)
        
        try:
            result = self.execute_with_retry(task_fn, task_name)
            is_success = result is True or (isinstance(result, tuple) and result is not None)
            
            if not is_success:
                logger.error(f"[单任务模式] {task_name_display} 执行失败")
                self.orchestrator.fail_task(task_name, "任务执行失败")
                return False
            else:
                logger.info(f"[单任务模式] {task_name_display} 执行成功")
                self.orchestrator.complete_task(task_name, result)
                return True
        except Exception as e:
            logger.error(f"[单任务模式] {task_name_display} 异常: {str(e)}", exc_info=True)
            self.orchestrator.fail_task(task_name, str(e))
            return False


def create_windows_task():
    """创建Windows计划任务"""
    script_path = Path(__file__).absolute()
    python_path = sys.executable
    
    startup_script = Path("start_scheduler_v8.bat")
    with open(startup_script, 'w', encoding='utf-8') as f:
        f.write(f'@echo off\n')
        f.write(f'cd /d "{script_path.parent}"\n')
        f.write(f'"{python_path}" "{script_path}"\n')
    
    logger.info(f"✓ 启动脚本已创建: {startup_script}")
    return startup_script


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='智能自动化分析系统V8.0')
    parser.add_argument('--run-once', action='store_true', help='立即运行一次完整流程')
    parser.add_argument('--setup-task', action='store_true', help='创建Windows计划任务')
    parser.add_argument('--status', action='store_true', help='查看当前状态')
    parser.add_argument('--monitor', action='store_true', help='查看任务监控面板')
    parser.add_argument('--task', type=str,
                        choices=['fetch', 'evaluate', 'optimize', 'train', 'send_report'],
                        help='单独执行某个任务')
    parser.add_argument('--manual-task', type=str,
                        help='手动运行指定任务')
    
    args = parser.parse_args()
    
    scheduler = AutoSchedulerV8()
    
    if args.run_once:
        scheduler.run_full_pipeline()
    elif args.setup_task:
        create_windows_task()
    elif args.status:
        print(f"当前状态: {scheduler.current_status}")
    elif args.monitor:
        monitoring_data = scheduler.get_task_monitoring_data()
        print(json.dumps(monitoring_data, indent=2, ensure_ascii=False, default=str))
    elif args.task:
        task_map = {
            'fetch': ('任务1: 数据获取', scheduler.task_fetch_data),
            'evaluate': ('任务2: 评估分析', scheduler.task_evaluate),
            'optimize': ('任务3: 策略优化', scheduler.task_optimize),
            'train': ('任务4: 深度训练', scheduler.task_train),
            'send_report': ('任务5: 发送报告', scheduler.task_send_report),
        }
        task_name, task_fn = task_map[args.task]
        logger.info(f"[单任务模式] 执行: {task_name}")
        try:
            result = scheduler.execute_with_retry(task_fn, args.task)
            is_success = result is True or (isinstance(result, tuple) and result is not None)
            if not is_success:
                logger.error(f"[单任务模式] {task_name} 执行失败")
                sys.exit(1)
            else:
                logger.info(f"[单任务模式] {task_name} 执行成功")
                sys.exit(0)
        except Exception as e:
            logger.error(f"[单任务模式] {task_name} 异常: {str(e)}", exc_info=True)
            sys.exit(1)
    elif args.manual_task:
        success = scheduler.run_task_manually(args.manual_task)
        if success:
            logger.info(f"手动运行任务 {args.manual_task} 成功")
        else:
            logger.error(f"手动运行任务 {args.manual_task} 失败")
            sys.exit(1)
    else:
        scheduler.run()
