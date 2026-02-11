#!/usr/bin/env python3
"""
LLM-Validated Category Recommendations

Uses an LLM to validate whether category pairings make sense for upsell.
Works at child category level (e.g., "Tactical Pants" not "Pants").

Usage:
    python scripts/validate_category_pairings.py
    python scripts/validate_category_pairings.py --provider openai
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import requests

# Add src to path for config and context
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config import settings

try:
    from context import STORE_CONTEXT, build_enriched_prompt, get_category_context
    HAS_CONTEXT = True
except ImportError:
    HAS_CONTEXT = False
    STORE_CONTEXT = ""


# =============================================================================
# LLM Integration
# =============================================================================

def get_llm_validation(
    source_category: str,
    target_category: str,
    provider: str = "openai",
    context: Optional[str] = None,
) -> dict:
    """
    Ask LLM if two categories make sense as an upsell pairing.
    
    Returns:
        {
            "valid": bool,
            "confidence": float (0-1),
            "reason": str,
            "suggested_weight": int (1-90)
        }
    """
    # Build enriched context if available
    if HAS_CONTEXT and context is None:
        context = build_enriched_prompt(source_category, target_category)
    
    prompt = f"""You are a retail merchandising expert evaluating upsell/cross-sell recommendations.

{STORE_CONTEXT if HAS_CONTEXT else "This is a safety/tactical/industrial supplies store."}

Given these two product categories:
- Source category (customer is buying): "{source_category}"
- Recommended category (upsell suggestion): "{target_category}"

{f"Category context: {get_category_context(source_category)}" if HAS_CONTEXT and get_category_context(source_category) else ""}
{f"Target context: {get_category_context(target_category)}" if HAS_CONTEXT and get_category_context(target_category) else ""}

Evaluate if this is a SENSIBLE upsell recommendation. Consider:
1. Are these products logically complementary or used together IN THE SAME JOB FUNCTION?
2. Would a customer buying the source REALISTICALLY also need the target?
3. Is this a professional/practical pairing (not random)?

CRITICAL EXCEPTIONS:
- If the item is in the SAME category (e.g., Helmet Light for Helmets), it is VALID if it is an accessory, part, or upgrade.
- Consumables (batteries, cleaning kits) are almost always VALID.

{context if context and not HAS_CONTEXT else ""}

Respond in JSON format:
{{
    "valid": true/false,
    "confidence": 0.0-1.0,
    "reason": "Brief explanation",
    "relationship_type": "accessory|complementary|bundle|unrelated",
    "suggested_weight": 1-90 (higher = stronger recommendation, 51-70 for category level)
}}
"""

    if provider == "azure":
        return _call_azure_openai(prompt)
    elif provider == "gpt5-nano":
        return _call_azure_openai(prompt, deployment="gpt-5-nano")
    elif provider == "gpt5-mini":
        return _call_azure_openai(prompt, deployment="gpt-5-mini")
    elif provider == "openai":
        return _call_openai(prompt)
    elif provider == "ollama":
        return _call_ollama(prompt)
    elif provider == "litellm":
        return _call_litellm(prompt)
    elif provider == "athena":
        return _call_athena(prompt)
    elif provider == "local":
        return _call_local_llm(prompt)
    else:
        # Default: return uncertain
        return {
            "valid": None,
            "confidence": 0.0,
            "reason": f"Unknown provider: {provider}",
            "relationship_type": "unknown",
            "suggested_weight": 0,
        }


def get_batch_llm_validation(
    source_category: str,
    target_items: list[dict],  # [{"name": "...", "sku": "...", "brand": "..."}, ...]
    provider: str = "athena",
    max_items: int = 10,
) -> list[dict]:
    """
    Batch evaluate multiple items for a single category in one LLM call.
    
    This is 3-4x faster than individual calls due to:
    - Single prompt processing overhead
    - MoE experts staying "warm" across items
    - Reduced round-trip latency
    
    Args:
        source_category: The category customer is buying from
        target_items: List of candidate items to evaluate
        provider: LLM provider (athena recommended for batch)
        max_items: Max items per batch (stay under 25k tokens)
    
    Returns:
        List of validation results, one per item
    """
    # Limit batch size to stay in effective context window
    items_to_evaluate = target_items[:max_items]
    
    # Build item list for prompt
    item_lines = []
    for i, item in enumerate(items_to_evaluate):
        base_line = f"  {i+1}. {item.get('name', 'Unknown')}"
        details = []
        
        if item.get('sku'):
            details.append(f"SKU: {item['sku']}")
        if item.get('brand'):
            details.append(f"Brand: {item['brand']}")
        if item.get('price'):
            details.append(f"Price: ${item['price']}")
            
        # Enriched Data
        if item.get('copurchase_text'):
            details.append(item['copurchase_text'])
        if item.get('margin_pct'):
            details.append(f"Gross Margin: {float(item['margin_pct'])*100:.1f}%")
        if item.get('velocity_text'):
            details.append(item['velocity_text'])
        if item.get('inventory_text'):
            details.append(item['inventory_text'])
        if item.get('same_category'):
            details.append("⚠️ SAME CATEGORY as source — valid ONLY if accessory/part/upgrade")
            
        # Combine
        if details:
            item_lines.append(f"{base_line}\n     - " + "\n     - ".join(details))
        else:
            item_lines.append(base_line)

    item_list = "\n".join(item_lines)
    
    prompt = f"""You are a retail merchandising expert evaluating upsell recommendations.

