import sys
import json
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from enrichment import EnrichmentService

MOCK_DATA = {
    "item_cooccurrence": [
        {
            "source_sku": "A",
            "rec_sku": "B",
            "copurchase_count": 10,
            "rec_velocity": 5,
            "rec_margin": 0.2
        },
        {
            "source_sku": "A",
            "rec_sku": "C",
            "copurchase_count": 5,
            "rec_velocity": 2,
            "rec_margin": 0.1
        }
    ],
    "category_cooccurrence": [
        {
            "category_id": 100,
            "rec_sku": "D",
            "copurchase_count": 20,
            "rec_velocity": 10,
            "rec_margin": 0.3
        }
    ]
}

@pytest.fixture
def mock_enrichment_file():
    with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_DATA))):
        yield

def test_load_data(mock_enrichment_file):
    """Test loading data on initialization."""
    service = EnrichmentService()
    assert len(service.item_map) > 0
    assert len(service.category_map) > 0

def test_get_item_cooccurrence(mock_enrichment_file):
    service = EnrichmentService()
    results = service.get_item_recommendations("A")
    
    assert len(results) == 2
    assert results[0]["rec_sku"] == "B"  # Sorted by count usually, or just present
    assert results[0]["copurchase_count"] == 10

def test_get_category_cooccurrence(mock_enrichment_file):
    service = EnrichmentService()
    results = service.get_category_recommendations(100)
    
    assert len(results) == 1
    assert results[0]["rec_sku"] == "D"
    assert results[0]["copurchase_count"] == 20

def test_missing_keys(mock_enrichment_file):
    service = EnrichmentService()
    assert service.get_item_recommendations("Z") == []
    assert service.get_category_recommendations(999) == []
