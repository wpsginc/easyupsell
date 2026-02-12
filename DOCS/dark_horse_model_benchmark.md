# Dark Horse Discovery — LLM Model Benchmark

**Date:** 2026-02-11
**Test:** Same 5 categories × 4 models
**Categories:** Gear Dryers, Agricultural Rescue, Air Bag Devices, Flashlights, Boots

---

## Summary Table

| Model | Size | Quant | Pairings | Gaps | Avg Time/Cat | Cost | JSON Reliability |
|---|---|---|---|---|---|---|---|
| **Azure GPT-5.2** | Cloud | N/A | ~28 | ~24 | ~5s | ~$0.05 | ★★★★★ |
| **GPT-OSS 120B** | 120B | Q5_K_M | 23 | 15 | ~9s | $0.00 | ★★★★☆ |
| **GLM-4.5 Air** | ~82B | Q4_K_M | **30** | 19 | ~30s | $0.00 | ★★★★☆ |
| **Qwen3 Coder Next** | 80B | Q6_K_XL | 7 | 17 | ~36s | $0.00 | ★★★★★ |

> [!NOTE]
> All local models ran on **Athena** (RTX-class GPU) via llama.cpp at `athena:8081`.

---

## Model Profiles

### Azure GPT-5.2 (Baseline)
- **Strengths:** Fast, reliable JSON, strong product knowledge, best recall
- **Weaknesses:** Costs money ($0.05 for 5 categories, ~$13 for full catalog)
- **Verdict:** Gold standard for quality. Use when budget allows or for final validation passes.

### GPT-OSS 120B Derestricted (Q5_K_M)
- **Strengths:** Strong world knowledge, fast for local inference (~9s/cat), good domain understanding
- **Weaknesses:** Required `response_format: json_object` + fallback regex to produce clean JSON. Initial run with old parser returned 0 results (all parse errors).
- **Notable finds:** Air Bag Devices → Wiring Harness + Diagnostic Scanner; Gear Dryers → Desiccant Packs
- **Verdict:** Best balance of speed, quality, and cost for batch runs. Recommended for production.

### GLM-4.5 Air Derestricted (Q4_K_M)
- **Strengths:** **Highest pairing count (30)**. Deepest product knowledge — found Carabiners for Flashlights, Boot Dryer for Boots, Pruning Shears for Agricultural Rescue.
- **Weaknesses:** Slowest local model (~30s/cat). Occasionally drifts off-topic — confused "Agricultural Rescue" (emergency rescue in farm settings) with farming/gardening, suggesting Fertilizer, Seeds, Soil.
- **Notable finds:** Flashlights → Carabiners, Lens Cleaner; Boots → Boot Dryer (via Gear Washer accessories)
- **Verdict:** Best wordsmith and broadest knowledge. Ideal for brainstorming phase, but needs validation layer to catch hallucinations.

### Qwen3 Coder Next (Q6_K_XL)
- **Strengths:** Perfect JSON output — zero parse errors. Strong structured reasoning.
- **Weaknesses:** Only 7 pairings — extremely conservative. Limited product/retail domain knowledge. Slowest inference (~36s/cat).
- **Notable finds:** Flashlights → Batteries, Lanyards, Charging, Mounting, Cases; Boots → Socks
- **Verdict:** Master tool-caller and coder, but not the right model for open-ended product brainstorming. Would excel at validation/scoring.

---

## Category Breakdown

### Gear Dryers

| Model | Pairings Found | Top Concepts |
|---|---|---|
| Azure GPT-5.2 | 4 | Vent Cleaning Brush, Power Cord, Gas Connector, Stacking Kit |
| GPT-OSS 120B | 6 | Replacement Element, Power Cord, Desiccant Packs, Cleaning Brush, Water Tray, Lint Trap |
| GLM-4.5 Air | 3 | Filter, Cleaning Brush, Lint Trap |
| Qwen3 Coder | 0 | (All concepts → gaps) |

### Agricultural Rescue

| Model | Pairings Found | Top Concepts |
|---|---|---|
| Azure GPT-5.2 | 6 | Multiple rescue equipment matches |
| GPT-OSS 120B | 7 | Rescue Harness, Rope, First Aid, Gloves, PPE, Portable Light, Tool Belt |
| GLM-4.5 Air | 3 | Pruning Shears, Rope, Gloves |
| Qwen3 Coder | 1 | Horse Saddle Pads |

### Flashlights

| Model | Pairings Found | Top Concepts |
|---|---|---|
| Azure GPT-5.2 | ~5 | Batteries, Lanyards, Holsters, Cases, Chargers |
| GPT-OSS 120B | 6 | Batteries, Holster, Lanyard, Case, Charger, Mounting Bracket |
| GLM-4.5 Air | **9** | Batteries, Holster, Replacement Bulb, Lanyard, Charger, Mount, Carabiner, Flashlight Stand, Lens Cleaner |
| Qwen3 Coder | 5 | Batteries, Lanyard, Charging, Mounting, Waterproof Case |

### Boots

| Model | Pairings Found | Top Concepts |
|---|---|---|
| Azure GPT-5.2 | ~3 | Socks, Boot Polish, Boot Trees |
| GPT-OSS 120B | 3 | Socks, Boot Polish, Boot Trees |
| GLM-4.5 Air | **5** | Socks, Boot Laces, Boot Polish, Cleaning Brush, **Boot Dryer** |
| Qwen3 Coder | 1 | Socks |

---

## Recommendations

### For Production Batch Runs
**GPT-OSS 120B** — best balance of speed (~9s/cat), quality (23 pairings), and cost ($0). Full 1,274-category run would take ~3 hours.

### For Maximum Discovery
**GLM-4.5 Air** — highest pairing count (30), deepest knowledge. Run overnight for full catalog (~10-12 hours). Requires validation layer to filter hallucinations.

### Optimal Hybrid Pipeline (Future)
1. **GLM-4.5 Air** for brainstorming (concept generation — broadest knowledge)
2. **Qwen3 Coder** or **GPT-OSS 120B** for validation (structured scoring — best JSON discipline)

This would combine GLM's creative breadth with a stricter model's analytical precision.

### Not Recommended for This Task
**Qwen3 Coder Next** — excellent for code generation and tool calling, but too conservative for open-ended product brainstorming. Only found 7 pairings vs 23-30 from other models.

---

## Technical Notes

- All local models used the Athena server via llama.cpp OpenAI-compatible API
- `_call_athena()` requires `response_format: {"type": "json_object"}` and a JSON fallback regex for reliable parsing
- `config.toml` controls provider selection — swap models by changing `default_provider`
- Output files: `data/dark_horse_gptoss120b.xlsx`, `data/dark_horse_glm45air.xlsx`, `data/dark_horse_athena.xlsx` (Qwen3)
