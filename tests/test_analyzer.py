import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Add src and easyupsell to path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "scripts"))

from easyupsell.core.analyzer import find_recommendations_for_category

def test_find_recommendations_with_enrichment():
    # Mock category
    category = {"id": 1, "name": "Test Category", "order_count": 100, "revenue": 5000}
    
    # Mock item
    items = [{
        "id": 10,
        "sku": "SKU123",
        "name": "Test Item",
        "price": 50.0,
        "categories": [1],
        "order_count": 10,
        "units_sold": 5,
        "revenue": 250.0
    }]
    
    id_to_name = {1: "Test Category"}
    
    # Mock enrichment service
    mock_enrichment_service = MagicMock()
    mock_enrichment_service.get_enrichment_for_category_pair.return_value = {
        "copurchase_count": 42,
        "rec_margin": 0.25,
        "rec_velocity": 15
    }
    
    # Mock LLM validation
    with patch("validate_category_pairings.get_llm_validation") as mock_llm:
        mock_llm.return_value = {"valid": True, "confidence": 0.9, "reason": "Tests"}
        
        recs = find_recommendations_for_category(
            category, items, id_to_name,
            enrichment_service=mock_enrichment_service,
            max_items=1
        )
    
    assert len(recs) == 1
    r = recs[0]
    assert r["recommended_sku"] == "SKU123"
    assert r["enrichment_copurchase_count"] == 42
    assert r["enrichment_margin"] == 0.25
    assert r["enrichment_velocity"] == 15
    
    # Verify enrichment service was called with correct args
    mock_enrichment_service.get_enrichment_for_category_pair.assert_called_with(1, "SKU123")

def test_find_recommendations_without_enrichment_service():
    category = {"id": 1, "name": "Test Category", "order_count": 100, "revenue": 5000}
    items = [{
        "id": 10, "sku": "SKU123", "name": "Test Item", "price": 50.0,
        "categories": [1], "order_count": 10, "units_sold": 5, "revenue": 250.0
    }]
    id_to_name = {1: "Test Category"}
    
    with patch("validate_category_pairings.get_llm_validation") as mock_llm:
        mock_llm.return_value = {"valid": True}
        
        recs = find_recommendations_for_category(
            category, items, id_to_name,
            enrichment_service=None,
            max_items=1
        )
    
    assert len(recs) == 1
    assert recs[0]["enrichment_copurchase_count"] == 0
    assert recs[0]["enrichment_margin"] == 0
    assert recs[0]["enrichment_velocity"] == 0
