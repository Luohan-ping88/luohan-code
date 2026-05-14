#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
难度评估器模块
实现任务难度评估、样本难度评估和难度分类
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path
import json
from datetime import datetime


class DifficultyLevel(Enum):
    """难度级别枚举"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class TaskDifficulty:
    """任务难度数据结构"""

    task_id: str
    difficulty_score: float
    level: DifficultyLevel
    factors: Dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class SampleDifficulty:
    """样本难度数据结构"""

    sample_id: str
    difficulty_score: float
    level: DifficultyLevel
    task_id: Optional[str] = None
    error_rate: float = 0.0
    avg_time_spent: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class DifficultyEvaluator:
    """难度评估器"""

    def __init__(self, storage_path: Optional[Path] = None):
        """初始化难度评估器

        Args:
            storage_path: 持久化存储路径
        """
        self.storage_path = storage_path or Path(
            "models/curriculum_difficulty.json"
        )
        self.task_difficulties: Dict[str, TaskDifficulty] = {}
        self.sample_difficulties: Dict[str, SampleDifficulty] = {}
        self._load()

    def evaluate_task_difficulty(
        self,
        task_id: str,
        factors: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
    ) -> TaskDifficulty:
        """评估任务难度

        Args:
            task_id: 任务ID
            factors: 难度因子字典
            weights: 权重字典，如果为None则使用均匀权重

        Returns:
            任务难度对象
        """
        if weights is None:
            weights = {k: 1.0 / len(factors) for k in factors.keys()}

        total_score = 0.0
        total_weight = 0.0

        for factor, value in factors.items():
            weight = weights.get(factor, 0.0)
            total_score += value * weight
            total_weight += weight

        if total_weight > 0:
            difficulty_score = total_score / total_weight
        else:
            difficulty_score = 0.5

        level = self._classify_difficulty(difficulty_score)

        task_diff = TaskDifficulty(
            task_id=task_id,
            difficulty_score=difficulty_score,
            level=level,
            factors=factors.copy(),
            updated_at=datetime.now(),
        )

        if task_id in self.task_difficulties:
            task_diff.created_at = self.task_difficulties[task_id].created_at

        self.task_difficulties[task_id] = task_diff
        self._save()

        return task_diff

    def evaluate_sample_difficulty(
        self,
        sample_id: str,
        error_rate: float,
        avg_time_spent: float,
        task_id: Optional[str] = None,
        time_weight: float = 0.5,
    ) -> SampleDifficulty:
        """评估样本难度

        Args:
            sample_id: 样本ID
            error_rate: 错误率 (0-1)
            avg_time_spent: 平均花费时间（秒）
            task_id: 关联的任务ID
            time_weight: 时间权重 (0-1)

        Returns:
            样本难度对象
        """
        error_weight = 1.0 - time_weight
        normalized_time = min(avg_time_spent / 300.0, 1.0)

        difficulty_score = (
            error_rate * error_weight + normalized_time * time_weight
        )
        level = self._classify_difficulty(difficulty_score)

        sample_diff = SampleDifficulty(
            sample_id=sample_id,
            difficulty_score=difficulty_score,
            level=level,
            task_id=task_id,
            error_rate=error_rate,
            avg_time_spent=avg_time_spent,
            updated_at=datetime.now(),
        )

        if sample_id in self.sample_difficulties:
            sample_diff.created_at = self.sample_difficulties[
                sample_id
            ].created_at

        self.sample_difficulties[sample_id] = sample_diff
        self._save()

        return sample_diff

    def _classify_difficulty(self, score: float) -> DifficultyLevel:
        """根据分数分类难度级别

        Args:
            score: 难度分数 (0-1)

        Returns:
            难度级别
        """
        if score < 0.4:
            return DifficultyLevel.EASY
        elif score < 0.7:
            return DifficultyLevel.MEDIUM
        else:
            return DifficultyLevel.HARD

    def get_task_difficulty(self, task_id: str) -> Optional[TaskDifficulty]:
        """获取任务难度

        Args:
            task_id: 任务ID

        Returns:
            任务难度对象，如果不存在则返回None
        """
        return self.task_difficulties.get(task_id)

    def get_sample_difficulty(
        self, sample_id: str
    ) -> Optional[SampleDifficulty]:
        """获取样本难度

        Args:
            sample_id: 样本ID

        Returns:
            样本难度对象，如果不存在则返回None
        """
        return self.sample_difficulties.get(sample_id)

    def get_samples_by_level(
        self, level: DifficultyLevel
    ) -> List[SampleDifficulty]:
        """获取指定难度级别的样本

        Args:
            level: 难度级别

        Returns:
            样本难度对象列表
        """
        return [
            sample
            for sample in self.sample_difficulties.values()
            if sample.level == level
        ]

    def get_tasks_by_level(
        self, level: DifficultyLevel
    ) -> List[TaskDifficulty]:
        """获取指定难度级别的任务

        Args:
            level: 难度级别

        Returns:
            任务难度对象列表
        """
        return [
            task
            for task in self.task_difficulties.values()
            if task.level == level
        ]

    def _load(self) -> None:
        """从文件加载数据"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for task_data in data.get("tasks", []):
                    task_data["level"] = DifficultyLevel(task_data["level"])
                    task_data["created_at"] = datetime.fromisoformat(
                        task_data["created_at"]
                    )
                    task_data["updated_at"] = datetime.fromisoformat(
                        task_data["updated_at"]
                    )
                    self.task_difficulties[task_data["task_id"]] = (
                        TaskDifficulty(**task_data)
                    )

                for sample_data in data.get("samples", []):
                    sample_data["level"] = DifficultyLevel(
                        sample_data["level"]
                    )
                    sample_data["created_at"] = datetime.fromisoformat(
                        sample_data["created_at"]
                    )
                    sample_data["updated_at"] = datetime.fromisoformat(
                        sample_data["updated_at"]
                    )
                    self.sample_difficulties[sample_data["sample_id"]] = (
                        SampleDifficulty(**sample_data)
                    )

            except Exception as e:
                print(f"加载难度数据失败: {e}")

    def _save(self) -> None:
        """保存数据到文件"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"tasks": [], "samples": []}

        for task in self.task_difficulties.values():
            task_dict = {
                **task.__dict__,
                "level": task.level.value,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
            }
            data["tasks"].append(task_dict)

        for sample in self.sample_difficulties.values():
            sample_dict = {
                **sample.__dict__,
                "level": sample.level.value,
                "created_at": sample.created_at.isoformat(),
                "updated_at": sample.updated_at.isoformat(),
            }
            data["samples"].append(sample_dict)

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
