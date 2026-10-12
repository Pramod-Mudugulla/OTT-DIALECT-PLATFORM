"""
Test Suite: Honest Impact Measurement and Holdout Comparison.
Verifies:
1. True Causal Effect is computed strictly using randomized holdout control group.
2. Demonstrates the mathematical inflation caused by naive (served vs unserved) selection bias.
"""

import pytest
from submission.src.impact_analyzer import ImpactAnalyzer


def test_impact_holdout_vs_naive_bias():
    analyzer = ImpactAnalyzer()

    # Synthetic cohort
    profiles = [
        {"viewer_id": f"V-{i}", "is_holdout": (i < 20)}
        for i in range(100)
    ]
    # 20 holdout viewers (organic conversion rate: 20%)
    # 50 treated served viewers (conversion rate: 40%)
    # 30 unserved dormant viewers (conversion rate: 5%)

    decisions = []
    outcomes = []

    for i in range(100):
        vid = f"V-{i}"
        is_h = i < 20
        is_treated = (i >= 20 and i < 70)

        dec_action = "HOME_PAGE" if is_treated else "DO_NOTHING"
        decisions.append({"viewer_id": vid, "action": dec_action})

        if is_h:
            # 4 out of 20 succeed (20%)
            status = "SUCCEEDED" if i < 4 else "FAILED"
        elif is_treated:
            # 20 out of 50 succeed (40%)
            status = "SUCCEEDED" if i < 40 else "FAILED"
        else:
            # 2 out of 30 succeed (~6.7%)
            status = "SUCCEEDED" if i < 72 else "FAILED"

        outcomes.append({"viewer_id": vid, "status": status})

    metrics = analyzer.compute_impact(decisions, outcomes, profiles)

    # True causal uplift: 40% - 20% = +20% absolute (+100% relative)
    assert metrics["true_causal_abs_uplift"] == pytest.approx(0.20, abs=1e-2)
    assert metrics["true_causal_rel_uplift_pct"] == pytest.approx(100.0, abs=1e-1)

    # Naive method (served vs unserved): 40% - 6.7% = ~33.3% absolute
    assert metrics["naive_abs_uplift"] > metrics["true_causal_abs_uplift"]
    assert metrics["selection_bias_inflation_pct"] > 0
