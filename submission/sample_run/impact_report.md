# Honest Impact & Causal Measurement Report

## 1. Executive Summary: Causal Uplift vs. Selection Bias

The earlier pilot summary report compared **Served Viewers vs. Everyone Else**, reporting an inflated headline lift.
Our evaluation establishes why that comparison is fundamentally flawed and presents the **honest causal effect** measured against the **randomized holdout (control group)**.

| Metric | Honest Measurement (Treated vs. Holdout) | Naive Method (Served vs. Everyone Else) | Difference / Bias Inflation |
| :--- | :--- | :--- | :--- |
| **Control Group Size** | 250 viewers (Holdout) | 4311 viewers (All Unserved) | - |
| **Treated Group Size** | 189 viewers | 189 viewers | - |
| **Baseline Conversion** | **0.00%** | 0.00% | - |
| **Treated Conversion** | **0.00%** | **0.00%** | - |
| **Absolute Uplift** | **+0.00%** | +0.00% | Overstated by +0.00% |
| **Relative Uplift (%)** | **+0.00%** | +0.00% | **Overstated by +0.00%** |

---

## 2. Why Simpler Comparisons Mislead (The Selection Bias Trap)

1. **Active Intent Bias:**
   Viewers who receive interventions ("Served") are users who actively opened the app, remained active long enough to trigger an evaluation, and met consent and quiet-hour requirements. In contrast, "Everyone Else" includes dormant, unengaged, or churned users who never entered the app during the window. Comparing these two groups conflates the agent's actual impact with the viewer's pre-existing intent to watch.

2. **The Purpose of the Randomized Holdout:**
   By withholding interventions from a randomly selected 10% slice of eligible active app-openers (`is_holdout = True`), both groups share identical arrival timing, intent, and platform health. Any difference in goal completion is strictly attributable to the agent's action.

3. **Attributable Signal Rigor:**
   Outcomes are credited only if the user engaged with recommended dialect titles or completed target actions prior to the explicit goal deadline. Ambient conversions that occur outside the deadline window or on unrelated genres without agent exposure are excluded from attribution.
