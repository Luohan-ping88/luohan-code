"""
多智能体协调模块 - 提供智能体对齐与统一的核心功能
"""

from .protocol import MessageType, MessagePriority, MessageHeader, Message, MessageQueue, CommunicationProtocol

from .memory import MemoryType, MemoryItem, ShortTermMemory, LongTermMemory, WorkingMemory, SharedMemorySystem

from .alignment import GoalStatus, GoalPriority, Milestone, AlignmentGoal, GoalTracker, GoalEvaluator

from .voting import VotingStrategy, VoteStatus, Vote, VotingSession, VotingEngine, DecisionAggregator, ConflictResolver

__all__ = [
    # Protocol
    "MessageType",
    "MessagePriority",
    "MessageHeader",
    "Message",
    "MessageQueue",
    "CommunicationProtocol",
    # Memory
    "MemoryType",
    "MemoryItem",
    "ShortTermMemory",
    "LongTermMemory",
    "WorkingMemory",
    "SharedMemorySystem",
    # Alignment
    "GoalStatus",
    "GoalPriority",
    "Milestone",
    "AlignmentGoal",
    "GoalTracker",
    "GoalEvaluator",
    # Voting
    "VotingStrategy",
    "VoteStatus",
    "Vote",
    "VotingSession",
    "VotingEngine",
    "DecisionAggregator",
    "ConflictResolver",
]
