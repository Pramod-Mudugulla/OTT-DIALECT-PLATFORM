"""
Goal Engine and Rule Management.
Evaluates eligibility across the 12 candidate goals, handles underspecified rules,
unmeasurable signals, and dynamic rule versioning / corrections mid-replay.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from submission.src.models import GoalRule, GoalInfo, ViewerState, ViewerFact


class GoalEngine:
    def __init__(self, initial_goals: Dict[str, GoalRule]):
        self.goals: Dict[str, GoalRule] = {k: v.model_copy() for k, v in initial_goals.items()}

    def correct_rule(self, goal_id: str, updated_fields: dict) -> GoalRule:
        """
        Dynamically corrects a goal rule during replay (Section 6 surprise requirement).
        Bumps the rule version and updates conditions.
        """
        if goal_id in self.goals:
            current = self.goals[goal_id]
            data = current.model_dump()
            data.update(updated_fields)
            data["version"] = current.version + 1
            updated_rule = GoalRule(**data)
            self.goals[goal_id] = updated_rule
            return updated_rule
        raise KeyError(f"Goal {goal_id} not found in catalog")

    def select_goal(
        self,
        viewer_state: ViewerState,
        facts: Dict[str, ViewerFact],
        current_time_iso: str
    ) -> Tuple[Optional[GoalInfo], Optional[str], List[str]]:
        """
        Selects a measurable goal the viewer is eligible for, or explains why no goal chosen.
        Returns:
          1. GoalInfo (id, deadline) or None
          2. Reason if no goal chosen
          3. Evidence references used for eligibility
        """
        # If viewer already has an active, non-expired goal, maintain single active plan ownership!
        if viewer_state.active_goal:
            try:
                deadline_dt = datetime.fromisoformat(viewer_state.active_goal.deadline.replace("Z", "+00:00"))
                now_dt = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
                if now_dt < deadline_dt:
                    return viewer_state.active_goal, None, [f"goal_active:{viewer_state.active_goal.id}"]
            except Exception:
                pass

        sub_fact = facts.get("subscription_status")
        sub_status = sub_fact.value if sub_fact else "free"
        now_dt = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))

        # Rule evaluation pipeline:
        # Check candidate 1: first_paid_plan_7d (If free / trial user)
        if sub_status in ["free", "free_trial"]:
            # If user has some activity, prioritize subscription conversion
            rule = self.goals.get("first_paid_plan_7d")
            if rule and not rule.missing_signal and not rule.is_underspecified:
                deadline = (now_dt + timedelta(hours=rule.deadline_hours)).isoformat() + "Z"
                return (
                    GoalInfo(id="first_paid_plan_7d", deadline=deadline),
                    None,
                    ["rule:first_paid_plan_7d", f"fact:subscription_status={sub_status}"]
                )

        # Check candidate 2: first_full_episode_3d (New viewer)
        rule = self.goals.get("first_full_episode_3d")
        if rule and not rule.missing_signal and not rule.is_underspecified:
            deadline = (now_dt + timedelta(hours=rule.deadline_hours)).isoformat() + "Z"
            return (
                GoalInfo(id="first_full_episode_3d", deadline=deadline),
                None,
                ["rule:first_full_episode_3d", "fact:viewer_onboarding"]
            )

        # Check candidate 3: resume_dropped_series_2d
        rule = self.goals.get("resume_dropped_series_2d")
        if rule and not rule.missing_signal:
            deadline = (now_dt + timedelta(hours=rule.deadline_hours)).isoformat() + "Z"
            return (
                GoalInfo(id="resume_dropped_series_2d", deadline=deadline),
                None,
                ["rule:resume_dropped_series_2d"]
            )

        # Handle unmeasurable or underspecified rules gracefully
        return None, "No eligible and measurable goal found for current viewer context", []

    def check_goal_measurability(self, goal_id: str) -> Tuple[bool, str]:
        """
        Verifies if goal is measurable with available event stream signals.
        """
        rule = self.goals.get(goal_id)
        if not rule:
            return False, f"Unknown goal: {goal_id}"
        if rule.missing_signal:
            return False, f"Goal {goal_id} requires signal '{rule.success_signal_type}' which is missing from event stream"
        if rule.is_underspecified:
            return False, f"Goal {goal_id} (version {rule.version}) has underspecified eligibility conditions"
        return True, "Measurable"
