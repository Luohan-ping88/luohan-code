#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段性能力测试模块
实现测试生成、测试评估和能力认证
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime
import random
from collections import defaultdict

from .difficulty import DifficultyLevel, DifficultyEvaluator
from .progress import ProgressTracker, SkillMastery


class TestStatus(Enum):
    """测试状态枚举"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CertificationLevel(Enum):
    """认证级别枚举"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class TestQuestion:
    """测试问题数据结构"""

    question_id: str
    skill_id: str
    difficulty: DifficultyLevel
    content: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    metadata: Dict[str, any] = field(default_factory=dict)


@dataclass
class TestResult:
    """测试结果数据结构"""

    result_id: str
    test_id: str
    answers: Dict[str, str]
    score: float
    correct_count: int
    total_count: int
    skill_performance: Dict[str, float]
    time_spent: float
    completed_at: datetime


@dataclass
class Test:
    """测试数据结构"""

    test_id: str
    name: str
    description: str
    skill_ids: List[str]
    difficulty: DifficultyLevel
    questions: List[TestQuestion]
    status: TestStatus = TestStatus.PENDING
    start_time: Optional[datetime] = None
    result: Optional[TestResult] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Certification:
    """能力认证数据结构"""

    certification_id: str
    skill_id: str
    level: CertificationLevel
    test_id: str
    score: float
    issued_at: datetime
    valid_until: Optional[datetime] = None
    metadata: Dict[str, any] = field(default_factory=dict)


