"""
Independent Verification Engine.
Validates planned decisions against policy rules, quiet hours, consent, frequency caps,
dialect availability, home-row minimums, and prompt injection attacks.
The verifier runs INDEPENDENTLY of the decision-making model or planner.
"""

from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
from submission.src.models import ActionType, DecisionOutput, ViewerState, CatalogueTitle, ChecksResult
from submission.src.data_loader import DataLoader


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



class IndependentVerifier:
    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader

    def verify(
        self,
        viewer_state: ViewerState,
        action: ActionType,
        dialect: str,
        content_ids: List[str],
        device_hour_local: Optional[int],
        trigger_received_at: str,
        is_duplicate: bool = False
    ) -> ChecksResult:
        """
        Executes strict independent policy and safety checks.
        Returns ChecksResult with passed and failed check names.
        """
        passed: List[str] = []
        failed: List[str] = []

        # 1. Idempotency / Duplicate Check
        if is_duplicate:
            failed.append("idempotency_duplicate_trigger")
        else:
            passed.append("idempotency")

        # 2. Holdout Check (Control Group Protection)
        if viewer_state.is_holdout:
            if action != ActionType.DO_NOTHING:
                failed.append("randomized_holdout_protection")
            else:
                passed.append("randomized_holdout_protection")

        # 3. Messaging Channel Specific Checks (Quiet Hours, Consent, Frequency Cap)
        if action in [ActionType.PUSH_NOTIFICATION, ActionType.WHATSAPP]:
            # a) Quiet hours check (22:00 - 08:00 local time)
            hour = device_hour_local if device_hour_local is not None else 12
            if hour >= 22 or hour < 8:
                failed.append("quiet_hours_violation")
            else:
                passed.append("quiet_hours")

            # b) Consent check
            profile = viewer_state.profile_snapshot or {}
            if action == ActionType.PUSH_NOTIFICATION:
                if not profile.get("push_consent", False):
                    failed.append("missing_push_consent")
                else:
                    passed.append("push_consent")
            elif action == ActionType.WHATSAPP:
                if not profile.get("whatsapp_consent", False):
                    failed.append("missing_whatsapp_consent")
                else:
                    passed.append("whatsapp_consent")

            # c) Frequency cap (at most 1 message per viewer per day)
            last_sent = viewer_state.last_message_sent_at
            if last_sent:
                now_dt = parse_iso_time(trigger_received_at)
                last_dt = parse_iso_time(last_sent)
                hours_since = (now_dt - last_dt).total_seconds() / 3600.0
                if hours_since < 24.0:
                    failed.append("frequency_cap_exceeded")
                else:
                    passed.append("frequency_cap")
            else:
                passed.append("frequency_cap")

        # 4. Dialect & Catalogue Availability Verification
        if action == ActionType.HOME_PAGE:
            valid_dialect_titles: List[str] = []
            for item in content_ids:
                tid = item.replace("title:", "")
                title_obj = self.data_loader.titles.get(tid)
                if not title_obj:
                    failed.append(f"title_not_found:{tid}")
                    continue
                if not title_obj.is_available:
                    failed.append(f"title_unavailable:{tid}")
                    continue
                if dialect not in title_obj.dialects:
                    failed.append(f"dialect_mismatch:{tid}_needs_{dialect}")
                    continue
                
                # Check for adversarial prompt injection in catalogue description
                if "Ignore" in title_obj.description and "instruction" in title_obj.description.lower():
                    failed.append("prompt_injection_detected_in_content")
                    continue

                valid_dialect_titles.append(tid)

            # Home page row minimum requirement: >= 3 titles required!
            if len(valid_dialect_titles) < 3:
                failed.append("home_row_minimum_titles_unmet")
            else:
                passed.append("home_row_minimum_titles")
                passed.append("dialect_match")
                passed.append("catalogue_availability")

        # 5. DO_NOTHING is always a valid safe action
        if action == ActionType.DO_NOTHING:
            passed.append("safe_abstention")

        return ChecksResult(passed=passed, failed=failed)
