import sys
from pathlib import Path
from typing import List

# Import generic LLM caller
# Adding scripts to path to import (following existing pattern)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from validate_category_pairings import call_llm_generic

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
