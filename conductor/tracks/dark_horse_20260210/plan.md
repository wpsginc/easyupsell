# Implementation Plan - Dark Horse Upsell Discovery

## Phase 1: Core "Discover" Command Infrastructure [checkpoint: 409d6aa]
- [x] Task: Create new CLI command `discover` [b336b0f]
    - [x] Create `easyupsell/commands/discover.py` with Typer skeleton.
    - [x] Register command in `easyupsell/cli.py`.
    - [x] Implement `--category` (single) and `--all` (batch) arguments.
- [x] Task: Implement Leaf Category Filter [cbac70c]
    - [x] Update `easyupsell/core/analyzer.py` or similar to support fetching ONLY leaf categories (categories with no children).
    - [x] Write unit test ensuring parent categories are excluded.
- [x] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Generative Brainstorming (The "Dark Horse" Engine) [checkpoint: d823137]
- [x] Task: Implement Local LLM Client Support [c2cd11a]
    - [x] Extend `easyupsell/src/enrichment.py` or `config.py` to support a custom `local` provider URL (OpenAI-compatible).
    - [x] Add config validation for local model endpoints.
- [x] Task: Create Brainstorming Prompt [c205273]
    - [x] Design the system prompt for "Concept Generation" (Input: Category Name -> Output: List of Concepts).
    - [x] Implement the `brainstorm_concepts(category)` function.
    - [x] Test with a local model mock or actual connection.
- [x] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Inventory Matching & Scoring Logic [checkpoint: 111b67b]
- [x] Task: Implement "Inventory Matcher" [3670c7b]
    - [x] Create a utility that loads all category names into memory.
    - [x] Implement fuzzy search (using `rapidfuzz` or `thefuzz`) to match "Concept" -> "Existing Category".
    - [x] Return matches and "misses" (gaps).
- [x] Task: Implement Scoring/Reasoning [552ac85]
    - [x] Create the "Validation Prompt" (Input: Source Cat + Candidate Match -> Output: Score & Reason).
    - [x] Integrate this step into the pipeline for *found* matches.
- [x] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)

## Phase 4: Output & Integration
- [x] Task: Implement CSV Writers [346a688]
    - [ ] Create `write_dark_horse_results(pairings)` for `data/dark_horse_pairings.csv`.
    - [ ] Create `write_catalog_gaps(gaps)` for `data/catalog_gaps.csv`.
    - [ ] Ensure headers match the specification.
- [ ] Task: End-to-End Testing
    - [ ] Run a dry run on a small subset (e.g., "Boots").
    - [ ] Verify output file format and content quality.
- [ ] Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)
