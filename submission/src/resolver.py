"""
Fact Assembly, Precedence, and Conflict Resolution Engine.
Resolves facts across event streams, profile snapshots, app settings, and campaign links
with strict provenance, freshness calculations, and explicit conflict logging.
"""

from datetime import datetime
from typing import Dict, Any, Tuple, List
from submission.src.models import TriggerEvent, ViewerFact, DialectDecision, ViewerState


from datetime import timezone

def parse_iso_time(ts_str: str) -> datetime:
    try:
        clean_str = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)



class FactResolver:
    def __init__(self):
        pass

    def assemble_and_resolve(
        self,
        trigger: TriggerEvent,
        viewer_state: ViewerState,
        latest_purchase_event: bool = False
    ) -> Tuple[Dict[str, ViewerFact], DialectDecision, List[str]]:
        """
        Assembles all facts about the viewer, calculates freshness,
        resolves conflicts according to explicit precedence rules,
        and returns:
          1. facts dict
          2. dialect decision (used, source, conflicts)
          3. list of assumptions made
        """
        now_dt = parse_iso_time(trigger.received_at)
        facts: Dict[str, ViewerFact] = {}
        assumptions: List[str] = []
        conflicts: List[str] = []

        profile = viewer_state.profile_snapshot or {}

        # -------------------------------------------------------------
        # 1. Dialect Resolution with Precedence and Conflict Tracking
        # -------------------------------------------------------------
        app_dialect = trigger.app_dialect
        profile_dialect = profile.get("preferred_dialect")
        campaign_dialect = trigger.campaign_dialect

        used_dialect = "d1"
        dialect_source = "default_fallback"

        # Check for conflicts between sources
        if profile_dialect and app_dialect and profile_dialect != app_dialect:
            conflicts.append(f"profile:{profile_dialect}")
        if campaign_dialect and app_dialect and campaign_dialect != app_dialect:
            conflicts.append(f"campaign:{campaign_dialect}")
        if campaign_dialect and profile_dialect and not app_dialect and campaign_dialect != profile_dialect:
            conflicts.append(f"campaign:{campaign_dialect}")

        # Precedence rule:
        # 1st: app_setting (active UI state the viewer is looking at right now)
        # 2nd: profile_snapshot (warehouse preference)
        # 3rd: campaign_link (ad referral)
        # 4th: default 'd1' fallback
        if app_dialect:
            used_dialect = app_dialect
            dialect_source = "app_setting"
        elif profile_dialect:
            used_dialect = profile_dialect
            dialect_source = "profile_snapshot"
            assumptions.append("Used profile dialect because app setting was omitted in trigger")
        elif campaign_dialect:
            used_dialect = campaign_dialect
            dialect_source = "campaign_link"
            assumptions.append("Used campaign dialect because app setting and profile were absent")
        else:
            used_dialect = "d1"
            dialect_source = "default_fallback"
            assumptions.append("Defaulted to dialect d1 because no dialect signals exist")

        dialect_decision = DialectDecision(
            used=used_dialect,
            source=dialect_source,
            conflicts=conflicts
        )

        facts["active_dialect"] = ViewerFact(
            key="active_dialect",
            value=used_dialect,
            source=dialect_source,
            recorded_at=trigger.received_at,
            freshness_s=0.0,
            confidence=0.95 if not conflicts else 0.75
        )

        # -------------------------------------------------------------
        # 2. Subscription Status Resolution
        # Precedence rule: Real-time purchase event strictly overrides
        # 1-day stale profile snapshot!
        # -------------------------------------------------------------
        if latest_purchase_event or trigger.event_type == "purchase":
            sub_status = "monthly"
            sub_source = "event_stream"
            sub_freshness = 0.0
            facts["has_paid"] = ViewerFact(
                key="has_paid",
                value=True,
                source="event_stream",
                recorded_at=trigger.received_at,
                freshness_s=0.0,
                confidence=1.0
            )
        else:
            profile_sub = profile.get("subscription_status", "free")
            snapshot_time = profile.get("snapshot_export_time")
            freshness = 86400.0  # default 1 day stale
            if snapshot_time:
                snap_dt = parse_iso_time(snapshot_time)
                freshness = max(0.0, (now_dt - snap_dt).total_seconds())

            sub_status = profile_sub
            sub_source = "profile_snapshot"
            sub_freshness = freshness

        facts["subscription_status"] = ViewerFact(
            key="subscription_status",
            value=sub_status,
            source=sub_source,
            recorded_at=trigger.received_at,
            freshness_s=sub_freshness,
            confidence=0.9 if sub_source == "event_stream" else 0.65
        )

        # -------------------------------------------------------------
        # 3. Trigger Timing & Freshness Check
        # Check for offline buffered bursts (device clock vs received_at)
        # -------------------------------------------------------------
        device_dt = parse_iso_time(trigger.timestamp)
        clock_skew_s = max(0.0, (now_dt - device_dt).total_seconds())
        trigger.event_age_s = clock_skew_s

        facts["event_age"] = ViewerFact(
            key="event_age",
            value=clock_skew_s,
            source="event_stream",
            recorded_at=trigger.received_at,
            freshness_s=0.0,
            confidence=1.0
        )

        if clock_skew_s > 86400:  # Older than 24 hours
            assumptions.append(f"Trigger was buffered offline for {clock_skew_s / 3600:.1f} hours")

        # -------------------------------------------------------------
        # 4. Consent and Communication Preferences
        # -------------------------------------------------------------
        push_consent = profile.get("push_consent", False)
        wa_consent = profile.get("whatsapp_consent", False)

        facts["push_consent"] = ViewerFact(
            key="push_consent",
            value=push_consent,
            source="profile_snapshot",
            recorded_at=profile.get("snapshot_export_time", trigger.received_at),
            freshness_s=86400.0,
            confidence=0.85
        )

        facts["whatsapp_consent"] = ViewerFact(
            key="whatsapp_consent",
            value=wa_consent,
            source="profile_snapshot",
            recorded_at=profile.get("snapshot_export_time", trigger.received_at),
            freshness_s=86400.0,
            confidence=0.85
        )

        return facts, dialect_decision, assumptions
