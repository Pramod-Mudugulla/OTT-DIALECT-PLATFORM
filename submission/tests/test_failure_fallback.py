"""
Test Suite: Tool and Model Failure Recovery.
Verifies that when a model or tool times out, fails, or exceeds budget,
the agent degrades gracefully to a safe action or DO_NOTHING without crashing.
"""

import pytest
from submission.src.models import TriggerEvent, ActionType, DecisionStatus
from submission.src.data_loader import DataLoader
from submission.src.memory import ViewerMemoryStore
from submission.src.resolver import FactResolver
from submission.src.goal_engine import GoalEngine
from submission.src.verifier import IndependentVerifier
from submission.src.provider import MockReplayProvider, BudgetExceededError
from submission.src.agent import ViewerAgent


def test_provider_failure_graceful_fallback(tmp_path):
    loader = DataLoader("submission/data")
    memory = ViewerMemoryStore(str(tmp_path / "viewer_state"))
    resolver = FactResolver()
    goals = GoalEngine(loader.goals)
    verifier = IndependentVerifier(loader)
    
    # Provider initialized with simulated failure flag (e.g. 503 LLM service timeout)
    failing_provider = MockReplayProvider(simulate_failure=True)

    agent = ViewerAgent("V-TEST-FAIL", memory, resolver, goals, verifier, failing_provider, loader)

    trigger = TriggerEvent(
        event_id="E-FAIL-01",
        viewer_id="V-TEST-FAIL",
        event_type="app_open",
        timestamp="2026-09-12T10:00:00Z",
        received_at="2026-09-12T10:00:01Z",
        app_dialect="d1"
    )

    # Must complete safely without unhandled exceptions
    decision = agent.process_trigger(trigger)

    assert decision.action == ActionType.DO_NOTHING
    assert decision.status in [DecisionStatus.ABSTAINED, DecisionStatus.FALLBACK]
    assert "Provider failure" in (decision.reason_for_no_action or "")


def test_budget_enforcement():
    # Enforce maximum 8 model calls per decision
    provider = MockReplayProvider(max_model_calls=2)
    provider.model_calls_count = 2

    with pytest.raises(BudgetExceededError):
        provider.plan_intervention({"candidate_titles": []})
