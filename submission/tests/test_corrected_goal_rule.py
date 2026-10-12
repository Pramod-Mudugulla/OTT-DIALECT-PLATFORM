"""
Test Suite: Corrected Goal Rule and Telemetry Telemetry Gaps.
Verifies:
1. Dynamic mid-replay rule updates bump versions and resolve underspecified conditions.
2. Unmeasurable goals with missing signals are flagged and cannot be chosen.
"""

import pytest
from submission.src.data_loader import DataLoader
from submission.src.goal_engine import GoalEngine


def test_correct_underspecified_goal_rule():
    loader = DataLoader("submission/data")
    engine = GoalEngine(loader.goals)

    # Initially, dialect_crossover_discovery_7d is underspecified in v1
    rule_v1 = engine.goals["dialect_crossover_discovery_7d"]
    assert rule_v1.is_underspecified is True
    assert rule_v1.version == 1

    # Mid-replay rule correction arrives
    updated_rule = engine.correct_rule("dialect_crossover_discovery_7d", {
        "is_underspecified": False,
        "description": "Corrected v2: Viewers in d1 map to d2/d3; d4 maps to d5/d6."
    })

    assert updated_rule.version == 2
    assert updated_rule.is_underspecified is False
    assert engine.goals["dialect_crossover_discovery_7d"].version == 2


def test_missing_telemetry_signal_rejection():
    loader = DataLoader("submission/data")
    engine = GoalEngine(loader.goals)

    # Goal social_share_referral_3d has missing signal in app telemetry
    is_measurable, reason = engine.check_goal_measurability("social_share_referral_3d")
    assert is_measurable is False
    assert "missing" in reason.lower()
