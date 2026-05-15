"""
对齐目标设定 - 定义和追踪多智能体系统的对齐目标
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from enum import Enum, auto
import uuid
import logging
import asyncio

logger = logging.getLogger(__name__)


class GoalStatus(Enum):
    """目标状态"""
    PENDING = auto()
    ACTIVE = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class GoalPriority(Enum):
    """目标优先级"""
    LOW = 1
    MEDIUM = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class Milestone:
    """目标里程碑"""
    name: str
    description: str
    milestone_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_date: Optional[datetime] = None
    completion_criteria: Dict[str, Any] = field(default_factory=dict)
    completed_at: Optional[datetime] = None
    is_completed: bool = False

    def check_completion(self, progress: Dict[str, Any]) -> bool:
        """检查是否完成"""
        for key, expected in self.completion_criteria.items():
            if key not in progress or progress[key] < expected:
                return False
        return True

    def complete(self) -> None:
        """标记完成"""
        self.is_completed = True
        self.completed_at = datetime.now()


@dataclass
class AlignmentGoal:
    """对齐目标"""
    name: str
    description: str
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: GoalStatus = GoalStatus.PENDING
    priority: GoalPriority = GoalPriority.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    target_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    milestones: List[Milestone] = field(default_factory=list)
    progress: Dict[str, Any] = field(default_factory=dict)
    success_metrics: Dict[str, float] = field(default_factory=dict)
    involved_agents: Set[str] = field(default_factory=set)
    parent_goal_id: Optional[str] = None
    sub_goals: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_progress_percentage(self) -> float:
        """获取进度百分比"""
        if not self.milestones:
            return 0.0
        completed = sum(1 for m in self.milestones if m.is_completed)
        return (completed / len(self.milestones)) * 100

    def add_milestone(self, milestone: Milestone) -> None:
        """添加里程碑"""
        self.milestones.append(milestone)
        self.updated_at = datetime.now()

    def update_progress(self, key: str, value: Any) -> None:
        """更新进度"""
        self.progress[key] = value
        self.updated_at = datetime.now()

        for milestone in self.milestones:
            if not milestone.is_completed and milestone.check_completion(self.progress):
                milestone.complete()
                logger.info(f"里程碑完成: {milestone.name}")

    def is_complete(self) -> bool:
        """检查目标是否完成"""
        return all(m.is_completed for m in self.milestones) if self.milestones else False

    def complete(self, success: bool = True) -> None:
        """标记目标完成"""
        self.status = GoalStatus.COMPLETED if success else GoalStatus.FAILED
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'goal_id': self.goal_id,
            'name': self.name,
            'description': self.description,
            'status': self.status.name,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'milestones': [{
                'milestone_id': m.milestone_id,
                'name': m.name,
                'description': m.description,
                'target_date': m.target_date.isoformat() if m.target_date else None,
                'completion_criteria': m.completion_criteria,
                'completed_at': m.completed_at.isoformat() if m.completed_at else None,
                'is_completed': m.is_completed
            } for m in self.milestones],
            'progress': self.progress,
            'success_metrics': self.success_metrics,
            'involved_agents': list(self.involved_agents),
            'parent_goal_id': self.parent_goal_id,
            'sub_goals': self.sub_goals,
            'metadata': self.metadata
        }


class GoalTracker:
    """目标追踪器"""

    def __init__(self):
        self.goals: Dict[str, AlignmentGoal] = {}
        self._lock = asyncio.Lock()

    async def create_goal(self, name: str, description: str,
                          priority: GoalPriority = GoalPriority.MEDIUM,
                          target_date: Optional[datetime] = None,
                          milestones: Optional[List[Milestone]] = None,
                          involved_agents: Optional[Set[str]] = None,
                          parent_goal_id: Optional[str] = None) -> str:
        """创建目标"""
        async with self._lock:
            goal = AlignmentGoal(
                name=name,
                description=description,
                priority=priority,
                target_date=target_date,
                milestones=milestones or [],
                involved_agents=involved_agents or set(),
                parent_goal_id=parent_goal_id,
                status=GoalStatus.ACTIVE
            )
            self.goals[goal.goal_id] = goal

            if parent_goal_id and parent_goal_id in self.goals:
                self.goals[parent_goal_id].sub_goals.append(goal.goal_id)

            logger.info(f"目标已创建: {goal.goal_id} - {name}")
            return goal.goal_id

    async def get_goal(self, goal_id: str) -> Optional[AlignmentGoal]:
        """获取目标"""
        async with self._lock:
            return self.goals.get(goal_id)

    async def update_goal_progress(self, goal_id: str, key: str, value: Any) -> bool:
        """更新目标进度"""
        async with self._lock:
            goal = self.goals.get(goal_id)
            if not goal:
                return False
            goal.update_progress(key, value)
            if goal.is_complete() and goal.status == GoalStatus.ACTIVE:
                goal.complete()
                logger.info(f"目标已完成: {goal_id}")
            return True

    async def complete_goal(self, goal_id: str, success: bool = True) -> bool:
        """完成目标"""
        async with self._lock:
            goal = self.goals.get(goal_id)
            if not goal:
                return False
            goal.complete(success)
            logger.info(f"目标状态已更新: {goal_id} -> {'成功' if success else '失败'}")
            return True

    async def get_goals_by_status(self, status: GoalStatus) -> List[AlignmentGoal]:
        """按状态获取目标"""
        async with self._lock:
            return [goal for goal in self.goals.values() if goal.status == status]

    async def get_goals_by_agent(self, agent_id: str) -> List[AlignmentGoal]:
        """按智能体获取目标"""
        async with self._lock:
            return [goal for goal in self.goals.values() if agent_id in goal.involved_agents]

    async def cancel_goal(self, goal_id: str) -> bool:
        """取消目标"""
        async with self._lock:
            goal = self.goals.get(goal_id)
            if not goal:
                return False
            goal.status = GoalStatus.CANCELLED
            goal.updated_at = datetime.now()
            logger.info(f"目标已取消: {goal_id}")
            return True


class GoalEvaluator:
    """目标达成评估器"""

    def __init__(self):
        self.evaluation_history: List[Dict[str, Any]] = []

    def evaluate_goal(self, goal: AlignmentGoal) -> Dict[str, Any]:
        """评估目标"""
        progress_pct = goal.get_progress_percentage()
        time_elapsed = (datetime.now() - goal.created_at).total_seconds()
        time_remaining = None
        if goal.target_date:
            time_remaining = (goal.target_date - datetime.now()).total_seconds()

        evaluation = {
            'goal_id': goal.goal_id,
            'name': goal.name,
            'status': goal.status.name,
            'progress_percentage': progress_pct,
            'time_elapsed_seconds': time_elapsed,
            'time_remaining_seconds': time_remaining,
            'milestones_total': len(goal.milestones),
            'milestones_completed': sum(1 for m in goal.milestones if m.is_completed),
            'success_metrics': goal.success_metrics,
            'evaluation_time': datetime.now().isoformat(),
            'is_on_track': self._is_on_track(goal, progress_pct, time_elapsed)
        }

        self.evaluation_history.append(evaluation)
        return evaluation

    def _is_on_track(self, goal: AlignmentGoal, progress_pct: float, 
                     time_elapsed: float) -> bool:
        """判断是否在正轨上"""
        if goal.status == GoalStatus.COMPLETED:
            return True

        if not goal.target_date:
            return progress_pct >= 0

        total_time = (goal.target_date - goal.created_at).total_seconds()
        if total_time <= 0:
            return False

        expected_progress = (time_elapsed / total_time) * 100
        return progress_pct >= (expected_progress * 0.8)

    def get_agent_performance(self, agent_id: str, goals: List[AlignmentGoal]) -> Dict[str, Any]:
        """获取智能体表现"""
        agent_goals = [g for g in goals if agent_id in g.involved_agents]
        if not agent_goals:
            return {'agent_id': agent_id, 'total_goals': 0}

        completed = sum(1 for g in agent_goals if g.status == GoalStatus.COMPLETED)
        avg_progress = sum(g.get_progress_percentage() for g in agent_goals) / len(agent_goals)

        return {
            'agent_id': agent_id,
            'total_goals': len(agent_goals),
            'completed_goals': completed,
            'completion_rate': completed / len(agent_goals) if agent_goals else 0,
            'avg_progress_percentage': avg_progress
        }
