"""
集体决策和投票机制 - 实现多智能体集体决策
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum, auto
import uuid
import logging
import asyncio
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class VotingStrategy(Enum):
    """投票策略"""

    MAJORITY = auto()
    WEIGHTED = auto()
    CONSENSUS = auto()
    RANKED_CHOICE = auto()


class VoteStatus(Enum):
    """投票状态"""

    PENDING = auto()
    OPEN = auto()
    CLOSED = auto()
    RESOLVED = auto()


@dataclass
class Vote:
    """单个投票"""

    vote_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    voter_id: str
    choice: Any
    weight: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0
    reasoning: Optional[str] = None


@dataclass
class VotingSession:
    """投票会话"""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    description: str
    options: List[Any]
    strategy: VotingStrategy = VotingStrategy.MAJORITY
    status: VoteStatus = VoteStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None
    votes: Dict[str, Vote] = field(default_factory=dict)
    voter_weights: Dict[str, float] = field(default_factory=dict)
    required_consensus: float = 0.9
    quorum: Optional[float] = None
    result: Optional[Any] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_vote(self, vote: Vote) -> bool:
        """添加投票"""
        if self.status != VoteStatus.OPEN:
            return False
        if vote.voter_id in self.votes:
            return False
        self.votes[vote.voter_id] = vote
        self.updated_at = datetime.now()
        return True

    def update_voter_weight(self, voter_id: str, weight: float) -> None:
        """更新投票权重"""
        self.voter_weights[voter_id] = weight
        self.updated_at = datetime.now()

    def get_voter_count(self) -> int:
        """获取投票人数"""
        return len(self.votes)

    def is_quorum_met(self, total_voters: int) -> bool:
        """检查是否达到法定人数"""
        if self.quorum is None:
            return True
        return (len(self.votes) / total_voters) >= self.quorum

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "description": self.description,
            "options": self.options,
            "strategy": self.strategy.name,
            "status": self.status.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "votes": {
                k: {
                    "vote_id": v.vote_id,
                    "voter_id": v.voter_id,
                    "choice": v.choice,
                    "weight": v.weight,
                    "timestamp": v.timestamp.isoformat(),
                    "confidence": v.confidence,
                    "reasoning": v.reasoning,
                }
                for k, v in self.votes.items()
            },
            "voter_weights": self.voter_weights,
            "required_consensus": self.required_consensus,
            "quorum": self.quorum,
            "result": self.result,
            "resolved_at": (
                self.resolved_at.isoformat() if self.resolved_at else None
            ),
            "metadata": self.metadata,
        }


class VotingEngine:
    """投票引擎"""

    def __init__(self):
        self.sessions: Dict[str, VotingSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        topic: str,
        description: str,
        options: List[Any],
        strategy: VotingStrategy = VotingStrategy.MAJORITY,
        deadline: Optional[datetime] = None,
        voter_weights: Optional[Dict[str, float]] = None,
        required_consensus: float = 0.9,
        quorum: Optional[float] = None,
    ) -> str:
        """创建投票会话"""
        async with self._lock:
            session = VotingSession(
                topic=topic,
                description=description,
                options=options,
                strategy=strategy,
                deadline=deadline,
                voter_weights=voter_weights or {},
                required_consensus=required_consensus,
                quorum=quorum,
                status=VoteStatus.OPEN,
            )
            self.sessions[session.session_id] = session
            logger.info(f"投票会话已创建: {session.session_id} - {topic}")
            return session.session_id

    async def get_session(self, session_id: str) -> Optional[VotingSession]:
        """获取投票会话"""
        async with self._lock:
            return self.sessions.get(session_id)

    async def cast_vote(
        self,
        session_id: str,
        voter_id: str,
        choice: Any,
        weight: float = 1.0,
        confidence: float = 1.0,
        reasoning: Optional[str] = None,
    ) -> bool:
        """提交投票"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session or session.status != VoteStatus.OPEN:
                return False
            if choice not in session.options:
                return False

            vote = Vote(
                voter_id=voter_id,
                choice=choice,
                weight=session.voter_weights.get(voter_id, weight),
                confidence=confidence,
                reasoning=reasoning,
            )
            success = session.add_vote(vote)
            if success:
                logger.debug(
                    f"投票已提交: {voter_id} -> {choice} (会话: {session_id})"
                )
            return success

    async def close_session(self, session_id: str) -> bool:
        """关闭投票会话"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False
            session.status = VoteStatus.CLOSED
            session.updated_at = datetime.now()
            logger.info(f"投票会话已关闭: {session_id}")
            return True


class DecisionAggregator:
    """决策集成器"""

    def __init__(self):
        self.conflict_resolvers: Dict[str, Callable] = {}

    def count_votes(self, session: VotingSession) -> Dict[Any, int]:
        """计票（多数制）"""
        counts = Counter()
        for vote in session.votes.values():
            counts[vote.choice] += 1
        return counts

    def count_weighted_votes(self, session: VotingSession) -> Dict[Any, float]:
        """计票（加权制）"""
        weighted_counts: Dict[Any, float] = defaultdict(float)
        for vote in session.votes.values():
            weighted_counts[vote.choice] += vote.weight * vote.confidence
        return weighted_counts

    def resolve_majority(self, session: VotingSession) -> Optional[Any]:
        """多数制决策"""
        counts = self.count_votes(session)
        if not counts:
            return None
        max_count = max(counts.values())
        winners = [
            choice for choice, count in counts.items() if count == max_count
        ]
        return winners[0] if len(winners) == 1 else None

    def resolve_weighted(self, session: VotingSession) -> Optional[Any]:
        """加权制决策"""
        weighted_counts = self.count_weighted_votes(session)
        if not weighted_counts:
            return None
        max_weight = max(weighted_counts.values())
        winners = [
            choice
            for choice, weight in weighted_counts.items()
            if weight == max_weight
        ]
        return winners[0] if len(winners) == 1 else None

    def resolve_consensus(self, session: VotingSession) -> Optional[Any]:
        """共识制决策"""
        if not session.votes:
            return None
        first_choice = next(iter(session.votes.values())).choice
        all_same = all(
            vote.choice == first_choice for vote in session.votes.values()
        )
        if all_same:
            return first_choice
        agreement = sum(
            1 for vote in session.votes.values() if vote.choice == first_choice
        ) / len(session.votes)
        return (
            first_choice if agreement >= session.required_consensus else None
        )

    def resolve_ranked_choice(self, session: VotingSession) -> Optional[Any]:
        """排序投票决策"""
        if not session.votes:
            return None
        return self.resolve_majority(session)

    def resolve(
        self, session: VotingSession, total_voters: Optional[int] = None
    ) -> Dict[str, Any]:
        """集成决策"""
        if session.status not in (VoteStatus.CLOSED, VoteStatus.OPEN):
            return {"success": False, "error": "投票会话未开放或已关闭"}

        if total_voters and not session.is_quorum_met(total_voters):
            return {"success": False, "error": "未达到法定人数"}

        result = None
        strategy = session.strategy

        if strategy == VotingStrategy.MAJORITY:
            result = self.resolve_majority(session)
        elif strategy == VotingStrategy.WEIGHTED:
            result = self.resolve_weighted(session)
        elif strategy == VotingStrategy.CONSENSUS:
            result = self.resolve_consensus(session)
        elif strategy == VotingStrategy.RANKED_CHOICE:
            result = self.resolve_ranked_choice(session)

        return {
            "success": result is not None,
            "result": result,
            "strategy": strategy.name,
            "vote_count": len(session.votes),
            "votes": self.count_votes(session),
            "weighted_votes": self.count_weighted_votes(session),
        }


class ConflictResolver:
    """冲突解决器"""

    def __init__(self):
        self.resolution_history: List[Dict[str, Any]] = []

    def mediate(
        self, session: VotingSession, conflicting_options: List[Any]
    ) -> Dict[str, Any]:
        """调解冲突"""
        logger.info(f"正在调解冲突: {conflicting_options}")

        vote_counts = Counter()
        for vote in session.votes.values():
            vote_counts[vote.choice] += 1

        resolution = {
            "session_id": session.session_id,
            "timestamp": datetime.now().isoformat(),
            "conflicting_options": conflicting_options,
            "vote_counts": dict(vote_counts),
            "mediation_strategy": "select_most_popular",
            "recommended_option": (
                max(vote_counts, key=vote_counts.get) if vote_counts else None
            ),
        }

        self.resolution_history.append(resolution)
        return resolution

    def find_common_ground(self, session: VotingSession) -> Optional[Any]:
        """寻找共同点"""
        if not session.votes:
            return None

        all_reasonings = [
            vote.reasoning for vote in session.votes.values() if vote.reasoning
        ]
        if all_reasonings:
            logger.info(f"基于投票理由寻找共同点: {all_reasonings}")

        return None
