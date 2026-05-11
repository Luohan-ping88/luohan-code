import os
import pickle
import json
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from src.core.utils import logger

# 日循环周期：22:15 → 第二天20:15
# 用于判断是否在日循环周期内
# 注意：此时间必须与配置文件中的 data_fetch_time 保持一致
DATA_FETCH_TIME = time(22, 0)  # 日循环触发时间（22:00起即视为周期开始）
SEND_REPORT_TIME = time(20, 15)  # 日循环结束时间（发送报告完成）

TASK_SCHEDULED_TIMES = {
    "data_fetch": time(22, 15),
    "evaluation": time(22, 15),
    "optimization": time(22, 45),
    "training": time(0, 30),
    "incremental_training": time(8, 0),
    "first_prediction_verification": time(10, 0),
    "second_prediction_verification": time(13, 0),
    "third_prediction_verification": time(15, 0),
    "deep_strategy_optimization": time(16, 0),
    "prediction_preview": time(17, 0),
    "final_prediction": time(18, 0),
    "final_prediction_verification": time(19, 0),
    "pre_sale_prediction": time(20, 0),
    "send_report": time(20, 15),
}


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class IntelligentWorkflowOrchestrator:
    # 配置键 → 任务名的映射（用于从配置文件动态构建任务时间表）
    _CONFIG_KEY_TO_TASK = {
        "data_fetch_time": "data_fetch",
        "evaluation_time": "evaluation",
        "optimization_start": "optimization",
        "training_start": "training",
        "incremental_training_morning": "incremental_training",
        "first_prediction_verification": "first_prediction_verification",
        "second_prediction_verification": "second_prediction_verification",
        "third_prediction_verification": "third_prediction_verification",
        "deep_strategy_optimization": "deep_strategy_optimization",
        "prediction_preview": "prediction_preview",
        "final_prediction_time": "final_prediction",
        "final_prediction_verification_time": "final_prediction_verification",
        "pre_sale_prediction_time": "pre_sale_prediction",
        "email_send_time": "send_report",
    }

    def __init__(self, state_file_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        if state_file_path is None:
            state_file_path = os.path.join("logs", "workflow_state.pkl")

        self.state_file_path = state_file_path
        self.workflow_dir = os.path.dirname(state_file_path)

        os.makedirs(self.workflow_dir, exist_ok=True)

        # 【动态时间表】从配置文件加载任务预定时间，取代硬编码常量
        # 确保与 setup_schedule() 注册的定时器时间完全一致
        self._task_scheduled_times: Dict[str, time] = self._build_scheduled_times(config)

        # 基础任务顺序（与 auto_scheduler_v8._build_task_map 的 custom_tasks 保持一致，共14步）
        self.task_order = [
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
        self.task_dependencies = {
            # 基础依赖链
            "data_fetch": [],
            "evaluation": ["data_fetch"],
            "optimization": ["evaluation"],
            "training": ["optimization"],
            # 增量训练（由 auto_scheduler_v8 注册）
            "incremental_training": ["training"],
            "extra_training": ["training"],
            # 预测佐证链
            "first_prediction_verification": ["incremental_training"],
            "second_prediction_verification": ["first_prediction_verification"],
            "third_prediction_verification": ["second_prediction_verification"],
            # 深度优化链
            "deep_strategy_optimization": ["third_prediction_verification"],
            "prediction_preview": ["deep_strategy_optimization"],
            "final_prediction": ["prediction_preview"],
            "final_prediction_verification": ["final_prediction"],
            "pre_sale_prediction": ["final_prediction_verification"],
            # 发送报告（依赖于所有预测任务）
            "send_report": ["pre_sale_prediction"],
            # 额外调优
            "hyperparameter_tune": ["training"],
            "ensemble_refine": ["training"],
            # 辅助任务（无依赖）
            "auto_learn_task": [],
            "strategy_selection": [],
            "ga_optimizer": ["evaluation"],
            "sa_optimizer": ["evaluation"],
            "full_training": [],
        }

        self._init_state()
        self._load_state()

    def _init_state(self):
        self.state = {
            "workflow_status": WorkflowStatus.IDLE.value,
            "tasks": {},
            "current_task": None,
            "start_time": None,
            "end_time": None,
            "updated_at": datetime.now().isoformat(),
            "cycle_date": self._get_current_cycle_date().isoformat(),
            "last_scheduled_time": None,
            "missed_tasks": [],
        }

        for task in self.task_order:
            self.state["tasks"][task] = {
                "status": TaskStatus.PENDING.value,
                "start_time": None,
                "end_time": None,
                "result": None,
                "error": None,
                "retry_count": 0,
                "last_executed_time": None,
                "is_missed": False,
            }

    @staticmethod
    def _build_scheduled_times(config: Optional[Dict[str, Any]]) -> Dict[str, time]:
        """从配置文件动态构建任务时间表。

        优先使用传入的 config 字典；若为 None，则尝试读取 config/scheduler_config.json。
        每个配置键（如 'data_fetch_time'）映射到任务名（如 'data_fetch'），
        确保与 setup_schedule() 注册的 schedule 定时器时间完全一致。
        """
        result = {}
        config_data = config

        # 若未传入配置，尝试从默认路径加载
        if config_data is None:
            config_path = os.path.join("config", "scheduler_config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                    logger.info(f"[WorkflowOrchestrator] 从 {config_path} 加载任务时间配置")
                except Exception as e:
                    logger.warning(f"[WorkflowOrchestrator] 加载配置文件失败: {e}")

        if config_data:
            for config_key, task_name in IntelligentWorkflowOrchestrator._CONFIG_KEY_TO_TASK.items():
                time_str = config_data.get(config_key)
                if time_str:
                    try:
                        h, m = time_str.split(":")
                        result[task_name] = time(int(h), int(m))
                    except (ValueError, AttributeError):
                        logger.warning(f"[WorkflowOrchestrator] 配置键 {config_key}={time_str} 格式错误")

        # 对未在配置中找到的任务，使用硬编码默认值作为兜底
        for task_name, default_t in TASK_SCHEDULED_TIMES.items():
            if task_name not in result:
                result[task_name] = default_t

        logger.info(f"[WorkflowOrchestrator] 任务时间表已构建: {len(result)} 个任务")
        for task, t in sorted(result.items(), key=lambda x: x[1]):
            logger.info(f"  {task}: {t}")
        return result

    def _get_current_cycle_date(self) -> datetime.date:
        now = datetime.now()
        current_time = now.time()

        if current_time >= DATA_FETCH_TIME:
            return now.date()
        elif current_time <= SEND_REPORT_TIME:
            return (now - timedelta(days=1)).date()
        else:
            return (now - timedelta(days=1)).date()

    def _load_state(self):
        json_path = self.state_file_path.replace(".pkl", ".json")
        loaded_state = None

        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    loaded_state = json.load(f)
                logger.info(f"[WorkflowOrchestrator] 从 JSON 加载工作流状态: {json_path}")
            except Exception as e:
                logger.warning(f"[WorkflowOrchestrator] 从 JSON 加载失败，尝试 PKL: {str(e)}")

        if not loaded_state and os.path.exists(self.state_file_path):
            try:
                with open(self.state_file_path, "rb") as f:
                    loaded_state = pickle.load(f)
                logger.info(f"[WorkflowOrchestrator] 从 PKL 加载工作流状态: {self.state_file_path}")
            except Exception as e:
                logger.warning(f"[WorkflowOrchestrator] 从 PKL 加载失败，使用初始状态: {str(e)}")

        if not loaded_state:
            self._init_state()
            return

        current_cycle_date = self._get_current_cycle_date()

        loaded_cycle_date_str = loaded_state.get("cycle_date")
        if loaded_cycle_date_str:
            loaded_cycle_date = datetime.fromisoformat(loaded_cycle_date_str).date()

            if loaded_cycle_date != current_cycle_date:
                logger.info(
                    f"[WorkflowOrchestrator] 检测到新的日循环周期（当前周期: {current_cycle_date}, 上次状态周期: {loaded_cycle_date}），自动重置工作流"
                )
                self._init_state()
                return
        else:
            updated_at_str = loaded_state.get("updated_at")
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str)
                updated_cycle_date = self._get_cycle_date_from_datetime(updated_at)

                if updated_cycle_date != current_cycle_date:
                    logger.info(
                        f"[WorkflowOrchestrator] 检测到新的日循环周期（当前周期: {current_cycle_date}, 上次状态周期: {updated_cycle_date}），自动重置工作流"
                    )
                    self._init_state()
                    return

        self.state = loaded_state

    def _get_cycle_date_from_datetime(self, dt: datetime) -> datetime.date:
        dt_time = dt.time()

        if dt_time >= DATA_FETCH_TIME:
            return dt.date()
        elif dt_time <= SEND_REPORT_TIME:
            return (dt - timedelta(days=1)).date()
        else:
            return (dt - timedelta(days=1)).date()

    def _get_task_scheduled_time(self, task_name: str) -> Optional[datetime]:
        """获取任务在当前日循环中的预定执行时间（datetime对象）。

        修复：严格判断预定时间是否已到，未到时间绝不返回可执行的datetime。
        """
        scheduled_time = self._task_scheduled_times.get(task_name)
        if not scheduled_time:
            return None

        now = datetime.now()
        today_scheduled = datetime.combine(now.date(), scheduled_time)

        # 严格判断：只有预定时间已过，才返回该时间（表示已过期，可以补执行）
        # 如果预定时间还未到，返回 None，禁止补执行
        if today_scheduled > now:
            return None  # 未到预定时间，不可补执行

        return today_scheduled  # 预定时间已过，可以补执行

    def _is_task_scheduled_time_reached(self, task_name: str) -> bool:
        """判断任务的预定执行时间是否已到。

        修复：严格区分「无配置」和「未到时间」两种情况。
        """
        # 先检查是否配置了预定时间
        configured_time = self._task_scheduled_times.get(task_name)
        if not configured_time:
            return True  # 无预定时间配置的任务，默认允许补执行

        scheduled_dt = self._get_task_scheduled_time(task_name)
        if scheduled_dt is None:
            return False  # 预定时间还未到，不允许补执行

        return datetime.now() >= scheduled_dt

    def _save_state(self):
        self.state["updated_at"] = datetime.now().isoformat()
        self.state["cycle_date"] = self._get_current_cycle_date().isoformat()

        # 同时保存 PKL 和 JSON（JSON 给客户打开）
        json_path = self.state_file_path.replace(".pkl", ".json")

        try:
            with open(self.state_file_path, "wb") as f:
                pickle.dump(self.state, f)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2, default=str)
            logger.debug(f"[WorkflowOrchestrator] 工作流状态已保存: {self.state_file_path} + {json_path}")
        except Exception as e:
            logger.error(f"[WorkflowOrchestrator] 保存工作流状态失败: {str(e)}")

    def get_workflow_status(self) -> str:
        return self.state["workflow_status"]

    def get_current_workflow_state(self) -> Dict[str, Any]:
        return self.state.copy()

    def get_task_status(self, task_name: str) -> Optional[str]:
        if task_name in self.state["tasks"]:
            return self.state["tasks"][task_name]["status"]
        return None

    def can_start_task(self, task_name: str) -> bool:
        if task_name not in self.task_dependencies:
            return True

        dependencies = self.task_dependencies[task_name]
        for dep in dependencies:
            if self.get_task_status(dep) != TaskStatus.COMPLETED.value:
                return False
        return True

    def get_next_pending_task(self) -> Optional[str]:
        for task in self.task_order:
            if self.get_task_status(task) == TaskStatus.PENDING.value:
                if self.can_start_task(task):
                    return task
        return None

    def start_task(self, task_name: str) -> bool:
        if task_name not in self.state["tasks"]:
            logger.error(f"[WorkflowOrchestrator] 任务不存在: {task_name}")
            return False

        if not self.can_start_task(task_name):
            logger.warning(f"[WorkflowOrchestrator] 任务依赖未满足: {task_name}")
            return False

        if self.get_workflow_status() == WorkflowStatus.IDLE.value:
            self.state["workflow_status"] = WorkflowStatus.RUNNING.value
            self.state["start_time"] = datetime.now().isoformat()

        self.state["current_task"] = task_name
        self.state["tasks"][task_name]["status"] = TaskStatus.IN_PROGRESS.value
        self.state["tasks"][task_name]["start_time"] = datetime.now().isoformat()

        logger.info(f"[WorkflowOrchestrator] 任务已启动: {task_name}")
        self._save_state()
        return True

    def complete_task(self, task_name: str, result: Any = None) -> bool:
        if task_name not in self.state["tasks"]:
            logger.error(f"[WorkflowOrchestrator] 任务不存在: {task_name}")
            return False

        current_status = self.get_task_status(task_name)
        if current_status == TaskStatus.COMPLETED.value:
            logger.debug(f"[WorkflowOrchestrator] 任务已完成，跳过重复完成: {task_name}")
            return True

        if current_status != TaskStatus.IN_PROGRESS.value:
            logger.info(f"[WorkflowOrchestrator] 任务状态为 {current_status}，强制标记完成: {task_name}")

        self.state["tasks"][task_name]["status"] = TaskStatus.COMPLETED.value
        self.state["tasks"][task_name]["end_time"] = datetime.now().isoformat()
        self.state["tasks"][task_name]["result"] = result
        self.state["tasks"][task_name]["last_executed_time"] = datetime.now().isoformat()

        self.reset_retry_count(task_name)

        logger.info(f"[WorkflowOrchestrator] 任务已完成: {task_name}")

        if self.state.get("current_task") == task_name:
            self.state["current_task"] = None

        next_task = self.get_next_pending_task()
        if next_task is None:
            all_completed = all(
                self.state["tasks"].get(t, {}).get("status") == TaskStatus.COMPLETED.value
                for t in self.task_order
                if t in self.state["tasks"]
            )
            if all_completed:
                self.state["workflow_status"] = WorkflowStatus.COMPLETED.value
                self.state["end_time"] = datetime.now().isoformat()
                logger.info("[WorkflowOrchestrator] 工作流已全部完成")

        self._save_state()
        return True

    def fail_task(self, task_name: str, error: str) -> bool:
        if task_name not in self.state["tasks"]:
            logger.error(f"[WorkflowOrchestrator] 任务不存在: {task_name}")
            return False

        if self.can_retry(task_name):
            self.increment_retry_count(task_name)
            retry_delay = self.get_retry_delay(task_name)
            self.state["tasks"][task_name]["status"] = TaskStatus.PENDING.value
            self.state["tasks"][task_name]["error"] = error
            self.state["current_task"] = None

            logger.warning(
                f"[WorkflowOrchestrator] 任务失败，将在 {retry_delay} 秒后重试: {task_name}, 错误: {error}, 当前重试次数: {self.get_retry_count(task_name)}"
            )
            self._save_state()
            return True
        else:
            self.state["tasks"][task_name]["status"] = TaskStatus.FAILED.value
            self.state["tasks"][task_name]["end_time"] = datetime.now().isoformat()
            self.state["tasks"][task_name]["error"] = error
            self.state["workflow_status"] = WorkflowStatus.FAILED.value
            self.state["end_time"] = datetime.now().isoformat()
            self.state["current_task"] = None

            logger.error(f"[WorkflowOrchestrator] 任务失败，已达最大重试次数: {task_name}, 错误: {error}")
            self._save_state()
            return False

    def reset_workflow(self):
        self._init_state()
        self._save_state()
        logger.info("[WorkflowOrchestrator] 工作流已重置")

    def get_task_result(self, task_name: str) -> Any:
        if task_name in self.state["tasks"]:
            return self.state["tasks"][task_name]["result"]
        return None

    def get_task_error(self, task_name: str) -> Optional[str]:
        if task_name in self.state["tasks"]:
            return self.state["tasks"][task_name]["error"]
        return None

    def is_in_time_window(self) -> bool:
        """判断是否在日循环周期内（22:15 → 第二天20:15）

        日循环窗口跨越午夜：属于 [22:15今天, 20:15明天] 的范围
        即：当前时间 >= 22:15 或 当前时间 <= 20:15
        """
        now = datetime.now().time()
        return now >= DATA_FETCH_TIME or now <= SEND_REPORT_TIME

    def should_execute_early(self, task_name: str) -> bool:
        if not self.is_in_time_window():
            return False

        if self.get_task_status(task_name) != TaskStatus.PENDING.value:
            return False

        if not self.can_start_task(task_name):
            return False

        current_task = self.state["current_task"]
        if current_task is None:
            return False

        current_status = self.get_task_status(current_task)
        if current_status != TaskStatus.IN_PROGRESS.value:
            return False

        return True

    def get_early_executable_tasks(self) -> List[str]:
        executable_tasks = []
        for task in self.task_order:
            if self.should_execute_early(task):
                executable_tasks.append(task)
        return executable_tasks

    def get_retry_count(self, task_name: str) -> int:
        if task_name in self.state["tasks"]:
            return self.state["tasks"][task_name]["retry_count"]
        return 0

    def increment_retry_count(self, task_name: str) -> bool:
        if task_name in self.state["tasks"]:
            self.state["tasks"][task_name]["retry_count"] += 1
            self._save_state()
            logger.info(
                f"[WorkflowOrchestrator] 任务重试次数已增加: {task_name}, 当前重试次数: {self.get_retry_count(task_name)}"
            )
            return True
        return False

    def can_retry(self, task_name: str) -> bool:
        return self.get_retry_count(task_name) < 3

    def get_retry_delay(self, task_name: str) -> int:
        retry_count = self.get_retry_count(task_name)
        if retry_count == 0:
            return 1
        elif retry_count == 1:
            return 2
        elif retry_count == 2:
            return 4
        return 4

    def reset_retry_count(self, task_name: str) -> bool:
        if task_name in self.state["tasks"]:
            self.state["tasks"][task_name]["retry_count"] = 0
            self._save_state()
            logger.info(f"[WorkflowOrchestrator] 任务重试次数已重置: {task_name}")
            return True
        return False

    def detect_missed_tasks(self, current_time: datetime) -> List[str]:
        if self.state["last_scheduled_time"] is None:
            self.state["last_scheduled_time"] = current_time.isoformat()
            self._save_state()
            return []

        last_check_time = datetime.fromisoformat(self.state["last_scheduled_time"])

        if current_time <= last_check_time:
            return []

        missed_tasks = []

        cycle_start, cycle_end = self._get_current_cycle_range(current_time)

        for task_name in self.task_order:
            task = self.state["tasks"][task_name]
            # 【V10.4修复】使用动态时间表替代硬编码常量，与配置文件保持一致
            scheduled_time = self._task_scheduled_times.get(task_name)

            if scheduled_time is None:
                continue

            # 【修复】先检查预定时间是否已到；未到时间绝不标记为错过
            if not self._is_task_scheduled_time_reached(task_name):
                continue

            last_executed = task.get("last_executed_time")

            if last_executed is None:
                task["is_missed"] = True
                missed_tasks.append(task_name)
                logger.info(f"[WorkflowOrchestrator] 检测到从未执行的任务（且已到预定时间）: {task_name}")
            else:
                last_executed_dt = datetime.fromisoformat(last_executed)
                is_in_current_cycle = cycle_start <= last_executed_dt <= cycle_end

                if not is_in_current_cycle:
                    task["is_missed"] = True
                    missed_tasks.append(task_name)
                    logger.info(
                        f"[WorkflowOrchestrator] 检测到错过当前周期执行的任务: {task_name} (上次执行: {last_executed_dt.strftime('%Y-%m-%d %H:%M:%S')}, 当前周期: {cycle_start.strftime('%Y-%m-%d %H:%M')} → {cycle_end.strftime('%Y-%m-%d %H:%M')})"
                    )

        self.state["missed_tasks"] = missed_tasks
        self.state["last_scheduled_time"] = current_time.isoformat()
        self._save_state()

        return missed_tasks

    def _get_current_cycle_range(self, current_time: datetime) -> tuple:
        """计算当前时间所属的日循环周期范围 [cycle_start, cycle_end]"""
        now_time = current_time.time()
        today = current_time.date()

        if now_time >= DATA_FETCH_TIME:
            cycle_start = datetime.combine(today, DATA_FETCH_TIME)
            cycle_end = datetime.combine(today + timedelta(days=1), SEND_REPORT_TIME)
        else:
            cycle_start = datetime.combine(today - timedelta(days=1), DATA_FETCH_TIME)
            cycle_end = datetime.combine(today, SEND_REPORT_TIME)

        return cycle_start, cycle_end

    def get_missed_tasks(self) -> List[str]:
        return self.state.get("missed_tasks", [])

    def should_catchup_task(self, task_name: str) -> bool:
        if not self.is_in_time_window():
            return False

        if task_name not in self.state["tasks"]:
            return False

        task = self.state["tasks"][task_name]
        task_status = task.get("status")

        # 检查是否需要补执行：
        # 1. 标记为错过的任务
        # 2. 状态为 pending 的任务
        if not (task.get("is_missed", False) or task_status == "pending"):
            return False

        # 【关键修复】检查任务的预定执行时间是否已到（从配置文件动态加载，与schedule定时器一致）
        # 避免在凌晨补执行预定在晚间的任务（如 06:53 补执行 20:00 的 pre_sale_prediction）
        if not self._is_task_scheduled_time_reached(task_name):
            scheduled_t = self._task_scheduled_times.get(task_name)
            logger.info(
                f"[WorkflowOrchestrator] 任务 {task_name} 预定时间 {scheduled_t} 未到，跳过补执行（将按日循环日程在预定时间由schedule定时器触发）"
            )
            return False

        if not self.can_start_task(task_name):
            return False

        current_task = self.state["current_task"]
        if current_task is not None:
            current_status = self.get_task_status(current_task)
            if current_status == TaskStatus.IN_PROGRESS.value:
                return False

        return True

    def get_catchup_candidates(self) -> List[str]:
        candidates = []
        for task_name in self.task_order:
            if self.should_catchup_task(task_name):
                candidates.append(task_name)
        return candidates

    def mark_task_catchup_started(self, task_name: str) -> bool:
        if task_name in self.state["tasks"]:
            self.state["tasks"][task_name]["is_missed"] = False
            self.state["tasks"][task_name]["last_executed_time"] = datetime.now().isoformat()
            if task_name in self.state["missed_tasks"]:
                self.state["missed_tasks"].remove(task_name)
            self._save_state()
            logger.info(f"[WorkflowOrchestrator] 补执行任务已启动: {task_name}")
            return True
        return False

    def clear_missed_tasks(self):
        self.state["missed_tasks"] = []
        for task_name in self.task_order:
            self.state["tasks"][task_name]["is_missed"] = False
        self._save_state()
        logger.info("[WorkflowOrchestrator] 已清除所有错过任务标记")
