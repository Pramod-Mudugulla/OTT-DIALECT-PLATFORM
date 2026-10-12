"""
Core Data Models for One User, One Agent System.
Defines schemas for triggers, facts, goals, actions, decisions, and outcomes.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ActionType(str, Enum):
    HOME_PAGE = "HOME_PAGE"
    PUSH_NOTIFICATION = "PUSH_NOTIFICATION"
    WHATSAPP = "WHATSAPP"
    IN_APP_MESSAGE = "IN_APP_MESSAGE"
    DO_NOTHING = "DO_NOTHING"


class Dialect(str, Enum):
    D1 = "d1"
    D2 = "d2"
    D3 = "d3"
    D4 = "d4"
    D5 = "d5"
    D6 = "d6"


class SubscriptionStatus(str, Enum):
    FREE = "free"
    FREE_TRIAL = "free_trial"
    MONTHLY = "monthly"
    ANNUAL = "annual"


class DecisionStatus(str, Enum):
    PUBLISHED = "PUBLISHED"
    ABSTAINED = "ABSTAINED"
    FALLBACK = "FALLBACK"
    REJECTED = "REJECTED"


class OutcomeStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    PENDING = "PENDING"


class ViewerFact(BaseModel):
    key: str
    value: Any
    source: str  # 'event_stream', 'app_setting', 'profile_snapshot', 'campaign_link'
    recorded_at: str  # ISO timestamp
    freshness_s: float
    confidence: float = 1.0


class TriggerEvent(BaseModel):
    event_id: str
    viewer_id: str
    event_type: str  # e.g., 'app_open', 'play', 'purchase', 'search'
    timestamp: str  # Client clock
    received_at: str  # Server reception time
    event_age_s: float = 0.0
    app_dialect: Optional[str] = None
    app_language: Optional[str] = None
    campaign_dialect: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class CatalogueTitle(BaseModel):
    title_id: str
    title_name: str
    dialects: List[str]
    languages: List[str]
    genres: List[str]
    content_type: str  # 'micro_drama', 'series', 'film'
    episodes: int = 1
    is_available: bool = True
    description: str = ""


class GoalRule(BaseModel):
    goal_id: str
    name: str
    description: str
    deadline_hours: int
    success_signal_type: str
    is_underspecified: bool = False
    missing_signal: bool = False
    version: int = 1


class DialectDecision(BaseModel):
    used: str
    source: str
    conflicts: List[str] = Field(default_factory=list)


class TriggerInfo(BaseModel):
    event: str
    received_at: str
    event_age_s: float


class GoalInfo(BaseModel):
    id: str
    deadline: str


class ChecksResult(BaseModel):
    passed: List[str] = Field(default_factory=list)
    failed: List[str] = Field(default_factory=list)


class DecisionOutput(BaseModel):
    decision_id: str
    viewer_id: str
    trigger: TriggerInfo
    goal: Optional[GoalInfo] = None
    action: ActionType
    dialect: DialectDecision
    content: List[str] = Field(default_factory=list)
    confidence: float
    confidence_reason: str = ""
    evidence: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    checks: ChecksResult = Field(default_factory=ChecksResult)
    decided_in_ms: int
    status: DecisionStatus
    reason_for_no_action: Optional[str] = None


class ViewerState(BaseModel):
    viewer_id: str
    is_holdout: bool = False  # Randomized 10% holdout for control group
    profile_snapshot: Dict[str, Any] = Field(default_factory=dict)
    known_facts: Dict[str, ViewerFact] = Field(default_factory=dict)
    active_goal: Optional[GoalInfo] = None
    active_plan: Optional[str] = None
    history_decisions: List[str] = Field(default_factory=list)
    history_actions: List[Dict[str, Any]] = Field(default_factory=list)
    history_outcomes: List[Dict[str, Any]] = Field(default_factory=list)
    last_message_sent_at: Optional[str] = None
    learnings: List[str] = Field(default_factory=list)
    last_seen: Optional[str] = None


class OutcomeJudgment(BaseModel):
    judgment_id: str
    decision_id: str
    viewer_id: str
    goal_id: str
    status: OutcomeStatus
    evaluated_at: str
    deadline: str
    attributable_signals: List[str]
    explanation: str
    learning_added: str
