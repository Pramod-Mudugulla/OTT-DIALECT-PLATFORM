"""
Viewer Agent Module.
Represents the dedicated lifecycle agent for one individual viewer.
Owns the viewer's single active plan, history, provenance, verification,
and real-time decision loop.
"""

import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from submission.src.models import (
    TriggerEvent, DecisionOutput, DecisionStatus, ActionType,
    TriggerInfo, GoalInfo, ChecksResult, DialectDecision
)
from submission.src.memory import ViewerMemoryStore
from submission.src.resolver import FactResolver
from submission.src.goal_engine import GoalEngine
from submission.src.verifier import IndependentVerifier
from submission.src.provider import BaseLLMProvider, MockReplayProvider, ModelUnavailableError, BudgetExceededError
from submission.src.data_loader import DataLoader


class ViewerAgent:
    def __init__(
        self,
        viewer_id: str,
        memory_store: ViewerMemoryStore,
        resolver: FactResolver,
        goal_engine: GoalEngine,
        verifier: IndependentVerifier,
        provider: BaseLLMProvider,
        data_loader: DataLoader
    ):
        self.viewer_id = viewer_id
        self.memory_store = memory_store
        self.resolver = resolver
        self.goal_engine = goal_engine
        self.verifier = verifier
        self.provider = provider
        self.data_loader = data_loader

    def process_trigger(
        self,
        trigger: TriggerEvent,
        latest_purchase_event: bool = False
    ) -> DecisionOutput:
        """
        Processes an incoming app-open or lifecycle trigger for this viewer.
        Must complete within latency budget and adhere to call budgets.
        """
        start_time = time.perf_counter()
        self.provider.reset_call_budget()

        # Retrieve or initialize durable viewer state
        profile_snapshot = self.data_loader.get_profile(self.viewer_id)
        state = self.memory_store.get_or_create(self.viewer_id, profile_snapshot)

        # 1. Idempotency Check (Duplicate trigger check)
        is_duplicate = self.memory_store.is_trigger_processed(trigger.event_id)
        if is_duplicate:
            # Idempotently return an abstention / duplicate acknowledgement
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return DecisionOutput(
                decision_id=f"D-DUP-{trigger.event_id}",
                viewer_id=self.viewer_id,
                trigger=TriggerInfo(
                    event=trigger.event_type,
                    received_at=trigger.received_at,
                    event_age_s=trigger.event_age_s
                ),
                goal=state.active_goal,
                action=ActionType.DO_NOTHING,
                dialect=DialectDecision(used="d1", source="idempotent_cache", conflicts=[]),
                content=[],
                confidence=1.0,
                confidence_reason="Duplicate trigger detected. Idempotent response returned.",
                evidence=[f"duplicate_event:{trigger.event_id}"],
                assumptions=["Trigger was already received and processed previously"],
                checks=ChecksResult(passed=[], failed=["idempotency_duplicate_trigger"]),
                decided_in_ms=elapsed_ms,
                status=DecisionStatus.ABSTAINED,
                reason_for_no_action="Duplicate trigger detected; skipping redundant execution"
            )

        # Mark trigger processed in memory
        self.memory_store.mark_trigger_processed(trigger.event_id)

        # 2. Fact Assembly & Conflict Resolution
        facts, dialect_decision, assumptions = self.resolver.assemble_and_resolve(
            trigger=trigger,
            viewer_state=state,
            latest_purchase_event=latest_purchase_event
        )

        for fact in facts.values():
            self.memory_store.record_fact(self.viewer_id, fact)

        # 3. Dynamic Plan Revision on Purchase Event
        if latest_purchase_event or trigger.event_type == "purchase":
            if state.active_goal and state.active_goal.id == "first_paid_plan_7d":
                state.active_goal = None
                state.active_plan = None
                assumptions.append("Purchase event arrived; completed previous conversion goal and revised plan")

        # 4. Goal Evaluation
        goal_info, no_goal_reason, goal_evidence = self.goal_engine.select_goal(
            viewer_state=state,
            facts=facts,
            current_time_iso=trigger.received_at
        )

        # 5. Content Retrieval within Active Dialect
        self.provider.record_tool_call()
        candidate_titles = self.data_loader.get_titles_for_dialect(
            dialect=dialect_decision.used,
            available_only=True
        )
        candidate_tids = [t.title_id for t in candidate_titles]

        # 6. Planning & Decision Step (with provider failure / budget handling)
        local_hour = trigger.payload.get("device_hour_local", 14)
        planning_context = {
            "viewer_id": self.viewer_id,
            "is_holdout": state.is_holdout,
            "facts": {k: v.model_dump() for k, v in facts.items()},
            "candidate_titles": candidate_tids,
            "active_goal": goal_info.model_dump() if goal_info else None,
            "device_hour_local": local_hour,
            "dialect": dialect_decision.used
        }

        fallback_triggered = False
        fallback_reason = None
        raw_plan = {}

        try:
            raw_plan = self.provider.plan_intervention(planning_context)
        except (ModelUnavailableError, BudgetExceededError, Exception) as exc:
            # Fallback gracefully to safe action when model/tool fails
            fallback_triggered = True
            fallback_reason = f"Provider failure ({str(exc)}). Safe fallback activated."
            raw_plan = {
                "action": ActionType.DO_NOTHING.value,
                "content": [],
                "confidence": 0.5,
                "confidence_reason": f"Fallback to safe abstention due to provider failure: {str(exc)}",
                "evidence": ["system:fallback"],
                "reason_for_no_action": fallback_reason
            }

        planned_action = ActionType(raw_plan.get("action", ActionType.DO_NOTHING.value))
        planned_content = raw_plan.get("content", [])

        # 7. Independent Verification Step (Completely separate from planner!)
        verification_result = self.verifier.verify(
            viewer_state=state,
            action=planned_action,
            dialect=dialect_decision.used,
            content_ids=planned_content,
            device_hour_local=local_hour,
            trigger_received_at=trigger.received_at,
            is_duplicate=False
        )

        final_action = planned_action
        final_content = planned_content
        decision_status = DecisionStatus.PUBLISHED
        reason_no_action = raw_plan.get("reason_for_no_action")

        # If verification failed, fall back to safe action
        if verification_result.failed:
            if planned_action in [ActionType.PUSH_NOTIFICATION, ActionType.WHATSAPP]:
                # Channel failure (e.g. quiet hours, consent, frequency cap) -> fall back to HOME_PAGE or DO_NOTHING
                if len(candidate_tids) >= 3:
                    final_action = ActionType.HOME_PAGE
                    final_content = [f"title:{t}" for t in candidate_tids[:3]]
                    decision_status = DecisionStatus.FALLBACK
                    reason_no_action = None
                    verification_result.passed.append("fallback_home_page_applied")
                else:
                    final_action = ActionType.DO_NOTHING
                    final_content = []
                    decision_status = DecisionStatus.REJECTED
                    reason_no_action = f"Verifier blocked messaging action: {', '.join(verification_result.failed)}"
            else:
                final_action = ActionType.DO_NOTHING
                final_content = []
                decision_status = DecisionStatus.REJECTED
                reason_no_action = f"Verifier blocked action: {', '.join(verification_result.failed)}"

        if final_action == ActionType.DO_NOTHING and decision_status != DecisionStatus.REJECTED:
            decision_status = DecisionStatus.ABSTAINED

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        decision_id = f"D-{uuid.uuid4().hex[:6].upper()}"

        # Combine evidence references
        evidence_list = [f"event:{trigger.event_id}"] + goal_evidence
        for c in final_content:
            evidence_list.append(f"catalogue:{c.replace('title:', '')}")
        if dialect_decision.source:
            evidence_list.append(f"source:{dialect_decision.source}")

        decision = DecisionOutput(
            decision_id=decision_id,
            viewer_id=self.viewer_id,
            trigger=TriggerInfo(
                event=trigger.event_type,
                received_at=trigger.received_at,
                event_age_s=trigger.event_age_s
            ),
            goal=goal_info,
            action=final_action,
            dialect=dialect_decision,
            content=final_content,
            confidence=raw_plan.get("confidence", 0.70),
            confidence_reason=raw_plan.get("confidence_reason", "Action chosen based on active goal and viewer dialect."),
            evidence=evidence_list,
            assumptions=assumptions,
            checks=verification_result,
            decided_in_ms=elapsed_ms,
            status=decision_status,
            reason_for_no_action=reason_no_action
        )

        # Record decision and durable action execution in memory
        self.memory_store.record_decision(self.viewer_id, decision)

        if final_action != ActionType.DO_NOTHING:
            self.memory_store.record_action_execution(
                self.viewer_id,
                {
                    "action_id": f"ACT-{uuid.uuid4().hex[:6]}",
                    "decision_id": decision_id,
                    "action_type": final_action.value,
                    "dialect": dialect_decision.used,
                    "content": final_content,
                    "executed_at": trigger.received_at
                }
            )

        return decision
