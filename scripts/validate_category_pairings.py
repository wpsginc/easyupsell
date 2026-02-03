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
import os
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

# Import store context
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
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
    elif provider == "openai":
        return _call_openai(prompt)
    elif provider == "ollama":
        return _call_ollama(prompt)
    elif provider == "litellm":
        return _call_litellm(prompt)
    elif provider == "athena":
        return _call_athena(prompt)
    else:
        # Default: return uncertain
        return {
            "valid": None,
            "confidence": 0.0,
            "reason": f"Unknown provider: {provider}",
            "relationship_type": "unknown",
            "suggested_weight": 0,
        }


def _call_azure_openai(prompt: str) -> dict:
    """Call Azure OpenAI API."""
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    api_base = os.environ.get("AZURE_OPENAI_API_BASE")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    if not api_key or not api_base:
        return {"valid": None, "confidence": 0, "reason": "Azure OpenAI not configured"}
    
    # Azure OpenAI endpoint format
    url = f"{api_base.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    
    response = requests.post(
        url,
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        },
        timeout=60,
    )
    response.raise_for_status()
    
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _call_openai(prompt: str) -> dict:
    """Call OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"valid": None, "confidence": 0, "reason": "No OPENAI_API_KEY set"}
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
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
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    
    response = requests.post(
        f"{ollama_host}/api/generate",
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
    litellm_host = os.environ.get("LITELLM_HOST", "http://localhost:4000")
    api_key = os.environ.get("LITELLM_API_KEY", "")
    
    response = requests.post(
        f"{litellm_host}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        json={
            "model": os.environ.get("LITELLM_MODEL", "gpt-4o-mini"),
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        },
        timeout=60,
    )
    response.raise_for_status()
    
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _call_athena(prompt: str) -> dict:
    """Call GPT-OSS 120B on Athena (local inference, FREE!)."""
    athena_host = os.environ.get("ATHENA_HOST", "http://100.64.0.3:8081")
    
    # Simplified prompt for better JSON response
    simple_prompt = f"""{prompt}

CRITICAL: Output ONLY valid JSON with these exact fields:
{{"valid": true/false, "confidence": 0.0-1.0, "reason": "one line", "relationship_type": "accessory|complementary|unrelated", "suggested_weight": 50}}"""
    
    # GPT-OSS uses OpenAI-compatible API
    response = requests.post(
        f"{athena_host}/v1/chat/completions",
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
    parser.add_argument("--provider", default="azure", choices=["azure", "openai", "ollama", "litellm"])
    parser.add_argument("--categories", default="data/categories.json", help="Categories file")
    parser.add_argument("--output", default="data/validated_pairings", help="Output path")
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
