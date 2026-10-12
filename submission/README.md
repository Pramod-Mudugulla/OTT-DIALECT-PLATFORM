# One User, One Agent: Regional Dialect OTT Lifecycle System

> **Hiring Challenge Submission:** Senior AI Engineer / Applied LLM Engineer  
> **Core Signal:** Goal-directed lifecycle decisions, strict evidence provenance, independent safety verification, and honest causal measurement.

---

## 1. Quick Start

### Installation
Ensure Python 3.10+ is installed. Clone the repository and install requirements:
```bash
pip install -r requirements.txt
```

### Run the Replay (Single Command)
Execute the complete replay stream across 300 triggers and generate all audit artifacts:
```bash
python run_replay.py
```
*or via module execution:*
```bash
python -m submission.src.cli
```

### Run Automated Tests
Run the full test suite (14 automated tests covering late triggers, duplicate deduplication, 3-way conflict resolution, provider failures, corrected goal rules, quiet hours, consent, frequency caps, prompt injection, and causal holdout impact):
```bash
pytest submission/tests -v
```

---

## 2. Repository Layout

```
submission/
├── README.md                 # Setup guide, system walkthrough & interview Q&A
├── ARCHITECTURE.md           # In-depth architectural note on 7 core pillars
├── AI_COLLABORATION.md       # AI assistant usage log and rejected suggestions
├── KNOWN_LIMITATIONS.md      # Intentional architectural trade-offs & future scope
├── src/
│   ├── models.py             # Pydantic data schemas (DecisionOutput, Facts, Goals)
│   ├── data_loader.py        # Catalog, profile, and replay stream loader
│   ├── memory.py             # Durable per-viewer state store (persisted to disk)
│   ├── resolver.py           # Precedence rules, freshness calculation & conflict resolution
│   ├── goal_engine.py        # 12 candidate goals, rule versioning & mid-replay corrections
│   ├── verifier.py           # Independent verification step (quiet hours, consent, injection defense)
│   ├── provider.py           # Model abstraction & MockReplayProvider (zero API key barrier)
│   ├── agent.py              # Dedicated per-viewer lifecycle agent
│   ├── outcome_judge.py      # Attributable telemetry measurement loop
│   ├── impact_analyzer.py    # Randomized holdout vs selection bias analyzer
│   ├── synthetic_generator.py# Deterministic generator for catalogues and replay streams
│   └── cli.py                # Command-line interface and replay runner
├── tests/
│   ├── test_duplicate_and_late.py
│   ├── test_conflicting_sources.py
│   ├── test_failure_fallback.py
│   ├── test_corrected_goal_rule.py
│   ├── test_verification_safety.py
│   └── test_impact_holdout.py
└── sample_run/
    ├── decisions.jsonl       # Required machine-readable decision records (Section 4)
    ├── viewer_state/         # Durable per-viewer JSON state files
    ├── actions.jsonl         # Published action logs
    ├── outcomes.jsonl        # Attributed outcome judgments
    ├── latency_report.json   # p50, p95, p99 latency benchmark report
    ├── impact_report.md      # Causal lift vs. selection bias report
    └── final_report.md       # Summary report of replay execution
```

---

## 3. Walkthrough of a Viewer Decision

Every decision adheres strictly to the **Section 4 JSON Schema** specified in the brief:

```json
{
  "decision_id": "D-A705B1",
  "viewer_id": "V-0015",
  "trigger": {
    "event": "app_open",
    "received_at": "2026-09-12T10:05:01Z",
    "event_age_s": 1.0
  },
  "goal": {
    "id": "first_paid_plan_7d",
    "deadline": "2026-09-19T10:05:01+00:00Z"
  },
  "action": "HOME_PAGE",
  "dialect": {
    "used": "d3",
    "source": "app_setting",
    "conflicts": ["profile:d1", "campaign:d2"]
  },
  "content": ["title:T0001", "title:T0004", "title:T0010"],
  "confidence": 0.71,
  "confidence_reason": "Trial viewer eligible for conversion discount during daytime session.",
  "evidence": [
    "event:E-SURPRISE-01",
    "rule:first_paid_plan_7d",
    "fact:subscription_status=free_trial",
    "catalogue:T0001",
    "catalogue:T0004",
    "catalogue:T0010",
    "source:app_setting"
  ],
  "assumptions": [],
  "checks": {
    "passed": ["idempotency", "quiet_hours", "push_consent", "fallback_home_page_applied"],
    "failed": ["frequency_cap_exceeded"]
  },
  "decided_in_ms": 4,
  "status": "FALLBACK",
  "reason_for_no_action": null
}
```

