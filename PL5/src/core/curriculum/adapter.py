#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应课程调整算法模块
实现根据进度调整难度、学习节奏控制和课程路径规划
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime

from .difficulty import DifficultyLevel, DifficultyEvaluator
from .progress import ProgressTracker, SkillMastery


class AdjustmentAction(Enum):
    """调整动作枚举"""

    INCREASE_DIFFICULTY = "increase_difficulty"
    DECREASE_DIFFICULTY = "decrease_difficulty"
    MAINTAIN_DIFFICULTY = "maintain_difficulty"
    SLOW_DOWN = "slow_down"
    SPEED_UP = "speed_up"
    REVIEW_PREVIOUS = "review_previous"
    INTRODUCE_NEW = "introduce_new"


@dataclass
class AdjustmentRecommendation:
    """调整建议数据结构"""

    action: AdjustmentAction
    target_difficulty: Optional[DifficultyLevel] = None
    confidence: float = 0.0
    reason: str = ""
    skill_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, any] = field(default_factory=dict)


@dataclass
class LearningPath:
    """学习路径数据结构"""

    path_id: str
    skill_sequence: List[str]
    difficulty_progression: List[DifficultyLevel]
    estimated_time: float = 0.0
    prerequisites: Dict[str, List[str]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class CurriculumAdapter:
    """自适应课程调整器"""

    def __init__(
        self,
        difficulty_evaluator: Optional[DifficultyEvaluator] = None,
        progress_tracker: Optional[ProgressTracker] = None,
        storage_path: Optional[Path] = None,
    ):
        """初始化课程调整器

        Args:
            difficulty_evaluator: 难度评估器
            progress_tracker: 进度追踪器
            storage_path: 持久化存储路径
        """
        self.difficulty_evaluator = (
            difficulty_evaluator or DifficultyEvaluator()
        )
        self.progress_tracker = progress_tracker or ProgressTracker()
        self.storage_path = storage_path or Path(
            "models/curriculum_adapter.json"
        )
        self.learning_paths: Dict[str, LearningPath] = {}
        self.adjustment_history: List[AdjustmentRecommendation] = []
        self._load()

    def recommend_difficulty(
        self, skill_ids: Optional[List[str]] = None
    ) -> Tuple[DifficultyLevel, AdjustmentRecommendation]:
        """推荐适合的难度级别

        Args:
            skill_ids: 技能ID列表，如果为None则使用所有技能

        Returns:
            (推荐难度级别, 调整建议)
        """
        skills = self._get_relevant_skills(skill_ids)

        if not skills:
            return DifficultyLevel.EASY, AdjustmentRecommendation(
                action=AdjustmentAction.MAINTAIN_DIFFICULTY,
                target_difficulty=DifficultyLevel.EASY,
                confidence=0.5,
                reason="没有学习记录，从简单开始",
            )

        avg_mastery = sum(s.mastery_level for s in skills) / len(skills)
        avg_accuracy = sum(s.accuracy for s in skills) / len(skills)
        total_practice = sum(s.practice_count for s in skills)

        recommendation = self._analyze_performance(
            avg_mastery, avg_accuracy, total_practice
        )

        target_level = self._get_target_difficulty(
            recommendation.action, avg_mastery
        )
        recommendation.target_difficulty = target_level

        return target_level, recommendation

    def _get_relevant_skills(
        self, skill_ids: Optional[List[str]]
    ) -> List[SkillMastery]:
        """获取相关技能

        Args:
            skill_ids: 技能ID列表

        Returns:
            技能掌握程度对象列表
        """
        all_skills = self.progress_tracker.get_all_skills()

        if skill_ids is None:
            return all_skills

        return [s for s in all_skills if s.skill_id in skill_ids]

    def _analyze_performance(
        self, avg_mastery: float, avg_accuracy: float, total_practice: int
    ) -> AdjustmentRecommendation:
        """分析学习表现并生成调整建议

        Args:
            avg_mastery: 平均掌握程度
            avg_accuracy: 平均准确率
            total_practice: 总练习次数

        Returns:
            调整建议
        """
        if (
            avg_mastery >= 0.85
            and avg_accuracy >= 0.9
            and total_practice >= 10
        ):
            return AdjustmentRecommendation(
                action=AdjustmentAction.INCREASE_DIFFICULTY,
                confidence=0.9,
                reason="表现优秀，可以提升难度",
            )
        elif (
            avg_mastery >= 0.7 and avg_accuracy >= 0.8 and total_practice >= 5
        ):
            return AdjustmentRecommendation(
                action=AdjustmentAction.MAINTAIN_DIFFICULTY,
                confidence=0.7,
                reason="表现稳定，保持当前难度",
            )
        elif avg_mastery < 0.4 or avg_accuracy < 0.5:
            return AdjustmentRecommendation(
                action=AdjustmentAction.DECREASE_DIFFICULTY,
                confidence=0.85,
                reason="表现不佳，需要降低难度",
            )
        elif avg_mastery < 0.6 and total_practice > 15:
            return AdjustmentRecommendation(
                action=AdjustmentAction.REVIEW_PREVIOUS,
                confidence=0.75,
                reason="进步缓慢，建议复习",
            )
        else:
            return AdjustmentRecommendation(
                action=AdjustmentAction.MAINTAIN_DIFFICULTY,
                confidence=0.6,
                reason="表现正常，继续当前节奏",
            )

    def _get_target_difficulty(
        self, action: AdjustmentAction, avg_mastery: float
    ) -> DifficultyLevel:
        """根据调整动作获取目标难度

        Args:
            action: 调整动作
            avg_mastery: 平均掌握程度

        Returns:
            目标难度级别
        """
        if action == AdjustmentAction.INCREASE_DIFFICULTY:
            if avg_mastery >= 0.9:
                return DifficultyLevel.HARD
            else:
                return DifficultyLevel.MEDIUM
        elif action == AdjustmentAction.DECREASE_DIFFICULTY:
            return DifficultyLevel.EASY
        else:
            if avg_mastery >= 0.7:
                return DifficultyLevel.MEDIUM
            else:
                return DifficultyLevel.EASY

    def recommend_learning_pace(self) -> Dict[str, any]:
        """推荐学习节奏

        Returns:
            学习节奏建议
        """
        stats = self.progress_tracker.get_overall_stats()
        recent_sessions = self.progress_tracker.get_session_history(limit=5)

        if not recent_sessions:
            return {
                "recommended_session_duration": 30,
                "recommended_practice_count": 10,
                "pace": "normal",
                "reason": "没有历史记录，使用默认设置",
            }

        avg_session_time = sum(s.total_time for s in recent_sessions) / len(
            recent_sessions
        )
        avg_accuracy = sum(s.session_accuracy for s in recent_sessions) / len(
            recent_sessions
        )

        if avg_accuracy > 0.9 and avg_session_time > 60:
            return {
                "recommended_session_duration": min(avg_session_time + 15, 90),
                "recommended_practice_count": 15,
                "pace": "fast",
                "reason": "表现优秀，可以加快节奏",
            }
        elif avg_accuracy < 0.6 or avg_session_time > 90:
            return {
                "recommended_session_duration": max(avg_session_time - 15, 20),
                "recommended_practice_count": 5,
                "pace": "slow",
                "reason": "需要放慢节奏，保证学习质量",
            }
        else:
            return {
                "recommended_session_duration": avg_session_time,
                "recommended_practice_count": 10,
                "pace": "normal",
                "reason": "节奏适中，保持当前状态",
            }

    def plan_learning_path(
        self,
        target_skills: List[str],
        prerequisites: Optional[Dict[str, List[str]]] = None,
    ) -> LearningPath:
        """规划学习路径

        Args:
            target_skills: 目标技能列表
            prerequisites: 先决条件字典

        Returns:
            学习路径对象
        """
        prerequisites = prerequisites or {}

        sequence = self._topological_sort(target_skills, prerequisites)

        difficulty_progression = []
        for i, skill_id in enumerate(sequence):
            skill = self.progress_tracker.get_skill_mastery(skill_id)
            if skill and skill.mastery_level > 0.5:
                difficulty_progression.append(DifficultyLevel.MEDIUM)
            elif skill and skill.mastery_level > 0.8:
                difficulty_progression.append(DifficultyLevel.HARD)
            else:
                difficulty_progression.append(DifficultyLevel.EASY)

        path_id = f"path_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        estimated_time = len(sequence) * 30

        path = LearningPath(
            path_id=path_id,
            skill_sequence=sequence,
            difficulty_progression=difficulty_progression,
            estimated_time=estimated_time,
            prerequisites=prerequisites.copy(),
        )

        self.learning_paths[path_id] = path
        self._save()

        return path

    def _topological_sort(
        self, skills: List[str], prerequisites: Dict[str, List[str]]
    ) -> List[str]:
        """拓扑排序确定学习顺序

        Args:
            skills: 技能列表
            prerequisites: 先决条件字典

        Returns:
            排序后的技能列表
        """
        visited = set()
        result = []

        def dfs(skill: str):
            if skill in visited:
                return
            visited.add(skill)

            for prereq in prerequisites.get(skill, []):
                dfs(prereq)

            result.append(skill)

        for skill in skills:
            dfs(skill)

        return result

    def record_adjustment(
        self, recommendation: AdjustmentRecommendation
    ) -> None:
        """记录调整历史

        Args:
            recommendation: 调整建议
        """
        self.adjustment_history.append(recommendation)
        self._save()

    def get_adjustment_history(
        self, limit: int = 10
    ) -> List[AdjustmentRecommendation]:
        """获取调整历史

        Args:
            limit: 返回数量限制

        Returns:
            调整建议列表
        """
        return self.adjustment_history[-limit:]

    def get_learning_path(self, path_id: str) -> Optional[LearningPath]:
        """获取学习路径

        Args:
            path_id: 路径ID

        Returns:
            学习路径对象，如果不存在则返回None
        """
        return self.learning_paths.get(path_id)

    def _load(self) -> None:
        """从文件加载数据"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for path_data in data.get("learning_paths", []):
                    path_data["difficulty_progression"] = [
                        DifficultyLevel(d)
                        for d in path_data["difficulty_progression"]
                    ]
                    path_data["created_at"] = datetime.fromisoformat(
                        path_data["created_at"]
                    )
                    self.learning_paths[path_data["path_id"]] = LearningPath(
                        **path_data
                    )

                for rec_data in data.get("adjustment_history", []):
                    rec_data["action"] = AdjustmentAction(rec_data["action"])
                    if rec_data.get("target_difficulty"):
                        rec_data["target_difficulty"] = DifficultyLevel(
                            rec_data["target_difficulty"]
                        )
                    self.adjustment_history.append(
                        AdjustmentRecommendation(**rec_data)
                    )

            except Exception as e:
                print(f"加载调整器数据失败: {e}")

    def _save(self) -> None:
        """保存数据到文件"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"learning_paths": [], "adjustment_history": []}

        for path in self.learning_paths.values():
            path_dict = {
                **path.__dict__,
                "difficulty_progression": [
                    d.value for d in path.difficulty_progression
                ],
                "created_at": path.created_at.isoformat(),
            }
            data["learning_paths"].append(path_dict)

        for rec in self.adjustment_history:
            rec_dict = {
                **rec.__dict__,
                "action": rec.action.value,
                "target_difficulty": (
                    rec.target_difficulty.value
                    if rec.target_difficulty
                    else None
                ),
            }
            data["adjustment_history"].append(rec_dict)

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
