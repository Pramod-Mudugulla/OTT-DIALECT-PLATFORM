"""
Test Suite: Conflicting Source Handling.
Verifies precedence rules:
1. Dialect precedence: app_setting > profile_snapshot > campaign_link, with explicit conflict logging.
2. Subscription precedence: Real-time purchase event strictly overrides 1-day stale profile snapshot.
"""

import pytest
from submission.src.models import TriggerEvent, ViewerState
from submission.src.resolver import FactResolver


def test_three_way_dialect_conflict():
    resolver = FactResolver()
    
    # State holds profile indicating 'd1'
    state = ViewerState(
        viewer_id="V-TEST-01",
        profile_snapshot={"preferred_dialect": "d1"}
    )

    # Trigger carries app_dialect 'd3' and campaign_dialect 'd2'
    trigger = TriggerEvent(
        event_id="E-CONFLICT-01",
        viewer_id="V-TEST-01",
        event_type="app_open",
        timestamp="2026-09-12T10:00:00Z",
        received_at="2026-09-12T10:00:01Z",
        app_dialect="d3",
        campaign_dialect="d2"
    )

    facts, dialect_dec, assumptions = resolver.assemble_and_resolve(trigger, state)

    # 1. Precedence must choose app_setting ('d3') because it represents active UI state
    assert dialect_dec.used == "d3"
    assert dialect_dec.source == "app_setting"

    # 2. Conflicts must be explicitly listed, never silently discarded
    assert "profile:d1" in dialect_dec.conflicts
    assert "campaign:d2" in dialect_dec.conflicts


def test_realtime_purchase_overrides_stale_profile():
    resolver = FactResolver()

    # Profile snapshot says user is free_trial (1-day stale)
    state = ViewerState(
        viewer_id="V-TEST-02",
        profile_snapshot={
            "subscription_status": "free_trial",
            "snapshot_export_time": "2026-09-11T04:00:00Z"
        }
    )

    # Real-time event arrives indicating purchase
    trigger = TriggerEvent(
        event_id="E-PURCHASE-01",
        viewer_id="V-TEST-02",
        event_type="purchase",
        timestamp="2026-09-12T10:00:00Z",
        received_at="2026-09-12T10:00:01Z",
        app_dialect="d1"
    )

    facts, _, _ = resolver.assemble_and_resolve(trigger, state, latest_purchase_event=True)

    # Real-time event stream must override warehouse snapshot
    sub_fact = facts["subscription_status"]
    assert sub_fact.value == "monthly"
    assert sub_fact.source == "event_stream"
    assert sub_fact.freshness_s == 0.0
