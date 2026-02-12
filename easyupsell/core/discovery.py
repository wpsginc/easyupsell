import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import generic LLM caller
# Adding scripts to path to import (following existing pattern)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from validate_category_pairings import call_llm_generic, get_llm_validation

from easyupsell.core.matching import InventoryMatcher

def brainstorm_concepts(category_name: str, provider: str = "local") -> List[str]:
    """
    Generate a list of complementary product concepts for a category.
    
    Uses 2-pass approach on supported providers (athena):
      Pass 1: Free-form domain knowledge (no JSON constraint — full MoE activation)
      Pass 2: Format raw text into JSON (trivial parsing task)
    
    Falls back to single-pass JSON for other providers.
    
    Returns (concepts_list, error_string_or_None).
    """
    # Providers that support raw text mode — use 2-pass
    two_pass_providers = {"athena"}
    
    if provider in two_pass_providers:
        return _brainstorm_two_pass(category_name, provider)
    else:
        return _brainstorm_single_pass(category_name, provider)


def _brainstorm_two_pass(category_name: str, provider: str):
    """2-pass brainstorm: knowledge first, JSON second."""
    
    # Pass 1 — Pure domain knowledge, no JSON constraint
    knowledge_prompt = f"""You are an expert retail merchandiser.

Category: "{category_name}"

List 5-10 generic product types (NOT specific brands) that are essential accessories, consumables, or complementary items someone buying from this category would also need.

For each item, briefly explain WHY it pairs well (one sentence).

Example for "Flashlights":
- Batteries — most flashlights require replaceable batteries
- Holster — hands-free carry for first responders
- Replacement Bulb — extends flashlight lifespan
- Lanyard — prevents drops during use"""
    
    try:
        raw_knowledge = call_llm_generic(knowledge_prompt, provider=provider, raw=True)
    except Exception as e:
        return [], f"Brainstorm pass 1 failed: {e}"
    
    if not raw_knowledge or len(raw_knowledge.strip()) < 10:
        return [], "Brainstorm pass 1 returned empty response"
    
    # Pass 2 — Pure formatting task (trivial for any model)
    format_prompt = f"""Extract ONLY the product type names from this list and return them as JSON.

{raw_knowledge}

Output JSON ONLY:
{{
    "concepts": ["Product Type 1", "Product Type 2", ...]
}}"""
    
    try:
        response = call_llm_generic(format_prompt, provider=provider)
        concepts = response.get("concepts", [])
        if not concepts:
            return [], "Pass 2 returned empty concepts list"
        return concepts, None
    except Exception as e:
        return [], f"Brainstorm pass 2 (JSON format) failed: {e}"


def _brainstorm_single_pass(category_name: str, provider: str):
    """Original single-pass brainstorm for providers without raw mode."""
    prompt = f"""You are a retail expert.
    
    Category: "{category_name}"
    
    List 5-10 generic product types (NOT specific brands) that are essential accessories, consumables, or complementary items for this category.
    
    Examples:
    - For "Flashlights": ["Batteries", "Holster", "Replacement Bulb", "Lanyard"]
    - For "Tactical Boots": ["Socks", "Insoles", "Boot Laces", "Waterproofing Spray"]
    
    Output JSON ONLY:
    {{
        "concepts": ["Concept 1", "Concept 2", ...]
    }}
    """
    
    try:
        response = call_llm_generic(prompt, provider=provider)
        concepts = response.get("concepts", [])
        if not concepts:
            return [], "LLM returned empty concepts list"
        return concepts, None
    except Exception as e:
        return [], f"Brainstorm failed: {e}"

def discover_dark_horses(
    category_name: str,
    all_categories: List[str],
    provider: str = "local",
    threshold: int = 80
) -> Dict[str, List[Dict]]:
    """
    Full pipeline: Brainstorm -> Match -> Validate.
    
    Returns:
        {
            "pairings": [...],
            "gaps": [...],
            "failures": [
                {"category": str, "stage": str, "error": str},
                ...
            ]
        }
    """
    failures = []
    
    concepts, error = brainstorm_concepts(category_name, provider=provider)
    if error:
        failures.append({
            "category": category_name,
            "stage": "brainstorm",
            "error": error
        })
        return {"pairings": [], "gaps": [], "failures": failures}
    
    matcher = InventoryMatcher(all_categories)
    
    pairings = []
    gaps = []
    
    for concept in concepts:
        match = matcher.find_match(concept, threshold=threshold)
        
        if match:
            target_category = match["name"]
            score = match["score"]
            
            # Validate pairing
            try:
                validation = get_llm_validation(
                    source_category=category_name,
                    target_category=target_category,
                    provider=provider
                )
            except Exception as e:
                failures.append({
                    "category": category_name,
                    "stage": "validation",
                    "error": f"Validation failed for concept '{concept}' -> '{target_category}': {e}"
                })
                continue
            
            if validation.get("valid"):
                pairings.append({
                    "source": category_name,
                    "target": target_category,
                    "concept": concept,
                    "match_score": score,
                    "validation": validation
                })
        else:
            gaps.append({
                "source": category_name,
                "missing_concept": concept
            })
            
    return {
        "pairings": pairings,
        "gaps": gaps,
        "failures": failures
    }