{STORE_CONTEXT if HAS_CONTEXT else "This is a safety/tactical/industrial supplies store."}

A customer is buying from: "{source_category}"

Evaluate EACH of these {len(items_to_evaluate)} potential upsell items:
{item_list}

For EACH item, determine if it's a sensible upsell. Consider:
1. Is this item complementary to {source_category} OR an accessory for it?
2. Would a customer REALISTICALLY buy both together?
3. Is this a professional/practical pairing?

CRITICAL EXCEPTIONS:
- If the item is in the SAME category (e.g., Helmet Light for Helmets), it is VALID if it is an accessory, part, or upgrade.
- Do NOT reject items just because they share a category name.
- Consumables (batteries, cleaning kits) are almost always VALID.

Respond with a JSON array containing one object per item, in order:
[
  {{"item_index": 1, "valid": true/false, "confidence": 0.0-1.0, "reason": "brief", "relationship_type": "accessory|complementary|bundle|unrelated", "suggested_weight": 1-90}},
  {{"item_index": 2, ...}},
  ...
]

IMPORTANT: Return ONLY the JSON array, no other text."""

    # Route to appropriate provider
    if provider == "athena":
        result = _call_athena_batch(prompt, len(items_to_evaluate))
    elif provider in ("azure", "gpt5-nano", "gpt5-mini"):
        deployment = None
        if provider == "gpt5-nano":
            deployment = "gpt-5-nano"
        elif provider == "gpt5-mini":
            deployment = "gpt-5-mini"
        result = _call_azure_batch(prompt, len(items_to_evaluate), deployment)
    else:
        # Fallback: return empty results
        return [{"valid": None, "confidence": 0, "reason": f"Provider {provider} not supported for batch"} 
                for _ in items_to_evaluate]
    
    # Parse results and match back to items
    if not isinstance(result, list):
        # Parsing failed - return defaults
        return [{"valid": None, "confidence": 0, "reason": "Batch parse failed"} 
                for _ in items_to_evaluate]
    
    # Ensure we have results for all items
    validated = []
    for i, item in enumerate(items_to_evaluate):
        if i < len(result):
            r = result[i]
            r["item_name"] = item.get("name")
            r["item_sku"] = item.get("sku")
            validated.append(r)
        else:
            validated.append({
                "valid": None, 
                "confidence": 0, 
                "reason": "Missing from batch response",
                "item_name": item.get("name"),
                "item_sku": item.get("sku"),
            })
    
    return validated


def _call_athena_batch(prompt: str, expected_count: int) -> list:
    """Call Athena for batch validation."""
    try:
        response = requests.post(
            f"{settings.ATHENA_HOST}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": "gpt-oss-120b-derestricted",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 300 * expected_count,  # ~300 tokens per item
            },
            timeout=settings.BATCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_batch_json(content)
    except Exception as e:
        print(f"  Athena batch error: {e}")
        return []


def _call_azure_batch(prompt: str, expected_count: int, deployment: Optional[str] = None) -> list:
    """Call Azure for batch validation."""
    if deployment is None:
        deployment = settings.AZURE_OPENAI_DEPLOYMENT
    
    if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_API_BASE:
        return []
    
    url = f"{settings.AZURE_OPENAI_API_BASE.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
    
    payload = {
        "messages": [{
            "role": "system",
            "content": "You are a retail merchandising expert. Always respond with a valid JSON array only, no other text."
        }, {
            "role": "user",
            "content": prompt
        }],
        # NOTE: Do NOT use response_format: json_object for batch calls.
        # json_object mode forces a single root object, preventing the model
        # from returning a bare JSON array of multiple items.
    }
    
    # GPT-5 models use different params
    if "nano" in deployment:
        payload["max_completion_tokens"] = 2000 + (200 * expected_count)
        payload["reasoning_effort"] = "low"
    elif "gpt-5" in deployment:
        payload["max_completion_tokens"] = 300 * expected_count
    else:
        payload["temperature"] = 0.3
        payload["max_tokens"] = 300 * expected_count
    
    try:
        response = requests.post(
            url,
            headers={"api-key": settings.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=settings.BATCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = _parse_batch_json(content)
        if not parsed:
            print(f"  ⚠️ Azure batch: got response but parsed 0 items. Raw: {content[:300]}")
        return parsed
    except Exception as e:
        print(f"  Azure batch error: {e}")
        return []


def _parse_batch_json(content: str) -> list:
    """Parse JSON array from LLM response, handling common issues."""
    content = content.strip()
    
    # Try direct parse
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
        # Azure response_format: json_object forces LLM to wrap arrays
        # in an object with arbitrary keys ("results", "items", "evaluations", etc.)
        if isinstance(result, dict):
            for value in result.values():
                if isinstance(value, list):
                    return value
        return []
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON array from markdown code block
    import re
    json_match = re.search(r'\[[\s\S]*\]', content)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    return []


def _call_azure_openai(prompt: str, deployment: Optional[str] = None) -> dict:
    """Call Azure OpenAI API."""
    if deployment is None:
        deployment = settings.AZURE_OPENAI_DEPLOYMENT
    
    if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_API_BASE:
        return {"valid": None, "confidence": 0, "reason": "Azure OpenAI not configured"}
    
    # Azure OpenAI endpoint format
    url = f"{settings.AZURE_OPENAI_API_BASE.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
    
    # GPT-5 models use max_completion_tokens instead of max_tokens
    # GPT-5-nano doesn't support temperature parameter
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    
    # Add appropriate token limit based on model
    # GPT-5-nano is a reasoning model - needs ~1400 tokens for thinking + output
    if "nano" in deployment:
        payload["max_completion_tokens"] = 2000  # Reasoning models need a lot more
        payload["reasoning_effort"] = "low"  # Minimize the evil internal monologue
    elif "gpt-5" in deployment or "gpt-oss" in deployment:
        payload["max_completion_tokens"] = 300
    
    # Only add temperature for models that support it (not nano)
    if "nano" not in deployment:
        payload["temperature"] = 0.3
    
    response = requests.post(
        url,
        headers={
            "api-key": settings.AZURE_OPENAI_API_KEY,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _call_openai(prompt: str) -> dict:
    """Call OpenAI API."""
    if not settings.OPENAI_API_KEY:
        return {"valid": None, "confidence": 0, "reason": "No OPENAI_API_KEY set"}
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        },
        timeout=30,
    )
    response.raise_for_status()
    
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _call_ollama(prompt: str) -> dict:
    """Call local Ollama instance."""
    response = requests.post(
        f"{settings.OLLAMA_HOST}/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=60,
    )
    response.raise_for_status()
    
    content = response.json()["response"]
    return json.loads(content)


def _call_litellm(prompt: str) -> dict:
    """Call via LiteLLM proxy (Moltbot/Athena compatible)."""
    response = requests.post(
        f"{settings.LITELLM_HOST}/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.LITELLM_API_KEY}"} if settings.LITELLM_API_KEY else {},
        json={
            "model": settings.LITELLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        },
        timeout=60,
    )
    response.raise_for_status()
    
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _call_local_llm(prompt: str) -> dict:
    """Call generic local LLM (OpenAI compatible)."""
    response = requests.post(
        f"{settings.LOCAL_LLM_HOST.rstrip('/')}/chat/completions",
        json={
            "model": settings.LOCAL_LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        },
        timeout=60,
    )
    response.raise_for_status()
    
    content = response.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Fallback for models that output markdown or extra text
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group())
        raise


def _call_athena(prompt: str) -> dict:
    """Call GPT-OSS 120B on Athena (local inference, FREE!)."""
    # Simplified prompt for better JSON response
    simple_prompt = f"""{prompt}

