"""
智能编排管理器 - 增强版
功能：只锚点训练开始和结束时间，其他节点智能实时编排
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import sys

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.utils.logger import get_logger
from src.core.workflow.intelligent_time_scheduler import IntelligentTimeScheduler

logger = get_logger('orchestration')


class OrchestrationTask:
    """智能编排任务"""
    
    def __init__(self, name: str, handler: Callable, priority: int = 1, 
                 dependencies: List[str] = None, max_retries: int = 3):
        self.name = name
        self.handler = handler
        self.priority = priority
        self.dependencies = dependencies or []
        self.max_retries = max_retries
        self.retries = 0
        self.status = "pending"  # pending, running, completed, failed
        self.start_time = None
        self.end_time = None
        self.error = None
        self.result = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "priority": self.priority,
            "status": self.status,
            "retries": self.retries,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error": str(self.error) if self.error else None
        }


class IntelligentOrchestrationManager:
    """智能编排管理器 - 锚点时间 + 实时智能编排"""
    
    # 锚点时间配置
    ANCHOR_START_TIME = "21:55"  # 训练开始
    ANCHOR_END_TIME = "21:00"    # 第二天训练结束（售前前）
    
    def __init__(self, scheduler_instance):
        self.scheduler = scheduler_instance
        self.tasks: Dict[str, OrchestrationTask] = {}
        self.lock = threading.RLock()
        self.is_running = False
        self.orchestration_thread = None
        self.last_check_time = None
        self.history: List[Dict] = []
        self.max_history = 100
        
        # 工作状态管理
        self.in_training_window = False
        self.training_window_start = None
        self.training_window_end = None
        
        logger.info("智能编排管理器已初始化")
    
    def register_task(self, name: str, handler: Callable, priority: int = 1, 
                     dependencies: List[str] = None):
        """注册一个任务到编排系统"""
        with self.lock:
            task = OrchestrationTask(name, handler, priority, dependencies)
            self.tasks[name] = task
            logger.info(f"已注册任务: {name}, 优先级: {priority}")
    
    def _is_in_training_window(self) -> bool:
        """检查是否在训练窗口期内"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        # 训练窗口是从 21:55 到次日 21:00
        start_hour, start_minute = 21, 55
        end_hour, end_minute = 21, 0
        
        current_hour, current_minute = now.hour, now.minute
        
        # 如果当前时间 >= 21:55 或 < 21:00，则在训练窗口期内
        if (current_hour > start_hour or 
            (current_hour == start_hour and current_minute >= start_minute)):
            return True
        elif current_hour < end_hour or (current_hour == end_hour and current_minute < end_minute):
            return True
        else:
            return False
    
    def _check_training_window(self):
        """检查训练窗口状态变化"""
        now = datetime.now()
        in_window = self._is_in_training_window()
        
        if in_window and not self.in_training_window:
            # 进入训练窗口
            self.in_training_window = True
            self.training_window_start = now
            
            # 计算窗口结束时间
            if now.hour >= 21:
                # 今天 21:55 开始，明天 21:00 结束
                self.training_window_end = (now + timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
            else:
                # 今天 00:00-21:00 属于昨天开始的窗口
                self.training_window_end = now.replace(hour=21, minute=0, second=0, microsecond=0)
            
            logger.info(f"进入训练窗口期: {self.training_window_start} -> {self.training_window_end}")
            
            # 立即触发任务链
            self._trigger_task_chain()
            
        elif not in_window and self.in_training_window:
            # 离开训练窗口
            self.in_training_window = False
            logger.info("离开训练窗口期，进入售前阶段")
    
    def _trigger_task_chain(self):
        """触发任务链执行"""
        logger.info("触发任务链执行")
        
        # 任务链顺序（根据依赖关系）
        task_order = [
            'pl5_detection_optimization',
            'data_fetch',
            'evaluation',
            'optimization',
            'training',
            'incremental_training',
            'first_prediction_verification',
            'second_prediction_verification',
            'third_prediction_verification',
            'deep_strategy_optimization',
            'prediction_preview',
            'final_prediction',
            'final_prediction_verification',
            'pre_sale_prediction',
            'send_report'
        ]
        
        # 执行任务链（在线程中执行，避免阻塞）
        threading.Thread(target=self._execute_task_chain, args=(task_order,), 
                       daemon=True, name="TaskChainThread").start()
    
    def _execute_task_chain(self, task_order: List[str]):
        """在后台线程中执行任务链"""
        for task_name in task_order:
            if task_name in self.tasks:
                self._execute_single_task(task_name)
            else:
                logger.warning(f"任务 {task_name} 未注册，跳过")
    
    def _execute_single_task(self, task_name: str):
        """执行单个任务"""
        task = self.tasks.get(task_name)
        if not task:
            logger.warning(f"任务 {task_name} 不存在")
            return False
        
        # 检查依赖是否已完成
        for dep in task.dependencies:
            dep_task = self.tasks.get(dep)
            if not dep_task or dep_task.status != "completed":
                logger.warning(f"任务 {task_name} 等待依赖 {dep} 完成")
                return False
        
        with self.lock:
            # 检查是否已经在运行
            if task.status == "running":
                logger.warning(f"任务 {task_name} 正在运行，跳过")
                return False
            
            task.status = "running"
            task.start_time = datetime.now()
        
        try:
            logger.info(f"开始执行任务: {task_name}")
            
            # 执行任务
            result = task.handler()
            task.result = result
            task.status = "completed"
            task.end_time = datetime.now()
            
            elapsed = (task.end_time - task.start_time).total_seconds()
            logger.info(f"任务完成: {task_name}, 耗时: {elapsed:.2f}秒")
            
            # 记录历史
            self._add_to_history(task)
            return True
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.end_time = datetime.now()
            elapsed = (task.end_time - task.start_time).total_seconds()
            logger.error(f"任务失败: {task_name}, 耗时: {elapsed:.2f}秒, 错误: {e}", exc_info=True)
            
            # 重试
            if task.retries < task.max_retries:
                task.retries += 1
                logger.info(f"任务 {task_name} 将重试 {task.retries}/{task.max_retries}")
                task.status = "pending"
                # 延迟重试
                time.sleep(2 ** task.retries)
                return self._execute_single_task(task_name)
            
            self._add_to_history(task)
            return False
    
    def _add_to_history(self, task: OrchestrationTask):
        """添加到历史记录"""
        with self.lock:
            self.history.append(task.to_dict())
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
    
    def get_task_status(self, task_name: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self.tasks.get(task_name)
        if task:
            return task.to_dict()
        return None
    
    def get_all_task_status(self) -> Dict:
        """获取所有任务状态"""
        with self.lock:
            return {name: task.to_dict() for name, task in self.tasks.items()}
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取历史记录"""
        with self.lock:
            return self.history[-limit:]
    
    def start(self):
        """启动智能编排系统"""
        if self.is_running:
            logger.warning("智能编排系统已在运行")
            return
        
        self.is_running = True
        self.orchestration_thread = threading.Thread(target=self._orchestration_loop, 
                                                    daemon=True, name="OrchestrationLoop")
        self.orchestration_thread.start()
        logger.info("智能编排系统已启动")
    
    def stop(self):
        """停止智能编排系统"""
        self.is_running = False
        if self.orchestration_thread and self.orchestration_thread.is_alive():
            self.orchestration_thread.join(timeout=5)
        logger.info("智能编排系统已停止")
    
    def _orchestration_loop(self):
        """编排主循环"""
        logger.info("编排循环已启动")
        while self.is_running:
            try:
                # 检查训练窗口
                self._check_training_window()
                
                # 智能检查和触发
                self._intelligent_check_and_trigger()
                
                # 记录检查时间
                self.last_check_time = datetime.now()
                
                # 检查间隔
                time.sleep(30)  # 每30秒检查一次
                
            except Exception as e:
                logger.error(f"编排循环异常: {e}", exc_info=True)
                time.sleep(5)
    
    def _intelligent_check_and_trigger(self):
        """智能检查并触发任务"""
        # 如果在训练窗口内，检查是否有需要重新执行的任务
        if self.in_training_window:
            # 可以在这里添加智能逻辑，例如：
            # - 检查数据是否更新
            # - 检查模型性能是否下降
            # - 智能决定是否重新训练
            pass
    
    def manual_trigger_task(self, task_name: str):
        """手动触发任务"""
        if task_name in self.tasks:
            logger.info(f"手动触发任务: {task_name}")
            threading.Thread(target=self._execute_single_task, 
                           args=(task_name,), daemon=True).start()
        else:
            logger.warning(f"任务 {task_name} 未注册")
    
    def get_orchestration_status(self) -> Dict:
        """获取编排系统状态"""
        return {
            "is_running": self.is_running,
            "in_training_window": self.in_training_window,
            "training_window_start": self.training_window_start.isoformat() if self.training_window_start else None,
            "training_window_end": self.training_window_end.isoformat() if self.training_window_end else None,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "tasks": self.get_all_task_status(),
            "history_count": len(self.history)
        }


# 单例实例
_orchestration_manager_instance = None

def get_orchestration_manager(scheduler_instance=None) -> IntelligentOrchestrationManager:
    """获取智能编排管理器单例"""
    global _orchestration_manager_instance
    if _orchestration_manager_instance is None and scheduler_instance is not None:
        _orchestration_manager_instance = IntelligentOrchestrationManager(scheduler_instance)
    return _orchestration_manager_instance