class TestingManager:
    """测试管理器"""

    def __init__(
        self,
        difficulty_evaluator: Optional[DifficultyEvaluator] = None,
        progress_tracker: Optional[ProgressTracker] = None,
        storage_path: Optional[Path] = None,
    ):
        """初始化测试管理器

        Args:
            difficulty_evaluator: 难度评估器
            progress_tracker: 进度追踪器
            storage_path: 持久化存储路径
        """
        self.difficulty_evaluator = difficulty_evaluator or DifficultyEvaluator()
        self.progress_tracker = progress_tracker or ProgressTracker()
        self.storage_path = storage_path or Path("models/curriculum_testing.json")
        self.tests: Dict[str, Test] = {}
        self.certifications: Dict[str, Certification] = {}
        self.question_bank: Dict[str, List[TestQuestion]] = defaultdict(list)
        self._load()

    def generate_test(
        self,
        skill_ids: List[str],
        name: str,
        description: str = "",
        difficulty: Optional[DifficultyLevel] = None,
        question_count: int = 10,
    ) -> Test:
        """生成测试

        Args:
            skill_ids: 技能ID列表
            name: 测试名称
            description: 测试描述
            difficulty: 难度级别，如果为None则根据学习进度自动确定
            question_count: 问题数量

        Returns:
            测试对象
        """
        if difficulty is None:
            difficulty = self._determine_test_difficulty(skill_ids)

        questions = self._select_questions(skill_ids, difficulty, question_count)

        test_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        test = Test(
            test_id=test_id,
            name=name,
            description=description,
            skill_ids=skill_ids.copy(),
            difficulty=difficulty,
            questions=questions,
        )

        self.tests[test_id] = test
        self._save()

        return test

    def _determine_test_difficulty(self, skill_ids: List[str]) -> DifficultyLevel:
        """根据学习进度确定测试难度

        Args:
            skill_ids: 技能ID列表

        Returns:
            难度级别
        """
        avg_mastery = 0.0
        count = 0

        for skill_id in skill_ids:
            skill = self.progress_tracker.get_skill_mastery(skill_id)
            if skill:
                avg_mastery += skill.mastery_level
                count += 1

        if count == 0:
            return DifficultyLevel.EASY

        avg_mastery /= count

        if avg_mastery < 0.4:
            return DifficultyLevel.EASY
        elif avg_mastery < 0.7:
            return DifficultyLevel.MEDIUM
        else:
            return DifficultyLevel.HARD

    def _select_questions(self, skill_ids: List[str], difficulty: DifficultyLevel, count: int) -> List[TestQuestion]:
        """从题库中选择问题

        Args:
            skill_ids: 技能ID列表
            difficulty: 难度级别
            count: 问题数量

        Returns:
            问题列表
        """
        selected = []

        for skill_id in skill_ids:
            skill_questions = [q for q in self.question_bank.get(skill_id, []) if q.difficulty == difficulty]
            selected.extend(skill_questions)

        if not selected:
            selected = self._generate_sample_questions(skill_ids, difficulty, count)

        if len(selected) > count:
            selected = random.sample(selected, count)
        elif len(selected) < count:
            additional = self._generate_sample_questions(skill_ids, difficulty, count - len(selected))
            selected.extend(additional)

        return selected

    def _generate_sample_questions(
        self, skill_ids: List[str], difficulty: DifficultyLevel, count: int
    ) -> List[TestQuestion]:
        """生成示例问题

        Args:
            skill_ids: 技能ID列表
            difficulty: 难度级别
            count: 问题数量

        Returns:
            问题列表
        """
        questions = []

        for i in range(count):
            skill_id = skill_ids[i % len(skill_ids)]
            question_id = f"q_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}"

            question = TestQuestion(
                question_id=question_id,
                skill_id=skill_id,
                difficulty=difficulty,
                content=f"关于 {skill_id} 的{difficulty.value}难度问题 {i + 1}",
                options=["选项A", "选项B", "选项C", "选项D"],
                correct_answer="选项A",
                explanation="这是一个示例问题的解释",
            )

            questions.append(question)

            self.question_bank[skill_id].append(question)

        return questions

    def start_test(self, test_id: str) -> Optional[Test]:
        """开始测试

        Args:
            test_id: 测试ID

        Returns:
            测试对象，如果测试不存在则返回None
        """
        if test_id not in self.tests:
            return None

        test = self.tests[test_id]
        test.status = TestStatus.IN_PROGRESS
        test.start_time = datetime.now()
        self._save()

        return test

    def submit_test(self, test_id: str, answers: Dict[str, str]) -> Optional[TestResult]:
        """提交测试答案

        Args:
            test_id: 测试ID
            answers: 答案字典 {question_id: answer}

        Returns:
            测试结果，如果测试不存在或未开始则返回None
        """
        if test_id not in self.tests:
            return None

        test = self.tests[test_id]

        if test.status != TestStatus.IN_PROGRESS:
            return None

        correct_count = 0
        skill_performance: Dict[str, List[bool]] = defaultdict(list)

        for question in test.questions:
            answer = answers.get(question.question_id)
            is_correct = answer == question.correct_answer

            if is_correct:
                correct_count += 1

            skill_performance[question.skill_id].append(is_correct)

        skill_scores = {}
        for skill_id, results in skill_performance.items():
            skill_scores[skill_id] = sum(results) / len(results) if results else 0.0

        total_count = len(test.questions)
        score = correct_count / total_count if total_count > 0 else 0.0

        time_spent = (datetime.now() - test.start_time).total_seconds() if test.start_time else 0.0

        result_id = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        result = TestResult(
            result_id=result_id,
            test_id=test_id,
            answers=answers.copy(),
            score=score,
            correct_count=correct_count,
            total_count=total_count,
            skill_performance=skill_scores,
            time_spent=time_spent,
            completed_at=datetime.now(),
        )

        test.status = TestStatus.COMPLETED
        test.result = result

        self._update_progress_from_test(test, result)

        self._save()

        return result

    def _update_progress_from_test(self, test: Test, result: TestResult) -> None:
        """根据测试结果更新学习进度

        Args:
            test: 测试对象
            result: 测试结果
        """
        for skill_id, performance in result.skill_performance.items():
            is_correct = performance >= 0.7

            self.progress_tracker.record_learning(
                task_id=f"test_{test.test_id}",
                skill_ids=[skill_id],
                is_correct=is_correct,
                time_spent=result.time_spent / len(result.skill_performance),
                difficulty_score=(
                    0.5
                    if test.difficulty == DifficultyLevel.MEDIUM
                    else (0.2 if test.difficulty == DifficultyLevel.EASY else 0.8)
                ),
            )

    def evaluate_certification(self, skill_id: str, test_id: str) -> Optional[Certification]:
        """评估并颁发能力认证

        Args:
            skill_id: 技能ID
            test_id: 测试ID

        Returns:
            认证对象，如果不符合条件则返回None
        """
        if test_id not in self.tests:
            return None

        test = self.tests[test_id]

        if test.status != TestStatus.COMPLETED or test.result is None:
            return None

        if skill_id not in test.result.skill_performance:
            return None

        score = test.result.skill_performance[skill_id]

        if score < 0.6:
            return None

        if score >= 0.95:
            level = CertificationLevel.EXPERT
        elif score >= 0.85:
            level = CertificationLevel.ADVANCED
        elif score >= 0.75:
            level = CertificationLevel.INTERMEDIATE
        else:
            level = CertificationLevel.BEGINNER

        certification_id = f"cert_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        certification = Certification(
            certification_id=certification_id,
            skill_id=skill_id,
            level=level,
            test_id=test_id,
            score=score,
            issued_at=datetime.now(),
        )

        self.certifications[certification_id] = certification
        self._save()

        return certification

    def get_test(self, test_id: str) -> Optional[Test]:
        """获取测试

        Args:
            test_id: 测试ID

        Returns:
            测试对象，如果不存在则返回None
        """
        return self.tests.get(test_id)

    def get_certification(self, certification_id: str) -> Optional[Certification]:
        """获取认证

        Args:
            certification_id: 认证ID

        Returns:
            认证对象，如果不存在则返回None
        """
        return self.certifications.get(certification_id)

    def get_certifications_for_skill(self, skill_id: str) -> List[Certification]:
        """获取技能的所有认证

        Args:
            skill_id: 技能ID

        Returns:
            认证对象列表
        """
        return [cert for cert in self.certifications.values() if cert.skill_id == skill_id]

    def add_question(self, question: TestQuestion) -> None:
        """添加问题到题库

        Args:
            question: 问题对象
        """
        self.question_bank[question.skill_id].append(question)
        self._save()

    def _load(self) -> None:
        """从文件加载数据"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for skill_id, questions_data in data.get("question_bank", {}).items():
                    for q_data in questions_data:
                        q_data["difficulty"] = DifficultyLevel(q_data["difficulty"])
                        self.question_bank[skill_id].append(TestQuestion(**q_data))

                for test_data in data.get("tests", []):
                    test_data["difficulty"] = DifficultyLevel(test_data["difficulty"])
                    test_data["status"] = TestStatus(test_data["status"])
                    if test_data.get("start_time"):
                        test_data["start_time"] = datetime.fromisoformat(test_data["start_time"])
                    test_data["created_at"] = datetime.fromisoformat(test_data["created_at"])

                    questions_data = test_data.pop("questions", [])
                    result_data = test_data.pop("result", None)

                    test = Test(**test_data)
                    test.questions = [
                        TestQuestion(**{**q, "difficulty": DifficultyLevel(q["difficulty"])}) for q in questions_data
                    ]

                    if result_data:
                        result_data["completed_at"] = datetime.fromisoformat(result_data["completed_at"])
                        test.result = TestResult(**result_data)

                    self.tests[test_data["test_id"]] = test

                for cert_data in data.get("certifications", []):
                    cert_data["level"] = CertificationLevel(cert_data["level"])
                    cert_data["issued_at"] = datetime.fromisoformat(cert_data["issued_at"])
                    if cert_data.get("valid_until"):
                        cert_data["valid_until"] = datetime.fromisoformat(cert_data["valid_until"])
                    self.certifications[cert_data["certification_id"]] = Certification(**cert_data)

            except Exception as e:
                print(f"加载测试数据失败: {e}")

    def _save(self) -> None:
        """保存数据到文件"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"question_bank": {}, "tests": [], "certifications": []}

        for skill_id, questions in self.question_bank.items():
            data["question_bank"][skill_id] = [{**q.__dict__, "difficulty": q.difficulty.value} for q in questions]

        for test in self.tests.values():
            test_dict = {
                **test.__dict__,
                "difficulty": test.difficulty.value,
                "status": test.status.value,
                "start_time": test.start_time.isoformat() if test.start_time else None,
                "created_at": test.created_at.isoformat(),
                "questions": [{**q.__dict__, "difficulty": q.difficulty.value} for q in test.questions],
                "result": None,
            }
            if test.result:
                test_dict["result"] = {**test.result.__dict__, "completed_at": test.result.completed_at.isoformat()}
            data["tests"].append(test_dict)

        for cert in self.certifications.values():
            cert_dict = {
                **cert.__dict__,
                "level": cert.level.value,
                "issued_at": cert.issued_at.isoformat(),
                "valid_until": cert.valid_until.isoformat() if cert.valid_until else None,
            }
            data["certifications"].append(cert_dict)

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
