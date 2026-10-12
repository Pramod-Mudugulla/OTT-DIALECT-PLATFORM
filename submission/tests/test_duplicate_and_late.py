"""
Test Suite: Duplicate and Late Offline Trigger Handling.
Verifies idempotent processing of duplicate triggers and accurate freshness tracking
for multi-day offline buffered triggers.
"""

import pytest
from submission.src.models import TriggerEvent, ActionType, DecisionStatus
from submission.src.data_loader import DataLoader
from submission.src.memory import ViewerMemoryStore
from submission.src.resolver import FactResolver
from submission.src.goal_engine import GoalEngine
from submission.src.verifier import IndependentVerifier
from submission.src.provider import MockReplayProvider
from submission.src.agent import ViewerAgent


@pytest.fixture
def agent_components(tmp_path):
    loader = DataLoader("submission/data")
    memory = ViewerMemoryStore(str(tmp_path / "viewer_state"))
    resolver = FactResolver()
    goals = GoalEngine(loader.goals)
    verifier = IndependentVerifier(loader)
    provider = MockReplayProvider()
    agent = ViewerAgent("V-0120", memory, resolver, goals, verifier, provider, loader)
    return agent, memory


def test_duplicate_trigger_idempotency(agent_components):
    agent, memory = agent_components
    trigger1 = TriggerEvent(
        event_id="E-TEST-DUP-01",
        viewer_id="V-0120",
        event_type="app_open",
        timestamp="2026-09-12T10:00:00Z",
        received_at="2026-09-12T10:00:01Z",
        app_dialect="d2"
    )

    # First call processes normally
    decision1 = agent.process_trigger(trigger1)
    assert decision1.status in [DecisionStatus.PUBLISHED, DecisionStatus.FALLBACK, DecisionStatus.ABSTAINED]
    assert memory.is_trigger_processed("E-TEST-DUP-01")

    # Second identical call must be detected as duplicate and handled idempotently
    decision2 = agent.process_trigger(trigger1)
    assert decision2.status == DecisionStatus.ABSTAINED
    assert decision2.action == ActionType.DO_NOTHING
    assert "idempotency_duplicate_trigger" in decision2.checks.failed
    assert "Duplicate trigger detected" in decision2.confidence_reason


def test_late_offline_buffered_trigger(agent_components):
    agent, _ = agent_components
    # Trigger whose device clock is 4 days older than server received_at
    late_trigger = TriggerEvent(
        event_id="E-TEST-LATE-01",
        viewer_id="V-0120",
        event_type="app_open",
        timestamp="2026-09-08T08:00:00Z",  # 4 days ago
        received_at="2026-09-12T08:00:00Z",  # received today
        app_dialect="d2"
    )

    decision = agent.process_trigger(late_trigger)
    assert decision.trigger.event_age_s == pytest.approx(4 * 86400, rel=1e-2)
    assert any("buffered offline" in assumption for assumption in decision.assumptions)
