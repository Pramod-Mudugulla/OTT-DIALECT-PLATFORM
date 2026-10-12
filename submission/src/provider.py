"""
Model Provider Abstraction and Mock/Replay Mode.
Enforces call budgets (max 8 model calls, 20 tool calls), handles model failures,
and provides mock/replay reasoning so evaluators can run without an external API key.
"""

import time
from typing import Dict, Any, List, Optional
from submission.src.models import ActionType


class BudgetExceededError(Exception):
    pass


class ModelUnavailableError(Exception):
    pass


class BaseLLMProvider:
    def __init__(self, max_model_calls: int = 8, max_tool_calls: int = 20):
        self.max_model_calls = max_model_calls
        self.max_tool_calls = max_tool_calls
        self.model_calls_count = 0
        self.tool_calls_count = 0

    def reset_call_budget(self):
        self.model_calls_count = 0
        self.tool_calls_count = 0

    def record_tool_call(self):
        self.tool_calls_count += 1
        if self.tool_calls_count > self.max_tool_calls:
            raise BudgetExceededError(f"Exceeded max tool call budget of {self.max_tool_calls}")

    def plan_intervention(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class MockReplayProvider(BaseLLMProvider):
    """
    Mock/Replay provider that emulates intelligent goal-directed decision making
    without requiring external API keys. Supports injecting simulated failures.
    """
    def __init__(self, simulate_failure: bool = False, max_model_calls: int = 8, max_tool_calls: int = 20):
        super().__init__(max_model_calls, max_tool_calls)
        self.simulate_failure = simulate_failure

    def plan_intervention(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self.model_calls_count += 1
        if self.model_calls_count > self.max_model_calls:
            raise BudgetExceededError(f"Exceeded max model call budget of {self.max_model_calls}")

        if self.simulate_failure:
            raise ModelUnavailableError("Simulated LLM service timeout (503 Service Unavailable)")

        # Extract context
        is_holdout = context.get("is_holdout", False)
        facts = context.get("facts", {})
        candidate_titles = context.get("candidate_titles", [])
        active_goal = context.get("active_goal")
        hour_local = context.get("device_hour_local", 14)

        # If user is in randomized holdout control group -> MUST ABSTAIN (DO_NOTHING)
        if is_holdout:
            return {
                "action": ActionType.DO_NOTHING.value,
                "content": [],
                "confidence": 1.0,
                "confidence_reason": "Viewer is in randomized holdout control group for measurement.",
                "evidence": ["holdout:control_group"],
                "reason_for_no_action": "Randomized holdout viewer assigned to control group"
            }

        # If it's night time (22:00 - 08:00) -> do not send messages, use home page or do nothing
        if hour_local >= 22 or hour_local < 8:
            # Home page intervention
            selected = [f"title:{t}" for t in candidate_titles[:4]] if len(candidate_titles) >= 3 else []
            if len(selected) >= 3:
                return {
                    "action": ActionType.HOME_PAGE.value,
                    "content": selected,
                    "confidence": 0.82,
                    "confidence_reason": "App opened during quiet hours; curated non-intrusive home page row.",
                    "evidence": ["time:quiet_hours", f"goal:{active_goal.get('id') if active_goal else 'general'}"],
                    "reason_for_no_action": None
                }
            return {
                "action": ActionType.DO_NOTHING.value,
                "content": [],
                "confidence": 0.9,
                "confidence_reason": "Quiet hours active and insufficient catalog titles for home row.",
                "evidence": ["time:quiet_hours"],
                "reason_for_no_action": "Quiet hours in effect"
            }

        # Active goal specific decision
        goal_id = active_goal.get("id") if active_goal else None

        if goal_id == "first_full_episode_3d":
            # Recommend top 3 curated titles in viewer dialect
            selected = [f"title:{t}" for t in candidate_titles[:3]]
            if len(selected) >= 3:
                return {
                    "action": ActionType.HOME_PAGE.value,
                    "content": selected,
                    "confidence": 0.78,
                    "confidence_reason": "Viewer has not completed first episode; displaying top onboarding row in active dialect.",
                    "evidence": ["event:app_open", f"goal:{goal_id}"],
                    "reason_for_no_action": None
                }

        elif goal_id == "first_paid_plan_7d":
            # Check consent for push / whatsapp
            push_consent = facts.get("push_consent", {}).get("value", False)
            if push_consent:
                return {
                    "action": ActionType.PUSH_NOTIFICATION.value,
                    "content": ["template:push_offer"],
                    "confidence": 0.71,
                    "confidence_reason": "Trial viewer eligible for conversion discount during daytime session.",
                    "evidence": ["fact:subscription_status=free_trial", "fact:push_consent=true"],
                    "reason_for_no_action": None
                }
            else:
                selected = [f"title:{t}" for t in candidate_titles[:3]]
                return {
                    "action": ActionType.HOME_PAGE.value,
                    "content": selected,
                    "confidence": 0.65,
                    "confidence_reason": "No push consent; showing premium showcase on home page instead.",
                    "evidence": ["fact:push_consent=false", f"goal:{goal_id}"],
                    "reason_for_no_action": None
                }

        # Default home page if candidate titles available
        selected = [f"title:{t}" for t in candidate_titles[:3]]
        if len(selected) >= 3:
            return {
                "action": ActionType.HOME_PAGE.value,
                "content": selected,
                "confidence": 0.60,
                "confidence_reason": "Displaying tailored regional dialect content row.",
                "evidence": ["event:app_open"],
                "reason_for_no_action": None
            }

        return {
            "action": ActionType.DO_NOTHING.value,
            "content": [],
            "confidence": 0.85,
            "confidence_reason": "Insufficient evidence or content to justify an intervention.",
            "evidence": ["evidence:sparse"],
            "reason_for_no_action": "Insufficient evidence for targeted intervention"
        }
