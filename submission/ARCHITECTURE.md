# System Architecture Note: One User, One Agent

This document outlines the architectural principles, component topology, trust boundaries, and operational guarantees of the **One User, One Agent** OTT Lifecycle Management System.

---

## 1. Core Architectural Topology

```
                       +----------------------------------+
                       | Incoming Trigger / Event Stream  |
                       +-----------------+----------------+
                                         |
                                         v
                       +----------------------------------+
                       | Idempotency & Deduplication Gate |
                       +-----------------+----------------+
                                         |
                                         v
                       +----------------------------------+
                       | Fact Assembly & Provenance Engine| <--- [Warehouse Profiles Snapshot]
                       |      (Precedence & Freshness)    | <--- [Real-time Purchase Stream]
                       +-----------------+----------------+
                                         |
                                         v
                       +----------------------------------+
                       | Dynamic Goal Engine & Revision   | <--- [12 Candidate Goals]
                       +-----------------+----------------+
                                         |
                                         v
                       +----------------------------------+
                       | LLM Planner / Model Provider     | <--- [Dialect Filtered Catalog]
                       | (Strict Budget: 8 calls, 20 tools)|
                       +-----------------+----------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| TRUST BOUNDARY: Independent Deterministic Verifier                                |
|  - Quiet Hours (22:00-08:00 Local)     - Dialect & Catalog Availability           |
|  - Consent Enforcement (Push/WA)       - Home-Page Row Minimum (>=3 Titles)       |
|  - Frequency Capping (1 msg/day)       - Prompt Injection Neutralization          |
+----------------------------------------+------------------------------------------+
                                         |
                +------------------------+------------------------+
                |                                                 |
         [Checks Passed]                                   [Checks Failed]
                |                                                 |
                v                                                 v
   +-------------------------+                       +-------------------------+
   |   Publish Action        |                       | Safe Fallback / Abstain |
   |  (STATUS: PUBLISHED)    |                       | (FALLBACK / ABSTAINED)  |
   +------------+------------+                       +------------+------------+
                |                                                 |
                +------------------------+------------------------+
                                         |
                                         v
                       +----------------------------------+
                       | Durable Viewer State & Audit Log |
                       +-----------------+----------------+
                                         |
                                         v
                       +----------------------------------+
                       | Outcome Judge & Attribution Loop |
                       |  (Attributable Signals & Holdout)|
                       +----------------------------------+
```

---

## 2. The Seven Architectural Pillars

### 1. Ownership: One Agent per Viewer
- Every viewer is assigned a single, dedicated lifecycle manager (`ViewerAgent`).
- **No Concurrency Conflicts:** No two components or background workers can pursue conflicting goals for the same viewer simultaneously.
- The agent maintains sole ownership of:
  - The viewer's single active goal and active plan.
  - The viewer's cumulative decision history and execution timestamps.
  - What has been learned from past interventions.

### 2. Planning: Event-Driven Revision vs. Fixed Schedules
- The agent does not re-plan on arbitrary clock schedules.
- Planning is purely event-driven:
  - When the viewer triggers an `app_open`, the agent assesses whether the current active goal remains valid.
  - If a key life-cycle milestone occurs (e.g. a `purchase` event arrives), any previous acquisition goal (e.g., `first_paid_plan_7d`) is immediately closed, and the agent revisions its plan towards content engagement or series completion.

### 3. Memory & Provenance: Never Let the Largest or Newest Blindly Win
- All facts are stored with full provenance:
  - `key`, `value`, `source` (`app_setting`, `profile_snapshot`, `event_stream`, `campaign_link`), `recorded_at`, and calculated `freshness_s`.
- **Precedence Rules:**
  - **Dialect Precedence:** `app_setting` (UI state right now) > `profile_snapshot` (warehouse preference) > `campaign_link` (ad referral). If conflicts exist, they are explicitly logged in `conflicts: [...]`.
  - **Subscription Precedence:** Real-time event stream purchases strictly supersede 1-day stale warehouse profile exports.
  - **Offline Buffering:** If `event_age_s > 86400`, the fact is flagged as stale; the agent records an assumption and suppresses push messaging.

### 4. Trust Boundaries & Independent Verification
- **Principle of Mistrust:** Generative model output is treated as untrusted intent, never as authorization or proof.
- The `IndependentVerifier` operates independently of the decision-making model:
  - **Quiet Hours:** Messages blocked between 22:00 and 08:00 in the viewer's local timezone.
  - **Consent:** Push notifications and WhatsApp messages require explicit consent flags from user profile settings.
  - **Frequency Cap:** Enforces a hard limit of at most 1 outbound message per viewer every 24 hours.
  - **Home-Page Rendering Invariant:** Rows must contain at least 3 valid, available titles in the active dialect.
  - **Adversarial Injection Defense:** Content catalog descriptions are scanned; injected system instructions are intercepted and stripped before affecting agent decisions.

### 5. Latency & Budget Enforcement
- **Latency Budget:** Each decision must be published within 60 seconds (with fail threshold at 5 minutes). In our implementation, p95 decision latency is <5ms.
- **Call Budget:** Hard limit of max 8 model calls and 20 tool calls per decision. If budgets are breached, execution halts immediately and invokes safe fallback.

### 6. Failure Recovery & Graceful Degradation
- **Network / Model Unavailable:** If the provider throws an exception (e.g., 503 HTTP error or timeout), the system catches the error and falls back to a deterministic safe action (`HOME_PAGE` with top regional titles) or `DO_NOTHING`, tagging `status = FALLBACK`.
- **Idempotent Deduplication:** Repeated triggers with identical event IDs return cached responses without executing redundant tool calls or message dispatches.

### 7. Measurement & Honest Impact
- **Attributable Telemetry:** Outcomes are credited only if the success signal matches the active goal deadline and user exposure.
- **Causal Holdout Comparison:** The system reserves a 10% randomized holdout control group (`is_holdout = True`). The true treatment effect is calculated strictly against this holdout, avoiding the selection bias inherent in naive "served vs. unserved" comparisons.
