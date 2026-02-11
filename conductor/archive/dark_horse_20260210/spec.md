# Specification: Dark Horse & Gap Analysis (Inventory Discovery)

## 1. Overview
This feature implements the "Dark Horse" analysis track from the roadmap. Its goal is to uncover hidden revenue opportunities by identifying logical product pairings that are currently missed by sales-data-driven algorithms (because the items haven't sold together yet).

It uses a "Concept-First" generative approach to brainstorm complementary items for every leaf category in the catalog. It then attempts to map these concepts to existing inventory.

## 2. Goals
1.  **Discover Hidden Inventory:** Identify products we already sell that should be recommended with a category but aren't (e.g., "Socks" for "Boots").
2.  **Identify Catalog Gaps:** Surface product types that we *should* be selling to complement our core offerings but currently do not.
3.  **High-Quality Output:** Produce human-readable CSVs with LLM-generated confidence scores and reasoning, suitable for import into PIM or manual review.

## 3. Core Logic

### 3.1 Input
-   **Source:** Full list of BigCommerce Categories.
-   **Filter:** Process **Leaf Categories** only (categories with no children).

### 3.2 Analysis Pipeline (Per Category)
For each source category (e.g., "Tactical Boots"):

1.  **Phase 1: Generative Brainstorming (LLM)**
    -   **Prompt:** "What are the essential accessories, consumables, or complementary products for 'Tactical Boots'? List generic product types."
    -   **Model:** Local Inference (GPT-OSS-120B compatible).
    -   **Output:** List of concepts (e.g., "Moisture-wicking socks", "Boot laces", "Leather waterproofing", "Insoles").

2.  **Phase 2: Inventory Matching**
    -   **Search:** For each concept, perform a fuzzy/keyword search against the **entire list of store categories**.
    -   **Logic:**
        -   *If Match Found:* Record as **Dark Horse Pairing** (Source Cat -> Target Cat).
        -   *If No Match:* Record as **Catalog Gap** (Source Cat -> Missing Concept).

3.  **Phase 3: Scoring & Validation**
    -   For each valid pairing, ask the LLM to:
        -   Assign a **Confidence Score (0-100%)**: How strong is this recommendation?
        -   Provide **Reasoning**: Why is this a good upsell? (e.g., "Socks are a high-wear consumable required for boots").

### 3.3 Output Files
1.  **`data/dark_horse_pairings.csv`**
    -   Columns: `source_category`, `target_category`, `suggested_weight` (Score), `relationship_type` (e.g., "Accessory", "Complementary"), `reason`, `llm_model_used`.
    -   Format compatible with `approved_category_pairings.csv`.

2.  **`data/catalog_gaps.csv`**
    -   Columns: `source_category`, `missing_product_type`, `suggested_weight`, `reason`.

## 4. Technical Requirements
-   **Integration:** Add as a new subcommand `easyupsell discover` (or similar).
-   **LLM Provider:** Support Local Inference configuration (OpenAI-compatible endpoint for local models).
-   **Performance:**
    -   Since we are iterating all leaf categories, this is a batch process.
    -   Implement progress tracking and resume capability (checkpoints).
-   **Search:** Simple efficient text search (e.g., rapidfuzz or simple substring match) for the "Inventory Matching" phase.

## 5. User Interface (CLI)

The `discover` command serves as the entry point for this feature.

### Usage Examples
```bash
# 1. Run analysis on ALL leaf categories (Batch Mode)
easyupsell discover --all

# 2. Run analysis on a specific category (Testing/Single Shot)
easyupsell discover --category "Tactical Boots"

# 3. Specify a specific model (e.g., pointing to a local endpoint)
easyupsell discover --all --model "local-120b"

# 4. Dry run (print to console instead of saving)
easyupsell discover --category "Flashlights" --dry-run
```

### Options
- `--all`: Flag to process the entire catalog (filters for leaves automatically).
- `--category <name>`: Process a single specific category name.
- `--model <name>`: Override the default model ID (useful for switching between local/cloud).
- `--dry-run`: Output results to stdout JSON instead of writing CSVs.

## 6. Out of Scope
-   Web searching for gaps (Phase 2).
-   Direct PIM integration (Output is CSV).
-   Item-level specific analysis (Category-level only for this iteration).
