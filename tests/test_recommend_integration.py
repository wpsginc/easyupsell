import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from recommend_items_full import find_recommendations_for_category
from enrichment import EnrichmentService

@pytest.fixture
def mock_enrichment():
    service = Mock(spec=EnrichmentService)
    service.category_map = {
        10: [
            {"rec_sku": "SKU1", "copurchase_count": 50, "rec_margin": 0.4, "rec_velocity": 100}
        ]
    }
    return service

@patch("recommend_items_full.get_batch_llm_validation")
def test_find_recommendations_with_enrichment(mock_validation, mock_enrichment):
    """Test that recommendations are enriched before sending to LLM."""
    
    # Setup
    category = {"id": 10, "name": "Test Category", "order_count": 100, "revenue": 1000}
    items = [
        {"name": "Item 1", "sku": "SKU1", "brand": "Brand A", "price": 50.0, "order_count": 10, "units_sold": 10, "revenue": 500, "categories": [1]},
        {"name": "Item 2", "sku": "SKU2", "brand": "Brand B", "price": 20.0, "order_count": 5, "units_sold": 5, "revenue": 100, "categories": [2]}
    ]
    id_to_name = {1: "Cat 1", 2: "Cat 2"}
    
    # Mock LLM response
    mock_validation.return_value = [
        {"valid": True, "confidence": 0.9, "item_sku": "SKU1"},
        {"valid": False, "confidence": 0.1, "item_sku": "SKU2"}
    ]
    
    # Execute
    recs = find_recommendations_for_category(
        category, items, id_to_name, mock_enrichment, provider="test"
    )
    
    # Verify LLM was called with enriched data
    call_args = mock_validation.call_args
    # call_args[0] is positional args. Arg 1 is batch_items
    batch_items = call_args[0][1]
    
    item1_data = next(i for i in batch_items if i["sku"] == "SKU1")
    assert "copurchase_text" in item1_data
    assert "Co-purchased with 'Test Category': 50 times" in item1_data["copurchase_text"]
    assert item1_data["margin_pct"] == 0.4
    
    item2_data = next(i for i in batch_items if i["sku"] == "SKU2")
    assert "copurchase_text" not in item2_data
    
    # Verify Output
    assert len(recs) == 2
    assert recs[0]["recommended_sku"] == "SKU1"
