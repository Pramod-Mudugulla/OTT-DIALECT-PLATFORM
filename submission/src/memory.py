"""
Durable Memory Store for One User, One Agent System.
Maintains per-viewer durable state: facts with provenance, decisions, actions,
outcomes, and learned insights. Persists to disk for auditability.
"""

import os
import json
from typing import Dict, Optional, Any
from submission.src.models import ViewerState, ViewerFact, DecisionOutput, OutcomeJudgment


class ViewerMemoryStore:
    def __init__(self, storage_dir: str = "submission/sample_run/viewer_state"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self._cache: Dict[str, ViewerState] = {}
        self._processed_triggers: set = set()

    def _file_path(self, viewer_id: str) -> str:
        safe_id = viewer_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self.storage_dir, f"{safe_id}.json")

    def get_or_create(self, viewer_id: str, profile_snapshot: Optional[dict] = None) -> ViewerState:
        if viewer_id in self._cache:
            return self._cache[viewer_id]

        file_path = self._file_path(viewer_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    state = ViewerState(**data)
                    self._cache[viewer_id] = state
                    return state
            except Exception:
                pass

        # Create new viewer state
        is_holdout = False
        if profile_snapshot:
            is_holdout = profile_snapshot.get("is_holdout", False)

        new_state = ViewerState(
            viewer_id=viewer_id,
            is_holdout=is_holdout,
            profile_snapshot=profile_snapshot or {}
        )
        self._cache[viewer_id] = new_state
        self.save(new_state)
        return new_state

    def save(self, state: ViewerState):
        self._cache[state.viewer_id] = state
        file_path = self._file_path(state.viewer_id)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(state.model_dump_json(indent=2))

    def is_trigger_processed(self, event_id: str) -> bool:
        return event_id in self._processed_triggers

    def mark_trigger_processed(self, event_id: str):
        self._processed_triggers.add(event_id)

    def record_fact(self, viewer_id: str, fact: ViewerFact):
        state = self.get_or_create(viewer_id)
        state.known_facts[fact.key] = fact
        self.save(state)

    def record_decision(self, viewer_id: str, decision: DecisionOutput):
        state = self.get_or_create(viewer_id)
        state.history_decisions.append(decision.decision_id)
        if decision.goal:
            state.active_goal = decision.goal
        state.active_plan = f"{decision.action.value} on {decision.dialect.used}"
        self.save(state)

    def record_action_execution(self, viewer_id: str, action_data: Dict[str, Any]):
        state = self.get_or_create(viewer_id)
        state.history_actions.append(action_data)
        if action_data.get("action_type") in ["PUSH_NOTIFICATION", "WHATSAPP", "IN_APP_MESSAGE"]:
            state.last_message_sent_at = action_data.get("executed_at")
        self.save(state)

    def record_outcome(self, viewer_id: str, outcome: OutcomeJudgment):
        state = self.get_or_create(viewer_id)
        state.history_outcomes.append(outcome.model_dump())
        if outcome.learning_added:
            state.learnings.append(outcome.learning_added)
        # Clear active goal if resolved
        if outcome.status in ["SUCCEEDED", "FAILED"]:
            state.active_goal = None
            state.active_plan = None
        self.save(state)

    def get_all_cached_states(self) -> Dict[str, ViewerState]:
        return self._cache
