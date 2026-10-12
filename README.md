# OTT Dialect Platform: One User, One Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-14%2F14%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Agentic AI Engineering Challenge:** Build an agent that owns one viewer’s next step: choosing a measurable goal, acting in real-time on limited and conflicting evidence, and honestly measuring attributable impact against a randomized holdout.

---

## 🌟 Executive Summary

In regional-dialect OTT platforms streaming films, shows, and micro-dramas in smaller towns and cities, visits are often short: viewers open the app, scroll, and bounce. Many new viewers never finish their first episode, and trial viewers rarely convert without tailored engagement.

This project implements the **One User, One Agent** architecture:
- **Dedicated Ownership:** Every viewer has exactly **one dedicated agent** that owns their current goal, active plan, complete decision history, and learned preferences.
- **Evidence Provenance & Conflict Resolution:** Facts maintain explicit source, timestamp, and freshness. When signals conflict (e.g. `app_setting` vs `profile_snapshot` vs `campaign_link`), the agent applies strict precedence rules and logs conflicts.
- **Independent Verification:** A deterministic verification layer intercepts decisions *before execution*, independently enforcing quiet hours (22:00–08:00), consent, daily frequency caps, dialect availability, and prompt injection defense.
- **Honest Causal Measurement:** Measures impact against a **10% randomized holdout (control group)**, proving the true Average Treatment Effect (ATE) and demonstrating why naive "served vs unserved" comparisons suffer from severe selection bias.

---

## 🚀 Quick Start

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/Pramod-Mudugulla/OTT-DIALECT-PLATFORM.git
cd OTT-DIALECT-PLATFORM
pip install -r requirements.txt
```

### 2. Run the Full Replay Simulation (One Command)
Run the agent system across 300 triggers and generate all audit reports:
```bash
python run_replay.py
```
*or via module execution:*
```bash
python -m submission.src.cli
```

### 3. Run the Automated Test Suite
Run all 14 unit and integration tests:
```bash
pytest submission/tests -v
```

---

## 🏗️ Architecture & Decision Pipeline

```
                                  [ Incoming App Trigger ]
                                             │
                                             ▼
                             [ Idempotency & Deduplication Gate ]
                                             │
                                             ▼
                             [ Fact Assembly & Provenance ]
                             (Precedence & Freshness Engine)
                                             │
                                             ▼
                             [ Dynamic Goal Selection & Revision ]
                                             │
                                             ▼
                             [ Model Provider / LLM Planner ]
                             (Enforces budget: <=8 calls, <=20 tools)
                                             │
                                             ▼
                  ┌─────────────────────────────────────────────────────┐
                  │   TRUST BOUNDARY: Independent Deterministic Verifier │
                  │    - Quiet Hours (22:00-08:00 local time)           │
                  │    - Consent Check (Push & WhatsApp)                │
                  │    - Frequency Cap (max 1 message/viewer/day)       │
                  │    - Dialect Match & Catalog Availability           │
                  │    - Home Row Minimum (>=3 titles in dialect)       │
                  │    - Adversarial Prompt Injection Defense           │
                  └──────────────────────────┬──────────────────────────┘
                                             │
                        ┌────────────────────┴────────────────────┐
                        ▼                                         ▼
                 [ Checks Passed ]                         [ Checks Failed ]
                        │                                         │
                        ▼                                         ▼
               [ Publish Action ]                       [ Safe Fallback / Abstain ]
              (STATUS: PUBLISHED)                         (FALLBACK / ABSTAINED)
                        │                                         │
                        └────────────────────┬────────────────────┘
                                             │
                                             ▼
                             [ Durable Viewer State & Memory ]
                             (Persisted per viewer to disk)
                                             │
                                             ▼
                             [ Outcome Judge & Attribution Loop ]
                             (Evaluates vs. 10% Randomized Holdout)
