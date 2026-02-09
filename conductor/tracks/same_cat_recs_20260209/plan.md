# Implementation Plan - Enable Same-Category Recommendations

## Phase 1: reproduction
- [x] Task: Create a reproduction test case [5fb680c]
    - [ ] Create a unit test in `tests/test_candidate_filter.py` using mock products from the same category.
    - [ ] Assert that the current behavior returns 0 candidates (confirming the block exists).
    - [ ] **Goal:** Fail the test (proving the filter is active) or confirm where the logic resides.
- [ ] Task: Conductor - User Manual Verification 'reproduction' (Protocol in workflow.md)

## Phase 2: Implementation
- [ ] Task: Modify Candidate Filter Logic
    - [ ] Locate the filtering logic (expected in `src/candidate_filter.py` or `easyupsell/core/analyzer.py`).
    - [ ] Remove or adjust the condition `if candidate.category_id == target.category_id: continue`.
    - [ ] Run the reproduction test again.
    - [ ] **Goal:** The test should now pass (candidates are returned).
- [ ] Task: Conductor - User Manual Verification 'Implementation' (Protocol in workflow.md)

## Phase 3: Validation
- [ ] Task: Run CLI Analysis
    - [ ] Execute `easyupsell analyze` on a known category (e.g., "Fire Helmets") using the `--category` flag.
    - [ ] manual check: Verify that accessories in the same category appear in the output CSV.
- [ ] Task: Conductor - User Manual Verification 'Validation' (Protocol in workflow.md)
