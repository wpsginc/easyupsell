from typing import List, Optional, Dict
from rapidfuzz import process, fuzz

class InventoryMatcher:
    def __init__(self, categories: List[str]):
        """
        Initialize with a list of all available category names.
        """
        self.categories = categories

    def find_match(self, concept: str, threshold: int = 80) -> Optional[Dict[str, any]]:
        """
        Find the best matching category for a concept.
        Returns dict with match details or None if below threshold.
        """
        if not self.categories:
            return None
            
        result = process.extractOne(
            concept, 
            self.categories, 
            scorer=fuzz.WRatio
        )
        
        if not result:
            return None
            
        # rapidfuzz extractOne returns (match, score, index)
        match_name, score, _ = result
        
        if score >= threshold:
            return {
                "name": match_name,
                "score": score
            }
            
        return None
