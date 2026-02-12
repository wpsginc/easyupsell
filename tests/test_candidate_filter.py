"""
Unit tests for candidate_filter.filter_candidates().

Pure logic tests — no LLM, no API calls.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from candidate_filter import filter_candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_category(cat_id: int = 100, name: str = "Fire Helmets") -> dict:
    return {"id": cat_id, "name": name}


def _make_item(name: str, categories: list[int] | None = None, sku: str = "SKU") -> dict:
    return {
        "name": name,
        "sku": sku,
        "categories": categories or [],
        "price": 50.0,
    }


# ---------------------------------------------------------------------------
# Test Cases (7 per SDD)
# ---------------------------------------------------------------------------

def test_exact_name_match_excluded():
    """Case 1: Product named exactly 'Fire Helmets' for 'Fire Helmets' category → excluded."""
    cat = _make_category(100, "Fire Helmets")
    items = [_make_item("Fire Helmets", [100])]
    result = filter_candidates(cat, items)
    assert len(result) == 0, f"Expected 0 items, got {len(result)}"


def test_substring_name_match_included():
    """Case 2: 'Streamlight Vantage Helmet Light' for 'Fire Helmets' → included, same_category=True."""
    cat = _make_category(100, "Fire Helmets")
    items = [_make_item("Streamlight Vantage Helmet Light", [100])]
    result = filter_candidates(cat, items)
    assert len(result) == 1, f"Expected 1 item, got {len(result)}"
    assert result[0]["same_category"] is True


def test_same_category_id_different_product():
    """Case 3: 'Helmet Shield' in Fire Helmets category → included, same_category=True."""
    cat = _make_category(100, "Fire Helmets")
    items = [_make_item("Helmet Shield", [100, 200])]
    result = filter_candidates(cat, items)
    assert len(result) == 1
    assert result[0]["same_category"] is True


def test_different_category():
    """Case 4: Item in completely different category → included, same_category=False."""
    cat = _make_category(100, "Fire Helmets")
    items = [_make_item("Tactical Belt", [200])]
    result = filter_candidates(cat, items)
    assert len(result) == 1
    assert result[0]["same_category"] is False


def test_item_no_categories():
    """Case 5: Item with no categories → included, same_category=False."""
    cat = _make_category(100, "Fire Helmets")
    items = [_make_item("Mystery Product", [])]
    result = filter_candidates(cat, items)
    assert len(result) == 1
    assert result[0]["same_category"] is False


def test_empty_items_list():
    """Case 6: Empty items list → returns []."""
    cat = _make_category(100, "Fire Helmets")
    result = filter_candidates(cat, [])
    assert result == []


def test_exclude_exact_match_disabled():
    """Case 7: exclude_exact_match=False → exact name match is KEPT."""
    cat = _make_category(100, "Fire Helmets")
    items = [_make_item("Fire Helmets", [100])]
    result = filter_candidates(cat, items, exclude_exact_match=False)
    assert len(result) == 1
    assert result[0]["same_category"] is True


def test_case_insensitive_exact_match():
    """Bonus: Exact match should be case-insensitive."""
    cat = _make_category(100, "Fire Helmets")
    items = [_make_item("fire helmets", [100])]
    result = filter_candidates(cat, items)
    assert len(result) == 0


def test_original_items_not_mutated():
    """Bonus: Original item dicts should not have 'same_category' added."""
    cat = _make_category(100, "Fire Helmets")
    items = [_make_item("Helmet Light", [100])]
    filter_candidates(cat, items)
    assert "same_category" not in items[0], "filter_candidates mutated the original item dict"


def test_reproduction_same_category_filtering():
    """
    Reproduction: Confirm that products in the same category ARE currently filtered out
    (unless they are whitelisted or logic is already permissive).
    
    The goal of the track is to REMOVE this restriction.
    So initially, we expect this test to FAIL if the filter is already permissive,
    or PASS if the filter IS working (blocking the items).
    
    Wait, the spec says: "The current recommendation engine proactively filters out candidate products that belong to the same category".
    
    Let's check the current behavior. If I add a test asserting that same-cat items ARE returned,
    it should FAIL if the filter is active.
    """
    cat = _make_category(100, "Fire Helmets")
    # Item in the same category (100)
    items = [_make_item("Helmet Light", [100])]
    
    # We want this to return 1 item eventually. 
    # If the bug (feature to be changed) exists, this might return 0.
    result = filter_candidates(cat, items)
    
    # For TDD Red Phase: Assert that we get the item back.
    # If the code currently blocks it, this assertion will fail.
    assert len(result) == 1, "Expected same-category item to be returned, but it was filtered out."