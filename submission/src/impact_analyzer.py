"""
Impact Analyzer and Causal Measurement Engine.
Compares agent interventions against the randomized holdout control group.
Demonstrates why naive comparisons (served vs unserved) suffer from severe selection bias.
"""

from typing import List, Dict, Any
from submission.src.models import OutcomeStatus, ActionType


class ImpactAnalyzer:
    def __init__(self):
        pass

    def compute_impact(
        self,
        decisions: List[Dict[str, Any]],
        outcomes: List[Dict[str, Any]],
        viewer_profiles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Computes both:
          1. Honest Causal Impact: Treated vs Randomized Holdout
          2. Naive Biased Comparison: Served vs Everyone Else
        """
        # Map outcomes by decision_id or viewer_id
        outcome_by_vid: Dict[str, str] = {}
        for out in outcomes:
            vid = out.get("viewer_id")
            status = out.get("status")
            if vid and status:
                outcome_by_vid[vid] = status

        # Map decisions by viewer_id
        decisions_by_vid: Dict[str, Dict[str, Any]] = {}
        for dec in decisions:
            vid = dec.get("viewer_id")
            if vid:
                decisions_by_vid[vid] = dec

        # Group viewers
        treated_count = 0
        treated_success = 0

        holdout_count = 0
        holdout_success = 0

        unserved_count = 0
        unserved_success = 0

        for p in viewer_profiles:
            vid = p.get("viewer_id")
            is_holdout = p.get("is_holdout", False)
            dec = decisions_by_vid.get(vid)
            status = outcome_by_vid.get(vid, "FAILED")

            is_success = (status == OutcomeStatus.SUCCEEDED.value)

            if is_holdout:
                holdout_count += 1
                if is_success:
                    holdout_success += 1
            elif dec and dec.get("action") not in [ActionType.DO_NOTHING.value, "DO_NOTHING"]:
                treated_count += 1
                if is_success:
                    treated_success += 1
            else:
                unserved_count += 1
                if is_success:
                    unserved_success += 1

        treated_rate = (treated_success / treated_count) if treated_count > 0 else 0.0
        holdout_rate = (holdout_success / holdout_count) if holdout_count > 0 else 0.0
        unserved_rate = (unserved_success / unserved_count) if unserved_count > 0 else 0.0

        # Honest A/B Causal Uplift (Treated vs Holdout)
        true_abs_uplift = treated_rate - holdout_rate
        true_rel_uplift = (true_abs_uplift / holdout_rate * 100.0) if holdout_rate > 0 else 0.0

        # Naive Flawed Comparison (Served vs Unserved)
        naive_abs_uplift = treated_rate - unserved_rate
        naive_rel_uplift = (naive_abs_uplift / unserved_rate * 100.0) if unserved_rate > 0 else 0.0

        selection_bias_overstatement = (naive_rel_uplift - true_rel_uplift)

        return {
            "treated_sample_size": treated_count,
            "treated_conversion_rate": treated_rate,
            "holdout_sample_size": holdout_count,
            "holdout_conversion_rate": holdout_rate,
            "unserved_sample_size": unserved_count,
            "unserved_conversion_rate": unserved_rate,
            "true_causal_abs_uplift": true_abs_uplift,
            "true_causal_rel_uplift_pct": true_rel_uplift,
            "naive_abs_uplift": naive_abs_uplift,
            "naive_rel_uplift_pct": naive_rel_uplift,
            "selection_bias_inflation_pct": selection_bias_overstatement
        }

    def generate_impact_markdown(self, metrics: Dict[str, Any]) -> str:
        report = f"""# Honest Impact & Causal Measurement Report

## 1. Executive Summary: Causal Uplift vs. Selection Bias

The earlier pilot summary report compared **Served Viewers vs. Everyone Else**, reporting an inflated headline lift.
Our evaluation establishes why that comparison is fundamentally flawed and presents the **honest causal effect** measured against the **randomized holdout (control group)**.

| Metric | Honest Measurement (Treated vs. Holdout) | Naive Method (Served vs. Everyone Else) | Difference / Bias Inflation |
| :--- | :--- | :--- | :--- |
| **Control Group Size** | {metrics['holdout_sample_size']} viewers (Holdout) | {metrics['unserved_sample_size']} viewers (All Unserved) | - |
| **Treated Group Size** | {metrics['treated_sample_size']} viewers | {metrics['treated_sample_size']} viewers | - |
| **Baseline Conversion** | **{metrics['holdout_conversion_rate']*100:.2f}%** | {metrics['unserved_conversion_rate']*100:.2f}% | - |
| **Treated Conversion** | **{metrics['treated_conversion_rate']*100:.2f}%** | **{metrics['treated_conversion_rate']*100:.2f}%** | - |
| **Absolute Uplift** | **+{metrics['true_causal_abs_uplift']*100:.2f}%** | +{metrics['naive_abs_uplift']*100:.2f}% | Overstated by +{metrics['naive_abs_uplift']*100 - metrics['true_causal_abs_uplift']*100:.2f}% |
| **Relative Uplift (%)** | **+{metrics['true_causal_rel_uplift_pct']:.2f}%** | +{metrics['naive_rel_uplift_pct']:.2f}% | **Overstated by +{metrics['selection_bias_inflation_pct']:.2f}%** |

---

## 2. Why Simpler Comparisons Mislead (The Selection Bias Trap)

1. **Active Intent Bias:**
   Viewers who receive interventions ("Served") are users who actively opened the app, remained active long enough to trigger an evaluation, and met consent and quiet-hour requirements. In contrast, "Everyone Else" includes dormant, unengaged, or churned users who never entered the app during the window. Comparing these two groups conflates the agent's actual impact with the viewer's pre-existing intent to watch.

2. **The Purpose of the Randomized Holdout:**
   By withholding interventions from a randomly selected 10% slice of eligible active app-openers (`is_holdout = True`), both groups share identical arrival timing, intent, and platform health. Any difference in goal completion is strictly attributable to the agent's action.

3. **Attributable Signal Rigor:**
   Outcomes are credited only if the user engaged with recommended dialect titles or completed target actions prior to the explicit goal deadline. Ambient conversions that occur outside the deadline window or on unrelated genres without agent exposure are excluded from attribution.
"""
        return report
