import csv
import pytest
from pathlib import Path
from easyupsell.core.output import write_dark_horse_results, write_catalog_gaps

def test_write_dark_horse_results(tmp_path):
    output_file = tmp_path / "dark_horse_pairings.csv"
    
    pairings = [
        {
            "source": "SourceCat",
            "target": "TargetCat",
            "concept": "Concept",
            "match_score": 90,
            "validation": {
                "valid": True,
                "confidence": 0.9,
                "relationship_type": "Accessory",
                "reason": "Because...",
                "suggested_weight": 80
            }
        }
    ]
    
    write_dark_horse_results(pairings, output_file)
    
    assert output_file.exists()
    
    with open(output_file) as f:
        reader = csv.DictReader(f)
        row = next(reader)
        assert row["source_category"] == "SourceCat"
        assert row["target_category"] == "TargetCat"
        assert row["suggested_weight"] == "80"
        assert row["relationship_type"] == "Accessory"
        assert row["reason"] == "Because..."
        # Optional: check if match_score or concept is saved? Spec says:
        # Columns: source_category, target_category, suggested_weight, relationship_type, reason, llm_model_used
        
        # We might want to save concept too, but spec didn't strictly require it.
        # But for debugging it's useful.

def test_write_catalog_gaps(tmp_path):
    output_file = tmp_path / "catalog_gaps.csv"
    
    gaps = [
        {
            "source": "SourceCat",
            "missing_concept": "Flux Capacitor"
        }
    ]
    
    write_catalog_gaps(gaps, output_file)
    
    assert output_file.exists()
    
    with open(output_file) as f:
        reader = csv.DictReader(f)
        row = next(reader)
        assert row["source_category"] == "SourceCat"
        assert row["missing_product_type"] == "Flux Capacitor"