CRITICAL: Output ONLY valid JSON with these exact fields:
{{"valid": true/false, "confidence": 0.0-1.0, "reason": "one line", "relationship_type": "accessory|complementary|unrelated", "suggested_weight": 50}}"""
    
    # GPT-OSS uses OpenAI-compatible API
    response = requests.post(
        f"{settings.ATHENA_HOST}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": "gpt-oss-120b",
            "messages": [{"role": "user", "content": simple_prompt}],
            "temperature": 0.3,
            "max_tokens": 300,  # Needs room for reasoning + output
        },
        timeout=180,  # Local model can be slower
    )
    response.raise_for_status()
    
    msg = response.json()["choices"][0]["message"]
    content = msg.get("content", "")
    
    # GPT-OSS might put reasoning in separate field, content has the answer
    if not content and msg.get("reasoning_content"):
        # Model still thinking, try extracting from reasoning
        content = msg.get("reasoning_content", "")
    
    # Find JSON in the response
    import re
    json_match = re.search(r'\{[^{}]*"valid"[^{}]*\}', content, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    
    # Try to parse the whole content as JSON
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    
    return json.loads(content)


# =============================================================================
# Category Pairing Validation
# =============================================================================

def validate_category_pairings(
    pairings: list[tuple[str, str]],
    provider: str = "openai",
) -> list[dict]:
    """
    Validate a list of category pairings using LLM.
    
    Args:
        pairings: List of (source_category, target_category) tuples
        provider: LLM provider to use
    
    Returns:
        List of validation results with original pairing info
    """
    results = []
    
    for i, (source, target) in enumerate(pairings):
        print(f"  Validating {i+1}/{len(pairings)}: {source} → {target}")
        
        try:
            validation = get_llm_validation(source, target, provider=provider)
            results.append({
                "source_category": source,
                "target_category": target,
                **validation,
            })
        except Exception as e:
            print(f"    ⚠️ Error: {e}")
            results.append({
                "source_category": source,
                "target_category": target,
                "valid": None,
                "confidence": 0,
                "reason": f"Error: {e}",
                "relationship_type": "error",
                "suggested_weight": 0,
            })
    
    return results


def load_categories(categories_path: Path) -> list[dict]:
    """Load categories from export."""
    if not categories_path.exists():
        return []
    
    with open(categories_path) as f:
        data = json.load(f)
    
    # Return flat list
    return data.get("flat", data) if isinstance(data, dict) else data


def generate_child_category_pairings(categories: list[dict]) -> list[tuple[str, str]]:
    """
    Generate candidate pairings from child categories (deepest level).
    """
    # Find max depth
    max_depth = max(c.get("depth", 0) for c in categories) if categories else 0
    
    # Get child categories (at max depth or depth >= 2)
    child_cats = [c for c in categories if c.get("depth", 0) >= min(2, max_depth)]
    
    # Generate pairings (all combinations, LLM will filter)
    pairings = []
    names = [c.get("name") for c in child_cats if c.get("name")]
    
    # Limit combinatorial explosion - sample or use heuristics
    if len(names) > 50:
        print(f"  Note: {len(names)} categories, limiting to same-parent pairings")
        # Group by parent, pair within groups
        by_parent = {}
        for c in child_cats:
            parent = c.get("parent_id", 0)
            if parent not in by_parent:
                by_parent[parent] = []
            by_parent[parent].append(c.get("name"))
        
        for parent_id, names in by_parent.items():
            for i, n1 in enumerate(names):
                for n2 in names[i+1:]:
                    pairings.append((n1, n2))
                    pairings.append((n2, n1))
    else:
        for i, n1 in enumerate(names):
            for n2 in names[i+1:]:
                pairings.append((n1, n2))
                pairings.append((n2, n1))
    
    return pairings[:100]  # Limit for cost control


def main():
    parser = argparse.ArgumentParser(description="Validate category pairings with LLM")
    parser.add_argument("--provider", default=settings.DEFAULT_PROVIDER, choices=["azure", "openai", "ollama", "litellm", "athena"])
    parser.add_argument("--categories", default=str(settings.DATA_DIR / "categories.json"), help="Categories file")
    parser.add_argument("--output", default=str(settings.DATA_DIR / "validated_pairings"), help="Output path")
    args = parser.parse_args()
    
    print("LLM-Validated Category Recommendations")
    print("=" * 50)
    
    # Load categories
    categories_path = Path(args.categories)
    categories = load_categories(categories_path)
    
    if not categories:
        print(f"⚠️  No categories found at {categories_path}")
        print("\nDemo mode: Testing sample pairings...")
        
        # Demo pairings
        test_pairings = [
            ("Tactical Pants", "Tactical Belts"),
            ("Fire Helmets", "Helmet Accessories"),
            ("Radios", "Radio Straps"),
            ("Fire Helmets", "Gun Magazines"),  # Should be invalid
            ("Tactical Boots", "Boot Socks"),
        ]
    else:
        print(f"Loaded {len(categories)} categories")
        test_pairings = generate_child_category_pairings(categories)
    
    print(f"\nValidating {len(test_pairings)} category pairings with {args.provider}...\n")
    
    results = validate_category_pairings(test_pairings, provider=args.provider)
    
    # Summary
    valid = [r for r in results if r.get("valid") is True]
    invalid = [r for r in results if r.get("valid") is False]
    uncertain = [r for r in results if r.get("valid") is None]
    
    print(f"\n✅ Valid pairings: {len(valid)}")
    print(f"❌ Invalid pairings: {len(invalid)}")
    print(f"❓ Uncertain: {len(uncertain)}")
    
    if valid:
        print("\nTop valid pairings:")
        for r in sorted(valid, key=lambda x: -x.get("suggested_weight", 0))[:10]:
            print(f"  {r['source_category']} → {r['target_category']}")
            print(f"    Weight: {r.get('suggested_weight')}, Type: {r.get('relationship_type')}")
            print(f"    Reason: {r.get('reason')}")
    
    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path.with_suffix(".json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {output_path.with_suffix('.json')}")
    
    # Save only valid as CSV for Peasisoft
    if valid:
        import csv
        csv_path = output_path.with_name("approved_category_pairings.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "source_category", "target_category", "suggested_weight", 
                "relationship_type", "reason"
            ])
            writer.writeheader()
            for r in valid:
                writer.writerow({
                    "source_category": r["source_category"],
                    "target_category": r["target_category"],
                    "suggested_weight": r.get("suggested_weight", 50),
                    "relationship_type": r.get("relationship_type", ""),
                    "reason": r.get("reason", ""),
                })
        print(f"Saved: {csv_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
