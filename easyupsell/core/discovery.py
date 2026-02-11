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
    """
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
        return response.get("concepts", [])
    except Exception as e:
        print(f"Error brainstorming for {category_name}: {e}")
        return []

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
            "pairings": [
                {"source": str, "target": str, "concept": str, "score": int, "validation": dict},
                ...
            ],
            "gaps": [
                {"source": str, "missing_concept": str},
                ...
            ]
        }
    """
    concepts = brainstorm_concepts(category_name, provider=provider)
    matcher = InventoryMatcher(all_categories)
    
    pairings = []
    gaps = []
    
    for concept in concepts:
        match = matcher.find_match(concept, threshold=threshold)
        
        if match:
            target_category = match["name"]
            score = match["score"]
            
            # Validate pairing
            validation = get_llm_validation(
                source_category=category_name,
                target_category=target_category,
                provider=provider
            )
            
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
        "gaps": gaps
    }