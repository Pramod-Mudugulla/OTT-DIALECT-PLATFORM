"""
Test Suite: Independent Verification and Safety Checks.
Verifies:
1. Quiet hours (22:00-08:00) blocks messaging channels.
2. Consent checks block unauthorized messages.
3. Frequency caps (max 1/day) prevent message spamming.
4. Home-page rows require at least 3 valid titles in dialect.
5. Injected prompt instructions in catalog descriptions are caught and blocked.
"""

import pytest
from submission.src.models import ActionType, ViewerState
from submission.src.data_loader import DataLoader
from submission.src.verifier import IndependentVerifier


@pytest.fixture
def verifier():
    loader = DataLoader("submission/data")
    return IndependentVerifier(loader)


def test_quiet_hours_blocks_push(verifier):
    state = ViewerState(
        viewer_id="V-QUIET-01",
        profile_snapshot={"push_consent": True}
    )
    # 23:00 local time
    result = verifier.verify(
        viewer_state=state,
        action=ActionType.PUSH_NOTIFICATION,
        dialect="d1",
        content_ids=[],
        device_hour_local=23,
        trigger_received_at="2026-09-12T17:30:00Z"
    )
    assert "quiet_hours_violation" in result.failed


def test_missing_consent_blocks_push(verifier):
    state = ViewerState(
        viewer_id="V-NOCONSENT-01",
        profile_snapshot={"push_consent": False}
    )
    # Daytime (14:00)
    result = verifier.verify(
        viewer_state=state,
        action=ActionType.PUSH_NOTIFICATION,
        dialect="d1",
        content_ids=[],
        device_hour_local=14,
        trigger_received_at="2026-09-12T10:00:00Z"
    )
    assert "missing_push_consent" in result.failed


def test_frequency_cap_blocks_second_message(verifier):
    state = ViewerState(
        viewer_id="V-CAP-01",
        profile_snapshot={"push_consent": True},
        last_message_sent_at="2026-09-12T08:00:00Z"
    )
    # Second message attempted only 2 hours later
    result = verifier.verify(
        viewer_state=state,
        action=ActionType.PUSH_NOTIFICATION,
        dialect="d1",
        content_ids=[],
        device_hour_local=10,
        trigger_received_at="2026-09-12T10:00:00Z"
    )
    assert "frequency_cap_exceeded" in result.failed


def test_home_row_minimum_titles_requirement(verifier):
    state = ViewerState(viewer_id="V-ROW-01")
    # Only 2 titles provided
    result = verifier.verify(
        viewer_state=state,
        action=ActionType.HOME_PAGE,
        dialect="d1",
        content_ids=["title:T0002", "title:T0003"],
        device_hour_local=12,
        trigger_received_at="2026-09-12T10:00:00Z"
    )
    assert "home_row_minimum_titles_unmet" in result.failed


def test_adversarial_prompt_injection_defense(verifier):
    state = ViewerState(viewer_id="V-ATTACK-01")
    # Title T0001 contains injected prompt instruction
    result = verifier.verify(
        viewer_state=state,
        action=ActionType.HOME_PAGE,
        dialect="d1",
        content_ids=["title:T0001", "title:T0002", "title:T0003"],
        device_hour_local=12,
        trigger_received_at="2026-09-12T10:00:00Z"
    )
    assert "prompt_injection_detected_in_content" in result.failed
