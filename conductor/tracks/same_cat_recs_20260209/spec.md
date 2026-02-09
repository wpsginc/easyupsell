# Specification: Enable Same-Category Recommendations

## Context
The current recommendation engine proactively filters out candidate products that belong to the same category as the target product. This was intended to prevent "substitute" recommendations (e.g., suggesting "Blue Pants" for "Red Pants").

## Problem
This filtering logic is too aggressive. It prevents valid "complementary" relationships that occur within the same category structure.
**Example:** "Fire Helmets" category contains both:
1. The Helmet itself (Target)
2. The Helmet Light (Accessory/Candidate)

By blocking same-category items, we miss high-value upsells like Helmet -> Helmet Light.

## Requirements
1. **Remove/Relax Hard Filter:** The hard constraint preventing same-category candidates must be removed.
2. **Rely on Validation:** We will rely on the subsequent LLM validation step (or explicit rules) to filter out true substitutes (Red Pants vs Blue Pants) while keeping accessories.
3. **Verification:** Ensure that `easyupsell analyze` can now produce candidates where `target.category == candidate.category`.

## Risk Assessment
- **Risk:** Increased noise in recommendations (substitutes appearing as upsells).
- **Mitigation:** The LLM prompt may need to be slightly adjusted to explicitly check for "substitute vs accessory" if it doesn't already. For this track, we focus primarily on **allowing** the candidates to reach the validation stage.