### Key Highlights of the Decision:
1. **Tri-Dialect Conflict Resolution:** The trigger arrived with `app_dialect = d3`, `profile_dialect = d1`, and `campaign_dialect = d2`. The resolver prioritized `app_setting` (what the user actually sees on their device) while explicitly recording `conflicts: ["profile:d1", "campaign:d2"]`.
2. **Independent Verification & Graceful Fallback:** The planner initially wanted to send a promotional push notification. However, the verifier detected that the viewer had already received a communication today (`frequency_cap_exceeded`). Instead of crashing or spamming the viewer, it safely fell back to a non-intrusive `HOME_PAGE` showcase.

---

## 4. Technical Discussion Q&A (Interview Preparation)

### Q1: How does your agent decide that what it knows about a viewer is current enough to act on?
**Answer:**  
Every fact in the viewer's memory carries strict metadata: its originating `source`, its `recorded_at` timestamp, and a calculated `freshness_s = max(0, trigger.received_at - recorded_at)`.
When an event arrives from an offline buffer (e.g. phone offline for 4 days), its `event_age_s` exceeds 24 hours. The agent flags an explicit assumption in the decision trace: `"Trigger was buffered offline for 97.9 hours"`. Because the context is stale, the agent refrains from real-time messaging alerts and only serves passive home-page rows or chooses `DO_NOTHING`.

### Q2: When should the agent do nothing, and how do you know that was the right call?
**Answer:**  
`DO_NOTHING` is treated as a first-class valid action rather than an error. The agent abstains when:
1. The viewer belongs to the **Randomized Holdout Control Group** (`is_holdout = True`).
2. Candidate goals lack measurable signals (e.g. `social_share_referral_3d` has no event stream telemetry).
3. The catalog in the viewer's active dialect has fewer than 3 available titles (violating UI rendering rules).
4. Safety checks fail and no safe fallback action exists.
We verify this was the right call by logging an explicit `reason_for_no_action` and auditing whether unserved viewers avoid unintended notification fatigue or broken UI layouts.

### Q3: How would you show that the agent caused a change rather than selecting viewers who were already likely to convert?
**Answer:**  
By comparing against the **Randomized Holdout (Control Group)**, rather than comparing against "everyone else".
Viewers who trigger app opens and pass eligibility checks already have high intent to watch. A naive comparison between served viewers and dormant unserved viewers creates an inflated selection bias. By withholding interventions from a random 10% slice of eligible viewers, both treated and control groups have identical arrival timing and baseline intent. Any difference in goal completion is the true **Average Treatment Effect (ATE)**.

### Q4: What happens when 1,000 viewers open the app in the same minute?
**Answer:**  
1. **Idempotence & Deduplication:** Duplicate triggers are filtered in constant time via the event cache.
2. **Strict Call & Latency Budgets:** Each decision executes within a tight budget (max 8 model calls, 20 tool calls, ~2–5ms in mock replay).
3. **Partitioned Concurrency:** Each viewer agent owns only its own state (`V-xxxx`), allowing horizontal sharding across viewer IDs with zero cross-viewer locks.

### Q5: Which decisions should never be automated?
**Answer:**  
1. **Policy & Consent Overrides:** An agent must never be permitted to bypass user opt-out or quiet hours based on "high model confidence".
2. **Monetary Commitments / Debits:** Billing deductions, subscription cancellations, or refunds must be verified by transactional payment gateways, not generative models.
3. **Content Catalog Censorship:** Automated suppression of titles based on subjective LLM opinions should be subject to human editorial review.

### Q6: How would the system work for 10 million viewers and 40 dialects?
**Answer:**  
- **Storage:** Per-viewer state stored in a key-value or document store (e.g., DynamoDB / Cassandra / Redis cluster) keyed by `viewer_id`.
- **Event Bus:** Kafka or Apache Pulsar partitioned by `hash(viewer_id)` to preserve per-viewer event ordering.
- **Dialect Catalog Cache:** Catalog metadata cached in Redis read replicas per dialect with fast set lookups (`SINTER dialect:d3 available:true`).
- **Distributed Agent Runtime:** Ray or Temporal actor per active viewer session.

### Q7: What did an AI coding assistant suggest that you chose not to accept?
**Answer:**  
1. **Rejected a Single Monolithic Prompt:** An AI assistant originally suggested sending all viewer history, catalog titles, and rules into one large prompt for the LLM to decide everything. We rejected this because it violates the latency budget, cannot guarantee policy enforcement, and risks prompt injection.
2. **Rejected Naive Uplift Reporting:** The assistant initially calculated uplift by subtracting average unserved viewer conversion from served viewer conversion. We rejected this because it introduces severe selection bias, replacing it with randomized holdout A/B measurement.
3. **Rejected Blind Trust in Generated Approvals:** The assistant suggested having the LLM output `checks_passed: true`. We strictly separated the verification step into an independent, deterministic policy engine.
