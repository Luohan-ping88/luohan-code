#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课程学习自适应机制模块
实现难度评估、进度追踪、自适应调整和能力测试
"""

from .difficulty import (
    DifficultyLevel,
    TaskDifficulty,
    SampleDifficulty,
    DifficultyEvaluator,
)

from .progress import (
    SkillMastery,
    LearningRecord,
    LearningSession,
    ProgressTracker,
)

from .adapter import (
    AdjustmentAction,
    AdjustmentRecommendation,
    LearningPath,
    CurriculumAdapter,
)

from .testing import (
    TestStatus,
    CertificationLevel,
    TestQuestion,
    TestResult,
    Test,
    Certification,
    TestingManager,
)

__all__ = [
    "DifficultyLevel",
    "TaskDifficulty",
    "SampleDifficulty",
    "DifficultyEvaluator",
    "SkillMastery",
    "LearningRecord",
    "LearningSession",
    "ProgressTracker",
    "AdjustmentAction",
    "AdjustmentRecommendation",
    "LearningPath",
    "CurriculumAdapter",
    "TestStatus",
    "CertificationLevel",
    "TestQuestion",
    "TestResult",
    "Test",
    "Certification",
    "TestingManager",
]
