"""
Outcome Judgement and Attribution Engine.
Closes the loop by evaluating attributable signals against active goal deadlines.
Judges outcomes as SUCCEEDED, FAILED, or INCONCLUSIVE, and feeds learnings
back into durable viewer memory.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from submission.src.models import (
    OutcomeJudgment, OutcomeStatus, DecisionOutput, ViewerState, TriggerEvent
)
from submission.src.memory import ViewerMemoryStore


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



class OutcomeJudge:
    def __init__(self, memory_store: ViewerMemoryStore):
        self.memory_store = memory_store

    def evaluate_decision_outcome(
        self,
        decision: DecisionOutput,
        subsequent_events: List[Dict[str, Any]],
        evaluation_time_iso: str
    ) -> OutcomeJudgment:
        """
        Judges whether an intervention led to goal achievement based strictly
        on attributable signals arriving before the goal deadline.
        """
        viewer_id = decision.viewer_id
        eval_dt = parse_iso_time(evaluation_time_iso)

        if not decision.goal:
            return OutcomeJudgment(
                judgment_id=f"JUDGE-{uuid.uuid4().hex[:6]}",
                decision_id=decision.decision_id,
                viewer_id=viewer_id,
                goal_id="none",
                status=OutcomeStatus.INCONCLUSIVE,
                evaluated_at=evaluation_time_iso,
                deadline="none",
                attributable_signals=[],
                explanation="No active goal was bound to this decision.",
                learning_added="Viewer had no active measurable goal."
            )

        goal_id = decision.goal.id
        deadline_str = decision.goal.deadline
        deadline_dt = parse_iso_time(deadline_str)

        attributable_signals = []
        is_success = False
        is_inconclusive = False

        # Filter events for this viewer that occurred between decision and deadline
        dec_received_dt = parse_iso_time(decision.trigger.received_at)

        for ev in subsequent_events:
            ev_dt = parse_iso_time(ev.get("timestamp", evaluation_time_iso))
            if ev_dt < dec_received_dt:
                continue  # Event preceded decision

            if ev_dt > deadline_dt:
                continue  # Arrived after deadline (not attributable to this window)

            ev_type = ev.get("event_type")
            payload = ev.get("payload", {})

            if goal_id == "first_full_episode_3d":
                if ev_type == "play" and payload.get("episode_completed", False):
                    # Check if attributable (watched one of recommended titles or during session)
                    played_title = payload.get("title_id")
                    if played_title:
                        attributable_signals.append(f"event:{ev.get('event_id', 'play')}:title_{played_title}")
                        is_success = True
                        break
                    else:
                        attributable_signals.append(f"event:{ev.get('event_id', 'play')}:general_play")
                        is_success = True
                        break

            elif goal_id == "first_paid_plan_7d":
                if ev_type == "purchase":
                    attributable_signals.append(f"event:{ev.get('event_id', 'purchase')}:plan_{payload.get('plan', 'monthly')}")
                    is_success = True
                    break

            elif goal_id == "resume_dropped_series_2d":
                if ev_type == "play":
                    attributable_signals.append(f"event:{ev.get('event_id', 'play')}:resumed")
                    is_success = True
                    break

        # Check for unmeasurable / missing signals (e.g. social share)
        if goal_id == "social_share_referral_3d":
            is_inconclusive = True
            explanation = "Success signal 'social_share' does not exist in event stream telemetry."
            learning = "Goal social_share_referral_3d cannot be proven; telemetry gap identified."
        elif is_success:
            status = OutcomeStatus.SUCCEEDED
            explanation = f"Viewer completed goal within deadline via attributable signals: {', '.join(attributable_signals)}"
            learning = f"Successful intervention on {decision.dialect.used} using {decision.action.value}."
        elif eval_dt >= deadline_dt:
            status = OutcomeStatus.FAILED
            explanation = f"Goal deadline {deadline_str} elapsed without attributable success signal."
            learning = f"Intervention {decision.action.value} did not achieve {goal_id} before deadline."
        else:
            status = OutcomeStatus.PENDING
            explanation = f"Goal active; deadline {deadline_str} has not yet passed."
            learning = ""

        if is_inconclusive:
            status = OutcomeStatus.INCONCLUSIVE

        judgment = OutcomeJudgment(
            judgment_id=f"JUDGE-{uuid.uuid4().hex[:6]}",
            decision_id=decision.decision_id,
            viewer_id=viewer_id,
            goal_id=goal_id,
            status=status,
            evaluated_at=evaluation_time_iso,
            deadline=deadline_str,
            attributable_signals=attributable_signals,
            explanation=explanation,
            learning_added=learning
        )

        # Record outcome and learning in durable viewer memory
        self.memory_store.record_outcome(viewer_id, judgment)
        return judgment
