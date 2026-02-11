import csv
from pathlib import Path
from typing import List, Dict

def write_dark_horse_results(pairings: List[Dict], output_path: Path):
    """
    Write valid pairings to CSV.
    """
    if not pairings:
        return

    fieldnames = [
        "source_category",
        "target_category",
        "suggested_weight",
        "relationship_type",
        "reason",
        "llm_model_used",
        "concept_matched", # Adding for traceability
        "match_confidence"
    ]
    
    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for p in pairings:
            val = p.get("validation", {})
            writer.writerow({
                "source_category": p.get("source"),
                "target_category": p.get("target"),
                "suggested_weight": val.get("suggested_weight", 50),
                "relationship_type": val.get("relationship_type", "unknown"),
                "reason": val.get("reason", ""),
                "llm_model_used": "local", # Placeholder, ideally passed down
                "concept_matched": p.get("concept"),
                "match_confidence": p.get("match_score")
            })

def write_catalog_gaps(gaps: List[Dict], output_path: Path):
    """
    Write catalog gaps to CSV.
    """
    if not gaps:
        return

    fieldnames = [
        "source_category",
        "missing_product_type",
        "suggested_weight",
        "reason"
    ]
    
    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for g in gaps:
            writer.writerow({
                "source_category": g.get("source"),
                "missing_product_type": g.get("missing_concept"),
                "suggested_weight": 0, # Gaps have no weight yet
                "reason": "Concept not found in inventory"
            })
