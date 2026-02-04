# Validation Report: Batch Run 2026-02-03

**Date:** 2026-02-03
**Run Type:** Batched Inference (Athena/GPT-OSS-120b)
**Data Source:** `full_recommendations.csv` (Sample Proxy)

## Summary Metrics

| Metric | Value |
| :--- | :--- |
| **Total Rows** | 120 |
| **Valid Recommendations** | 24 |
| **Acceptance Rate** | **20.0%** |
| **Mean Confidence** | 0.70 |

## Observations

1.  **Low Acceptance Rate:** The 20% acceptance rate indicates rigorous filtering, which is positive for quality control but suggests we may need to widen the candidate pool or relax the prompt slightly if we want more volume.
2.  **Category "Self-Rejection":** Categories like "Helmets" had high rejection rates. This might be due to the logic filtering out items that are "too similar" or the LLM deciding that buying a helmet with another helmet-related accessory (that isn't strictly necessary) is invalid.
3.  **Confidence Scores:** The confidence scores for valid items are tightly clustered around 0.70. This suggests the model is "cautiously optimistic" rather than highly confident. We might need to adjust the prompt to encourage higher confidence differentiation.

## Top Rejected Categories
- Helmets (12 rejections)
- Inventory Blowout (6 rejections)
- New Products (6 rejections)

## Recommendations for Next Steps
1.  **Prompt Engineering:** Adjust the system prompt to explicitly allow "same-category accessories" (e.g., helmet lights for helmets).
2.  **Confidence Calibration:** Investigate why scores are capped around 0.74.
3.  **Expand Candidates:** Increase `items-per-category` to finding more valid hits.
