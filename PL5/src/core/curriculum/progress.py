#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学习进度追踪器模块
实现学习状态记录、技能掌握程度追踪和学习曲线分析
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class SkillMastery:
    """技能掌握程度数据结构"""

    skill_id: str
    mastery_level: float
    practice_count: int = 0
    correct_count: int = 0
    last_practiced: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def accuracy(self) -> float:
        """计算准确率"""
        if self.practice_count == 0:
            return 0.0
        return self.correct_count / self.practice_count


@dataclass
class LearningRecord:
    """学习记录数据结构"""

    record_id: str
    task_id: str
    sample_id: Optional[str] = None
    skill_ids: List[str] = field(default_factory=list)
    is_correct: bool = False
    time_spent: float = 0.0
    difficulty_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, any] = field(default_factory=dict)


@dataclass
class LearningSession:
    """学习会话数据结构"""

    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    records: List[LearningRecord] = field(default_factory=list)
    total_practice: int = 0
    correct_practice: int = 0
    total_time: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def session_accuracy(self) -> float:
        """会话准确率"""
        if self.total_practice == 0:
            return 0.0
        return self.correct_practice / self.total_practice


class ProgressTracker:
    """学习进度追踪器"""

    def __init__(self, storage_path: Optional[Path] = None):
        """初始化进度追踪器

        Args:
            storage_path: 持久化存储路径
        """
        self.storage_path = storage_path or Path(
            "models/curriculum_progress.json"
        )
        self.skills: Dict[str, SkillMastery] = {}
        self.records: Dict[str, LearningRecord] = {}
        self.sessions: Dict[str, LearningSession] = {}
        self.current_session: Optional[LearningSession] = None
        self._load()

    def start_session(
        self, session_id: Optional[str] = None
    ) -> LearningSession:
        """开始新的学习会话

        Args:
            session_id: 会话ID，如果为None则自动生成

        Returns:
            学习会话对象
        """
        if session_id is None:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        session = LearningSession(
            session_id=session_id, start_time=datetime.now()
        )

        self.current_session = session
        self.sessions[session_id] = session
        self._save()

        return session

    def end_session(self) -> Optional[LearningSession]:
        """结束当前学习会话

        Returns:
            学习会话对象，如果没有当前会话则返回None
        """
        if self.current_session is None:
            return None

        self.current_session.end_time = datetime.now()
        self.current_session.total_time = (
            self.current_session.end_time - self.current_session.start_time
        ).total_seconds()

        session = self.current_session
        self.current_session = None
        self._save()

        return session

    def record_learning(
        self,
        task_id: str,
        skill_ids: List[str],
        is_correct: bool,
        time_spent: float,
        difficulty_score: float = 0.0,
        sample_id: Optional[str] = None,
        metadata: Optional[Dict[str, any]] = None,
    ) -> LearningRecord:
        """记录学习活动

        Args:
            task_id: 任务ID
            skill_ids: 相关技能ID列表
            is_correct: 是否正确
            time_spent: 花费时间（秒）
            difficulty_score: 难度分数
            sample_id: 样本ID
            metadata: 元数据

        Returns:
            学习记录对象
        """
        record_id = f"record_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        record = LearningRecord(
            record_id=record_id,
            task_id=task_id,
            sample_id=sample_id,
            skill_ids=skill_ids.copy(),
            is_correct=is_correct,
            time_spent=time_spent,
            difficulty_score=difficulty_score,
            metadata=metadata or {},
        )

        self.records[record_id] = record

        if self.current_session is not None:
            self.current_session.records.append(record)
            self.current_session.total_practice += 1
            if is_correct:
                self.current_session.correct_practice += 1
            self.current_session.total_time += time_spent

        for skill_id in skill_ids:
            self._update_skill_mastery(skill_id, is_correct)

        self._save()

        return record

    def _update_skill_mastery(self, skill_id: str, is_correct: bool) -> None:
        """更新技能掌握程度

        Args:
            skill_id: 技能ID
            is_correct: 是否正确
        """
        if skill_id not in self.skills:
            self.skills[skill_id] = SkillMastery(
                skill_id=skill_id, mastery_level=0.0
            )

        skill = self.skills[skill_id]
        skill.practice_count += 1
        if is_correct:
            skill.correct_count += 1

        learning_rate = 0.1
        if is_correct:
            skill.mastery_level = min(
                skill.mastery_level
                + learning_rate * (1 - skill.mastery_level),
                1.0,
            )
        else:
            skill.mastery_level = max(
                skill.mastery_level - learning_rate * skill.mastery_level, 0.0
            )

        skill.last_practiced = datetime.now()
        skill.updated_at = datetime.now()

    def get_skill_mastery(self, skill_id: str) -> Optional[SkillMastery]:
        """获取技能掌握程度

        Args:
            skill_id: 技能ID

        Returns:
            技能掌握程度对象，如果不存在则返回None
        """
        return self.skills.get(skill_id)

    def get_all_skills(self) -> List[SkillMastery]:
        """获取所有技能掌握程度

        Returns:
            技能掌握程度对象列表
        """
        return list(self.skills.values())

    def get_learning_curve(
        self, skill_id: Optional[str] = None, days: int = 30
    ) -> List[Tuple[datetime, float]]:
        """获取学习曲线数据

        Args:
            skill_id: 技能ID，如果为None则获取整体学习曲线
            days: 天数

        Returns:
            学习曲线数据点列表 [(日期, 掌握程度)]
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        daily_mastery = defaultdict(list)

        for record in self.records.values():
            if record.timestamp < cutoff_date:
                continue

            if skill_id is not None and skill_id not in record.skill_ids:
                continue

            date_key = record.timestamp.date()
            daily_mastery[date_key].append(1.0 if record.is_correct else 0.0)

        curve = []
        for date in sorted(daily_mastery.keys()):
            avg_mastery = sum(daily_mastery[date]) / len(daily_mastery[date])
            curve.append(
                (datetime.combine(date, datetime.min.time()), avg_mastery)
            )

        return curve

    def get_session_history(self, limit: int = 10) -> List[LearningSession]:
        """获取会话历史

        Args:
            limit: 返回数量限制

        Returns:
            学习会话列表
        """
        sorted_sessions = sorted(
            self.sessions.values(), key=lambda s: s.start_time, reverse=True
        )
        return sorted_sessions[:limit]

    def get_overall_stats(self) -> Dict[str, any]:
        """获取总体统计数据

        Returns:
            统计数据字典
        """
        total_records = len(self.records)
        correct_records = sum(1 for r in self.records.values() if r.is_correct)
        total_time = sum(r.time_spent for r in self.records.values())

        skill_stats = {
            "total_skills": len(self.skills),
            "mastered_skills": sum(
                1 for s in self.skills.values() if s.mastery_level >= 0.8
            ),
            "average_mastery": (
                sum(s.mastery_level for s in self.skills.values())
                / len(self.skills)
                if self.skills
                else 0.0
            ),
        }

        return {
            "total_records": total_records,
            "accuracy": (
                correct_records / total_records if total_records > 0 else 0.0
            ),
            "total_time": total_time,
            "total_sessions": len(self.sessions),
            "skills": skill_stats,
        }

    def _load(self) -> None:
        """从文件加载数据"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for skill_data in data.get("skills", []):
                    if skill_data.get("last_practiced"):
                        skill_data["last_practiced"] = datetime.fromisoformat(
                            skill_data["last_practiced"]
                        )
                    skill_data["created_at"] = datetime.fromisoformat(
                        skill_data["created_at"]
                    )
                    skill_data["updated_at"] = datetime.fromisoformat(
                        skill_data["updated_at"]
                    )
                    self.skills[skill_data["skill_id"]] = SkillMastery(
                        **skill_data
                    )

                for record_data in data.get("records", []):
                    record_data["timestamp"] = datetime.fromisoformat(
                        record_data["timestamp"]
                    )
                    self.records[record_data["record_id"]] = LearningRecord(
                        **record_data
                    )

                for session_data in data.get("sessions", []):
                    session_data["start_time"] = datetime.fromisoformat(
                        session_data["start_time"]
                    )
                    if session_data.get("end_time"):
                        session_data["end_time"] = datetime.fromisoformat(
                            session_data["end_time"]
                        )
                    session_data["created_at"] = datetime.fromisoformat(
                        session_data["created_at"]
                    )
                    session_records = session_data.pop("records", [])
                    session = LearningSession(**session_data)
                    session.records = [
                        self.records[r["record_id"]]
                        for r in session_records
                        if r["record_id"] in self.records
                    ]
                    self.sessions[session_data["session_id"]] = session

            except Exception as e:
                print(f"加载进度数据失败: {e}")

    def _save(self) -> None:
        """保存数据到文件"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"skills": [], "records": [], "sessions": []}

        for skill in self.skills.values():
            skill_dict = {
                **skill.__dict__,
                "last_practiced": (
                    skill.last_practiced.isoformat()
                    if skill.last_practiced
                    else None
                ),
                "created_at": skill.created_at.isoformat(),
                "updated_at": skill.updated_at.isoformat(),
            }
            data["skills"].append(skill_dict)

        for record in self.records.values():
            record_dict = {
                **record.__dict__,
                "timestamp": record.timestamp.isoformat(),
            }
            data["records"].append(record_dict)

        for session in self.sessions.values():
            session_dict = {
                **session.__dict__,
                "start_time": session.start_time.isoformat(),
                "end_time": (
                    session.end_time.isoformat() if session.end_time else None
                ),
                "created_at": session.created_at.isoformat(),
                "records": [
                    {"record_id": r.record_id} for r in session.records
                ],
            }
            data["sessions"].append(session_dict)

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