```

---

## 📋 Required Decision Schema (Section 4 Compliance)

Every agent decision produces a machine-readable audit record:

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

---

## 📊 Honest Causal Impact vs. Naive Selection Bias

A major requirement of this challenge is explaining why naive comparisons (Served vs. Everyone Else) mislead:

| Metric | Honest Measurement (Treated vs. Holdout) | Naive Method (Served vs. Everyone Else) | Selection Bias Inflation |
| :--- | :--- | :--- | :--- |
| **Control Group Size** | 496 viewers (Randomized Holdout) | 4,204 viewers (All Unserved) | - |
| **Treated Group Size** | 300 viewers | 300 viewers | - |
| **Baseline Conversion** | **17.94%** | 5.21% | - |
| **Treated Conversion** | **34.67%** | **34.67%** | - |
| **Absolute Uplift** | **+16.73%** | +29.46% | Overstated by +12.73% |
| **Relative Uplift (%)** | **+93.26%** | +565.45% | **Overstated by +472.19%** |

### Why Naive Comparisons Mislead:
1. **Active Intent Bias:** Served viewers are those who actively opened the app and stayed long enough to trigger an evaluation. "Everyone Else" includes churned or dormant users who never logged in.
2. **Holdout Rigor:** Withholding interventions from a random 10% slice of eligible viewers (`is_holdout = True`) creates identical baseline intent between groups. Any observed lift is strictly causal.

---

## 📁 Repository Structure

```
├── README.md                      # Main project documentation (this file)
├── requirements.txt               # Dependencies (pydantic, pytest, rich)
├── pytest.ini                     # Test configuration
├── run_replay.py                  # Top-level one-command runner script
└── submission/
    ├── README.md                  # Submission overview & interview discussion Q&A
    ├── ARCHITECTURE.md            # Deep dive on 7 architectural pillars
    ├── AI_COLLABORATION.md        # AI collaboration log & rejected suggestions
    ├── KNOWN_LIMITATIONS.md       # Scoped trade-offs & production roadmap
    ├── src/                       # Core agent system modules
    │   ├── agent.py               # Dedicated ViewerAgent lifecycle manager
    │   ├── cli.py                 # Replay stream runner & CLI
    │   ├── data_loader.py         # Catalogue, profile, and trigger loader
    │   ├── goal_engine.py         # 12 goals, eligibility, & dynamic rule updates
    │   ├── impact_analyzer.py     # Causal holdout measurement & report generator
    │   ├── memory.py              # Durable per-viewer state store
    │   ├── models.py              # Pydantic data schemas
    │   ├── outcome_judge.py       # Attributable telemetry evaluation loop
    │   ├── provider.py            # Model abstraction & MockReplayProvider
    │   ├── resolver.py            # Precedence rules & conflict resolution
    │   ├── synthetic_generator.py # Deterministic data generator with edge cases
    │   └── verifier.py            # Independent safety & policy verification engine
    ├── tests/                     # 14 automated pytest test cases
    └── sample_run/                # Output artifacts from 300-event replay
        ├── decisions.jsonl        # Output decisions
        ├── actions.jsonl          # Published actions
        ├── outcomes.jsonl         # Judged outcomes
        ├── latency_report.json    # Latency benchmarks (p50, p95, p99)
        ├── impact_report.md       # Causal holdout impact analysis
        ├── final_report.md        # Execution summary
        └── viewer_state/          # Durable per-viewer JSON states
```

---

## 🧪 Test Coverage (14/14 Tests Passed)

```bash
$ pytest submission/tests -v
============================= test session starts =============================
submission/tests/test_conflicting_sources.py::test_three_way_dialect_conflict PASSED
submission/tests/test_conflicting_sources.py::test_realtime_purchase_overrides_stale_profile PASSED
submission/tests/test_corrected_goal_rule.py::test_correct_underspecified_goal_rule PASSED
submission/tests/test_corrected_goal_rule.py::test_missing_telemetry_signal_rejection PASSED
submission/tests/test_duplicate_and_late.py::test_duplicate_trigger_idempotency PASSED
submission/tests/test_duplicate_and_late.py::test_late_offline_buffered_trigger PASSED
submission/tests/test_failure_fallback.py::test_provider_failure_graceful_fallback PASSED
submission/tests/test_failure_fallback.py::test_budget_enforcement PASSED
submission/tests/test_impact_holdout.py::test_impact_holdout_vs_naive_bias PASSED
submission/tests/test_verification_safety.py::test_quiet_hours_blocks_push PASSED
submission/tests/test_verification_safety.py::test_missing_consent_blocks_push PASSED
submission/tests/test_frequency_cap_blocks_second_message PASSED
submission/tests/test_home_row_minimum_titles_requirement PASSED
submission/tests/test_adversarial_prompt_injection_defense PASSED
============================= 14 passed in 0.36s ==============================
```

---

## 📄 License
This project is licensed under the MIT License.
