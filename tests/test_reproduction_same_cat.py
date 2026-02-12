
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from candidate_filter import filter_candidates

def _make_category(cat_id: int = 100, name: str = "Fire Helmets") -> dict:
    return {"id": cat_id, "name": name}

def _make_item(name: str, categories: list[int] | None = None) -> dict:
    return {
        "name": name,
        "sku": "SKU",
        "categories": categories or [],
        "price": 50.0,
    }

def test_repro_same_category_allowed():
    """
    Verify that items in the same category are NOT filtered out.
    """
    cat = _make_category(100, "Fire Helmets")
    # Item in the same category (100)
    item = _make_item("Helmet Light", [100])
    items = [item]
    
    result = filter_candidates(cat, items)
    
    # Assert we get the item back
    assert len(result) == 1
    assert result[0]["same_category"] is True
